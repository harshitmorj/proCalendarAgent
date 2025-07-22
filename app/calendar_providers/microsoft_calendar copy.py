import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import msal
from dotenv import load_dotenv
import requests

load_dotenv()

class MicrosoftCalendarProvider:
    def __init__(self):
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID")
        self.redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI")
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["https://graph.microsoft.com/Calendars.ReadWrite"]
        
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
                print(f'Error fetching events: {response.status_code}')
                return []
        except Exception as error:
            print(f'An error occurred: {error}')
            return []
    
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
                print(f'Error fetching events: {response.status_code}')
                return []
        except Exception as error:
            print(f'An error occurred: {error}')
            return []
