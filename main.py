from app import app, db  # noqa: F401
from chat import chat_bp, ChatMessage
from routes_emergency import emergency_bp

# Register blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(emergency_bp)

# Make sure database tables are created
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
