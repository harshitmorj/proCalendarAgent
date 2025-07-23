"""
RSVP Node - Handles queries about event attendance and RSVP statuses
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.langgraph_agent.schemas.router_schema import SearchResult, TaskStatus
from app.langgraph_agent.llm_wrapper import LLMWrapper
from app.database.models import CalendarEvent, EventAttendee, RSVPStatus
from sqlalchemy.orm import joinedload

def rsvp_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle RSVP-related queries like "who is attending", "who declined", etc.
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
            "response": "Error: User ID is required for RSVP operations",
            "error": "Missing user_id"
        }
    
    try:
        # Extract RSVP query parameters
        rsvp_params = extract_rsvp_parameters(message, action)
        
        # Initialize integrated calendar to find events
        integrated_cal = IntegratedCalendar(user_id=user_id, db_session=db_session)
        
        # Find events based on query
        events = []
        if rsvp_params.get("event_query"):
            events = integrated_cal.search_events(
                query=rsvp_params["event_query"],
                limit=10
            )
        elif rsvp_params.get("start_date") or rsvp_params.get("end_date"):
            start_date = rsvp_params.get("start_date", datetime.now())
            end_date = rsvp_params.get("end_date", start_date + timedelta(days=7))
            events = integrated_cal.get_all_events(
                start_date=start_date,
                end_date=end_date,
                max_results=10
            )
        else:
            # Default: look at upcoming events
            events = integrated_cal.get_all_events(
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=30),
                max_results=10
            )
        
        if not events:
            return {
                **state,
                "response": "No events found to check RSVP status for.",
                "rsvp_data": []
            }
        
        # Process RSVP information for each event
        rsvp_results = []
        requested_status = rsvp_params.get("status_filter")
        
        for event in events:
            # For now, we'll extract attendee info from the event data
            # In a full implementation, this would query the EventAttendee table
            attendees_info = extract_attendees_from_event(event)
            
            if requested_status:
                # Filter by requested status
                filtered_attendees = [a for a in attendees_info 
                                    if a.get("status", "").lower() == requested_status.lower()]
                if filtered_attendees:
                    rsvp_results.append({
                        "event": event,
                        "attendees": filtered_attendees,
                        "status_filter": requested_status
                    })
            else:
                # Show all attendees with their statuses
                rsvp_results.append({
                    "event": event,
                    "attendees": attendees_info,
                    "status_filter": None
                })
        
        # Generate response
        response = generate_rsvp_response(rsvp_results, rsvp_params)
        
        # Update task context if this is part of a compound task
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task:
                current_task.status = TaskStatus.COMPLETED
                current_task.result = {
                    "summary": f"Found RSVP info for {len(rsvp_results)} events",
                    "count": len(rsvp_results)
                }
        
        return {
            **state,
            "response": response,
            "rsvp_data": rsvp_results,
            "task_context": task_context
        }
        
    except Exception as e:
        error_msg = f"RSVP query failed: {str(e)}"
        
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

def extract_rsvp_parameters(message: str, action: str) -> Dict[str, Any]:
    """
    Extract RSVP query parameters from message
    """
    params = {}
    message_lower = message.lower()
    
    # Determine what status they're asking about (order matters for specificity)
    if any(word in message_lower for word in ["tentative", "maybe", "might", "tentatively", "possibly"]):
        params["status_filter"] = "tentative"
    elif any(phrase in message_lower for phrase in ["hasn't responded", "haven't responded", "didn't respond", "no response", "pending"]):
        params["status_filter"] = "pending"
    elif any(word in message_lower for word in ["attending", "accepted", "going", "will be there", "coming"]):
        params["status_filter"] = "accepted"
    elif any(word in message_lower for word in ["declined", "not attending", "not going", "can't make it", "won't be there"]):
        params["status_filter"] = "declined"
    
    # Extract event search terms using multiple patterns
    event_query = None
    
    # Pattern 1: "who is attending [the] [event name]"
    patterns = [
        r"attending\s+(?:the\s+)?(.+?)(?:\?|$)",
        r"declined\s+(?:the\s+)?(.+?)(?:\?|$)", 
        r"going\s+to\s+(?:the\s+)?(.+?)(?:\?|$)",
        r"for\s+(?:the\s+)?(.+?)(?:\?|$)",
        r"rsvp\s+(?:for\s+)?(?:the\s+)?(.+?)(?:\?|$)",
        r"maybe\s+attending\s+(?:the\s+)?(.+?)(?:\?|$)",
        r"responded\s+to\s+(?:the\s+)?(.+?)(?:\?|$)"
    ]
    
    import re
    for pattern in patterns:
        match = re.search(pattern, message_lower)
        if match:
            event_query = match.group(1).strip()
            # Clean up common words
            event_query = re.sub(r'\b(the|my|our|this|that|invitation)\b', '', event_query).strip()
            if event_query:
                params["event_query"] = event_query
                break
    
    # Fallback: Look for specific event keywords
    if not event_query:
        event_keywords = ["meeting", "call", "standup", "review", "lunch", "dinner", "appointment", "event", "session"]
        for keyword in event_keywords:
            if keyword in message_lower:
                params["event_query"] = keyword
                break
    
    return params

def extract_attendees_from_event(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract attendee information from event data
    Supports both Google Calendar and Microsoft Graph API formats
    """
    attendees = []
    
    # Auto-detect provider based on event structure
    provider = event.get("provider", "").lower()
    if not provider:
        # Auto-detect based on event structure
        if "summary" in event or any("responseStatus" in att for att in event.get("attendees", []) if isinstance(att, dict)):
            provider = "google"
        elif "subject" in event or any("emailAddress" in att for att in event.get("attendees", []) if isinstance(att, dict)):
            provider = "microsoft"
    
    # Get attendees from event data
    event_attendees = event.get("attendees", [])
    
    for attendee in event_attendees:
        if isinstance(attendee, dict):
            if provider == "google":
                # Google Calendar format
                attendee_info = {
                    "email": attendee.get("email", ""),
                    "name": attendee.get("displayName", attendee.get("email", "")),
                    "status": map_google_status_to_rsvp(attendee.get("responseStatus", "needsAction")),
                    "organizer": attendee.get("organizer", False),
                    "optional": attendee.get("optional", False)
                }
            elif provider == "microsoft":
                # Microsoft Graph API format
                email_addr = attendee.get("emailAddress", {})
                attendee_info = {
                    "email": email_addr.get("address", ""),
                    "name": email_addr.get("name", email_addr.get("address", "")),
                    "status": map_microsoft_status_to_rsvp(attendee.get("status", {}).get("response", "none")),
                    "organizer": attendee.get("type", "") == "required" and attendee.get("status", {}).get("response") == "organizer",
                    "optional": attendee.get("type", "") == "optional"
                }
            else:
                # Generic format fallback
                attendee_info = {
                    "email": attendee.get("email", ""),
                    "name": attendee.get("displayName", attendee.get("name", attendee.get("email", ""))),
                    "status": "no_response",
                    "organizer": attendee.get("organizer", False),
                    "optional": attendee.get("optional", False)
                }
            
            attendees.append(attendee_info)
        elif isinstance(attendee, str):
            # Simple email string
            attendees.append({
                "email": attendee,
                "name": attendee,
                "status": "no_response",
                "organizer": False,
                "optional": False
            })
    
    return attendees

def map_google_status_to_rsvp(google_status: str) -> str:
    """Map Google Calendar response status to our RSVP enum"""
    mapping = {
        "accepted": "accepted",
        "declined": "declined", 
        "tentative": "tentative",
        "needsAction": "pending"
    }
    return mapping.get(google_status, "no_response")

def map_microsoft_status_to_rsvp(microsoft_status: str) -> str:
    """Map Microsoft Graph API response status to our RSVP enum"""
    mapping = {
        "accepted": "accepted",
        "declined": "declined",
        "tentativelyAccepted": "tentative",
        "notResponded": "pending",
        "none": "no_response",
        "organizer": "accepted"  # Organizer is typically attending
    }
    return mapping.get(microsoft_status, "no_response")

def generate_rsvp_response(rsvp_results: List[Dict[str, Any]], params: Dict[str, Any]) -> str:
    """
    Generate a human-readable response about RSVP status
    """
    if not rsvp_results:
        return "No events found with attendee information."
    
    status_filter = params.get("status_filter")
    response = ""
    
    if status_filter:
        # Focused response on specific status
        status_name = {
            "accepted": "attending",
            "declined": "not attending", 
            "tentative": "tentatively attending",
            "pending": "haven't responded yet"
        }.get(status_filter, status_filter)
        
        response += f"📋 **People who are {status_name}:**\n\n"
        
        for result in rsvp_results:
            event = result["event"]
            attendees = result["attendees"]
            
            if attendees:
                response += f"**{event.get('title', 'Untitled Event')}** ({event.get('start', 'No time')}):\n"
                for attendee in attendees:
                    name = attendee.get("name", attendee.get("email", "Unknown"))
                    response += f"  • {name}\n"
                response += "\n"
    else:
        # General RSVP summary
        response += "📊 **RSVP Summary:**\n\n"
        
        for result in rsvp_results:
            event = result["event"]
            attendees = result["attendees"]
            
            response += f"**{event.get('title', 'Untitled Event')}** ({event.get('start', 'No time')}):\n"
            
            # Group by status
            status_groups = {}
            for attendee in attendees:
                status = attendee.get("status", "no_response")
                if status not in status_groups:
                    status_groups[status] = []
                status_groups[status].append(attendee.get("name", attendee.get("email", "Unknown")))
            
            for status, names in status_groups.items():
                status_emoji = {
                    "accepted": "✅",
                    "declined": "❌", 
                    "tentative": "❓",
                    "pending": "⏳",
                    "no_response": "⏳"
                }.get(status, "📝")
                
                status_label = {
                    "accepted": "Attending",
                    "declined": "Not attending",
                    "tentative": "Tentative", 
                    "pending": "Pending",
                    "no_response": "No response"
                }.get(status, status.title())
                
                response += f"  {status_emoji} **{status_label}** ({len(names)}): {', '.join(names)}\n"
            
            response += "\n"
    
    return response
