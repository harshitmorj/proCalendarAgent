"""
Human in Loop Node - Handles user interactions and confirmations
"""

from typing import Dict, Any
from app.langgraph_agent.schemas.router_schema import HumanFeedback, TaskStatus

def human_in_loop_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle human interactions, confirmations, and clarifications
    """
    human_feedback = state.get("human_feedback")
    task_context = state.get("task_context")
    current_subtask_id = state.get("current_subtask_id")
    awaiting_confirmation = state.get("awaiting_confirmation", False)
    
    if not human_feedback:
        return {
            **state,
            "response": "Waiting for user input...",
            "requires_human_input": True
        }
    
    # Process different types of feedback
    if human_feedback.feedback_type == "confirmation":
        return handle_confirmation(state, human_feedback, task_context, current_subtask_id or "")
    
    elif human_feedback.feedback_type == "selection":
        return handle_selection(state, human_feedback, task_context, current_subtask_id or "")
    
    elif human_feedback.feedback_type == "clarification":
        return handle_clarification(state, human_feedback, task_context)
    
    else:
        return {
            **state,
            "response": f"Received feedback: {human_feedback.user_input}",
            "awaiting_confirmation": False,
            "human_feedback": None
        }

def handle_confirmation(state: Dict[str, Any], feedback: HumanFeedback, task_context, current_subtask_id: str) -> Dict[str, Any]:
    """
    Handle confirmation responses (yes/no/cancel)
    """
    user_response = feedback.user_input.lower().strip()
    
    # Standard confirmation responses
    if user_response in ["yes", "y", "confirm", "ok", "proceed"]:
        return {
            **state,
            "awaiting_confirmation": False,
            "human_feedback": None,
            "response": "Proceeding with the operation..."
        }
    
    elif user_response in ["no", "n", "cancel", "stop"]:
        # Cancel the current operation
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task:
                current_task.status = TaskStatus.FAILED
                current_task.error = "Operation cancelled by user"
        
        return {
            **state,
            "awaiting_confirmation": False,
            "human_feedback": None,
            "response": "Operation cancelled by user.",
            "status": "cancelled"
        }
    
    else:
        # Ask for clarification on unclear response
        return {
            **state,
            "response": f"I didn't understand '{user_response}'. Please respond with 'yes' to proceed or 'no' to cancel.",
            "awaiting_confirmation": True,
            "human_feedback": HumanFeedback(
                feedback_type="confirmation",
                question="Please confirm: yes or no?",
                user_input="",
                options=[
                    {"value": "yes", "label": "Yes, proceed"},
                    {"value": "no", "label": "No, cancel"}
                ]
            )
        }

def handle_selection(state: Dict[str, Any], feedback: HumanFeedback, task_context, current_subtask_id: str) -> Dict[str, Any]:
    """
    Handle selection responses (choosing from options)
    """
    user_input = feedback.user_input.strip()
    options = feedback.options or []
    
    try:
        # Parse selection (e.g., "1,3,5" or "2")
        if "," in user_input:
            selected_indices = [int(x.strip()) - 1 for x in user_input.split(",")]
        else:
            selected_indices = [int(user_input.strip()) - 1]
        
        # Validate selections
        valid_selections = []
        for idx in selected_indices:
            if 0 <= idx < len(options):
                valid_selections.append(options[idx])
            else:
                return {
                    **state,
                    "response": f"Invalid selection: {idx + 1}. Please select from 1 to {len(options)}.",
                    "awaiting_confirmation": True
                }
        
        # Store selections in state for processing
        return {
            **state,
            "selected_results": valid_selections,
            "awaiting_confirmation": False,
            "human_feedback": None,
            "response": f"Selected {len(valid_selections)} item(s). Processing..."
        }
        
    except ValueError:
        return {
            **state,
            "response": f"Invalid input '{user_input}'. Please enter numbers separated by commas (e.g., 1,3,5).",
            "awaiting_confirmation": True
        }

def handle_clarification(state: Dict[str, Any], feedback: HumanFeedback, task_context) -> Dict[str, Any]:
    """
    Handle clarification responses
    """
    user_response = feedback.user_input.strip()
    
    if not user_response:
        return {
            **state,
            "response": "Please provide more information to help me understand what you want to do.",
            "requires_human_input": True
        }
    
    # Update the original message with clarification
    original_message = state.get("message", "")
    enhanced_message = f"{original_message}. Additional context: {user_response}"
    
    return {
        **state,
        "message": enhanced_message,
        "human_feedback": None,
        "requires_human_input": False,
        "response": f"Thank you for the clarification. Processing: {enhanced_message}",
        # Reset intent to re-route with new information
        "intent": None
    }

def format_options_for_display(options: list) -> str:
    """
    Format options for user-friendly display
    """
    if not options:
        return ""
    
    formatted = "\nOptions:\n"
    for i, option in enumerate(options, 1):
        label = option.get("label", option.get("value", f"Option {i}"))
        formatted += f"{i}. {label}\n"
    
    return formatted
