import logging
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, current_user
from werkzeug.security import check_password_hash
from datetime import datetime
from app import db
from models import User, PasswordEntry, EmergencyAccessRequest

emergency_bp = Blueprint('emergency', __name__)

@emergency_bp.route('/emergency-access', methods=['GET', 'POST'])
def emergency_access():
    """Handle emergency access requests"""
    if request.method == 'POST':
        user_email = request.form.get('user_email')
        requester_email = request.form.get('requester_email')
        
        if not user_email or not requester_email:
            flash('Both user email and requester email are required.', 'danger')
            return redirect(url_for('emergency.emergency_access'))
        
        # Process the emergency access request
        try:
            from premium import request_emergency_access as process_request
            return process_request()
        except Exception as e:
            logging.error(f"Error processing emergency access request: {str(e)}")
            flash('An error occurred while processing your request.', 'danger')
            return redirect(url_for('emergency.emergency_access'))
    
    return render_template('emergency/request_access.html')

@emergency_bp.route('/emergency-access/login', methods=['GET', 'POST'])
def emergency_login():
    """Handle emergency access login"""
    if request.method == 'POST':
        user_email = request.form.get('user_email')
        requester_email = request.form.get('requester_email')
        
        if not user_email or not requester_email:
            flash('Both user email and requester email are required.', 'danger')
            return redirect(url_for('emergency.emergency_login'))
        
        # Check if there's an approved emergency access request
        try:
            user = User.query.filter_by(email=user_email).first()
            if not user:
                flash('Emergency access login failed. Please check your information.', 'danger')
                return redirect(url_for('emergency.emergency_login'))
            
            # Find the emergency access request
            access_request = EmergencyAccessRequest.query.filter_by(
                user_id=user.id,
                requester_email=requester_email,
            ).order_by(EmergencyAccessRequest.requested_at.desc()).first()
            
            if not access_request:
                flash('No emergency access request found.', 'danger')
                return redirect(url_for('emergency.emergency_login'))
            
            # Check if access is approved or if waiting period has passed
            if access_request.status == 'approved' or (access_request.status == 'pending' and datetime.utcnow() > access_request.expires_at):
                # If pending but expired, update to approved
                if access_request.status == 'pending' and datetime.utcnow() > access_request.expires_at:
                    access_request.status = 'approved'
                    db.session.commit()
                    # Send notification email
                    from utils import send_emergency_access_granted_notification
                    send_emergency_access_granted_notification(user.email, requester_email)
                
                # Mark request as "accessed" in the session
                session['emergency_mode'] = True
                session['emergency_for_user_id'] = user.id
                
                # Log in as the user
                login_user(user)
                flash('Emergency access has been granted. You now have temporary access to this vault.', 'success')
                return redirect(url_for('dashboard'))
            elif access_request.status == 'denied':
                flash('This emergency access request has been denied by the vault owner.', 'danger')
                return redirect(url_for('emergency.emergency_login'))
            else:
                # Still pending and not expired
                days_left = (access_request.expires_at - datetime.utcnow()).days
                flash(f'Your emergency access request is still pending. Access will be automatically granted in {days_left} days if the owner does not respond.', 'info')
                return redirect(url_for('emergency.emergency_login'))
                
        except Exception as e:
            logging.error(f"Error during emergency login: {str(e)}")
            flash('An error occurred during emergency login.', 'danger')
            return redirect(url_for('emergency.emergency_login'))
    
    return render_template('emergency/login.html')