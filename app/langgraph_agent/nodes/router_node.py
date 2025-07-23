"""
Router Node - Analyzes user messages and determines intent with task decomposition
"""

import json
from typing import Dict, Any, List
from app.langgraph_agent.llm_wrapper import LLMWrapper
from app.langgraph_agent.schemas.router_schema import (
    CalendarIntent, RouterOutput, CompoundSubtask, SubTask, TaskStatus
)
from langsmith import traceable
import uuid

@traceable(name="router_node")
def router_node_func(state: Dict[str, Any]) -> RouterOutput:
    """
    Analyze user message and determine intent with task decomposition capability
    """
    message = state.get("message", "")
    user_id = state.get("user_id")
    
    llm = LLMWrapper()
    
    # Enhanced system prompt for intent classification and task decomposition
    system_prompt = """You are a calendar assistant router. Your job is to analyze user messages and determine:
1. The primary intent
2. Whether clarification is needed
3. If it's a compound task that needs decomposition

Calendar Intents:
- SEARCH: Find/list existing events with sufficient details
- CREATE: Add new events/meetings with all required information for a task
- UPDATE: Modify existing events with all required information
- DELETE: Remove events with all required information
- SCHEDULE: Multi-user meeting coordination
- RSVP: Check attendee responses/RSVP status (who's attending, declined, etc.)
- FREE_TIME: Find free time slots, check availability, suggest meeting times, or analyze schedule availability
- COMPOUND: Multiple operations (e.g., "delete all meetings with John and create a new one")
- CLARIFY: User has provided less information than needed for the task
- KNOWLEDGE_ANALYSIS: Set up semantic search capabilities for smarter event search
- GENERAL: Conversation, help, or other

For COMPOUND tasks, break them down into subtasks.
For DELETE tasks involving search (like "delete meetings with Soham"), mark as COMPOUND.
For RSVP queries like "who is attending the meeting", "who declined", use RSVP intent.
For requests about "semantic search", "smart search", "analyze my calendar", "set up knowledge", use KNOWLEDGE_ANALYSIS.
For FREE_TIME queries like "when am I free", "find available time", "suggest meeting times", "check availability", use FREE_TIME intent.

Return ONLY a JSON object with this exact structure:
{
    "intent": "intent_name",
    "reason": "brief explanation",
    "action": "specific action if single task",
    "confidence": 0.8,
    "needs_clarification": false,
    "subtasks": [{"intent": "subtask_intent", "description": "what to do"}]]
}

You should ask for clarification when the user has given insufficient details for the task. If the intent is unclear or missing key information, set `needs_clarification` to true and provide a reason. Like a meeting can not be scheduled without date or title.

Examples:
- "Create meeting tomorrow" → {"intent": "CLARIFY", "reason": "Missing details like time, date, attendees", "needs_clarification": true}
- "Show me meetings tomorrow" → {"intent": "SEARCH", "reason": "User wants to view events", "confidence": 0.9}
- "Delete meetings with Soham" → {"intent": "COMPOUND", "subtasks": [{"intent": "SEARCH", "description": "Find meetings with Soham"}, {"intent": "DELETE", "description": "Delete found meetings"}]}
- "Set up semantic search" → {"intent": "KNOWLEDGE_ANALYSIS", "reason": "User wants to enable smart search", "confidence": 0.9}
- "When am I free tomorrow?" → {"intent": "FREE_TIME", "reason": "User wants to find available time slots", "confidence": 0.9}
- "Find 2 hours of free time this week" → {"intent": "FREE_TIME", "reason": "User wants to find specific duration of free time", "confidence": 0.9}
- "Check my availability for 2pm" → {"intent": "FREE_TIME", "reason": "User wants to check if they're available at a specific time", "confidence": 0.9}
- "Suggest meeting times with John" → {"intent": "FREE_TIME", "reason": "User wants meeting time suggestions", "confidence": 0.8}
- "Who is attending the team meeting?" → {"intent": "RSVP", "reason": "User wants to check attendee status", "confidence": 0.9}
- "Who declined the lunch meeting?" → {"intent": "RSVP", "reason": "User wants to see who declined", "confidence": 0.9}
- "Show me who hasn't responded to the event" → {"intent": "RSVP", "reason": "User wants to check pending responses", "confidence": 0.8}
"""

    user_prompt = f"User message: '{message}'"
    
    try:
        response = llm.invoke([system_prompt, user_prompt])
        
        # Clean and parse JSON response
        response_clean = response.strip()
        if response_clean.startswith('```json'):
            response_clean = response_clean[7:]
        if response_clean.endswith('```'):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()
        
        result_data = json.loads(response_clean)
        
        # Validate and create RouterOutput
        intent = CalendarIntent(result_data.get("intent", "GENERAL"))
        
        # Handle compound tasks
        subtasks = None
        if intent == CalendarIntent.COMPOUND:
            subtasks = []
            for st in result_data.get("subtasks", []):
                subtasks.append(CompoundSubtask(
                    intent=CalendarIntent(st["intent"]),
                    description=st.get("description", "")
                ))
        
        return RouterOutput(
            intent=intent,
            reason=result_data.get("reason", ""),
            action=result_data.get("action", ""),
            confidence=result_data.get("confidence", 0.5),
            needs_clarification=result_data.get("needs_clarification", False),
            subtasks=subtasks
        )
        
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Fallback routing with simple keyword matching
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["delete", "remove", "cancel"]):
            if any(word in message_lower for word in ["with", "containing", "named", "called"]):
                # Compound delete task requiring search first
                return RouterOutput(
                    intent=CalendarIntent.COMPOUND,
                    reason="Delete task requires search first",
                    confidence=0.7,
                    subtasks=[
                        CompoundSubtask(intent=CalendarIntent.SEARCH, description="Find matching events"),
                        CompoundSubtask(intent=CalendarIntent.DELETE, description="Delete found events")
                    ]
                )
            else:
                return RouterOutput(intent=CalendarIntent.DELETE, reason="Delete operation", confidence=0.6)
        
        elif any(phrase in message_lower for phrase in ["semantic search", "smart search", "analyze calendar", "set up knowledge", "knowledge analysis", "enable semantic", "setup semantic"]):
            return RouterOutput(intent=CalendarIntent.KNOWLEDGE_ANALYSIS, reason="Knowledge analysis setup", confidence=0.8)
        
        elif any(phrase in message_lower for phrase in ["free time", "available", "availability", "when am i free", "find time", "suggest meeting", "best time", "optimal time", "next available", "check availability", "free slots"]):
            return RouterOutput(intent=CalendarIntent.FREE_TIME, reason="Free time/availability query", confidence=0.8)
        
        elif any(word in message_lower for word in ["find", "show", "list", "search", "get"]):
            return RouterOutput(intent=CalendarIntent.SEARCH, reason="Search operation", confidence=0.6)
        
        elif any(word in message_lower for word in ["create", "add", "new", "schedule", "book"]):
            return RouterOutput(intent=CalendarIntent.CREATE, reason="Create operation", confidence=0.6)
        
        elif any(word in message_lower for word in ["update", "change", "modify", "edit"]):
            return RouterOutput(intent=CalendarIntent.UPDATE, reason="Update operation", confidence=0.6)
        
        else:
            return RouterOutput(
                intent=CalendarIntent.CLARIFY,
                reason=f"Could not parse intent clearly. Error: {str(e)}",
                needs_clarification=True,
                confidence=0.3
            )
