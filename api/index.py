"""
Unified Flask API for Vercel deployment
Combines Reddit Analysis API + Telegram Webhooks + Stripe Payments
"""

from flask import Flask, request, jsonify
import os
import sys
import logging
import asyncio
import stripe
from datetime import datetime, timedelta
from telegram import Update, Bot
from telegram.ext import Application

# Add lib directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from database import Database

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Initialize database (will be initialized per request)
db = None

async def get_db():
    """Get or create database instance"""
    global db
    if db is None:
        db = Database()
        await db.init_pool()
    return db

# ========== HEALTH & STATUS ENDPOINTS ==========

@app.route('/')
def index():
    """API root endpoint"""
    return jsonify({
        'service': 'Reddit Analyzer Bot API',
        'version': '2.0',
        'status': 'healthy',
        'endpoints': {
            'telegram_webhook': '/webhook',
            'stripe_webhook': '/stripe-webhook',
            'health': '/health',
            'database_health': '/database-health'
        }
    })

@app.route('/health')
def health():
    """Simple health check"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/debug-env')
def debug_env():
    """Debug endpoint to check environment variables"""
    env_status = {
        'TELEGRAM_BOT_TOKEN': 'SET' if os.getenv('TELEGRAM_BOT_TOKEN') else 'NOT SET',
        'DATABASE_URL': 'SET' if os.getenv('DATABASE_URL') else 'NOT SET',
        'OPENAI_API_KEY': 'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET',
        'STRIPE_SECRET_KEY': 'SET' if os.getenv('STRIPE_SECRET_KEY') else 'NOT SET',
    }
    return jsonify({
        'status': 'ok',
        'environment_variables': env_status,
        'python_version': sys.version
    })

@app.route('/database-health')
def database_health():
    """Check database connectivity"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        database = loop.run_until_complete(get_db())

        # Test database query
        stats = loop.run_until_complete(database.get_bot_statistics())

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }), 500

# ========== STRIPE WEBHOOK ENDPOINT ==========

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe payment webhooks"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )

        logger.info(f"Received webhook event: {event['type']}")

        # Handle successful payment
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']

            # Get user and package info from metadata
            user_id = int(session['metadata']['user_id'])
            total_coins = int(session['metadata']['total_coins'])
            package_name = session['metadata'].get('package', 'Unknown')

            logger.info(f"Processing payment for user {user_id}, {total_coins} coins")

            # Add coins to user
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            database = loop.run_until_complete(get_db())

            success = loop.run_until_complete(
                database.add_coins(
                    user_id=user_id,
                    amount=total_coins,
                    transaction_type='purchase',
                    description=f"Purchased {package_name}",
                    extend_expiry=True
                )
            )

            if success:
                logger.info(f"Successfully added {total_coins} coins to user {user_id}")

                # Update payment history
                loop.run_until_complete(
                    database.update_payment_status(
                        session_id=session['id'],
                        status='completed',
                        payment_intent=session.get('payment_intent')
                    )
                )

                # Send notification to user via Telegram
                try:
                    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
                    bot = Bot(token=telegram_token)

                    # Get user's new balance
                    user_coins = loop.run_until_complete(database.get_user_coins(user_id))

                    message = (
                        f"✅ <b>Payment Successful!</b>\n\n"
                        f"🪙 {total_coins} coins have been added to your account!\n"
                        f"💰 New balance: {user_coins['balance']} coins\n\n"
                        f"Use /balance to check your balance."
                    )

                    loop.run_until_complete(
                        bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode='HTML'
                        )
                    )
                    logger.info(f"Notification sent to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            else:
                logger.error(f"Failed to add coins to user {user_id}")
                return jsonify({'error': 'Failed to add coins'}), 500

            return jsonify({'received': True}), 200

        # Handle failed payment
        elif event['type'] == 'payment_intent.payment_failed':
            session = event['data']['object']
            logger.info(f"Payment failed: {session.get('id')}")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            database = loop.run_until_complete(get_db())

            loop.run_until_complete(
                database.update_payment_status(
                    session_id=session.get('id'),
                    status='failed'
                )
            )

            return jsonify({'received': True}), 200

        return jsonify({'received': True}), 200

    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400

    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return jsonify({'error': str(e)}), 500

# ========== TELEGRAM BOT WEBHOOK ENDPOINT ==========

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Handle Telegram bot webhooks"""
    try:
        # Get the webhook update
        update_data = request.get_json()
        logger.info(f"Received Telegram webhook: {update_data}")

        # Process the update
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Import bot application
        from bot_handler import process_update

        # Process the update
        result = loop.run_until_complete(
            process_update(update_data)
        )

        return jsonify({'ok': True}), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'error': str(e)}), 500

# ========== USER & COIN MANAGEMENT ENDPOINTS ==========

@app.route('/get-user-coins/<int:user_id>')
def get_user_coins(user_id):
    """Get user coin balance"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        database = loop.run_until_complete(get_db())

        coins = loop.run_until_complete(database.get_user_coins(user_id))
        return jsonify(coins)
    except Exception as e:
        logger.error(f"Error getting user coins: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/add-coins', methods=['POST'])
def add_coins():
    """Add coins via API"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        transaction_type = data.get('transaction_type', 'admin_add')
        description = data.get('description')
        extend_expiry = data.get('extend_expiry', True)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        database = loop.run_until_complete(get_db())

        success = loop.run_until_complete(
            database.add_coins(
                user_id, amount, transaction_type,
                description, extend_expiry
            )
        )

        if success:
            coins = loop.run_until_complete(database.get_user_coins(user_id))
            return jsonify({
                'success': True,
                'new_balance': coins['balance']
            })
        else:
            return jsonify({'success': False}), 400

    except Exception as e:
        logger.error(f"Error adding coins: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/deduct-coins', methods=['POST'])
def deduct_coins():
    """Deduct coins via API"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        command = data.get('command', 'unknown')
        description = data.get('description')

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        database = loop.run_until_complete(get_db())

        success = loop.run_until_complete(
            database.deduct_coins(user_id, amount, command, description)
        )

        if success:
            coins = loop.run_until_complete(database.get_user_coins(user_id))
            return jsonify({
                'success': True,
                'new_balance': coins['balance']
            })
        else:
            return jsonify({'success': False}), 400

    except Exception as e:
        logger.error(f"Error deducting coins: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/create-user', methods=['POST'])
def create_user():
    """Create a new user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        username = data.get('username')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        added_by = data.get('added_by')

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        database = loop.run_until_complete(get_db())

        success = loop.run_until_complete(
            database.add_user(user_id, username, first_name, last_name, added_by)
        )

        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-all-users')
def get_all_users():
    """Get all users"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        database = loop.run_until_complete(get_db())

        users = loop.run_until_complete(database.get_all_users())
        return jsonify(users)
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'error': str(e)}), 500

# For local development
if __name__ == '__main__':
    app.run(debug=True, port=5000)
