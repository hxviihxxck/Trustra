import base64
import os
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
        key = base64.urlsafe_b64decode(self.encryption_key.encode('utf-8'))
        return Fernet(key)

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
    
    def set_password(self, plaintext_password):
        fernet = self.owner.get_fernet()
        self.password_encrypted = fernet.encrypt(plaintext_password.encode('utf-8'))
    
    def get_password(self):
        fernet = self.owner.get_fernet()
        return fernet.decrypt(self.password_encrypted).decode('utf-8')
