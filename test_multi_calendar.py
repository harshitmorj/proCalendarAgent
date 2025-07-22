#!/usr/bin/env python3
"""
Test script to demonstrate the new multi-calendar functionality
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
sys.path.append(os.path.dirname(__file__))

from app.calendar_providers.google_calendar import GoogleCalendarProvider
from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.database.models import Base, User, CalendarAccount
from app.database.database import get_db

def test_google_multi_calendar():
    """Test the new Google Calendar multi-calendar functionality"""
    
    print("=== Testing Google Calendar Multi-Calendar Support ===\n")
    
    # Initialize the Google Calendar provider
    provider = GoogleCalendarProvider()
    
    # Example token file path (you would need a real token file for this to work)
    token_file_path = "user_data/user_2/google_8d7ea959-3eb5-40b4-b13c-928290fb9105.json"
    
    if not os.path.exists(token_file_path):
        print(f"❌ Token file not found: {token_file_path}")
        print("Please ensure you have authenticated with Google Calendar first.")
        return False
    
    try:
        # 1. Test getting all calendars
        print("1. Getting all available calendars...")
        calendars = provider.get_all_calendars(token_file_path)
        
        if calendars:
            print(f"✅ Found {len(calendars)} calendars:")
            for cal in calendars:
                print(f"   - {cal['name']} (ID: {cal['id']}) - Primary: {cal.get('primary', False)}")
        else:
            print("❌ No calendars found")
            return False
        
        print()
        
        # 2. Test getting events from all calendars
        print("2. Getting events from all calendars...")
        all_events = provider.get_events_from_all_calendars(
            token_file_path=token_file_path,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=7),
            max_results=10
        )
        
        print(f"✅ Found {len(all_events)} events across all calendars:")
        for event in all_events[:5]:  # Show first 5 events
            print(f"   - {event['title']} (Calendar: {event.get('calendar_name', 'Unknown')})")
        
        print()
        
        # 3. Test creating an event in a specific calendar
        if calendars:
            # Find a writable calendar (not the read-only holidays calendar)
            writable_calendars = [cal for cal in calendars if cal.get('access_role') in ['owner', 'writer']]
            
            if writable_calendars:
                target_calendar = writable_calendars[0]  # Use the first writable calendar
                print(f"3. Testing event creation in calendar: {target_calendar['name']}")
                
                test_event_data = {
                    'title': 'Multi-Calendar Test Event',
                    'description': 'This is a test event created using the new multi-calendar functionality',
                    'start': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                    'end': (datetime.utcnow() + timedelta(hours=2)).isoformat(),
                    'timezone': 'UTC'
                }
                
                created_event = provider.create_event(
                    token_file_path=token_file_path,
                    event_data=test_event_data,
                    calendar_id=target_calendar['id']
                )
                
                print(f"✅ Created event: {created_event['title']} in calendar {created_event.get('calendar_id')}")
                
                # Clean up - delete the test event
                provider.delete_event(
                    token_file_path=token_file_path,
                    event_id=created_event['id'],
                    calendar_id=target_calendar['id']
                )
                print("✅ Test event cleaned up")
            else:
                print("⚠️  No writable calendars found - skipping event creation test")
        else:
            print("⚠️  No calendars found - skipping event creation test")
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        return False

def test_integrated_calendar():
    """Test the IntegratedCalendar with multi-calendar support"""
    
    print("=== Testing IntegratedCalendar Multi-Calendar Support ===\n")
    
    # Set up database connection
    engine = create_engine("sqlite:///calendar_agent.db")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Find a user with Google calendar accounts
        users = db.query(User).all()
        if not users:
            print("❌ No users found in database")
            return False
            
        user = users[1]  # Use the first user
        print(f"Using user: {user.username} (ID: {user.id})")
        
        # Check if user has any calendar accounts
        calendar_accounts = db.query(CalendarAccount).filter(
            CalendarAccount.user_id == user.id,
            CalendarAccount.is_active == True
        ).all()
        
        if not calendar_accounts:
            print("❌ No active calendar accounts found for this user")
            print("   Please connect some calendar accounts first using the web interface")
            return False
        
        print(f"Found {len(calendar_accounts)} calendar account(s)")
        
        # Initialize IntegratedCalendar
        integrated_cal = IntegratedCalendar(user_id=user.id, db_session=db)
        
        # 1. Test getting all calendars
        print("1. Getting all calendars from IntegratedCalendar...")
        all_calendars = integrated_cal.get_all_calendars()
        
        if all_calendars:
            print(f"✅ Found {len(all_calendars)} calendars:")
            for cal in all_calendars:
                print(f"   - {cal['name']} ({cal['provider']}: {cal['account_email']})")
        else:
            print("❌ No calendars found")
            return False
        
        print()
        
        # 2. Test getting events from all calendars
        print("2. Getting events from all calendars...")
        all_events = integrated_cal.get_all_events(
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=7),
            max_results=10
        )
        
        print(f"✅ Found {len(all_events)} events across all calendars:")
        for event in all_events[:5]:  # Show first 5 events
            calendar_name = event.get('calendar_name', 'Unknown')
            provider = event.get('provider', 'Unknown')
            print(f"   - {event['title']} ({provider}: {calendar_name})")
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        return False
    finally:
        db.close()

def main():
    """Main test function"""
    print("🚀 Testing Multi-Calendar Functionality\n")
    
    # Test individual Google Calendar provider
    google_success = test_google_multi_calendar()
    
    print("\n" + "="*60 + "\n")
    
    # Test IntegratedCalendar
    integrated_success = test_integrated_calendar()
    
    print("\n" + "="*60 + "\n")
    
    # Summary
    print("📊 Test Summary:")
    print(f"   Google Calendar Provider: {'✅ PASSED' if google_success else '❌ FAILED'}")
    print(f"   IntegratedCalendar: {'✅ PASSED' if integrated_success else '❌ FAILED'}")
    
    if google_success and integrated_success:
        print("\n🎉 All tests passed! Multi-calendar functionality is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please check the error messages above.")

if __name__ == "__main__":
    main()
