from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import enum
from dotenv import load_dotenv

load_dotenv()

# RSVP Status Enum
class RSVPStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    NO_RESPONSE = "no_response"

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    calendar_accounts = relationship("CalendarAccount", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")

class CalendarAccount(Base):
    __tablename__ = "calendar_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False)  # 'google' or 'microsoft'
    account_email = Column(String, nullable=False)
    token_file_path = Column(String, nullable=False)  # Path to stored token file
    is_active = Column(Boolean, default=True)
    connected_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="calendar_accounts")
    calendar_events = relationship("CalendarEvent", back_populates="calendar_account")

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    
    id = Column(Integer, primary_key=True, index=True)
    calendar_account_id = Column(Integer, ForeignKey("calendar_accounts.id"), nullable=False)
    event_id = Column(String, nullable=False)  # Provider's event ID
    title = Column(String, nullable=False)
    description = Column(Text)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    location = Column(String)
    attendees = Column(Text)  # JSON string of attendees
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    calendar_account = relationship("CalendarAccount", back_populates="calendar_events")
    event_attendees = relationship("EventAttendee", back_populates="calendar_event")
    
    # RSVP utility methods
    def get_attendees_by_status(self, status: RSVPStatus):
        """Get all attendees with a specific RSVP status"""
        return [attendee for attendee in self.event_attendees if attendee.rsvp_status == status]
    
    def get_attending_count(self):
        """Get count of attendees who accepted"""
        return len(self.get_attendees_by_status(RSVPStatus.ACCEPTED))
    
    def get_declined_count(self):
        """Get count of attendees who declined"""
        return len(self.get_attendees_by_status(RSVPStatus.DECLINED))
    
    def get_pending_count(self):
        """Get count of attendees who haven't responded"""
        return len([a for a in self.event_attendees 
                   if a.rsvp_status in [RSVPStatus.PENDING, RSVPStatus.NO_RESPONSE]])
    
    def get_tentative_count(self):
        """Get count of attendees who marked tentative"""
        return len(self.get_attendees_by_status(RSVPStatus.TENTATIVE))
    
    def get_rsvp_summary(self):
        """Get a summary of all RSVP statuses"""
        return {
            "attending": self.get_attending_count(),
            "declined": self.get_declined_count(), 
            "tentative": self.get_tentative_count(),
            "pending": self.get_pending_count(),
            "total_invited": len(self.event_attendees)
        }
    
    def get_attendee_names_by_status(self, status: RSVPStatus):
        """Get names/emails of attendees with specific status"""
        attendees = self.get_attendees_by_status(status)
        return [(a.attendee_name or a.attendee_email, a.attendee_email) for a in attendees]

class EventAttendee(Base):
    __tablename__ = "event_attendees"
    
    id = Column(Integer, primary_key=True, index=True)
    calendar_event_id = Column(Integer, ForeignKey("calendar_events.id"), nullable=False)
    attendee_email = Column(String, nullable=False)
    attendee_name = Column(String)
    rsvp_status = Column(Enum(RSVPStatus), default=RSVPStatus.NO_RESPONSE)
    is_organizer = Column(Boolean, default=False)
    is_optional = Column(Boolean, default=False)
    response_datetime = Column(DateTime)  # When they responded
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    calendar_event = relationship("CalendarEvent", back_populates="event_attendees")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    chat_messages = relationship("ChatMessage", back_populates="chat_session")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    chat_session = relationship("ChatSession", back_populates="chat_messages")
