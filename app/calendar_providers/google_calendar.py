import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

class GoogleCalendarProvider:
    def __init__(self):
        # Use comprehensive scopes for calendar and user info
        # Include 'openid' explicitly to match Google's automatic inclusion
        self.SCOPES = [
            'openid',
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ]
        self.credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", "credentials/google_calendar_credentials.json")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/calendar/callback/google")
        
    def get_authorization_url(self, state: str) -> str:
        """Get Google OAuth authorization URL"""
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri
        
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='false',  # Don't include previously granted scopes
            prompt='consent',  # Force re-consent to ensure clean scope
            state=state
        )
        return authorization_url
    
    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri
        
        flow.fetch_token(code=code)
        
        # Get user info
        credentials = flow.credentials
        
        try:
            # Try to get user info from OAuth2 API
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            user_email = user_info.get("email")
            user_name = user_info.get("name")
        except Exception as e:
            print(f"Could not get user info from OAuth2 API: {e}")
            # Fallback: get user info from calendar settings
            try:
                calendar_service = build('calendar', 'v3', credentials=credentials)
                calendar_list = calendar_service.calendarList().list().execute()
                primary_calendar = None
                for calendar in calendar_list.get('items', []):
                    if calendar.get('primary'):
                        primary_calendar = calendar
                        break
                
                user_email = primary_calendar.get('id', 'unknown@gmail.com') if primary_calendar else 'unknown@gmail.com'
                user_name = primary_calendar.get('summary', 'Unknown User') if primary_calendar else 'Unknown User'
            except Exception as fallback_error:
                print(f"Fallback method also failed: {fallback_error}")
                user_email = 'unknown@gmail.com'
                user_name = 'Unknown User'
        
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "user_email": user_email,
            "user_name": user_name
        }
    
    def save_token(self, token_data: Dict[str, Any], file_path: str):
        """Save token to file"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(token_data, f)
    
    def load_token(self, file_path: str) -> Credentials:
        """Load token from file"""
        with open(file_path, 'r') as f:
            token_data = json.load(f)
        
        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes")
        )
        
        # Refresh token if necessary
        if credentials.expired:
            credentials.refresh(Request())
            # Update the saved token
            token_data.update({
                "access_token": credentials.token,
            })
            self.save_token(token_data, file_path)
        
        return credentials
    
    def get_all_calendars(self, token_file_path: str) -> List[Dict[str, Any]]:
        """Get list of all calendars accessible to the user"""
        try:
            credentials = self.load_token(token_file_path)
            service = build('calendar', 'v3', credentials=credentials)
            
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            
            formatted_calendars = []
            for calendar in calendars:
                formatted_calendars.append({
                    'id': calendar['id'],
                    'name': calendar.get('summary', calendar['id']),
                    'description': calendar.get('description', ''),
                    'primary': calendar.get('primary', False),
                    'access_role': calendar.get('accessRole', 'reader'),
                    'selected': calendar.get('selected', True),
                    'color_id': calendar.get('colorId'),
                    'background_color': calendar.get('backgroundColor'),
                    'foreground_color': calendar.get('foregroundColor')
                })
            
            return formatted_calendars
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_calendar_events(self, token_file_path: str, max_results: int = 10, calendar_id: str = 'primary') -> List[Dict[str, Any]]:
        """Get calendar events"""
        try:
            credentials = self.load_token(token_file_path)
            service = build('calendar', 'v3', credentials=credentials)
            
            # Call the Calendar API
            now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                formatted_events.append({
                    'id': event['id'],
                    'title': event.get('summary', 'No Title'),
                    'description': event.get('description', ''),
                    'start': start,
                    'end': end,
                    'location': event.get('location', ''),
                    'attendees': [attendee.get('email') for attendee in event.get('attendees', [])],
                    'calendar_id': calendar_id
                })
            
            return formatted_events
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_next_month_events(self, token_file_path: str, calendar_id: str = 'primary') -> List[Dict[str, Any]]:
        """Get next month's calendar events"""
        try:
            credentials = self.load_token(token_file_path)
            service = build('calendar', 'v3', credentials=credentials)
            
            # Get events for next month
            now = datetime.utcnow()
            next_month = now.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            month_end = (next_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            time_min = next_month.isoformat() + 'Z'
            time_max = month_end.isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                formatted_events.append({
                    'id': event['id'],
                    'title': event.get('summary', 'No Title'),
                    'description': event.get('description', ''),
                    'start': start,
                    'end': end,
                    'location': event.get('location', ''),
                    'attendees': [attendee.get('email') for attendee in event.get('attendees', [])],
                    'calendar_id': calendar_id
                })
            
            return formatted_events
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_events_in_range(self, token_file_path: str, start_date: datetime, end_date: datetime, max_results: int = 50, calendar_id: str = 'primary') -> List[Dict[str, Any]]:
        """Get calendar events within a specific date range"""
        try:
            credentials = self.load_token(token_file_path)
            service = build('calendar', 'v3', credentials=credentials)
            
            # Convert datetime to RFC3339 format
            time_min = start_date.isoformat() + 'Z'
            time_max = end_date.isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                formatted_events.append({
                    'id': event['id'],
                    'title': event.get('summary', 'No Title'),
                    'description': event.get('description', ''),
                    'start': start,
                    'end': end,
                    'location': event.get('location', ''),
                    'attendees': [attendee.get('email') for attendee in event.get('attendees', [])],
                    'calendar_id': calendar_id
                })
            
            return formatted_events
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def create_event(self, token_file_path: str, event_data: Dict[str, Any], calendar_id: str = 'primary') -> Dict[str, Any]:
        """Create a new calendar event"""
        try:
            credentials = self.load_token(token_file_path)
            service = build('calendar', 'v3', credentials=credentials)
            
            # Prepare event data for Google Calendar API
            google_event = {
                'summary': event_data.get('title', 'New Event'),
                'description': event_data.get('description', ''),
                'start': {
                    'dateTime': event_data.get('start'),
                    'timeZone': event_data.get('timezone', 'UTC'),
                },
                'end': {
                    'dateTime': event_data.get('end'),
                    'timeZone': event_data.get('timezone', 'UTC'),
                },
            }
            
            # Add location if provided
            if event_data.get('location'):
                google_event['location'] = event_data['location']
            
            # Add attendees if provided
            if event_data.get('attendees'):
                google_event['attendees'] = [{'email': email} for email in event_data['attendees']]
            
            # Create the event
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=google_event
            ).execute()
            
            # Return formatted event
            return {
                'id': created_event['id'],
                'title': created_event.get('summary', 'No Title'),
                'description': created_event.get('description', ''),
                'start': created_event['start'].get('dateTime', created_event['start'].get('date')),
                'end': created_event['end'].get('dateTime', created_event['end'].get('date')),
                'location': created_event.get('location', ''),
                'attendees': [attendee.get('email') for attendee in created_event.get('attendees', [])],
                'calendar_id': calendar_id
            }
            
        except HttpError as error:
            raise Exception(f'Failed to create Google Calendar event: {error}')
    
    def update_event(self, token_file_path: str, event_id: str, event_data: Dict[str, Any], calendar_id: str = 'primary') -> Dict[str, Any]:
        """Update an existing calendar event"""
        try:
            credentials = self.load_token(token_file_path)
            service = build('calendar', 'v3', credentials=credentials)
            
            # Get the existing event
            existing_event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update with new data
            if event_data.get('title'):
                existing_event['summary'] = event_data['title']
            if event_data.get('description'):
                existing_event['description'] = event_data['description']
            if event_data.get('start'):
                existing_event['start'] = {
                    'dateTime': event_data['start'],
                    'timeZone': event_data.get('timezone', 'UTC'),
                }
            if event_data.get('end'):
                existing_event['end'] = {
                    'dateTime': event_data['end'],
                    'timeZone': event_data.get('timezone', 'UTC'),
                }
            if event_data.get('location'):
                existing_event['location'] = event_data['location']
            if event_data.get('attendees'):
                existing_event['attendees'] = [{'email': email} for email in event_data['attendees']]
            
            # Update the event
            updated_event = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=existing_event
            ).execute()
            
            # Return formatted event
            return {
                'id': updated_event['id'],
                'title': updated_event.get('summary', 'No Title'),
                'description': updated_event.get('description', ''),
                'start': updated_event['start'].get('dateTime', updated_event['start'].get('date')),
                'end': updated_event['end'].get('dateTime', updated_event['end'].get('date')),
                'location': updated_event.get('location', ''),
                'attendees': [attendee.get('email') for attendee in updated_event.get('attendees', [])],
                'calendar_id': calendar_id
            }
            
        except HttpError as error:
            raise Exception(f'Failed to update Google Calendar event: {error}')
    
    def delete_event(self, token_file_path: str, event_id: str, calendar_id: str = 'primary') -> bool:
        """Delete a calendar event"""
        try:
            credentials = self.load_token(token_file_path)
            service = build('calendar', 'v3', credentials=credentials)
            
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return True
            
        except HttpError as error:
            if error.resp.status == 404:
                # Event already deleted or doesn't exist
                return True
            raise Exception(f'Failed to delete Google Calendar event: {error}')
    
    def get_event_by_id(self, token_file_path: str, event_id: str, calendar_id: str = 'primary') -> Optional[Dict[str, Any]]:
        """Get a specific event by ID"""
        try:
            credentials = self.load_token(token_file_path)
            service = build('calendar', 'v3', credentials=credentials)
            
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Return formatted event
            return {
                'id': event['id'],
                'title': event.get('summary', 'No Title'),
                'description': event.get('description', ''),
                'start': event['start'].get('dateTime', event['start'].get('date')),
                'end': event['end'].get('dateTime', event['end'].get('date')),
                'location': event.get('location', ''),
                'attendees': [attendee.get('email') for attendee in event.get('attendees', [])],
                'calendar_id': calendar_id
            }
            
        except HttpError as error:
            if error.resp.status == 404:
                return None
            raise Exception(f'Failed to get Google Calendar event: {error}')
    
    def get_events_from_all_calendars(self, token_file_path: str, 
                                    start_date: Optional[datetime] = None, 
                                    end_date: Optional[datetime] = None,
                                    max_results: int = 50) -> List[Dict[str, Any]]:
        """Get events from all accessible calendars"""
        try:
            # Get all calendars first
            calendars = self.get_all_calendars(token_file_path)
            
            if not calendars:
                return []
            
            # Set default date range if not provided
            if start_date is None:
                start_date = datetime.utcnow()
            if end_date is None:
                end_date = start_date + timedelta(days=30)
            
            all_events = []
            
            for calendar in calendars:
                try:
                    # Only get events from calendars where user has read access
                    if calendar.get('access_role') in ['reader', 'writer', 'owner']:
                        events = self.get_events_in_range(
                            token_file_path=token_file_path,
                            start_date=start_date,
                            end_date=end_date,
                            max_results=max_results,
                            calendar_id=calendar['id']
                        )
                        
                        # Add calendar metadata to each event
                        for event in events:
                            event.update({
                                'calendar_name': calendar['name'],
                                'calendar_primary': calendar.get('primary', False),
                                'calendar_color_id': calendar.get('color_id'),
                                'calendar_background_color': calendar.get('background_color'),
                                'calendar_foreground_color': calendar.get('foreground_color')
                            })
                        
                        all_events.extend(events)
                        
                except Exception as e:
                    print(f"Error fetching events from calendar {calendar['name']} ({calendar['id']}): {str(e)}")
                    continue
            
            # Sort events by start time
            all_events.sort(key=lambda x: x.get('start', ''))
            
            return all_events
            
        except Exception as error:
            print(f'An error occurred: {error}')
            return []
