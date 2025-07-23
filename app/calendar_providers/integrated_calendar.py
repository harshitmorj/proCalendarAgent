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
                        if not calendar.get('primary'):
                            continue
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
                                calendar_id: str = 'primary',
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
    
    def get_free_times(self, 
                       start_date: datetime,
                       end_date: datetime,
                       duration_minutes: int = 60,
                       working_hours_start: int = 9,
                       working_hours_end: int = 17,
                       include_weekends: bool = False,
                       buffer_minutes: int = 15) -> List[Dict[str, Any]]:
        """
        Find free time slots for scheduling meetings
        
        Args:
            start_date: Start of the search range
            end_date: End of the search range
            duration_minutes: Required duration for the meeting in minutes
            working_hours_start: Start of working hours (24-hour format, default: 9 AM)
            working_hours_end: End of working hours (24-hour format, default: 5 PM)
            include_weekends: Whether to include weekends in search
            buffer_minutes: Buffer time between meetings (default: 15 minutes)
            
        Returns:
            List of available time slots with start/end times
        """
        # Get all busy times in the range
        busy_times = self.get_busy_times(start_date, end_date)
        
        # Convert busy times to datetime objects for easier manipulation
        busy_periods = []
        for busy in busy_times:
            try:
                start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                busy_periods.append({
                    'start': start,
                    'end': end,
                    'title': busy.get('title', 'Busy'),
                    'provider': busy.get('provider'),
                    'account_email': busy.get('account_email')
                })
            except (ValueError, AttributeError) as e:
                # Skip invalid time formats
                continue
        
        # Sort busy periods by start time
        busy_periods.sort(key=lambda x: x['start'])
        
        # Generate free time slots
        free_slots = []
        current_date = start_date.date()
        end_date_date = end_date.date()
        
        while current_date <= end_date_date:
            # Skip weekends if not included
            if not include_weekends and current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                current_date += timedelta(days=1)
                continue
            
            # Define working hours for this day
            day_start = datetime.combine(current_date, datetime.min.time().replace(hour=working_hours_start))
            day_end = datetime.combine(current_date, datetime.min.time().replace(hour=working_hours_end))
            
            # Make timezone-aware if needed
            if start_date.tzinfo:
                day_start = day_start.replace(tzinfo=start_date.tzinfo)
                day_end = day_end.replace(tzinfo=start_date.tzinfo)
            
            # Get busy periods for this day
            day_busy_periods = [
                bp for bp in busy_periods 
                if bp['start'].date() == current_date or bp['end'].date() == current_date
            ]
            
            # Find free slots for this day
            day_free_slots = self._find_free_slots_in_day(
                day_start, day_end, day_busy_periods, duration_minutes, buffer_minutes
            )
            
            free_slots.extend(day_free_slots)
            current_date += timedelta(days=1)
        
        return free_slots
    
    def _find_free_slots_in_day(self, 
                                day_start: datetime,
                                day_end: datetime,
                                busy_periods: List[Dict[str, Any]],
                                duration_minutes: int,
                                buffer_minutes: int) -> List[Dict[str, Any]]:
        """
        Find free slots within a single day
        
        Args:
            day_start: Start of the working day
            day_end: End of the working day
            busy_periods: List of busy periods for this day
            duration_minutes: Required meeting duration
            buffer_minutes: Buffer time between meetings
            
        Returns:
            List of free time slots for this day
        """
        free_slots = []
        required_duration = timedelta(minutes=duration_minutes)
        buffer_duration = timedelta(minutes=buffer_minutes)
        
        # Filter and sort busy periods that overlap with this day
        day_busy = []
        for busy in busy_periods:
            # Adjust busy period to fit within the working day
            busy_start = max(busy['start'], day_start)
            busy_end = min(busy['end'], day_end)
            
            # Only include if there's actual overlap
            if busy_start < busy_end:
                day_busy.append({
                    'start': busy_start,
                    'end': busy_end,
                    'title': busy.get('title', 'Busy'),
                    'provider': busy.get('provider'),
                    'account_email': busy.get('account_email')
                })
        
        # Sort by start time
        day_busy.sort(key=lambda x: x['start'])
        
        # Merge overlapping busy periods
        merged_busy = self._merge_overlapping_periods(day_busy, buffer_duration)
        
        # Find gaps between busy periods
        current_time = day_start
        
        for busy in merged_busy:
            # Check if there's a gap before this busy period
            gap_end = busy['start']
            gap_duration = gap_end - current_time
            
            if gap_duration >= required_duration:
                # Found a free slot
                free_slots.append({
                    'start': current_time.isoformat(),
                    'end': gap_end.isoformat(),
                    'duration_minutes': int(gap_duration.total_seconds() / 60),
                    'date': current_time.date().isoformat(),
                    'day_of_week': current_time.strftime('%A'),
                    'can_fit_meeting': True
                })
            
            # Move current time to end of this busy period
            current_time = busy['end']
        
        # Check for free time after the last busy period
        if current_time < day_end:
            gap_duration = day_end - current_time
            if gap_duration >= required_duration:
                free_slots.append({
                    'start': current_time.isoformat(),
                    'end': day_end.isoformat(),
                    'duration_minutes': int(gap_duration.total_seconds() / 60),
                    'date': current_time.date().isoformat(),
                    'day_of_week': current_time.strftime('%A'),
                    'can_fit_meeting': True
                })
        
        return free_slots
    
    def _merge_overlapping_periods(self, 
                                   periods: List[Dict[str, Any]], 
                                   buffer_duration: timedelta) -> List[Dict[str, Any]]:
        """
        Merge overlapping or adjacent busy periods (considering buffer time)
        
        Args:
            periods: List of time periods to merge
            buffer_duration: Buffer time to consider when merging
            
        Returns:
            List of merged periods
        """
        if not periods:
            return []
        
        merged = []
        current = periods[0].copy()
        
        for next_period in periods[1:]:
            # Check if periods overlap or are close enough (within buffer)
            gap = next_period['start'] - current['end']
            
            if gap <= buffer_duration:
                # Merge periods
                current['end'] = max(current['end'], next_period['end'])
                # Combine titles if different
                if current.get('title') != next_period.get('title'):
                    current['title'] = f"{current.get('title', 'Busy')} / {next_period.get('title', 'Busy')}"
            else:
                # No overlap, add current to merged list and start new period
                merged.append(current)
                current = next_period.copy()
        
        # Add the last period
        merged.append(current)
        
        return merged
    
    def suggest_meeting_times(self, 
                              participants: List[str],
                              duration_minutes: int = 60,
                              start_date: Optional[datetime] = None,
                              end_date: Optional[datetime] = None,
                              preferred_times: Optional[List[str]] = None,
                              working_hours_start: int = 9,
                              working_hours_end: int = 17,
                              include_weekends: bool = False,
                              max_suggestions: int = 5) -> List[Dict[str, Any]]:
        """
        Suggest optimal meeting times considering all participants' calendars
        
        Args:
            participants: List of participant email addresses
            duration_minutes: Required meeting duration
            start_date: Start of search range (default: now)
            end_date: End of search range (default: 7 days from start)
            preferred_times: List of preferred time slots (e.g., ['morning', 'afternoon'])
            working_hours_start: Start of working hours
            working_hours_end: End of working hours
            include_weekends: Whether to include weekends
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of suggested meeting times with participant availability
        """
        # Set default date range if not provided
        if start_date is None:
            start_date = datetime.utcnow()
        if end_date is None:
            end_date = start_date + timedelta(days=7)
        
        # Get free times for the organizer (current user)
        free_slots = self.get_free_times(
            start_date=start_date,
            end_date=end_date,
            duration_minutes=duration_minutes,
            working_hours_start=working_hours_start,
            working_hours_end=working_hours_end,
            include_weekends=include_weekends
        )
        
        # Score and rank free slots
        suggestions = []
        
        for slot in free_slots:
            try:
                slot_start = datetime.fromisoformat(slot['start'])
                slot_end = datetime.fromisoformat(slot['end'])
                
                # Calculate preference score
                score = self._calculate_time_preference_score(
                    slot_start, preferred_times, working_hours_start, working_hours_end
                )
                
                suggestion = {
                    'start_time': slot['start'],
                    'end_time': slot_start + timedelta(minutes=duration_minutes),
                    'date': slot['date'],
                    'day_of_week': slot['day_of_week'],
                    'duration_minutes': duration_minutes,
                    'available_duration': slot['duration_minutes'],
                    'preference_score': score,
                    'participants': participants,
                    'availability_status': 'available',
                    'conflicts': [],
                    'notes': []
                }
                
                # Add time-of-day description
                hour = slot_start.hour
                if hour < 12:
                    suggestion['time_of_day'] = 'morning'
                elif hour < 17:
                    suggestion['time_of_day'] = 'afternoon'
                else:
                    suggestion['time_of_day'] = 'evening'
                
                # Add buffer time info
                buffer_available = slot['duration_minutes'] - duration_minutes
                if buffer_available > 0:
                    suggestion['notes'].append(f"{buffer_available} minutes buffer available")
                
                suggestions.append(suggestion)
                
            except (ValueError, KeyError) as e:
                continue
        
        # Sort by preference score (descending) and take top suggestions
        suggestions.sort(key=lambda x: x['preference_score'], reverse=True)
        
        return suggestions[:max_suggestions]
    
    def _calculate_time_preference_score(self, 
                                         slot_start: datetime,
                                         preferred_times: Optional[List[str]],
                                         working_hours_start: int,
                                         working_hours_end: int) -> float:
        """
        Calculate a preference score for a time slot
        
        Args:
            slot_start: Start time of the slot
            preferred_times: List of preferred time periods
            working_hours_start: Start of working hours
            working_hours_end: End of working hours
            
        Returns:
            Score between 0 and 1 (higher is better)
        """
        score = 0.5  # Base score
        
        hour = slot_start.hour
        day_of_week = slot_start.weekday()  # 0 = Monday, 6 = Sunday
        
        # Prefer core working hours
        if working_hours_start + 1 <= hour <= working_hours_end - 2:
            score += 0.2
        
        # Prefer weekdays
        if day_of_week < 5:  # Monday to Friday
            score += 0.1
        
        # Prefer Tuesday to Thursday (avoid Monday/Friday)
        if 1 <= day_of_week <= 3:
            score += 0.1
        
        # Apply preferred times if specified
        if preferred_times:
            for pref in preferred_times:
                if pref.lower() == 'morning' and 8 <= hour < 12:
                    score += 0.2
                elif pref.lower() == 'afternoon' and 12 <= hour < 17:
                    score += 0.2
                elif pref.lower() == 'evening' and 17 <= hour < 20:
                    score += 0.1
        
        # Slight preference for round hours
        if slot_start.minute == 0:
            score += 0.05
        elif slot_start.minute == 30:
            score += 0.02
        
        return min(score, 1.0)  # Cap at 1.0
    
    def check_availability(self, 
                          start_time: datetime,
                          end_time: datetime,
                          participants: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Check availability for a specific time slot
        
        Args:
            start_time: Proposed meeting start time
            end_time: Proposed meeting end time
            participants: List of participant emails (optional)
            
        Returns:
            Availability information including conflicts
        """
        # Get busy times for the time range
        busy_times = self.get_busy_times(start_time, end_time)
        
        conflicts = []
        for busy in busy_times:
            try:
                busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                
                # Check for overlap
                if not (end_time <= busy_start or start_time >= busy_end):
                    conflicts.append({
                        'title': busy.get('title', 'Busy'),
                        'start': busy['start'],
                        'end': busy['end'],
                        'provider': busy.get('provider'),
                        'account_email': busy.get('account_email'),
                        'overlap_start': max(start_time, busy_start).isoformat(),
                        'overlap_end': min(end_time, busy_end).isoformat()
                    })
            except (ValueError, AttributeError):
                continue
        
        is_available = len(conflicts) == 0
        
        return {
            'available': is_available,
            'requested_start': start_time.isoformat(),
            'requested_end': end_time.isoformat(),
            'duration_minutes': int((end_time - start_time).total_seconds() / 60),
            'conflicts': conflicts,
            'conflict_count': len(conflicts),
            'participants': participants or [],
            'checked_at': datetime.utcnow().isoformat()
        }
    
    def find_next_available_time(self, 
                                duration_minutes: int = 60,
                                start_from: Optional[datetime] = None,
                                working_hours_start: int = 9,
                                working_hours_end: int = 17,
                                include_weekends: bool = False,
                                max_days_ahead: int = 14) -> Optional[Dict[str, Any]]:
        """
        Find the next available time slot for a meeting
        
        Args:
            duration_minutes: Required meeting duration
            start_from: Start searching from this time (default: now)
            working_hours_start: Start of working hours
            working_hours_end: End of working hours
            include_weekends: Whether to include weekends
            max_days_ahead: Maximum days to search ahead
            
        Returns:
            Next available time slot or None if not found
        """
        if start_from is None:
            start_from = datetime.utcnow()
        
        # Round start time to next 15-minute interval
        minutes = start_from.minute
        rounded_minutes = ((minutes // 15) + 1) * 15
        if rounded_minutes >= 60:
            start_from = start_from.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            start_from = start_from.replace(minute=rounded_minutes, second=0, microsecond=0)
        
        search_end = start_from + timedelta(days=max_days_ahead)
        
        # Get free times in the search range
        free_slots = self.get_free_times(
            start_date=start_from,
            end_date=search_end,
            duration_minutes=duration_minutes,
            working_hours_start=working_hours_start,
            working_hours_end=working_hours_end,
            include_weekends=include_weekends
        )
        
        if not free_slots:
            return None
        
        # Return the first available slot
        first_slot = free_slots[0]
        slot_start = datetime.fromisoformat(first_slot['start'])
        
        return {
            'start_time': first_slot['start'],
            'end_time': (slot_start + timedelta(minutes=duration_minutes)).isoformat(),
            'date': first_slot['date'],
            'day_of_week': first_slot['day_of_week'],
            'duration_minutes': duration_minutes,
            'available_duration': first_slot['duration_minutes'],
            'time_from_now': str(slot_start - start_from),
            'found_in_days': (slot_start.date() - start_from.date()).days
        }
    
    def get_availability_summary(self, 
                                start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None,
                                working_hours_start: int = 9,
                                working_hours_end: int = 17) -> Dict[str, Any]:
        """
        Get a summary of availability within a date range
        
        Args:
            start_date: Start of analysis range (default: today)
            end_date: End of analysis range (default: 7 days from start)
            working_hours_start: Start of working hours
            working_hours_end: End of working hours
            
        Returns:
            Availability summary with statistics
        """
        if start_date is None:
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if end_date is None:
            end_date = start_date + timedelta(days=7)
        
        # Calculate total working hours in the range
        total_working_hours = 0
        current_date = start_date.date()
        end_date_date = end_date.date()
        
        while current_date <= end_date_date:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday to Friday
                total_working_hours += (working_hours_end - working_hours_start)
            current_date += timedelta(days=1)
        
        # Get busy times
        busy_times = self.get_busy_times(start_date, end_date)
        
        # Calculate busy hours
        busy_hours = 0
        for busy in busy_times:
            try:
                busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                
                # Only count time within working hours
                day_start = datetime.combine(busy_start.date(), 
                                           datetime.min.time().replace(hour=working_hours_start))
                day_end = datetime.combine(busy_start.date(), 
                                         datetime.min.time().replace(hour=working_hours_end))
                
                if start_date.tzinfo:
                    day_start = day_start.replace(tzinfo=start_date.tzinfo)
                    day_end = day_end.replace(tzinfo=start_date.tzinfo)
                
                # Clip to working hours
                clipped_start = max(busy_start, day_start)
                clipped_end = min(busy_end, day_end)
                
                if clipped_start < clipped_end:
                    busy_hours += (clipped_end - clipped_start).total_seconds() / 3600
                    
            except (ValueError, AttributeError):
                continue
        
        # Get free slots for analysis
        free_slots = self.get_free_times(
            start_date=start_date,
            end_date=end_date,
            duration_minutes=60,  # 1-hour slots for analysis
            working_hours_start=working_hours_start,
            working_hours_end=working_hours_end,
            include_weekends=False
        )
        
        # Calculate statistics
        free_hours = total_working_hours - busy_hours
        utilization_percent = (busy_hours / total_working_hours * 100) if total_working_hours > 0 else 0
        
        # Analyze free slot distribution
        slot_distribution = {
            'short_slots_under_1h': 0,
            'medium_slots_1_2h': 0,
            'long_slots_over_2h': 0
        }
        
        longest_free_slot = 0
        for slot in free_slots:
            duration = slot['duration_minutes']
            longest_free_slot = max(longest_free_slot, duration)
            
            if duration < 60:
                slot_distribution['short_slots_under_1h'] += 1
            elif duration < 120:
                slot_distribution['medium_slots_1_2h'] += 1
            else:
                slot_distribution['long_slots_over_2h'] += 1
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date.date() - start_date.date()).days + 1
            },
            'working_hours': {
                'daily_start': working_hours_start,
                'daily_end': working_hours_end,
                'total_hours': total_working_hours
            },
            'busy_time': {
                'total_hours': round(busy_hours, 2),
                'events_count': len(busy_times),
                'utilization_percent': round(utilization_percent, 1)
            },
            'free_time': {
                'total_hours': round(free_hours, 2),
                'available_percent': round(100 - utilization_percent, 1),
                'free_slots_count': len(free_slots),
                'longest_slot_minutes': longest_free_slot
            },
            'slot_distribution': slot_distribution,
            'availability_status': self._get_availability_status(utilization_percent),
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def _get_availability_status(self, utilization_percent: float) -> str:
        """Get availability status based on utilization percentage"""
        if utilization_percent < 30:
            return 'very_available'
        elif utilization_percent < 60:
            return 'moderately_available'
        elif utilization_percent < 80:
            return 'limited_availability'
        else:
            return 'very_busy'
