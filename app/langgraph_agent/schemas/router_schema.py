from enum import Enum
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class CalendarIntent(str, Enum):
    SEARCH = "search"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SCHEDULE = "schedule"  # For multi-user meeting scheduling
    RSVP = "rsvp"  # For checking attendee responses
    COMPOUND = "compound"
    CLARIFY = "clarify"
    KNOWLEDGE_ANALYSIS = "knowledge_analysis"  # For setting up semantic search
    GENERAL = "general"

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_SEARCH = "waiting_search"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"

class SubTask(BaseModel):
    id: str
    intent: CalendarIntent
    description: str
    status: TaskStatus = TaskStatus.PENDING
    parameters: Optional[Dict[str, Any]] = None
    search_results: Optional[List[Dict[str, Any]]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    dependencies: Optional[List[str]] = None  # List of subtask IDs this depends on

class CompoundSubtask(BaseModel):
    intent: CalendarIntent
    description: Optional[str]

class RouterOutput(BaseModel):
    intent: CalendarIntent
    reason: Optional[str]
    action: Optional[str] = None  # Specific action instructions for tool nodes
    subtasks: Optional[List[CompoundSubtask]] = None  # Only for compound intent
    confidence: Optional[float] = None
    needs_clarification: Optional[bool] = False

class HumanFeedback(BaseModel):
    feedback_type: str  # "confirmation", "selection", "clarification"
    user_input: str
    options: Optional[List[Dict[str, Any]]] = None
    question: str

class SearchResult(BaseModel):
    event_id: str
    title: str
    description: Optional[str]
    start_time: str
    end_time: str
    provider: str
    account_email: str
    location: Optional[str] = None
    attendees: Optional[List[str]] = None

class TaskContext(BaseModel):
    original_message: str
    user_id: int
    current_task: Optional[SubTask] = None
    subtasks: List[SubTask] = []
    search_results: List[SearchResult] = []
    human_feedback: Optional[HumanFeedback] = None
    requires_confirmation: bool = False
    confirmation_message: Optional[str] = None
