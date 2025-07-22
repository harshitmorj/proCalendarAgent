"""
Pydantic schemas for structured outputs and agent state management
"""
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class TaskType(str, Enum):
    """Types of tasks the agent can perform"""
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SEARCH = "search"
    COMPOUND = "compound"
    GENERAL = "general"

class CalendarProvider(str, Enum):
    """Supported calendar providers"""
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    ANY = "any"

class EventData(BaseModel):
    """Event data structure for creating/updating events"""
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    start_datetime: datetime = Field(..., description="Event start date and time")
    end_datetime: datetime = Field(..., description="Event end date and time")
    attendees: Optional[List[str]] = Field(default_factory=list, description="List of attendee emails")
    reminders: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Reminder settings")

class EventFilter(BaseModel):
    """Filter criteria for searching events"""
    title_contains: Optional[str] = Field(None, description="Title contains this text")
    description_contains: Optional[str] = Field(None, description="Description contains this text")
    location_contains: Optional[str] = Field(None, description="Location contains this text")
    attendee_email: Optional[str] = Field(None, description="Event has this attendee")
    start_date: Optional[datetime] = Field(None, description="Events after this date")
    end_date: Optional[datetime] = Field(None, description="Events before this date")
    provider: Optional[CalendarProvider] = Field(None, description="Filter by calendar provider")

class TaskIntent(BaseModel):
    """Parsed intent from user message"""
    task_type: TaskType = Field(..., description="Primary task type")
    confidence: float = Field(..., description="Confidence score (0-1)")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    requires_confirmation: bool = Field(False, description="Whether task requires user confirmation")

class SubTask(BaseModel):
    """Individual sub-task in a compound operation"""
    task_type: TaskType = Field(..., description="Type of sub-task")
    parameters: Dict[str, Any] = Field(..., description="Parameters for this sub-task")
    depends_on: Optional[List[int]] = Field(None, description="Indices of sub-tasks this depends on")
    description: str = Field(..., description="Human-readable description of the sub-task")

class CompoundTask(BaseModel):
    """Compound task with multiple sub-tasks"""
    subtasks: List[SubTask] = Field(..., description="List of sub-tasks to execute")
    description: str = Field(..., description="Overall task description")

class ToolResult(BaseModel):
    """Result from a tool execution"""
    success: bool = Field(..., description="Whether the tool execution was successful")
    data: Optional[Any] = Field(None, description="Result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class AgentResponse(BaseModel):
    """Final response from the agent"""
    message: str = Field(..., description="Response message to user")
    data: Optional[Any] = Field(None, description="Structured data if applicable")
    actions_taken: List[str] = Field(default_factory=list, description="List of actions performed")
    suggestions: Optional[List[str]] = Field(None, description="Follow-up suggestions")

class DateTimeRange(BaseModel):
    """Date and time range specification"""
    start: Optional[datetime] = Field(None, description="Start date and time")
    end: Optional[datetime] = Field(None, description="End date and time")
    description: str = Field(..., description="Human-readable description of the range")

class SearchQuery(BaseModel):
    """Structured search query"""
    text: Optional[str] = Field(None, description="Free text search")
    filters: Optional[EventFilter] = Field(None, description="Specific filters")
    date_range: Optional[DateTimeRange] = Field(None, description="Date range for search")
    limit: Optional[int] = Field(20, description="Maximum number of results")

class EventIdentifier(BaseModel):
    """Identifies a specific event"""
    event_id: Optional[str] = Field(None, description="Specific event ID")
    provider: Optional[CalendarProvider] = Field(None, description="Calendar provider")
    account_email: Optional[str] = Field(None, description="Account email")
    search_criteria: Optional[SearchQuery] = Field(None, description="Search criteria if ID not available")

class CreateEventRequest(BaseModel):
    """Request to create a new event"""
    event_data: EventData = Field(..., description="Event details")
    provider: Optional[CalendarProvider] = Field(default=CalendarProvider.ANY, description="Preferred provider")
    account_email: Optional[str] = Field(None, description="Specific account to create in")

class UpdateEventRequest(BaseModel):
    """Request to update an existing event"""
    event_identifier: EventIdentifier = Field(..., description="How to find the event")
    updates: Dict[str, Any] = Field(..., description="Fields to update")

class DeleteEventRequest(BaseModel):
    """Request to delete an event"""
    event_identifier: EventIdentifier = Field(..., description="How to find the event")
    confirmation: bool = Field(False, description="User confirmation for deletion")

class CalendarOperation(BaseModel):
    """Generic calendar operation"""
    operation_type: Literal["create", "read", "update", "delete", "search"] = Field(
        ..., description="Type of operation"
    )
    parameters: Dict[str, Any] = Field(..., description="Operation parameters")
    target_provider: Optional[CalendarProvider] = Field(None, description="Target provider")
    target_account: Optional[str] = Field(None, description="Target account email")

class IntentExtractionResult(BaseModel):
    """Result of intent extraction from user message"""
    primary_intent: TaskIntent = Field(..., description="Primary task intent")
    secondary_intents: List[TaskIntent] = Field(default_factory=list, description="Additional intents")
    is_compound: bool = Field(False, description="Whether this is a compound task")
    compound_task: Optional[CompoundTask] = Field(None, description="Compound task breakdown")
    extracted_entities: Dict[str, Any] = Field(default_factory=dict, description="All extracted entities")
    confidence_score: float = Field(..., description="Overall confidence in extraction")

class ExecutionPlan(BaseModel):
    """Plan for executing tasks"""
    steps: List[Dict[str, Any]] = Field(..., description="Execution steps")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in seconds")
    requires_confirmation: bool = Field(False, description="Whether confirmation is needed")
    risk_level: Literal["low", "medium", "high"] = Field("low", description="Risk level of operations")

class NodeResult(BaseModel):
    """Result from a graph node execution"""
    node_name: str = Field(..., description="Name of the node that executed")
    success: bool = Field(..., description="Whether execution was successful")
    output: Any = Field(None, description="Node output")
    next_node: Optional[str] = Field(None, description="Suggested next node")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
