"""
Coin system integration for Reddit Analyzer Bot
Add this to your reddit_bot.py
"""

from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from payment import PaymentProcessor, CoinManager
import os
from database import Database


# Then when initializing:
db = Database()  # Create your own instance
payment_processor = PaymentProcessor(
    stripe_secret_key=os.getenv('STRIPE_SECRET_KEY'),
    stripe_webhook_secret=os.getenv('STRIPE_WEBHOOK_SECRET'),
    database=db  # Now db is defined
)

# ========== COIN MANAGEMENT COMMANDS ==========

async def balance_command(update: Update, context):
    """Check coin balance"""
    user = update.effective_user
    if not user:
        return
    
    # Get user's coin data
    user_coins = await db.get_user_coins(user.id)
    
    if user_coins['is_admin']:
        await update.message.reply_text(
            "👑 <b>Admin Account</b>\n\n"
            "You have unlimited coins!",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Format expiration date
    expires_text = "Never"
    if user_coins['expires_at']:
        expire_date = datetime.fromisoformat(user_coins['expires_at'])
        days_left = (expire_date - datetime.now()).days
        if days_left > 365:
            expires_text = "Never"
        else:
            expires_text = f"{days_left} days"
    
    # Get transaction history
    history = await db.get_user_transaction_history(user.id, limit=5)
    
    # Format response
    response = (
        f"💰 <b>Your Coin Balance</b>\n\n"
        f"Balance: {CoinManager.format_coin_display(user_coins['balance'])}\n"
        f"Expires in: {expires_text}\n\n"
    )
    
    if user_coins['is_expired']:
        response += "⚠️ <b>Your coins have expired!</b>\n"
        response += "Purchase new coins to continue using the bot.\n\n"
    
    # Add recent transactions
    if history:
        response += "<b>Recent Transactions:</b>\n"
        for trans in history[:5]:
            if trans['amount'] > 0:
                emoji = "➕"
            else:
                emoji = "➖"
            response += f"{emoji} {abs(trans['amount'])} coins - {trans['description'][:30]}\n"
    
    # Add buttons
    keyboard = [[
        InlineKeyboardButton("🛒 Buy Coins", callback_data="buy_coins"),
        InlineKeyboardButton("📊 View Packages", callback_data="view_packages")
    ]]
    
    if not user_coins['is_expired'] and user_coins['balance'] > 0:
        keyboard.append([
            InlineKeyboardButton("📜 Transaction History", callback_data="transaction_history")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        response,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def buy_coins_command(update: Update, context):
    """Show coin packages for purchase"""
    user = update.effective_user
    if not user:
        return
    
    packages = payment_processor.get_all_packages()
    
    response = (
        "🛒 <b>Coin Packages</b>\n\n"
        "Choose a package to purchase:\n\n"
    )
    
    keyboard = []
    
    for key, package in packages.items():
        total_coins = package['coins'] + package['bonus']
        value_text = ""
        
        if package['bonus'] > 0:
            value_text = f" (+{package['bonus']} bonus)"
        
        if key == 'ultimate':
            value_text += " 🏆 BEST VALUE"
        
        response += (
            f"<b>{package['name']}</b>\n"
            f"🪙 {total_coins} coins{value_text}\n"
            f"💵 ${package['price']}\n\n"
        )
        
        keyboard.append([
            InlineKeyboardButton(
                f"{package['name']} - ${package['price']}",
                callback_data=f"package_{key}"
            )
        ])
    
    response += (
        "ℹ️ <b>Important Info:</b>\n"
        "• All purchases extend expiration by 30 days\n"
        "• No refunds available\n"
        "• Secure payment via Stripe\n"
    )
    
    keyboard.append([
        InlineKeyboardButton("💰 Check Balance", callback_data="check_balance")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        response,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def prices_command(update: Update, context):
    """Show command prices"""
    user = update.effective_user
    if not user:
        return
    
    response = (
        "💎 <b>Command Prices</b>\n\n"
        "Here's how much each command costs:\n\n"
        "<b>Analysis Commands:</b>\n"
        f"📊 /analyze - {CoinManager.format_coin_display(2)}\n"
        f"📋 /requirements - {CoinManager.format_coin_display(2)}\n"
        f"🆚 /compare - {CoinManager.format_coin_display(5)}\n"
        f"🔍 /search - {CoinManager.format_coin_display(1)}\n"
        f"🎯 /niche - {CoinManager.format_coin_display(3)}\n\n"
        "<b>Data Commands:</b>\n"
        f"📜 /rules - {CoinManager.format_coin_display(1)}\n"
        f"🏷️ /flairs - {CoinManager.format_coin_display(1)}\n"
        f"⛏️ /scrape - FREE\n"
        f"🤖 AI Recreation:\n"
        f"  • 10 posts - {CoinManager.format_coin_display(2)}\n"
        f"  • 20 posts - {CoinManager.format_coin_display(4)}\n"
        f"  • 30 posts - {CoinManager.format_coin_display(6)}\n\n"
        "💰 Use /balance to check your coins\n"
        "🛒 Use /buy to purchase more coins"
    )
    
    keyboard = [[
        InlineKeyboardButton("💰 Check Balance", callback_data="check_balance"),
        InlineKeyboardButton("🛒 Buy Coins", callback_data="buy_coins")
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        response,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

# ========== ADMIN COIN COMMANDS ==========

@admin_required
async def add_coins_command(update: Update, context):
    """Admin command to add coins to a user"""
    admin = update.effective_user
    if not admin:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /addcoins [user_id] [amount] [optional: description]\n\n"
            "Example: /addcoins 123456789 50 Bonus for feedback",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        description = " ".join(context.args[2:]) if len(context.args) > 2 else f"Added by admin {admin.username or admin.id}"
        
        # Add coins
        success = await db.add_coins(
            target_user_id,
            amount,
            'admin_add',
            description,
            extend_expiry=False  # Don't extend expiry for admin adds
        )
        
        if success:
            # Log admin action
            await db.log_admin_action(
                admin.id,
                'add_coins',
                f"Added {amount} coins to user {target_user_id}: {description}"
            )
            
            # Try to notify the user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎁 You received {CoinManager.format_coin_display(amount)}!\n\n"
                         f"Reason: {description}\n\n"
                         f"Use /balance to check your new balance.",
                    parse_mode=ParseMode.HTML
                )
                notification = "✅ User notified"
            except:
                notification = "⚠️ Could not notify user"
            
            await update.message.reply_text(
                f"✅ Successfully added {CoinManager.format_coin_display(amount)} to user {target_user_id}\n\n"
                f"{notification}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "❌ Failed to add coins. Please check the user ID.",
                parse_mode=ParseMode.HTML
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid user ID or amount. Both must be numbers.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in add_coins_command: {e}")
        await update.message.reply_text(
            "❌ An error occurred while adding coins.",
            parse_mode=ParseMode.HTML
        )

@admin_required
async def set_coins_command(update: Update, context):
    """Admin command to set a user's coin balance"""
    admin = update.effective_user
    if not admin:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /setcoins [user_id] [amount]\n\n"
            "Example: /setcoins 123456789 100",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        new_balance = int(context.args[1])
        
        # Get current balance
        current = await db.get_user_coins(target_user_id)
        difference = new_balance - current['balance']
        
        if difference > 0:
            # Add coins
            success = await db.add_coins(
                target_user_id,
                difference,
                'admin_add',
                f"Balance set to {new_balance} by admin",
                extend_expiry=False
            )
        elif difference < 0:
            # Deduct coins
            success = await db.deduct_coins(
                target_user_id,
                abs(difference),
                'admin_deduct',
                f"Balance set to {new_balance} by admin"
            )
        else:
            await update.message.reply_text(
                f"ℹ️ User already has {new_balance} coins.",
                parse_mode=ParseMode.HTML
            )
            return
        
        if success:
            await db.log_admin_action(
                admin.id,
                'set_coins',
                f"Set user {target_user_id} balance to {new_balance} coins"
            )
            
            await update.message.reply_text(
                f"✅ Set user {target_user_id}'s balance to {CoinManager.format_coin_display(new_balance)}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "❌ Failed to set coin balance.",
                parse_mode=ParseMode.HTML
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid user ID or amount.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in set_coins_command: {e}")
        await update.message.reply_text(
            "❌ An error occurred.",
            parse_mode=ParseMode.HTML
        )