from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database.database import get_db
from ..database.models import User, CalendarAccount
from ..auth.dependencies import get_current_user
from ..calendar_providers.google_calendar import GoogleCalendarProvider
from ..calendar_providers.microsoft_calendar import MicrosoftCalendarProvider
from ..calendar_providers.integrated_calendar import IntegratedCalendar
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
import uuid
from typing import List, Optional

router = APIRouter(prefix="/calendar", tags=["calendar"])

class CalendarAccountResponse(BaseModel):
    id: int
    provider: str
    account_email: str
    connected_at: str
    
    @classmethod
    def from_db(cls, db_account: CalendarAccount):
        return cls(
            id=db_account.id,
            provider=db_account.provider,
            account_email=db_account.account_email,
            connected_at=db_account.connected_at.isoformat() if db_account.connected_at else ""
        )

@router.get("/accounts", response_model=List[CalendarAccountResponse])
async def get_calendar_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all connected calendar accounts for the current user"""
    accounts = db.query(CalendarAccount).filter(
        CalendarAccount.user_id == current_user.id,
        CalendarAccount.is_active == True
    ).all()
    
    return [CalendarAccountResponse.from_db(account) for account in accounts]

@router.get("/connect/{provider}")
async def connect_calendar(
    provider: str,
    current_user: User = Depends(get_current_user)
):
    """Initiate OAuth flow for calendar provider"""
    if provider not in ["google", "microsoft"]:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    
    # Generate state parameter for OAuth security
    state = f"{current_user.id}:{uuid.uuid4()}"
    
    if provider == "google":
        google_provider = GoogleCalendarProvider()
        auth_url = google_provider.get_authorization_url(state)
    else:  # microsoft
        microsoft_provider = MicrosoftCalendarProvider()
        auth_url = microsoft_provider.get_authorization_url(state)
    
    return {"authorization_url": auth_url}

@router.get("/callback/{provider}")
async def calendar_callback(
    provider: str,
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """Handle OAuth callback from calendar provider"""
    if provider not in ["google", "microsoft"]:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    
    try:
        # Extract user_id from state
        user_id = int(state.split(":")[0])
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Exchange code for token
        if provider == "google":
            google_provider = GoogleCalendarProvider()
            token_data = google_provider.exchange_code_for_token(code, state)
        else:  # microsoft
            microsoft_provider = MicrosoftCalendarProvider()
            token_data = microsoft_provider.exchange_code_for_token(code, state)
        
        # Create user directory if it doesn't exist
        user_dir = f"user_data/user_{user_id}"
        os.makedirs(user_dir, exist_ok=True)
        
        # Save token file
        token_filename = f"{provider}_{uuid.uuid4()}.json"
        token_path = os.path.join(user_dir, token_filename)
        
        if provider == "google":
            google_provider.save_token(token_data, token_path)
        else:
            microsoft_provider.save_token(token_data, token_path)
        
        # Save calendar account to database
        calendar_account = CalendarAccount(
            user_id=user_id,
            provider=provider,
            account_email=token_data["user_email"],
            token_file_path=token_path
        )
        db.add(calendar_account)
        db.commit()
        
        # Redirect back to add-calendar page with success message
        return RedirectResponse(
            url=f"/add-calendar?success=calendar_connected&provider={provider}",
            status_code=302
        )
        
    except Exception as e:
        # Redirect back to add-calendar page with error message
        return RedirectResponse(
            url=f"/add-calendar?error=calendar_connection_failed&message={str(e)}",
            status_code=302
        )

@router.delete("/accounts/{account_id}")
async def disconnect_calendar(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect a calendar account"""
    account = db.query(CalendarAccount).filter(
        CalendarAccount.id == account_id,
        CalendarAccount.user_id == current_user.id
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Calendar account not found")
    
    # Mark as inactive instead of deleting to preserve history
    account.is_active = False
    db.commit()
    
    return {"message": "Calendar disconnected successfully"}

@router.get("/events")
async def get_calendar_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    max_results: int = 10
):
    """Get events from all connected calendars"""
    accounts = db.query(CalendarAccount).filter(
        CalendarAccount.user_id == current_user.id,
        CalendarAccount.is_active == True
    ).all()
    
    if not accounts:
        return {"events": [], "message": "No calendar accounts connected"}
    
    all_events = []
    
    for account in accounts:
        try:
            if account.provider == "google":
                provider = GoogleCalendarProvider()
                events = provider.get_calendar_events(account.token_file_path, max_results)
            elif account.provider == "microsoft":
                provider = MicrosoftCalendarProvider()
                events = provider.get_calendar_events(account.token_file_path, max_results)
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
    
    # Sort events by start time
    all_events.sort(key=lambda x: x['start'])
    
    return {"events": all_events[:max_results]}

@router.get("/events/range")
async def get_calendar_events_range(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 100
):
    """Get events from all connected calendars within a date range"""
    
    # Parse dates or set defaults (past month to next 2 months)
    if start_date:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    else:
        start_dt = datetime.utcnow() - timedelta(days=30)  # Past month
    
    if end_date:
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    else:
        end_dt = datetime.utcnow() + timedelta(days=60)  # Next 2 months
    
    try:
        integrated_calendar = IntegratedCalendar(current_user.id, db)
        events = integrated_calendar.get_all_events(
            start_date=start_dt,
            end_date=end_dt,
            max_results=max_results
        )
        
        return {"events": events, "start_date": start_dt.isoformat(), "end_date": end_dt.isoformat()}
        
    except Exception as e:
        print(f"Error fetching events: {str(e)}")
        return {"events": [], "error": str(e)}

@router.delete("/events/{provider}/{account_email}/{event_id}")
async def delete_calendar_event(
    provider: str,
    account_email: str,
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a specific calendar event"""
    
    try:
        integrated_calendar = IntegratedCalendar(current_user.id, db)
        success = integrated_calendar.delete_event(
            provider=provider,
            account_email=account_email,
            event_id=event_id
        )
        
        if success:
            return {"message": "Event deleted successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to delete event")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting event: {str(e)}")

@router.get("/events/{provider}/{account_email}/{event_id}")
async def get_calendar_event_details(
    provider: str,
    account_email: str,
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific calendar event"""
    
    try:
        integrated_calendar = IntegratedCalendar(current_user.id, db)
        event = integrated_calendar.get_event_by_id(
            provider=provider,
            account_email=account_email,
            event_id=event_id
        )
        
        if event:
            return {"event": event}
        else:
            raise HTTPException(status_code=404, detail="Event not found")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching event: {str(e)}")
