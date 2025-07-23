"""
Update Node - Handles event update operations
"""

from typing import Dict, Any
from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.langgraph_agent.schemas.router_schema import TaskStatus
from app.langgraph_agent.llm_wrapper import LLMWrapper
import json

def update_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update existing calendar events
    """
    user_id = state.get("user_id")
    db_session = state.get("db_session")
    message = state.get("message", "")
    action = state.get("action", "")
    task_context = state.get("task_context")
    current_subtask_id = state.get("current_subtask_id")
    search_results = state.get("search_results", [])
    
    if not user_id:
        return {
            **state,
            "response": "Error: User ID is required for update operations",
            "error": "Missing user_id"
        }
    
    try:
        # Initialize integrated calendar
        integrated_cal = IntegratedCalendar(user_id=user_id, db_session=db_session)
        
        # Get events to update
        events_to_update = []
        
        # If this is part of a compound task, get events from previous search
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task:
                # Look for search results from previous tasks
                for prev_task in task_context.subtasks:
                    if (prev_task.intent.value == "SEARCH" and 
                        prev_task.status == TaskStatus.COMPLETED and 
                        prev_task.search_results):
                        events_to_update.extend(prev_task.search_results)
                        break
        
        # If no events from compound task, use current search results
        if not events_to_update and search_results:
            events_to_update = [result.dict() if hasattr(result, 'dict') else result for result in search_results]
        
        if not events_to_update:
            return {
                **state,
                "response": "No events found to update. Please search for events first.",
                "error": "No events to update"
            }
        
        # Extract update data from message
        update_data = extract_update_data(message, action, task_context, current_subtask_id or "")
        
        if not update_data:
            return {
                **state,
                "response": "Could not determine what changes to make. Please specify what you want to update.",
                "error": "No update data"
            }
        
        # Update events
        updated_count = 0
        failed_updates = []
        
        for event in events_to_update:
            try:
                # Merge update data with existing event data
                merged_data = {
                    "title": update_data.get("title", event.get("title")),
                    "description": update_data.get("description", event.get("description")),
                    "start": update_data.get("start", event.get("start_time")),
                    "end": update_data.get("end", event.get("end_time")),
                    "location": update_data.get("location", event.get("location")),
                    "timezone": update_data.get("timezone", "UTC")
                }
                
                success = integrated_cal.update_event(
                    provider=event.get("provider"),
                    account_email=event.get("account_email"),
                    event_id=event.get("event_id") or event.get("id"),
                    event_data=merged_data
                )
                
                if success:
                    updated_count += 1
                else:
                    failed_updates.append(event.get("title", "Unknown event"))
                    
            except Exception as e:
                failed_updates.append(f"{event.get('title', 'Unknown event')}: {str(e)}")
        
        # Update task context if this is part of a compound task
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task:
                if updated_count > 0:
                    current_task.status = TaskStatus.COMPLETED
                    current_task.result = {
                        "summary": f"Updated {updated_count} events",
                        "updated_count": updated_count,
                        "failed_count": len(failed_updates)
                    }
                else:
                    current_task.status = TaskStatus.FAILED
                    current_task.error = f"Failed to update events: {'; '.join(failed_updates)}"
        
        # Generate response
        if updated_count > 0:
            response = f"✅ Successfully updated {updated_count} event(s)."
            if failed_updates:
                response += f"\n⚠️ Failed to update {len(failed_updates)} event(s): {'; '.join(failed_updates)}"
        else:
            response = f"❌ Failed to update any events. Errors: {'; '.join(failed_updates)}"
        
        return {
            **state,
            "response": response,
            "task_context": task_context
        }
        
    except Exception as e:
        error_msg = f"Update operation failed: {str(e)}"
        
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

def extract_update_data(message: str, action: str, task_context, current_subtask_id: str) -> Dict[str, Any]:
    """
    Extract update data from message using LLM
    """
    # If this is part of a compound task, get parameters from subtask
    if task_context and current_subtask_id:
        current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
        if current_task and current_task.parameters:
            return current_task.parameters
    
    llm = LLMWrapper()
    
    system_prompt = """Extract what needs to be updated from this message.
    
    Return JSON with only the fields that should be changed:
    {
        "title": "new title if changing",
        "description": "new description if changing",
        "start": "new start time if changing (YYYY-MM-DDTHH:MM:SS)",
        "end": "new end time if changing (YYYY-MM-DDTHH:MM:SS)",
        "location": "new location if changing",
        "timezone": "UTC"
    }
    
    Only include fields that are being updated. Leave out fields that shouldn't change.
    
    Examples:
    - "Change time to 3pm" → {"start": "...T15:00:00", "end": "...T16:00:00"}
    - "Move to conference room A" → {"location": "Conference Room A"}
    - "Rename to Team Meeting" → {"title": "Team Meeting"}
    """
    
    try:
        full_text = f"{message} {action}".strip()
        response = llm.invoke([system_prompt, f"Request: {full_text}"])
        
        # Clean and parse JSON response
        response_clean = response.strip()
        if response_clean.startswith('```json'):
            response_clean = response_clean[7:-3]
        
        update_data = json.loads(response_clean)
        
        # Remove empty values
        return {k: v for k, v in update_data.items() if v}
        
    except Exception as e:
        # Fallback: simple keyword-based extraction
        update_data = {}
        message_lower = f"{message} {action}".lower()
        
        # Look for time changes
        if any(word in message_lower for word in ["time", "pm", "am", "o'clock"]):
            # Try to extract time (basic pattern matching)
            import re
            time_pattern = r'(\d{1,2})\s*(am|pm|:)'
            match = re.search(time_pattern, message_lower)
            if match:
                hour = int(match.group(1))
                if "pm" in match.group(2) and hour != 12:
                    hour += 12
                # Create a simple time update (would need more sophisticated parsing)
                update_data["time_change"] = True
        
        # Look for location changes
        if any(word in message_lower for word in ["move", "room", "location", "place"]):
            # Extract location (basic)
            location_keywords = ["room", "conference", "office", "building"]
            words = message.split()
            for i, word in enumerate(words):
                if word.lower() in location_keywords and i + 1 < len(words):
                    update_data["location"] = f"{word} {words[i+1]}"
                    break
        
        return update_data
