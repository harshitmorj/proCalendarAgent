#!/usr/bin/env python3
"""
Quick timezone test
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone
from app.langgraph_agent.nodes.free_time_node import free_time_node
from app.database.database import get_db

def test_timezone_fix():
    """Test if timezone fix resolves the issue"""
    
    print("🔧 Testing timezone fix")
    
    db_session = next(get_db())
    
    test_state = {
        "message": "When am I free tomorrow?",
        "user_id": 2,
        "db_session": db_session,
        "action": "find_free_time"
    }
    
    try:
        result = free_time_node(test_state)
        
        if "error" in result:
            print(f"❌ Still has error: {result['error']}")
        else:
            print(f"✅ Success! Response: {result.get('response', 'No response')[:100]}...")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
    
    db_session.close()

if __name__ == "__main__":
    test_timezone_fix()
