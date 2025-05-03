import os
import logging

from flask import Flask
from config import Config
from extensions import db, login_manager, csrf  # ✅ Use these directly
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask application
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24))
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
csrf.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Register routes and blueprints
with app.app_context():
    from models import User, PasswordEntry
    from routes import *
    from routes_emergency import emergency_bp
    app.register_blueprint(emergency_bp)
    
    db.create_all()
