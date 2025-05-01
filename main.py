from app import app  # noqa: F401
from chat import chat_bp

# Register blueprints
app.register_blueprint(chat_bp)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
