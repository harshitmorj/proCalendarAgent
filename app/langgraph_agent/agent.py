from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable
from .enhanced_tools import CalendarTools
import os
from dotenv import load_dotenv
import json
import re
from datetime import datetime, timedelta

# Load environment variables and configure LangSmith tracing
load_dotenv()

# Configure LangSmith tracing
if os.getenv("LANGCHAIN_TRACING_V2") == "true":
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "calendar-agent")
    print("🔍 LangSmith tracing enabled for calendar agent")

class CalendarAgentState(TypedDict):
    messages: list
    user_id: int
    db_session: Any
    task_type: str
    extracted_entities: dict
    tool_results: list
    requires_confirmation: bool

@traceable
class CalendarAgent:
    def __init__(self):
        # Force reload environment variables to get the latest API keys
        load_dotenv(override=True)
        
        # Initialize both OpenAI and Gemini models
        self.openai_llm = ChatOpenAI(
            model="gpt-4o-mini",  # Using a more available model
            temperature=0.3,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.gemini_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",  # Using the latest Gemini model
            temperature=0.3,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
    def call_llm_with_fallback(self, messages: list) -> str:
        """Try OpenAI first, then Gemini as fallback"""
        # Try OpenAI first
        try:
            response = self.openai_llm.invoke(messages)
            return response.content
        except Exception as openai_error:
            print(f"OpenAI API error: {openai_error}")
            
            # Fallback to Gemini
            try:
                response = self.gemini_llm.invoke(messages)
                return response.content
            except Exception as gemini_error:
                print(f"Gemini API error: {gemini_error}")
                # Final fallback
                return "I'm here to help with your calendar! For the best experience, try asking me about your events, schedule, or connected calendars. You can say things like 'Show me my next events' or 'What's my schedule today?'"
        
    @traceable(name="extract_task_intent")
    def extract_task_intent(self, message: str) -> Dict[str, Any]:
        """Extract task intent and entities from user message using LLM"""
        
        system_prompt = """You are an expert at understanding calendar-related requests. 
        Analyze the user's message and extract:
        1. Task type: read, create, update, delete, search, compound
        2. Entities: dates, times, people, locations, event details
        3. Whether it requires confirmation (for delete/update operations)
        
        Respond with JSON in this format:
        {
            "task_type": "read|create|update|delete|search|compound",
            "entities": {
                "dates": [],
                "times": [],
                "people": [],
                "locations": [],
                "event_titles": [],
                "search_terms": []
            },
            "requires_confirmation": false,
            "confidence": 0.0-1.0,
            "is_compound": false
        }
        
        Examples:
        "Show me my meetings tomorrow" → task_type: "read", entities: {"dates": ["tomorrow"]}
        "Create a team meeting at 2pm" → task_type: "create", entities: {"times": ["2pm"], "event_titles": ["team meeting"]}
        "Find my call with Sarah and cancel it" → task_type: "compound", entities: {"people": ["Sarah"]}, requires_confirmation: true
        "Delete all Friday meetings" → task_type: "delete", entities: {"dates": ["Friday"]}, requires_confirmation: true
        """
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Message: {message}"}
            ]
            
            # Convert to LangChain format
            lc_messages = [
                ("system", system_prompt),
                ("human", f"Message: {message}")
            ]
            
            response = self.openai_llm.invoke(lc_messages)
            result = json.loads(response.content)
            return result
        except Exception as e:
            print(f"LLM intent extraction error: {e}")
            # Fallback to rule-based extraction
            return self._fallback_intent_extraction(message)
    
    def _fallback_intent_extraction(self, message: str) -> Dict[str, Any]:
        """Rule-based fallback for intent extraction"""
        message_lower = message.lower()
        
        # Determine task type
        if any(word in message_lower for word in ["show", "list", "view", "get", "display", "what's"]):
            task_type = "read"
        elif any(word in message_lower for word in ["create", "add", "schedule", "book", "new"]):
            task_type = "create"
        elif any(word in message_lower for word in ["update", "change", "modify", "edit", "reschedule"]):
            task_type = "update"
        elif any(word in message_lower for word in ["delete", "remove", "cancel"]):
            task_type = "delete"
        elif any(word in message_lower for word in ["find", "search", "look for"]):
            task_type = "search"
        else:
            task_type = "read"  # Default
        
        # Extract entities
        entities = {
            "dates": [],
            "times": [],
            "people": [],
            "locations": [],
            "event_titles": [],
            "search_terms": []
        }
        
        # Basic date extraction
        date_patterns = ["today", "tomorrow", "yesterday", "friday", "monday", "tuesday", "wednesday", "thursday", "saturday", "sunday"]
        for pattern in date_patterns:
            if pattern in message_lower:
                entities["dates"].append(pattern)
        
        # Basic time extraction
        time_matches = re.findall(r'\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)', message_lower)
        entities["times"] = time_matches
        
        # Extract potential search terms
        if task_type in ["search", "update", "delete"]:
            # Remove common words and extract meaningful terms
            words = message_lower.split()
            meaningful_words = [w for w in words if len(w) > 2 and w not in ["the", "and", "with", "for", "my", "me", "find", "search", "delete", "cancel", "update"]]
            entities["search_terms"] = meaningful_words
        
        # Check for compound operations
        is_compound = any(phrase in message_lower for phrase in ["and then", "and cancel", "and delete", "and update", "and reschedule"])
        
        return {
            "task_type": task_type,
            "entities": entities,
            "requires_confirmation": task_type in ["delete", "update"] or "cancel" in message_lower,
            "confidence": 0.7,
            "is_compound": is_compound
        }
    
    @traceable(name="router_node")
    def router_node(self, state: CalendarAgentState) -> CalendarAgentState:
        """Route and extract intent from the user message"""
        last_message = state["messages"][-1] if state["messages"] else None
        
        if isinstance(last_message, HumanMessage):
            intent = self.extract_task_intent(last_message.content)
            state["task_type"] = intent["task_type"]
            state["extracted_entities"] = intent["entities"]
            state["requires_confirmation"] = intent["requires_confirmation"]
            state["tool_results"] = []
        
        return state
    
    @traceable(name="tool_executor_node")
    def tool_executor_node(self, state: CalendarAgentState) -> CalendarAgentState:
        """Execute calendar tools based on extracted intent"""
        task_type = state.get("task_type", "read")
        entities = state.get("extracted_entities", {})
        
        try:
            # Initialize calendar tools
            calendar_tools = CalendarTools(state["user_id"], state["db_session"])
            
            if task_type == "read":
                # Get events
                result = calendar_tools.get_events(limit=15)
                
            elif task_type == "search":
                # Search for events
                from .schemas import SearchQuery
                search_text = " ".join(entities.get("search_terms", []))
                if entities.get("people"):
                    search_text += " " + " ".join(entities["people"])
                
                query = SearchQuery(text=search_text, limit=20)
                result = calendar_tools.search_events(query)
                
            elif task_type == "create":
                # Create event (simplified)
                from .schemas import CreateEventRequest, EventData
                from datetime import datetime, timedelta
                
                title = " ".join(entities.get("event_titles", ["New Event"]))
                start_time = datetime.now() + timedelta(hours=1)  # Default to 1 hour from now
                end_time = start_time + timedelta(hours=1)
                
                event_data = EventData(
                    title=title,
                    start_datetime=start_time,
                    end_datetime=end_time
                )
                
                request = CreateEventRequest(event_data=event_data)
                result = calendar_tools.create_event(request)
                
            elif task_type in ["update", "delete"] and not state.get("requires_confirmation"):
                # For update/delete, first search then act
                from .schemas import SearchQuery
                search_text = " ".join(entities.get("search_terms", []))
                query = SearchQuery(text=search_text, limit=5)
                result = calendar_tools.search_events(query)
                
                if result.success and result.data:
                    # Found events, need confirmation
                    state["requires_confirmation"] = True
                    result.metadata["pending_operation"] = task_type
                    result.metadata["found_events"] = len(result.data)
                
            else:
                # Default to getting calendar summary
                result = calendar_tools.get_calendar_summary()
            
            state["tool_results"].append(result)
            
        except Exception as e:
            print(f"Tool execution error: {e}")
            from .schemas import ToolResult
            error_result = ToolResult(
                success=False,
                error=f"Failed to execute {task_type}: {str(e)}"
            )
            state["tool_results"].append(error_result)
        
        return state
    
    @traceable(name="response_generator_node")
    def response_generator_node(self, state: CalendarAgentState) -> CalendarAgentState:
        """Generate human-readable response from tool results"""
        tool_results = state.get("tool_results", [])
        task_type = state.get("task_type", "read")
        
        if not tool_results:
            response = "I couldn't process your request. Please try again."
        elif state.get("requires_confirmation"):
            # Handle confirmation requests
            result = tool_results[-1] if tool_results else None
            if result and result.success and result.data:
                if isinstance(result.data, list) and result.data:
                    event_count = len(result.data)
                    operation = result.metadata.get("pending_operation", "modify")
                    
                    response = f"⚠️ I found {event_count} event(s) that match your search. "
                    response += f"Are you sure you want to {operation} "
                    response += "these events? Please confirm by saying 'yes' or provide more specific criteria."
                    
                    # Show the found events
                    response += "\n\nFound events:\n"
                    for i, event in enumerate(result.data[:3]):  # Show first 3
                        response += f"{i+1}. **{event.get('title', 'Untitled')}** - {event.get('start', '')}\n"
                    if event_count > 3:
                        response += f"... and {event_count - 3} more\n"
                else:
                    response = f"Are you sure you want to {task_type} this event? Please confirm."
            else:
                response = "I couldn't find the event you're referring to. Please be more specific."
        else:
            # Normal responses
            result = tool_results[-1] if tool_results else None
            if result and result.success:
                response = self._format_tool_result(result, task_type)
            else:
                error = result.error if result else "Unknown error"
                response = f"Sorry, I encountered an error: {error}"
        
        # Add the AI response to messages
        state["messages"].append(AIMessage(content=response))
        return state
    
    @traceable(name="format_tool_result")
    def _format_tool_result(self, result, task_type: str) -> str:
        """Format tool result into human-readable response"""
        if not result.data:
            return "No results found."
        
        if task_type == "read":
            if isinstance(result.data, list):
                if not result.data:
                    return "No upcoming events found."
                
                response = f"📅 Here are your upcoming events ({len(result.data)} found):\n\n"
                for event in result.data[:10]:  # Show first 10
                    response += f"**{event.get('title', 'Untitled')}**\n"
                    response += f"📅 {event.get('start', '')} to {event.get('end', '')}\n"
                    if event.get('location'):
                        response += f"📍 {event['location']}\n"
                    response += f"🔗 {event.get('provider', '').title()} ({event.get('account_email', '')})\n\n"
                
                if len(result.data) > 10:
                    response += f"... and {len(result.data) - 10} more events\n"
                
                return response
        
        elif task_type == "search":
            if isinstance(result.data, list):
                count = len(result.data)
                if count == 0:
                    return "No events found matching your search criteria."
                elif count == 1:
                    event = result.data[0]
                    return f"✅ Found 1 event:\n**{event.get('title', 'Untitled')}**\n📅 {event.get('start', '')} to {event.get('end', '')}"
                else:
                    response = f"✅ Found {count} events matching your search:\n\n"
                    for event in result.data[:5]:  # Show first 5
                        response += f"• **{event.get('title', 'Untitled')}** - {event.get('start', '')}\n"
                    if count > 5:
                        response += f"... and {count - 5} more\n"
                    return response
        
        elif task_type == "create":
            if isinstance(result.data, dict) and 'title' in result.data:
                event = result.data
                return f"✅ Successfully created event:\n**{event.get('title')}**\n📅 {event.get('start', '')} to {event.get('end', '')}"
        
        # Default formatting
        if isinstance(result.data, list):
            return f"Found {len(result.data)} items."
        elif isinstance(result.data, dict):
            return "Operation completed successfully."
        else:
            return str(result.data)
    
    def create_graph(self):
        """Create the LangGraph workflow"""
        workflow = StateGraph(CalendarAgentState)
        
        # Add nodes
        workflow.add_node("router", self.router_node)
        workflow.add_node("tool_executor", self.tool_executor_node)
        workflow.add_node("response_generator", self.response_generator_node)
        
        # Set entry point
        workflow.set_entry_point("router")
        
        # Add edges
        workflow.add_edge("router", "tool_executor")
        workflow.add_edge("tool_executor", "response_generator")
        workflow.add_edge("response_generator", END)
        
        return workflow.compile()
    
    @traceable
    def process_message(self, message: str, user_id: int, db_session) -> str:
        """Process a user message and return response"""
        # Initialize state
        state: CalendarAgentState = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "db_session": db_session,
            "task_type": "read",
            "extracted_entities": {},
            "tool_results": [],
            "requires_confirmation": False
        }
        
        # Create and run graph
        graph = self.create_graph()
        result = graph.invoke(state)
        
        # Return the last AI message
        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        return ai_messages[-1].content if ai_messages else "I'm sorry, I couldn't process your request."
