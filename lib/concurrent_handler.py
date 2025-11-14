"""
Enhanced concurrent command execution for Reddit Analyzer Bot
Replaces the queue system with smart concurrent execution
"""

import asyncio
import time
from typing import Dict, Any, Optional
from collections import deque
from functools import wraps
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class ConcurrentCommandManager:
    """Manages concurrent command execution with smart rate limiting"""
    
    def __init__(self, rate_limit: int = 90, time_window: int = 60):
        self.rate_limit = rate_limit  # Max requests per minute
        self.time_window = time_window  # Time window in seconds
        self.request_times = deque()  # Track request timestamps
        self.active_commands = {}  # Track active commands per user
        self.command_counter = 0  # Total commands processed
        
    def _cleanup_old_requests(self):
        """Remove request timestamps older than the time window"""
        current_time = time.time()
        while self.request_times and current_time - self.request_times[0] > self.time_window:
            self.request_times.popleft()
    
    def can_execute_immediately(self) -> tuple[bool, Optional[float]]:
        """Check if command can execute immediately or needs to wait"""
        self._cleanup_old_requests()
        current_time = time.time()
        
        # Check current rate
        current_rate = len(self.request_times)
        
        if current_rate >= self.rate_limit:
            # Calculate wait time until oldest request expires
            oldest_request = self.request_times[0]
            wait_time = self.time_window - (current_time - oldest_request) + 0.1
            return False, wait_time
        
        return True, None
    
    def record_request(self):
        """Record a new request timestamp"""
        self.request_times.append(time.time())
        self.command_counter += 1
    
    def get_status(self) -> Dict[str, Any]:
        """Get current manager status"""
        self._cleanup_old_requests()
        return {
            'current_rate': len(self.request_times),
            'rate_limit': self.rate_limit,
            'rate_percentage': (len(self.request_times) / self.rate_limit) * 100,
            'total_commands': self.command_counter,
            'active_commands': len(self.active_commands)
        }

# Initialize the concurrent manager
concurrent_manager = ConcurrentCommandManager(rate_limit=90, time_window=60)

def concurrent_command(func):
    """Decorator for concurrent command execution with smart rate limiting"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        
        command_name = update.message.text.split()[0] if update.message else "unknown"
        
        # Check if we can execute immediately
        can_execute, wait_time = concurrent_manager.can_execute_immediately()
        
        if not can_execute:
            # Only queue if we're over the Reddit API limit
            await update.message.reply_text(
                f"⚠️ <b>High traffic detected!</b>\n\n"
                f"Reddit API limit reached ({concurrent_manager.rate_limit} requests/min).\n"
                f"Your command will execute in {wait_time:.1f} seconds.\n\n"
                f"<i>This only happens during peak usage.</i>",
                parse_mode=ParseMode.HTML
            )
            await asyncio.sleep(wait_time)
        
        # Record the request
        concurrent_manager.record_request()
        
        # Track active command for this user
        command_id = f"{user.id}_{time.time()}"
        concurrent_manager.active_commands[command_id] = {
            'user_id': user.id,
            'command': command_name,
            'start_time': time.time()
        }
        
        try:
            # Execute the command concurrently
            await func(update, context)
        finally:
            # Remove from active commands
            if command_id in concurrent_manager.active_commands:
                del concurrent_manager.active_commands[command_id]
    
    return wrapper

def requires_coins_with_notification(cost: int = None, command_name: str = None):
    """Enhanced coin decorator that shows deduction message"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context):
            user = update.effective_user
            if not user:
                return
            
            # Check if command has required argument (subreddit/topic)
            if not context.args:
                # Don't deduct coins if no argument provided
                await update.message.reply_text(
                    f"❌ Please provide a subreddit or topic.\n"
                    f"Example: <code>{update.message.text.split()[0]} python</code>",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Check if admin (admins don't need coins)
            from database import Database
            db = Database()
            is_admin = await db.is_admin(user.id)
            
            if is_admin:
                # Admins get a different message
                await update.message.reply_text(
                    "👑 <b>Admin Mode</b> - No coins required",
                    parse_mode=ParseMode.HTML,
                    disable_notification=True
                )
                return await func(update, context)
            
            # Import CoinManager locally to avoid circular imports
            from payment import CoinManager
            
            # Determine cost
            if cost is not None:
                required_coins = cost
            elif command_name:
                required_coins = CoinManager.get_command_cost(command_name)
            else:
                cmd = func.__name__.replace('_command', '').replace('_endpoint', '')
                required_coins = CoinManager.get_command_cost(cmd)
            
            # Get user's coin balance
            user_coins = await db.get_user_coins(user.id)
            
            # Check if coins expired
            if user_coins['is_expired']:
                keyboard = [[
                    InlineKeyboardButton("🛒 Buy Coins", callback_data="buy_coins"),
                    InlineKeyboardButton("📊 View Packages", callback_data="view_packages")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "⏰ <b>Your coins have expired!</b>\n\n"
                    "Purchase a new coin package to continue using the bot.\n"
                    "All purchases extend your expiration by 30 days.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                return
            
            # Check sufficient balance
            if user_coins['balance'] < required_coins:
                keyboard = [[
                    InlineKeyboardButton("🛒 Buy Coins", callback_data="buy_coins"),
                    InlineKeyboardButton("💰 Check Balance", callback_data="check_balance")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"❌ <b>Insufficient coins!</b>\n\n"
                    f"This command costs: {CoinManager.format_coin_display(required_coins)}\n"
                    f"Your balance: {CoinManager.format_coin_display(user_coins['balance'])}\n"
                    f"You need: {CoinManager.format_coin_display(required_coins - user_coins['balance'])} more\n\n"
                    f"Purchase coins to continue using the bot!",
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                return
            
            # Deduct coins
            command = func.__name__.replace('_command', '').replace('_endpoint', '')
            target = context.args[0] if context.args else 'unknown'
            success = await db.deduct_coins(
                user.id, 
                required_coins, 
                command,
                f"Used /{command} on {target}"
            )
            
            if not success:
                await update.message.reply_text(
                    "❌ Failed to process payment. Please try again.",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Calculate new balance
            new_balance = user_coins['balance'] - required_coins
            
            # Send coin deduction notification
            coin_message = await update.message.reply_text(
                f"💰 <b>Coins Deducted</b>\n\n"
                f"Command: /{command} {target}\n"
                f"Cost: {CoinManager.format_coin_display(required_coins)}\n"
                f"New balance: {CoinManager.format_coin_display(new_balance)}\n\n"
                f"<i>Processing your request...</i>",
                parse_mode=ParseMode.HTML
            )
            
            # Store the coin message ID so we can delete it later
            context.user_data['coin_message_id'] = coin_message.message_id
            context.user_data['coins_deducted'] = required_coins
            context.user_data['coins_remaining'] = new_balance
            
            # Execute the command
            return await func(update, context)
        
        return wrapper
    return decorator

async def cleanup_coin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clean up the coin deduction message after command completes"""
    if 'coin_message_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['coin_message_id']
            )
        except:
            pass  # Message might already be deleted
        finally:
            del context.user_data['coin_message_id']

# Status command to check concurrent execution
async def concurrent_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check concurrent execution status"""
    status = concurrent_manager.get_status()
    
    # Determine status emoji
    if status['rate_percentage'] < 50:
        status_emoji = "🟢"
        status_text = "Optimal"
    elif status['rate_percentage'] < 80:
        status_emoji = "🟡"
        status_text = "Moderate"
    else:
        status_emoji = "🔴"
        status_text = "High Load"
    
    response = (
        f"{status_emoji} <b>System Status: {status_text}</b>\n\n"
        f"📊 <b>Current Metrics:</b>\n"
        f"• API Usage: {status['current_rate']}/{status['rate_limit']} requests/min\n"
        f"• Load: {status['rate_percentage']:.1f}%\n"
        f"• Active Commands: {status['active_commands']}\n"
        f"• Total Processed: {status['total_commands']}\n\n"
        f"💡 <b>Performance:</b>\n"
    )
    
    if status['rate_percentage'] < 90:
        response += "✅ All commands execute immediately\n"
        response += "✅ No queueing needed\n"
        response += "✅ Optimal performance"
    else:
        response += "⚠️ Near Reddit API limit\n"
        response += "⚠️ Some commands may be delayed\n"
        response += "⚠️ Consider spreading requests"
    
    await update.message.reply_text(response, parse_mode=ParseMode.HTML)