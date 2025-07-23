"""
Schedule Node - Handles multi-user meeting scheduling with availability checking
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.langgraph_agent.schemas.router_schema import TaskStatus
from app.langgraph_agent.llm_wrapper import LLMWrapper
import json

def schedule_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Schedule meetings considering multiple participants' availability
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
            "response": "Error: User ID is required for scheduling operations",
            "error": "Missing user_id"
        }
    
    try:
        # Initialize integrated calendar
        integrated_cal = IntegratedCalendar(user_id=user_id, db_session=db_session)
        
        # Extract scheduling parameters
        schedule_params = extract_schedule_parameters(message, action, task_context, current_subtask_id or "")
        
        if not schedule_params:
            return {
                **state,
                "response": "Could not extract scheduling details. Please specify participants, duration, and preferred time range.",
                "error": "Missing schedule parameters"
            }
        
        # Get available time slots
        availability_results = find_available_slots(
            integrated_cal, 
            schedule_params
        )
        
        if not availability_results["available_slots"]:
            response = "❌ No available time slots found for all participants."
            if availability_results["busy_periods"]:
                response += "\\n\\nBusy periods found:"
                for period in availability_results["busy_periods"][:5]:
                    response += f"\\n- {period.get('start', 'Unknown time')}: {period.get('title', 'Busy')}"
        else:
            # Create meeting at the best available slot
            best_slot = availability_results["available_slots"][0]
            
            event_data = {
                "title": schedule_params.get("title", "Team Meeting"),
                "description": schedule_params.get("description", ""),
                "start": best_slot["start"],
                "end": best_slot["end"],
                "location": schedule_params.get("location", ""),
                "timezone": "UTC",
                "attendees": schedule_params.get("attendees", [])
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
            
            # Create the meeting
            target_account = connected_accounts[0]
            created_event = integrated_cal.create_event(
                provider=target_account['provider'],
                account_email=target_account['account_email'],
                event_data=event_data
            )
            
            # Update task context
            if task_context and current_subtask_id:
                current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
                if current_task:
                    current_task.status = TaskStatus.COMPLETED
                    current_task.result = {
                        "summary": f"Scheduled meeting: {event_data['title']}",
                        "event_id": created_event.get('id', ''),
                        "time_slot": best_slot
                    }
            
            response = f"✅ Successfully scheduled meeting:\\n"
            response += f"📝 **{event_data['title']}**\\n"
            response += f"📅 {best_slot['start']} - {best_slot['end']}\\n"
            if event_data.get('location'):
                response += f"📍 {event_data['location']}\\n"
            response += f"👥 Participants: {', '.join(schedule_params.get('attendees', []))}\\n"
            response += f"🏢 {target_account['provider']} ({target_account['account_email']})"
            
            if len(availability_results["available_slots"]) > 1:
                response += f"\\n\\n📊 Found {len(availability_results['available_slots'])} available time slots."
        
        return {
            **state,
            "response": response,
            "task_context": task_context,
            "availability_results": availability_results
        }
        
    except Exception as e:
        error_msg = f"Scheduling failed: {str(e)}"
        
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

def extract_schedule_parameters(message: str, action: str, task_context, current_subtask_id: str) -> Dict[str, Any]:
    """
    Extract scheduling parameters from message
    """
    # If this is part of a compound task, get parameters from subtask
    if task_context and current_subtask_id:
        current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
        if current_task and current_task.parameters:
            return current_task.parameters
    
    llm = LLMWrapper()
    
    system_prompt = """Extract scheduling parameters from this meeting request.
    
    Return JSON with:
    {
        "title": "meeting title",
        "description": "meeting description",
        "attendees": ["email1@domain.com", "participant name"],
        "duration_minutes": 60,
        "preferred_start_date": "YYYY-MM-DD",
        "preferred_end_date": "YYYY-MM-DD", 
        "preferred_time_start": "HH:MM",
        "preferred_time_end": "HH:MM",
        "location": "location if specified"
    }
    
    For attendees, extract names or email addresses mentioned.
    Default duration is 60 minutes.
    Use working hours (9-17) if no time preference specified.
    
    Examples:
    - "Schedule meeting with John tomorrow" → {"attendees": ["John"], "preferred_start_date": "tomorrow"}
    - "Book 30min call with team next week" → {"duration_minutes": 30, "preferred_start_date": "next week"}
    """
    
    try:
        full_text = f"{message} {action}".strip()
        response = llm.invoke([system_prompt, f"Request: {full_text}"])
        
        # Clean and parse JSON response
        response_clean = response.strip()
        if response_clean.startswith('```json'):
            response_clean = response_clean[7:-3]
        
        params = json.loads(response_clean)
        
        # Set defaults
        if not params.get("duration_minutes"):
            params["duration_minutes"] = 60
        
        if not params.get("preferred_time_start"):
            params["preferred_time_start"] = "09:00"
        
        if not params.get("preferred_time_end"):
            params["preferred_time_end"] = "17:00"
        
        # Parse date strings
        if params.get("preferred_start_date"):
            params["preferred_start_date"] = parse_date_string(params["preferred_start_date"])
        else:
            params["preferred_start_date"] = datetime.now().date()
        
        if params.get("preferred_end_date"):
            params["preferred_end_date"] = parse_date_string(params["preferred_end_date"])
        else:
            # Default to 1 week from start date
            start_date = params["preferred_start_date"]
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date).date()
            params["preferred_end_date"] = start_date + timedelta(days=7)
        
        return params
        
    except Exception as e:
        # Fallback extraction
        return {
            "title": "Meeting",
            "duration_minutes": 60,
            "preferred_start_date": datetime.now().date(),
            "preferred_end_date": datetime.now().date() + timedelta(days=7),
            "preferred_time_start": "09:00",
            "preferred_time_end": "17:00",
            "attendees": extract_attendees_from_message(message)
        }

def extract_attendees_from_message(message: str) -> List[str]:
    """
    Simple attendee extraction from message
    """
    attendees = []
    message_lower = message.lower()
    
    # Look for patterns like "with John", "and Mary", etc.
    import re
    
    # Pattern for "with [name]"
    with_pattern = r'with\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)'
    matches = re.findall(with_pattern, message, re.IGNORECASE)
    attendees.extend(matches)
    
    # Pattern for email addresses
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_matches = re.findall(email_pattern, message)
    attendees.extend(email_matches)
    
    return list(set(attendees))  # Remove duplicates

def find_available_slots(integrated_cal: IntegratedCalendar, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find available time slots for all participants
    """
    try:
        start_date = params["preferred_start_date"]
        end_date = params["preferred_end_date"]
        duration_minutes = params["duration_minutes"]
        
        # Convert to datetime objects
        if isinstance(start_date, str):
            start_datetime = datetime.fromisoformat(start_date)
        else:
            start_datetime = datetime.combine(start_date, datetime.min.time())
        
        if isinstance(end_date, str):
            end_datetime = datetime.fromisoformat(end_date)
        else:
            end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Get busy times for the date range
        busy_times = integrated_cal.get_busy_times(start_datetime, end_datetime)
        
        # Generate potential time slots
        available_slots = []
        current_date = start_datetime.date()
        
        while current_date <= end_datetime.date():
            # Check each hour within working hours
            for hour in range(9, 17):  # 9 AM to 5 PM
                slot_start = datetime.combine(current_date, datetime.min.time().replace(hour=hour))
                slot_end = slot_start + timedelta(minutes=duration_minutes)
                
                # Check if this slot conflicts with busy times
                is_free = True
                for busy_period in busy_times:
                    busy_start = datetime.fromisoformat(busy_period.get("start", ""))
                    busy_end = datetime.fromisoformat(busy_period.get("end", ""))
                    
                    # Check for overlap
                    if (slot_start < busy_end and slot_end > busy_start):
                        is_free = False
                        break
                
                if is_free:
                    available_slots.append({
                        "start": slot_start.isoformat(),
                        "end": slot_end.isoformat(),
                        "date": current_date.isoformat(),
                        "duration_minutes": duration_minutes
                    })
            
            current_date += timedelta(days=1)
        
        return {
            "available_slots": available_slots[:10],  # Limit to first 10 slots
            "busy_periods": busy_times,
            "search_range": {
                "start": start_datetime.isoformat(),
                "end": end_datetime.isoformat()
            }
        }
        
    except Exception as e:
        return {
            "available_slots": [],
            "busy_periods": [],
            "error": str(e)
        }

def parse_date_string(date_str: str):
    """
    Parse natural language date strings to date objects
    """
    date_str = date_str.lower().strip()
    now = datetime.now()
    
    if date_str in ["today"]:
        return now.date()
    elif date_str in ["tomorrow"]:
        return (now + timedelta(days=1)).date()
    elif "next week" in date_str:
        days_ahead = 7 - now.weekday()
        return (now + timedelta(days=days_ahead)).date()
    elif "week" in date_str:
        return (now + timedelta(days=7)).date()
    else:
        try:
            return datetime.fromisoformat(date_str).date()
        except:
            return now.date()
