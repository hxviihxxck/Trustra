#!/usr/bin/env python3
import os
import sys
from app import app, db
from models import User
from datetime import datetime, timedelta

def make_admin(email):
    """Make a user an admin by email address"""
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"User with email {email} not found")
            return False
        
        user.is_admin = True
        db.session.commit()
        print(f"User {user.username} ({user.email}) is now an admin")
        return True

def upgrade_to_premium(email):
    """Upgrade a user to premium status by email address"""
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"No user found with email: {email}")
            return False
        
        # Set premium status
        user.is_premium = True
        user.subscription_status = 'active'
        user.subscription_end_date = datetime.utcnow() + timedelta(days=365)  # Set to expire in 1 year
        
        # Set a placeholder subscription ID
        if not user.subscription_id:
            user.subscription_id = f"demo_sub_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        db.session.commit()
        print(f"User {email} upgraded to premium status until {user.subscription_end_date}")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python admin_commands.py [admin|premium] <user_email>")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    email = sys.argv[2]
    
    if command == "admin":
        if make_admin(email):
            sys.exit(0)
        else:
            sys.exit(1)
    elif command == "premium":
        if upgrade_to_premium(email):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        print(f"Unknown command: {command}")
        print("Available commands: admin, premium")
        sys.exit(1)