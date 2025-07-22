#!/usr/bin/env python3
"""
Setup script for Calendar Agent
Creates database and admin user
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def setup_database_and_user():
    """Set up database and create admin user"""
    try:
        from app.database.database import SessionLocal, create_tables
        from app.database.models import User
        from app.auth.auth import create_user
        
        print("📊 Creating database tables...")
        create_tables()
        print("✅ Database tables created successfully!")
        
        print("👤 Creating admin user...")
        db = SessionLocal()
        try:
            # Check if admin user already exists
            existing_user = db.query(User).filter(User.username == "admin").first()
            if existing_user:
                print("ℹ️  Admin user already exists!")
                print("   Username: admin")
                print("   Password: admin123")
                return True
            
            # Create admin user
            create_user(db, "admin", "admin123")
            print("✅ Admin user created successfully!")
            print("   Username: admin")
            print("   Password: admin123")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error during setup: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔧 Calendar Agent Setup")
    print("=" * 30)
    
    success = setup_database_and_user()
    if success:
        print("\n🎉 Setup completed successfully!")
        print("\n🚀 You can now start the application with:")
        print("   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
        print("\n🌐 Then visit: http://localhost:8000")
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)
