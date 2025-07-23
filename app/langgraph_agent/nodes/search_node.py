"""
Search Node - Handles event search operations with semantic search support
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.langgraph_agent.schemas.router_schema import SearchResult, TaskStatus
from app.langgraph_agent.llm_wrapper import LLMWrapper
from app.langgraph_agent.knowledge.semantic_search import SemanticEventSearch, format_semantic_results
from langsmith import traceable

@traceable(name="search_node")
def search_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for calendar events based on query parameters with semantic search support
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
            "response": "Error: User ID is required for search operations",
            "error": "Missing user_id"
        }
    
    # Extract search parameters
    search_params = extract_search_parameters(message, action, task_context, current_subtask_id or "")
    
    try:
        # Initialize integrated calendar
        integrated_cal = IntegratedCalendar(user_id=user_id, db_session=db_session)
        
        # Initialize semantic search
        semantic_search = SemanticEventSearch(user_id=user_id)
        use_semantic_search = semantic_search.is_available() and search_params.get("query")
        
        # Perform search based on parameters
        events = []
        semantic_results = []
        
        if search_params.get("query"):
            # Try semantic search first if available
            if use_semantic_search:
                semantic_results = semantic_search.semantic_search(
                    query=search_params["query"],
                    limit=search_params.get("limit", 20),
                    threshold=0.6  # Adjust threshold as needed
                )
                
                # If semantic search finds good results, use them
                if semantic_results and len(semantic_results) > 0:
                    # Convert semantic results to event format
                    events = []
                    for result in semantic_results:
                        event = {
                            "id": result.get("event_id"),
                            "title": result.get("title"),
                            "description": "",
                            "start": result.get("start"),
                            "end": result.get("end"),
                            "provider": result.get("provider"),
                            "account_email": "",
                            "location": result.get("location", ""),
                            "attendees": result.get("attendees", "").split(", ") if result.get("attendees") else [],
                            "similarity_score": result.get("similarity_score", 0.0),
                            "matched_text": result.get("matched_text", "")
                        }
                        events.append(event)
                
            # Fallback to traditional text search if semantic search unavailable or no results
            if not events:
                events = integrated_cal.search_events(
                    query=search_params["query"],
                    limit=search_params.get("limit", 20)
                )
        else:
            # Date-based search - handle None values properly
            start_date = search_params.get("start_date")
            if start_date is None:
                start_date = datetime.now()
            
            end_date = search_params.get("end_date")
            if end_date is None:
                end_date = start_date + timedelta(days=7)
            
            events = integrated_cal.get_all_events(
                start_date=start_date,
                end_date=end_date,
                max_results=search_params.get("limit", 20)
            )
        
        # Convert to SearchResult objects
        search_results = []
        for event in events:
            search_result = SearchResult(
                event_id=event.get("id", ""),
                title=event.get("title", "Untitled"),
                description=event.get("description", ""),
                start_time=event.get("start", ""),
                end_time=event.get("end", ""),
                provider=event.get("provider", ""),
                account_email=event.get("account_email", ""),
                location=event.get("location", ""),
                attendees=event.get("attendees", [])
            )
            search_results.append(search_result)
        
        # Update task context if this is part of a compound task
        if task_context and current_subtask_id:
            current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
            if current_task:
                current_task.status = TaskStatus.COMPLETED
                current_task.search_results = [result.dict() for result in search_results]
                current_task.result = {
                    "summary": f"Found {len(search_results)} events",
                    "count": len(search_results)
                }
        
        # Generate response
        if search_results:
            # Use semantic search formatting if semantic results were used
            if use_semantic_search and semantic_results:
                response = format_semantic_results(semantic_results, search_params.get("query", ""))
            else:
                # Traditional search result formatting
                response = f"Found {len(search_results)} events:\n\n"
                for i, result in enumerate(search_results[:5], 1):
                    response += f"{i}. **{result.title}**\n"
                    response += f"   📅 {result.start_time}\n"
                    response += f"   🏢 {result.provider} ({result.account_email})\n"
                    if result.location:
                        response += f"   📍 {result.location}\n"
                    response += "\n"
                
                if len(search_results) > 5:
                    response += f"... and {len(search_results) - 5} more events\n"
        else:
            response = "No events found matching your criteria."
            
            # If semantic search was unavailable, mention it
            if search_params.get("query") and not use_semantic_search:
                search_stats = semantic_search.get_stats()
                if not search_stats.get("available", False):
                    response += f"\n\n💡 **Tip**: Semantic search is not available. {search_stats.get('reason', 'Run the knowledge analysis to enable smarter search.')}"
        
        return {
            **state,
            "search_results": search_results,
            "response": response,
            "task_context": task_context
        }
        
    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        
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

def extract_search_parameters(message: str, action: str, task_context, current_subtask_id: str) -> Dict[str, Any]:
    """
    Extract search parameters from message, action, or task context
    """
    params = {}
    
    # If this is part of a compound task, get parameters from subtask
    if task_context and current_subtask_id:
        current_task = next((t for t in task_context.subtasks if t.id == current_subtask_id), None)
        if current_task and current_task.parameters:
            params.update(current_task.parameters)
    
    # Extract from message using LLM
    if not params.get("query"):
        llm = LLMWrapper()
        
        system_prompt = """Extract search parameters from this calendar search request.
        
        Return JSON with:
        {
            "query": "text to search for (names, titles, keywords)",
            "start_date": "YYYY-MM-DD or null for default",
            "end_date": "YYYY-MM-DD or null for default", 
            "limit": 20
        }
        
        Examples:
        - "meetings with Soham" → {"query": "Soham"}
        - "events tomorrow" → {"start_date": "tomorrow 00:00", "end_date": "tomorrow 23:59"}
        - "show me this week" → {"start_date": "this week start", "end_date": "this week end"}
        """
        
        try:
            # Properly format the request message
            request_text = message
            if action and action.strip():
                request_text = f"{message} {action}"
            
            response = llm.invoke([system_prompt, f"Request: {request_text}"])
            
            import json
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:-3]
            
            extracted_params = json.loads(response_clean)
            params.update(extracted_params)
            
        except Exception:
            # Fallback: simple keyword extraction
            message_lower = message.lower()
            if action and action.strip():
                message_lower = f"{message} {action}".lower()
            
            # Look for names or keywords
            if any(word in message_lower for word in ["with", "containing", "named", "called"]):
                # Extract search terms
                for pattern in ["with ", "containing ", "named ", "called "]:
                    if pattern in message_lower:
                        start_idx = message_lower.find(pattern) + len(pattern)
                        remaining = message_lower[start_idx:].split()
                        search_terms = []
                        for word in remaining:
                            if word in ["and", "or", "from", "on", "at", "in"]:
                                break
                            search_terms.append(word.strip(".,!?\"'"))
                        if search_terms:
                            params["query"] = " ".join(search_terms)
                        break
    
    # Set defaults
    if not params.get("limit"):
        params["limit"] = 20
    
    # Parse date strings
    if params.get("start_date") and isinstance(params["start_date"], str):
        params["start_date"] = parse_date_string(params["start_date"])
    if params.get("end_date") and isinstance(params["end_date"], str):
        params["end_date"] = parse_date_string(params["end_date"])
    
    return params

def parse_date_string(date_str: str) -> datetime:
    """
    Parse natural language date strings
    """
    date_str = date_str.lower().strip()
    now = datetime.now()
    
    if date_str in ["today"]:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_str in ["tomorrow"]:
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif "week" in date_str:
        # Start of current week
        days_since_monday = now.weekday()
        start_of_week = now - timedelta(days=days_since_monday)
        return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    elif "month" in date_str:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Try to parse as ISO date
        try:
            return datetime.fromisoformat(date_str)
        except:
            return now
