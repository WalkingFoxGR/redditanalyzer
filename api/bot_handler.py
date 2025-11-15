"""
Telegram Bot Handler for Webhook Mode (Vercel)
Processes Telegram updates via webhooks instead of polling
"""

import os
import sys
import logging
import asyncio
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode
import stripe

# Setup logging first
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

from payment import PaymentProcessor

# Initialize components
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')

# Global application instance
application = None
db = None

async def init_application():
    """Initialize bot application"""
    global application, db

    # For serverless: always create new application to avoid event loop conflicts
    # Each request gets its own event loop, so we can't reuse the application

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Initialize database (Supabase doesn't need DATABASE_URL parameter)
    if db is None:
        db = Database()
        await db.init_pool()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("niche", niche_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("requirements", requirements_command))
    application.add_handler(CommandHandler("compare", compare_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Initialize application
    await application.initialize()
    await application.start()

    return application

async def process_update(update_data: Dict[str, Any]):
    """Process incoming webhook update"""
    try:
        # Initialize application
        app = await init_application()

        # Create Update object from JSON
        update = Update.de_json(update_data, app.bot)

        # Process the update
        await app.process_update(update)

        return {'success': True}
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        raise

# ========== COMMAND HANDLERS ==========

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user

    # Register or update user in database
    await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    welcome_message = f"""
👋 <b>Welcome to Reddit Analyzer Bot!</b>

Hi {user.first_name}! I help you discover the best subreddits for your content.

<b>🎁 You've received 10 FREE coins to get started!</b>

<b>Key Features:</b>
• Analyze subreddit engagement & requirements
• Find niche communities for your content
• Compare multiple subreddits
• Search for relevant communities
• Get posting rules & requirements

<b>Quick Start:</b>
• /balance - Check your coin balance
• /analyze <i>subreddit</i> - Analyze a subreddit (2 coins)
• /search <i>topic</i> - Find subreddits (1 coin)
• /help - See all commands

<b>Need more coins?</b> Use /buy to purchase coin packages!

Let's find the perfect subreddits for your content! 🚀
"""

    await update.message.reply_text(welcome_message, parse_mode=ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
<b>📚 Available Commands</b>

<b>Analysis Commands:</b>
• /analyze &lt;subreddit&gt; - Deep analysis (2 coins)
• /search &lt;topic&gt; - Find subreddits (1 coin)
• /niche &lt;topic&gt; - Find niche communities (3 coins)
• /compare &lt;sub1,sub2,sub3&gt; - Compare subreddits (5 coins)
• /rules &lt;subreddit&gt; - Get posting rules (1 coin)
• /requirements &lt;subreddit&gt; - Check karma requirements (2 coins)

<b>Account Commands:</b>
• /balance - Check your coins
• /buy - Purchase more coins
• /help - Show this message

<b>Admin Commands:</b>
• /admin - Admin panel
• /users - List all users
• /stats - Bot statistics

<b>Coin Costs:</b>
💰 Most commands cost 1-5 coins
🎁 New users get 10 free coins
💳 Purchase packages with /buy

Need help? Just ask!
"""

    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command"""
    user = update.effective_user

    # Get user coins
    coins_data = await db.get_user_coins(user.id)

    if coins_data['is_admin']:
        message = f"""
🎯 <b>Admin Account</b>

💰 Balance: ♾️ Unlimited Coins
👑 Status: Administrator

You have unlimited access to all features!
"""
    else:
        balance = coins_data['balance']
        expires_at = coins_data.get('expires_at')
        is_expired = coins_data['is_expired']

        if is_expired:
            message = f"""
⚠️ <b>Coins Expired</b>

💰 Current Balance: 0 coins
⏰ Your coins have expired

Use /buy to purchase more coins!
"""
        else:
            from datetime import datetime
            if expires_at:
                expiry_date = datetime.fromisoformat(expires_at).strftime('%B %d, %Y')
                message = f"""
💰 <b>Your Coin Balance</b>

🪙 Balance: {balance} coins
⏰ Expires: {expiry_date}

Use /buy to add more coins!
"""
            else:
                message = f"""
💰 <b>Your Coin Balance</b>

🪙 Balance: {balance} coins

Use /buy to add more coins!
"""

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buy command - show coin packages"""
    user = update.effective_user

    # Get packages
    packages = await db.get_coin_packages()

    if not packages:
        await update.message.reply_text("⚠️ No packages available at the moment.")
        return

    message = "<b>💳 Coin Packages</b>\n\n"
    message += "Choose a package to purchase:\n\n"

    keyboard = []

    for pkg in packages:
        pkg_name = pkg['package_name']
        coins = pkg['coins']
        bonus = pkg['bonus_coins']
        price = pkg['price_usd']

        total_coins = coins + bonus

        message += f"<b>{pkg_name}</b>\n"
        message += f"• {coins} coins"
        if bonus > 0:
            message += f" + {bonus} bonus = {total_coins} total"
        message += f"\n• ${price:.2f}\n\n"

        # Create button
        keyboard.append([
            InlineKeyboardButton(
                f"💳 {pkg_name} - ${price:.2f}",
                callback_data=f"buy_{pkg_name.lower().replace(' ', '_')}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data

    # Handle buy button
    if data.startswith('buy_'):
        package_name = data.replace('buy_', '').replace('_', ' ').title()

        # Get package details
        packages = await db.get_coin_packages()
        package = next((p for p in packages if p['package_name'].lower() == package_name.lower()), None)

        if not package:
            await query.edit_message_text("⚠️ Package not found.")
            return

        # Create Stripe checkout session
        stripe.api_key = STRIPE_SECRET_KEY

        total_coins = package['coins'] + package['bonus_coins']

        try:
            # Create checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': package['package_name'],
                            'description': f"{total_coins} coins ({package['coins']} + {package['bonus_coins']} bonus)"
                        },
                        'unit_amount': int(package['price_usd'] * 100)
                    },
                    'quantity': 1
                }],
                mode='payment',
                success_url=f"https://t.me/{context.bot.username}?start=payment_success",
                cancel_url=f"https://t.me/{context.bot.username}?start=payment_cancelled",
                metadata={
                    'user_id': str(user.id),
                    'package': package['package_name'],
                    'total_coins': str(total_coins)
                }
            )

            # Save payment to database
            await db.add_payment_history(
                user_id=user.id,
                session_id=session.id,
                amount_usd=package['price_usd'],
                coins_purchased=total_coins,
                status='pending'
            )

            # Send payment link
            keyboard = [[InlineKeyboardButton("💳 Complete Payment", url=session.url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"💳 <b>Payment Link Created!</b>\n\n"
                f"Package: {package['package_name']}\n"
                f"Coins: {total_coins}\n"
                f"Price: ${package['price_usd']:.2f}\n\n"
                f"Click the button below to complete your purchase securely.",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            await query.edit_message_text(
                "⚠️ Error creating payment link. Please try again later."
            )

# ========== ANALYSIS COMMANDS (Placeholder - implement with Reddit API) ==========

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /analyze command"""
    user = update.effective_user

    # Check coins
    coins_data = await db.get_user_coins(user.id)
    command_cost = await db.get_command_cost('analyze')

    if not coins_data['is_admin'] and coins_data['balance'] < command_cost:
        await update.message.reply_text(
            f"⚠️ Insufficient coins! This command costs {command_cost} coins.\n"
            f"Your balance: {coins_data['balance']} coins\n\n"
            f"Use /buy to purchase more coins!"
        )
        return

    # Get subreddit name
    if not context.args:
        await update.message.reply_text(
            "Usage: /analyze <subreddit>\nExample: /analyze technology"
        )
        return

    subreddit = context.args[0].replace('r/', '')

    # Deduct coins
    if not coins_data['is_admin']:
        await db.deduct_coins(user.id, command_cost, 'analyze', f"Analyzed r/{subreddit}")

    # Send processing message
    await update.message.reply_text(
        f"🔍 Analyzing r/{subreddit}...\n\n"
        f"⚠️ <b>Note:</b> Reddit API integration needed.\n"
        f"This is a placeholder. Connect to Reddit API for full analysis.",
        parse_mode=ParseMode.HTML
    )

    # TODO: Implement Reddit API call here
    # You'll need to add the Reddit API endpoints to the Flask API
    # or call them directly from PRAW

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command"""
    await update.message.reply_text(
        "🔍 Search feature - implement with Reddit API\n"
        "Usage: /search <topic>"
    )

async def niche_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /niche command"""
    await update.message.reply_text(
        "🎯 Niche discovery - implement with Reddit API\n"
        "Usage: /niche <topic>"
    )

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rules command"""
    await update.message.reply_text(
        "📋 Rules check - implement with Reddit API\n"
        "Usage: /rules <subreddit>"
    )

async def requirements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /requirements command"""
    await update.message.reply_text(
        "✅ Requirements check - implement with Reddit API\n"
        "Usage: /requirements <subreddit>"
    )

async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /compare command"""
    await update.message.reply_text(
        "📊 Comparison - implement with Reddit API\n"
        "Usage: /compare sub1,sub2,sub3"
    )

# ========== ADMIN COMMANDS ==========

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command"""
    user = update.effective_user

    is_admin = await db.is_admin(user.id)

    if not is_admin:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return

    keyboard = [
        [InlineKeyboardButton("👥 View Users", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("💰 Add Coins to User", callback_data="admin_addcoins")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👑 <b>Admin Panel</b>\n\nSelect an option:",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /users command - show all users"""
    user = update.effective_user

    is_admin = await db.is_admin(user.id)

    if not is_admin:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return

    users = await db.get_all_users()

    if not users:
        await update.message.reply_text("No users found.")
        return

    message = "<b>👥 Registered Users</b>\n\n"

    for u in users[:20]:  # Limit to 20 users
        admin_badge = "👑 " if u['is_admin'] else ""
        status = "✅" if u['is_active'] else "❌"
        username = u['username'] or "No username"
        name = u['first_name'] or "Unknown"

        message += f"{admin_badge}{status} <b>{name}</b> (@{username})\n"
        message += f"   ID: {u['user_id']} | Coins: {u['coin_balance']}\n\n"

    if len(users) > 20:
        message += f"\n... and {len(users) - 20} more users"

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user = update.effective_user

    is_admin = await db.is_admin(user.id)

    if not is_admin:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return

    stats = await db.get_bot_statistics()

    message = "<b>📊 Bot Statistics</b>\n\n"
    message += f"👥 Total Users: {stats.get('total_users', 0)}\n"
    message += f"✅ Active Users: {stats.get('active_users', 0)}\n"
    message += f"⚡ Commands (24h): {stats.get('commands_24h', 0)}\n\n"

    if stats.get('top_commands'):
        message += "<b>Top Commands (7 days):</b>\n"
        for cmd in stats['top_commands'][:5]:
            message += f"• /{cmd['command']}: {cmd['count']} uses\n"

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)
