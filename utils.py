import os
import logging
import json
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent

def send_email(to_email, subject, text_content=None, html_content=None, from_email="noreply@trustra.app"):
    """Send an email using SendGrid"""
    if not os.environ.get('SENDGRID_API_KEY'):
        logging.error("SENDGRID_API_KEY is not set")
        return False

    message = Mail(
        from_email=Email(from_email),
        to_emails=To(to_email),
        subject=subject
    )

    if html_content:
        message.content = HtmlContent(html_content)
    elif text_content:
        message.content = Content("text/plain", text_content)
    else:
        message.content = Content("text/plain", "This is an automated message from Trustra.")

    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        logging.info(f"Email sent to {to_email}, status code: {response.status_code}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")
        return False

def send_emergency_access_request_notification(user, requester_email, expires_at):
    """Send notification about emergency access request"""
    # Calculate days until access is granted
    days_until_access = (expires_at - datetime.utcnow()).days
    
    # Create HTML content
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="border-bottom: 3px solid #4f46e5; padding-bottom: 20px; margin-bottom: 20px;">
            <h1 style="color: #4f46e5; margin: 0;">Trustra Password Manager</h1>
            <p style="font-size: 18px; margin: 5px 0 0;">Emergency Access Request</p>
        </div>
        
        <p>Hello {user.username},</p>
        
        <p><strong>{requester_email}</strong> has requested emergency access to your Trustra vault.</p>
        
        <p>If you did not authorize this request, please log in to your account immediately and deny this request.</p>
        
        <div style="background-color: #f3f4f6; border-left: 4px solid #ef4444; padding: 15px; margin: 20px 0;">
            <p style="margin: 0; font-weight: bold;">Important:</p>
            <p style="margin: 10px 0 0;">If no action is taken, access will be automatically granted in <strong>{days_until_access} days</strong>.</p>
        </div>
        
        <a href="https://trustra.app/emergency-access" style="display: inline-block; background-color: #4f46e5; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; margin-top: 15px;">Review Request</a>
        
        <p style="margin-top: 30px; font-size: 14px; color: #6b7280;">
            If you have any questions, please contact support at support@trustra.app.
        </p>
        
        <p style="font-size: 12px; color: #9ca3af; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 20px;">
            This is an automated message from Trustra Password Manager. Please do not reply to this email.
        </p>
    </body>
    </html>
    """
    
    # Plain text fallback
    text_content = f"""
    Trustra Password Manager - Emergency Access Request
    
    Hello {user.username},
    
    {requester_email} has requested emergency access to your Trustra vault.
    
    If you did not authorize this request, please log in to your account immediately and deny this request.
    
    Important: If no action is taken, access will be automatically granted in {days_until_access} days.
    
    Please visit https://trustra.app/emergency-access to review this request.
    
    If you have any questions, please contact support at support@trustra.app.
    
    This is an automated message from Trustra Password Manager. Please do not reply to this email.
    """
    
    # Send the email
    return send_email(
        to_email=user.email,
        subject="Trustra - Emergency Access Request",
        text_content=text_content,
        html_content=html_content
    )

def send_emergency_access_granted_notification(user_email, requester_email):
    """Send notification that emergency access has been granted"""
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="border-bottom: 3px solid #4f46e5; padding-bottom: 20px; margin-bottom: 20px;">
            <h1 style="color: #4f46e5; margin: 0;">Trustra Password Manager</h1>
            <p style="font-size: 18px; margin: 5px 0 0;">Emergency Access Granted</p>
        </div>
        
        <p>Hello,</p>
        
        <p>Your emergency access request to <strong>{user_email}</strong>'s Trustra vault has been <strong>granted</strong>.</p>
        
        <p>You can now log in and access their vault using the emergency access option on the login page.</p>
        
        <a href="https://trustra.app/login" style="display: inline-block; background-color: #4f46e5; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; margin-top: 15px;">Log In Now</a>
        
        <p style="margin-top: 30px; font-size: 14px; color: #6b7280;">
            If you have any questions, please contact support at support@trustra.app.
        </p>
        
        <p style="font-size: 12px; color: #9ca3af; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 20px;">
            This is an automated message from Trustra Password Manager. Please do not reply to this email.
        </p>
    </body>
    </html>
    """
    
    text_content = f"""
    Trustra Password Manager - Emergency Access Granted
    
    Hello,
    
    Your emergency access request to {user_email}'s Trustra vault has been granted.
    
    You can now log in and access their vault using the emergency access option on the login page.
    
    Please visit https://trustra.app/login to log in now.
    
    If you have any questions, please contact support at support@trustra.app.
    
    This is an automated message from Trustra Password Manager. Please do not reply to this email.
    """
    
    return send_email(
        to_email=requester_email,
        subject="Trustra - Emergency Access Granted",
        text_content=text_content,
        html_content=html_content
    )

def send_emergency_access_denied_notification(user_email, requester_email):
    """Send notification that emergency access has been denied"""
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="border-bottom: 3px solid #4f46e5; padding-bottom: 20px; margin-bottom: 20px;">
            <h1 style="color: #4f46e5; margin: 0;">Trustra Password Manager</h1>
            <p style="font-size: 18px; margin: 5px 0 0;">Emergency Access Denied</p>
        </div>
        
        <p>Hello,</p>
        
        <p>Your emergency access request to <strong>{user_email}</strong>'s Trustra vault has been <strong>denied</strong>.</p>
        
        <p>If you believe this is an error, please contact the vault owner directly.</p>
        
        <p style="margin-top: 30px; font-size: 14px; color: #6b7280;">
            If you have any questions, please contact support at support@trustra.app.
        </p>
        
        <p style="font-size: 12px; color: #9ca3af; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 20px;">
            This is an automated message from Trustra Password Manager. Please do not reply to this email.
        </p>
    </body>
    </html>
    """
    
    text_content = f"""
    Trustra Password Manager - Emergency Access Denied
    
    Hello,
    
    Your emergency access request to {user_email}'s Trustra vault has been denied.
    
    If you believe this is an error, please contact the vault owner directly.
    
    If you have any questions, please contact support at support@trustra.app.
    
    This is an automated message from Trustra Password Manager. Please do not reply to this email.
    """
    
    return send_email(
        to_email=requester_email,
        subject="Trustra - Emergency Access Denied",
        text_content=text_content,
        html_content=html_content
    )