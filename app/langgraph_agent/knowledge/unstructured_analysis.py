import os
import sys
import json
from datetime import datetime, timedelta
from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.database.database import SessionLocal
import chromadb
from chromadb.config import Settings
import openai
from collections import defaultdict
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv(override=True)

# Usage: python unstructured_analysis.py <user_id>
USER_ID = sys.argv[1] if len(sys.argv) > 1 else "1"
OUTPUT_DIR = f"user_knowledge/user_{USER_ID}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load events
db_session = SessionLocal()
calendar_agent = IntegratedCalendar(
    user_id=int(USER_ID), db_session=db_session)
events = calendar_agent.get_all_events(
    start_date=None, end_date=None, max_results=2000)

# Prepare ChromaDB client
chroma_client = chromadb.Client(Settings(
    persist_directory=OUTPUT_DIR
))
collection = chroma_client.get_or_create_collection(name="calendar_events")

# Prepare OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

meta_list = []


def clean_metadata(metadata: dict):
    cleaned = {}
    for k, v in metadata.items():
        if isinstance(v, (str, int, float, bool)):
            cleaned[k] = v
        elif v is None:
            cleaned[k] = "unknown"
        else:
            cleaned[k] = str(v)
    return cleaned


def create_semantic_text(event: dict) -> str:
    """
    Create semantic text in the format: {title} on {date} with {attendees}
    """
    title = event.get('title', 'No Title')
    attendees = event.get('attendees', [])
    attendee_str = ', '.join(attendees) if attendees else 'solo'
    location = event.get('location', '')
    location_desc = f"at {location}" if location else ""
    start = event.get('start')
    end = event.get('end')
    
    try:
        start_dt = datetime.fromisoformat(
            start.replace('Z', '+00:00')) if start else None
        end_dt = datetime.fromisoformat(
            end.replace('Z', '+00:00')) if end else None
    except Exception:
        start_dt = None
        end_dt = None
    
    day_str = start_dt.strftime('%A, %d %b %Y') if start_dt else "Unknown day"
    time_str = start_dt.strftime('%H:%M') if start_dt else "Unknown time"
    duration_min = int((end_dt - start_dt).total_seconds() /
                       60) if start_dt and end_dt else "Unknown duration"
    recurrence = 'recurring' if event.get('recurrence') else 'ad-hoc'
    organizer = event.get('organizer', '')
    calendar_id = event.get('calendar_id', '')
    provider = event.get('provider', '')
    rsvp = event.get('rsvp_status', '')
    
    # Primary semantic format: {title} on {date} with {attendees}
    semantic_text = f"{title} on {day_str} with {attendee_str}"
    
    # Enhanced context for better search
    full_text = f"{semantic_text} {location_desc}, scheduled at {time_str} for {duration_min} minutes ({recurrence}). Organizer: {organizer}. RSVP: {rsvp}. Calendar: {calendar_id} ({provider})"
    
    return full_text


for idx, event in tqdm(enumerate(events), total=len(events), desc="Processing events"):
    # Create semantic text for embedding
    text = create_semantic_text(event)

    # Get embedding from OpenAI (openai>=1.0.0)
    try:
        response = openai.embeddings.create(
            input=[text],
            model="text-embedding-ada-002"
        )
        embedding = response.data[0].embedding
    except Exception as e:
        print(f"Embedding error for event {idx}: {e}")
        embedding = None

    # Prepare metadata for storage
    title = event.get('title', 'No Title')
    attendees = event.get('attendees', [])
    start = event.get('start')
    end = event.get('end')
    
    try:
        start_dt = datetime.fromisoformat(
            start.replace('Z', '+00:00')) if start else None
        end_dt = datetime.fromisoformat(
            end.replace('Z', '+00:00')) if end else None
        duration_min = int((end_dt - start_dt).total_seconds() /
                           60) if start_dt and end_dt else "Unknown duration"
    except Exception:
        duration_min = "Unknown duration"
    
    # Store in ChromaDB
    raw_metadata = {
        "event_id": event.get('id'),
        "title": title,
        "attendees": ', '.join(attendees) if attendees else None,
        "location": event.get('location', ''),
        "start": start,
        "end": end,
        "duration_min": duration_min,
        "recurrence": 'recurring' if event.get('recurrence') else 'ad-hoc',
        "organizer": event.get('organizer', ''),
        "calendar_id": event.get('calendar_id', ''),
        "provider": event.get('provider', ''),
        "rsvp_status": event.get('rsvp_status', ''),
        "embedding_text": text
    }
    metadata = clean_metadata(raw_metadata)

    meta_list.append(metadata)
    if embedding:
        collection.add(
            ids=[str(event.get('id', idx))],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[text]
        )

# Save metadata for all events
with open(os.path.join(OUTPUT_DIR, "unstructured_meta.json"), "w") as f:
    json.dump(meta_list, f, indent=2)

print(f"✅ Processed {len(events)} events for user {USER_ID}")
print(f"📁 Data saved to: {OUTPUT_DIR}")
print(f"🔍 Semantic search now available for user {USER_ID}")

# Close database session
db_session.close()
