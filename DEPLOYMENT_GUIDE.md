# Vercel Deployment Guide for Reddit Analyzer Bot

## Current Issues & Solutions

### Problem: Bot Not Responding on Telegram
The bot is deployed and healthy, but not receiving messages from Telegram.

**Root Cause:** The Telegram webhook is not configured to point to your Vercel deployment.

---

## Solution Steps

### Step 1: Configure Vercel Environment Variables

Make sure ALL these environment variables are set in your Vercel dashboard:

1. Go to: https://vercel.com/your-project/settings/environment-variables

2. Add these required variables:

```bash
# Required - Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Required - Database URL (Supabase)
# IMPORTANT: Use port 6543 for connection pooling (serverless)
DATABASE_URL=postgresql://postgres.lcggdsdgasdtfcxbtfezl:YOUR_PASSWORD@db.lcggdsdgasdtfcxbtfezl.supabase.co:6543/postgres

# Required - OpenAI API Key
OPENAI_API_KEY=sk-your_openai_api_key

# Required - Stripe Keys (if using payments)
STRIPE_SECRET_KEY=sk_test_or_live_key
STRIPE_PUBLISHABLE_KEY=pk_test_or_live_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Optional - Reddit API (for Reddit features)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=RedditAnalyzerBot/1.0

# Optional - Bot Configuration
INITIAL_FREE_COINS=10
COINS_EXPIRY_DAYS=30
```

**IMPORTANT:** After adding environment variables, you must **redeploy** your app for them to take effect!

---

### Step 2: Fix Database URL Format

Your current Supabase URL format is correct for **connection pooling** (port 6543), which is what you need for serverless deployments like Vercel.

**Correct format:**
```
postgresql://postgres:<PASSWORD>@db.<PROJECT_ID>.supabase.co:6543/postgres
```

**Example:**
```
DATABASE_URL=postgresql://postgres.lcggdsdgasdtfcxbtfezl:<YOUR_ACTUAL_PASSWORD>@db.lcggdsdgasdtfcxbtfezl.supabase.co:6543/postgres
```

Replace `<YOUR_ACTUAL_PASSWORD>` with your Supabase database password.

---

### Step 3: Set Up Telegram Webhook

After deploying with the correct environment variables, run the webhook setup:

#### Option A: Run the setup script locally

1. Create a `.env` file in the `vercel-bot` directory:
```bash
cd vercel-bot
cp .env.example .env
```

2. Edit `.env` and add your `TELEGRAM_BOT_TOKEN`

3. Install dependencies:
```bash
pip install requests python-dotenv
```

4. Run the webhook setup script:
```bash
python setup_webhook.py
```

#### Option B: Set webhook manually using curl

Replace `YOUR_BOT_TOKEN` with your actual bot token:

```bash
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://redditanalyzer-kappa.vercel.app/webhook", "drop_pending_updates": true}'
```

#### Option C: Use Telegram Bot API directly

Visit this URL in your browser (replace YOUR_BOT_TOKEN):
```
https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook?url=https://redditanalyzer-kappa.vercel.app/webhook&drop_pending_updates=true
```

---

### Step 4: Verify Webhook Setup

Check if the webhook is configured correctly:

```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getWebhookInfo"
```

You should see:
```json
{
  "ok": true,
  "result": {
    "url": "https://redditanalyzer-kappa.vercel.app/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

---

### Step 5: Test Your Bot

1. Open Telegram
2. Find your bot
3. Send `/start`
4. You should receive a welcome message!

---

## Troubleshooting

### Bot still not responding?

1. **Check Vercel Logs:**
   - Go to your Vercel dashboard
   - Click on "Deployments" → Latest deployment → "View Function Logs"
   - Send a message to your bot
   - Check if any requests are coming in

2. **Verify environment variables:**
   ```bash
   # Check if DATABASE_URL is set correctly
   curl https://redditanalyzer-kappa.vercel.app/database-health
   ```
   Should return: `{"status": "healthy", "database": "connected"}`

3. **Check webhook status:**
   ```bash
   curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getWebhookInfo"
   ```
   - Look for `last_error_message` - this will tell you if Telegram is having issues reaching your webhook
   - Check `pending_update_count` - if this is high, updates are queued but not being processed

4. **Common issues:**

   **Database connection errors:**
   - Make sure you're using port `6543` (connection pooling) not `5432` (direct connection)
   - Verify your password doesn't have special characters that need URL encoding
   - Check that your Supabase project hasn't paused due to inactivity

   **Webhook not receiving updates:**
   - Ensure the webhook URL is `https://` (not `http://`)
   - Make sure you redeployed after setting environment variables
   - Try deleting and re-setting the webhook

   **Missing environment variables:**
   - Telegram returns 500 errors → `TELEGRAM_BOT_TOKEN` not set
   - Database errors → `DATABASE_URL` not set or incorrect format
   - Payment features fail → Stripe keys not set

---

## Quick Fix Checklist

- [ ] All environment variables set in Vercel dashboard
- [ ] Redeployed after setting environment variables
- [ ] DATABASE_URL uses port 6543 (connection pooling)
- [ ] Webhook configured to point to `https://redditanalyzer-kappa.vercel.app/webhook`
- [ ] Webhook info shows no errors
- [ ] Database health check returns "connected"
- [ ] Tested bot with `/start` command

---

## Useful Commands

### Get bot info
```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getMe"
```

### Delete webhook (to test locally with polling)
```bash
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/deleteWebhook?drop_pending_updates=true"
```

### Set webhook
```bash
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://redditanalyzer-kappa.vercel.app/webhook"}'
```

### Check webhook status
```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getWebhookInfo"
```

---

## Contact & Support

If you're still having issues:
1. Check Vercel function logs
2. Check Supabase logs
3. Verify all environment variables are set correctly
4. Make sure you redeployed after configuration changes
