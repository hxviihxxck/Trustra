import base64
import os
import logging
from datetime import datetime
from flask_login import UserMixin
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    encryption_key = db.Column(db.String(256), nullable=False)
    passwords = db.relationship('PasswordEntry', backref='owner', lazy='dynamic', cascade="all, delete-orphan")
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    
    # User role fields
    is_admin = db.Column(db.Boolean, default=False)  # Admin flag for staff access
    
    # Subscription-related fields
    is_premium = db.Column(db.Boolean, default=False)
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    subscription_id = db.Column(db.String(255), nullable=True)
    subscription_status = db.Column(db.String(50), default='free')  # free, active, past_due, canceled
    subscription_end_date = db.Column(db.DateTime, nullable=True)
    selected_theme = db.Column(db.String(50), default='default')  # For premium theme features
    last_password_check = db.Column(db.DateTime, nullable=True)  # For password health score
    password_score = db.Column(db.Integer, default=0)  # Overall password health score
    
    # Emergency access fields
    emergency_contact_email = db.Column(db.String(120), nullable=True)
    emergency_access_enabled = db.Column(db.Boolean, default=False)
    emergency_wait_time_days = db.Column(db.Integer, default=7)  # Days before emergency access granted
    emergency_request_date = db.Column(db.DateTime, nullable=True)  # When emergency access was requested
    
    # Security settings
    geo_access_enabled = db.Column(db.Boolean, default=False)
    allowed_regions = db.Column(db.Text, nullable=True)  # JSON list of allowed regions/IPs
    auto_logout_minutes = db.Column(db.Integer, default=15)  # Inactivity timeout
    decoy_password_hash = db.Column(db.String(256), nullable=True)  # For hidden vault mode
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        # Generate a unique encryption key for this user
        if not self.encryption_key:
            self.encryption_key = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_fernet(self):
        try:
            # Make sure the key is properly padded
            encryption_key = self.encryption_key
            # Ensure padding is correct for base64
            padding_needed = len(encryption_key) % 4
            if padding_needed:
                encryption_key += '=' * (4 - padding_needed)
            
            key = base64.urlsafe_b64decode(encryption_key.encode('utf-8'))
            # Ensure key is exactly 32 bytes
            if len(key) != 32:
                logging.error(f"Key length is {len(key)} bytes, not 32 bytes")
                # Pad or truncate to 32 bytes
                if len(key) < 32:
                    key = key.ljust(32, b'\0')  # Pad with null bytes
                else:
                    key = key[:32]  # Truncate to 32 bytes
            
            # Create valid Fernet key
            valid_key = base64.urlsafe_b64encode(key)
            return Fernet(valid_key)
        except Exception as e:
            logging.error(f"Error creating Fernet key: {str(e)}")
            # Generate a new encryption key and save it
            self.encryption_key = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')
            from app import db
            db.session.commit()
            # Return a new Fernet instance with the new key
            return Fernet(base64.urlsafe_b64encode(base64.urlsafe_b64decode(self.encryption_key.encode('utf-8'))))
        
    def has_premium_features(self):
        """Check if the user has access to premium features"""
        return self.is_premium and self.subscription_status == 'active'
        
    def update_password_score(self):
        """Calculate password health score based on various factors"""
        if not self.passwords.count():
            self.password_score = 0
            return
            
        score = 70  # Base score
        passwords = self.passwords.all()
        
        # Check for password reuse
        unique_passwords = set()
        for entry in passwords:
            unique_passwords.add(entry.get_password())
        
        if len(unique_passwords) < len(passwords):
            score -= 10  # Penalty for reused passwords
            
        # Check for weak passwords
        weak_count = 0
        for entry in passwords:
            password = entry.get_password()
            if len(password) < 10:
                weak_count += 1
                
        if weak_count > 0:
            score -= min(10, weak_count * 2)  # Penalty for weak passwords
            
        # Calculate diversity score
        categories = set(entry.category for entry in passwords if entry.category)
        category_bonus = min(10, len(categories) * 2)
        score += category_bonus
        
        # Cap score between 0-100
        self.password_score = max(0, min(100, score))
        self.last_password_check = datetime.utcnow()

class PasswordEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    password_encrypted = db.Column(db.LargeBinary, nullable=False)
    url = db.Column(db.String(255))
    notes = db.Column(db.Text)
    category = db.Column(db.String(50))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expiry_date = db.Column(db.DateTime, nullable=True)  # For password expiry alerts
    breach_status = db.Column(db.Boolean, default=False)  # For breach monitoring
    last_breach_check = db.Column(db.DateTime, nullable=True)  # When last checked for breaches
    is_hidden = db.Column(db.Boolean, default=False)  # For hidden vault mode
    strength_score = db.Column(db.Integer, default=0)  # Password strength score
    
    # Relationship to password history entries
    history = db.relationship('PasswordHistory', backref='password_entry', lazy='dynamic', cascade="all, delete-orphan")
    
    def set_password(self, plaintext_password):
        # Make sure owner is loaded
        if not hasattr(self, 'owner') or self.owner is None:
            from app import db
            if self.user_id:
                logging.debug(f"Loading owner for password entry with user_id={self.user_id}")
                # Try to find owner with two different methods
                self.owner = db.session.query(User).get(self.user_id)
                
                if not self.owner:
                    try:
                        # Try using filter_by if get doesn't work
                        self.owner = db.session.query(User).filter_by(id=self.user_id).first()
                    except Exception as e:
                        logging.error(f"Error in filter_by: {str(e)}")
                
                if self.owner:
                    logging.debug(f"Found owner: {self.owner.username}")
                else:
                    logging.error(f"Could not find owner with user_id={self.user_id}")
            else:
                logging.error("Password entry has no user_id")
                
        # If we still don't have an owner, we can't encrypt
        if not hasattr(self, 'owner') or self.owner is None:
            from flask_login import current_user
            # If current_user is available, use that
            if current_user and current_user.is_authenticated:
                logging.debug(f"Using current_user as owner: {current_user.username}")
                self.owner = current_user
                self.user_id = current_user.id
            else:
                error_msg = "Cannot encrypt password without a valid user owner"
                logging.error(error_msg)
                raise ValueError(error_msg)
            
        # Create history entry for premium users
        if self.id and self.owner.has_premium_features():
            old_password = None
            try:
                old_password = self.get_password()
            except:
                pass  # Handle case where decryption fails
                
            if old_password:
                history_entry = PasswordHistory(
                    password_id=self.id,
                    old_value_encrypted=self.password_encrypted,
                    changed_by=self.owner.username
                )
                db.session.add(history_entry)
        
        # Encrypt and store the new password
        fernet = self.owner.get_fernet()
        self.password_encrypted = fernet.encrypt(plaintext_password.encode('utf-8'))
        
        # Calculate password strength score
        self.calculate_strength(plaintext_password)
    
    def get_password(self):
        # Make sure owner is loaded
        if not hasattr(self, 'owner') or self.owner is None:
            from app import db
            if self.user_id:
                logging.debug(f"Loading owner for decryption with user_id={self.user_id}")
                # Try to find owner with two different methods
                self.owner = db.session.query(User).get(self.user_id)
                
                if not self.owner:
                    try:
                        # Try using filter_by if get doesn't work
                        self.owner = db.session.query(User).filter_by(id=self.user_id).first()
                    except Exception as e:
                        logging.error(f"Error in filter_by: {str(e)}")
                
                if self.owner:
                    logging.debug(f"Found owner for decryption: {self.owner.username}")
                else:
                    logging.error(f"Could not find owner for decryption with user_id={self.user_id}")
            else:
                logging.error("Password entry has no user_id for decryption")
                
        # If we still don't have an owner, we can't decrypt
        if not hasattr(self, 'owner') or self.owner is None:
            from flask_login import current_user
            # If current_user is available, use that
            if current_user and current_user.is_authenticated:
                logging.debug(f"Using current_user as owner for decryption: {current_user.username}")
                self.owner = current_user
                self.user_id = current_user.id
            else:
                error_msg = "Cannot decrypt password without a valid user owner"
                logging.error(error_msg)
                raise ValueError(error_msg)
            
        try:
            fernet = self.owner.get_fernet()
            return fernet.decrypt(self.password_encrypted).decode('utf-8')
        except Exception as e:
            logging.error(f"Error decrypting password: {str(e)}")
            raise ValueError(f"Could not decrypt password: {str(e)}")
        
    def calculate_strength(self, password):
        """Calculate password strength score (0-100)"""
        score = 0
        
        # Length-based score
        if len(password) >= 16:
            score += 30
        elif len(password) >= 12:
            score += 25
        elif len(password) >= 8:
            score += 15
        else:
            score += 5
            
        # Character diversity
        if any(c.islower() for c in password):
            score += 10
        if any(c.isupper() for c in password):
            score += 10
        if any(c.isdigit() for c in password):
            score += 10
        if any(not c.isalnum() for c in password):
            score += 15
            
        # Additional bonus for length
        score += min(25, len(password) - 8)
        
        # Cap at 100
        self.strength_score = min(100, score)
        
    def check_for_breach(self):
        """Check if this password has been in a data breach (premium feature)"""
        import hashlib
        import random
        from app import db
        
        # Mark it as checked
        self.last_breach_check = datetime.utcnow()
        
        # In a real implementation, we would use the haveibeenpwned API
        # For demonstration, we'll simulate some passwords being breached
        try:
            plaintext = self.get_password()
            
            if plaintext:
                # Create SHA-1 hash of the password
                sha1_hash = hashlib.sha1(plaintext.encode('utf-8')).hexdigest().upper()
                logging.debug(f"Checking breach status for password with hash prefix {sha1_hash[:5]}...")
                
                # Simulate breach detection (15% chance of a breach)
                # In a real implementation, we would check with the haveibeenpwned API
                is_breached = random.random() < 0.15 or len(plaintext) < 8
                
                # Update the breach status
                self.breach_status = is_breached
                db.session.commit()
                
                return is_breached
        except Exception as e:
            logging.error(f"Error checking for breach: {str(e)}")
            # Set breach status to True in case of error (better safe than sorry)
            self.breach_status = True
            try:
                db.session.commit()
            except:
                pass
            return True
        
        return False


class PasswordHistory(db.Model):
    """Tracks password change history for premium users"""
    id = db.Column(db.Integer, primary_key=True)
    password_id = db.Column(db.Integer, db.ForeignKey('password_entry.id'), nullable=False)
    old_value_encrypted = db.Column(db.LargeBinary, nullable=False)
    date_changed = db.Column(db.DateTime, default=datetime.utcnow)
    changed_by = db.Column(db.String(100), nullable=False)  # Username who made the change
    
    def get_old_password(self, user):
        """Decrypt the old password value"""
        try:
            fernet = user.get_fernet()
            return fernet.decrypt(self.old_value_encrypted).decode('utf-8')
        except Exception as e:
            logging.error(f"Error decrypting password history: {str(e)}")
            return "*** Decryption failed ***"


class EmergencyAccessRequest(db.Model):
    """Tracks emergency access requests and approvals"""
    id = db.Column(db.Integer, primary_key=True)
    requester_email = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # When access will be automatically granted
    status = db.Column(db.String(20), default='pending')  # pending, approved, denied, expired
    
    user = db.relationship('User', backref='emergency_requests')
    
    @property
    def is_approved(self):
        return self.status == 'approved'
        
    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
