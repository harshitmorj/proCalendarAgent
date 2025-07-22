# Calendar Agent

A powerful LLM-powered calendar management system built with FastAPI, LangGraph, and modern web technologies. This application allows users to connect their Google and Microsoft calendars and interact with them using natural language through an intelligent agent.

## Features

- **Multi-Calendar Support**: Connect both Google Calendar and Microsoft Outlook/Office 365 calendars
- **OAuth Integration**: Secure authentication with Google and Microsoft
- **LLM-Powered Agent**: Natural language interaction using LangGraph and OpenAI
- **Web Interface**: Modern, responsive web interface with three main sections:
  - Calendar Management: Connect and manage calendar accounts
  - AI Assistant: Chat with the intelligent calendar agent
  - Integrated Calendar View: Unified view of all connected calendars
- **User Management**: Admin can create users with username/password authentication
- **LangSmith Integration**: Optional tracing and monitoring of LLM interactions

## Architecture

- **Backend**: FastAPI with SQLAlchemy ORM
- **Database**: SQLite (easily configurable for PostgreSQL/MySQL)
- **LLM Framework**: LangGraph for building the conversational agent
- **Calendar APIs**: Google Calendar API and Microsoft Graph API
- **Authentication**: JWT tokens with OAuth2 for calendar providers
- **Frontend**: HTML/CSS/JavaScript with Bootstrap

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo>
cd proCalendarAgent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the environment template and configure your credentials:

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
# Required API Keys and Secrets
SECRET_KEY=your-secret-key-change-this-in-production
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
MICROSOFT_TENANT_ID=your-microsoft-tenant-id
OPENAI_API_KEY=your-openai-api-key

# Optional: LangSmith for tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=calendar-agent
```

### 4. Get API Credentials

#### Google Calendar API:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials
5. Add `http://localhost:8000/auth/google/callback` to authorized redirect URIs

#### Microsoft Graph API:
1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to Azure Active Directory > App registrations
3. Create a new registration
4. Add `http://localhost:8000/auth/microsoft/callback` to redirect URIs
5. Grant permissions for `Calendars.ReadWrite`

### 5. Start the Application

Use the convenient startup script:

```bash
python start.py
```

Or start manually:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Access the Application

- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Default Admin**: admin / admin123 (if created during startup)

## Usage

### 1. Login
Use the admin credentials to log into the web interface.

### 2. Connect Calendars
- Navigate to the "Add Calendar" tab
- Click "Connect Google" or "Connect Microsoft" 
- Complete the OAuth flow in the popup window
- Your connected accounts will appear in the list

### 3. Chat with the Agent
- Go to the "LLM Agent" tab
- Try commands like:
  - "Show me my next 15 events"
  - "What's my schedule today?"
  - "Tell me about my connected calendars"
  - Ask general questions too!

### 4. View Integrated Calendar
- The "Integrated Calendar" tab shows a unified view
- Events from all connected calendars are displayed together
- Navigate between months to see future events

## Agent Capabilities

The LangGraph-powered agent can:

- **Calendar Operations**:
  - List upcoming events (next 15 events)
  - Show calendar account summaries
  - Understand natural language queries about schedules

- **General Assistance**:
  - Answer general questions
  - Provide helpful information
  - Route calendar-specific queries to appropriate tools

## API Endpoints

### Authentication
- `POST /auth/register` - Create new user (admin)
- `POST /auth/login` - User login

### Calendar Management
- `GET /calendar/accounts` - List connected accounts
- `GET /calendar/connect/{provider}` - Initiate OAuth flow
- `GET /calendar/callback/{provider}` - OAuth callback
- `DELETE /calendar/accounts/{account_id}` - Disconnect account
- `GET /calendar/events` - Get events from all calendars

### Agent Interaction
- `POST /agent/chat` - Send message to agent
- `GET /agent/chat/history/{session_id}` - Get chat history
- `GET /agent/chat/sessions` - List chat sessions

## Development

### Project Structure

```
proCalendarAgent/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── database/              # Database models and config
│   ├── auth/                  # Authentication logic
│   ├── calendar_providers/    # Google & Microsoft integrations
│   ├── langgraph_agent/       # LLM agent implementation
│   ├── routers/               # API routes
│   ├── templates/             # HTML templates
│   └── static/                # CSS/JS files
├── user_data/                 # User-specific token storage
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
└── start.py                  # Startup script
```

### Adding New Features

1. **New Calendar Provider**: 
   - Add provider class in `calendar_providers/`
   - Update routes and UI components

2. **New Agent Tools**:
   - Add functions in `langgraph_agent/tools.py`
   - Update agent routing logic

3. **New API Endpoints**:
   - Add routes in appropriate router file
   - Update main.py to include router

## Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

- Set strong `SECRET_KEY`
- Use production database (PostgreSQL recommended)
- Configure proper OAuth redirect URIs for your domain
- Set up LangSmith for monitoring (optional)

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed: `pip install -r requirements.txt`

2. **OAuth Errors**: 
   - Check redirect URIs in Google/Microsoft console
   - Verify client IDs and secrets in .env

3. **Agent Not Responding**: 
   - Check OpenAI API key
   - Verify LangSmith configuration (if enabled)

4. **Calendar Connection Fails**:
   - Check API credentials
   - Ensure proper scopes are granted
   - Verify token file permissions

### Logs

- FastAPI logs appear in the console
- LangSmith tracing (if enabled) provides detailed agent execution logs
- Calendar API errors are logged to console

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with proper tests
4. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review API documentation at `/docs`
3. Create an issue in the repository
