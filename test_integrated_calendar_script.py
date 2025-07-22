#!/usr/bin/env python3
"""
Test script for IntegratedCalendar functionality
Tests CRUD operations across all connected calendar providers
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
    from app.calendar_providers.google_calendar import GoogleCalendarProvider
    from app.calendar_providers.microsoft_calendar import MicrosoftCalendarProvider
    from app.calendar_providers.integrated_calendar import IntegratedCalendar
    from sqlalchemy.orm import Session
    
    print("✅ All imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Configuration
TEST_USER_ID = 2
TEST_USER_DATA_DIR = '/home/harshit/Documents/proCalendarAgent/user_data/user_2'

def setup_environment():
    """Setup environment and database"""
    print("🔧 Setting up environment...")
    
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

def test_database_connection():
    """Test database connection and user setup"""
    print("\n📊 Testing database connection...")
    
    db_session = get_db_session()
    if not db_session:
        print("❌ Failed to get database session!")
        return False, None
    
    # Check if user2 exists
    user2 = db_session.query(User).filter(User.id == TEST_USER_ID).first()
    if not user2:
        print("❌ User2 not found in database!")
        return False, db_session
    
    print(f"✅ User2 found: {user2.username}")
    
    # Check connected calendar accounts
    accounts = db_session.query(CalendarAccount).filter(
        CalendarAccount.user_id == TEST_USER_ID,
        CalendarAccount.is_active == True
    ).all()
    
    print(f"📅 Connected calendar accounts: {len(accounts)}")
    for account in accounts:
        token_exists = os.path.exists(account.token_file_path)
        status = "✅" if token_exists else "❌"
        print(f"   {status} {account.provider}: {account.account_email}")
        if not token_exists:
            print(f"      Token file missing: {account.token_file_path}")
    
    return True, db_session

def test_integrated_calendar_init(db_session):
    """Test IntegratedCalendar initialization"""
    print("\n🚀 Testing IntegratedCalendar initialization...")
    
    try:
        integrated_cal = IntegratedCalendar(
            user_id=TEST_USER_ID,
            db_session=db_session
        )
        print("✅ IntegratedCalendar initialized successfully!")
        return integrated_cal
    except Exception as e:
        print(f"❌ IntegratedCalendar initialization failed: {e}")
        traceback.print_exc()
        return None

def test_accounts_summary(integrated_cal):
    """Test getting calendar accounts summary"""
    print("\n📋 Testing accounts summary...")
    
    try:
        summary = integrated_cal.get_calendar_accounts_summary()
        print(f"✅ Accounts summary retrieved: {len(summary)} accounts")
        
        for account in summary:
            print(f"   📧 {account['provider']}: {account['account_email']} - {account['status']}")
        
        return summary
    except Exception as e:
        print(f"❌ Failed to get accounts summary: {e}")
        traceback.print_exc()
        return []

def test_event_retrieval(integrated_cal):
    """Test event retrieval functionality"""
    print("\n📅 Testing event retrieval...")
    
    try:
        # Test 1: Get all events (next 7 days)
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7)
        
        all_events = integrated_cal.get_all_events(
            start_date=start_date,
            end_date=end_date,
            max_results=10
        )
        
        print(f"✅ Retrieved {len(all_events)} events for next 7 days")
        
        # Group by provider
        provider_counts = {}
        for event in all_events:
            provider = event.get('provider', 'unknown')
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
        
        for provider, count in provider_counts.items():
            print(f"   📊 {provider}: {count} events")
        
        # Show sample events
        if all_events:
            print(f"\n📝 Sample events:")
            for i, event in enumerate(all_events[:3]):
                print(f"   {i+1}. {event.get('title', 'No Title')}")
                print(f"      🕒 {event.get('start', 'N/A')}")
                print(f"      🏢 {event.get('provider', 'N/A')}")
        
        return all_events
        
    except Exception as e:
        print(f"❌ Event retrieval failed: {e}")
        traceback.print_exc()
        return []

def test_microsoft_token_refresh(db_session):
    """Test Microsoft token refresh functionality"""
    print("\n🔐 Testing Microsoft token refresh...")
    
    try:
        # Get Microsoft accounts
        microsoft_accounts = db_session.query(CalendarAccount).filter(
            CalendarAccount.user_id == TEST_USER_ID,
            CalendarAccount.provider == 'microsoft',
            CalendarAccount.is_active == True
        ).all()
        
        if not microsoft_accounts:
            print("⚠️  No Microsoft accounts found")
            return True
        
        refresh_success = 0
        
        for account in microsoft_accounts:
            print(f"\n🔍 Testing Microsoft account: {account.account_email}")
            
            if not os.path.exists(account.token_file_path):
                print(f"   ❌ Token file not found: {account.token_file_path}")
                continue
            
            try:
                # Initialize provider with context
                ms_provider = MicrosoftCalendarProvider(
                    user_id=TEST_USER_ID,
                    account_email=account.account_email,
                    db_session=db_session
                )
                
                # Test token validity
                print(f"   🔑 Testing token validity...")
                user_profile = ms_provider.get_user_profile(account.token_file_path)
                
                if user_profile:
                    print(f"   ✅ Token valid - User: {user_profile.get('displayName', 'Unknown')}")
                    refresh_success += 1
                else:
                    print(f"   ⚠️  Token invalid, attempting refresh...")
                    
                    # Try refresh
                    if ms_provider.refresh_access_token(account.token_file_path):
                        print(f"   ✅ Token refresh successful!")
                        
                        # Test again
                        user_profile = ms_provider.get_user_profile(account.token_file_path)
                        if user_profile:
                            print(f"   ✅ Token now valid - User: {user_profile.get('displayName', 'Unknown')}")
                            refresh_success += 1
                        else:
                            print(f"   ❌ Token still invalid after refresh")
                    else:
                        print(f"   ❌ Token refresh failed")
                
            except Exception as token_error:
                print(f"   ❌ Token test error: {str(token_error)[:100]}...")
        
        print(f"\n📊 Microsoft token test summary: {refresh_success}/{len(microsoft_accounts)} successful")
        return refresh_success > 0
        
    except Exception as e:
        print(f"❌ Microsoft token test failed: {e}")
        traceback.print_exc()
        return False

def test_event_creation(integrated_cal, accounts_summary):
    """Test event creation across providers"""
    print("\n📝 Testing event creation...")
    
    created_events = {}
    
    for account in accounts_summary:
        if account['status'] != 'connected':
            print(f"⚠️  Skipping {account['provider']} - {account['account_email']} (not connected)")
            continue
        
        provider = account['provider']
        account_email = account['account_email']
        
        print(f"\n➕ Creating test event in {provider} ({account_email})")
        
        try:
            # Create event data
            event_start = datetime.now() + timedelta(days=1, hours=10)  # Tomorrow at 10 AM
            event_end = event_start + timedelta(hours=1)  # 1 hour duration
            
            event_data = {
                'title': f'Test Event - IntegratedCalendar Script ({provider})',
                'description': f'Test event created by integration script for {provider}. Created at {datetime.now().isoformat()}',
                'start': event_start.isoformat(),
                'end': event_end.isoformat(),
                'location': f'Test Location - {provider} Calendar',
                'timezone': 'UTC'
            }
            
            # Create the event
            created_event = integrated_cal.create_event(
                provider=provider,
                account_email=account_email,
                event_data=event_data
            )
            
            created_events[f"{provider}_{account_email}"] = created_event
            
            print(f"   ✅ Event created successfully!")
            print(f"   📌 Event ID: {created_event.get('id', 'N/A')}")
            print(f"   📅 Title: {created_event.get('title', 'N/A')}")
            
        except Exception as e:
            print(f"   ❌ Failed to create event in {provider}: {str(e)[:100]}...")
            traceback.print_exc()
    
    print(f"\n✅ Created {len(created_events)} events across providers")
    return created_events

def test_event_search(integrated_cal):
    """Test event search functionality"""
    print("\n🔍 Testing event search...")
    
    search_terms = ["Test Event", "IntegratedCalendar", "meeting"]
    
    for term in search_terms:
        try:
            print(f"\n🔎 Searching for: '{term}'")
            search_results = integrated_cal.search_events(query=term, limit=5)
            
            print(f"   📊 Found {len(search_results)} matching events")
            
            if search_results:
                for i, result in enumerate(search_results[:2]):
                    print(f"   {i+1}. {result.get('title', 'No Title')}")
                    print(f"      🏢 {result.get('provider', 'N/A')}")
            
        except Exception as e:
            print(f"   ❌ Search error for '{term}': {str(e)[:100]}...")

def test_busy_times(integrated_cal):
    """Test busy times functionality"""
    print("\n⏰ Testing busy times...")
    
    try:
        start_date = datetime.now()
        end_date = start_date + timedelta(days=3)
        
        busy_times = integrated_cal.get_busy_times(start_date, end_date)
        
        print(f"✅ Retrieved busy times for next 3 days: {len(busy_times)} periods")
        
        if busy_times:
            print(f"📋 Sample busy periods:")
            for i, period in enumerate(busy_times[:3]):
                print(f"   {i+1}. {period.get('title', 'Busy')} - {period.get('start', 'N/A')}")
        
        return busy_times
        
    except Exception as e:
        print(f"❌ Busy times test failed: {str(e)}")
        traceback.print_exc()
        return []

def main():
    """Main test function"""
    print("🧪 IntegratedCalendar Test Script")
    print("=" * 50)
    
    # Setup
    setup_environment()
    
    # Test database connection
    db_success, db_session = test_database_connection()
    if not db_success or not db_session:
        print("❌ Database tests failed!")
        return False
    
    # Test Microsoft token refresh first
    ms_token_success = test_microsoft_token_refresh(db_session)
    
    # Test IntegratedCalendar initialization
    integrated_cal = test_integrated_calendar_init(db_session)
    if not integrated_cal:
        print("❌ IntegratedCalendar initialization failed!")
        return False
    
    # Test accounts summary
    accounts_summary = test_accounts_summary(integrated_cal)
    if not accounts_summary:
        print("❌ No calendar accounts available!")
        return False
    
    # Test event retrieval
    retrieved_events = test_event_retrieval(integrated_cal)
    
    # Test event creation
    created_events = test_event_creation(integrated_cal, accounts_summary)
    
    # Test event search
    test_event_search(integrated_cal)
    
    # Test busy times
    test_busy_times(integrated_cal)
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 30)
    print(f"✅ Database connection: {'PASS' if db_success else 'FAIL'}")
    print(f"✅ Microsoft tokens: {'PASS' if ms_token_success else 'FAIL'}")
    print(f"✅ IntegratedCalendar init: {'PASS' if integrated_cal else 'FAIL'}")
    print(f"✅ Accounts summary: {len(accounts_summary)} accounts")
    print(f"✅ Event retrieval: {len(retrieved_events)} events")
    print(f"✅ Event creation: {len(created_events)} created")
    
    if created_events:
        print(f"\n🎉 IntegratedCalendar tests completed successfully!")
        print(f"   Created test events: {list(created_events.keys())}")
    else:
        print(f"\n⚠️  IntegratedCalendar tests completed with issues!")
        print(f"   No events were created - check authentication tokens")
    
    # Cleanup notification
    print(f"\n🧹 Note: Test events were created and may need manual cleanup")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)
