from flask import Blueprint, request, jsonify, render_template, current_app, redirect, url_for, session, abort, flash
from flask_login import current_user, login_required
import json
import random
import os
from datetime import datetime
from openai import OpenAI
from app import db
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey

# Create a blueprint for chat routes
chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

# Model for chat conversations
class ChatMessage(db.Model):
    """Model for storing chat messages"""
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(64), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_email = db.Column(db.String(120))
    user_name = db.Column(db.String(64))
    sender = db.Column(db.String(20))  # 'user', 'system', or 'admin'
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    requires_human = db.Column(db.Boolean, default=False)
    is_hidden = db.Column(db.Boolean, default=False)

# Try to initialize the OpenAI client
openai_client = None
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")

# Predefine context for AI responses about Trustra
TRUSTRA_CONTEXT = """
Trustra is a secure password manager application that helps users store and manage their passwords safely.
Key features include:
1. End-to-end encryption for password security
2. Password health score monitoring
3. Breach monitoring for premium users
4. Custom themes for premium users
5. Password history tracking
6. Emergency access for trusted contacts
7. Hidden vault mode for sensitive credentials
8. Basic plan is free, Premium subscription is $4.99/month

When answering questions, remember that:
- Trustra encrypts all passwords with industry-standard algorithms
- Only the user can decrypt their passwords with their master password
- Premium features include health score, breach monitoring, custom themes, password history
- Subscriptions can be canceled anytime from account settings
- Refunds are processed within 14 days of purchase per our refund policy
- Technical support is available 24/7 through the chat system
"""

# Predefined responses for when AI is not available
fallback_responses = [
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

# Keyword-based responses for when AI is not available
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
    
    # Generate a conversation ID if needed
    conversation_id = session.get('chat_conversation_id')
    if not conversation_id:
        conversation_id = f"conv_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_email}"
        session['chat_conversation_id'] = conversation_id
    
    # Store the user message in the database
    user_id = current_user.id if current_user.is_authenticated else None
    
    # Create tables if they don't exist
    with current_app.app_context():
        try:
            db.create_all()
        except:
            # If create_all fails, just continue - tables might already exist
            pass
    
    # Try to store the message
    try:
        user_msg = ChatMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            sender='user',
            content=user_message,
            timestamp=datetime.utcnow()
        )
        db.session.add(user_msg)
        db.session.commit()
    except Exception as e:
        print(f"Error saving user message: {e}")
        # Continue even if database save fails
    
    # Generate response based on message content
    requires_human = False
    if "speak to staff" in user_message.lower() or "speak to a human" in user_message.lower() or "human support" in user_message.lower():
        response = "I'll connect you with one of our support staff. Please wait a moment while I transfer your conversation."
        requires_human = True
    else:
        response = generate_ai_response(conversation_id, user_message, user_name)
    
    # Store the response in the database
    try:
        system_msg = ChatMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            sender='system',
            content=response,
            timestamp=datetime.utcnow(),
            requires_human=requires_human
        )
        db.session.add(system_msg)
        db.session.commit()
    except Exception as e:
        print(f"Error saving system response: {e}")
    
    return jsonify({'response': response, 'requiresHuman': requires_human})

def generate_ai_response(conversation_id, message, user_name):
    """Generate a response using OpenAI API if available, otherwise fallback to predefined responses"""
    if not openai_client:
        return generate_fallback_response(message)
    
    try:
        # Get the last 5 messages from this conversation for context
        history = get_conversation_history(conversation_id, limit=5)
        
        # Format the conversation history for the OpenAI API
        messages = [
            {"role": "system", "content": f"{TRUSTRA_CONTEXT}\nYou are the Trustra support assistant helping {user_name}. Be helpful, friendly and concise."}
        ]
        
        # Add conversation history
        for msg in history:
            role = "user" if msg.sender == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})
        
        # Add the current message
        messages.append({"role": "user", "content": message})
        
        # Call the OpenAI API
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"Error generating AI response: {e}")
        return generate_fallback_response(message)

def generate_fallback_response(message):
    """Generate a response based on keywords when AI is not available"""
    message_lower = message.lower()
    
    # Check for keyword matches
    for keyword, responses in keyword_responses.items():
        if keyword in message_lower:
            return random.choice(responses)
    
    # If no keyword matches, return a random general response
    return random.choice(fallback_responses)

def get_conversation_history(conversation_id, limit=10):
    """Get the conversation history for the given conversation_id"""
    try:
        return ChatMessage.query.filter_by(conversation_id=conversation_id).order_by(ChatMessage.timestamp.asc()).limit(limit).all()
    except Exception as e:
        print(f"Error getting conversation history: {e}")
        return []

@chat_bp.route('/history', methods=['GET'])
def get_chat_history():
    """Get the chat history for the current user"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conversation_id = session.get('chat_conversation_id')
    if not conversation_id:
        return jsonify({'history': []})
    
    try:
        messages = ChatMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(ChatMessage.timestamp.asc()).all()
        
        history = [
            {
                'sender': msg.sender,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'requires_human': msg.requires_human
            }
            for msg in messages
        ]
        
        return jsonify({'history': history})
    except Exception as e:
        print(f"Error retrieving chat history: {e}")
        return jsonify({'history': [], 'error': str(e)})

@chat_bp.route('/clear', methods=['POST'])
def clear_chat_history():
    """Clear the chat history for the current user"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conversation_id = session.get('chat_conversation_id')
    if conversation_id:
        try:
            # Don't actually delete, just hide the messages
            messages = ChatMessage.query.filter_by(conversation_id=conversation_id).all()
            for msg in messages:
                msg.is_hidden = True
            
            db.session.commit()
            
            # Generate a new conversation ID
            new_conversation_id = f"conv_{datetime.now().strftime('%Y%m%d%H%M%S')}_{current_user.email}"
            session['chat_conversation_id'] = new_conversation_id
        except Exception as e:
            print(f"Error clearing chat history: {e}")
    
    return jsonify({'status': 'success'})

# Admin routes for managing chat conversations
@chat_bp.route('/admin', methods=['GET'])
@login_required
def admin_dashboard():
    """Admin dashboard for managing chat conversations"""
    # Only allow admin users
    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get all conversations that require human attention
    try:
        # Find conversations with messages that require human attention
        conversations = db.session.query(ChatMessage.conversation_id, 
                                       ChatMessage.user_name, 
                                       ChatMessage.user_email,
                                       db.func.max(ChatMessage.timestamp).label('last_message'))\
            .filter(ChatMessage.requires_human == True)\
            .filter(ChatMessage.is_hidden == False)\
            .group_by(ChatMessage.conversation_id, ChatMessage.user_name, ChatMessage.user_email)\
            .order_by(db.func.max(ChatMessage.timestamp).desc())\
            .all()
        
        # Also get recent conversations (last 50)
        recent_conversations = db.session.query(ChatMessage.conversation_id, 
                                              ChatMessage.user_name, 
                                              ChatMessage.user_email,
                                              db.func.max(ChatMessage.timestamp).label('last_message'))\
            .filter(ChatMessage.is_hidden == False)\
            .group_by(ChatMessage.conversation_id, ChatMessage.user_name, ChatMessage.user_email)\
            .order_by(db.func.max(ChatMessage.timestamp).desc())\
            .limit(50)\
            .all()
        
        return render_template('chat/admin_dashboard.html', 
                             require_attention=conversations, 
                             recent_conversations=recent_conversations)
    except Exception as e:
        print(f"Error loading admin dashboard: {e}")
        flash('Error loading admin dashboard', 'danger')
        return redirect(url_for('dashboard'))

@chat_bp.route('/admin/conversation/<conversation_id>', methods=['GET', 'POST'])
@login_required
def admin_conversation(conversation_id):
    """View and respond to a specific conversation"""
    # Only allow admin users
    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Handle admin response
        admin_message = request.form.get('message')
        if not admin_message:
            flash('Message cannot be empty', 'warning')
            return redirect(url_for('chat.admin_conversation', conversation_id=conversation_id))
        
        # Get user info from previous messages
        user_info = db.session.query(ChatMessage.user_id, ChatMessage.user_email, ChatMessage.user_name)\
            .filter_by(conversation_id=conversation_id)\
            .first()
        
        if not user_info:
            flash('Conversation not found', 'danger')
            return redirect(url_for('chat.admin_dashboard'))
        
        # Save admin response
        try:
            admin_msg = ChatMessage(
                conversation_id=conversation_id,
                user_id=user_info.user_id,
                user_email=user_info.user_email,
                user_name=user_info.user_name,
                sender='admin',
                content=admin_message,
                timestamp=datetime.utcnow()
            )
            db.session.add(admin_msg)
            db.session.commit()
            flash('Response sent successfully', 'success')
        except Exception as e:
            print(f"Error saving admin response: {e}")
            flash('Error sending response', 'danger')
        
        return redirect(url_for('chat.admin_conversation', conversation_id=conversation_id))
    
    # Display conversation
    try:
        messages = ChatMessage.query.filter_by(
            conversation_id=conversation_id,
            is_hidden=False
        ).order_by(ChatMessage.timestamp.asc()).all()
        
        # Mark messages as read
        for msg in messages:
            if not msg.is_read:
                msg.is_read = True
        
        db.session.commit()
        
        # Get user info
        user_info = None
        if messages:
            first_message = messages[0]
            user_info = {
                'name': first_message.user_name,
                'email': first_message.user_email,
                'user_id': first_message.user_id
            }
        
        return render_template('chat/admin_conversation.html', 
                             messages=messages, 
                             conversation_id=conversation_id,
                             user_info=user_info)
    except Exception as e:
        print(f"Error loading conversation: {e}")
        flash('Error loading conversation', 'danger')
        return redirect(url_for('chat.admin_dashboard'))