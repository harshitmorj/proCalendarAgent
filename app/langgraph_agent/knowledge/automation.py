import os
import subprocess
from app.database.database import SessionLocal
from app.database.models import User

def main():
    db_session = SessionLocal()
    user_ids = [user.id for user in db_session.query(User).all()]
    print(f"Found user IDs: {user_ids}")

    for user_id in user_ids:
        print(f"Processing user {user_id}...")
        # Run structured analysis
        subprocess.run([
            "python3", "app/langgraph_agent/knowledge/structured_analysis.py", str(user_id)
        ], check=False)
        # Run unstructured analysis
        subprocess.run([
            "python3", "app/langgraph_agent/knowledge/unstructured_analysis.py", str(user_id)
        ], check=False)

if __name__ == "__main__":
    main()
