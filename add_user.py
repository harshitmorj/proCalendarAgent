#!/usr/bin/env python3
"""
Add user script for Calendar Agent
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def add_user(username, password):
    """Add a new user to the database"""
    try:
        from app.database.database import SessionLocal
        from app.database.models import User
        from app.auth.auth import create_user
        
        db = SessionLocal()
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                print(f"❌ User '{username}' already exists!")
                return False
            
            # Create new user
            create_user(db, username, password)
            print(f"✅ User '{username}' created successfully!")
            print(f"   Username: {username}")
            print(f"   Password: {password}")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return False

if __name__ == "__main__":
    print("👤 Adding New User")
    print("=" * 20)
    
    success = add_user("harshitmorj", "123456")
    if success:
        print(f"\n🎉 User added successfully!")
        print(f"You can now login with:")
        print(f"   Username: harshitmorj")
        print(f"   Password: 123456")
    else:
        print(f"\n❌ Failed to add user!")
        sys.exit(1)
