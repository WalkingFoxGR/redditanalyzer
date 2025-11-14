"""
Diagnostic Script for Reddit Analyzer Bot Deployment
Checks all components and identifies issues
"""

import os
import requests
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Configuration
VERCEL_URL = 'https://redditanalyzer-kappa.vercel.app'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def print_status(check_name, status, message=""):
    """Print a check status"""
    symbol = "✅" if status else "❌"
    print(f"{symbol} {check_name}")
    if message:
        print(f"   → {message}")

def check_vercel_deployment():
    """Check if Vercel deployment is accessible"""
    print_header("1. Vercel Deployment Check")

    try:
        # Check main endpoint
        response = requests.get(f"{VERCEL_URL}/", timeout=10)
        if response.status_code == 200:
            print_status("Main endpoint", True, f"Status: {response.status_code}")
            data = response.json()
            print(f"   Service: {data.get('service', 'Unknown')}")
            print(f"   Version: {data.get('version', 'Unknown')}")
        else:
            print_status("Main endpoint", False, f"HTTP {response.status_code}")
            return False

        # Check health endpoint
        response = requests.get(f"{VERCEL_URL}/health", timeout=10)
        if response.status_code == 200:
            print_status("Health endpoint", True)
        else:
            print_status("Health endpoint", False, f"HTTP {response.status_code}")

        return True

    except requests.exceptions.RequestException as e:
        print_status("Vercel deployment", False, f"Error: {e}")
        return False

def check_database():
    """Check database connectivity"""
    print_header("2. Database Connectivity Check")

    try:
        response = requests.get(f"{VERCEL_URL}/database-health", timeout=15)

        if response.status_code == 200:
            data = response.json()
            status = data.get('status')
            database = data.get('database')

            if status == 'healthy' and database == 'connected':
                print_status("Database connection", True, "Connected successfully")
                stats = data.get('stats', {})
                if stats:
                    print(f"   Total users: {stats.get('total_users', 0)}")
                    print(f"   Active users: {stats.get('active_users', 0)}")
                return True
            else:
                print_status("Database connection", False, "Not connected")
                return False
        else:
            print_status("Database connection", False, f"HTTP {response.status_code}")
            if response.status_code == 500:
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data.get('error', 'Unknown error')}")
                except:
                    pass
            return False

    except requests.exceptions.RequestException as e:
        print_status("Database health check", False, f"Error: {e}")
        return False

def check_telegram_bot():
    """Check Telegram bot configuration"""
    print_header("3. Telegram Bot Configuration Check")

    if not TELEGRAM_BOT_TOKEN:
        print_status("Bot token", False, "TELEGRAM_BOT_TOKEN not found in .env file")
        print("\n   ⚠️  Please create a .env file with your TELEGRAM_BOT_TOKEN")
        return False

    print_status("Bot token", True, f"Found (ends with: ...{TELEGRAM_BOT_TOKEN[-5:]})")

    try:
        # Get bot info
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                bot_info = data.get('result', {})
                print_status("Bot API connection", True)
                print(f"   Bot username: @{bot_info.get('username', 'Unknown')}")
                print(f"   Bot name: {bot_info.get('first_name', 'Unknown')}")
                return True
            else:
                print_status("Bot API connection", False, "Invalid response")
                return False
        else:
            print_status("Bot API connection", False, f"HTTP {response.status_code}")
            if response.status_code == 401:
                print("   ⚠️  Invalid bot token!")
            return False

    except requests.exceptions.RequestException as e:
        print_status("Telegram API", False, f"Error: {e}")
        return False

def check_webhook():
    """Check webhook configuration"""
    print_header("4. Webhook Configuration Check")

    if not TELEGRAM_BOT_TOKEN:
        print_status("Webhook check", False, "Bot token not available")
        return False

    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo",
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                info = data.get('result', {})

                # Check webhook URL
                webhook_url = info.get('url', '')
                expected_url = f"{VERCEL_URL}/webhook"

                if webhook_url == expected_url:
                    print_status("Webhook URL", True, webhook_url)
                elif webhook_url:
                    print_status("Webhook URL", False, f"Wrong URL: {webhook_url}")
                    print(f"   Expected: {expected_url}")
                    print(f"\n   💡 Run: python setup_webhook.py to fix this")
                    return False
                else:
                    print_status("Webhook URL", False, "Not configured")
                    print(f"   Expected: {expected_url}")
                    print(f"\n   💡 Run: python setup_webhook.py to set it up")
                    return False

                # Check for errors
                last_error = info.get('last_error_message')
                if last_error:
                    print_status("Webhook errors", False, last_error)
                    last_error_date = info.get('last_error_date', 'Unknown')
                    print(f"   Last error date: {last_error_date}")
                else:
                    print_status("Webhook errors", True, "No errors")

                # Check pending updates
                pending = info.get('pending_update_count', 0)
                if pending > 0:
                    print_status("Pending updates", False, f"{pending} updates waiting")
                    print("   💡 Updates are queued but not being processed")
                else:
                    print_status("Pending updates", True, "No pending updates")

                return webhook_url == expected_url and not last_error

        else:
            print_status("Webhook info", False, f"HTTP {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print_status("Webhook check", False, f"Error: {e}")
        return False

def check_environment_variables():
    """Check required environment variables"""
    print_header("5. Environment Variables Check (Local)")

    required_vars = {
        'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
        'DATABASE_URL': os.getenv('DATABASE_URL'),
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    }

    optional_vars = {
        'STRIPE_SECRET_KEY': os.getenv('STRIPE_SECRET_KEY'),
        'STRIPE_WEBHOOK_SECRET': os.getenv('STRIPE_WEBHOOK_SECRET'),
        'REDDIT_CLIENT_ID': os.getenv('REDDIT_CLIENT_ID'),
        'REDDIT_CLIENT_SECRET': os.getenv('REDDIT_CLIENT_SECRET'),
    }

    all_good = True

    print("\n  Required variables:")
    for var_name, var_value in required_vars.items():
        if var_value:
            masked = f"...{var_value[-5:]}" if len(var_value) > 5 else "***"
            print_status(var_name, True, masked)
        else:
            print_status(var_name, False, "Not set")
            all_good = False

    print("\n  Optional variables:")
    for var_name, var_value in optional_vars.items():
        if var_value:
            masked = f"...{var_value[-5:]}" if len(var_value) > 5 else "***"
            print_status(var_name, True, masked)
        else:
            print_status(var_name, False, "Not set (optional)")

    if not all_good:
        print("\n   ⚠️  Missing required variables in local .env file")
        print("   Note: These must also be set in Vercel dashboard!")

    return all_good

def main():
    """Run all diagnostic checks"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "Reddit Analyzer Bot - Diagnostics" + " " * 14 + "║")
    print("╚" + "═" * 58 + "╝")

    results = {
        'vercel': check_vercel_deployment(),
        'database': check_database(),
        'telegram': check_telegram_bot(),
        'webhook': check_webhook(),
        'env_vars': check_environment_variables(),
    }

    # Summary
    print_header("Summary")

    total_checks = len(results)
    passed_checks = sum(1 for v in results.values() if v)

    print(f"\n  Checks passed: {passed_checks}/{total_checks}")

    if all(results.values()):
        print("\n  ✅ All checks passed! Your bot should be working.")
        print("  Try sending /start to your bot on Telegram.")
    else:
        print("\n  ⚠️  Some checks failed. Please review the issues above.")

        if not results['vercel']:
            print("\n  → Vercel deployment issue - check your deployment")

        if not results['database']:
            print("\n  → Database issue - check DATABASE_URL in Vercel dashboard")
            print("     Make sure you're using port 6543 for Supabase connection pooling")

        if not results['telegram']:
            print("\n  → Telegram bot token issue - check TELEGRAM_BOT_TOKEN")

        if not results['webhook']:
            print("\n  → Webhook not configured - run: python setup_webhook.py")

        if not results['env_vars']:
            print("\n  → Environment variables missing - check .env file")
            print("     Also ensure they are set in Vercel dashboard!")

    print("\n" + "=" * 60)
    print("\n  📚 For more help, see: DEPLOYMENT_GUIDE.md")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
