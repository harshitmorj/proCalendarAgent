"""
Task Orchestrator Node - Manages compound tasks and coordinates subtask execution
"""

import uuid
from typing import Dict, Any, List
from app.langgraph_agent.schemas.router_schema import (
    TaskContext, SubTask, TaskStatus, CalendarIntent, HumanFeedback
)
from app.langgraph_agent.llm_wrapper import LLMWrapper

def task_orchestrator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrates compound tasks by managing subtasks and their dependencies
    """
    task_context = state.get("task_context")
    message = state.get("message", "")
    user_id = state.get("user_id", 0)
    
    if not task_context:
        # Initialize task context for compound tasks
        task_context = TaskContext(
            original_message=message,
            user_id=user_id or 0,
            subtasks=[]
        )
    
    # If this is the first run, decompose the task
    if not task_context.subtasks:
        subtasks = decompose_task(message)
        task_context.subtasks = subtasks
    
    # Process current subtask or find next one
    current_task = find_next_task(task_context)
    
    if not current_task:
        # All tasks completed - generate summary
        return generate_final_response(state, task_context)
    
    # Set current task and prepare for execution
    task_context.current_task = current_task
    current_task.status = TaskStatus.IN_PROGRESS
    
    return {
        **state,
        "task_context": task_context,
        "current_subtask_id": current_task.id,
        "action": current_task.description,
        "response": f"Executing: {current_task.description}"
    }

def decompose_task(message: str) -> List[SubTask]:
    """
    Use LLM to decompose complex tasks into subtasks
    """
    llm = LLMWrapper()
    
    system_prompt = """Decompose this calendar task into ordered subtasks. 
    
    For delete operations with search terms (like "delete meetings with Soham"), always start with SEARCH then DELETE.
    For update operations, start with SEARCH to find events, then UPDATE.
    For scheduling with multiple people, use SEARCH to check availability, then CREATE.
    
    Return JSON array of subtasks:
    [
        {
            "intent": "SEARCH|CREATE|UPDATE|DELETE|SCHEDULE",
            "description": "Clear description of what to do",
            "parameters": {"search_query": "...", "action_type": "..."}
        }
    ]
    
    Example for "delete meetings with Soham":
    [
        {"intent": "SEARCH", "description": "Find all meetings containing 'Soham'", "parameters": {"search_query": "Soham"}},
        {"intent": "DELETE", "description": "Delete the found meetings", "parameters": {"confirm_before_delete": false}}
    ]"""
    
    try:
        response = llm.invoke([system_prompt, f"Task: {message}"])
        
        # Parse response and create SubTask objects
        import json
        response_clean = response.strip()
        if response_clean.startswith('```json'):
            response_clean = response_clean[7:-3]
        
        subtask_data = json.loads(response_clean)
        
        subtasks = []
        for i, task_data in enumerate(subtask_data):
            subtask = SubTask(
                id=str(uuid.uuid4()),
                intent=CalendarIntent(task_data["intent"]),
                description=task_data["description"],
                parameters=task_data.get("parameters", {}),
                status=TaskStatus.PENDING
            )
            
            # Set dependencies (each task depends on previous ones)
            if i > 0:
                subtask.dependencies = [subtasks[i-1].id]
            
            subtasks.append(subtask)
        
        return subtasks
        
    except Exception as e:
        # Fallback: create basic search -> delete pattern for delete operations
        if "delete" in message.lower() and any(word in message.lower() for word in ["with", "containing", "named"]):
            search_terms = extract_search_terms(message)
            search_task = SubTask(
                id=str(uuid.uuid4()),
                intent=CalendarIntent.SEARCH,
                description=f"Find events matching: {search_terms}",
                parameters={"search_query": search_terms},
                status=TaskStatus.PENDING
            )
            delete_task = SubTask(
                id=str(uuid.uuid4()),
                intent=CalendarIntent.DELETE,
                description="Delete the found events",
                parameters={"confirm_before_delete": False},
                status=TaskStatus.PENDING,
                dependencies=[search_task.id]
            )
            return [search_task, delete_task]
        
        # Single task fallback
        return [SubTask(
            id=str(uuid.uuid4()),
            intent=CalendarIntent.GENERAL,
            description=message,
            status=TaskStatus.PENDING
        )]

def extract_search_terms(message: str) -> str:
    """
    Extract search terms from delete/update messages
    """
    # Simple extraction - look for terms after "with", "containing", "named", etc.
    message_lower = message.lower()
    
    patterns = ["with ", "containing ", "named ", "called ", "including "]
    for pattern in patterns:
        if pattern in message_lower:
            start_idx = message_lower.find(pattern) + len(pattern)
            # Extract until next preposition or end
            remaining = message[start_idx:].split()
            search_terms = []
            for word in remaining:
                if word.lower() in ["and", "or", "from", "on", "at", "in"]:
                    break
                search_terms.append(word.strip(".,!?\"'"))
            return " ".join(search_terms)
    
    return message

def find_next_task(task_context: TaskContext) -> SubTask | None:
    """
    Find the next task ready for execution (no pending dependencies)
    """
    for task in task_context.subtasks:
        if task.status == TaskStatus.PENDING:
            # Check if dependencies are met
            if not task.dependencies:
                return task
            
            # Check if all dependencies are completed
            deps_completed = all(
                any(t.id == dep_id and t.status == TaskStatus.COMPLETED 
                    for t in task_context.subtasks)
                for dep_id in task.dependencies
            )
            
            if deps_completed:
                return task
    
    return None

def generate_final_response(state: Dict[str, Any], task_context: TaskContext) -> Dict[str, Any]:
    """
    Generate final response when all subtasks are completed
    """
    completed_tasks = [t for t in task_context.subtasks if t.status == TaskStatus.COMPLETED]
    failed_tasks = [t for t in task_context.subtasks if t.status == TaskStatus.FAILED]
    
    if failed_tasks:
        response = f"Task partially completed. {len(completed_tasks)} succeeded, {len(failed_tasks)} failed."
        for failed_task in failed_tasks:
            response += f"\nFailed: {failed_task.description} - {failed_task.error}"
    else:
        response = f"Task completed successfully! Executed {len(completed_tasks)} operations."
        for task in completed_tasks:
            if task.result:
                response += f"\n- {task.description}: {task.result.get('summary', 'Done')}"
    
    return {
        **state,
        "response": response,
        "status": "completed",
        "task_context": task_context,
        "current_subtask_id": None
    }
