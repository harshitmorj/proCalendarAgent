"""
Delete Node - Handles event deletion operations with confirmation
"""

from typing import Dict, Any, List
from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.langgraph_agent.schemas.router_schema import TaskStatus, HumanFeedback
from app.langgraph_agent.llm_wrapper import LLMWrapper

def delete_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete calendar events with confirmation
    """
    user_id = state.get("user_id")
    db_session = state.get("db_session")
    message = state.get("message", "")
    task_context = state.get("task_context")
    current_subtask_id = state.get("current_subtask_id")
    search_results = state.get("search_results", [])
    human_feedback = state.get("human_feedback")
    
    if not user_id:
        return {
            **state,
            "response": "Error: User ID is required for delete operations",
            "error": "Missing user_id"
        }
    
    try:
        # Initialize integrated calendar
        integrated_cal = IntegratedCalendar(user_id=user_id, db_session=db_session)
        
        # Get events to delete
        events_to_delete = []
        
        # If this is part of a compound task, get events from previous search
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task:
                # Look for search results from previous tasks
                for prev_task in task_context.subtasks:
                    if (prev_task.intent.value == "SEARCH" and 
                        prev_task.status == TaskStatus.COMPLETED and 
                        prev_task.search_results):
                        events_to_delete.extend(prev_task.search_results)
                        break
        
        # If no events from compound task, use current search results
        if not events_to_delete and search_results:
            events_to_delete = [result.dict() if hasattr(result, 'dict') else result for result in search_results]
        
        # If still no events, try to find them based on message
        if not events_to_delete:
            return {
                **state,
                "response": "No events found to delete. Please search for events first.",
                "error": "No events to delete"
            }
        
        # Check if confirmation is needed and not yet provided
        needs_confirmation = True
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task and current_task.parameters:
                needs_confirmation = current_task.parameters.get("confirm_before_delete", True)
            
            # For compound tasks, skip confirmation if not explicitly required
            # The user already expressed intent to delete in the original message
            if current_task and not current_task.parameters.get("require_confirmation", False):
                needs_confirmation = False
        
        # Handle confirmation flow
        if needs_confirmation and not human_feedback:
            # Request confirmation from user
            confirmation_message = f"Are you sure you want to delete {len(events_to_delete)} event(s)?\n\n"
            for i, event in enumerate(events_to_delete[:5], 1):
                confirmation_message += f"{i}. {event.get('title', 'Untitled')} - {event.get('start_time', 'No time')}\n"
            if len(events_to_delete) > 5:
                confirmation_message += f"... and {len(events_to_delete) - 5} more\n"
            
            return {
                **state,
                "awaiting_confirmation": True,
                "human_feedback": HumanFeedback(
                    feedback_type="confirmation",
                    question=confirmation_message,
                    user_input="",
                    options=[
                        {"value": "yes", "label": "Yes, delete all"},
                        {"value": "no", "label": "No, cancel"},
                        {"value": "select", "label": "Let me select which ones"}
                    ]
                ),
                "response": confirmation_message + "\nPlease confirm: (yes/no/select)"
            }
        
        # Process confirmation response
        if human_feedback and human_feedback.feedback_type == "confirmation":
            user_response = human_feedback.user_input.lower().strip()
            
            if user_response in ["no", "n", "cancel"]:
                return {
                    **state,
                    "response": "Delete operation cancelled.",
                    "status": "cancelled"
                }
            
            elif user_response in ["select", "s"]:
                # Let user select specific events
                return handle_selective_deletion(state, events_to_delete)
            
            # Proceed with deletion for "yes" or other confirmations
        
        # Perform deletions
        deleted_count = 0
        failed_deletions = []
        
        for event in events_to_delete:
            try:
                success = integrated_cal.delete_event(
                    provider=event.get("provider"),
                    account_email=event.get("account_email"),
                    event_id=event.get("event_id") or event.get("id")
                )
                
                if success:
                    deleted_count += 1
                else:
                    failed_deletions.append(event.get("title", "Unknown event"))
                    
            except Exception as e:
                failed_deletions.append(f"{event.get('title', 'Unknown event')}: {str(e)}")
        
        # Update task context if this is part of a compound task
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task:
                if deleted_count > 0:
                    current_task.status = TaskStatus.COMPLETED
                    current_task.result = {
                        "summary": f"Deleted {deleted_count} events",
                        "deleted_count": deleted_count,
                        "failed_count": len(failed_deletions)
                    }
                else:
                    current_task.status = TaskStatus.FAILED
                    current_task.error = f"Failed to delete events: {'; '.join(failed_deletions)}"
        
        # Generate response
        if deleted_count > 0:
            response = f"✅ Successfully deleted {deleted_count} event(s)."
            if failed_deletions:
                response += f"\n⚠️ Failed to delete {len(failed_deletions)} event(s): {'; '.join(failed_deletions)}"
        else:
            response = f"❌ Failed to delete any events. Errors: {'; '.join(failed_deletions)}"
        
        return {
            **state,
            "response": response,
            "task_context": task_context,
            "awaiting_confirmation": False,
            "human_feedback": None
        }
        
    except Exception as e:
        error_msg = f"Delete operation failed: {str(e)}"
        
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

def handle_selective_deletion(state: Dict[str, Any], events_to_delete: List[Dict]) -> Dict[str, Any]:
    """
    Handle selective deletion - let user choose which events to delete
    """
    options = []
    for i, event in enumerate(events_to_delete):
        options.append({
            "value": str(i),
            "label": f"{event.get('title', 'Untitled')} - {event.get('start_time', 'No time')}"
        })
    
    return {
        **state,
        "awaiting_confirmation": True,
        "human_feedback": HumanFeedback(
            feedback_type="selection",
            question="Select which events to delete (comma-separated numbers, e.g., 1,3,5):",
            user_input="",
            options=options
        ),
        "response": "Please select which events to delete by entering their numbers (e.g., 1,3,5):"
    }
