import os
import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from urllib.parse import urlparse
from app.calendar_providers.integrated_calendar import IntegratedCalendar
from app.database.database import SessionLocal

# Usage: python structured_analysis.py <user_id>
import sys

USER_ID = sys.argv[1] if len(sys.argv) > 1 else "user_1"
OUTPUT_FILE = f"user_knowledge/user_{USER_ID}/structured.json"

# Date range: last 1 year
TZ_OFFSET = timedelta(hours=5, minutes=30)
now = datetime.utcnow() + TZ_OFFSET
start_date = now - timedelta(days=365)
end_date = now

# Get DB session
db_session = SessionLocal()
calendar_agent = IntegratedCalendar(user_id=int(USER_ID), db_session=db_session)

# Only use 'primary' calendar for each account
events = calendar_agent.get_all_events(start_date=start_date, end_date=end_date, max_results=2000)

# 1. Time segmentation
hourly_slots = defaultdict(int)
working_hour_slots = defaultdict(int)
weekday_slots = defaultdict(int)

# 2. Location frequency
location_counter = Counter()
location_domains = Counter()

# 3. Contacts
contact_counter = Counter()
day_contacts = defaultdict(Counter)

# 4. Day-wise meeting analysis
day_meeting_counter = Counter()

# 5. Additional
rsvp_counter = Counter()
organizer_counter = Counter()
duration_list = []
meeting_type_counter = Counter()

from dateutil import parser as dtparser

# For solo/group meeting analysis
solo_meeting_count = 0
group_meeting_count = 0

# For earliest/latest meeting
meeting_times = []

# For break analysis
workday_gaps = defaultdict(list)  # day -> list of gaps in minutes

# For frequent event titles
title_counter = Counter()

for event in events:
    # Parse start/end time in UTC+5:30, handle Z and offset
    try:
        start_dt = dtparser.isoparse(event['start'])
        end_dt = dtparser.isoparse(event['end'])
        # Convert to UTC+5:30
        start_dt = start_dt.astimezone() + TZ_OFFSET if start_dt.tzinfo is None else start_dt.astimezone()
        end_dt = end_dt.astimezone() + TZ_OFFSET if end_dt.tzinfo is None else end_dt.astimezone()
    except Exception:
        continue
    duration = (end_dt - start_dt).total_seconds() / 60  # minutes
    duration_list.append(duration)
    meeting_times.append(start_dt)
    day = start_dt.strftime('%A')
    hour = start_dt.hour
    slot_key = f"{day} {hour:02d}:00"
    hourly_slots[slot_key] += 1
    if day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'] and 9 <= hour < 18:
        working_hour_slots[slot_key] += 1
        # For break analysis, store meeting times for workdays
        workday_gaps[day].append((start_dt, end_dt))
    weekday_slots[day] += 1
    day_meeting_counter[day] += 1
    # Location
    location = event.get('location', '')
    if location:
        location_counter[location] += 1
        if location.startswith('http'):
            domain = urlparse(location).netloc
            location_domains[domain] += 1
    # Contacts
    attendees = event.get('attendees', [])
    for contact in attendees:
        contact_counter[contact] += 1
        day_contacts[day][contact] += 1
    # Solo/group meeting analysis
    if not attendees:
        solo_meeting_count += 1
    else:
        group_meeting_count += 1
    # RSVP status
    for attendee in attendees:
        pass  # Extend if RSVP info is present
    # Organizer
    organizer = event.get('organizer', '')
    if organizer:
        organizer_counter[organizer] += 1
    # Meeting type
    if event.get('recurrence'):
        meeting_type_counter['recurring'] += 1
    else:
        meeting_type_counter['ad-hoc'] += 1
    # Frequent event titles
    title = event.get('title', '')
    if title:
        title_counter[title] += 1

# Break analysis: longest gap in a workday
longest_gap_minutes = 0
for day, meetings in workday_gaps.items():
    # Sort meetings by start time
    meetings_sorted = sorted(meetings, key=lambda x: x[0])
    for i in range(1, len(meetings_sorted)):
        prev_end = meetings_sorted[i-1][1]
        curr_start = meetings_sorted[i][0]
        gap = (curr_start - prev_end).total_seconds() / 60
        if gap > longest_gap_minutes:
            longest_gap_minutes = gap

# Busiest/least busy slots
busiest_slots = dict(sorted(hourly_slots.items(), key=lambda x: x[1], reverse=True)[:5])
least_busy_working_slots = dict(sorted(working_hour_slots.items(), key=lambda x: x[1])[:5])

# Average duration
avg_duration = sum(duration_list) / len(duration_list) if duration_list else 0


def sort_dict_desc(d):
    return dict(sorted(d.items(), key=lambda x: x[1], reverse=True))

def sort_nested_dict_desc(d):
    return {k: sort_dict_desc(v) for k, v in d.items()}

result = {
    "hourly_slots": sort_dict_desc(hourly_slots),
    "working_hour_slots": sort_dict_desc(working_hour_slots),
    "weekday_slots": sort_dict_desc(weekday_slots),
    "busiest_slot": busiest_slots,
    "least_busy_working_slot": least_busy_working_slots,
    "location_frequency": sort_dict_desc(location_counter),
    "location_domains": sort_dict_desc(location_domains),
    "contacts": sort_dict_desc(contact_counter),
    "day_contacts": sort_nested_dict_desc(day_contacts),
    "day_meeting_counter": sort_dict_desc(day_meeting_counter),
    "avg_meeting_duration_min": avg_duration,
    "meeting_type_counter": sort_dict_desc(meeting_type_counter),
    "organizer_counter": sort_dict_desc(organizer_counter),
    "solo_meeting_count": solo_meeting_count,
    "group_meeting_count": group_meeting_count,
    "longest_workday_gap_min": longest_gap_minutes,
    "frequent_event_titles": sort_dict_desc(title_counter),
    # RSVP status, extend if available
}

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(result, f, indent=2)
