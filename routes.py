import logging
from flask import render_template, url_for, flash, redirect, request, jsonify
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
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember.data)
                next_page = request.args.get('next')
                flash('Login successful!', 'success')
                return redirect(next_page if next_page else url_for('dashboard'))
            else:
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
    
    if query:
        # Search in password entries
        passwords = PasswordEntry.query.filter(
            PasswordEntry.user_id == current_user.id,
            (PasswordEntry.title.ilike(f'%{query}%') | 
             PasswordEntry.username.ilike(f'%{query}%') | 
             PasswordEntry.url.ilike(f'%{query}%') | 
             PasswordEntry.category.ilike(f'%{query}%'))
        ).order_by(PasswordEntry.date_updated.desc()).all()
    else:
        # Get all password entries for the current user
        passwords = PasswordEntry.query.filter_by(
            user_id=current_user.id
        ).order_by(PasswordEntry.date_updated.desc()).all()
    
    return render_template('dashboard.html', title='Dashboard', 
                          passwords=passwords, search_form=search_form, query=query)

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
