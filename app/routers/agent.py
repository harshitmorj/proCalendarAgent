from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database.database import get_db
from ..database.models import User, ChatSession, ChatMessage
from ..auth.dependencies import get_current_user
from ..langgraph_agent.agent import CalendarAgent
from pydantic import BaseModel
import uuid
from typing import List, Optional

router = APIRouter(prefix="/agent", tags=["agent"])

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

class ChatHistoryResponse(BaseModel):
    id: int
    message: str
    response: str
    timestamp: str
    
    class Config:
        from_attributes = True

@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat with the calendar agent"""
    try:
        # Get or create chat session
        session_id = chat_request.session_id or str(uuid.uuid4())
        
        chat_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not chat_session:
            chat_session = ChatSession(
                user_id=current_user.id,
                session_id=session_id
            )
            db.add(chat_session)
            db.commit()
            db.refresh(chat_session)
        
        # Process message with the agent (create fresh instance to get updated API keys)
        agent = CalendarAgent()
        response = agent.process_message(
            message=chat_request.message,
            user_id=current_user.id,
            db_session=db
        )
        
        # Save chat message and response
        chat_message = ChatMessage(
            chat_session_id=chat_session.id,
            message=chat_request.message,
            response=response
        )
        db.add(chat_message)
        db.commit()
        
        return ChatResponse(response=response, session_id=session_id)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.get("/chat/history/{session_id}", response_model=List[ChatHistoryResponse])
async def get_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history for a session"""
    chat_session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.chat_session_id == chat_session.id
    ).order_by(ChatMessage.timestamp.asc()).all()
    
    return messages

@router.get("/chat/sessions")
async def get_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all chat sessions for the current user"""
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.created_at.desc()).all()
    
    session_data = []
    for session in sessions:
        # Get the last message from this session
        last_message = db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session.id
        ).order_by(ChatMessage.timestamp.desc()).first()
        
        session_data.append({
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "last_message": last_message.message if last_message else "No messages",
            "last_activity": last_message.timestamp.isoformat() if last_message else session.created_at.isoformat()
        })
    
    return {"sessions": session_data}
