"""
Setup Telegram Webhook for Vercel Deployment
Run this script to configure your bot's webhook URL
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
VERCEL_URL = 'https://redditanalyzer-kappa.vercel.app'

def set_webhook():
    """Set the webhook URL for the Telegram bot"""
    webhook_url = f"{VERCEL_URL}/webhook"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"

    payload = {
        'url': webhook_url,
        'drop_pending_updates': True  # Clear any pending updates
    }

    print(f"Setting webhook to: {webhook_url}")
    response = requests.post(url, json=payload)

    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            print("✅ Webhook set successfully!")
            print(f"Response: {result}")
        else:
            print("❌ Failed to set webhook")
            print(f"Error: {result}")
    else:
        print(f"❌ HTTP Error: {response.status_code}")
        print(f"Response: {response.text}")

def get_webhook_info():
    """Get current webhook information"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"

    response = requests.get(url)

    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            info = result.get('result', {})
            print("\n📊 Current Webhook Info:")
            print(f"URL: {info.get('url', 'Not set')}")
            print(f"Pending updates: {info.get('pending_update_count', 0)}")
            print(f"Last error: {info.get('last_error_message', 'None')}")
            print(f"Last error date: {info.get('last_error_date', 'N/A')}")
            print(f"Max connections: {info.get('max_connections', 'N/A')}")
            return info
        else:
            print("❌ Failed to get webhook info")
    else:
        print(f"❌ HTTP Error: {response.status_code}")

    return None

def delete_webhook():
    """Delete the webhook (switch to polling mode)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"

    payload = {
        'drop_pending_updates': True
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            print("✅ Webhook deleted successfully!")
        else:
            print("❌ Failed to delete webhook")
    else:
        print(f"❌ HTTP Error: {response.status_code}")

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment variables")
        print("Please create a .env file with your TELEGRAM_BOT_TOKEN")
        exit(1)

    print("=" * 50)
    print("Telegram Webhook Setup for Vercel")
    print("=" * 50)

    # First, check current webhook status
    print("\n1. Checking current webhook status...")
    current_info = get_webhook_info()

    # Set the new webhook
    print("\n2. Setting new webhook...")
    set_webhook()

    # Verify the webhook was set
    print("\n3. Verifying webhook configuration...")
    get_webhook_info()

    print("\n" + "=" * 50)
    print("Setup complete!")
    print("=" * 50)
    print("\nYou can now test your bot by sending /start to it on Telegram")
