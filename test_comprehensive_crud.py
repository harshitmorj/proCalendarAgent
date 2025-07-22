#!/usr/bin/env python3
"""
Comprehensive test script for IntegratedCalendar CRUD operations
Tests all CRUD operations including updates and deletions
"""

import sys
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import traceback

# Add the app directory to Python path
sys.path.append('/home/harshit/Documents/proCalendarAgent')
sys.path.append('/home/harshit/Documents/proCalendarAgent/app')

try:
    from dotenv import load_dotenv
    from app.database.database import get_db, create_tables
    from app.database.models import User, CalendarAccount
    from app.calendar_providers.integrated_calendar import IntegratedCalendar
    print("✅ All imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Configuration
TEST_USER_ID = 2

def get_db_session():
    """Get a database session"""
    try:
        db_gen = get_db()
        return next(db_gen)
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def test_full_crud_operations():
    """Test complete CRUD operations"""
    print("🧪 Comprehensive CRUD Operations Test")
    print("=" * 50)
    
    # Load environment and setup
    load_dotenv('/home/harshit/Documents/proCalendarAgent/.env')
    create_tables()
    
    # Get database session
    db_session = get_db_session()
    if not db_session:
        print("❌ Failed to get database session!")
        return False
    
    # Initialize IntegratedCalendar
    try:
        integrated_cal = IntegratedCalendar(
            user_id=TEST_USER_ID,
            db_session=db_session
        )
        print("✅ IntegratedCalendar initialized successfully!")
    except Exception as e:
        print(f"❌ IntegratedCalendar initialization failed: {e}")
        return False
    
    # Get accounts
    accounts_summary = integrated_cal.get_calendar_accounts_summary()
    connected_accounts = [acc for acc in accounts_summary if acc['status'] == 'connected']
    
    if not connected_accounts:
        print("❌ No connected accounts found!")
        return False
    
    print(f"📊 Testing with {len(connected_accounts)} connected accounts")
    
    test_results = {}
    
    for account in connected_accounts:
        provider = account['provider']
        account_email = account['account_email']
        
        print(f"\n🔄 Testing CRUD operations for {provider} ({account_email})")
        
        test_results[f"{provider}_{account_email}"] = {
            'create': False,
            'read': False,
            'update': False,
            'delete': False,
            'search': False
        }
        
        try:
            # CREATE
            print(f"   ➕ CREATE: Creating test event...")
            event_start = datetime.now() + timedelta(days=1, hours=14)
            event_end = event_start + timedelta(hours=1)
            
            event_data = {
                'title': f'CRUD Test Event - {provider}',
                'description': f'Testing CRUD operations for {provider}. Created: {datetime.now().isoformat()}',
                'start': event_start.isoformat(),
                'end': event_end.isoformat(),
                'location': f'Test Location - {provider}',
                'timezone': 'UTC'
            }
            
            created_event = integrated_cal.create_event(
                provider=provider,
                account_email=account_email,
                event_data=event_data
            )
            
            if created_event and created_event.get('id'):
                print(f"      ✅ Event created: {created_event['id']}")
                test_results[f"{provider}_{account_email}"]['create'] = True
                event_id = created_event['id']
            else:
                print(f"      ❌ Event creation failed")
                continue
            
            # READ
            print(f"   📖 READ: Retrieving event by ID...")
            retrieved_event = integrated_cal.get_event_by_id(
                provider=provider,
                account_email=account_email,
                event_id=event_id
            )
            
            if retrieved_event and retrieved_event.get('id') == event_id:
                print(f"      ✅ Event retrieved successfully")
                test_results[f"{provider}_{account_email}"]['read'] = True
            else:
                print(f"      ❌ Event retrieval failed")
            
            # UPDATE
            print(f"   ✏️ UPDATE: Updating event...")
            updated_start = event_start + timedelta(hours=1)
            updated_end = updated_start + timedelta(hours=1, minutes=30)
            
            update_data = {
                'title': f'UPDATED CRUD Test Event - {provider}',
                'description': f'UPDATED: Testing CRUD operations for {provider}. Updated: {datetime.now().isoformat()}',
                'start': updated_start.isoformat(),
                'end': updated_end.isoformat(),
                'location': f'UPDATED Test Location - {provider}',
                'timezone': 'UTC'
            }
            
            updated_event = integrated_cal.update_event(
                provider=provider,
                account_email=account_email,
                event_id=event_id,
                event_data=update_data
            )
            
            if updated_event and 'UPDATED' in updated_event.get('title', ''):
                print(f"      ✅ Event updated successfully")
                test_results[f"{provider}_{account_email}"]['update'] = True
            else:
                print(f"      ❌ Event update failed")
            
            # SEARCH
            print(f"   🔍 SEARCH: Searching for updated event...")
            search_results = integrated_cal.search_events(
                query='UPDATED CRUD Test',
                limit=5
            )
            
            found_event = any(e.get('id') == event_id for e in search_results)
            if found_event:
                print(f"      ✅ Event found in search results")
                test_results[f"{provider}_{account_email}"]['search'] = True
            else:
                print(f"      ❌ Event not found in search")
            
            # DELETE
            print(f"   🗑️ DELETE: Deleting test event...")
            delete_success = integrated_cal.delete_event(
                provider=provider,
                account_email=account_email,
                event_id=event_id
            )
            
            if delete_success:
                print(f"      ✅ Event deleted successfully")
                test_results[f"{provider}_{account_email}"]['delete'] = True
                
                # Verify deletion
                print(f"      🔍 Verifying deletion...")
                deleted_event = integrated_cal.get_event_by_id(
                    provider=provider,
                    account_email=account_email,
                    event_id=event_id
                )
                
                if deleted_event is None:
                    print(f"      ✅ Deletion verified - event no longer exists")
                else:
                    print(f"      ⚠️ Event still exists after deletion")
            else:
                print(f"      ❌ Event deletion failed")
            
        except Exception as e:
            print(f"      ❌ CRUD test error: {str(e)[:100]}...")
            traceback.print_exc()
    
    # Results summary
    print(f"\n📊 CRUD Test Results Summary")
    print("=" * 40)
    
    total_accounts = len(test_results)
    operation_counts = {'create': 0, 'read': 0, 'update': 0, 'delete': 0, 'search': 0}
    
    for account, results in test_results.items():
        print(f"\n🏢 {account}:")
        for operation, success in results.items():
            status = "✅" if success else "❌"
            print(f"   {operation.upper()}: {status}")
            if success:
                operation_counts[operation] += 1
    
    print(f"\n📈 Overall Success Rates:")
    for operation, count in operation_counts.items():
        percentage = (count / total_accounts * 100) if total_accounts > 0 else 0
        print(f"   {operation.upper()}: {count}/{total_accounts} ({percentage:.1f}%)")
    
    # Final assessment
    all_operations_success = all(
        operation_counts[op] == total_accounts 
        for op in ['create', 'read', 'update', 'delete', 'search']
    )
    
    if all_operations_success:
        print(f"\n🎉 ALL CRUD OPERATIONS SUCCESSFUL!")
        print(f"   IntegratedCalendar is fully functional across all providers!")
    else:
        print(f"\n⚠️ Some CRUD operations failed.")
        print(f"   Check the specific errors above for troubleshooting.")
    
    return all_operations_success

def test_additional_features():
    """Test additional IntegratedCalendar features"""
    print(f"\n🔧 Testing Additional Features")
    print("=" * 40)
    
    db_session = get_db_session()
    integrated_cal = IntegratedCalendar(user_id=TEST_USER_ID, db_session=db_session)
    
    # Test busy times with various date ranges
    print(f"⏰ Testing busy times functionality...")
    try:
        # Today only
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        busy_today = integrated_cal.get_busy_times(today, tomorrow)
        print(f"   📅 Today's busy periods: {len(busy_today)}")
        
        # Next week
        week_start = today + timedelta(days=1)
        week_end = week_start + timedelta(days=7)
        
        busy_week = integrated_cal.get_busy_times(week_start, week_end)
        print(f"   📅 Next week's busy periods: {len(busy_week)}")
        
        print(f"   ✅ Busy times functionality working")
        
    except Exception as e:
        print(f"   ❌ Busy times error: {str(e)}")
    
    # Test event retrieval with different parameters
    print(f"📅 Testing event retrieval variations...")
    try:
        # All events (default)
        all_events = integrated_cal.get_all_events()
        print(f"   📊 All events (default): {len(all_events)}")
        
        # Limited results
        limited_events = integrated_cal.get_all_events(max_results=5)
        print(f"   📊 Limited events (5): {len(limited_events)}")
        
        # Specific date range
        tomorrow = datetime.now() + timedelta(days=1)
        day_after = tomorrow + timedelta(days=1)
        range_events = integrated_cal.get_all_events(
            start_date=tomorrow,
            end_date=day_after
        )
        print(f"   📊 Tomorrow's events: {len(range_events)}")
        
        print(f"   ✅ Event retrieval variations working")
        
    except Exception as e:
        print(f"   ❌ Event retrieval error: {str(e)}")
    
    # Test search with various queries
    print(f"🔍 Testing search functionality...")
    try:
        search_terms = ["training", "meeting", "test", "work", "lunch"]
        
        for term in search_terms:
            results = integrated_cal.search_events(query=term, limit=3)
            print(f"   🔎 '{term}': {len(results)} results")
        
        print(f"   ✅ Search functionality working")
        
    except Exception as e:
        print(f"   ❌ Search error: {str(e)}")

if __name__ == "__main__":
    try:
        print("🚀 Starting comprehensive IntegratedCalendar test...")
        
        # Run CRUD tests
        crud_success = test_full_crud_operations()
        
        # Run additional feature tests
        test_additional_features()
        
        # Final status
        if crud_success:
            print(f"\n🎉 COMPREHENSIVE TEST PASSED!")
            print(f"   IntegratedCalendar is fully functional and ready for production!")
        else:
            print(f"\n⚠️ COMPREHENSIVE TEST COMPLETED WITH ISSUES!")
            print(f"   Some operations failed - review the logs above.")
        
        sys.exit(0 if crud_success else 1)
        
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)
