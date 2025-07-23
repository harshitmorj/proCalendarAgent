import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import msal
from dotenv import load_dotenv
import requests

load_dotenv()

class MicrosoftCalendarProvider:
    def __init__(self, user_id: Optional[int] = None, account_email: Optional[str] = None, db_session: Optional[Any] = None):
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID")
        self.redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI")
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["https://graph.microsoft.com/Calendars.ReadWrite"]
        
        # Store user context for token management
        self.user_id = user_id
        self.account_email = account_email
        self.db_session = db_session
    
    def get_user_profile(self, token_file_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get user profile to test token validity"""
        if not token_file_path and self.user_id and self.account_email:
            # Try to get token file path from database context
            token_file_path = self._get_token_file_path()
        
        if not token_file_path:
            return None
            
        try:
            token_data = self.load_token(token_file_path)
            headers = {'Authorization': f"Bearer {token_data['access_token']}"}
            
            response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
            
            if response.status_code == 401:
                # Token expired, try to refresh
                if self.refresh_access_token(token_file_path):
                    # Retry with refreshed token
                    token_data = self.load_token(token_file_path)
                    headers = {'Authorization': f"Bearer {token_data['access_token']}"}
                    response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
                else:
                    return None
            
            if response.status_code == 200:
                user_info = response.json()
                return {
                    "email": user_info.get("mail") or user_info.get("userPrincipalName"),
                    "displayName": user_info.get("displayName"),
                    "id": user_info.get("id")
                }
            else:
                return None
                
        except Exception as error:
            print(f"Error getting user profile: {error}")
            return None
    
    def _get_token_file_path(self) -> Optional[str]:
        """Get token file path from database context"""
        if not self.db_session or not self.user_id or not self.account_email:
            return None
        
        try:
            from ..database.models import CalendarAccount
            account = self.db_session.query(CalendarAccount).filter(
                CalendarAccount.user_id == self.user_id,
                CalendarAccount.account_email == self.account_email,
                CalendarAccount.provider == 'microsoft',
                CalendarAccount.is_active == True
            ).first()
            
            return account.token_file_path if account else None
        except Exception:
            return None
    
    def refresh_access_token(self, token_file_path: Optional[str] = None) -> bool:
        """Refresh access token using refresh token, with improved error handling and logging."""
        if not token_file_path and self.user_id and self.account_email:
            token_file_path = self._get_token_file_path()

        if not token_file_path:
            print("No token file path provided for refresh.")
            return False

        try:
            token_data = self.load_token(token_file_path)
            refresh_token = token_data.get('refresh_token')

            if not refresh_token:
                print("No refresh token available in token data:", token_data)
                return False

            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=self.authority,
                client_credential=self.client_secret
            )

            result = app.acquire_token_by_refresh_token(
                refresh_token,
                scopes=self.scopes
            )

            print("MSAL refresh response:", result)

            if "error" in result or not result.get("access_token"):
                print(f"Token refresh failed: {result.get('error_description', 'Unknown error')}")
                print("Prompt user to re-authenticate.")
                return False

            # Update token data with new tokens
            updated_token_data = {
                **token_data,
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token", refresh_token),  # Keep old if new not provided
                "expires_in": result.get("expires_in"),
                "token_type": result.get("token_type"),
                "scope": result.get("scope")
            }

            # Save updated token
            self.save_token(updated_token_data, token_file_path)
            print("Token successfully refreshed and saved.")
            return True

        except Exception as error:
            print(f"Token refresh error: {error}")
            print("Prompt user to re-authenticate.")
            return False
        
    def get_authorization_url(self, state: str) -> str:
        """Get Microsoft OAuth authorization URL"""
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )
        
        auth_url = app.get_authorization_request_url(
            scopes=self.scopes,
            state=state,
            redirect_uri=self.redirect_uri
        )
        return auth_url
    
    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )
        
        result = app.acquire_token_by_authorization_code(
            code,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        
        if "error" in result:
            raise Exception(f"Token acquisition failed: {result['error_description']}")
        
        # Get user info
        headers = {'Authorization': f"Bearer {result['access_token']}"}
        user_response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
        user_info = user_response.json()
        
        return {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "token_type": result["token_type"],
            "expires_in": result["expires_in"],
            "scope": result["scope"],
            "user_email": user_info.get("mail") or user_info.get("userPrincipalName"),
            "user_name": user_info.get("displayName")
        }
    
    def save_token(self, token_data: Dict[str, Any], file_path: str):
        """Save token to file"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(token_data, f)
    
    def load_token(self, file_path: str) -> Dict[str, Any]:
        """Load token from file"""
        with open(file_path, 'r') as f:
            token_data = json.load(f)
        
        # Check if token needs refresh (simplified - in production, check expiration)
        return token_data

    def get_calendar_events(self, token_file_path: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Get calendar events"""
        try:
            token_data = self.load_token(token_file_path)
            headers = {'Authorization': f"Bearer {token_data['access_token']}"}
            
            # Get events from Microsoft Graph API
            now = datetime.utcnow().isoformat() + 'Z'
            url = f"https://graph.microsoft.com/v1.0/me/events?$filter=start/dateTime ge '{now}'&$orderby=start/dateTime&$top={max_results}"
            
            response = requests.get(url, headers=headers)
            
            # Handle token expiration
            if response.status_code == 401:
                if self.refresh_access_token(token_file_path):
                    token_data = self.load_token(token_file_path)
                    headers = {'Authorization': f"Bearer {token_data['access_token']}"}
                    response = requests.get(url, headers=headers)
                else:
                    raise Exception("Token refresh failed")
            
            if response.status_code == 200:
                events = response.json().get('value', [])
                
                formatted_events = []
                for event in events:
                    attendees = []
                    if event.get('attendees'):
                        attendees = [attendee['emailAddress']['address'] for attendee in event['attendees']]
                    
                    formatted_events.append({
                        'id': event['id'],
                        'title': event.get('subject', 'No Title'),
                        'description': event.get('body', {}).get('content', ''),
                        'start': event['start']['dateTime'],
                        'end': event['end']['dateTime'],
                        'location': event.get('location', {}).get('displayName', ''),
                        'attendees': attendees
                    })
                
                return formatted_events
            else:
                raise Exception(f'HTTP {response.status_code}: {response.text}')
        except Exception as error:
            raise Exception(f'Failed to get Microsoft Calendar events: {error}')
    
    def get_next_month_events(self, token_file_path: str) -> List[Dict[str, Any]]:
        """Get next month's calendar events"""
        try:
            token_data = self.load_token(token_file_path)
            headers = {'Authorization': f"Bearer {token_data['access_token']}"}
            
            # Get events for next month
            now = datetime.utcnow()
            next_month = now.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            month_end = (next_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            time_min = next_month.isoformat() + 'Z'
            time_max = month_end.isoformat() + 'Z'
            
            url = f"https://graph.microsoft.com/v1.0/me/events?$filter=start/dateTime ge '{time_min}' and start/dateTime le '{time_max}'&$orderby=start/dateTime"
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                events = response.json().get('value', [])
                
                formatted_events = []
                for event in events:
                    attendees = []
                    if event.get('attendees'):
                        attendees = [attendee['emailAddress']['address'] for attendee in event['attendees']]
                    
                    formatted_events.append({
                        'id': event['id'],
                        'title': event.get('subject', 'No Title'),
                        'description': event.get('body', {}).get('content', ''),
                        'start': event['start']['dateTime'],
                        'end': event['end']['dateTime'],
                        'location': event.get('location', {}).get('displayName', ''),
                        'attendees': attendees
                    })
                
                return formatted_events
            else:
                print(f'Error fetching events: {response.status_code} : {response.text}')
                return []
        except Exception as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_events_in_range(self, token_file_path: str, start_date: datetime, end_date: datetime, max_results: int = 50) -> List[Dict[str, Any]]:
        """Get calendar events within a specific date range"""
        try:
            token_data = self.load_token(token_file_path)
            headers = {'Authorization': f"Bearer {token_data['access_token']}"}
            
            # Convert datetime to ISO format
            time_min = start_date.isoformat() + 'Z'
            time_max = end_date.isoformat() + 'Z'
            
            url = f"https://graph.microsoft.com/v1.0/me/events?$filter=start/dateTime ge '{time_min}' and start/dateTime le '{time_max}'&$orderby=start/dateTime&$top={max_results}"
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                events = response.json().get('value', [])
                
                formatted_events = []
                for event in events:
                    attendees = []
                    if event.get('attendees'):
                        attendees = [attendee['emailAddress']['address'] for attendee in event['attendees']]
                    
                    formatted_events.append({
                        'id': event['id'],
                        'title': event.get('subject', 'No Title'),
                        'description': event.get('body', {}).get('content', ''),
                        'start': event['start']['dateTime'],
                        'end': event['end']['dateTime'],
                        'location': event.get('location', {}).get('displayName', ''),
                        'attendees': attendees
                    })
                
                return formatted_events
            else:
                print(f'Error fetching events: {response.status_code} : {response.text}')
                return []
        except Exception as error:
            print(f'An error occurred: {error}')
            return []
    
    def create_event(self, token_file_path: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new calendar event"""
        try:
            token_data = self.load_token(token_file_path)
            headers = {
                'Authorization': f"Bearer {token_data['access_token']}",
                'Content-Type': 'application/json'
            }
            
            # Prepare event data for Microsoft Graph API
            microsoft_event = {
                'subject': event_data.get('title', 'New Event'),
                'body': {
                    'contentType': 'Text',
                    'content': event_data.get('description', '')
                },
                'start': {
                    'dateTime': event_data.get('start'),
                    'timeZone': event_data.get('timezone', 'UTC')
                },
                'end': {
                    'dateTime': event_data.get('end'),
                    'timeZone': event_data.get('timezone', 'UTC')
                }
            }
            
            # Add location if provided
            if event_data.get('location'):
                microsoft_event['location'] = {
                    'displayName': event_data['location']
                }
            
            # Add attendees if provided
            if event_data.get('attendees'):
                microsoft_event['attendees'] = [
                    {
                        'emailAddress': {
                            'address': email,
                            'name': email
                        },
                        'type': 'required'
                    } for email in event_data['attendees']
                ]
            
            # Create the event
            url = "https://graph.microsoft.com/v1.0/me/events"
            response = requests.post(url, headers=headers, json=microsoft_event)
            
            # Handle token expiration
            if response.status_code == 401:
                if self.refresh_access_token(token_file_path):
                    token_data = self.load_token(token_file_path)
                    headers['Authorization'] = f"Bearer {token_data['access_token']}"
                    response = requests.post(url, headers=headers, json=microsoft_event)
                else:
                    raise Exception("Token refresh failed")
            
            if response.status_code == 201:
                created_event = response.json()
                
                # Return formatted event
                attendees = []
                if created_event.get('attendees'):
                    attendees = [attendee['emailAddress']['address'] for attendee in created_event['attendees']]
                
                return {
                    'id': created_event['id'],
                    'title': created_event.get('subject', 'No Title'),
                    'description': created_event.get('body', {}).get('content', ''),
                    'start': created_event['start']['dateTime'],
                    'end': created_event['end']['dateTime'],
                    'location': created_event.get('location', {}).get('displayName', ''),
                    'attendees': attendees
                }
            else:
                raise Exception(f'HTTP {response.status_code}: {response.text}')
                
        except Exception as error:
            raise Exception(f'Failed to create Microsoft Calendar event: {error}')
    
    def update_event(self, token_file_path: str, event_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing calendar event"""
        try:
            token_data = self.load_token(token_file_path)
            headers = {
                'Authorization': f"Bearer {token_data['access_token']}",
                'Content-Type': 'application/json'
            }
            
            # Prepare update data
            update_data = {}
            
            if event_data.get('title'):
                update_data['subject'] = event_data['title']
            if event_data.get('description'):
                update_data['body'] = {
                    'contentType': 'Text',
                    'content': event_data['description']
                }
            if event_data.get('start'):
                update_data['start'] = {
                    'dateTime': event_data['start'],
                    'timeZone': event_data.get('timezone', 'UTC')
                }
            if event_data.get('end'):
                update_data['end'] = {
                    'dateTime': event_data['end'],
                    'timeZone': event_data.get('timezone', 'UTC')
                }
            if event_data.get('location'):
                update_data['location'] = {
                    'displayName': event_data['location']
                }
            if event_data.get('attendees'):
                update_data['attendees'] = [
                    {
                        'emailAddress': {
                            'address': email,
                            'name': email
                        },
                        'type': 'required'
                    } for email in event_data['attendees']
                ]
            
            # Update the event
            url = f"https://graph.microsoft.com/v1.0/me/events/{event_id}"
            response = requests.patch(url, headers=headers, json=update_data)
            
            if response.status_code == 200:
                updated_event = response.json()
                
                # Return formatted event
                attendees = []
                if updated_event.get('attendees'):
                    attendees = [attendee['emailAddress']['address'] for attendee in updated_event['attendees']]
                
                return {
                    'id': updated_event['id'],
                    'title': updated_event.get('subject', 'No Title'),
                    'description': updated_event.get('body', {}).get('content', ''),
                    'start': updated_event['start']['dateTime'],
                    'end': updated_event['end']['dateTime'],
                    'location': updated_event.get('location', {}).get('displayName', ''),
                    'attendees': attendees
                }
            else:
                raise Exception(f'HTTP {response.status_code}: {response.text}')
                
        except Exception as error:
            raise Exception(f'Failed to update Microsoft Calendar event: {error}')
    
    def delete_event(self, token_file_path: str, event_id: str) -> bool:
        """Delete a calendar event"""
        try:
            token_data = self.load_token(token_file_path)
            headers = {'Authorization': f"Bearer {token_data['access_token']}"}
            
            url = f"https://graph.microsoft.com/v1.0/me/events/{event_id}"
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 204:
                return True
            elif response.status_code == 404:
                # Event already deleted or doesn't exist
                return True
            else:
                raise Exception(f'HTTP {response.status_code}: {response.text}')
                
        except Exception as error:
            if "404" in str(error):
                return True
            raise Exception(f'Failed to delete Microsoft Calendar event: {error}')
    
    def get_event_by_id(self, token_file_path: str, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event by ID"""
        try:
            token_data = self.load_token(token_file_path)
            headers = {'Authorization': f"Bearer {token_data['access_token']}"}
            
            url = f"https://graph.microsoft.com/v1.0/me/events/{event_id}"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                event = response.json()
                
                # Return formatted event
                attendees = []
                if event.get('attendees'):
                    attendees = [attendee['emailAddress']['address'] for attendee in event['attendees']]
                
                return {
                    'id': event['id'],
                    'title': event.get('subject', 'No Title'),
                    'description': event.get('body', {}).get('content', ''),
                    'start': event['start']['dateTime'],
                    'end': event['end']['dateTime'],
                    'location': event.get('location', {}).get('displayName', ''),
                    'attendees': attendees
                }
            elif response.status_code == 404:
                return None
            else:
                raise Exception(f'HTTP {response.status_code}: {response.text}')
                
        except Exception as error:
            if "404" in str(error):
                return None
            raise Exception(f'Failed to get Microsoft Calendar event: {error}')
