#!/bin/bash
# Check Telegram webhook for errors

echo "Paste your TELEGRAM_BOT_TOKEN and press Enter:"
read BOT_TOKEN

echo ""
echo "Checking webhook status..."
echo ""

curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -c "
import sys
import json

data = json.load(sys.stdin)
if data.get('ok'):
    info = data.get('result', {})
    print('Webhook URL:', info.get('url', 'Not set'))
    print('Pending updates:', info.get('pending_update_count', 0))
    print('Max connections:', info.get('max_connections', 40))
    print('')

    last_error = info.get('last_error_message')
    if last_error:
        print('❌ LAST ERROR:', last_error)
        print('Error date:', info.get('last_error_date', 'Unknown'))
        print('')
        print('This is the problem! Vercel is returning an error.')
    else:
        print('✅ No webhook errors detected')
else:
    print('Failed to get webhook info')
"
