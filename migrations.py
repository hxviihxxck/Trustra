from app import app, db
from sqlalchemy import Column, Boolean
import sys

def run_migrations():
    """Run database migrations to add new columns"""
    with app.app_context():
        try:
            # Check if is_admin column exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            user_columns = [col['name'] for col in inspector.get_columns('user')]
            
            # Add is_admin column if it doesn't exist
            if 'is_admin' not in user_columns:
                print("Adding is_admin column to user table...")
                # Use direct SQL for the migration
                from sqlalchemy import text
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN is_admin BOOLEAN DEFAULT FALSE'))
                db.session.commit()
                print("is_admin column added successfully")
            else:
                print("is_admin column already exists")
                
            # Check for ChatMessage table
            table_names = inspector.get_table_names()
            if 'chat_message' not in table_names:
                print("Creating chat_message table...")
                from chat import ChatMessage
                db.create_all()
                print("chat_message table created successfully")
            else:
                print("chat_message table already exists")
                
            return True
            
        except Exception as e:
            print(f"Error running migrations: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    if run_migrations():
        print("Migrations completed successfully")
        sys.exit(0)
    else:
        print("Migrations failed")
        sys.exit(1)