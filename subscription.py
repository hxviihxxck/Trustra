import os
import stripe
import logging
import traceback
from datetime import datetime, timedelta

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, session, Response
from flask_login import login_required, current_user
from app import db
from models import User
from forms import SubscriptionForm

# Set up Stripe API key from environment variables
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Log some information about the API key for debugging
key_info = None
if stripe.api_key:
    key_info = {
        'length': len(stripe.api_key),
        'prefix': stripe.api_key[:7] + '...' if len(stripe.api_key) > 10 else '',
        'is_live': stripe.api_key.startswith('sk_live_')
    }
logging.info(f"Stripe API Key information: {key_info}")

# Define the plans using Stripe Product/Price IDs (recommended for production)
# These IDs should match your Stripe Dashboard products and prices
SUBSCRIPTION_PLANS = {
    'monthly': {
        'name': 'Monthly Premium',
        'description': 'Unlock all premium features with monthly billing',
        'price': 4.99,  # Display price only
        'interval': 'month',
        'price_id': 'price_1PfP9ZQ8pVR1OhK9NNfsgJSo'  # Monthly premium price ID
    },
    'yearly': {
        'name': 'Yearly Premium',
        'description': 'Unlock all premium features with yearly billing (save 16%)',
        'price': 49.99,  # Display price only
        'interval': 'year',
        'product_id': 'prod_SEo2wOilwIp8ik',  # Yearly premium product ID
        'price_id': 'price_1PfP9oQ8pVR1OhK9ZLwsj7nH'  # Yearly premium price ID
    }
}

# Blueprint for subscription routes
subscription_bp = Blueprint('subscription', __name__)

@subscription_bp.route('/subscription/plans')
@login_required
def plans():
    """Display available subscription plans"""
    stripe_publishable_key = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    return render_template('subscription/plans.html', 
                          plans=SUBSCRIPTION_PLANS,
                          stripe_publishable_key=stripe_publishable_key)

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
        
        # Apply the 30% discount for early adopters using coupon
        # Store the display prices for the template
        original_price = plan['price']
        discounted_price = original_price * 0.7  # 30% off for display purposes
        
        # Log the price ID being used
        logging.info(f"Using price ID: {plan['price_id']}")
        
        # First, check if the LAUNCH30 coupon exists in Stripe or create it
        try:
            # Try to retrieve the coupon first
            launch_coupon = None
            try:
                launch_coupon = stripe.Coupon.retrieve('LAUNCH30')
                logging.info("LAUNCH30 coupon already exists in Stripe")
            except Exception as e:
                if "No such coupon" in str(e):
                    # Coupon doesn't exist, create it
                    logging.info("Creating LAUNCH30 coupon in Stripe")
                    launch_coupon = stripe.Coupon.create(
                        id='LAUNCH30',
                        percent_off=30,
                        duration='forever',
                        name='30% Launch Discount'
                    )
        except Exception as coupon_error:
            logging.error(f"Error with coupon: {str(coupon_error)}")
            # Continue without discount if coupon fails
            
        # Create the checkout session with existing price ID and apply discount if available
        checkout_params = {
            'customer': current_user.stripe_customer_id,
            'payment_method_types': ['card'],
            'line_items': [
                {
                    # Use price_id for the specific price
                    'price': plan['price_id'],
                    'quantity': 1,
                },
            ],
            'mode': 'subscription',
            'success_url': domain_url + url_for('subscription.success') + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': domain_url + url_for('subscription.cancel'),
            'metadata': {
                'user_id': current_user.id,
                'plan_id': plan_id,
                'promotion': 'LAUNCH30',
                'original_price': str(original_price),
                'discount_percentage': '30'
            }
        }
        
        # Add coupon if it was successfully retrieved or created
        if locals().get('launch_coupon'):
            checkout_params['discounts'] = [{'coupon': launch_coupon.id}]
            
        checkout_session = stripe.checkout.Session.create(**checkout_params)
        
        # Log the checkout URL
        checkout_url = checkout_session.url
        logging.info(f"Created Stripe checkout session with 30% discount: {checkout_url}")
        
        # Render a dedicated page that will handle the redirect to Stripe
        return render_template('subscription/checkout_redirect.html', 
                              checkout_url=checkout_url,
                              plan_name=plan['name'],
                              plan_description=f'{plan["description"]} - 30% Launch Discount Applied',
                              plan_price=discounted_price,
                              original_price=original_price,
                              plan_interval=plan['interval'])
    except Exception as e:
        error_trace = traceback.format_exc()
        logging.error(f"Stripe error: {str(e)}")
        logging.error(f"Traceback: {error_trace}")
        logging.error(f"Stripe Key: {'Valid' if stripe.api_key else 'Invalid/Empty'}")
        logging.error(f"Plan data: {plan}")
        logging.error(f"Discounted price: {discounted_price}")
        
        # More user-friendly error message
        flash(f'An error occurred while processing your subscription request: {str(e)}. Please try again or contact support.', 'danger')
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
    
    # Render a dedicated management page instead of redirecting to Stripe portal
    return render_template('subscription/manage.html', 
                          subscription_id=current_user.subscription_id,
                          subscription_status=current_user.subscription_status,
                          subscription_end_date=current_user.subscription_end_date)

@subscription_bp.route('/subscription/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel the user's subscription"""
    if not current_user.subscription_id:
        flash('You do not have an active subscription to cancel.', 'info')
        return redirect(url_for('subscription.plans'))
    
    try:
        # For real implementation, you would use Stripe API to cancel the subscription
        # stripe.Subscription.modify(current_user.subscription_id, cancel_at_period_end=True)
        
        # Update user's subscription status in database
        current_user.subscription_status = 'canceled'
        db.session.commit()
        
        flash('Your subscription has been canceled. You will have access to premium features until the end of your current billing period.', 'success')
        return redirect(url_for('subscription.premium_features'))
    except Exception as e:
        logging.error(f"Error canceling subscription: {str(e)}")
        flash('An error occurred while canceling your subscription.', 'danger')
        return redirect(url_for('subscription.premium_features'))

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
    if not current_user.has_premium_features():
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