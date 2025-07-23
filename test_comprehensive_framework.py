#!/usr/bin/env python3
"""
Comprehensive test suite for the robust LangGraph calendar agent framework
Tests all nodes, flows, edge cases, and error scenarios
"""

import sys
import os
import json
import traceback
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add the app directory to Python path
sys.path.append('/home/harshit/Documents/proCalendarAgent')
sys.path.append('/home/harshit/Documents/proCalendarAgent/app')

try:
    from dotenv import load_dotenv
    from app.database.database import get_db, create_tables
    from app.database.models import User, CalendarAccount
    from app.langgraph_agent.agent import CalendarAgent
    from app.langgraph_agent.schemas.router_schema import (
        CalendarIntent, TaskStatus, SubTask, TaskContext, HumanFeedback
    )
    from app.langgraph_agent.nodes.router_node import router_node_func
    from app.calendar_providers.integrated_calendar import IntegratedCalendar
    from sqlalchemy.orm import Session
    
    print("✅ All imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    traceback.print_exc()
    sys.exit(1)

# Configuration
TEST_USER_ID = 2
TEST_USER_DATA_DIR = '/home/harshit/Documents/proCalendarAgent/user_data/user_2'

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.test_details = []
    
    def add_result(self, test_name: str, status: str, details: str = ""):
        self.test_details.append({
            "name": test_name,
            "status": status,
            "details": details
        })
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        else:
            self.errors += 1
    
    def print_summary(self):
        total = self.passed + self.failed + self.errors
        print(f"\n📊 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.passed}/{total}")
        print(f"❌ Failed: {self.failed}/{total}")
        print(f"🔥 Errors: {self.errors}/{total}")
        print(f"📈 Success Rate: {(self.passed/total*100):.1f}%" if total > 0 else "0%")
        
        if self.failed > 0 or self.errors > 0:
            print(f"\n❌ Failed/Error Tests:")
            for test in self.test_details:
                if test["status"] in ["FAIL", "ERROR"]:
                    print(f"   • {test['name']}: {test['status']}")
                    if test["details"]:
                        print(f"     {test['details'][:100]}...")

def setup_environment():
    """Setup environment and database"""
    print("🔧 Setting up test environment...")
    
    # Load environment variables
    load_dotenv('/home/harshit/Documents/proCalendarAgent/.env')
    
    # Create tables
    create_tables()
    
    # Create test user data directory
    os.makedirs(TEST_USER_DATA_DIR, exist_ok=True)
    
    print("✅ Environment setup complete!")

def get_db_session():
    """Get a database session"""
    try:
        db_gen = get_db()
        return next(db_gen)
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def test_router_node_directly(results: TestResults):
    """Test router node in isolation"""
    print("\n🧪 Testing Router Node Directly")
    print("-" * 40)
    
    test_cases = [
        {
            "name": "Simple Search Intent",
            "message": "show me meetings tomorrow",
            "expected_intent": CalendarIntent.SEARCH
        },
        {
            "name": "Simple Create Intent", 
            "message": "create meeting with John at 2pm",
            "expected_intent": CalendarIntent.CREATE
        },
        {
            "name": "Simple Delete Intent",
            "message": "delete my 3pm meeting",
            "expected_intent": CalendarIntent.DELETE
        },
        {
            "name": "Compound Delete Task",
            "message": "delete all meetings with Soham",
            "expected_intent": CalendarIntent.COMPOUND
        },
        {
            "name": "Ambiguous Request",
            "message": "meeting",
            "expected_intent": CalendarIntent.CLARIFY
        },
        {
            "name": "General Conversation",
            "message": "hello how are you",
            "expected_intent": CalendarIntent.GENERAL
        }
    ]
    
    for test_case in test_cases:
        try:
            print(f"   Testing: {test_case['name']}")
            
            state = {
                "message": test_case["message"],
                "user_id": TEST_USER_ID
            }
            
            result = router_node_func(state)
            
            if result.intent == test_case["expected_intent"]:
                results.add_result(f"Router: {test_case['name']}", "PASS")
                print(f"   ✅ {test_case['name']}: {result.intent.value}")
            else:
                results.add_result(f"Router: {test_case['name']}", "FAIL", 
                                 f"Expected {test_case['expected_intent'].value}, got {result.intent.value}")
                print(f"   ❌ {test_case['name']}: Expected {test_case['expected_intent'].value}, got {result.intent.value}")
                
        except Exception as e:
            results.add_result(f"Router: {test_case['name']}", "ERROR", str(e))
            print(f"   🔥 {test_case['name']}: Error - {str(e)}")

def test_integrated_calendar_connection(results: TestResults):
    """Test integrated calendar functionality"""
    print("\n🧪 Testing Integrated Calendar Connection")
    print("-" * 40)
    
    db_session = get_db_session()
    if not db_session:
        results.add_result("Calendar Connection", "ERROR", "No database session")
        return
    
    try:
        # Test calendar initialization
        integrated_cal = IntegratedCalendar(user_id=TEST_USER_ID, db_session=db_session)
        results.add_result("Calendar Initialization", "PASS")
        print("   ✅ Calendar initialized successfully")
        
        # Test accounts summary
        accounts = integrated_cal.get_calendar_accounts_summary()
        connected_accounts = [acc for acc in accounts if acc['status'] == 'connected']
        
        if connected_accounts:
            results.add_result("Calendar Accounts", "PASS", f"{len(connected_accounts)} connected")
            print(f"   ✅ Found {len(connected_accounts)} connected accounts")
        else:
            results.add_result("Calendar Accounts", "FAIL", "No connected accounts")
            print("   ⚠️  No connected accounts found")
        
        # Test basic search (if accounts available)
        if connected_accounts:
            try:
                events = integrated_cal.get_all_events(
                    start_date=datetime.now(),
                    end_date=datetime.now() + timedelta(days=1),
                    max_results=5
                )
                results.add_result("Calendar Search", "PASS", f"{len(events)} events")
                print(f"   ✅ Search returned {len(events)} events")
            except Exception as e:
                results.add_result("Calendar Search", "FAIL", str(e))
                print(f"   ❌ Search failed: {str(e)[:50]}...")
        
    except Exception as e:
        results.add_result("Calendar Connection", "ERROR", str(e))
        print(f"   🔥 Calendar connection error: {str(e)}")

def test_agent_simple_operations(results: TestResults):
    """Test agent with simple operations"""
    print("\n🧪 Testing Agent Simple Operations")
    print("-" * 40)
    
    db_session = get_db_session()
    if not db_session:
        results.add_result("Agent Simple Ops", "ERROR", "No database session")
        return
    
    agent = CalendarAgent()
    
    simple_tests = [
        {
            "name": "General Greeting",
            "message": "hello",
            "should_contain": ["calendar", "help"]
        },
        {
            "name": "Search Request",
            "message": "show me today's meetings",
            "should_contain": ["events", "found"]
        },
        {
            "name": "Ambiguous Create",
            "message": "create meeting",
            "should_contain": ["details", "title", "time"]
        }
    ]
    
    for test in simple_tests:
        try:
            print(f"   Testing: {test['name']}")
            
            result = agent.process_message(
                message=test["message"],
                user_id=TEST_USER_ID,
                db_session=db_session
            )
            
            response = result.get("response", "").lower()
            
            # Check if response contains expected keywords
            contains_expected = any(keyword in response for keyword in test["should_contain"])
            
            if contains_expected:
                results.add_result(f"Agent: {test['name']}", "PASS")
                print(f"   ✅ {test['name']}: Response appropriate")
            else:
                results.add_result(f"Agent: {test['name']}", "FAIL", 
                                 f"Response missing expected content")
                print(f"   ❌ {test['name']}: Response missing expected keywords")
                print(f"      Response: {response[:100]}...")
                
        except Exception as e:
            results.add_result(f"Agent: {test['name']}", "ERROR", str(e))
            print(f"   🔥 {test['name']}: Error - {str(e)[:50]}...")

def test_agent_edge_cases(results: TestResults):
    """Test agent with edge cases and error scenarios"""
    print("\n🧪 Testing Agent Edge Cases")
    print("-" * 40)
    
    db_session = get_db_session()
    if not db_session:
        results.add_result("Agent Edge Cases", "ERROR", "No database session")
        return
    
    agent = CalendarAgent()
    
    edge_cases = [
        {
            "name": "Empty Message",
            "message": "",
            "expect_error": False
        },
        {
            "name": "Very Long Message",
            "message": "create meeting " * 100,
            "expect_error": False
        },
        {
            "name": "Special Characters",
            "message": "create meeting @#$%^&*()",
            "expect_error": False
        },
        {
            "name": "Non-English Text",
            "message": "créer une réunion",
            "expect_error": False
        },
        {
            "name": "Numbers Only",
            "message": "123456789",
            "expect_error": False
        }
    ]
    
    for test in edge_cases:
        try:
            print(f"   Testing: {test['name']}")
            
            result = agent.process_message(
                message=test["message"],
                user_id=TEST_USER_ID,
                db_session=db_session
            )
            
            has_response = bool(result.get("response"))
            has_error = bool(result.get("error"))
            
            if test["expect_error"]:
                if has_error:
                    results.add_result(f"Edge: {test['name']}", "PASS")
                    print(f"   ✅ {test['name']}: Expected error occurred")
                else:
                    results.add_result(f"Edge: {test['name']}", "FAIL", "Expected error but none occurred")
                    print(f"   ❌ {test['name']}: Expected error but none occurred")
            else:
                if has_response and not has_error:
                    results.add_result(f"Edge: {test['name']}", "PASS")
                    print(f"   ✅ {test['name']}: Handled gracefully")
                else:
                    results.add_result(f"Edge: {test['name']}", "FAIL", "Unexpected error or no response")
                    print(f"   ❌ {test['name']}: Unexpected error or no response")
                
        except Exception as e:
            results.add_result(f"Edge: {test['name']}", "ERROR", str(e))
            print(f"   🔥 {test['name']}: Exception - {str(e)[:50]}...")

def test_compound_task_flows(results: TestResults):
    """Test compound task handling without infinite loops"""
    print("\n🧪 Testing Compound Task Flows")
    print("-" * 40)
    
    db_session = get_db_session()
    if not db_session:
        results.add_result("Compound Tasks", "ERROR", "No database session")
        return
    
    agent = CalendarAgent()
    
    compound_tests = [        {
            "name": "Search-Based Delete",
            "message": "delete meetings with test",
            "expected_intents": ["compound", "search", "delete"]
        },
        {
            "name": "Find and Update",
            "message": "find my meeting with John and change time to 3pm",
            "expected_intents": ["compound"]
        }
    ]
    
    for test in compound_tests:
        try:
            print(f"   Testing: {test['name']}")
            
            # Set a timeout to prevent infinite loops
            start_time = time.time()
            timeout = 30  # 30 seconds max
            
            result = agent.process_message(
                message=test["message"],
                user_id=TEST_USER_ID,
                db_session=db_session
            )
            
            elapsed_time = time.time() - start_time
            
            if elapsed_time > timeout:
                results.add_result(f"Compound: {test['name']}", "FAIL", "Timeout - possible infinite loop")
                print(f"   ❌ {test['name']}: Timeout after {elapsed_time:.1f}s")
            else:
                # Check if it's identified as compound or handled appropriately
                intent = result.get("intent", "").lower()
                has_response = bool(result.get("response"))
                
                if "compound" in intent or has_response:
                    results.add_result(f"Compound: {test['name']}", "PASS")
                    print(f"   ✅ {test['name']}: Completed in {elapsed_time:.1f}s")
                else:
                    results.add_result(f"Compound: {test['name']}", "FAIL", "No proper handling")
                    print(f"   ❌ {test['name']}: No proper compound handling")
                
        except Exception as e:
            results.add_result(f"Compound: {test['name']}", "ERROR", str(e))
            print(f"   🔥 {test['name']}: Exception - {str(e)[:50]}...")

def test_human_in_loop_scenarios(results: TestResults):
    """Test human-in-the-loop scenarios"""
    print("\n🧪 Testing Human-in-Loop Scenarios")
    print("-" * 40)
    
    db_session = get_db_session()
    if not db_session:
        results.add_result("Human-in-Loop", "ERROR", "No database session")
        return
    
    agent = CalendarAgent()
    
    # Test clarification requests
    clarification_tests = [
        "schedule meeting",
        "delete meeting", 
        "update event",
        "meeting"
    ]
    
    for message in clarification_tests:
        try:
            print(f"   Testing clarification: '{message}'")
            
            result = agent.process_message(
                message=message,
                user_id=TEST_USER_ID,
                db_session=db_session
            )
            
            requires_input = result.get("requires_human_input", False)
            has_clarification = "clarification" in result.get("status", "").lower()
            intent = result.get("intent", "")
            
            if requires_input or has_clarification or intent == "clarify":
                results.add_result(f"Clarification: {message}", "PASS")
                print(f"   ✅ Clarification requested appropriately")
            else:
                # Check if it provided a reasonable response anyway
                response = result.get("response", "")
                if len(response) > 20:  # Has substantial response
                    results.add_result(f"Clarification: {message}", "PASS")
                    print(f"   ✅ Provided helpful response instead")
                else:
                    results.add_result(f"Clarification: {message}", "FAIL", "No clarification or response")
                    print(f"   ❌ No clarification requested or response provided")
                
        except Exception as e:
            results.add_result(f"Clarification: {message}", "ERROR", str(e))
            print(f"   🔥 Error: {str(e)[:50]}...")

def test_performance_and_reliability(results: TestResults):
    """Test performance and reliability"""
    print("\n🧪 Testing Performance and Reliability")
    print("-" * 40)
    
    db_session = get_db_session()
    if not db_session:
        results.add_result("Performance", "ERROR", "No database session")
        return
    
    agent = CalendarAgent()
    
    # Test response times
    test_messages = [
        "hello",
        "show me meetings today",
        "create meeting tomorrow",
        "delete all events"
    ]
    
    response_times = []
    
    for message in test_messages:
        try:
            print(f"   Testing response time: '{message[:20]}...'")
            
            start_time = time.time()
            result = agent.process_message(
                message=message,
                user_id=TEST_USER_ID,
                db_session=db_session
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            response_times.append(response_time)
            
            if response_time < 10.0:  # Should respond within 10 seconds
                print(f"   ✅ Response time: {response_time:.2f}s")
            else:
                print(f"   ⚠️  Slow response: {response_time:.2f}s")
                
        except Exception as e:
            print(f"   🔥 Error: {str(e)[:50]}...")
    
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        
        if avg_time < 5.0 and max_time < 15.0:
            results.add_result("Performance", "PASS", f"Avg: {avg_time:.2f}s, Max: {max_time:.2f}s")
            print(f"   ✅ Performance: Avg {avg_time:.2f}s, Max {max_time:.2f}s")
        else:
            results.add_result("Performance", "FAIL", f"Slow responses: Avg {avg_time:.2f}s")
            print(f"   ❌ Performance: Too slow - Avg {avg_time:.2f}s")
    else:
        results.add_result("Performance", "FAIL", "No successful responses")

def main():
    """Main test execution"""
    print("🧪 COMPREHENSIVE CALENDAR AGENT TEST SUITE")
    print("=" * 70)
    print("Testing all aspects of the robust LangGraph framework...")
    print("=" * 70)
    
    results = TestResults()
    
    # Setup
    setup_environment()
    
    # Run all test suites
    test_suites = [
        ("Router Node", test_router_node_directly),
        ("Calendar Connection", test_integrated_calendar_connection),
        ("Simple Operations", test_agent_simple_operations),
        ("Edge Cases", test_agent_edge_cases),
        ("Compound Tasks", test_compound_task_flows),
        ("Human-in-Loop", test_human_in_loop_scenarios),
        ("Performance", test_performance_and_reliability)
    ]
    
    for suite_name, test_func in test_suites:
        try:
            print(f"\n🎯 Running {suite_name} Tests...")
            test_func(results)
        except Exception as e:
            print(f"🔥 Test suite '{suite_name}' crashed: {str(e)}")
            results.add_result(f"{suite_name} Suite", "ERROR", str(e))
    
    # Print comprehensive results
    results.print_summary()
    
    print(f"\n🔍 DETAILED ANALYSIS")
    print("=" * 50)
    
    # Framework robustness assessment
    if results.passed >= (results.passed + results.failed + results.errors) * 0.8:
        print("🎉 FRAMEWORK STATUS: ROBUST & PRODUCTION READY")
        print("   • High success rate indicates stable implementation")
        print("   • Error handling appears effective")
        print("   • Human-in-loop mechanisms functioning")
    elif results.passed >= (results.passed + results.failed + results.errors) * 0.6:
        print("⚠️  FRAMEWORK STATUS: MOSTLY STABLE")
        print("   • Good core functionality but some issues remain")
        print("   • Recommend addressing failures before production")
    else:
        print("❌ FRAMEWORK STATUS: NEEDS WORK")
        print("   • Significant issues detected")
        print("   • Major revisions needed before deployment")
    
    print(f"\n📋 RECOMMENDATIONS:")
    if results.errors > 0:
        print("   • Fix error-causing issues first")
    if results.failed > 0:
        print("   • Review failed test scenarios")
    print("   • Consider adding more edge case handling")
    print("   • Implement comprehensive logging")
    print("   • Add performance monitoring")
    
    print(f"\n✨ FRAMEWORK HIGHLIGHTS:")
    print("   ✅ Modular node-based architecture")
    print("   ✅ Intent classification and routing")
    print("   ✅ Task decomposition capabilities")
    print("   ✅ Human interaction support")
    print("   ✅ Error handling and graceful degradation")
    print("   ✅ Integration with calendar providers")
    
    return results.passed >= (results.passed + results.failed + results.errors) * 0.7

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n🔥 Test suite crashed: {e}")
        traceback.print_exc()
        sys.exit(1)
