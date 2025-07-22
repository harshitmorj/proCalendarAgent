from fastapi import FastAPI, Request, Depends, HTTPException, status, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .database.database import get_db, create_tables
from .database.models import User
from .auth.dependencies import get_current_user
from .auth.auth import verify_token, get_user
from .routers import auth, calendar, agent
import os
from dotenv import load_dotenv

load_dotenv(override=True)

app = FastAPI(title="Calendar Agent", description="LLM-powered calendar management system")

# Create database tables
create_tables()

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(agent.router)

async def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """Get current user from Authorization header or return None"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        username = verify_token(token)
        if username is None:
            return None
        
        user = get_user(db, username)
        return user
    except:
        return None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page - redirect to login"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard - redirect to add-calendar"""
    return RedirectResponse(url="/add-calendar", status_code=302)

@app.get("/add-calendar", response_class=HTMLResponse)
async def add_calendar_page(request: Request):
    """Add calendar page"""
    return templates.TemplateResponse("add_calendar.html", {
        "request": request,
        "user": None
    })

@app.get("/agent-chat", response_class=HTMLResponse)
async def agent_chat_page(request: Request):
    """Agent chat page"""
    return templates.TemplateResponse("agent_chat.html", {
        "request": request,
        "user": None
    })

@app.get("/calendar-view", response_class=HTMLResponse)
async def calendar_view_page(request: Request):
    """Integrated calendar view page"""
    return templates.TemplateResponse("calendar_view.html", {
        "request": request,
        "user": None
    })

@app.get("/api/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return {"username": current_user.username, "id": current_user.id}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Calendar Agent is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
