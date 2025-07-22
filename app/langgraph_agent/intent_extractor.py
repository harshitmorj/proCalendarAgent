"""
LLM-powered intent extraction and task routing for calendar operations
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import re
from dateutil import parser as date_parser
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import ValidationError

from .schemas import (
    TaskType, IntentExtractionResult, TaskIntent, CompoundTask, SubTask,
    SearchQuery, EventFilter, EventData, CreateEventRequest, 
    UpdateEventRequest, DeleteEventRequest, EventIdentifier,
    CalendarProvider, DateTimeRange
)
import os
from dotenv import load_dotenv

load_dotenv()

class LLMIntentExtractor:
    """LLM-powered intent extraction and task planning"""
    
    def __init__(self):
        self.openai_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.gemini_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.1,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
    
    def extract_intent(self, user_message: str, context: Dict[str, Any] = None) -> IntentExtractionResult:
        """Extract structured intent from user message"""
        
        intent_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_intent_system_prompt()),
            ("user", "Message: {message}\nContext: {context}\n\nAnalyze this message and extract the intent:")
        ])
        
        try:
            # Try OpenAI first
            chain = intent_prompt | self.openai_llm | JsonOutputParser()
            result = chain.invoke({
                "message": user_message,
                "context": json.dumps(context or {})
            })
        except Exception:
            try:
                # Fallback to Gemini
                chain = intent_prompt | self.gemini_llm | JsonOutputParser()
                result = chain.invoke({
                    "message": user_message,
                    "context": json.dumps(context or {})
                })
            except Exception as e:
                # Fallback to rule-based extraction
                return self._fallback_intent_extraction(user_message)
        
        try:
            return self._parse_intent_result(result)
        except (ValidationError, KeyError) as e:
            print(f"Intent parsing error: {e}")
            return self._fallback_intent_extraction(user_message)
    
    def plan_compound_task(self, intent_result: IntentExtractionResult) -> CompoundTask:
        """Plan execution steps for compound tasks"""
        
        planning_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_planning_system_prompt()),
            ("user", "Intent: {intent}\nCreate an execution plan:")
        ])
        
        try:
            chain = planning_prompt | self.openai_llm | JsonOutputParser()
            result = chain.invoke({
                "intent": intent_result.model_dump_json()
            })
            
            return CompoundTask(**result)
        except Exception:
            # Fallback to simple task breakdown
            return self._fallback_task_planning(intent_result)
    
    def _get_intent_system_prompt(self) -> str:
        return """You are an expert at extracting structured intent from natural language calendar requests.

Analyze the user's message and extract:
1. Primary task type (read, create, update, delete, search, compound, general)
2. Entities mentioned (dates, times, event titles, locations, people)
3. Parameters for the task
4. Whether it's a compound task requiring multiple operations

Calendar Task Types:
- READ: Getting/viewing events, schedules, busy times
- CREATE: Creating new events, meetings, appointments
- UPDATE: Modifying existing events (time, title, attendees, etc.)
- DELETE: Removing events
- SEARCH: Finding specific events based on criteria
- COMPOUND: Multiple operations in sequence (e.g., "find my meeting with John and reschedule it")
- GENERAL: Non-calendar related queries

Entity Extraction:
- Dates: Extract relative (today, tomorrow, next week) and absolute dates
- Times: Extract start/end times, durations
- People: Names, email addresses
- Locations: Meeting rooms, addresses, online platforms
- Event details: Titles, descriptions, types

Return JSON with this structure:
{
    "primary_intent": {
        "task_type": "read|create|update|delete|search|compound|general",
        "confidence": 0.0-1.0,
        "entities": {},
        "parameters": {},
        "requires_confirmation": false
    },
    "secondary_intents": [],
    "is_compound": false,
    "extracted_entities": {},
    "confidence_score": 0.0-1.0
}

Examples:

"Show me my meetings tomorrow"
→ task_type: "read", entities: {"date": "tomorrow"}, confidence: 0.95

"Create a team meeting next Tuesday at 2pm"
→ task_type: "create", entities: {"date": "next Tuesday", "time": "2pm", "title": "team meeting"}, confidence: 0.9

"Find my call with Sarah and move it to 3pm"
→ task_type: "compound", is_compound: true, entities: {"person": "Sarah", "new_time": "3pm"}, confidence: 0.85

"Cancel all meetings on Friday"
→ task_type: "delete", entities: {"date": "Friday", "scope": "all"}, requires_confirmation: true"""

    def _get_planning_system_prompt(self) -> str:
        return """You are an expert task planner for calendar operations.

Given an extracted intent, create a detailed execution plan with sub-tasks.

For compound tasks, break them down into sequential steps:
1. SEARCH operations to find events
2. READ operations to get details
3. UPDATE/DELETE operations to modify
4. CREATE operations for new events

Each sub-task should specify:
- task_type: The operation type
- parameters: Required parameters
- depends_on: Which previous tasks this depends on (by index)
- description: Human-readable description

Return JSON with this structure:
{
    "subtasks": [
        {
            "task_type": "search",
            "parameters": {},
            "depends_on": null,
            "description": "Find events matching criteria"
        }
    ],
    "description": "Overall task description"
}

Example: "Find my meeting with John tomorrow and cancel it"
→ 
{
    "subtasks": [
        {
            "task_type": "search",
            "parameters": {"query": "John", "date": "tomorrow"},
            "depends_on": null,
            "description": "Search for meetings with John tomorrow"
        },
        {
            "task_type": "delete",
            "parameters": {"confirmation_required": true},
            "depends_on": [0],
            "description": "Cancel the found meeting"
        }
    ],
    "description": "Find and cancel meeting with John tomorrow"
}"""

    def _parse_intent_result(self, result: Dict[str, Any]) -> IntentExtractionResult:
        """Parse LLM result into structured intent"""
        primary_intent = TaskIntent(
            task_type=TaskType(result["primary_intent"]["task_type"]),
            confidence=result["primary_intent"]["confidence"],
            entities=result["primary_intent"].get("entities", {}),
            parameters=result["primary_intent"].get("parameters", {}),
            requires_confirmation=result["primary_intent"].get("requires_confirmation", False)
        )
        
        secondary_intents = []
        for intent_data in result.get("secondary_intents", []):
            secondary_intents.append(TaskIntent(
                task_type=TaskType(intent_data["task_type"]),
                confidence=intent_data["confidence"],
                entities=intent_data.get("entities", {}),
                parameters=intent_data.get("parameters", {}),
                requires_confirmation=intent_data.get("requires_confirmation", False)
            ))
        
        compound_task = None
        if result.get("is_compound") and "compound_task" in result:
            compound_data = result["compound_task"]
            subtasks = []
            for subtask_data in compound_data["subtasks"]:
                subtasks.append(SubTask(
                    task_type=TaskType(subtask_data["task_type"]),
                    parameters=subtask_data["parameters"],
                    depends_on=subtask_data.get("depends_on"),
                    description=subtask_data["description"]
                ))
            compound_task = CompoundTask(
                subtasks=subtasks,
                description=compound_data["description"]
            )
        
        return IntentExtractionResult(
            primary_intent=primary_intent,
            secondary_intents=secondary_intents,
            is_compound=result.get("is_compound", False),
            compound_task=compound_task,
            extracted_entities=result.get("extracted_entities", {}),
            confidence_score=result.get("confidence_score", 0.0)
        )
    
    def _fallback_intent_extraction(self, message: str) -> IntentExtractionResult:
        """Rule-based fallback for intent extraction"""
        message_lower = message.lower()
        
        # Determine task type based on keywords
        if any(word in message_lower for word in ["show", "list", "view", "get", "display", "what's"]):
            task_type = TaskType.READ
        elif any(word in message_lower for word in ["create", "add", "schedule", "book", "new"]):
            task_type = TaskType.CREATE
        elif any(word in message_lower for word in ["update", "change", "modify", "edit", "reschedule"]):
            task_type = TaskType.UPDATE
        elif any(word in message_lower for word in ["delete", "remove", "cancel"]):
            task_type = TaskType.DELETE
        elif any(word in message_lower for word in ["find", "search", "look for"]):
            task_type = TaskType.SEARCH
        else:
            task_type = TaskType.GENERAL
        
        # Extract basic entities
        entities = {}
        
        # Date extraction
        date_patterns = [
            r"today", r"tomorrow", r"yesterday",
            r"next\s+week", r"this\s+week", r"next\s+month",
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday",
            r"\d{1,2}/\d{1,2}/\d{2,4}", r"\d{4}-\d{2}-\d{2}"
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, message_lower)
            if matches:
                entities["dates"] = matches
                break
        
        # Time extraction
        time_patterns = [
            r"\d{1,2}:\d{2}\s*(?:am|pm)?",
            r"\d{1,2}\s*(?:am|pm)",
            r"noon", r"midnight"
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, message_lower)
            if matches:
                entities["times"] = matches
                break
        
        # Check for compound tasks
        is_compound = any(word in message_lower for word in [
            "and then", "after that", "also", "then",
            "find and", "search and", "get and"
        ])
        
        primary_intent = TaskIntent(
            task_type=task_type,
            confidence=0.7,  # Lower confidence for rule-based
            entities=entities,
            parameters={},
            requires_confirmation="delete" in message_lower or "cancel" in message_lower
        )
        
        return IntentExtractionResult(
            primary_intent=primary_intent,
            secondary_intents=[],
            is_compound=is_compound,
            compound_task=None,
            extracted_entities=entities,
            confidence_score=0.7
        )
    
    def _fallback_task_planning(self, intent_result: IntentExtractionResult) -> CompoundTask:
        """Simple fallback task planning"""
        subtasks = []
        
        if intent_result.is_compound:
            # Create basic compound task
            if intent_result.primary_intent.task_type in [TaskType.UPDATE, TaskType.DELETE]:
                # First search, then act
                subtasks.append(SubTask(
                    task_type=TaskType.SEARCH,
                    parameters={"query": ""},
                    depends_on=None,
                    description="Find the event to modify"
                ))
                subtasks.append(SubTask(
                    task_type=intent_result.primary_intent.task_type,
                    parameters=intent_result.primary_intent.parameters,
                    depends_on=[0],
                    description=f"{intent_result.primary_intent.task_type.value} the found event"
                ))
        else:
            # Single task
            subtasks.append(SubTask(
                task_type=intent_result.primary_intent.task_type,
                parameters=intent_result.primary_intent.parameters,
                depends_on=None,
                description=f"Execute {intent_result.primary_intent.task_type.value} operation"
            ))
        
        return CompoundTask(
            subtasks=subtasks,
            description="Generated task plan"
        )
