import os
import sys
from app import app, db
from models import User, PasswordEntry, PasswordHistory, EmergencyAccessRequest
import sqlalchemy as sa
from sqlalchemy import inspect, Column, String, Boolean, Integer, DateTime, LargeBinary, Text, ForeignKey

# Run this script to create or update database tables
with app.app_context():
    print("Creating database tables...")
    
    # First make sure all tables exist
    db.create_all()
    
    # Get metadata and inspector
    metadata = db.metadata
    inspector = inspect(db.engine)
    
    # Check and add missing columns to User model
    print("\nChecking and adding missing columns...")
    
    # User table columns to add if missing
    user_columns = {
        "is_premium": Column(Boolean, default=False),
        "stripe_customer_id": Column(String(255), nullable=True),
        "subscription_id": Column(String(255), nullable=True),
        "subscription_status": Column(String(50), default='free'),
        "subscription_end_date": Column(DateTime, nullable=True),
        "selected_theme": Column(String(50), default='default'),
        "last_password_check": Column(DateTime, nullable=True),
        "password_score": Column(Integer, default=0),
        "emergency_contact_email": Column(String(120), nullable=True),
        "emergency_access_enabled": Column(Boolean, default=False),
        "emergency_wait_time_days": Column(Integer, default=7),
        "emergency_request_date": Column(DateTime, nullable=True),
        "geo_access_enabled": Column(Boolean, default=False),
        "allowed_regions": Column(Text, nullable=True),
        "auto_logout_minutes": Column(Integer, default=15),
        "decoy_password_hash": Column(String(256), nullable=True)
    }
    
    # Password entry columns to add if missing
    password_entry_columns = {
        "expiry_date": Column(DateTime, nullable=True),
        "breach_status": Column(Boolean, default=False),
        "last_breach_check": Column(DateTime, nullable=True),
        "is_hidden": Column(Boolean, default=False),
        "strength_score": Column(Integer, default=0)
    }
    
    # Add missing columns to user table
    user_table_columns = [col['name'] for col in inspector.get_columns('user')]
    for col_name, col_def in user_columns.items():
        if col_name not in user_table_columns:
            print(f"Adding column '{col_name}' to user table...")
            column_type = col_def.type.compile(dialect=db.engine.dialect)
            nullable = "NULL" if col_def.nullable else "NOT NULL"
            default = f"DEFAULT {col_def.default.arg}" if col_def.default and col_def.default.arg is not None else ""
            
            # SQL command to add the column
            if col_def.default and isinstance(col_def.default.arg, str):
                default_value = f"DEFAULT '{col_def.default.arg}'"
            elif default:
                default_value = default
            else:
                default_value = ""
                
            sql = f"ALTER TABLE \"user\" ADD COLUMN {col_name} {column_type} {nullable} {default_value};"
            db.session.execute(sa.text(sql))
    
    # Add missing columns to password_entry table
    password_entry_table_columns = [col['name'] for col in inspector.get_columns('password_entry')]
    for col_name, col_def in password_entry_columns.items():
        if col_name not in password_entry_table_columns:
            print(f"Adding column '{col_name}' to password_entry table...")
            column_type = col_def.type.compile(dialect=db.engine.dialect)
            nullable = "NULL" if col_def.nullable else "NOT NULL"
            default = f"DEFAULT {col_def.default.arg}" if col_def.default and col_def.default.arg is not None else ""
            
            # SQL command to add the column
            if col_def.default and isinstance(col_def.default.arg, str):
                default_value = f"DEFAULT '{col_def.default.arg}'"
            elif default:
                default_value = default
            else:
                default_value = ""
                
            sql = f"ALTER TABLE password_entry ADD COLUMN {col_name} {column_type} {nullable} {default_value};"
            db.session.execute(sa.text(sql))
    
    # Commit all changes
    db.session.commit()
    print("Database schema updated successfully!")

    # Display the tables that were created
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print("\nTables in database:")
    for table in tables:
        print(f"- {table}")
        columns = inspector.get_columns(table)
        for column in columns:
            print(f"  - {column['name']}: {column['type']}")