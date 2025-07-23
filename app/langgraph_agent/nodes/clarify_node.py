"""
Clarify Node - Handles clarification requests when user intent is unclear
"""

from typing import Dict, Any
from app.langgraph_agent.llm_wrapper import LLMWrapper
from app.langgraph_agent.schemas.router_schema import HumanFeedback

def clarify_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ask for clarification when user intent is unclear or information is missing
    """
    message = state.get("message", "")
    action = state.get("action", "")
    intent = state.get("intent", "")
    
    llm = LLMWrapper()
    
    # System prompt for generating clarification questions
    system_prompt = """You are a calendar assistant that needs to ask clarifying questions. The user's request was unclear or missing important information.

Based on the user's message and the detected intent, ask specific clarifying questions to gather the missing information needed to complete their calendar task.

For different intents, you typically need:
- CREATE: title, date/time, duration, location, attendees
- SEARCH: what to search for, date range, specific criteria  
- UPDATE: which event to update, what to change
- DELETE: which events to delete, confirmation criteria
- SCHEDULE: participants, duration, preferred times, date range

Ask 1-2 specific questions rather than overwhelming the user. Be friendly and helpful.

Examples:
- For "create meeting": "I'd be happy to create a meeting for you! Could you tell me the title, date/time, and who should attend?"
- For "delete meeting": "I can help delete meetings. Which specific meeting would you like me to remove, or what criteria should I use to find it?"
- For "show meetings": "I'll show you your meetings. Would you like to see today's events, this week's, or a specific date range?"

Provide a clear, friendly clarification request.
"""
    
    try:
        prompt = f"User message: '{message}'\nDetected intent: {intent}\nAction context: {action}\n\nWhat clarifying questions should I ask?"
        
        response = llm.invoke([system_prompt, prompt])
        
        # Create human feedback request for clarification
        human_feedback = HumanFeedback(
            feedback_type="clarification",
            question=response,
            user_input="",
            options=None
        )
        
        return {
            **state,
            "response": response,
            "requires_human_input": True,
            "human_feedback": human_feedback,
            "status": "awaiting_clarification"
        }
        
    except Exception as e:
        # Fallback clarification based on intent
        if intent == "CREATE" or intent == "create":
            clarification = """I'd like to help you create an event! To get started, I need a few details:

📝 **What should I include?**
- Event title (e.g., "Team Meeting", "Lunch with John")
- Date and time (e.g., "tomorrow at 2pm", "next Friday 10am-11am") 
- Location (optional)
- Who should attend? (optional)

**Example:** "Create Team Standup tomorrow at 9am for 30 minutes in Conference Room A"

What event would you like me to create?"""
        
        elif intent == "SEARCH" or intent == "search":
            clarification = """I can help you find events! What would you like me to search for?

🔍 **Search options:**
- Show specific time period: "show me today's meetings"
- Find events with keywords: "meetings with John"  
- Filter by date: "events next week"
- Find by location: "conference room bookings"

**Examples:**
- "Show me tomorrow's schedule"
- "Find all meetings with Sarah"
- "What do I have this afternoon?"

What events are you looking for?"""
        
        elif intent == "DELETE" or intent == "delete":
            clarification = """I can help you delete events. To be safe and accurate, could you specify:

🗑️ **Which events to delete?**
- Specific event: "delete my 3pm meeting today"
- Events with criteria: "delete all meetings with John"
- Events in timeframe: "delete tomorrow's appointments"

**Examples:**
- "Delete my lunch meeting with Sarah"
- "Remove all events containing 'standup'"
- "Cancel meetings on Friday"

Which events would you like me to delete?"""
        
        else:
            clarification = f"""I want to help you with your calendar, but I need a bit more information about what you'd like to do.

Your message: "{message}"

Could you provide more details about:
- What specific action you want me to take?
- Which events or time periods are involved?
- Any specific requirements or preferences?

**Examples of clear requests:**
- "Show me meetings tomorrow"
- "Create team lunch next Friday at noon"  
- "Delete the meeting with John at 3pm"
- "Find time for a 1-hour call with Sarah next week"

How can I help you with your calendar?"""
        
        human_feedback = HumanFeedback(
            feedback_type="clarification",
            question=clarification,
            user_input="",
            options=None
        )
        
        return {
            **state,
            "response": clarification,
            "requires_human_input": True,
            "human_feedback": human_feedback,
            "status": "awaiting_clarification",
            "error": f"Clarification fallback used due to: {str(e)}"
        }
