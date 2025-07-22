from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..database.models import User, CalendarAccount
from .google_calendar import GoogleCalendarProvider
from .microsoft_calendar import MicrosoftCalendarProvider
import uuid
import json

class IntegratedCalendar:
    """
    IntegratedCalendar provides unified CRUD operations across all connected calendar providers.
    This class abstracts the complexity of different calendar APIs and provides a consistent interface.
    """
    
    def __init__(self, user_id: int, db_session: Session):
        self.user_id = user_id
        self.db = db_session
        self.google_provider = GoogleCalendarProvider()
        self.microsoft_provider = MicrosoftCalendarProvider()
        
    def _get_calendar_accounts(self) -> List[CalendarAccount]:
        """Get all active calendar accounts for the user"""
        return self.db.query(CalendarAccount).filter(
            CalendarAccount.user_id == self.user_id,
            CalendarAccount.is_active == True
        ).all()
    
    def _get_provider(self, provider_name: str):
        """Get the appropriate provider instance"""
        if provider_name == "google":
            return self.google_provider
        elif provider_name == "microsoft":
            return self.microsoft_provider
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")
    
    def get_all_events(self, 
                       start_date: Optional[datetime] = None, 
                       end_date: Optional[datetime] = None,
                       max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Get events from all connected calendars within the specified date range
        
        Args:
            start_date: Start date for event retrieval (default: now)
            end_date: End date for event retrieval (default: 30 days from start)
            max_results: Maximum number of events to retrieve per calendar
            
        Returns:
            List of unified event dictionaries
        """
        accounts = self._get_calendar_accounts()
        
        if not accounts:
            return []
        
        # Set default date range if not provided
        if start_date is None:
            start_date = datetime.utcnow()
        if end_date is None:
            end_date = start_date + timedelta(days=30)
        
        all_events = []
        
        for account in accounts:
            try:
                provider = self._get_provider(account.provider)
                
                if account.provider == "google":
                    # Use the new method to get events from all Google calendars
                    events = provider.get_events_from_all_calendars(
                        token_file_path=account.token_file_path,
                        start_date=start_date,
                        end_date=end_date,
                        max_results=max_results
                    )
                else:
                    # For Microsoft and other providers, use the existing method
                    events = provider.get_events_in_range(
                        token_file_path=account.token_file_path,
                        start_date=start_date,
                        end_date=end_date,
                        max_results=max_results
                    )
                
                # Add metadata to each event
                for event in events:
                    event.update({
                        'provider': account.provider,
                        'account_email': account.account_email,
                        'account_id': account.id
                    })
                
                all_events.extend(events)
                
            except Exception as e:
                print(f"Error fetching events from {account.provider} ({account.account_email}): {str(e)}")
                continue
        
        # Sort events by start time
        all_events.sort(key=lambda x: x.get('start', ''))
        
        return all_events
    
    def get_all_calendars(self) -> List[Dict[str, Any]]:
        """
        Get all calendars from all connected accounts
        
        Returns:
            List of calendar dictionaries with provider metadata
        """
        accounts = self._get_calendar_accounts()
        
        if not accounts:
            return []
        
        all_calendars = []
        
        for account in accounts:
            try:
                provider = self._get_provider(account.provider)
                
                if account.provider == "google":
                    calendars = provider.get_all_calendars(account.token_file_path)
                    
                    # Add metadata to each calendar
                    for calendar in calendars:
                        calendar.update({
                            'provider': account.provider,
                            'account_email': account.account_email,
                            'account_id': account.id
                        })
                    
                    all_calendars.extend(calendars)
                else:
                    # For Microsoft, we might want to implement a similar method
                    # For now, we'll add a basic entry for the account
                    all_calendars.append({
                        'id': 'primary',
                        'name': f"{account.account_email} (Default)",
                        'description': f"Default calendar for {account.account_email}",
                        'primary': True,
                        'access_role': 'owner',
                        'provider': account.provider,
                        'account_email': account.account_email,
                        'account_id': account.id
                    })
                
            except Exception as e:
                print(f"Error fetching calendars from {account.provider} ({account.account_email}): {str(e)}")
                continue
        
        return all_calendars
    
    def get_events_from_calendar(self, 
                                provider: str,
                                account_email: str,
                                calendar_id: str,
                                start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None,
                                max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Get events from a specific calendar
        
        Args:
            provider: Calendar provider ('google' or 'microsoft')
            account_email: Email of the account
            calendar_id: ID of the specific calendar
            start_date: Start date for event retrieval
            end_date: End date for event retrieval
            max_results: Maximum number of events to retrieve
            
        Returns:
            List of events from the specified calendar
        """
        # Find the specific account
        account = self.db.query(CalendarAccount).filter(
            CalendarAccount.user_id == self.user_id,
            CalendarAccount.provider == provider,
            CalendarAccount.account_email == account_email,
            CalendarAccount.is_active == True
        ).first()
        
        if not account:
            raise ValueError(f"No active {provider} account found for {account_email}")
        
        # Set default date range if not provided
        if start_date is None:
            start_date = datetime.utcnow()
        if end_date is None:
            end_date = start_date + timedelta(days=30)
        
        try:
            provider_instance = self._get_provider(provider)
            
            if provider == "google":
                events = provider_instance.get_events_in_range(
                    token_file_path=account.token_file_path,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=max_results,
                    calendar_id=calendar_id
                )
            else:
                # For Microsoft and other providers
                events = provider_instance.get_events_in_range(
                    token_file_path=account.token_file_path,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=max_results
                )
            
            # Add metadata to each event
            for event in events:
                event.update({
                    'provider': provider,
                    'account_email': account_email,
                    'account_id': account.id
                })
            
            return events
            
        except Exception as e:
            print(f"Error fetching events from {provider} calendar {calendar_id}: {str(e)}")
            return []
    
    def create_event(self, 
                     provider: str,
                     account_email: str,
                     event_data: Dict[str, Any],
                     calendar_id: str = 'primary') -> Dict[str, Any]:
        """
        Create an event in a specific calendar
        
        Args:
            provider: Calendar provider ('google' or 'microsoft')
            account_email: Email of the account to create event in
            event_data: Event details dictionary
            calendar_id: ID of the calendar to create event in (default: 'primary')
            
        Returns:
            Created event details
        """
        # Find the specific account
        account = self.db.query(CalendarAccount).filter(
            CalendarAccount.user_id == self.user_id,
            CalendarAccount.provider == provider,
            CalendarAccount.account_email == account_email,
            CalendarAccount.is_active == True
        ).first()
        
        if not account:
            raise ValueError(f"No active {provider} account found for {account_email}")
        
        try:
            provider_instance = self._get_provider(provider)
            
            # For Microsoft provider, initialize with user context for better token management
            if provider == "microsoft":
                provider_instance = MicrosoftCalendarProvider(
                    user_id=self.user_id,
                    account_email=account_email,
                    db_session=self.db
                )
                created_event = provider_instance.create_event(
                    token_file_path=account.token_file_path,
                    event_data=event_data
                )
            else:
                # For Google provider, use the calendar_id parameter
                created_event = provider_instance.create_event(
                    token_file_path=account.token_file_path,
                    event_data=event_data,
                    calendar_id=calendar_id
                )
            
            # Add metadata
            created_event.update({
                'provider': provider,
                'account_email': account_email,
                'account_id': account.id
            })
            
            return created_event
            
        except Exception as e:
            raise Exception(f"Failed to create event in {provider}: {str(e)}")
    
    def update_event(self, 
                     provider: str,
                     account_email: str,
                     event_id: str,
                     event_data: Dict[str, Any],
                     calendar_id: str = 'primary') -> Dict[str, Any]:
        """
        Update an existing event
        
        Args:
            provider: Calendar provider ('google' or 'microsoft')
            account_email: Email of the account containing the event
            event_id: ID of the event to update
            event_data: Updated event details
            calendar_id: ID of the calendar containing the event (default: 'primary')
            
        Returns:
            Updated event details
        """
        # Find the specific account
        account = self.db.query(CalendarAccount).filter(
            CalendarAccount.user_id == self.user_id,
            CalendarAccount.provider == provider,
            CalendarAccount.account_email == account_email,
            CalendarAccount.is_active == True
        ).first()
        
        if not account:
            raise ValueError(f"No active {provider} account found for {account_email}")
        
        try:
            provider_instance = self._get_provider(provider)
            
            if provider == "google":
                updated_event = provider_instance.update_event(
                    token_file_path=account.token_file_path,
                    event_id=event_id,
                    event_data=event_data,
                    calendar_id=calendar_id
                )
            else:
                # For Microsoft and other providers
                updated_event = provider_instance.update_event(
                    token_file_path=account.token_file_path,
                    event_id=event_id,
                    event_data=event_data
                )
            
            # Add metadata
            updated_event.update({
                'provider': provider,
                'account_email': account_email,
                'account_id': account.id
            })
            
            return updated_event
            
        except Exception as e:
            raise Exception(f"Failed to update event in {provider}: {str(e)}")
    
    def delete_event(self, 
                     provider: str,
                     account_email: str,
                     event_id: str,
                     calendar_id: str = 'primary') -> bool:
        """
        Delete an event from a specific calendar
        
        Args:
            provider: Calendar provider ('google' or 'microsoft')
            account_email: Email of the account containing the event
            event_id: ID of the event to delete
            calendar_id: ID of the calendar containing the event (default: 'primary')
            
        Returns:
            True if deletion was successful
        """
        # Find the specific account
        account = self.db.query(CalendarAccount).filter(
            CalendarAccount.user_id == self.user_id,
            CalendarAccount.provider == provider,
            CalendarAccount.account_email == account_email,
            CalendarAccount.is_active == True
        ).first()
        
        if not account:
            raise ValueError(f"No active {provider} account found for {account_email}")
        
        try:
            provider_instance = self._get_provider(provider)
            
            if provider == "google":
                return provider_instance.delete_event(
                    token_file_path=account.token_file_path,
                    event_id=event_id,
                    calendar_id=calendar_id
                )
            else:
                # For Microsoft and other providers
                return provider_instance.delete_event(
                    token_file_path=account.token_file_path,
                    event_id=event_id
                )
            
        except Exception as e:
            raise Exception(f"Failed to delete event from {provider}: {str(e)}")
    
    def get_event_by_id(self, 
                        provider: str,
                        account_email: str,
                        event_id: str,
                        calendar_id: str = 'primary') -> Optional[Dict[str, Any]]:
        """
        Get a specific event by ID
        
        Args:
            provider: Calendar provider ('google' or 'microsoft')
            account_email: Email of the account containing the event
            event_id: ID of the event to retrieve
            calendar_id: ID of the calendar containing the event (default: 'primary')
            
        Returns:
            Event details or None if not found
        """
        # Find the specific account
        account = self.db.query(CalendarAccount).filter(
            CalendarAccount.user_id == self.user_id,
            CalendarAccount.provider == provider,
            CalendarAccount.account_email == account_email,
            CalendarAccount.is_active == True
        ).first()
        
        if not account:
            raise ValueError(f"No active {provider} account found for {account_email}")
        
        try:
            provider_instance = self._get_provider(provider)
            
            if provider == "google":
                event = provider_instance.get_event_by_id(
                    token_file_path=account.token_file_path,
                    event_id=event_id,
                    calendar_id=calendar_id
                )
            else:
                # For Microsoft and other providers
                event = provider_instance.get_event_by_id(
                    token_file_path=account.token_file_path,
                    event_id=event_id
                )
            
            if event:
                # Add metadata
                event.update({
                    'provider': provider,
                    'account_email': account_email,
                    'account_id': account.id
                })
            
            return event
            
        except Exception as e:
            print(f"Failed to get event from {provider}: {str(e)}")
            return None
    
    def get_calendar_accounts_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary information about all connected calendar accounts
        
        Returns:
            List of account summaries
        """
        accounts = self._get_calendar_accounts()
        
        summary = []
        for account in accounts:
            try:
                provider_instance = self._get_provider(account.provider)
                
                # Get recent events count as a health check
                recent_events = provider_instance.get_calendar_events(
                    token_file_path=account.token_file_path,
                    max_results=5
                )
                
                summary.append({
                    'id': account.id,
                    'provider': account.provider,
                    'account_email': account.account_email,
                    'connected_at': account.connected_at.isoformat(),
                    'is_active': account.is_active,
                    'recent_events_count': len(recent_events),
                    'status': 'connected'
                })
                
            except Exception as e:
                summary.append({
                    'id': account.id,
                    'provider': account.provider,
                    'account_email': account.account_email,
                    'connected_at': account.connected_at.isoformat(),
                    'is_active': account.is_active,
                    'recent_events_count': 0,
                    'status': f'error: {str(e)}'
                })
        
        return summary
    
    def search_events(self, 
                      query: str,
                      start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None,
                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for events across all calendars
        
        Args:
            query: Search query string
            start_date: Start date for search range
            end_date: End date for search range
            limit: Maximum number of results to return
            
        Returns:
            List of matching events
        """
        all_events = self.get_all_events(start_date=start_date, end_date=end_date)
        
        # Simple text search across event fields
        query_lower = query.lower()
        matching_events = []
        
        for event in all_events:
            title = event.get('title', '').lower()
            description = event.get('description', '').lower()
            location = event.get('location', '').lower()
            attendees = ' '.join(event.get('attendees', [])).lower()
            
            if (query_lower in title or 
                query_lower in description or 
                query_lower in location or 
                query_lower in attendees):
                matching_events.append(event)
                
                # Apply limit if specified
                if limit and len(matching_events) >= limit:
                    break
        
        return matching_events
    
    def get_busy_times(self, 
                       start_date: datetime,
                       end_date: datetime) -> List[Dict[str, Any]]:
        """
        Get all busy times (events) within a date range for scheduling purposes
        
        Args:
            start_date: Start of the time range
            end_date: End of the time range
            
        Returns:
            List of busy time slots
        """
        events = self.get_all_events(start_date=start_date, end_date=end_date)
        
        busy_times = []
        for event in events:
            # Only include events that have confirmed times (not all-day events)
            if event.get('start') and event.get('end'):
                busy_times.append({
                    'start': event['start'],
                    'end': event['end'],
                    'title': event.get('title', 'Busy'),
                    'provider': event.get('provider'),
                    'account_email': event.get('account_email')
                })
        
        # Sort by start time
        busy_times.sort(key=lambda x: x['start'])
        
        return busy_times
