"""
Enhanced calendar tools with full CRUD capabilities and structured outputs
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from langsmith import traceable
from .schemas import (
    ToolResult, EventData, SearchQuery, EventIdentifier, 
    CreateEventRequest, UpdateEventRequest, DeleteEventRequest,
    CalendarProvider, DateTimeRange
)
from ..calendar_providers.integrated_calendar import IntegratedCalendar
from ..database.models import User, CalendarAccount
import json
import re
from dateutil import parser as date_parser

class CalendarTools:
    """Enhanced calendar tools with full CRUD capabilities"""
    
    def __init__(self, user_id: int, db_session: Session):
        self.user_id = user_id
        self.db = db_session
        self.integrated_calendar = IntegratedCalendar(user_id, db_session)
    
    def get_events(self, 
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   limit: int = 50) -> ToolResult:
        """Get events from all calendars with optional date filtering"""
        try:
            if start_date is None:
                start_date = datetime.utcnow()
            if end_date is None:
                end_date = start_date + timedelta(days=30)
            
            events = self.integrated_calendar.get_all_events(
                start_date=start_date,
                end_date=end_date,
                max_results=limit
            )
            
            return ToolResult(
                success=True,
                data=events,
                metadata={
                    "count": len(events),
                    "date_range": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    }
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to get events: {str(e)}"
            )
    
    def search_events(self, query: SearchQuery) -> ToolResult:
        """Search for events using structured query"""
        try:
            # Build search parameters
            search_text = query.text or ""
            start_date = None
            end_date = None
            
            if query.date_range:
                start_date = query.date_range.start
                end_date = query.date_range.end
            elif query.filters:
                start_date = query.filters.start_date
                end_date = query.filters.end_date
            
            # Perform search
            events = self.integrated_calendar.search_events(
                query=search_text,
                start_date=start_date,
                end_date=end_date,
                limit=query.limit
            )
            
            # Apply additional filters if specified
            if query.filters:
                events = self._apply_filters(events, query.filters)
            
            return ToolResult(
                success=True,
                data=events,
                metadata={
                    "count": len(events),
                    "query": query.text,
                    "filters_applied": query.filters is not None
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}"
            )
    
    def create_event(self, request: CreateEventRequest) -> ToolResult:
        """Create a new calendar event"""
        try:
            # Determine target account
            provider, account_email = self._resolve_account(
                request.provider, 
                request.account_email
            )
            
            if not provider or not account_email:
                return ToolResult(
                    success=False,
                    error="Could not determine target calendar account"
                )
            
            # Convert EventData to provider format
            event_data = {
                'title': request.event_data.title,
                'description': request.event_data.description,
                'location': request.event_data.location,
                'start_datetime': request.event_data.start_datetime,
                'end_datetime': request.event_data.end_datetime,
                'attendees': request.event_data.attendees or [],
                'reminders': request.event_data.reminders or {}
            }
            
            # Create event
            created_event = self.integrated_calendar.create_event(
                provider=provider,
                account_email=account_email,
                event_data=event_data
            )
            
            return ToolResult(
                success=True,
                data=created_event,
                metadata={
                    "provider": provider,
                    "account": account_email,
                    "event_id": created_event.get('id')
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to create event: {str(e)}"
            )
    
    def update_event(self, request: UpdateEventRequest) -> ToolResult:
        """Update an existing calendar event"""
        try:
            # Find the event first
            event_info = self._find_event(request.event_identifier)
            if not event_info:
                return ToolResult(
                    success=False,
                    error="Could not find the specified event"
                )
            
            event, provider, account_email = event_info
            
            # Update event
            updated_event = self.integrated_calendar.update_event(
                provider=provider,
                account_email=account_email,
                event_id=event['id'],
                event_data=request.updates
            )
            
            return ToolResult(
                success=True,
                data=updated_event,
                metadata={
                    "provider": provider,
                    "account": account_email,
                    "event_id": event['id'],
                    "updated_fields": list(request.updates.keys())
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to update event: {str(e)}"
            )
    
    def delete_event(self, request: DeleteEventRequest) -> ToolResult:
        """Delete a calendar event"""
        try:
            # Find the event first
            event_info = self._find_event(request.event_identifier)
            if not event_info:
                return ToolResult(
                    success=False,
                    error="Could not find the specified event"
                )
            
            event, provider, account_email = event_info
            
            # Require confirmation for deletion
            if not request.confirmation:
                return ToolResult(
                    success=False,
                    error="Deletion requires user confirmation",
                    metadata={
                        "requires_confirmation": True,
                        "event_title": event.get('title'),
                        "event_start": event.get('start'),
                        "provider": provider,
                        "account": account_email
                    }
                )
            
            # Delete event
            success = self.integrated_calendar.delete_event(
                provider=provider,
                account_email=account_email,
                event_id=event['id']
            )
            
            return ToolResult(
                success=success,
                data={"deleted": success},
                metadata={
                    "provider": provider,
                    "account": account_email,
                    "event_id": event['id'],
                    "event_title": event.get('title')
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to delete event: {str(e)}"
            )
    
    def get_busy_times(self, start_date: datetime, end_date: datetime) -> ToolResult:
        """Get busy times for scheduling purposes"""
        try:
            busy_times = self.integrated_calendar.get_busy_times(start_date, end_date)
            
            return ToolResult(
                success=True,
                data=busy_times,
                metadata={
                    "date_range": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    },
                    "busy_slots_count": len(busy_times)
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get busy times: {str(e)}"
            )
    
    def get_calendar_summary(self) -> ToolResult:
        """Get summary of connected calendar accounts"""
        try:
            summary = self.integrated_calendar.get_calendar_accounts_summary()
            
            return ToolResult(
                success=True,
                data=summary,
                metadata={
                    "accounts_count": len(summary),
                    "providers": list(set(acc['provider'] for acc in summary))
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get calendar summary: {str(e)}"
            )
    
    def _resolve_account(self, 
                        preferred_provider: Optional[CalendarProvider],
                        preferred_account: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """Resolve which account to use for operations"""
        accounts = self.db.query(CalendarAccount).filter(
            CalendarAccount.user_id == self.user_id,
            CalendarAccount.is_active == True
        ).all()
        
        if not accounts:
            return None, None
        
        # If specific account requested
        if preferred_account:
            for account in accounts:
                if account.account_email == preferred_account:
                    return account.provider, account.account_email
        
        # If specific provider requested
        if preferred_provider and preferred_provider != CalendarProvider.ANY:
            provider_accounts = [acc for acc in accounts if acc.provider == preferred_provider.value]
            if provider_accounts:
                return provider_accounts[0].provider, provider_accounts[0].account_email
        
        # Default to first available account
        return accounts[0].provider, accounts[0].account_email
    
    def _find_event(self, identifier: EventIdentifier) -> Optional[tuple[Dict[str, Any], str, str]]:
        """Find an event based on identifier"""
        # If we have a direct event ID
        if identifier.event_id and identifier.provider and identifier.account_email:
            event = self.integrated_calendar.get_event_by_id(
                provider=identifier.provider.value,
                account_email=identifier.account_email,
                event_id=identifier.event_id
            )
            if event:
                return event, identifier.provider.value, identifier.account_email
        
        # If we need to search
        if identifier.search_criteria:
            search_result = self.search_events(identifier.search_criteria)
            if search_result.success and search_result.data:
                events = search_result.data
                if len(events) == 1:
                    event = events[0]
                    return event, event['provider'], event['account_email']
                elif len(events) > 1:
                    # Multiple events found - this needs user clarification
                    raise Exception(f"Multiple events found ({len(events)}). Please be more specific.")
        
        return None
    
    def _apply_filters(self, events: List[Dict[str, Any]], filters) -> List[Dict[str, Any]]:
        """Apply additional filters to events"""
        filtered_events = events
        
        if filters.title_contains:
            filtered_events = [
                e for e in filtered_events 
                if filters.title_contains.lower() in e.get('title', '').lower()
            ]
        
        if filters.description_contains:
            filtered_events = [
                e for e in filtered_events 
                if filters.description_contains.lower() in e.get('description', '').lower()
            ]
        
        if filters.location_contains:
            filtered_events = [
                e for e in filtered_events 
                if filters.location_contains.lower() in e.get('location', '').lower()
            ]
        
        if filters.attendee_email:
            filtered_events = [
                e for e in filtered_events 
                if any(filters.attendee_email.lower() in attendee.lower() 
                      for attendee in e.get('attendees', []))
            ]
        
        if filters.provider and filters.provider != CalendarProvider.ANY:
            filtered_events = [
                e for e in filtered_events 
                if e.get('provider') == filters.provider.value
            ]
        
        return filtered_events


# Legacy function wrappers for backward compatibility
def get_next_15_events(user_id: int, db: Session) -> str:
    """Get the next 15 events - legacy wrapper"""
    tools = CalendarTools(user_id, db)
    result = tools.get_events(limit=15)
    
    if not result.success:
        return f"Error: {result.error}"
    
    events = result.data
    if not events:
        return "No upcoming events found in your connected calendars."
    
    # Format events for display
    formatted_events = []
    for event in events:
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
    """Get calendar summary - legacy wrapper"""
    tools = CalendarTools(user_id, db)
    result = tools.get_calendar_summary()
    
    if not result.success:
        return f"Error: {result.error}"
    
    accounts = result.data
    if not accounts:
        return "No calendar accounts connected."
    
    summary = f"You have {len(accounts)} connected calendar account(s):\n\n"
    
    for account in accounts:
        summary += f"• {account['provider'].title()}: {account['account_email']} "
        summary += f"(connected on {account['connected_at'][:10]}) - {account['status']}\n"
    
    return summary
