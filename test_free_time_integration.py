#!/usr/bin/env python3
"""
Test Free Time Integration - Test the complete free time functionality
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.database import get_db
from app.langgraph_agent.agent import CalendarAgent

def test_free_time_queries():
    """Test various free time queries through the agent"""
    
    # Initialize the agent
    agent = CalendarAgent()
    db_session = next(get_db())
    
    test_cases = [
        {
            "query": "When am I free tomorrow?",
            "expected_intent": "free_time",
            "description": "Basic free time query"
        },
        {
            "query": "Find me 2 hours of free time this week",
            "expected_intent": "free_time", 
            "description": "Specific duration request"
        },
        {
            "query": "Check my availability for 2pm today",
            "expected_intent": "free_time",
            "description": "Availability check"
        },
        {
            "query": "Suggest meeting times with john@example.com",
            "expected_intent": "free_time",
            "description": "Meeting suggestions"
        },
        {
            "query": "What's my next available time slot?",
            "expected_intent": "free_time",
            "description": "Next available query"
        },
        {
            "query": "How busy am I this week?",
            "expected_intent": "free_time",
            "description": "Availability summary"
        },
        {
            "query": "Show me free time including weekends",
            "expected_intent": "free_time",
            "description": "Weekend inclusion"
        },
        {
            "query": "Find me morning slots only",
            "expected_intent": "free_time",
            "description": "Time preference"
        }
    ]
    
    print("🧪 Testing Free Time Agent Integration")
    print("=" * 50)
    
    user_id = 2  # Test with user 2
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"Query: '{test_case['query']}'")
        
        try:
            # Process the query through the agent
            response = agent.process_message(
                message=test_case["query"],
                user_id=user_id,
                db_session=db_session
            )
            
            print(f"✅ Response: {response[:200]}{'...' if len(response) > 200 else ''}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
    
    db_session.close()

def test_router_intent_classification():
    """Test that the router correctly classifies free time queries"""
    
    from app.langgraph_agent.nodes.router_node import router_node_func
    
    test_queries = [
        "When am I free tomorrow?",
        "Find available time slots",
        "Check my availability for 3pm",
        "Suggest meeting times",
        "What's my next free slot?",
        "How busy am I this week?",
        "Find me 30 minutes of free time",
        "Am I available at 2pm on Friday?",
    ]
    
    print("\n🎯 Testing Router Intent Classification for Free Time")
    print("=" * 55)
    
    for query in test_queries:
        try:
            state = {"message": query, "user_id": 2}
            result = router_node_func(state)
            
            print(f"\nQuery: '{query}'")
            print(f"Intent: {result.intent}")
            print(f"Confidence: {result.confidence}")
            print(f"Reason: {result.reason}")
            
            if result.intent == "free_time":
                print("✅ Correctly classified as FREE_TIME")
            else:
                print(f"⚠️  Classified as {result.intent} instead of FREE_TIME")
                
        except Exception as e:
            print(f"❌ Error processing '{query}': {str(e)}")

def test_direct_free_time_node():
    """Test the free time node directly"""
    
    from app.langgraph_agent.nodes.free_time_node import free_time_node
    from app.database.database import get_db
    
    print("\n🔧 Testing Free Time Node Directly")
    print("=" * 40)
    
    db_session = next(get_db())
    
    test_states = [
        {
            "message": "When am I free tomorrow?",
            "user_id": 2,
            "db_session": db_session,
            "action": "find_free_time"
        },
        {
            "message": "Check my availability for 2pm today",
            "user_id": 2,
            "db_session": db_session,
            "action": "check_availability"
        },
        {
            "message": "Suggest meeting times with john@example.com for 1 hour",
            "user_id": 2,
            "db_session": db_session,
            "action": "suggest_meeting_times"
        },
        {
            "message": "What's my next available time?",
            "user_id": 2,
            "db_session": db_session,
            "action": "next_available"
        },
        {
            "message": "How busy am I this week?",
            "user_id": 2,
            "db_session": db_session,
            "action": "availability_summary"
        }
    ]
    
    for i, state in enumerate(test_states, 1):
        print(f"\n{i}. Testing: {state['message']}")
        
        try:
            result = free_time_node(state)
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                response = result.get("response", "No response")
                print(f"✅ Response: {response[:150]}{'...' if len(response) > 150 else ''}")
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
    
    db_session.close()

if __name__ == "__main__":
    print("🚀 Starting Free Time Integration Tests")
    print("=" * 60)
    
    # Test 1: Router classification
    test_router_intent_classification()
    
    # Test 2: Direct node testing
    test_direct_free_time_node()
    
    # Test 3: Full agent integration
    test_free_time_queries()
    
    print("\n" + "=" * 60)
    print("✅ Free Time Integration Tests Complete!")
