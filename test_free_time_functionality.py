#!/usr/bin/env python3
"""
Test Free Time Functionality - Comprehensive test for meeting scheduling features
"""

import sys
import os
from datetime import datetime, timedelta
import json

# Add the app directory to Python path
sys.path.append('/home/harshit/Documents/proCalendarAgent')

from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.database.database import SessionLocal

def test_get_busy_times():
    """Test the get_busy_times functionality"""
    print("🧪 Testing get_busy_times...")
    
    db_session = SessionLocal()
    try:
        integrated_cal = IntegratedCalendar(user_id=1, db_session=db_session)
        
        # Test for next 7 days
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=7)
        
        busy_times = integrated_cal.get_busy_times(start_date, end_date)
        
        print(f"   Found {len(busy_times)} busy periods:")
        for i, busy in enumerate(busy_times[:3], 1):
            print(f"   {i}. {busy.get('title', 'Untitled')} - {busy['start']} to {busy['end']}")
            print(f"      Provider: {busy.get('provider', 'Unknown')}")
        
        if len(busy_times) > 3:
            print(f"   ... and {len(busy_times) - 3} more")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db_session.close()

def test_get_free_times():
    """Test the get_free_times functionality"""
    print("\n🧪 Testing get_free_times...")
    
    db_session = SessionLocal()
    try:
        integrated_cal = IntegratedCalendar(user_id=1, db_session=db_session)
        
        # Test for next 3 days with 1-hour meetings
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=3)
        
        free_slots = integrated_cal.get_free_times(
            start_date=start_date,
            end_date=end_date,
            duration_minutes=60,
            working_hours_start=9,
            working_hours_end=17,
            include_weekends=False,
            buffer_minutes=15
        )
        
        print(f"   Found {len(free_slots)} free time slots:")
        for i, slot in enumerate(free_slots[:5], 1):
            start_time = datetime.fromisoformat(slot['start'])
            print(f"   {i}. {slot['day_of_week']} {start_time.strftime('%m/%d')} at {start_time.strftime('%H:%M')}")
            print(f"      Duration: {slot['duration_minutes']} minutes")
            print(f"      Can fit 60-min meeting: {slot['can_fit_meeting']}")
        
        if len(free_slots) > 5:
            print(f"   ... and {len(free_slots) - 5} more")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db_session.close()

def test_suggest_meeting_times():
    """Test the suggest_meeting_times functionality"""
    print("\n🧪 Testing suggest_meeting_times...")
    
    db_session = SessionLocal()
    try:
        integrated_cal = IntegratedCalendar(user_id=1, db_session=db_session)
        
        participants = ["alice@example.com", "bob@example.com"]
        
        suggestions = integrated_cal.suggest_meeting_times(
            participants=participants,
            duration_minutes=60,
            preferred_times=['morning', 'afternoon'],
            max_suggestions=3
        )
        
        print(f"   Found {len(suggestions)} meeting suggestions:")
        for i, suggestion in enumerate(suggestions, 1):
            start_time = datetime.fromisoformat(suggestion['start_time'])
            print(f"   {i}. {suggestion['day_of_week']} {start_time.strftime('%m/%d')} at {start_time.strftime('%H:%M')}")
            print(f"      Time of day: {suggestion['time_of_day']}")
            print(f"      Preference score: {suggestion['preference_score']:.2f}")
            print(f"      Available duration: {suggestion['available_duration']} minutes")
            if suggestion['notes']:
                print(f"      Notes: {', '.join(suggestion['notes'])}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db_session.close()

def test_check_availability():
    """Test the check_availability functionality"""
    print("\n🧪 Testing check_availability...")
    
    db_session = SessionLocal()
    try:
        integrated_cal = IntegratedCalendar(user_id=1, db_session=db_session)
        
        # Test availability for tomorrow at 2 PM for 1 hour
        tomorrow = datetime.utcnow() + timedelta(days=1)
        test_start = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
        test_end = test_start + timedelta(hours=1)
        
        availability = integrated_cal.check_availability(
            start_time=test_start,
            end_time=test_end,
            participants=["alice@example.com"]
        )
        
        print(f"   Checking: {test_start.strftime('%A %m/%d at %H:%M')} - {test_end.strftime('%H:%M')}")
        print(f"   Available: {availability['available']}")
        print(f"   Duration: {availability['duration_minutes']} minutes")
        print(f"   Conflicts: {availability['conflict_count']}")
        
        if availability['conflicts']:
            print("   Conflict details:")
            for conflict in availability['conflicts']:
                print(f"     • {conflict['title']} ({conflict['start']} - {conflict['end']})")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db_session.close()

def test_find_next_available_time():
    """Test the find_next_available_time functionality"""
    print("\n🧪 Testing find_next_available_time...")
    
    db_session = SessionLocal()
    try:
        integrated_cal = IntegratedCalendar(user_id=1, db_session=db_session)
        
        next_slot = integrated_cal.find_next_available_time(
            duration_minutes=60,
            working_hours_start=9,
            working_hours_end=17,
            include_weekends=False,
            max_days_ahead=7
        )
        
        if next_slot:
            start_time = datetime.fromisoformat(next_slot['start_time'])
            print(f"   Next available: {next_slot['day_of_week']} {start_time.strftime('%m/%d at %H:%M')}")
            print(f"   Duration: {next_slot['duration_minutes']} minutes")
            print(f"   Available slot duration: {next_slot['available_duration']} minutes")
            print(f"   Found in: {next_slot['found_in_days']} days")
        else:
            print("   No available time found in the next 7 days")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db_session.close()

def test_get_availability_summary():
    """Test the get_availability_summary functionality"""
    print("\n🧪 Testing get_availability_summary...")
    
    db_session = SessionLocal()
    try:
        integrated_cal = IntegratedCalendar(user_id=1, db_session=db_session)
        
        summary = integrated_cal.get_availability_summary(
            working_hours_start=9,
            working_hours_end=17
        )
        
        print(f"   📊 Availability Summary:")
        print(f"   Period: {summary['period']['days']} days")
        print(f"   Total working hours: {summary['working_hours']['total_hours']}")
        print(f"   Busy hours: {summary['busy_time']['total_hours']} ({summary['busy_time']['utilization_percent']}%)")
        print(f"   Free hours: {summary['free_time']['total_hours']} ({summary['free_time']['available_percent']}%)")
        print(f"   Events count: {summary['busy_time']['events_count']}")
        print(f"   Free slots: {summary['free_time']['free_slots_count']}")
        print(f"   Longest free slot: {summary['free_time']['longest_slot_minutes']} minutes")
        print(f"   Status: {summary['availability_status']}")
        
        print(f"   Slot distribution:")
        dist = summary['slot_distribution']
        print(f"     • Short (<1h): {dist['short_slots_under_1h']}")
        print(f"     • Medium (1-2h): {dist['medium_slots_1_2h']}")
        print(f"     • Long (>2h): {dist['long_slots_over_2h']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db_session.close()

def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n🧪 Testing edge cases...")
    
    db_session = SessionLocal()
    try:
        integrated_cal = IntegratedCalendar(user_id=1, db_session=db_session)
        
        # Test with very short duration
        free_slots_short = integrated_cal.get_free_times(
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=1),
            duration_minutes=15,
            working_hours_start=9,
            working_hours_end=17
        )
        print(f"   15-minute slots found: {len(free_slots_short)}")
        
        # Test with very long duration
        free_slots_long = integrated_cal.get_free_times(
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=1),
            duration_minutes=240,  # 4 hours
            working_hours_start=9,
            working_hours_end=17
        )
        print(f"   4-hour slots found: {len(free_slots_long)}")
        
        # Test with weekends included
        free_slots_weekend = integrated_cal.get_free_times(
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=7),
            duration_minutes=60,
            include_weekends=True
        )
        print(f"   Slots including weekends: {len(free_slots_weekend)}")
        
        # Test availability check in the past
        past_time = datetime.utcnow() - timedelta(days=1)
        past_availability = integrated_cal.check_availability(
            start_time=past_time,
            end_time=past_time + timedelta(hours=1)
        )
        print(f"   Past time availability check: {past_availability['available']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db_session.close()

def main():
    """Run all free time functionality tests"""
    print("🚀 Testing Free Time Functionality...\n")
    
    tests = [
        ("Get Busy Times", test_get_busy_times),
        ("Get Free Times", test_get_free_times),
        ("Suggest Meeting Times", test_suggest_meeting_times),
        ("Check Availability", test_check_availability),
        ("Find Next Available Time", test_find_next_available_time),
        ("Get Availability Summary", test_get_availability_summary),
        ("Edge Cases", test_edge_cases)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"{'='*50}")
        print(f"🧪 {test_name}")
        print(f"{'='*50}")
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"💥 {test_name} CRASHED: {e}")
    
    print(f"\n{'='*50}")
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All free time functionality tests passed!")
        print("\n💡 Available methods:")
        print("   • get_free_times() - Find available time slots")
        print("   • suggest_meeting_times() - Get optimal meeting suggestions")
        print("   • check_availability() - Check if specific time is free")
        print("   • find_next_available_time() - Find next free slot")
        print("   • get_availability_summary() - Get detailed availability stats")
        print("   • get_busy_times() - Get all busy periods")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()
