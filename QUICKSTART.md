# Quick Start - Fix Your Bot in 3 Steps

Your bot is deployed and running, but it's not receiving Telegram messages because **the webhook isn't configured**.

## Step 1: Set Environment Variables in Vercel

1. Go to your Vercel dashboard: https://vercel.com
2. Select your project: `redditanalyzer-kappa`
3. Go to **Settings** → **Environment Variables**
4. Add these variables:

### Required Variables:

```bash
TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>
```

```bash
DATABASE_URL=postgresql://postgres.lcggdsdgasdtfcxbtfezl:<YOUR_ACTUAL_PASSWORD>@db.lcggdsdgasdtfcxbtfezl.supabase.co:6543/postgres
```
⚠️ **Replace `<YOUR_ACTUAL_PASSWORD>` with your actual Supabase password!**

```bash
OPENAI_API_KEY=<your_openai_api_key>
```

### Optional (for payments):

```bash
STRIPE_SECRET_KEY=<your_stripe_secret_key>
STRIPE_PUBLISHABLE_KEY=<your_stripe_publishable_key>
STRIPE_WEBHOOK_SECRET=<your_stripe_webhook_secret>
```

5. **IMPORTANT:** After adding variables, click **Redeploy** on your latest deployment!

---

## Step 2: Configure Telegram Webhook

### Option A: Using the Setup Script (Recommended)

1. Create a `.env` file in the `vercel-bot` folder:
```bash
cd vercel-bot
nano .env  # or use any text editor
```

2. Add your bot token to `.env`:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

3. Install dependencies and run the setup script:
```bash
pip install requests python-dotenv
python setup_webhook.py
```

### Option B: Manual Setup (Quick)

Replace `YOUR_BOT_TOKEN` with your actual token and run this command:

```bash
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://redditanalyzer-kappa.vercel.app/webhook", "drop_pending_updates": true}'
```

Or visit this URL in your browser:
```
https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook?url=https://redditanalyzer-kappa.vercel.app/webhook&drop_pending_updates=true
```

---

## Step 3: Test Your Bot

1. Open Telegram
2. Find your bot
3. Send: `/start`
4. You should get a welcome message! 🎉

---

## Troubleshooting

### Still not working?

Run the diagnostic script:
```bash
cd vercel-bot
python diagnose.py
```

This will check:
- ✅ Vercel deployment status
- ✅ Database connectivity
- ✅ Telegram bot configuration
- ✅ Webhook setup
- ✅ Environment variables

### Common Issues:

**1. "Invalid bot token"**
- Double-check your `TELEGRAM_BOT_TOKEN` in Vercel environment variables
- Make sure you redeployed after adding it

**2. "Database connection failed"**
- Verify `DATABASE_URL` format: must use port `6543` (not `5432`)
- Check that your Supabase password is correct
- Ensure no special characters need URL encoding

**3. "Webhook not configured"**
- Run `python setup_webhook.py`
- Or use the manual curl command from Step 2

**4. "Environment variable not set"**
- Go to Vercel dashboard → Settings → Environment Variables
- Add missing variables
- **Redeploy** your app!

---

## What's Happening Behind the Scenes?

Your deployment has these components:

1. **Vercel App** (✅ Working)
   - URL: https://redditanalyzer-kappa.vercel.app
   - Status: Healthy

2. **Database** (✅ Connected)
   - Supabase PostgreSQL
   - Connection pooling on port 6543

3. **Telegram Webhook** (❌ Not Configured - **THIS IS YOUR ISSUE**)
   - Needs to point to: `https://redditanalyzer-kappa.vercel.app/webhook`
   - Currently not set up

4. **Environment Variables** (⚠️ Need to be set in Vercel)
   - Must be configured in Vercel dashboard
   - Then redeploy for changes to take effect

---

## Need More Help?

See the full deployment guide: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

Or check your deployment health:
- Main API: https://redditanalyzer-kappa.vercel.app/
- Health check: https://redditanalyzer-kappa.vercel.app/health
- Database: https://redditanalyzer-kappa.vercel.app/database-health
