"""
Create Node - Handles event creation operations
"""

from typing import Dict, Any
from datetime import datetime
from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.langgraph_agent.schemas.router_schema import TaskStatus
from app.langgraph_agent.llm_wrapper import LLMWrapper
import json

def create_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create new calendar events
    """
    user_id = state.get("user_id")
    db_session = state.get("db_session")
    message = state.get("message", "")
    action = state.get("action", "")
    task_context = state.get("task_context")
    current_subtask_id = state.get("current_subtask_id")
    
    if not user_id:
        return {
            **state,
            "response": "Error: User ID is required for create operations",
            "error": "Missing user_id"
        }
    
    try:
        # Initialize integrated calendar
        integrated_cal = IntegratedCalendar(user_id=user_id, db_session=db_session)
        
        # Extract event data from message
        event_data = extract_event_data(message, action, task_context, current_subtask_id or "")
        
        if not event_data:
            return {
                **state,
                "response": "Could not extract event details from your message. Please provide title, date, and time.",
                "error": "Missing event data"
            }
        
        # Get user's calendar accounts
        accounts_summary = integrated_cal.get_calendar_accounts_summary()
        connected_accounts = [acc for acc in accounts_summary if acc['status'] == 'connected']
        
        if not connected_accounts:
            return {
                **state,
                "response": "No connected calendar accounts found. Please connect a calendar first.",
                "error": "No calendar accounts"
            }
        
        # Use the first connected account (or let user choose in future enhancement)
        target_account = connected_accounts[0]
        
        # Create the event
        created_event = integrated_cal.create_event(
            provider=target_account['provider'],
            account_email=target_account['account_email'],
            event_data=event_data
        )
        
        # Update task context if this is part of a compound task
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task:
                current_task.status = TaskStatus.COMPLETED
                current_task.result = {
                    "summary": f"Created event: {event_data.get('title', 'Untitled')}",
                    "event_id": created_event.get('id', ''),
                    "event_data": event_data
                }
        
        # Generate response
        response = f"✅ Successfully created event:\n"
        response += f"📝 **{event_data.get('title', 'Untitled')}**\n"
        response += f"📅 {event_data.get('start', 'No date/time')}\n"
        if event_data.get('location'):
            response += f"📍 {event_data['location']}\n"
        response += f"🏢 {target_account['provider']} ({target_account['account_email']})\n"
        if created_event.get('id'):
            response += f"🆔 Event ID: {created_event['id']}"
        
        return {
            **state,
            "response": response,
            "task_context": task_context,
            "created_event": created_event
        }
        
    except Exception as e:
        error_msg = f"Event creation failed: {str(e)}"
        
        # Update task context with error
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task:
                current_task.status = TaskStatus.FAILED
                current_task.error = error_msg
        
        return {
            **state,
            "response": error_msg,
            "error": error_msg,
            "task_context": task_context
        }

def extract_event_data(message: str, action: str, task_context, current_subtask_id: str) -> Dict[str, Any]:
    """
    Extract event data from message using LLM
    """
    # If this is part of a compound task, get parameters from subtask
    if task_context and current_subtask_id:
        current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
        if current_task and current_task.parameters:
            return current_task.parameters
    
    llm = LLMWrapper()
    
    system_prompt = """Extract event details from this calendar creation request.
    
    Return JSON with:
    {
        "title": "event title",
        "description": "event description",
        "start": "YYYY-MM-DDTHH:MM:SS",
        "end": "YYYY-MM-DDTHH:MM:SS", 
        "location": "location if mentioned",
        "timezone": "UTC"
    }
    
    For dates/times:
    - Use current date if no date specified
    - Default to 1-hour duration if no end time
    - Use 24-hour format
    - Convert relative dates (tomorrow, next week, etc.)
    
    Examples:
    - "Meeting tomorrow at 2pm" → start: "2024-12-25T14:00:00", end: "2024-12-25T15:00:00"
    - "Lunch with John" → title: "Lunch with John", duration: 1 hour from now
    """
    
    try:
        full_text = f"{message} {action}".strip()
        response = llm.invoke([system_prompt, f"Request: {full_text}"])
        
        # Clean and parse JSON response
        response_clean = response.strip()
        if response_clean.startswith('```json'):
            response_clean = response_clean[7:-3]
        
        event_data = json.loads(response_clean)
        
        # Validate required fields
        if not event_data.get("title"):
            event_data["title"] = "New Event"
        
        # Ensure start time exists
        if not event_data.get("start"):
            # Default to current time + 1 hour
            now = datetime.now()
            event_data["start"] = (now.replace(minute=0, second=0, microsecond=0)).isoformat()
        
        # Ensure end time exists
        if not event_data.get("end"):
            start_dt = datetime.fromisoformat(event_data["start"].replace("Z", ""))
            end_dt = start_dt.replace(hour=start_dt.hour + 1)
            event_data["end"] = end_dt.isoformat()
        
        # Set default timezone
        if not event_data.get("timezone"):
            event_data["timezone"] = "UTC"
        
        return event_data
        
    except Exception as e:
        # Fallback: extract basic information
        title = extract_title_from_message(message)
        now = datetime.now()
        start_time = now.replace(minute=0, second=0, microsecond=0) 
        end_time = start_time.replace(hour=start_time.hour + 1)
        
        return {
            "title": title or "New Event",
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "timezone": "UTC"
        }

def extract_title_from_message(message: str) -> str:
    """
    Simple title extraction fallback
    """
    # Remove common calendar keywords
    keywords = ["create", "add", "new", "schedule", "book", "meeting", "event", "appointment"]
    words = message.split()
    
    filtered_words = []
    for word in words:
        if word.lower().strip(".,!?") not in keywords:
            filtered_words.append(word)
    
    title = " ".join(filtered_words).strip()
    return title if title else "New Event"
