"""
Test script to verify bot is working
Sends a test message to check webhook response
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
VERCEL_URL = 'https://redditanalyzer-kappa.vercel.app'

def check_webhook_status():
    """Check current webhook configuration"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get('ok'):
            info = data.get('result', {})
            print("📊 Webhook Status:")
            print(f"   URL: {info.get('url', 'Not set')}")
            print(f"   Pending updates: {info.get('pending_update_count', 0)}")

            last_error = info.get('last_error_message')
            if last_error:
                print(f"   ⚠️  Last error: {last_error}")
                print(f"   Error date: {info.get('last_error_date', 'Unknown')}")
                return False
            else:
                print(f"   ✅ No errors")
                return True
    return False

def get_bot_info():
    """Get bot information"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get('ok'):
            bot = data.get('result', {})
            print("\n🤖 Bot Information:")
            print(f"   Username: @{bot.get('username', 'Unknown')}")
            print(f"   Name: {bot.get('first_name', 'Unknown')}")
            print(f"   ID: {bot.get('id', 'Unknown')}")
            return bot
    return None

def test_vercel_endpoints():
    """Test all Vercel endpoints"""
    print("\n🔍 Testing Vercel Endpoints:")

    endpoints = {
        'Main': '/',
        'Health': '/health',
        'Database': '/database-health'
    }

    all_good = True
    for name, endpoint in endpoints.items():
        try:
            response = requests.get(f"{VERCEL_URL}{endpoint}", timeout=10)
            if response.status_code == 200:
                print(f"   ✅ {name}: OK")
                if endpoint == '/database-health':
                    data = response.json()
                    if data.get('database') == 'connected':
                        print(f"      Database: Connected")
                        stats = data.get('stats', {})
                        if stats:
                            print(f"      Total users: {stats.get('total_users', 0)}")
            else:
                print(f"   ❌ {name}: HTTP {response.status_code}")
                all_good = False
        except Exception as e:
            print(f"   ❌ {name}: Error - {e}")
            all_good = False

    return all_good

def get_updates():
    """Get recent updates (messages sent to bot)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get('ok'):
            updates = data.get('result', [])
            print(f"\n📬 Recent Updates: {len(updates)} messages")

            if updates:
                print("\n   Last 3 messages:")
                for update in updates[-3:]:
                    msg = update.get('message', {})
                    user = msg.get('from', {})
                    text = msg.get('text', 'No text')
                    print(f"   - From @{user.get('username', 'Unknown')}: {text}")
            else:
                print("   No messages yet. Send /start to your bot!")

            return updates
    return []

def main():
    print("\n" + "="*60)
    print("  Telegram Bot - Complete Test")
    print("="*60)

    if not TELEGRAM_BOT_TOKEN:
        print("\n❌ Error: TELEGRAM_BOT_TOKEN not found in .env file")
        return

    # Test 1: Get bot info
    bot_info = get_bot_info()
    if not bot_info:
        print("\n❌ Failed to get bot info. Check your token.")
        return

    # Test 2: Check webhook
    webhook_ok = check_webhook_status()

    # Test 3: Test Vercel endpoints
    vercel_ok = test_vercel_endpoints()

    # Test 4: Get recent messages
    updates = get_updates()

    # Summary
    print("\n" + "="*60)
    print("  Summary")
    print("="*60)

    if webhook_ok and vercel_ok:
        print("\n✅ Everything looks good!")
        print("\nNext steps:")
        print("1. Open Telegram")
        print(f"2. Search for @{bot_info.get('username')}")
        print("3. Send: /start")
        print("4. You should get a welcome message!")

        if not updates:
            print("\n💡 No messages received yet. Try sending /start to your bot now!")
    else:
        print("\n⚠️ Some issues detected:")
        if not webhook_ok:
            print("   - Webhook has errors")
        if not vercel_ok:
            print("   - Vercel endpoints not responding properly")
        print("\n💡 Check the errors above and:")
        print("   1. Verify DATABASE_URL is set in Vercel")
        print("   2. Verify TELEGRAM_BOT_TOKEN is set in Vercel")
        print("   3. Make sure you redeployed after setting env vars")

    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
