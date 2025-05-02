import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import User, PasswordEntry, EmergencyAccessRequest, PasswordHistory

# Blueprint for premium features
premium_bp = Blueprint('premium', __name__)

@premium_bp.route('/premium/update-password-score', methods=['POST'])
@login_required
def update_password_score():
    """Update the user's password health score"""
    if not current_user.has_premium_features():
        flash('This feature is only available to premium subscribers.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        # Calculate and update the password score
        current_user.update_password_score()
        db.session.commit()
        
        flash('Password health score has been updated.', 'success')
    except Exception as e:
        logging.error(f"Error updating password score: {str(e)}")
        flash('An error occurred while updating your password health score.', 'danger')
    
    return redirect(url_for('subscription.premium_features'))

@premium_bp.route('/premium/check-breaches', methods=['POST'])
@login_required
def check_breaches():
    """Check user's passwords for breaches"""
    if not current_user.has_premium_features():
        flash('This feature is only available to premium subscribers.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        # Get all passwords for the current user
        passwords = PasswordEntry.query.filter_by(user_id=current_user.id).all()
        
        breached_count = 0
        for password in passwords:
            # Check each password for breaches
            was_breached = password.check_for_breach()
            if was_breached:
                breached_count += 1
        
        if breached_count > 0:
            flash(f'{breached_count} passwords were found in data breaches. Please consider changing them.', 'warning')
        else:
            flash('Great news! None of your passwords were found in known data breaches.', 'success')
    except Exception as e:
        logging.error(f"Error checking for breaches: {str(e)}")
        flash('An error occurred while checking for data breaches.', 'danger')
    
    return redirect(url_for('subscription.premium_features'))

@premium_bp.route('/premium/set-theme', methods=['POST'])
@login_required
def set_theme():
    """Set the user's theme preference"""
    if not current_user.has_premium_features():
        flash('Custom themes are only available to premium subscribers.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        theme = request.form.get('theme', 'default')
        allowed_themes = ['default', 'cyberpunk', 'neon', 'solarized']
        
        if theme not in allowed_themes:
            theme = 'default'
        
        current_user.selected_theme = theme
        db.session.commit()
        
        flash(f'Theme has been updated to {theme.capitalize()}.', 'success')
    except Exception as e:
        logging.error(f"Error setting theme: {str(e)}")
        flash('An error occurred while updating your theme.', 'danger')
    
    return redirect(url_for('subscription.premium_features'))

@premium_bp.route('/premium/setup-emergency-access', methods=['POST'])
@login_required
def setup_emergency_access():
    """Set up emergency access settings"""
    if not current_user.has_premium_features():
        flash('Emergency access is only available to premium subscribers.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        emergency_contact = request.form.get('emergency_contact')
        waiting_period = int(request.form.get('waiting_period', 7))
        enabled = 'emergency_access_enabled' in request.form
        
        current_user.emergency_contact_email = emergency_contact
        current_user.emergency_wait_time_days = waiting_period
        current_user.emergency_access_enabled = enabled
        
        db.session.commit()
        
        if enabled:
            flash('Emergency access has been enabled and configured.', 'success')
        else:
            flash('Emergency access has been disabled.', 'info')
    except Exception as e:
        logging.error(f"Error setting up emergency access: {str(e)}")
        flash('An error occurred while updating your emergency access settings.', 'danger')
    
    return redirect(url_for('subscription.premium_features'))

@premium_bp.route('/premium/setup-hidden-vault', methods=['POST'])
@login_required
def setup_hidden_vault():
    """Set up hidden vault mode"""
    if not current_user.has_premium_features():
        flash('Hidden vault mode is only available to premium subscribers.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        decoy_password = request.form.get('decoy_password')
        enabled = 'enable_hidden_vault' in request.form
        
        if enabled and not decoy_password:
            flash('You must set a decoy password to enable hidden vault mode.', 'warning')
            return redirect(url_for('subscription.premium_features'))
        
        # Get all passwords for the user
        passwords = PasswordEntry.query.filter_by(user_id=current_user.id).all()
        
        # If enabling hidden vault
        if enabled:
            # Store the decoy password securely (hashed)
            from werkzeug.security import generate_password_hash
            hashed_decoy = generate_password_hash(decoy_password)
            current_user.decoy_password_hash = hashed_decoy
            
            # Mark some passwords as hidden (about 40% of them)
            import random
            hidden_count = max(1, int(len(passwords) * 0.4))
            passwords_to_hide = random.sample(passwords, min(hidden_count, len(passwords)))
            
            for password in passwords_to_hide:
                password.is_hidden = True
                
            # Commit changes
            db.session.commit()
            flash(f'Hidden vault mode enabled. {len(passwords_to_hide)} passwords are now hidden in normal mode.', 'success')
        else:
            # Disable hidden vault
            current_user.decoy_password_hash = None
            
            # Unhide all passwords
            for password in passwords:
                password.is_hidden = False
                
            # Commit changes
            db.session.commit()
            flash('Hidden vault mode has been disabled.', 'success')
    except Exception as e:
        logging.error(f"Error setting up hidden vault: {str(e)}")
        flash('An error occurred while updating your hidden vault settings.', 'danger')
    
    return redirect(url_for('subscription.premium_features'))

@premium_bp.route('/premium/setup-geo-access', methods=['POST'])
@login_required
def setup_geo_access():
    """Set up geo-fenced access"""
    if not current_user.has_premium_features():
        flash('Geo-fenced access is only available to premium subscribers.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        allowed_ips = request.form.get('allowed_ips', '').strip()
        allowed_regions = request.form.getlist('allowed_regions')
        enabled = 'geo_access_enabled' in request.form
        
        current_user.geo_access_enabled = enabled
        
        # Store regions and IPs as JSON in the database
        regions_and_ips = {
            'ips': [ip.strip() for ip in allowed_ips.split(',') if ip.strip()],
            'regions': allowed_regions
        }
        current_user.allowed_regions = json.dumps(regions_and_ips)
        
        db.session.commit()
        
        if enabled:
            flash('Geo-fenced access has been enabled and configured.', 'success')
        else:
            flash('Geo-fenced access has been disabled.', 'info')
    except Exception as e:
        logging.error(f"Error setting up geo access: {str(e)}")
        flash('An error occurred while updating your geo-fenced access settings.', 'danger')
    
    return redirect(url_for('subscription.premium_features'))

@premium_bp.route('/premium/setup-auto-logout', methods=['POST'])
@login_required
def setup_auto_logout():
    """Set up automatic logout timer"""
    if not current_user.has_premium_features():
        flash('Custom auto-logout timer is only available to premium subscribers.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        logout_minutes = int(request.form.get('logout_minutes', 15))
        
        # Ensure the value is within a reasonable range
        if logout_minutes < 1:
            logout_minutes = 1
        elif logout_minutes > 60:
            logout_minutes = 60
        
        current_user.auto_logout_minutes = logout_minutes
        db.session.commit()
        
        flash(f'Auto-logout timer has been set to {logout_minutes} minutes.', 'success')
    except Exception as e:
        logging.error(f"Error setting up auto logout: {str(e)}")
        flash('An error occurred while updating your auto-logout settings.', 'danger')
    
    return redirect(url_for('subscription.premium_features'))

@premium_bp.route('/premium/password-history/<int:password_id>')
@login_required
def password_history(password_id):
    """View password entry history"""
    if not current_user.has_premium_features():
        flash('Password history is only available to premium subscribers.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        # Get the password entry and ensure it belongs to the current user
        password_entry = PasswordEntry.query.get_or_404(password_id)
        
        # Enhanced logging for debugging
        logging.debug(f"Retrieving password entry (ID: {password_id}, User ID: {password_entry.user_id}, Title: {password_entry.title})")
        
        if password_entry.user_id != current_user.id:
            flash('You do not have permission to view this password history.', 'danger')
            return redirect(url_for('dashboard'))
        
        # Try to get the password to verify encryption/decryption is working
        try:
            current_password = password_entry.get_password()
            logging.debug(f"Successfully retrieved current password for entry {password_id}")
        except Exception as e:
            logging.error(f"Failed to decrypt current password: {str(e)}")
            flash('There was an issue retrieving the current password data.', 'warning')
            
        # Get all history entries for this password
        history = password_entry.history.order_by(PasswordHistory.date_changed.desc()).all()
        logging.debug(f"Found {len(history)} history entries for password {password_id}")
        
        # Pre-process history entries to catch decryption errors before rendering
        for entry in history:
            try:
                # Try to get old password to verify it works
                entry.get_old_password(current_user)
            except Exception as e:
                logging.error(f"Pre-processing error for history entry {entry.id}: {str(e)}")
        
        return render_template('premium/password_history.html', 
                              password_entry=password_entry, 
                              history=history)
    except Exception as e:
        logging.error(f"Error retrieving password history: {str(e)}")
        flash('An error occurred while retrieving the password history.', 'danger')
        return redirect(url_for('dashboard'))

@premium_bp.route('/premium/request-emergency-access', methods=['POST'])
def request_emergency_access():
    """Request emergency access to a user's vault"""
    try:
        user_email = request.form.get('user_email')
        requester_email = request.form.get('requester_email')
        
        if not user_email or not requester_email:
            flash('Both user email and requester email are required.', 'danger')
            return redirect(url_for('index'))
        
        # Find the user account
        user = User.query.filter_by(email=user_email).first()
        if not user or not user.emergency_access_enabled:
            # Don't reveal whether the account exists or has emergency access enabled
            flash('Emergency access request has been submitted. If the account exists and has emergency access enabled, the owner will be notified.', 'info')
            return redirect(url_for('index'))
        
        # Check if the requester is the configured emergency contact
        if user.emergency_contact_email != requester_email:
            flash('Emergency access request has been submitted. If the account exists and has emergency access enabled, the owner will be notified.', 'info')
            return redirect(url_for('index'))
        
        # Calculate expiration time based on user's waiting period
        expires_at = datetime.utcnow() + timedelta(days=user.emergency_wait_time_days)
        
        # Create the emergency access request
        request_entry = EmergencyAccessRequest(
            requester_email=requester_email,
            user_id=user.id,
            expires_at=expires_at
        )
        
        db.session.add(request_entry)
        db.session.commit()
        
        # Send email notification to the vault owner
        from utils import send_emergency_access_request_notification
        email_sent = send_emergency_access_request_notification(user, requester_email, expires_at)
        
        if email_sent:
            logging.info(f"Emergency access notification email sent to {user.email}")
        else:
            logging.error(f"Failed to send emergency access notification email to {user.email}")
        
        flash('Emergency access request has been submitted. The account owner has been notified and has the option to approve or deny your request. If no action is taken, access will be granted after the waiting period.', 'info')
    except Exception as e:
        logging.error(f"Error requesting emergency access: {str(e)}")
        flash('An error occurred while processing your emergency access request.', 'danger')
    
    return redirect(url_for('index'))

@premium_bp.route('/premium/emergency-requests')
@login_required
def view_emergency_requests():
    """View pending emergency access requests"""
    try:
        # Get all pending emergency requests for the current user
        requests = EmergencyAccessRequest.query.filter_by(
            user_id=current_user.id,
            status='pending'
        ).all()
        
        return render_template('premium/emergency_requests.html', requests=requests)
    except Exception as e:
        logging.error(f"Error retrieving emergency requests: {str(e)}")
        flash('An error occurred while retrieving emergency access requests.', 'danger')
        return redirect(url_for('dashboard'))

@premium_bp.route('/premium/handle-emergency-request/<int:request_id>/<action>', methods=['POST'])
@login_required
def handle_emergency_request(request_id, action):
    """Approve or deny an emergency access request"""
    try:
        # Get the emergency request and ensure it belongs to the current user
        emergency_request = EmergencyAccessRequest.query.get_or_404(request_id)
        if emergency_request.user_id != current_user.id:
            flash('You do not have permission to manage this emergency access request.', 'danger')
            return redirect(url_for('dashboard'))
        
        from utils import send_emergency_access_granted_notification, send_emergency_access_denied_notification
        
        if action == 'approve':
            emergency_request.status = 'approved'
            
            # Send approval notification
            email_sent = send_emergency_access_granted_notification(
                current_user.email, 
                emergency_request.requester_email
            )
            
            if email_sent:
                logging.info(f"Emergency access granted notification sent to {emergency_request.requester_email}")
            else:
                logging.error(f"Failed to send emergency access granted notification to {emergency_request.requester_email}")
                
            flash('Emergency access request has been approved. The requester has been notified.', 'success')
            
        elif action == 'deny':
            emergency_request.status = 'denied'
            
            # Send denial notification
            email_sent = send_emergency_access_denied_notification(
                current_user.email, 
                emergency_request.requester_email
            )
            
            if email_sent:
                logging.info(f"Emergency access denied notification sent to {emergency_request.requester_email}")
            else:
                logging.error(f"Failed to send emergency access denied notification to {emergency_request.requester_email}")
                
            flash('Emergency access request has been denied. The requester has been notified.', 'success')
            
        else:
            flash('Invalid action.', 'danger')
            return redirect(url_for('premium.view_emergency_requests'))
        
        db.session.commit()
        
    except Exception as e:
        logging.error(f"Error handling emergency request: {str(e)}")
        flash('An error occurred while processing the emergency access request.', 'danger')
    
    return redirect(url_for('premium.view_emergency_requests'))