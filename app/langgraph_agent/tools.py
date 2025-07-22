from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..database.models import User, CalendarAccount
from ..calendar_providers.google_calendar import GoogleCalendarProvider
from ..calendar_providers.microsoft_calendar import MicrosoftCalendarProvider
import os

def get_next_15_events(user_id: int, db: Session) -> str:
    """Get the next 15 events from all connected calendars for a user."""
    
    # Get user's calendar accounts
    calendar_accounts = db.query(CalendarAccount).filter(
        CalendarAccount.user_id == user_id,
        CalendarAccount.is_active == True
    ).all()
    
    if not calendar_accounts:
        return "No calendar accounts connected. Please connect a calendar first."
    
    all_events = []
    
    for account in calendar_accounts:
        try:
            if account.provider == "google":
                provider = GoogleCalendarProvider()
                events = provider.get_calendar_events(account.token_file_path, max_results=15)
            elif account.provider == "microsoft":
                provider = MicrosoftCalendarProvider()
                events = provider.get_calendar_events(account.token_file_path, max_results=15)
            else:
                continue
            
            # Add provider info to events
            for event in events:
                event['provider'] = account.provider
                event['account_email'] = account.account_email
            
            all_events.extend(events)
            
        except Exception as e:
            print(f"Error fetching events from {account.provider}: {str(e)}")
            continue
    
    if not all_events:
        return "No upcoming events found in your connected calendars."
    
    # Sort events by start time and limit to 15
    all_events.sort(key=lambda x: x['start'])
    limited_events = all_events[:15]
    
    # Format events for display
    formatted_events = []
    for event in limited_events:
        event_info = f"**{event['title']}**\n"
        event_info += f"📅 {event['start']} to {event['end']}\n"
        if event['location']:
            event_info += f"📍 {event['location']}\n"
        if event['description']:
            event_info += f"📝 {event['description'][:100]}...\n" if len(event['description']) > 100 else f"📝 {event['description']}\n"
        event_info += f"🔗 {event['provider'].title()} ({event['account_email']})\n"
        formatted_events.append(event_info)
    
    return f"Here are your next 15 upcoming events:\n\n" + "\n---\n".join(formatted_events)

def get_calendar_summary(user_id: int, db: Session) -> str:
    """Get a summary of connected calendar accounts for a user."""
    
    calendar_accounts = db.query(CalendarAccount).filter(
        CalendarAccount.user_id == user_id,
        CalendarAccount.is_active == True
    ).all()
    
    if not calendar_accounts:
        return "No calendar accounts connected."
    
    summary = f"You have {len(calendar_accounts)} connected calendar account(s):\n\n"
    
    for account in calendar_accounts:
        summary += f"• {account.provider.title()}: {account.account_email} (connected on {account.connected_at.strftime('%Y-%m-%d')})\n"
    
    return summary
