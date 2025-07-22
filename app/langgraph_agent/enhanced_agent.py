"""
Enhanced Calendar Agent with multi-node architecture and compound task support
"""
from typing import Dict, Any, TypedDict, List, Optional, Union
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable
from sqlalchemy.orm import Session
import json
import os
from dotenv import load_dotenv

from .schemas import (
    TaskType, IntentExtractionResult, ToolResult, AgentResponse,
    SearchQuery, CreateEventRequest, UpdateEventRequest, DeleteEventRequest,
    EventData, EventIdentifier, CalendarProvider, ExecutionPlan, NodeResult
)
from .enhanced_tools import CalendarTools
from .intent_extractor import LLMIntentExtractor

load_dotenv()

class EnhancedCalendarAgentState(TypedDict):
    """Enhanced state for the calendar agent"""
    messages: List[Any]
    user_id: int
    db_session: Session
    extracted_intent: Optional[IntentExtractionResult]
    execution_plan: Optional[ExecutionPlan]
    tool_results: List[ToolResult]
    current_step: int
    requires_confirmation: bool
    confirmation_data: Optional[Dict[str, Any]]
    final_response: Optional[AgentResponse]
    error_state: Optional[str]

@traceable
class EnhancedCalendarAgent:
    """Enhanced Calendar Agent with LLM-powered reasoning and compound task support"""
    
    def __init__(self):
        load_dotenv(override=True)
        
        # Initialize LLMs
        self.openai_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.gemini_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.3,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Initialize components
        self.intent_extractor = LLMIntentExtractor()
    
    def call_llm_with_fallback(self, messages: List[Dict[str, str]]) -> str:
        """Call LLM with fallback mechanism"""
        try:
            # Convert to proper message format
            formatted_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    formatted_messages.append(("system", msg["content"]))
                elif msg["role"] == "user":
                    formatted_messages.append(("human", msg["content"]))
                elif msg["role"] == "assistant":
                    formatted_messages.append(("ai", msg["content"]))
            
            response = self.openai_llm.invoke(formatted_messages)
            return response.content
        except Exception as openai_error:
            print(f"OpenAI error: {openai_error}")
            try:
                response = self.gemini_llm.invoke(formatted_messages)
                return response.content
            except Exception as gemini_error:
                print(f"Gemini error: {gemini_error}")
                return "I'm having trouble processing your request. Please try again."
    
    # Node Functions
    def router_node(self, state: EnhancedCalendarAgentState) -> EnhancedCalendarAgentState:
        """Route incoming message and extract intent"""
        last_message = state["messages"][-1] if state["messages"] else None
        
        if not isinstance(last_message, HumanMessage):
            state["error_state"] = "Invalid message type"
            return state
        
        try:
            # Extract intent using LLM
            intent_result = self.intent_extractor.extract_intent(
                last_message.content,
                context={"user_id": state["user_id"]}
            )
            
            state["extracted_intent"] = intent_result
            state["current_step"] = 0
            state["tool_results"] = []
            
            # Check if confirmation is needed
            if intent_result.primary_intent.requires_confirmation:
                state["requires_confirmation"] = True
            
        except Exception as e:
            print(f"Router node error: {e}")
            state["error_state"] = f"Failed to extract intent: {str(e)}"
        
        return state
    
    def planner_node(self, state: EnhancedCalendarAgentState) -> EnhancedCalendarAgentState:
        """Plan execution steps for the task"""
        intent_result = state.get("extracted_intent")
        
        if not intent_result:
            state["error_state"] = "No intent extracted"
            return state
        
        try:
            if intent_result.is_compound:
                # Use LLM to plan compound task
                compound_task = self.intent_extractor.plan_compound_task(intent_result)
                
                # Convert to execution plan
                steps = []
                for i, subtask in enumerate(compound_task.subtasks):
                    steps.append({
                        "step_id": i,
                        "task_type": subtask.task_type,
                        "parameters": subtask.parameters,
                        "depends_on": subtask.depends_on,
                        "description": subtask.description,
                        "completed": False
                    })
                
                execution_plan = ExecutionPlan(
                    steps=steps,
                    requires_confirmation=any(step["task_type"] in [TaskType.DELETE, TaskType.UPDATE] 
                                           for step in steps),
                    risk_level="medium" if any(step["task_type"] == TaskType.DELETE for step in steps) else "low"
                )
            else:
                # Single task
                execution_plan = ExecutionPlan(
                    steps=[{
                        "step_id": 0,
                        "task_type": intent_result.primary_intent.task_type,
                        "parameters": intent_result.primary_intent.parameters,
                        "depends_on": None,
                        "description": f"Execute {intent_result.primary_intent.task_type.value} operation",
                        "completed": False
                    }],
                    requires_confirmation=intent_result.primary_intent.requires_confirmation,
                    risk_level="low"
                )
            
            state["execution_plan"] = execution_plan
            
        except Exception as e:
            print(f"Planner node error: {e}")
            state["error_state"] = f"Failed to create execution plan: {str(e)}"
        
        return state
    
    def tool_executor_node(self, state: EnhancedCalendarAgentState) -> EnhancedCalendarAgentState:
        """Execute calendar tools based on the plan"""
        execution_plan = state.get("execution_plan")
        current_step = state.get("current_step", 0)
        
        if not execution_plan or current_step >= len(execution_plan.steps):
            return state
        
        step = execution_plan.steps[current_step]
        
        # Check dependencies
        if step.get("depends_on"):
            for dep_idx in step["depends_on"]:
                if not execution_plan.steps[dep_idx].get("completed"):
                    state["error_state"] = f"Dependency step {dep_idx} not completed"
                    return state
        
        try:
            # Initialize tools
            calendar_tools = CalendarTools(state["user_id"], state["db_session"])
            
            # Execute based on task type
            result = self._execute_tool_step(calendar_tools, step, state)
            
            # Store result
            state["tool_results"].append(result)
            
            # Mark step as completed
            step["completed"] = True
            step["result"] = result
            
            # Move to next step
            state["current_step"] += 1
            
        except Exception as e:
            print(f"Tool executor error: {e}")
            result = ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}"
            )
            state["tool_results"].append(result)
        
        return state
    
    def confirmation_node(self, state: EnhancedCalendarAgentState) -> EnhancedCalendarAgentState:
        """Handle confirmation requests for high-risk operations"""
        execution_plan = state.get("execution_plan")
        
        if not execution_plan or not execution_plan.requires_confirmation:
            return state
        
        # Check if confirmation is needed for current step
        current_step = state.get("current_step", 0)
        if current_step < len(execution_plan.steps):
            step = execution_plan.steps[current_step]
            
            if step["task_type"] in [TaskType.DELETE, TaskType.UPDATE]:
                # Prepare confirmation data
                state["requires_confirmation"] = True
                state["confirmation_data"] = {
                    "operation": step["task_type"].value,
                    "description": step["description"],
                    "risk_level": execution_plan.risk_level,
                    "step_id": current_step
                }
        
        return state
    
    def response_generator_node(self, state: EnhancedCalendarAgentState) -> EnhancedCalendarAgentState:
        """Generate final response based on execution results"""
        tool_results = state.get("tool_results", [])
        execution_plan = state.get("execution_plan")
        error_state = state.get("error_state")
        
        if error_state:
            # Handle errors
            response = AgentResponse(
                message=f"I encountered an error: {error_state}",
                actions_taken=[],
                suggestions=["Please try rephrasing your request", "Check if your calendars are connected"]
            )
        elif state.get("requires_confirmation") and not state.get("confirmation_received"):
            # Handle confirmation requests
            confirmation_data = state.get("confirmation_data", {})
            response = AgentResponse(
                message=f"⚠️ Confirmation required for {confirmation_data.get('operation', 'operation')}:\n"
                       f"{confirmation_data.get('description', 'This action')}\n\n"
                       f"Please confirm by saying 'yes' or 'confirm'.",
                actions_taken=[],
                suggestions=["Say 'yes' to confirm", "Say 'no' to cancel"]
            )
        else:
            # Generate response based on results
            response = self._generate_response_from_results(tool_results, execution_plan)
        
        state["final_response"] = response
        return state
    
    def _execute_tool_step(self, calendar_tools: CalendarTools, step: Dict[str, Any], 
                          state: EnhancedCalendarAgentState) -> ToolResult:
        """Execute a single tool step"""
        task_type = step["task_type"]
        parameters = step["parameters"]
        
        # Get context from previous results if needed
        previous_results = state.get("tool_results", [])
        
        if task_type == TaskType.READ:
            return calendar_tools.get_events(limit=parameters.get("limit", 15))
        
        elif task_type == TaskType.SEARCH:
            # Build search query from parameters and intent
            intent = state.get("extracted_intent")
            search_query = self._build_search_query(parameters, intent)
            return calendar_tools.search_events(search_query)
        
        elif task_type == TaskType.CREATE:
            # Build create request
            create_request = self._build_create_request(parameters, intent)
            return calendar_tools.create_event(create_request)
        
        elif task_type == TaskType.UPDATE:
            # Build update request, potentially using search results
            update_request = self._build_update_request(parameters, previous_results)
            return calendar_tools.update_event(update_request)
        
        elif task_type == TaskType.DELETE:
            # Build delete request, potentially using search results
            delete_request = self._build_delete_request(parameters, previous_results)
            return calendar_tools.delete_event(delete_request)
        
        else:
            return ToolResult(
                success=False,
                error=f"Unknown task type: {task_type}"
            )
    
    def _build_search_query(self, parameters: Dict[str, Any], 
                           intent: Optional[IntentExtractionResult]) -> SearchQuery:
        """Build search query from parameters and intent"""
        # Extract search text from various sources
        search_text = parameters.get("query", "")
        
        if intent and intent.extracted_entities:
            # Add entities to search
            if "person" in intent.extracted_entities:
                search_text += f" {intent.extracted_entities['person']}"
            if "title" in intent.extracted_entities:
                search_text += f" {intent.extracted_entities['title']}"
        
        return SearchQuery(
            text=search_text.strip(),
            limit=parameters.get("limit", 20)
        )
    
    def _build_create_request(self, parameters: Dict[str, Any], 
                             intent: Optional[IntentExtractionResult]) -> CreateEventRequest:
        """Build create request from parameters and intent"""
        # This would need more sophisticated parsing
        # For now, return a basic structure
        event_data = EventData(
            title=parameters.get("title", "New Event"),
            description=parameters.get("description"),
            location=parameters.get("location"),
            start_datetime=parameters.get("start_datetime", datetime.now()),
            end_datetime=parameters.get("end_datetime", datetime.now() + timedelta(hours=1))
        )
        
        return CreateEventRequest(
            event_data=event_data,
            provider=CalendarProvider.ANY
        )
    
    def _build_update_request(self, parameters: Dict[str, Any], 
                             previous_results: List[ToolResult]) -> UpdateEventRequest:
        """Build update request, using search results if available"""
        # Find event from previous search results
        event_identifier = EventIdentifier()
        
        # Get the first successful search result
        for result in previous_results:
            if result.success and result.data and isinstance(result.data, list) and result.data:
                event = result.data[0]  # Take first event
                event_identifier = EventIdentifier(
                    event_id=event.get("id"),
                    provider=CalendarProvider(event.get("provider", "google")),
                    account_email=event.get("account_email")
                )
                break
        
        return UpdateEventRequest(
            event_identifier=event_identifier,
            updates=parameters
        )
    
    def _build_delete_request(self, parameters: Dict[str, Any], 
                             previous_results: List[ToolResult]) -> DeleteEventRequest:
        """Build delete request, using search results if available"""
        # Similar to update request
        event_identifier = EventIdentifier()
        
        for result in previous_results:
            if result.success and result.data and isinstance(result.data, list) and result.data:
                event = result.data[0]
                event_identifier = EventIdentifier(
                    event_id=event.get("id"),
                    provider=CalendarProvider(event.get("provider", "google")),
                    account_email=event.get("account_email")
                )
                break
        
        return DeleteEventRequest(
            event_identifier=event_identifier,
            confirmation=parameters.get("confirmation", False)
        )
    
    def _generate_response_from_results(self, tool_results: List[ToolResult], 
                                       execution_plan: Optional[ExecutionPlan]) -> AgentResponse:
        """Generate human-readable response from tool results"""
        if not tool_results:
            return AgentResponse(
                message="I couldn't complete your request.",
                actions_taken=[]
            )
        
        successful_results = [r for r in tool_results if r.success]
        failed_results = [r for r in tool_results if not r.success]
        
        # Build response message
        message_parts = []
        actions_taken = []
        
        if successful_results:
            for i, result in enumerate(successful_results):
                if result.data:
                    if isinstance(result.data, list) and result.data:
                        # Event list
                        if len(result.data) == 1:
                            event = result.data[0]
                            message_parts.append(f"✅ Found event: **{event.get('title', 'Untitled')}**")
                            message_parts.append(f"📅 {event.get('start', '')} to {event.get('end', '')}")
                            if event.get('location'):
                                message_parts.append(f"📍 {event['location']}")
                        else:
                            message_parts.append(f"✅ Found {len(result.data)} events:")
                            for event in result.data[:5]:  # Show first 5
                                message_parts.append(f"• **{event.get('title', 'Untitled')}** - {event.get('start', '')}")
                            if len(result.data) > 5:
                                message_parts.append(f"... and {len(result.data) - 5} more")
                    
                    elif isinstance(result.data, dict):
                        # Single event or operation result
                        if 'title' in result.data:
                            # Event data
                            event = result.data
                            message_parts.append(f"✅ Event: **{event.get('title', 'Untitled')}**")
                            message_parts.append(f"📅 {event.get('start', '')} to {event.get('end', '')}")
                        elif 'deleted' in result.data:
                            message_parts.append("✅ Event deleted successfully")
                        else:
                            message_parts.append("✅ Operation completed successfully")
                
                actions_taken.append(f"Step {i+1}: {execution_plan.steps[i]['description'] if execution_plan else 'Action completed'}")
        
        if failed_results:
            for result in failed_results:
                message_parts.append(f"❌ Error: {result.error}")
        
        # Generate suggestions
        suggestions = []
        if execution_plan and len(successful_results) > 0:
            if any("search" in step.get("description", "").lower() for step in execution_plan.steps):
                suggestions.append("Try searching with different keywords")
            if any("create" in step.get("description", "").lower() for step in execution_plan.steps):
                suggestions.append("Create another event")
        
        return AgentResponse(
            message="\n".join(message_parts) if message_parts else "Operation completed.",
            actions_taken=actions_taken,
            suggestions=suggestions
        )
    
    def _route_next_node(self, state: EnhancedCalendarAgentState) -> str:
        """Determine the next node to execute"""
        # Error state
        if state.get("error_state"):
            return "response_generator"
        
        # Need confirmation
        if state.get("requires_confirmation") and not state.get("confirmation_received"):
            return "confirmation"
        
        # Planning phase
        if not state.get("execution_plan"):
            return "planner"
        
        # Execution phase
        execution_plan = state.get("execution_plan")
        current_step = state.get("current_step", 0)
        
        if current_step < len(execution_plan.steps):
            return "tool_executor"
        
        # All steps completed
        return "response_generator"
    
    def create_graph(self):
        """Create the enhanced LangGraph workflow"""
        workflow = StateGraph(EnhancedCalendarAgentState)
        
        # Add nodes
        workflow.add_node("router", self.router_node)
        workflow.add_node("planner", self.planner_node)
        workflow.add_node("tool_executor", self.tool_executor_node)
        workflow.add_node("confirmation", self.confirmation_node)
        workflow.add_node("response_generator", self.response_generator_node)
        
        # Set entry point
        workflow.set_entry_point("router")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "router",
            self._route_next_node,
            {
                "planner": "planner",
                "response_generator": "response_generator"
            }
        )
        
        workflow.add_conditional_edges(
            "planner",
            self._route_next_node,
            {
                "tool_executor": "tool_executor",
                "confirmation": "confirmation",
                "response_generator": "response_generator"
            }
        )
        
        workflow.add_conditional_edges(
            "tool_executor",
            self._route_next_node,
            {
                "tool_executor": "tool_executor",  # Loop for multiple steps
                "confirmation": "confirmation",
                "response_generator": "response_generator"
            }
        )
        
        workflow.add_conditional_edges(
            "confirmation",
            self._route_next_node,
            {
                "tool_executor": "tool_executor",
                "response_generator": "response_generator"
            }
        )
        
        workflow.add_edge("response_generator", END)
        
        return workflow.compile()
    
    @traceable
    def process_message(self, message: str, user_id: int, db_session: Session) -> str:
        """Process a user message and return response"""
        # Initialize state
        state: EnhancedCalendarAgentState = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "db_session": db_session,
            "extracted_intent": None,
            "execution_plan": None,
            "tool_results": [],
            "current_step": 0,
            "requires_confirmation": False,
            "confirmation_data": None,
            "final_response": None,
            "error_state": None
        }
        
        # Create and run graph
        graph = self.create_graph()
        result = graph.invoke(state)
        
        # Return the final response
        final_response = result.get("final_response")
        if final_response and isinstance(final_response, AgentResponse):
            return final_response.message
        else:
            return "I'm sorry, I couldn't process your request properly. Please try again."
