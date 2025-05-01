from flask import Blueprint, request, jsonify, render_template
from flask_login import current_user
import json
import random
from datetime import datetime

# Create a blueprint for chat routes
chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

# Store chat histories in memory (in a real app, this would be in a database)
chat_histories = {}

# Predefined responses for the simulated chat agent
agent_responses = [
    "I'd be happy to help with that! Could you provide more details?",
    "That's a great question. Let me check that for you.",
    "I understand your concern. Here's what I can suggest...",
    "Thanks for reaching out. Let me guide you through this.",
    "I'm looking into this for you. Just a moment please.",
    "We value your feedback. I'll make sure this gets addressed.",
    "Have you tried checking the Trustra documentation? It might have the answer you're looking for.",
    "I'll connect you with a specialist who can help with that specific issue.",
    "Let me know if you need any clarification on anything I've explained.",
    "Is there anything else you'd like help with today?"
]

# Keyword-based responses
keyword_responses = {
    'password': [
        "Trustra keeps your passwords secure with end-to-end encryption. Nobody can access your passwords except you.",
        "Your passwords are encrypted with industry-standard algorithms. Only you can decrypt them with your master password.",
        "We recommend using unique, strong passwords for each of your accounts. Trustra can help generate these for you."
    ],
    'subscription': [
        "Premium subscriptions start at $4.99/month and include features like password health checks, breach monitoring, and emergency access.",
        "You can upgrade to premium at any time from the subscription page. We offer both monthly and annual billing.",
        "Premium subscribers get priority support and early access to new features."
    ],
    'refund': [
        "You can cancel your subscription anytime from your account settings. Refunds are processed according to our refund policy within 14 days of purchase.",
        "If you're having issues with your subscription, our support team can help resolve them before you consider a refund."
    ],
    'security': [
        "Trustra uses end-to-end encryption to keep your data secure. We can't access your passwords, even if we wanted to.",
        "We recommend enabling two-factor authentication for an additional layer of security on your Trustra account."
    ],
    'help': [
        "I'm here to help! You can ask me about password management, security practices, account settings, or subscription details.",
        "What specific aspect of Trustra would you like assistance with?"
    ]
}

@chat_bp.route('/send', methods=['POST'])
def send_message():
    """Handle incoming chat messages and return responses"""
    data = request.json
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400
    
    user_message = data['message']
    user_email = data.get('userEmail', 'guest')
    user_name = data.get('userName', 'Guest')
    
    # Store in chat history
    if user_email not in chat_histories:
        chat_histories[user_email] = []
    
    chat_histories[user_email].append({
        'sender': 'user',
        'content': user_message,
        'timestamp': datetime.now().isoformat()
    })
    
    # Generate response based on message content
    response = generate_response(user_message)
    
    # Store response in chat history
    chat_histories[user_email].append({
        'sender': 'system',
        'content': response,
        'timestamp': datetime.now().isoformat()
    })
    
    return jsonify({'response': response})

def generate_response(message):
    """Generate a response based on the user's message"""
    message_lower = message.lower()
    
    # Check for keyword matches
    for keyword, responses in keyword_responses.items():
        if keyword in message_lower:
            return random.choice(responses)
    
    # If no keyword matches, return a random general response
    return random.choice(agent_responses)

@chat_bp.route('/history', methods=['GET'])
def get_chat_history():
    """Get the chat history for the current user"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_email = current_user.email
    if user_email not in chat_histories:
        return jsonify({'history': []})
    
    return jsonify({'history': chat_histories[user_email]})

@chat_bp.route('/clear', methods=['POST'])
def clear_chat_history():
    """Clear the chat history for the current user"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_email = current_user.email
    if user_email in chat_histories:
        chat_histories[user_email] = []
    
    return jsonify({'status': 'success'})