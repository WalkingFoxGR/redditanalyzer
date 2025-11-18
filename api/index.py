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

# Setup logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add lib directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

# Use Supabase database for Vercel compatibility
try:
    from database_supabase import SupabaseDatabase as Database
    logger.info("Using Supabase REST API for database")
except ImportError:
    from database import Database
    logger.info("Using asyncpg for database")

# Import Reddit scraper
from reddit_scraper import RedditScraper

app = Flask(__name__)

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
        'REDDIT_CLIENT_ID': 'SET' if os.getenv('REDDIT_CLIENT_ID') else 'NOT SET',
        'REDDIT_CLIENT_SECRET': 'SET' if os.getenv('REDDIT_CLIENT_SECRET') else 'NOT SET',
        'REDDIT_USER_AGENT': 'SET' if os.getenv('REDDIT_USER_AGENT') else 'NOT SET',
        'SUPABASE_URL': 'SET' if os.getenv('SUPABASE_URL') else 'NOT SET',
        'SUPABASE_ANON_KEY': 'SET' if os.getenv('SUPABASE_ANON_KEY') else 'NOT SET',
    }
    return jsonify({
        'status': 'ok',
        'environment_variables': env_status,
        'python_version': sys.version
    })

@app.route('/test-bot-import')
def test_bot_import():
    """Test if bot_handler can be imported"""
    try:
        # Add api directory to path for Vercel
        api_dir = os.path.dirname(__file__)
        if api_dir not in sys.path:
            sys.path.insert(0, api_dir)

        # Try to import bot_handler
        from bot_handler import process_update

        return jsonify({
            'status': 'ok',
            'bot_handler': 'imported successfully',
            'process_update': str(type(process_update)),
            'api_dir': api_dir
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__,
            'sys_path': sys.path,
            'current_file': __file__
        }), 500

@app.route('/database-health')
def database_health():
    """Check database connectivity"""
    try:
        async def check_db():
            database = await get_db()
            stats = await database.get_bot_statistics()
            return stats

        stats = run_async(check_db())

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

# ========== REDDIT API ENDPOINTS ==========

# Initialize Reddit scraper (lazy initialization)
reddit_scraper = None

def get_reddit_scraper():
    """Get or create Reddit scraper instance"""
    global reddit_scraper
    if reddit_scraper is None:
        reddit_scraper = RedditScraper()
    return reddit_scraper

def run_async(coro):
    """Helper to run async code in Flask synchronous context with proper cleanup"""
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        if loop:
            try:
                # Clean up any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                # Close the loop properly
                loop.close()
            except Exception as e:
                logger.warning(f"Error closing event loop: {e}")

@app.route('/reddit/analyze', methods=['POST'])
def reddit_analyze():
    """Analyze a subreddit"""
    try:
        data = request.get_json()
        subreddit = data.get('subreddit')
        days = data.get('days', 7)

        if not subreddit:
            return jsonify({'error': 'Subreddit name required'}), 400

        scraper = get_reddit_scraper()
        result = run_async(scraper.analyze_subreddit(subreddit, days))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in reddit analyze: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reddit/search', methods=['POST'])
def reddit_search():
    """Search for subreddits"""
    try:
        data = request.get_json()
        query = data.get('query')
        limit = data.get('limit', 100)

        if not query:
            return jsonify({'error': 'Query required'}), 400

        scraper = get_reddit_scraper()
        result = run_async(scraper.search_subreddits(query, limit))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in reddit search: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reddit/search-and-analyze', methods=['POST'])
def reddit_search_and_analyze():
    """Search and analyze subreddits (niche discovery)"""
    try:
        data = request.get_json()
        query = data.get('query')
        limit = data.get('limit', 100)
        days = data.get('days', 7)

        if not query:
            return jsonify({'error': 'Query required'}), 400

        async def search_and_analyze_async():
            scraper = get_reddit_scraper()

            # Search for subreddits
            search_result = await scraper.search_subreddits(query, limit)

            if not search_result.get('success'):
                return search_result

            # Analyze top subreddits
            subreddits = search_result['results'][:10]  # Analyze top 10
            analyzed = []

            for sub in subreddits:
                analysis = await scraper.analyze_subreddit(sub['display_name'], days)
                if analysis.get('success'):
                    analyzed.append(analysis)

            return {
                'success': True,
                'results': analyzed,
                'count': len(analyzed)
            }

        result = run_async(search_and_analyze_async())
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in search and analyze: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reddit/analyze-multiple', methods=['POST'])
def reddit_analyze_multiple():
    """Analyze multiple subreddits for comparison"""
    try:
        data = request.get_json()
        subreddits_str = data.get('subreddits', '')
        days = data.get('days', 7)

        subreddits = [s.strip() for s in subreddits_str.split(',')]

        if not subreddits:
            return jsonify({'error': 'Subreddits required'}), 400

        async def analyze_multiple_async():
            scraper = get_reddit_scraper()
            results = []

            for subreddit in subreddits:
                result = await scraper.analyze_subreddit(subreddit, days)
                if result.get('success'):
                    results.append(result)

            return {
                'success': True,
                'results': results,
                'count': len(results)
            }

        result = run_async(analyze_multiple_async())
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in analyze multiple: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reddit/rules', methods=['POST'])
def reddit_rules():
    """Get subreddit rules"""
    try:
        data = request.get_json()
        subreddit = data.get('subreddit')

        if not subreddit:
            return jsonify({'error': 'Subreddit name required'}), 400

        scraper = get_reddit_scraper()
        result = run_async(scraper.get_rules(subreddit))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting rules: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reddit/requirements', methods=['POST'])
def reddit_requirements():
    """Analyze posting requirements"""
    try:
        data = request.get_json()
        subreddit = data.get('subreddit')

        if not subreddit:
            return jsonify({'error': 'Subreddit name required'}), 400

        scraper = get_reddit_scraper()
        result = run_async(scraper.analyze_requirements(subreddit))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error analyzing requirements: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reddit/flairs', methods=['POST'])
def reddit_flairs():
    """Analyze flair performance"""
    try:
        data = request.get_json()
        subreddit = data.get('subreddit')

        if not subreddit:
            return jsonify({'error': 'Subreddit name required'}), 400

        scraper = get_reddit_scraper()
        result = run_async(scraper.analyze_flairs(subreddit))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error analyzing flairs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reddit/scrape', methods=['POST'])
def reddit_scrape():
    """Scrape posts from subreddit"""
    try:
        data = request.get_json()
        subreddit = data.get('subreddit')
        limit = data.get('limit', 50)
        sort = data.get('sort', 'hot')
        time_filter = data.get('time_filter', 'week')

        if not subreddit:
            return jsonify({'error': 'Subreddit name required'}), 400

        scraper = get_reddit_scraper()
        result = run_async(scraper.scrape_posts(subreddit, limit, sort, time_filter))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error scraping posts: {e}")
        return jsonify({'error': str(e)}), 500

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

            async def process_payment():
                database = await get_db()

                success = await database.add_coins(
                    user_id=user_id,
                    amount=total_coins,
                    transaction_type='purchase',
                    description=f"Purchased {package_name}",
                    extend_expiry=True
                )

                if success:
                    logger.info(f"Successfully added {total_coins} coins to user {user_id}")

                    # Update payment history
                    await database.update_payment_status(
                        session_id=session['id'],
                        status='completed',
                        payment_intent=session.get('payment_intent')
                    )

                    # Send notification to user via Telegram
                    try:
                        telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
                        bot = Bot(token=telegram_token)

                        # Get user's new balance
                        user_coins = await database.get_user_coins(user_id)

                        message = (
                            f"✅ <b>Payment Successful!</b>\n\n"
                            f"🪙 {total_coins} coins have been added to your account!\n"
                            f"💰 New balance: {user_coins['balance']} coins\n\n"
                            f"Use /balance to check your balance."
                        )

                        await bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode='HTML'
                        )
                        logger.info(f"Notification sent to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")
                    return True
                else:
                    logger.error(f"Failed to add coins to user {user_id}")
                    return False

            success = run_async(process_payment())
            if not success:
                return jsonify({'error': 'Failed to add coins'}), 500

            return jsonify({'received': True}), 200

        # Handle failed payment
        elif event['type'] == 'payment_intent.payment_failed':
            session = event['data']['object']
            logger.info(f"Payment failed: {session.get('id')}")

            async def process_failed_payment():
                database = await get_db()
                await database.update_payment_status(
                    session_id=session.get('id'),
                    status='failed'
                )

            run_async(process_failed_payment())
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

# Import bot handler at module level for performance
try:
    # Add api directory to path for Vercel serverless environment
    api_dir = os.path.dirname(__file__)
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)

    from bot_handler import process_update
    logger.info("Bot handler imported at module level")
except ImportError as e:
    logger.error(f"Failed to import bot_handler at module level: {e}")
    process_update = None

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Handle Telegram bot webhooks"""
    try:
        # Check if bot_handler was imported successfully
        if process_update is None:
            logger.error("Bot handler not available")
            return jsonify({'ok': False, 'error': 'Bot handler not available'}), 500

        # Get the webhook update
        update_data = request.get_json()
        logger.info(f"Received Telegram webhook update")

        # Process the update using run_async helper
        result = run_async(process_update(update_data))
        logger.info(f"Update processed successfully: {result}")

        return jsonify({'ok': True}), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Return 200 to prevent Telegram from retrying
        # Log the error but don't fail the webhook
        return jsonify({'ok': True, 'error_logged': str(e)}), 200

# ========== USER & COIN MANAGEMENT ENDPOINTS ==========

@app.route('/get-user-coins/<int:user_id>')
def get_user_coins(user_id):
    """Get user coin balance"""
    try:
        async def get_coins():
            database = await get_db()
            return await database.get_user_coins(user_id)

        coins = run_async(get_coins())
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

        async def add_coins_async():
            database = await get_db()
            success = await database.add_coins(
                user_id, amount, transaction_type,
                description, extend_expiry
            )
            if success:
                coins = await database.get_user_coins(user_id)
                return {
                    'success': True,
                    'new_balance': coins['balance']
                }
            else:
                return {'success': False}

        result = run_async(add_coins_async())
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400

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

        async def deduct_coins_async():
            database = await get_db()
            success = await database.deduct_coins(user_id, amount, command, description)
            if success:
                coins = await database.get_user_coins(user_id)
                return {
                    'success': True,
                    'new_balance': coins['balance']
                }
            else:
                return {'success': False}

        result = run_async(deduct_coins_async())
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400

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

        async def create_user_async():
            database = await get_db()
            return await database.add_user(user_id, username, first_name, last_name, added_by)

        success = run_async(create_user_async())
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-all-users')
def get_all_users():
    """Get all users"""
    try:
        async def get_users():
            database = await get_db()
            return await database.get_all_users()

        users = run_async(get_users())
        return jsonify(users)
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'error': str(e)}), 500

# For local development
if __name__ == '__main__':
    app.run(debug=True, port=5000)
