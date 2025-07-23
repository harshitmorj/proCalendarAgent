# proCalendarAgent 🗓️🤖

An intelligent AI-powered calendar assistant that helps users manage and coordinate calendar events across multiple platforms (Google Calendar, Microsoft Outlook) with advanced features like multi-user scheduling and optimal meeting time recommendations.

## 🌟 Features

### Core Calendar Management
- **Multi-Platform Integration**: Connect to Google Calendar and Microsoft Outlook
- **CRUD Operations**: Create, read, update, and delete calendar events
- **Natural Language Processing**: Interact with your calendar using plain English
- **Smart Event Search**: Find events using flexible search criteria

### Advanced Scheduling
- **Multi-User Coordination**: Schedule meetings with multiple participants
- **Optimal Time Finder**: AI-powered suggestions for best meeting times
- **Conflict Detection**: Automatic identification of scheduling conflicts
- **Availability Analysis**: Real-time analysis of participant availability

### Intelligent Agent
- **Intent Recognition**: Understands various calendar-related requests
- **Context Awareness**: Maintains conversation context for better interactions
- **Error Handling**: Graceful handling of ambiguous or invalid requests
- **Flexible Input**: Supports various date/time formats and natural language

## 🏗️ Architecture

### Technology Stack
- **Backend**: FastAPI (Python)
- **AI/ML**: LangChain + LangGraph for agent orchestration
- **Database**: SQLAlchemy with SQLite/PostgreSQL
- **Calendar APIs**: Google Calendar API, Microsoft Graph API
- **Frontend**: HTML/CSS/JavaScript with Jinja2 templates

### Agent Architecture
```
User Input → Router Node → Specialized Nodes → Calendar Providers → Response
              ↓
        ┌─────────────┐
        │ Intent      │
        │ Recognition │
        └─────────────┘
              ↓
    ┌─────────────────────────┐
    │ Specialized Nodes       │
    │ • Search Node          │
    │ • Create Node          │
    │ • Update Node          │
    │ • Delete Node          │
    │ • Schedule Node        │
    │ • General Node         │
    └─────────────────────────┘
              ↓
    ┌─────────────────────────┐
    │ Calendar Providers      │
    │ • Google Calendar      │
    │ • Microsoft Calendar   │
    │ • Integrated Calendar  │
    └─────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Cloud Console account (for Google Calendar)
- Microsoft Azure account (for Outlook integration)

### Installation
1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd proCalendarAgent
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run setup script**
   ```bash
   python setup_agent.py
   ```

4. **Configure calendar credentials**
   - Place `google_calendar_credentials.json` in the `credentials/` folder
   - Configure Microsoft app registration details in environment variables

5. **Start the application**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

6. **Access the web interface**
   Open `http://localhost:8000` in your browser

## 📋 Usage Examples

### Basic Event Management
```
User: "Create a team meeting tomorrow at 2 PM for 1 hour"
Agent: ✅ Event 'team meeting' created on google calendar at 2025-07-24T14:00:00

User: "Show me my meetings this week"
Agent: 📅 Found 3 events:
       1. Team Meeting - 2025-07-24T14:00:00
       2. Client Call - 2025-07-25T10:00:00
       3. Project Review - 2025-07-26T16:00:00
```

### Advanced Scheduling
```
User: "Schedule a 2-hour planning session with john@company.com and jane@company.com next week"
Agent: 🗓️ Meeting: Planning Session
       👥 Attendees: john@company.com, jane@company.com
       ⏱️ Duration: 120 minutes
       
       🎯 Optimal Time Slots:
       1. Tuesday, July 29 at 10:00 AM ✅ Perfect - All attendees available
       2. Wednesday, July 30 at 2:00 PM ⚠️ 2/2 attendees available
       3. Thursday, July 31 at 9:00 AM ✅ Perfect - All attendees available
```

### Event Updates and Deletions
```
User: "Move the team meeting to 3 PM"
Agent: ✅ Updated 'Team Meeting' - changed start_time to '2025-07-24T15:00:00'

User: "Cancel the client call on Friday"
Agent: ⚠️ Are you sure you want to delete 'Client Call' on 2025-07-25T10:00:00? 
       Please confirm your deletion request.
```

## 🧪 Testing

### Run Comprehensive Tests
```bash
python test_complete_agent.py
```

### Test Individual Components
```bash
# Test calendar integration
python test_integrated_calendar_script.py

# Test agent functionality
python test_enhanced_agent.py

# Test multi-calendar support
python test_multi_calendar.py
```

## 🔧 Configuration

### Environment Variables
Create a `.env` file with:
```env
DATABASE_URL=sqlite:///./calendar_agent.db
LANGCHAIN_API_KEY=your_langchain_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=proCalendarAgent

# Google Calendar
GOOGLE_CALENDAR_CREDENTIALS_PATH=credentials/google_calendar_credentials.json

# Microsoft Graph API
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret
MICROSOFT_TENANT_ID=your_tenant_id
```

### Calendar Provider Setup

#### Google Calendar
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable Google Calendar API
4. Create credentials (OAuth 2.0)
5. Download and place in `credentials/google_calendar_credentials.json`

#### Microsoft Outlook
1. Go to [Azure Portal](https://portal.azure.com)
2. Register a new application
3. Configure API permissions for Microsoft Graph
4. Note down Client ID, Client Secret, and Tenant ID

## 📁 Project Structure

```
proCalendarAgent/
├── app/
│   ├── auth/                    # Authentication & authorization
│   ├── calendar_providers/      # Calendar API integrations
│   ├── database/               # Database models & operations
│   ├── langgraph_agent/        # AI agent implementation
│   │   ├── graph/              # LangGraph workflow definition
│   │   ├── nodes/              # Agent node implementations
│   │   ├── schemas/            # Pydantic schemas
│   │   └── knowledge/          # Agent knowledge base
│   ├── routers/                # FastAPI route handlers
│   ├── static/                 # Static web assets
│   └── templates/              # HTML templates
├── credentials/                # API credentials
├── user_data/                  # User-specific data storage
├── user_knowledge/             # User knowledge graphs
├── requirements.txt            # Python dependencies
├── setup_agent.py             # Setup script
└── test_complete_agent.py      # Comprehensive test suite
```

## 🤖 Agent Capabilities

### Intent Recognition
The agent can understand and route various types of requests:
- **Search**: "Show my meetings", "Find events with John"
- **Create**: "Create a meeting", "Schedule lunch tomorrow"
- **Update**: "Move the meeting to 3 PM", "Change location to Room B"
- **Delete**: "Cancel the call", "Remove meeting on Friday"
- **Schedule**: "Find time for a meeting with team", "Best time for all attendees"
- **General**: Non-calendar queries and casual conversation

### Smart Scheduling Features
- **Conflict Detection**: Identifies overlapping meetings
- **Optimal Time Suggestions**: Ranks time slots by participant availability
- **Multi-Calendar Support**: Searches across all connected calendars
- **Flexible Date Parsing**: Understands "tomorrow", "next week", specific dates
- **Duration Intelligence**: Automatically calculates end times

## 🔐 Security & Privacy

- **OAuth 2.0**: Secure authentication with calendar providers
- **Token Management**: Encrypted storage of access tokens
- **User Isolation**: Data segregation between users
- **Permission Control**: Granular calendar access permissions
- **Data Encryption**: Sensitive data encrypted at rest

## 🚀 Deployment

### Development
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UnicornWorker --bind 0.0.0.0:8000
```

### Docker (Optional)
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📈 Performance & Scalability

- **Async Operations**: Non-blocking I/O for calendar API calls
- **Database Optimization**: Indexed queries and connection pooling
- **Caching**: Intelligent caching of calendar data
- **Rate Limiting**: Respects API rate limits
- **Horizontal Scaling**: Stateless design supports load balancing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📝 Design Decisions & Trade-offs

### Architecture Choices
- **LangGraph over Custom Logic**: Provides better intent routing and conversation flow
- **Multi-Provider Design**: Supports multiple calendar platforms with unified interface
- **Database Storage**: Local storage for user data and calendar metadata
- **FastAPI Framework**: Modern, fast, and well-documented Python web framework

### Trade-offs
- **Complexity vs Flexibility**: More complex architecture enables advanced features
- **Local vs Cloud**: Local deployment for privacy vs cloud for scalability
- **Real-time vs Cached**: Balance between fresh data and performance
- **AI Processing**: LLM calls add latency but enable natural language interaction

## 🐛 Troubleshooting

### Common Issues
1. **Calendar API Authentication**: Ensure credentials are properly configured
2. **Database Connection**: Check DATABASE_URL environment variable
3. **LLM Integration**: Verify LangChain API key is set
4. **Port Conflicts**: Change port if 8000 is occupied

### Debug Mode
Set `DEBUG=True` in environment variables for detailed logging.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- LangChain community for the excellent agent framework
- Google Calendar API documentation
- Microsoft Graph API team
- FastAPI creators for the amazing web framework

---

**Built with ❤️ for better calendar management through AI**
