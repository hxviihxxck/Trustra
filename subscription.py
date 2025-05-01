import os
import stripe
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, session
from flask_login import login_required, current_user
from app import db
from models import User
from forms import SubscriptionForm

# Set up Stripe API key from environment variables
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Define the plans - these should match your Stripe product/price IDs
# For development/testing, we'll use the test mode functionality instead of specific price IDs
# This approach uses the price parameter directly instead of a price ID
SUBSCRIPTION_PLANS = {
    'monthly': {
        'name': 'Monthly Premium',
        'description': 'Unlock all premium features with monthly billing',
        'price': 4.99,
        'interval': 'month'
    },
    'yearly': {
        'name': 'Yearly Premium',
        'description': 'Unlock all premium features with yearly billing (save 16%)',
        'price': 49.99,
        'interval': 'year'
    }
}

# Blueprint for subscription routes
subscription_bp = Blueprint('subscription', __name__)

@subscription_bp.route('/subscription/plans')
@login_required
def plans():
    """Display available subscription plans"""
    return render_template('subscription/plans.html', plans=SUBSCRIPTION_PLANS)

@subscription_bp.route('/subscription/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe checkout session for subscription"""
    plan_id = request.form.get('plan_id')
    
    if plan_id not in SUBSCRIPTION_PLANS:
        flash('Invalid subscription plan selected.', 'danger')
        return redirect(url_for('subscription.plans'))
    
    plan = SUBSCRIPTION_PLANS[plan_id]
    
    # Determine the domain to use for success/cancel URLs
    domain_url = request.host_url.rstrip('/')
    
    try:
        # Create a new customer in Stripe if the user doesn't have one
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.username,
                metadata={
                    'user_id': current_user.id
                }
            )
            current_user.stripe_customer_id = customer.id
            db.session.commit()
        
        # Create the checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'SecureVault Premium - {plan["name"]}',
                            'description': plan['description'],
                        },
                        'unit_amount': int(plan['price'] * 100),  # Convert dollars to cents
                        'recurring': {
                            'interval': plan['interval'],
                        }
                    },
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=domain_url + url_for('subscription.success') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=domain_url + url_for('subscription.cancel'),
            metadata={
                'user_id': current_user.id,
                'plan_id': plan_id
            }
        )
        
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        logging.error(f"Stripe error: {str(e)}")
        flash('An error occurred while processing your subscription request. Please try again.', 'danger')
        return redirect(url_for('subscription.plans'))

@subscription_bp.route('/subscription/success')
@login_required
def success():
    """Handle successful subscription checkout"""
    session_id = request.args.get('session_id')
    
    if not session_id:
        flash('Invalid checkout session.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        # Retrieve the checkout session to get subscription details
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        subscription_id = checkout_session.subscription
        
        # Update user with subscription information
        current_user.subscription_id = subscription_id
        current_user.is_premium = True
        current_user.subscription_status = 'active'
        
        # Set subscription end date based on subscription period
        subscription = stripe.Subscription.retrieve(subscription_id)
        end_timestamp = subscription.current_period_end
        current_user.subscription_end_date = datetime.fromtimestamp(end_timestamp)
        
        db.session.commit()
        
        flash('Subscription activated successfully! You now have access to all premium features.', 'success')
        return redirect(url_for('subscription.premium_features'))
    except Exception as e:
        logging.error(f"Error processing subscription success: {str(e)}")
        flash('There was an issue activating your subscription. Please contact support.', 'danger')
        return redirect(url_for('dashboard'))

@subscription_bp.route('/subscription/cancel')
@login_required
def cancel():
    """Handle canceled checkout"""
    flash('Subscription checkout was canceled. No charges were made.', 'info')
    return redirect(url_for('subscription.plans'))

@subscription_bp.route('/subscription/manage')
@login_required
def manage():
    """Manage existing subscription"""
    if not current_user.subscription_id:
        flash('You do not have an active subscription to manage.', 'info')
        return redirect(url_for('subscription.plans'))
    
    try:
        # Create a Stripe customer portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=request.host_url.rstrip('/') + url_for('subscription.portal_return'),
        )
        return redirect(portal_session.url, code=303)
    except Exception as e:
        logging.error(f"Stripe portal error: {str(e)}")
        flash('An error occurred while accessing your subscription management portal.', 'danger')
        return redirect(url_for('dashboard'))

@subscription_bp.route('/subscription/portal-return')
@login_required
def portal_return():
    """Handle return from customer portal"""
    flash('Your subscription settings have been updated.', 'success')
    return redirect(url_for('dashboard'))

@subscription_bp.route('/subscription/premium-features')
@login_required
def premium_features():
    """Display and configure premium features"""
    if not current_user.has_premium_features:
        flash('This page is only accessible to premium subscribers.', 'warning')
        return redirect(url_for('subscription.plans'))
    
    return render_template('subscription/premium_features.html')

@subscription_bp.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    # This endpoint should be configured in the Stripe dashboard and the signing secret set in environment variables
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    
    event = None
    
    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        else:
            # For development purposes, we can parse the payload directly
            event = stripe.Event.construct_from(
                request.json, stripe.api_key
            )
    except Exception as e:
        logging.error(f"Webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 400
    
    # Handle the event
    if event.type == 'customer.subscription.updated':
        subscription = event.data.object
        handle_subscription_updated(subscription)
    elif event.type == 'customer.subscription.deleted':
        subscription = event.data.object
        handle_subscription_deleted(subscription)
    
    return jsonify({'status': 'success'})

def handle_subscription_updated(subscription):
    """Handle subscription updated event"""
    customer_id = subscription.customer
    status = subscription.status
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        logging.error(f"Unknown customer ID in subscription update: {customer_id}")
        return
    
    user.subscription_status = status
    
    if status == 'active':
        user.is_premium = True
        user.subscription_end_date = datetime.fromtimestamp(subscription.current_period_end)
    elif status in ['past_due', 'unpaid', 'canceled', 'incomplete_expired']:
        # Don't revoke premium immediately on past_due, give a grace period
        if status == 'canceled':
            user.is_premium = False
    
    db.session.commit()
    logging.info(f"Updated subscription status for user {user.id} to {status}")

def handle_subscription_deleted(subscription):
    """Handle subscription deleted event"""
    customer_id = subscription.customer
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        logging.error(f"Unknown customer ID in subscription deletion: {customer_id}")
        return
    
    user.is_premium = False
    user.subscription_status = 'canceled'
    user.subscription_id = None
    
    db.session.commit()
    logging.info(f"Subscription canceled for user {user.id}")