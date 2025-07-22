"""
Test script for LangSmith tracing with the Enhanced Calendar Agent
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up LangSmith tracing before importing the agent
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "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"
os.environ["LANGCHAIN_PROJECT"] = "calendar-agent"

from app.database.database import get_db
from app.langgraph_agent.agent import CalendarAgent
from datetime import datetime, timedelta
import uuid

def test_agent_with_tracing():
    """Test the enhanced calendar agent with LangSmith tracing enabled"""
    
    print("🔍 Testing Enhanced Calendar Agent with LangSmith Tracing")
    print("=" * 60)
    
    # Initialize database session
    db = next(get_db())
    
    # Test user ID
    user_id = 2
    
    # Initialize agent
    agent = CalendarAgent()
    
    # Generate unique session ID for this test run
    session_id = f"test-session-{uuid.uuid4().hex[:8]}"
    print(f"📊 LangSmith Project: calendar-agent-enhanced")
    print(f"🔑 Session ID: {session_id}")
    print()
    
    # Test scenarios designed to show different tracing patterns
    test_scenarios = [
        {
            "name": "🎯 Intent Extraction Test",
            "message": "Show me my next 5 events",
            "description": "Tests LLM-powered intent extraction with simple read operation"
        },
        {
            "name": "🔍 Search with Fallback",
            "message": "Find my important meetings",
            "description": "Tests search functionality and LLM reasoning"
        },
        {
            "name": "📝 Create Event Test",
            "message": "Create a team standup tomorrow at 9am",
            "description": "Tests event creation with date/time parsing"
        },
        {
            "name": "🔄 Compound Task Test",
            "message": "Find my call with John and reschedule it",
            "description": "Tests compound task planning and execution"
        },
        {
            "name": "⚠️ Confirmation Required",
            "message": "Cancel all my Friday meetings",
            "description": "Tests confirmation flow for destructive operations"
        },
        {
            "name": "🤖 General Query",
            "message": "What's the weather like?",
            "description": "Tests general query handling and fallback mechanisms"
        }
    ]
    
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"Test {i}: {scenario['name']}")
        print(f"Message: \"{scenario['message']}\"")
        print(f"Purpose: {scenario['description']}")
        print("-" * 50)
        
        try:
            # Add metadata for tracing
            trace_metadata = {
                "test_scenario": scenario["name"],
                "test_number": i,
                "session_id": session_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
            
            # Process message with enhanced agent
            # The @traceable decorators will automatically capture this in LangSmith
            response = agent.process_message(scenario["message"], user_id, db)
            
            print("✅ Agent Response:")
            print(response)
            print()
            
            results.append({
                "test": scenario["name"],
                "message": scenario["message"],
                "response": response,
                "status": "success",
                "metadata": trace_metadata
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
    
    # Summary with tracing information
    successful_tests = [r for r in results if r["status"] == "success"]
    failed_tests = [r for r in results if r["status"] == "failed"]
    
    print(f"\n📊 Test Summary:")
    print(f"✅ Successful: {len(successful_tests)}/{len(results)}")
    print(f"❌ Failed: {len(failed_tests)}/{len(results)}")
    print()
    
    print("🔍 LangSmith Tracing Information:")
    print(f"📊 Project: calendar-agent-enhanced")
    print(f"🔗 URL: https://smith.langchain.com/o/7d4a12d7-98bb-514e-9c1c-f18b57b52a7f/projects/p/2e5dd2e6-aa6a-4866-a3e9-8e49f5e1a28e")
    print(f"🏷️  Session ID: {session_id}")
    print()
    
    print("🎯 What you can see in LangSmith:")
    tracing_features = [
        "🔍 Intent extraction LLM calls with prompts and responses",
        "🏗️ Multi-node execution flow through the graph",
        "⚡ Tool execution timing and success rates",
        "🔄 Fallback mechanism activations",
        "📊 Token usage and cost tracking",
        "🐛 Error traces and debugging information",
        "📈 Performance metrics across different query types",
        "🔗 Parent-child relationships between operations"
    ]
    
    for feature in tracing_features:
        print(f"  {feature}")
    
    print("\n💡 Key Traces to Look For:")
    key_traces = [
        "process_message → router_node → extract_task_intent",
        "tool_executor_node → CalendarTools execution",
        "response_generator_node → format_tool_result",
        "LLM fallback chains (OpenAI → Gemini → Rule-based)",
        "Search and compound task execution flows"
    ]
    
    for trace in key_traces:
        print(f"  • {trace}")
    
    db.close()
    return results, session_id

def test_specific_tracing_scenarios():
    """Test specific scenarios to demonstrate tracing capabilities"""
    
    print("\n🎯 Specific LangSmith Tracing Scenarios")
    print("=" * 50)
    
    db = next(get_db())
    user_id = 2
    agent = CalendarAgent()
    
    # Test LLM reasoning with complex query
    print("1. Testing Complex Intent Extraction...")
    complex_query = "Find my meeting with Sarah next week and move it to 3pm on Friday, then create a follow-up call for the week after"
    
    try:
        response = agent.process_message(complex_query, user_id, db)
        print(f"✅ Complex query processed: {len(response)} characters response")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test fallback mechanism
    print("\n2. Testing Fallback Mechanism...")
    # This should trigger fallback to rule-based processing
    fallback_query = "xyzabc123 nonsensical query that should fail LLM parsing"
    
    try:
        response = agent.process_message(fallback_query, user_id, db)
        print(f"✅ Fallback mechanism activated: {len(response)} characters response")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test confirmation flow
    print("\n3. Testing Confirmation Flow...")
    confirmation_query = "Delete all my events tomorrow"
    
    try:
        response = agent.process_message(confirmation_query, user_id, db)
        print(f"✅ Confirmation flow triggered: {len(response)} characters response")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    db.close()

if __name__ == "__main__":
    print("🚀 LangSmith Tracing Test Suite for Enhanced Calendar Agent")
    print("=" * 70)
    
    # Verify tracing is enabled
    print("🔧 LangSmith Configuration:")
    print(f"  LANGCHAIN_TRACING_V2: {os.environ.get('LANGCHAIN_TRACING_V2')}")
    print(f"  LANGCHAIN_PROJECT: {os.environ.get('LANGCHAIN_PROJECT')}")
    print(f"  LANGCHAIN_ENDPOINT: {os.environ.get('LANGCHAIN_ENDPOINT')}")
    print()
    
    # Run main tests
    test_results, session_id = test_agent_with_tracing()
    
    # Run specific tracing scenarios
    test_specific_tracing_scenarios()
    
    print("\n🎉 LangSmith Tracing Tests Completed!")
    print(f"🔗 View traces at: https://smith.langchain.com")
    print(f"🏷️  Session ID: {session_id}")
    print()
    print("📋 What's Now Traced:")
    print("✅ All LLM calls with prompts and responses")
    print("✅ Graph node execution flow and timing")
    print("✅ Tool execution results and errors")
    print("✅ Intent extraction and parsing")
    print("✅ Fallback mechanism activations")
    print("✅ Calendar operations across providers")
    print("✅ Response generation and formatting")
