#!/usr/bin/env python3
import os
import sys
from app import app, db
from models import User
from flask import Flask

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

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python admin_commands.py <user_email>")
        sys.exit(1)
    
    email = sys.argv[1]
    if make_admin(email):
        sys.exit(0)
    else:
        sys.exit(1)