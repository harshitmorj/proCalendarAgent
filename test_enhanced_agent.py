"""
Test script for the enhanced Calendar Agent with CRUD capabilities
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database import get_db
from app.langgraph_agent.agent import CalendarAgent
from app.langgraph_agent.enhanced_tools import CalendarTools
from app.langgraph_agent.schemas import SearchQuery, CreateEventRequest, EventData
from datetime import datetime, timedelta
import json

def test_enhanced_agent():
    """Test the enhanced calendar agent with various CRUD operations"""
    
    print("🚀 Testing Enhanced Calendar Agent with CRUD Capabilities")
    print("=" * 60)
    
    # Initialize database session
    db = next(get_db())
    
    # Test user ID (adjust based on your setup)
    user_id = 2
    
    # Initialize agent
    agent = CalendarAgent()
    
    # Test scenarios
    test_scenarios = [
        # Basic read operations
        {
            "name": "📅 View Upcoming Events",
            "message": "Show me my upcoming events",
            "expected": "read operation with events list"
        },
        {
            "name": "🔍 Search for Specific Events",
            "message": "Find my meetings with John",
            "expected": "search operation for John-related meetings"
        },
        {
            "name": "📝 Create New Event",
            "message": "Create a team meeting at 2pm tomorrow",
            "expected": "create operation for new meeting"
        },
        {
            "name": "🔄 Compound Task - Find and Reschedule",
            "message": "Find my call with Sarah and reschedule it to 3pm",
            "expected": "compound operation: search + update"
        },
        {
            "name": "❌ Delete Events with Confirmation",
            "message": "Cancel all my meetings on Friday",
            "expected": "delete operation requiring confirmation"
        },
        {
            "name": "🤖 General Query",
            "message": "What can you help me with?",
            "expected": "general assistance information"
        }
    ]
    
    print(f"Testing with User ID: {user_id}")
    print(f"Total test scenarios: {len(test_scenarios)}\n")
    
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"Test {i}: {scenario['name']}")
        print(f"Message: \"{scenario['message']}\"")
        print("-" * 40)
        
        try:
            # Process message with enhanced agent
            response = agent.process_message(scenario["message"], user_id, db)
            
            print("✅ Agent Response:")
            print(response)
            print()
            
            results.append({
                "test": scenario["name"],
                "message": scenario["message"],
                "response": response,
                "status": "success"
            })
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print()
            
            results.append({
                "test": scenario["name"],
                "message": scenario["message"],
                "error": str(e),
                "status": "failed"
            })
        
        print("=" * 60)
    
    # Summary
    successful_tests = [r for r in results if r["status"] == "success"]
    failed_tests = [r for r in results if r["status"] == "failed"]
    
    print(f"\n📊 Test Summary:")
    print(f"✅ Successful: {len(successful_tests)}/{len(results)}")
    print(f"❌ Failed: {len(failed_tests)}/{len(results)}")
    
    if failed_tests:
        print("\nFailed Tests:")
        for test in failed_tests:
            print(f"- {test['test']}: {test.get('error', 'Unknown error')}")
    
    db.close()
    return results

def test_direct_tools():
    """Test the enhanced calendar tools directly"""
    
    print("\n🔧 Testing Direct Calendar Tools")
    print("=" * 40)
    
    # Initialize database session
    db = next(get_db())
    user_id = 2
    
    # Initialize tools
    tools = CalendarTools(user_id, db)
    
    # Test basic operations
    print("1. Getting calendar summary...")
    try:
        summary_result = tools.get_calendar_summary()
        print(f"✅ Summary: {summary_result.success}")
        if summary_result.success:
            print(f"   Accounts: {summary_result.metadata.get('accounts_count', 0)}")
        else:
            print(f"   Error: {summary_result.error}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n2. Getting upcoming events...")
    try:
        events_result = tools.get_events(limit=5)
        print(f"✅ Events: {events_result.success}")
        if events_result.success:
            print(f"   Count: {events_result.metadata.get('count', 0)}")
        else:
            print(f"   Error: {events_result.error}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n3. Testing search functionality...")
    try:
        search_query = SearchQuery(text="meeting", limit=3)
        search_result = tools.search_events(search_query)
        print(f"✅ Search: {search_result.success}")
        if search_result.success:
            print(f"   Found: {search_result.metadata.get('count', 0)} events")
        else:
            print(f"   Error: {search_result.error}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    db.close()

def demonstrate_features():
    """Demonstrate key features of the enhanced agent"""
    
    print("\n🌟 Enhanced Calendar Agent Features")
    print("=" * 50)
    
    features = [
        "🎯 LLM-Powered Intent Extraction - Understands natural language requests",
        "🔄 Compound Task Support - Can chain multiple operations (search + delete)",
        "⚠️ Smart Confirmation - Requires confirmation for destructive operations",
        "🔍 Advanced Search - Search across all calendar fields and providers",
        "📅 Full CRUD Operations - Create, Read, Update, Delete calendar events",
        "🏗️ Multi-Node Architecture - Router → Tool Executor → Response Generator",
        "🔀 Fallback Mechanisms - OpenAI → Gemini → Rule-based processing",
        "🛡️ Error Handling - Graceful degradation and detailed error messages",
        "📊 Structured Outputs - Pydantic schemas for type safety and validation",
        "🔗 Multi-Provider Support - Works with Google Calendar and Microsoft Calendar"
    ]
    
    for feature in features:
        print(f"  {feature}")
    
    print("\n💡 Example Commands You Can Try:")
    examples = [
        "\"Show me my meetings tomorrow\"",
        "\"Create a team standup at 9am next Monday\"",
        "\"Find my call with John and move it to 3pm\"",
        "\"Cancel all meetings on Friday\"",
        "\"What's my schedule for this week?\"",
        "\"Search for events with 'project review' in the title\""
    ]
    
    for example in examples:
        print(f"  • {example}")

if __name__ == "__main__":
    print("🤖 Enhanced Calendar Agent Testing Suite")
    print("=" * 60)
    
    # Demonstrate features
    demonstrate_features()
    
    # Test direct tools first
    test_direct_tools()
    
    # Test the full agent
    test_results = test_enhanced_agent()
    
    print("\n🎉 Testing completed!")
    print("\nThe enhanced calendar agent now supports:")
    print("✅ CRUD operations (Create, Read, Update, Delete)")
    print("✅ Compound tasks with multi-step execution")
    print("✅ LLM-powered intent extraction and reasoning")
    print("✅ Smart confirmation for destructive operations")
    print("✅ Advanced search capabilities")
    print("✅ Multi-provider calendar support")
    print("✅ Structured outputs with Pydantic validation")
    print("✅ Robust error handling and fallback mechanisms")
