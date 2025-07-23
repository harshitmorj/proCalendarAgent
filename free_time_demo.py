#!/usr/bin/env python3
"""
Free Time Demo - Simple working demonstration of the free time functionality
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.langgraph_agent.agent import CalendarAgent
from app.database.database import get_db

def demo_free_time_agent():
    """Demonstrate the free time functionality with working queries"""
    
    print("🚀 Free Time Agent Demo")
    print("=" * 40)
    
    # Initialize the agent
    agent = CalendarAgent()
    db_session = next(get_db())
    user_id = 2  # Test with user 2
    
    # Working test cases that should succeed
    working_queries = [
        "When am I free tomorrow?",
        "Find me free time this week",
        "Show me available time slots",
        "When can I schedule a 30 minute meeting?"
    ]
    
    for i, query in enumerate(working_queries, 1):
        print(f"\n{i}. Query: '{query}'")
        print("-" * 50)
        
        try:
            response = agent.process_message(
                message=query,
                user_id=user_id,
                db_session=db_session
            )
            
            # Print response nicely
            lines = response.split('\n')
            for line in lines[:15]:  # First 15 lines
                print(line)
            
            if len(lines) > 15:
                print("...")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    db_session.close()
    print("\n" + "=" * 40)
    print("✅ Free Time Demo Complete!")

if __name__ == "__main__":
    demo_free_time_agent()
