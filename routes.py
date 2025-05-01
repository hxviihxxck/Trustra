import logging
from flask import render_template, url_for, flash, redirect, request, jsonify, session
from flask_login import login_user, current_user, logout_user, login_required
from app import app, db
from models import User, PasswordEntry
from forms import RegistrationForm, LoginForm, PasswordEntryForm, SearchForm
from werkzeug.exceptions import BadRequest
from subscription import subscription_bp
from premium import premium_bp

# Register blueprints
app.register_blueprint(subscription_bp)
app.register_blueprint(premium_bp)

# Index route
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html', title='Secure Password Manager')

# User registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Check if user with this email already exists
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('An account with this email already exists.', 'danger')
                return render_template('register.html', title='Register', form=form)
                
            # Check if username is taken
            existing_username = User.query.filter_by(username=form.username.data).first()
            if existing_username:
                flash('This username is already taken.', 'danger')
                return render_template('register.html', title='Register', form=form)
                
            # Create the new user
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Your account has been created! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Registration error: {str(e)}")
            flash('An unexpected error occurred. Please try again.', 'danger')
    
    return render_template('register.html', title='Register', form=form)

# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data).first()
            
            # Check if this is a normal login
            if user and user.check_password(form.password.data):
                # Regular successful login
                login_user(user, remember=form.remember.data)
                next_page = request.args.get('next')
                
                # Set session flag to indicate normal mode
                session['hidden_vault_mode'] = False
                
                flash('Login successful!', 'success')
                return redirect(next_page if next_page else url_for('dashboard'))
            
            # Check if this is a hidden vault mode login
            # Only check if normal login failed and user has premium features with hidden vault
            elif user and user.has_premium_features() and user.decoy_password_hash:
                from werkzeug.security import check_password_hash
                
                if check_password_hash(user.decoy_password_hash, form.password.data):
                    # Hidden vault mode login
                    login_user(user, remember=form.remember.data)
                    
                    # Set session flag for hidden vault mode
                    session['hidden_vault_mode'] = True
                    
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
            
            # If we get here, login failed            
            flash('Login unsuccessful. Please check your email and password.', 'danger')
        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            flash('An unexpected error occurred. Please try again.', 'danger')
    
    return render_template('login.html', title='Login', form=form)

# User logout
@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Dashboard
@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    search_form = SearchForm()
    query = request.args.get('query', '')
    
    # Check if we're in hidden vault mode
    hidden_vault_mode = session.get('hidden_vault_mode', False)
    
    # Base query - always filter by user ID
    base_query = PasswordEntry.query.filter_by(user_id=current_user.id)
    
    # If in hidden vault mode, only show non-hidden passwords
    # If in normal mode, hide the passwords marked as hidden
    if hidden_vault_mode:
        # In hidden vault mode, only show non-hidden passwords
        base_query = base_query.filter_by(is_hidden=False)
    else:
        # In normal mode, check if user has hidden passwords
        if current_user.has_premium_features() and current_user.decoy_password_hash:
            base_query = base_query.filter_by(is_hidden=False)
    
    # Apply search query if exists
    if query:
        # Search in password entries
        passwords = base_query.filter(
            (PasswordEntry.title.ilike(f'%{query}%') | 
             PasswordEntry.username.ilike(f'%{query}%') | 
             PasswordEntry.url.ilike(f'%{query}%') | 
             PasswordEntry.category.ilike(f'%{query}%'))
        ).order_by(PasswordEntry.date_updated.desc()).all()
    else:
        # Get filtered password entries
        passwords = base_query.order_by(PasswordEntry.date_updated.desc()).all()
    
    return render_template('dashboard.html', title='Dashboard', 
                          passwords=passwords, search_form=search_form, 
                          query=query, hidden_vault_mode=hidden_vault_mode)

# Add a new password
@app.route('/add-password', methods=['GET', 'POST'])
@login_required
def add_password():
    form = PasswordEntryForm()
    if form.validate_on_submit():
        try:
            # Create new password entry
            password_entry = PasswordEntry(
                title=form.title.data,
                username=form.username.data,
                url=form.url.data,
                category=form.category.data,
                notes=form.notes.data,
                user_id=current_user.id
            )
            password_entry.set_password(form.password.data)
            
            db.session.add(password_entry)
            db.session.commit()
            
            flash('Password added successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Add password error: {str(e)}")
            flash('An error occurred while adding your password. Please try again.', 'danger')
    
    return render_template('add_password.html', title='Add Password', form=form)

# Edit password
@app.route('/edit-password/<int:password_id>', methods=['GET', 'POST'])
@login_required
def edit_password(password_id):
    password_entry = PasswordEntry.query.get_or_404(password_id)
    
    # Verify that the password entry belongs to the current user
    if password_entry.user_id != current_user.id:
        flash('You do not have permission to edit this password.', 'danger')
        return redirect(url_for('dashboard'))
    
    form = PasswordEntryForm()
    
    if form.validate_on_submit():
        try:
            # Update password entry
            password_entry.title = form.title.data
            password_entry.username = form.username.data
            password_entry.url = form.url.data
            password_entry.category = form.category.data
            password_entry.notes = form.notes.data
            
            # Only update the password if a new one was provided
            if form.password.data:
                password_entry.set_password(form.password.data)
            
            db.session.commit()
            
            flash('Password updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Edit password error: {str(e)}")
            flash('An error occurred while updating your password. Please try again.', 'danger')
    
    # Pre-fill form with existing data
    if request.method == 'GET':
        form.title.data = password_entry.title
        form.username.data = password_entry.username
        form.url.data = password_entry.url
        form.category.data = password_entry.category
        form.notes.data = password_entry.notes
        # We don't pre-fill the password for security reasons
    
    return render_template('edit_password.html', title='Edit Password', form=form, password_id=password_id)

# Delete password
@app.route('/delete-password/<int:password_id>', methods=['POST'])
@login_required
def delete_password(password_id):
    try:
        password_entry = PasswordEntry.query.get_or_404(password_id)
        
        # Verify that the password entry belongs to the current user
        if password_entry.user_id != current_user.id:
            flash('You do not have permission to delete this password.', 'danger')
            return redirect(url_for('dashboard'))
        
        db.session.delete(password_entry)
        db.session.commit()
        
        flash('Password deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Delete password error: {str(e)}")
        flash('An error occurred while deleting your password. Please try again.', 'danger')
    
    return redirect(url_for('dashboard'))

# View password (AJAX)
@app.route('/get-password/<int:password_id>', methods=['GET'])
@login_required
def get_password(password_id):
    try:
        password_entry = PasswordEntry.query.get_or_404(password_id)
        
        # Verify that the password entry belongs to the current user
        if password_entry.user_id != current_user.id:
            return jsonify({"error": "Access denied"}), 403
        
        # Decrypt and return the password
        decrypted_password = password_entry.get_password()
        return jsonify({"password": decrypted_password}), 200
    except Exception as e:
        logging.error(f"Get password error: {str(e)}")
        return jsonify({"error": "Failed to retrieve password"}), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_code=404, error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500

@app.errorhandler(BadRequest)
def handle_bad_request(error):
    return render_template('error.html', error_code=400, error_message="Bad request"), 400

# Demo route for upgrading to premium (for demonstration purposes only)
@app.route('/demo-upgrade-premium', methods=['GET', 'POST'])
@login_required
def demo_upgrade_premium():
    """Upgrade current user to premium for demonstration purposes"""
    from datetime import datetime, timedelta
    
    try:
        # Set premium status
        current_user.is_premium = True
        current_user.subscription_status = 'active'
        current_user.subscription_end_date = datetime.utcnow() + timedelta(days=365)  # Set to expire in 1 year
        
        # Set a placeholder subscription ID
        if not current_user.subscription_id:
            current_user.subscription_id = f"demo_sub_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        db.session.commit()
        
        flash('Your account has been upgraded to premium for demonstration purposes!', 'success')
        return redirect(url_for('subscription.premium_features'))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Demo premium upgrade error: {str(e)}")
        flash('An error occurred while upgrading your account. Please try again.', 'danger')
        return redirect(url_for('dashboard'))

# Admin dashboard (protected route)
@app.route('/admin-dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard for site administrators"""
    if not getattr(current_user, 'is_admin', False):
        flash('You do not have permission to access the admin dashboard.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get user statistics
    user_count = User.query.count()
    premium_user_count = User.query.filter_by(is_premium=True).count()
    total_passwords = PasswordEntry.query.count()
    
    # Get recent users
    recent_users = User.query.order_by(User.date_joined.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', 
                         title='Admin Dashboard',
                         user_count=user_count,
                         premium_user_count=premium_user_count,
                         total_passwords=total_passwords,
                         recent_users=recent_users)
