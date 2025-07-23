"""
Free Time Node - Handles free time and availability queries
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
from app.calendar_providers.integrated_calendar import IntegratedCalendar
import re

try:
    from langsmith import traceable
except ImportError:
    def traceable(name: str):
        def decorator(func):
            return func
        return decorator

@traceable(name="free_time_node")
def free_time_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle free time and availability queries
    """
    user_id = state.get("user_id")
    db_session = state.get("db_session")
    message = state.get("message", "")
    action = state.get("action", "")
    
    if not user_id:
        return {
            **state,
            "response": "Error: User ID is required for free time operations",
            "error": "Missing user_id"
        }
    
    # Extract parameters from the message
    params = extract_free_time_parameters(message, action)
    
    try:
        # Initialize integrated calendar
        integrated_cal = IntegratedCalendar(user_id=user_id, db_session=db_session)
        
        # Determine which free time operation to perform
        operation = params.get("operation", "find_free_time")
        
        if operation == "check_availability":
            return handle_availability_check(integrated_cal, params, state)
        elif operation == "suggest_meeting_times":
            return handle_meeting_suggestions(integrated_cal, params, state)
        elif operation == "next_available":
            return handle_next_available(integrated_cal, params, state)
        elif operation == "availability_summary":
            return handle_availability_summary(integrated_cal, params, state)
        else:
            return handle_find_free_time(integrated_cal, params, state)
    
    except Exception as e:
        return {
            **state,
            "response": f"Error processing free time request: {str(e)}",
            "error": str(e)
        }

def extract_free_time_parameters(message: str, action: str) -> Dict[str, Any]:
    """
    Extract parameters for free time operations from the message
    """
    params = {}
    message_lower = message.lower()
    
    # Determine operation type
    if any(phrase in message_lower for phrase in ["check availability", "available at", "free at", "busy at"]):
        params["operation"] = "check_availability"
    elif any(phrase in message_lower for phrase in ["suggest meeting", "best time", "optimal time", "when to meet"]):
        params["operation"] = "suggest_meeting_times"
    elif any(phrase in message_lower for phrase in ["next available", "next free", "earliest available"]):
        params["operation"] = "next_available"
    elif any(phrase in message_lower for phrase in ["availability summary", "how busy", "schedule overview"]):
        params["operation"] = "availability_summary"
    else:
        params["operation"] = "find_free_time"
    
    # Extract duration
    duration_match = re.search(r'(\d+)\s*(hour|hr|minute|min)', message_lower)
    if duration_match:
        duration_value = int(duration_match.group(1))
        duration_unit = duration_match.group(2)
        if 'hour' in duration_unit or 'hr' in duration_unit:
            params["duration_minutes"] = duration_value * 60
        else:
            params["duration_minutes"] = duration_value
    else:
        params["duration_minutes"] = 60  # Default 1 hour
    
    # Extract time preferences
    if "morning" in message_lower:
        params["preferred_times"] = ["morning"]
    elif "afternoon" in message_lower:
        params["preferred_times"] = ["afternoon"]
    elif "evening" in message_lower:
        params["preferred_times"] = ["evening"]
    
    # Extract date range
    params.update(extract_date_range(message_lower))
    
    # Extract working hours preferences
    if "early" in message_lower or "8 am" in message_lower or "8am" in message_lower:
        params["working_hours_start"] = 8
    elif "late" in message_lower or "6 pm" in message_lower or "6pm" in message_lower:
        params["working_hours_end"] = 18
    
    # Include weekends?
    if "weekend" in message_lower or "saturday" in message_lower or "sunday" in message_lower:
        params["include_weekends"] = True
    else:
        params["include_weekends"] = False
    
    # Extract participants for meeting suggestions
    participants = extract_participants(message)
    if participants:
        params["participants"] = participants
    
    return params

def extract_date_range(message_lower: str) -> Dict[str, Any]:
    """Extract date range from message"""
    params = {}
    
    # Use timezone-aware UTC datetime
    now = datetime.now(timezone.utc)
    
    if "today" in message_lower:
        params["start_date"] = now.replace(hour=0, minute=0, second=0, microsecond=0)
        params["end_date"] = params["start_date"] + timedelta(days=1)
    elif "tomorrow" in message_lower:
        tomorrow = now + timedelta(days=1)
        params["start_date"] = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        params["end_date"] = params["start_date"] + timedelta(days=1)
    elif "this week" in message_lower:
        params["start_date"] = now
        params["end_date"] = now + timedelta(days=7)
    elif "next week" in message_lower:
        params["start_date"] = now + timedelta(days=7)
        params["end_date"] = params["start_date"] + timedelta(days=7)
    else:
        # Default to next 3 days
        params["start_date"] = now
        params["end_date"] = now + timedelta(days=3)
    
    return params

def extract_participants(message: str) -> List[str]:
    """Extract email addresses or participant names from message"""
    # Simple email extraction
    import re
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message)
    
    # Also look for "with X" patterns
    with_pattern = re.search(r'with\s+([A-Za-z\s,]+?)(?:\s|$|\.)', message, re.IGNORECASE)
    if with_pattern and not emails:
        names = with_pattern.group(1).split(',')
        return [name.strip() for name in names if name.strip()]
    
    return emails

def handle_find_free_time(integrated_cal: IntegratedCalendar, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle general free time requests"""
    
    # Get dates with defaults (timezone-aware)
    start_date = params.get("start_date")
    if start_date is None:
        start_date = datetime.now(timezone.utc)
    
    end_date = params.get("end_date")
    if end_date is None:
        end_date = start_date + timedelta(days=3)
    
    free_slots = integrated_cal.get_free_times(
        start_date=start_date,
        end_date=end_date,
        duration_minutes=params.get("duration_minutes", 60),
        working_hours_start=params.get("working_hours_start", 9),
        working_hours_end=params.get("working_hours_end", 17),
        include_weekends=params.get("include_weekends", False),
        buffer_minutes=15
    )
    
    if not free_slots:
        response = "No free time slots found in the specified period."
        if not params.get("include_weekends", False):
            response += " Try including weekends or expanding the date range."
    else:
        duration = params.get("duration_minutes", 60)
        response = f"🗓️ **Found {len(free_slots)} free time slots for {duration}-minute meetings:**\n\n"
        
        for i, slot in enumerate(free_slots[:10], 1):
            start_time = datetime.fromisoformat(slot['start'])
            end_time = datetime.fromisoformat(slot['end'])
            
            response += f"{i}. **{slot['day_of_week']}** {start_time.strftime('%m/%d')} at {start_time.strftime('%H:%M')}\n"
            response += f"   ⏱️ Available: {slot['duration_minutes']} minutes\n"
            response += f"   🎯 Can fit {duration}-min meeting: ✅\n\n"
        
        if len(free_slots) > 10:
            response += f"... and {len(free_slots) - 10} more slots available\n"
    
    return {
        **state,
        "response": response,
        "free_slots": free_slots
    }

def handle_availability_check(integrated_cal: IntegratedCalendar, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle availability check for specific time"""
    
    # For now, check the next occurrence of the requested time
    start_date = params.get("start_date", datetime.now(timezone.utc))
    duration = params.get("duration_minutes", 60)
    
    # Check availability at the start of the period
    test_start = start_date.replace(hour=14, minute=0, second=0, microsecond=0)  # Default 2 PM
    test_end = test_start + timedelta(minutes=duration)
    
    availability = integrated_cal.check_availability(
        start_time=test_start,
        end_time=test_end,
        participants=params.get("participants", [])
    )
    
    if availability['available']:
        response = f"✅ **Available!** You're free on {test_start.strftime('%A %m/%d at %H:%M')} for {duration} minutes.\n\n"
        response += f"📅 **Time slot:** {test_start.strftime('%H:%M')} - {test_end.strftime('%H:%M')}\n"
        response += f"⏱️ **Duration:** {duration} minutes\n"
    else:
        response = f"❌ **Not available** on {test_start.strftime('%A %m/%d at %H:%M')} for {duration} minutes.\n\n"
        response += f"🚫 **Conflicts found:** {availability['conflict_count']}\n\n"
        
        for i, conflict in enumerate(availability['conflicts'], 1):
            conflict_start = datetime.fromisoformat(conflict['start'])
            conflict_end = datetime.fromisoformat(conflict['end'])
            response += f"{i}. **{conflict['title']}**\n"
            response += f"   ⏰ {conflict_start.strftime('%H:%M')} - {conflict_end.strftime('%H:%M')}\n"
            response += f"   📧 {conflict.get('account_email', 'Unknown')}\n\n"
    
    return {
        **state,
        "response": response,
        "availability": availability
    }

def handle_meeting_suggestions(integrated_cal: IntegratedCalendar, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle meeting time suggestions"""
    
    participants = params.get("participants", [])
    
    # Get dates with defaults (timezone-aware)
    start_date = params.get("start_date")
    if start_date is None:
        start_date = datetime.now(timezone.utc)
    
    end_date = params.get("end_date")
    if end_date is None:
        end_date = start_date + timedelta(days=7)
    
    suggestions = integrated_cal.suggest_meeting_times(
        participants=participants,
        duration_minutes=params.get("duration_minutes", 60),
        start_date=start_date,
        end_date=end_date,
        preferred_times=params.get("preferred_times"),
        working_hours_start=params.get("working_hours_start", 9),
        working_hours_end=params.get("working_hours_end", 17),
        include_weekends=params.get("include_weekends", False),
        max_suggestions=5
    )
    
    if not suggestions:
        response = "No suitable meeting times found in the specified period."
    else:
        duration = params.get("duration_minutes", 60)
        response = f"🤝 **Best {len(suggestions)} meeting times for {duration}-minute meeting:**\n\n"
        
        if participants:
            response += f"👥 **Participants:** {', '.join(participants)}\n\n"
        
        for i, suggestion in enumerate(suggestions, 1):
            start_time = datetime.fromisoformat(suggestion['start_time'])
            
            response += f"**{i}. {suggestion['day_of_week']}** {start_time.strftime('%m/%d')} at {start_time.strftime('%H:%M')}\n"
            response += f"   🌅 Time of day: {suggestion['time_of_day'].title()}\n"
            response += f"   ⭐ Preference score: {suggestion['preference_score']:.2f}/1.0\n"
            response += f"   ⏱️ Available duration: {suggestion['available_duration']} minutes\n"
            
            if suggestion['notes']:
                response += f"   💡 Notes: {', '.join(suggestion['notes'])}\n"
            
            response += "\n"
    
    return {
        **state,
        "response": response,
        "meeting_suggestions": suggestions
    }

def handle_next_available(integrated_cal: IntegratedCalendar, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle next available time requests"""
    
    # Get start date with default (timezone-aware)
    start_date = params.get("start_date")
    if start_date is None:
        start_date = datetime.now(timezone.utc)
    
    next_slot = integrated_cal.find_next_available_time(
        duration_minutes=params.get("duration_minutes", 60),
        start_from=start_date,
        working_hours_start=params.get("working_hours_start", 9),
        working_hours_end=params.get("working_hours_end", 17),
        include_weekends=params.get("include_weekends", False),
        max_days_ahead=14
    )
    
    if not next_slot:
        response = "⚠️ No available time slots found in the next 14 days."
        response += "\n\nTry:\n• Including weekends\n• Shorter meeting duration\n• Extended search period"
    else:
        start_time = datetime.fromisoformat(next_slot['start_time'])
        duration = params.get("duration_minutes", 60)
        
        response = f"⏰ **Next available time for {duration}-minute meeting:**\n\n"
        response += f"📅 **{next_slot['day_of_week']}** {start_time.strftime('%B %d, %Y')}\n"
        response += f"⏰ **Time:** {start_time.strftime('%H:%M')} - {datetime.fromisoformat(next_slot['end_time']).strftime('%H:%M')}\n"
        response += f"🗓️ **Available in:** {next_slot['found_in_days']} days\n"
        response += f"⏱️ **Slot duration:** {next_slot['available_duration']} minutes\n"
        
        if next_slot['found_in_days'] == 0:
            response += "\n✨ **Available today!**"
        elif next_slot['found_in_days'] == 1:
            response += "\n📋 **Available tomorrow**"
    
    return {
        **state,
        "response": response,
        "next_available": next_slot
    }

def handle_availability_summary(integrated_cal: IntegratedCalendar, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle availability summary requests"""
    
    # Get dates with defaults (timezone-aware)
    start_date = params.get("start_date")
    if start_date is None:
        start_date = datetime.now(timezone.utc)
    
    end_date = params.get("end_date")
    if end_date is None:
        end_date = start_date + timedelta(days=7)
    
    summary = integrated_cal.get_availability_summary(
        start_date=start_date,
        end_date=end_date,
        working_hours_start=params.get("working_hours_start", 9),
        working_hours_end=params.get("working_hours_end", 17)
    )
    
    # Format the summary
    status_emojis = {
        'very_available': '🟢',
        'moderately_available': '🟡',
        'limited_availability': '🟠',
        'very_busy': '🔴'
    }
    
    status_emoji = status_emojis.get(summary['availability_status'], '📊')
    
    response = f"📊 **Availability Summary** {status_emoji}\n\n"
    response += f"📅 **Period:** {summary['period']['days']} days\n"
    response += f"⏰ **Working hours:** {summary['working_hours']['daily_start']}:00 - {summary['working_hours']['daily_end']}:00\n\n"
    
    response += f"**📈 Time Breakdown:**\n"
    response += f"• **Total working hours:** {summary['working_hours']['total_hours']}h\n"
    response += f"• **Busy time:** {summary['busy_time']['total_hours']}h ({summary['busy_time']['utilization_percent']}%)\n"
    response += f"• **Free time:** {summary['free_time']['total_hours']}h ({summary['free_time']['available_percent']}%)\n\n"
    
    response += f"**📋 Activity:**\n"
    response += f"• **Scheduled events:** {summary['busy_time']['events_count']}\n"
    response += f"• **Free slots:** {summary['free_time']['free_slots_count']}\n"
    response += f"• **Longest free slot:** {summary['free_time']['longest_slot_minutes']} minutes\n\n"
    
    dist = summary['slot_distribution']
    response += f"**🎯 Free Slot Distribution:**\n"
    response += f"• **Short (<1h):** {dist['short_slots_under_1h']} slots\n"
    response += f"• **Medium (1-2h):** {dist['medium_slots_1_2h']} slots\n"
    response += f"• **Long (>2h):** {dist['long_slots_over_2h']} slots\n\n"
    
    # Add recommendations
    if summary['availability_status'] == 'very_busy':
        response += "💡 **Recommendation:** Consider shorter meetings or weekend availability for urgent items."
    elif summary['availability_status'] == 'very_available':
        response += "💡 **Great news:** Plenty of availability for scheduling new meetings!"
    
    return {
        **state,
        "response": response,
        "availability_summary": summary
    }
