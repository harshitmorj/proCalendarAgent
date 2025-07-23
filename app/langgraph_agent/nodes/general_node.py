"""
General Node - Handles general conversations and non-calendar tasks
"""

from typing import Dict, Any
from app.langgraph_agent.llm_wrapper import LLMWrapper

def general_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle general conversations, help requests, and non-calendar tasks
    """
    message = state.get("message", "")
    user_id = state.get("user_id")
    
    llm = LLMWrapper()
    
    # System prompt for general assistant behavior
    system_prompt = """You are a helpful calendar assistant. The user's message doesn't require calendar operations, so provide a friendly and helpful general response.

You can:
- Answer questions about calendar functionality
- Provide help with using the calendar agent
- Engage in brief friendly conversation
- Explain what calendar operations are available

Available calendar operations:
- Search for events: "show me meetings tomorrow"  
- Create events: "schedule meeting with John at 2pm"
- Update events: "move my 3pm meeting to 4pm"
- Delete events: "delete meetings with Soham"
- Schedule multi-person meetings: "find time for team meeting next week"

Keep responses concise and helpful. Always offer to help with calendar tasks.
"""
    
    try:
        response = llm.invoke([system_prompt, f"User: {message}"])
        
        return {
            **state,
            "response": response,
            "status": "completed"
        }
        
    except Exception as e:
        # Fallback response
        if any(word in message.lower() for word in ["help", "what", "how", "?"]):
            response = """I'm your calendar assistant! I can help you with:

📅 **Calendar Operations:**
- Search events: "show me meetings tomorrow"
- Create events: "schedule lunch with John at 1pm" 
- Update events: "move my meeting to 3pm"
- Delete events: "delete all meetings with Soham"
- Schedule meetings: "find time for team meeting next week"

💬 **Just ask me naturally!** I understand requests like:
- "What do I have this afternoon?"
- "Cancel my meeting with Sarah"
- "Book a 30-minute call with the team"
- "Move tomorrow's standup to 10am"

How can I help you with your calendar today?"""
        else:
            response = f"I understand you said: '{message}'. I'm primarily a calendar assistant. How can I help you manage your schedule today?"
        
        return {
            **state,
            "response": response,
            "status": "completed"
        }
