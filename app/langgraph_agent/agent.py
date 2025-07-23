# agent.py
from typing import List, Dict, Any, Optional
from app.langgraph_agent.graph.calendar_graph import calendar_graph


class CalendarAgent:
    def __init__(self):
        self.graph = calendar_graph

    def process_message(self, message: str, user_id: Optional[int] = None, db_session=None, memory=None):
        input_data = {
            "message": message,
            "user_id": user_id,
            "db_session": db_session,
            "memory": memory
        }
        
        # Enhanced config with tracing metadata
        config = {
            "recursion_limit": 50,
            "tags": ["calendar-agent-session", "user-request"],
            "metadata": {
                "user_id": user_id,
                "message_preview": message[:50] + "..." if len(message) > 50 else message,
                "session_type": "calendar_interaction"
            }
        }
        
        result = self.graph.invoke(input_data, config=config)
        return result["response"]
