"""
Telegram Bot Handler for Webhook Mode (Vercel) - FULL VERSION
Complete Reddit Analyzer Bot with all features
"""

import os
import sys
import logging
import asyncio
import time
from typing import Dict, Any
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode, ChatAction
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

# Import Reddit functionality
from reddit_api import RedditAPI
from openai_analyzer import OpenAIAnalyzer
from utils import format_number, escape_html

# Initialize components
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# Use Vercel deployment URL or localhost for Reddit API
VERCEL_URL = os.getenv('VERCEL_URL', 'https://redditanalyzer-kappa.vercel.app')
REDDIT_API_URL = os.getenv('REDDIT_API_URL', VERCEL_URL)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')

# Global application instance
application = None
db = None
reddit_api = None
ai_analyzer = None

async def init_application():
    """Initialize bot application"""
    global application, db, reddit_api, ai_analyzer

    # For serverless: always create new application to avoid event loop conflicts
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Initialize database (Supabase doesn't need DATABASE_URL parameter)
    if db is None:
        db = Database()
        await db.init_pool()

    # Initialize Reddit API and AI Analyzer
    if reddit_api is None:
        reddit_api = RedditAPI(REDDIT_API_URL)

    if ai_analyzer is None and OPENAI_API_KEY:
        ai_analyzer = OpenAIAnalyzer(OPENAI_API_KEY)

    # ===== BASIC COMMANDS =====
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("buy", buy_command))

    # ===== ANALYSIS COMMANDS =====
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("niche", niche_command))
    application.add_handler(CommandHandler("compare", compare_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("requirements", requirements_command))
    application.add_handler(CommandHandler("flairs", flairs_command))
    application.add_handler(CommandHandler("scrape", scrape_command))

    # ===== ADMIN COMMANDS =====
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("addcoins", add_coins_command))
    application.add_handler(CommandHandler("setcoins", set_coins_command))
    application.add_handler(CommandHandler("makeadmin", makeadmin_command))
    application.add_handler(CommandHandler("announce", announce_command))

    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Initialize application (webhook mode - don't start update fetcher)
    await application.initialize()

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

# ========== HELPER FUNCTIONS ==========

def sanitize_error_message(error_msg: str) -> str:
    """Remove sensitive information from error messages"""
    import re
    error_msg = re.sub(r'https?://[^\s]+', '[API endpoint]', error_msg)
    error_msg = re.sub(r'/[\w/]+\.[\w]+', '[file path]', error_msg)
    return error_msg

# ========== BASIC COMMAND HANDLERS ==========

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
• Scrape top posts for analysis

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
• /flairs &lt;subreddit&gt; - Analyze flair performance (2 coins)
• /scrape &lt;subreddit&gt; [limit] - Scrape top posts (3 coins)

<b>Account Commands:</b>
• /balance - Check your coins
• /buy - Purchase more coins
• /help - Show this message

<b>Admin Commands:</b>
• /admin - Admin panel
• /users - List all users
• /stats - Bot statistics
• /addcoins &lt;user_id&gt; &lt;amount&gt; - Add coins
• /setcoins &lt;user_id&gt; &lt;amount&gt; - Set coin balance
• /makeadmin &lt;user_id&gt; - Make user admin
• /announce &lt;message&gt; - Send announcement

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
            if expires_at:
                expiry_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00')).strftime('%B %d, %Y')
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

# ========== ANALYSIS COMMANDS ==========

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

    subreddit = context.args[0].replace('r/', '').replace('/r/', '')

    # Deduct coins
    if not coins_data['is_admin']:
        await db.deduct_coins(user.id, command_cost, 'analyze', f"Analyzed r/{subreddit}")

    # Send processing message
    msg = await update.message.reply_text(
        f"🔍 <b>Analyzing r/{escape_html(subreddit)}...</b>\n\n"
        "⏳ This may take 30-90 seconds for accurate results.",
        parse_mode=ParseMode.HTML
    )

    try:
        # Analyze subreddit
        result = await reddit_api.analyze_subreddit(subreddit)

        if "error" in result:
            error_msg = sanitize_error_message(result.get('error', 'Unknown error'))
            await msg.edit_text(
                f"❌ Error: {escape_html(error_msg)}",
                parse_mode=ParseMode.HTML
            )
            return

        if not result.get('success'):
            await msg.edit_text(
                "❌ Analysis failed. Please try again.",
                parse_mode=ParseMode.HTML
            )
            return

        # Format metrics
        metrics_overview = (
            f"📊 <b>Analysis for r/{subreddit}</b>\n\n"
            f"🔢 Effectiveness: {result['effectiveness_score']}/100\n"
            f"👥 Subscribers: {format_number(result['subscribers'])}\n"
            f"📝 Posts/Day: {result['avg_posts_per_day']:.1f}\n"
            f"⭐ Avg Score: {result['avg_score_per_post']:.1f}\n"
            f"📊 Median Score: {result['median_score_per_post']:.1f}\n"
            f"💬 Avg Comments: {result['avg_comments_per_post']:.1f}\n"
            f"📅 Period: {result['days_analyzed']} days\n\n"
        )

        # Add top post if available
        if result.get('top_post'):
            tp = result['top_post']
            metrics_overview += (
                f"🏆 <b>TOP POST:</b> \"{tp['title'][:80]}...\"\n"
                f"   by u/{tp['author']}\n"
                f"   📈 {tp['score']} upvotes, {tp['comments']} comments\n\n"
            )

        # Get AI analysis if available
        if ai_analyzer and result.get('success'):
            ai_prompt = f"""Analyze this subreddit data:

SUBREDDIT: r/{result['subreddit']}
Subscribers: {format_number(result['subscribers'])}
Effectiveness Score: {result['effectiveness_score']}/100
Average score: {result['avg_score_per_post']:.1f}
Median score: {result['median_score_per_post']:.1f}
Average comments: {result['avg_comments_per_post']:.1f}
Posts/day: {result['avg_posts_per_day']:.1f}

Provide a verdict on whether this is good for content marketing."""

            ai_response = await ai_analyzer.analyze_subreddit(ai_prompt)
            final_response = metrics_overview + "\n" + ai_response

            if len(final_response) > 4000:
                await msg.edit_text(metrics_overview, parse_mode=ParseMode.HTML)
                await update.message.reply_text(ai_response, parse_mode=ParseMode.HTML)
            else:
                await msg.edit_text(final_response, parse_mode=ParseMode.HTML)
        else:
            await msg.edit_text(metrics_overview, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in analyze command: {e}")
        await msg.edit_text(
            "❌ An error occurred during analysis. Please try again.",
            parse_mode=ParseMode.HTML
        )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command"""
    user = update.effective_user

    # Check coins
    coins_data = await db.get_user_coins(user.id)
    command_cost = await db.get_command_cost('search')

    if not coins_data['is_admin'] and coins_data['balance'] < command_cost:
        await update.message.reply_text(
            f"⚠️ Insufficient coins! This command costs {command_cost} coins.\n"
            f"Your balance: {coins_data['balance']} coins\n\n"
            f"Use /buy to purchase more coins!"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /search <topic>\nExample: /search programming"
        )
        return

    query = " ".join(context.args)

    # Deduct coins
    if not coins_data['is_admin']:
        await db.deduct_coins(user.id, command_cost, 'search', f"Searched for {query}")

    msg = await update.message.reply_text(
        f"🔍 Searching for subreddits about '{escape_html(query)}'...",
        parse_mode=ParseMode.HTML
    )

    try:
        result = await reddit_api.search_subreddits(query)

        if "error" in result:
            await msg.edit_text(f"❌ Error: {escape_html(result['error'])}", parse_mode=ParseMode.HTML)
            return

        subreddits = result.get('results', [])

        if not subreddits:
            await msg.edit_text("No subreddits found for your query.", parse_mode=ParseMode.HTML)
            return

        response = f"<b>🔍 Search Results for '{escape_html(query)}'</b>\n\n"
        response += f"Found {len(subreddits)} subreddits:\n\n"

        for i, sub in enumerate(subreddits[:20], 1):
            name = sub.get('display_name', 'Unknown')
            members = format_number(sub.get('subscribers', 0))
            desc = sub.get('public_description', '')[:100]
            response += f"{i}. <b>r/{name}</b> ({members} members)\n"
            if desc:
                response += f"   <i>{escape_html(desc)}...</i>\n"
            response += "\n"

        await msg.edit_text(response[:4000], parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in search command: {e}")
        await msg.edit_text("❌ Search failed. Please try again.", parse_mode=ParseMode.HTML)

async def niche_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /niche command"""
    user = update.effective_user

    coins_data = await db.get_user_coins(user.id)
    command_cost = await db.get_command_cost('niche')

    if not coins_data['is_admin'] and coins_data['balance'] < command_cost:
        await update.message.reply_text(
            f"⚠️ Insufficient coins! This command costs {command_cost} coins.\n"
            f"Your balance: {coins_data['balance']} coins"
        )
        return

    if not context.args:
        await update.message.reply_text("Usage: /niche <topic>\nExample: /niche python programming")
        return

    query = " ".join(context.args)

    if not coins_data['is_admin']:
        await db.deduct_coins(user.id, command_cost, 'niche', f"Niche search for {query}")

    msg = await update.message.reply_text(
        f"🎯 Finding niche communities for '{escape_html(query)}'...\n"
        "This may take 1-2 minutes...",
        parse_mode=ParseMode.HTML
    )

    try:
        result = await reddit_api.search_and_analyze(query)

        if "error" in result:
            await msg.edit_text(f"❌ Error: {escape_html(result['error'])}", parse_mode=ParseMode.HTML)
            return

        subreddits = result.get('results', [])

        if not subreddits:
            await msg.edit_text("No niche communities found.", parse_mode=ParseMode.HTML)
            return

        response = f"<b>🎯 Niche Communities for '{escape_html(query)}'</b>\n\n"
        response += f"Found {len(subreddits)} communities:\n\n"

        for i, sub in enumerate(subreddits[:15], 1):
            name = sub.get('display_name', 'Unknown')
            score = sub.get('effectiveness_score', 0)
            members = format_number(sub.get('subscribers', 0))
            emoji = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"

            response += f"{i}. {emoji} <b>r/{name}</b> (Score: {score}/100)\n"
            response += f"   👥 {members} members\n\n"

        await msg.edit_text(response[:4000], parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in niche command: {e}")
        await msg.edit_text("❌ Niche discovery failed.", parse_mode=ParseMode.HTML)

async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /compare command"""
    user = update.effective_user

    coins_data = await db.get_user_coins(user.id)
    command_cost = await db.get_command_cost('compare')

    if not coins_data['is_admin'] and coins_data['balance'] < command_cost:
        await update.message.reply_text(
            f"⚠️ Insufficient coins! This command costs {command_cost} coins.\n"
            f"Your balance: {coins_data['balance']} coins"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /compare <sub1,sub2,sub3>\nExample: /compare python,javascript,golang"
        )
        return

    subreddits_str = context.args[0]

    if not coins_data['is_admin']:
        await db.deduct_coins(user.id, command_cost, 'compare', f"Compared {subreddits_str}")

    msg = await update.message.reply_text(
        f"📊 Comparing subreddits...\nThis may take 1-2 minutes...",
        parse_mode=ParseMode.HTML
    )

    try:
        result = await reddit_api.analyze_multiple(subreddits_str)

        if "error" in result:
            await msg.edit_text(f"❌ Error: {escape_html(result['error'])}", parse_mode=ParseMode.HTML)
            return

        comparisons = result.get('results', [])

        response = "<b>📊 Subreddit Comparison</b>\n\n"

        for comp in comparisons:
            name = comp.get('subreddit', 'Unknown')
            score = comp.get('effectiveness_score', 0)
            members = format_number(comp.get('subscribers', 0))
            emoji = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"

            response += f"{emoji} <b>r/{name}</b> - {score}/100\n"
            response += f"👥 {members} members\n"
            response += f"📝 {comp.get('avg_posts_per_day', 0):.1f} posts/day\n"
            response += f"⭐ {comp.get('avg_score_per_post', 0):.1f} avg score\n\n"

        if ai_analyzer:
            ai_prompt = f"Compare these subreddits and recommend which is best:\n\n{response}"
            ai_response = await ai_analyzer.compare_subreddits(ai_prompt)
            final_response = response + "\n" + ai_response

            if len(final_response) > 4000:
                await msg.edit_text(response, parse_mode=ParseMode.HTML)
                await update.message.reply_text(ai_response, parse_mode=ParseMode.HTML)
            else:
                await msg.edit_text(final_response, parse_mode=ParseMode.HTML)
        else:
            await msg.edit_text(response[:4000], parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in compare command: {e}")
        await msg.edit_text("❌ Comparison failed.", parse_mode=ParseMode.HTML)

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rules command"""
    user = update.effective_user

    coins_data = await db.get_user_coins(user.id)
    command_cost = await db.get_command_cost('rules')

    if not coins_data['is_admin'] and coins_data['balance'] < command_cost:
        await update.message.reply_text(
            f"⚠️ Insufficient coins! Cost: {command_cost} coins. Balance: {coins_data['balance']}"
        )
        return

    if not context.args:
        await update.message.reply_text("Usage: /rules <subreddit>\nExample: /rules technology")
        return

    subreddit = context.args[0].replace('r/', '')

    if not coins_data['is_admin']:
        await db.deduct_coins(user.id, command_cost, 'rules', f"Rules for r/{subreddit}")

    msg = await update.message.reply_text(
        f"📋 Getting rules for r/{escape_html(subreddit)}...",
        parse_mode=ParseMode.HTML
    )

    try:
        result = await reddit_api.get_rules(subreddit)

        if "error" in result:
            await msg.edit_text(f"❌ Error: {escape_html(result['error'])}", parse_mode=ParseMode.HTML)
            return

        rules = result.get('rules', [])
        response = f"<b>📋 Rules for r/{subreddit}</b>\n\n"

        for i, rule in enumerate(rules, 1):
            response += f"{i}. <b>{rule.get('title', 'Unknown')}</b>\n"
            if rule.get('description'):
                desc = rule['description'][:150]
                response += f"   {escape_html(desc)}...\n"
            response += "\n"

        if len(response) > 4000:
            response = response[:4000] + "\n\n<i>...truncated</i>"

        await msg.edit_text(response, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in rules command: {e}")
        await msg.edit_text("❌ Failed to get rules.", parse_mode=ParseMode.HTML)

async def requirements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /requirements command"""
    user = update.effective_user

    coins_data = await db.get_user_coins(user.id)
    command_cost = await db.get_command_cost('requirements')

    if not coins_data['is_admin'] and coins_data['balance'] < command_cost:
        await update.message.reply_text(
            f"⚠️ Insufficient coins! Cost: {command_cost} coins."
        )
        return

    if not context.args:
        await update.message.reply_text("Usage: /requirements <subreddit>")
        return

    subreddit = context.args[0].replace('r/', '')

    if not coins_data['is_admin']:
        await db.deduct_coins(user.id, command_cost, 'requirements', f"Requirements for r/{subreddit}")

    msg = await update.message.reply_text(
        f"✅ Checking requirements for r/{escape_html(subreddit)}...\n"
        "This may take 30-60 seconds...",
        parse_mode=ParseMode.HTML
    )

    try:
        result = await reddit_api.analyze_requirements(subreddit)

        if "error" in result:
            await msg.edit_text(f"❌ Error: {escape_html(result['error'])}", parse_mode=ParseMode.HTML)
            return

        karma_req = result.get('karma_requirements', {})
        response = f"<b>✅ Requirements for r/{subreddit}</b>\n\n"
        response += f"<b>Karma Requirements:</b>\n"
        response += f"• Post karma: {karma_req.get('post_karma_min', 0)}+\n"
        response += f"• Comment karma: {karma_req.get('comment_karma_min', 0)}+\n"
        response += f"• Account age: {karma_req.get('account_age_days', 0)}+ days\n"
        response += f"• Confidence: {karma_req.get('confidence', 'Unknown')}\n"

        await msg.edit_text(response, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in requirements command: {e}")
        await msg.edit_text("❌ Failed to get requirements.", parse_mode=ParseMode.HTML)

async def flairs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /flairs command"""
    user = update.effective_user

    coins_data = await db.get_user_coins(user.id)
    command_cost = await db.get_command_cost('flairs')

    if not coins_data['is_admin'] and coins_data['balance'] < command_cost:
        await update.message.reply_text(f"⚠️ Insufficient coins! Cost: {command_cost} coins.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /flairs <subreddit>")
        return

    subreddit = context.args[0].replace('r/', '')

    if not coins_data['is_admin']:
        await db.deduct_coins(user.id, command_cost, 'flairs', f"Flairs for r/{subreddit}")

    msg = await update.message.reply_text(
        f"🏷️ Analyzing flairs for r/{escape_html(subreddit)}...",
        parse_mode=ParseMode.HTML
    )

    try:
        result = await reddit_api.analyze_flairs(subreddit)

        if "error" in result:
            await msg.edit_text(f"❌ Error: {escape_html(result['error'])}", parse_mode=ParseMode.HTML)
            return

        flairs = result.get('flair_analysis', [])
        response = f"<b>🏷️ Flair Analysis for r/{subreddit}</b>\n\n"

        for i, flair in enumerate(flairs[:10], 1):
            response += f"{i}. <b>{flair.get('flair', 'No Flair')}</b>\n"
            response += f"   Posts: {flair.get('post_count', 0)}\n"
            response += f"   Avg score: {flair.get('avg_score', 0):.1f}\n\n"

        await msg.edit_text(response[:4000], parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in flairs command: {e}")
        await msg.edit_text("❌ Failed to analyze flairs.", parse_mode=ParseMode.HTML)

async def scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scrape command"""
    user = update.effective_user

    coins_data = await db.get_user_coins(user.id)
    command_cost = await db.get_command_cost('scrape')

    if not coins_data['is_admin'] and coins_data['balance'] < command_cost:
        await update.message.reply_text(f"⚠️ Insufficient coins! Cost: {command_cost} coins.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /scrape <subreddit> [limit]\nExample: /scrape technology 50")
        return

    subreddit = context.args[0].replace('r/', '')
    limit = int(context.args[1]) if len(context.args) > 1 else 50

    if not coins_data['is_admin']:
        await db.deduct_coins(user.id, command_cost, 'scrape', f"Scraped r/{subreddit}")

    msg = await update.message.reply_text(
        f"📥 Scraping top {limit} posts from r/{escape_html(subreddit)}...",
        parse_mode=ParseMode.HTML
    )

    try:
        result = await reddit_api.scrape_posts(subreddit, limit, 'hot', 'week')

        if "error" in result:
            await msg.edit_text(f"❌ Error: {escape_html(result['error'])}", parse_mode=ParseMode.HTML)
            return

        posts = result.get('posts', [])
        response = f"<b>📥 Top Posts from r/{subreddit}</b>\n\n"
        response += f"Scraped {len(posts)} posts:\n\n"

        for i, post in enumerate(posts[:15], 1):
            title = post.get('title', '')[:80]
            score = post.get('score', 0)
            comments = post.get('num_comments', 0)
            response += f"{i}. {escape_html(title)}...\n"
            response += f"   📈 {score} upvotes | 💬 {comments} comments\n\n"

        await msg.edit_text(response[:4000], parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in scrape command: {e}")
        await msg.edit_text("❌ Failed to scrape posts.", parse_mode=ParseMode.HTML)

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

    for u in users[:20]:
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

async def add_coins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addcoins command"""
    user = update.effective_user

    is_admin = await db.is_admin(user.id)
    if not is_admin:
        await update.message.reply_text("⚠️ Admin only.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addcoins <user_id> <amount>")
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])

        success = await db.add_coins(target_user_id, amount, 'admin_add', f'Added by admin {user.id}')

        if success:
            await update.message.reply_text(f"✅ Added {amount} coins to user {target_user_id}")
        else:
            await update.message.reply_text("❌ Failed to add coins.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount.")

async def set_coins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setcoins command"""
    user = update.effective_user

    is_admin = await db.is_admin(user.id)
    if not is_admin:
        await update.message.reply_text("⚠️ Admin only.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setcoins <user_id> <amount>")
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])

        # Get current balance
        current = await db.get_user_coins(target_user_id)
        difference = amount - current['balance']

        success = await db.add_coins(target_user_id, difference, 'admin_set', f'Set by admin {user.id}')

        if success:
            await update.message.reply_text(f"✅ Set balance for user {target_user_id} to {amount} coins")
        else:
            await update.message.reply_text("❌ Failed to set coins.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount.")

async def makeadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /makeadmin command"""
    user = update.effective_user

    is_admin = await db.is_admin(user.id)
    if not is_admin:
        await update.message.reply_text("⚠️ Admin only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /makeadmin <user_id>")
        return

    try:
        target_user_id = int(context.args[0])

        # Update admin status in database (you'll need to add this method)
        # await db.set_admin_status(target_user_id, True)

        await update.message.reply_text(f"✅ User {target_user_id} is now an admin!")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /announce command - send message to all users"""
    user = update.effective_user

    is_admin = await db.is_admin(user.id)
    if not is_admin:
        await update.message.reply_text("⚠️ Admin only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /announce <message>")
        return

    message = " ".join(context.args)

    users = await db.get_all_users()
    sent = 0
    failed = 0

    status_msg = await update.message.reply_text(
        f"📢 Sending announcement to {len(users)} users...",
        parse_mode=ParseMode.HTML
    )

    for u in users:
        try:
            await context.bot.send_message(
                chat_id=u['user_id'],
                text=f"📢 <b>Announcement</b>\n\n{message}",
                parse_mode=ParseMode.HTML
            )
            sent += 1
            await asyncio.sleep(0.05)  # Rate limiting
        except:
            failed += 1

    await status_msg.edit_text(
        f"✅ Announcement sent!\n\n"
        f"Delivered: {sent}\n"
        f"Failed: {failed}",
        parse_mode=ParseMode.HTML
    )

# ========== PAYMENT CALLBACK ==========

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
