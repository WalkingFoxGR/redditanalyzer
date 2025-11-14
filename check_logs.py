"""
Check if Telegram is sending updates to the bot
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
VERCEL_URL = 'https://redditanalyzer-kappa.vercel.app'

def check_webhook_info():
    """Check webhook status and errors"""
    print("=" * 60)
    print("  Checking Telegram Webhook Status")
    print("=" * 60)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get('ok'):
            info = data.get('result', {})

            print(f"\n✅ Webhook URL: {info.get('url', 'Not set')}")
            print(f"   Pending updates: {info.get('pending_update_count', 0)}")
            print(f"   Max connections: {info.get('max_connections', 40)}")

            last_error = info.get('last_error_message')
            if last_error:
                print(f"\n❌ LAST ERROR: {last_error}")
                print(f"   Error date: {info.get('last_error_date', 'Unknown')}")
                print(f"\n   This means Telegram IS sending updates but Vercel is returning errors!")
                return False
            else:
                print(f"\n✅ No webhook errors")

            last_sync = info.get('last_synchronization_error_date')
            if last_sync:
                print(f"   Last sync error: {last_sync}")

            return True

    return False

def test_webhook_endpoint():
    """Test if webhook endpoint is accessible"""
    print("\n" + "=" * 60)
    print("  Testing Vercel Webhook Endpoint")
    print("=" * 60)

    # Test with a fake update to see if endpoint responds
    url = f"{VERCEL_URL}/webhook"

    print(f"\n   Testing: {url}")

    # Send a test POST request
    test_data = {
        "update_id": 999999999,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "first_name": "Test",
                "username": "test"
            },
            "chat": {
                "id": 123456789,
                "type": "private"
            },
            "date": 1234567890,
            "text": "/start"
        }
    }

    try:
        response = requests.post(url, json=test_data, timeout=10)
        print(f"   Response: HTTP {response.status_code}")

        if response.status_code == 200:
            print(f"   ✅ Webhook endpoint is accessible")
            return True
        else:
            print(f"   ❌ Webhook returned error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def check_database():
    """Check database connectivity"""
    print("\n" + "=" * 60)
    print("  Checking Database Connection")
    print("=" * 60)

    url = f"{VERCEL_URL}/database-health"

    try:
        response = requests.get(url, timeout=15)

        if response.status_code == 200:
            data = response.json()
            status = data.get('status')
            database = data.get('database')

            if status == 'healthy' and database == 'connected':
                print(f"\n   ✅ Database: Connected")
                stats = data.get('stats', {})
                if stats:
                    print(f"   Total users: {stats.get('total_users', 0)}")
                    print(f"   Active users: {stats.get('active_users', 0)}")

                    if stats.get('total_users', 0) > 0:
                        print(f"\n   ✅ Database has users - tables are created!")
                    else:
                        print(f"\n   ⚠️  Database connected but no users yet")
                        print(f"   Tables should be created when you first use the bot")
                return True
            else:
                print(f"\n   ❌ Database status: {status}, connection: {database}")
                return False
        else:
            print(f"\n   ❌ Database check failed: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown')}")
            except:
                print(f"   Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return False

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env file")
        return

    print("\n")

    # Check webhook
    webhook_ok = check_webhook_info()

    # Test webhook endpoint
    endpoint_ok = test_webhook_endpoint()

    # Check database
    db_ok = check_database()

    # Summary
    print("\n" + "=" * 60)
    print("  DIAGNOSIS")
    print("=" * 60)

    if webhook_ok and endpoint_ok and db_ok:
        print("\n✅ Everything looks good!")
        print("\n   Try these steps:")
        print("   1. Open Telegram")
        print("   2. Send /start to your bot")
        print("   3. Wait a few seconds")
        print("   4. You should get a welcome message")

    else:
        print("\n⚠️  Issues detected:")

        if not webhook_ok:
            print("\n   ❌ WEBHOOK HAS ERRORS")
            print("   → Telegram is trying to send updates but getting errors from Vercel")
            print("   → Check Vercel logs for the error details")
            print("   → Most likely: DATABASE_URL or TELEGRAM_BOT_TOKEN not set in Vercel")

        if not endpoint_ok:
            print("\n   ❌ WEBHOOK ENDPOINT NOT RESPONDING")
            print("   → The /webhook endpoint is not accessible or returning errors")
            print("   → Check Vercel deployment status")

        if not db_ok:
            print("\n   ❌ DATABASE NOT CONNECTED")
            print("   → DATABASE_URL not set correctly in Vercel")
            print("   → Use port 6543 (not 5432)")
            print("   → Make sure you redeployed after setting it")

        print("\n   📋 ACTION ITEMS:")
        print("   1. Go to Vercel Dashboard → Settings → Environment Variables")
        print("   2. Verify these are set:")
        print("      - TELEGRAM_BOT_TOKEN")
        print("      - DATABASE_URL (with port 6543)")
        print("      - OPENAI_API_KEY")
        print("   3. Click 'Redeploy' on your latest deployment")
        print("   4. Wait 1-2 minutes for deployment to complete")
        print("   5. Run this script again")

    print("\n" + "=" * 60 + "\n")

if __name__ == "__main__":
    main()
