# Supabase Setup for Vercel Deployment

Your bot now uses **Supabase's REST API** instead of direct PostgreSQL connections. This works perfectly with Vercel's serverless environment!

## Step 1: Get Your Supabase Credentials

1. Go to your Supabase project: https://supabase.com/dashboard
2. Select your project
3. Click **Settings** (gear icon) in the left sidebar
4. Click **API** section

You'll see two important values:

### Project URL
```
https://[YOUR_PROJECT_REF].supabase.co
```

### API Keys
- **anon/public key** - Use this for the bot
- **service_role key** - More powerful, but keep it secret

## Step 2: Add Environment Variables to Vercel

Go to Vercel Dashboard → Settings → Environment Variables

Add these TWO new variables:

```bash
SUPABASE_URL=https://lcoakvgumktfcxbtfezl.supabase.co
```

```bash
SUPABASE_ANON_KEY=your_anon_key_here
```

**Or** use the service role key for full access:

```bash
SUPABASE_SERVICE_KEY=your_service_role_key_here
```

**Note:** The bot will automatically extract the project ref from your existing `DATABASE_URL` if `SUPABASE_URL` is not set.

## Step 3: Keep Existing Environment Variables

Make sure these are still set:

- ✅ `TELEGRAM_BOT_TOKEN` - Your bot token
- ✅ `DATABASE_URL` - Keep this (used as fallback)
- ✅ `OPENAI_API_KEY` - Your OpenAI key
- ✅ `STRIPE_SECRET_KEY` - For payments (optional)

## Step 4: Redeploy

1. Go to Vercel Dashboard
2. Click **Deployments**
3. Find the latest deployment
4. Click the three dots (...) → **Redeploy**

## Step 5: Test

After deployment (1-2 minutes):

1. Send `/start` to your Telegram bot
2. You should get a welcome message!

## How It Works

The bot now uses:
- **Supabase REST API** for database operations (HTTP requests)
- **No direct PostgreSQL connections** (fixes Vercel networking issues)
- **Same database tables** (no data migration needed)

## Troubleshooting

### Can't find SUPABASE_URL?

The bot will try to extract it from your DATABASE_URL automatically:
- `postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:6543/postgres`
- Becomes: `https://PROJECT.supabase.co`

### Bot still not working?

Check Vercel logs for error messages:
- Go to Deployments → Latest → View Function Logs
- Send a message to your bot
- Check for errors

### Need the service role key instead?

The anon key has Row Level Security (RLS) restrictions. If you get permission errors, use the service role key instead:
```bash
SUPABASE_SERVICE_KEY=eyJhbGc...your_service_role_key
```

## What Changed?

- ✅ Added `supabase-py` library
- ✅ Created `database_supabase.py` wrapper
- ✅ Updated bot to use REST API instead of PostgreSQL connections
- ✅ Works perfectly with Vercel's serverless environment
- ✅ No more "[Errno 99] Cannot assign requested address" errors!
