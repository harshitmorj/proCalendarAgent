#!/usr/bin/env python3
"""
Calendar Agent Startup Script

This script helps you start the Calendar Agent application.
Make sure to set up your environment variables in .env file before running.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_env_file():
    """Check if .env file exists and has required variables"""
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found!")
        print("Please copy .env.example to .env and fill in your credentials:")
        print("cp .env.example .env")
        return False
    
    required_vars = [
        "SECRET_KEY",
        "GOOGLE_CLIENT_ID", 
        "GOOGLE_CLIENT_SECRET",
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_CLIENT_SECRET", 
        "MICROSOFT_TENANT_ID",
        "OPENAI_API_KEY"
    ]
    
    missing_vars = []
    with open(env_path) as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=your-" in content or f"{var}=" not in content:
                missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing or incomplete environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease update your .env file with actual values.")
        return False
    
    print("✅ Environment variables configured")
    return True

def create_admin_user():
    """Create an admin user for testing"""
    print("\n📝 Creating admin user...")
    print("You can use this user to log in and test the application")
    
    username = input("Enter admin username (default: admin): ").strip() or "admin"
    password = input("Enter admin password (default: admin123): ").strip() or "admin123"
    
    try:
        # Import here to avoid import issues if dependencies aren't installed
        from app.database.database import SessionLocal, create_tables
        from app.database.models import User
        from app.auth.auth import create_user
        
        # Create tables first
        create_tables()
        
        # Create admin user
        db = SessionLocal()
        try:
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                print(f"User '{username}' already exists!")
                return
            
            create_user(db, username, password)
            print(f"✅ Admin user '{username}' created successfully!")
            print(f"   Username: {username}")
            print(f"   Password: {password}")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        print("You can create users manually later using the API")

def main():
    """Main startup function"""
    print("🚀 Calendar Agent Startup")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not Path("app").exists():
        print("❌ Please run this script from the project root directory")
        return 1
    
    # Check environment
    if not check_env_file():
        return 1
    
    # Ask if user wants to create admin user
    create_user = input("\n🤔 Create admin user? (y/N): ").lower().startswith('y')
    if create_user:
        try:
            create_admin_user()
        except ImportError:
            print("❌ Dependencies not installed. Please run: pip install -r requirements.txt")
            return 1
    
    print("\n🌟 Starting Calendar Agent...")
    print("📱 Web interface will be available at: http://localhost:8000")
    print("📚 API documentation will be available at: http://localhost:8000/docs")
    print("🛑 Press Ctrl+C to stop the server")
    print("-" * 40)
    
    try:
        # Start the FastAPI application
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n👋 Calendar Agent stopped")
        return 0
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
