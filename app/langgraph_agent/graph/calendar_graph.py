from typing import TypedDict, Optional, Any, List, Dict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.runnables import RunnableLambda
import os
from dotenv import load_dotenv
from app.langgraph_agent.schemas.router_schema import (
    CalendarIntent, TaskStatus, SubTask, TaskContext, HumanFeedback, SearchResult
)
from app.langgraph_agent.nodes.router_node import router_node_func
from app.langgraph_agent.nodes.general_node import general_node
from app.langgraph_agent.nodes.task_orchestrator_node import task_orchestrator_node
from app.langgraph_agent.nodes.search_node import search_node
from app.langgraph_agent.nodes.create_node import create_node
from app.langgraph_agent.nodes.update_node import update_node
from app.langgraph_agent.nodes.delete_node import delete_node
from app.langgraph_agent.nodes.schedule_node import schedule_node
from app.langgraph_agent.nodes.clarify_node import clarify_node
from app.langgraph_agent.nodes.human_in_loop_node import human_in_loop_node
from app.langgraph_agent.nodes.rsvp_node import rsvp_node
from app.langgraph_agent.nodes.knowledge_analysis_node import knowledge_analysis_node

# Configure LangSmith tracing
def setup_langsmith_tracing():
    """Setup LangSmith tracing for the entire graph"""
    # These environment variables should already be set in .env
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    os.environ.setdefault("LANGCHAIN_PROJECT", "pro-calendar-agent-test")
    
    # Verify tracing is enabled
    if os.getenv("LANGCHAIN_TRACING_V2") == "true":
        print("✅ LangSmith tracing enabled for calendar agent")
        print(f"📊 Project: {os.getenv('LANGCHAIN_PROJECT', 'default')}")
    else:
        print("⚠️ LangSmith tracing not enabled")

# Initialize tracing
setup_langsmith_tracing()

# Enhanced state that flows between nodes
class AgentState(TypedDict):
    message: str
    user_id: Optional[int]
    db_session: Optional[Any]
    memory: Optional[Any]
    
    # Router outputs
    intent: Optional[str]
    action: Optional[str]
    confidence: Optional[float]
    
    # Task orchestration
    task_context: Optional[TaskContext]
    current_subtask_id: Optional[str]
    subtasks: Optional[List[SubTask]]
    
    # Search and results
    search_results: Optional[List[SearchResult]]
    selected_results: Optional[List[Dict[str, Any]]]
    
    # Human interaction
    requires_human_input: Optional[bool]
    human_feedback: Optional[HumanFeedback]
    awaiting_confirmation: Optional[bool]
    
    # Final response
    response: Optional[str]
    status: Optional[str]
    error: Optional[str]

# Router wrapper
def router_wrapper(state: AgentState) -> AgentState:
    result = router_node_func(dict(state))
    
    # Initialize task context if compound task
    task_context = None
    if result.intent == CalendarIntent.COMPOUND:
        task_context = TaskContext(
            original_message=state["message"],
            user_id=state["user_id"] or 0,
            subtasks=[]
        )
    
    return {
        **state, 
        "intent": result.intent.value if hasattr(result.intent, 'value') else result.intent,
        "action": result.action,
        "confidence": result.confidence,
        "task_context": task_context,
        "requires_human_input": result.needs_clarification
    }

# Enhanced router edge function
def router_edge(state: AgentState) -> str:
    intent = state.get("intent", CalendarIntent.GENERAL.value)
    
    # Check if clarification is needed
    if state.get("requires_human_input", False):
        return "clarify"
    
    # Route based on intent
    if intent == "clarify":
        return "clarify"
    elif intent == "compound":
        return "task_orchestrator"
    elif intent == "search":
        return "search"
    elif intent == "create":
        return "create"
    elif intent == "update":
        return "update"
    elif intent == "delete":
        return "delete"
    elif intent == "schedule":
        return "schedule"
    elif intent == "rsvp":
        return "rsvp"
    elif intent == "knowledge_analysis":
        return "knowledge_analysis"
    else:
        return "general"

# Task orchestrator edge function
def orchestrator_edge(state: AgentState) -> str:
    """Route from task orchestrator based on current subtask or completion"""
    if state.get("awaiting_confirmation", False):
        return "human_in_loop"
    
    task_context = state.get("task_context")
    if not task_context:
        return END
    
    # Check if all tasks are completed
    pending_tasks = [t for t in task_context.subtasks if t.status == TaskStatus.PENDING]
    in_progress_tasks = [t for t in task_context.subtasks if t.status == TaskStatus.IN_PROGRESS]
    waiting_tasks = [t for t in task_context.subtasks if t.status in [TaskStatus.WAITING_SEARCH, TaskStatus.WAITING_USER]]
    
    if not pending_tasks and not in_progress_tasks and not waiting_tasks:
        return END  # All tasks completed
    
    # Route to appropriate node based on current subtask
    current_subtask_id = state.get("current_subtask_id")
    if current_subtask_id:
        current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
        if current_task and current_task.status == TaskStatus.IN_PROGRESS:
            if current_task.intent == CalendarIntent.SEARCH:
                return "search"
            elif current_task.intent == CalendarIntent.CREATE:
                return "create"
            elif current_task.intent == CalendarIntent.UPDATE:
                return "update"
            elif current_task.intent == CalendarIntent.DELETE:
                return "delete"
            elif current_task.intent == CalendarIntent.SCHEDULE:
                return "schedule"
            elif current_task.intent == CalendarIntent.RSVP:
                return "rsvp"
    
    # If no specific subtask in progress, continue orchestrating
    return END

# Human in loop edge function
def human_in_loop_edge(state: AgentState) -> str:
    """Route from human in loop node"""
    human_feedback = state.get("human_feedback")
    if human_feedback and human_feedback.feedback_type == "confirmation":
        return "task_orchestrator"
    elif human_feedback and human_feedback.feedback_type == "clarification":
        return "clarify"
    return "task_orchestrator"

# Action node edge function
def action_node_edge(state: AgentState) -> str:
    """Route from action nodes back to orchestrator or end"""
    task_context = state.get("task_context")
    if task_context:
        return "task_orchestrator"
    return END

# Build the enhanced graph
builder = StateGraph(AgentState)

# Add all nodes
builder.add_node("router", RunnableLambda(router_wrapper))
builder.add_node("general", general_node)
builder.add_node("task_orchestrator", task_orchestrator_node)
builder.add_node("search", search_node)
builder.add_node("create", create_node)
builder.add_node("update", update_node)
builder.add_node("delete", delete_node)
builder.add_node("schedule", schedule_node)
builder.add_node("rsvp", rsvp_node)
builder.add_node("clarify", clarify_node)
builder.add_node("knowledge_analysis", knowledge_analysis_node)
builder.add_node("human_in_loop", human_in_loop_node)

# Set entry point
builder.set_entry_point("router")

# Add conditional edges
builder.add_conditional_edges("router", router_edge)
builder.add_conditional_edges("task_orchestrator", orchestrator_edge)
builder.add_conditional_edges("human_in_loop", human_in_loop_edge)

# Add edges back to orchestrator from action nodes
builder.add_conditional_edges("search", action_node_edge)
builder.add_conditional_edges("create", action_node_edge)
builder.add_conditional_edges("update", action_node_edge)
builder.add_conditional_edges("delete", action_node_edge)
builder.add_conditional_edges("schedule", action_node_edge)
builder.add_conditional_edges("rsvp", action_node_edge)

# Add edges to END for simple nodes
builder.add_edge("general", END)
builder.add_edge("knowledge_analysis", END)
builder.add_edge("clarify", "router")  # Clarify routes back to router for re-evaluation

# Compile the graph with LangSmith tracing enabled
calendar_graph = builder.compile(
    checkpointer=None,
    interrupt_before=None,
    interrupt_after=None,
    debug=True  # Enable debug mode for better tracing
)

# Add metadata for better trace identification
calendar_graph = calendar_graph.with_config({
    "tags": ["calendar-agent", "langgraph", "compound-tasks"],
    "metadata": {
        "agent_type": "calendar_agent",
        "version": "1.0",
        "capabilities": ["search", "create", "update", "delete", "schedule", "compound_tasks"]
    }
})

