# Reddit Analyzer Telegram Bot - Vercel Deployment

A powerful Telegram bot that analyzes Reddit subreddits to help content creators find the best communities for their content. Deployed on Vercel with Supabase PostgreSQL database.

## Features

- **Subreddit Analysis**: Deep analysis of engagement, requirements, and performance
- **Smart Search**: Find relevant subreddits by topic
- **Niche Discovery**: Discover smaller, highly-engaged communities
- **Comparison Tools**: Compare multiple subreddits side-by-side
- **Coin System**: Monetization with Stripe payment integration
- **Webhook Mode**: Serverless deployment on Vercel
- **PostgreSQL Database**: Scalable Supabase integration

## Architecture

```
vercel-bot/
├── api/
│   ├── index.py          # Main Flask API (webhooks, payments, coin management)
│   └── bot_handler.py    # Telegram bot commands (webhook mode)
├── lib/
│   ├── database.py       # PostgreSQL database with asyncpg
│   ├── config.py         # Configuration management
│   ├── payment.py        # Stripe payment processor
│   ├── utils.py          # Helper functions
│   └── ...              # Other utility modules
├── vercel.json          # Vercel configuration
├── requirements.txt     # Python dependencies
├── .env.example        # Environment variables template
└── README.md           # This file
```

## Prerequisites

Before deployment, you'll need:

1. **Telegram Bot Token**
   - Create a bot via [@BotFather](https://t.me/botfather)
   - Save the token

2. **Supabase Account**
   - Sign up at [supabase.com](https://supabase.com)
   - Create a new project
   - Get your PostgreSQL connection string

3. **Stripe Account**
   - Sign up at [stripe.com](https://stripe.com)
   - Get API keys and webhook secret

4. **Reddit API Credentials**
   - Create an app at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
   - Get client ID and secret

5. **Vercel Account**
   - Sign up at [vercel.com](https://vercel.com)

## Deployment Steps

### 1. Supabase Database Setup

1. Go to your Supabase project dashboard
2. Navigate to **Database** > **Connection Pooling**
3. Enable connection pooling mode: **Transaction**
4. Copy the connection string (format: `postgresql://user:password@host:port/database`)
5. The database tables will be created automatically on first run

### 2. Stripe Webhook Setup

1. Go to [Stripe Dashboard](https://dashboard.stripe.com)
2. Navigate to **Developers** > **Webhooks**
3. Click **Add endpoint**
4. Set endpoint URL: `https://your-vercel-app.vercel.app/stripe-webhook`
5. Select events to listen for:
   - `checkout.session.completed`
   - `payment_intent.payment_failed`
6. Copy the webhook signing secret

### 3. Deploy to Vercel

#### Option A: Deploy via Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy from the vercel-bot directory
cd vercel-bot
vercel

# Follow prompts and configure project
```

#### Option B: Deploy via GitHub

1. Push this directory to a GitHub repository
2. Go to [vercel.com/new](https://vercel.com/new)
3. Import your GitHub repository
4. Vercel will auto-detect the configuration
5. Click **Deploy**

### 4. Configure Environment Variables

In Vercel Dashboard, go to **Settings** > **Environment Variables** and add:

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_URL=https://your-app.vercel.app/webhook

# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Stripe
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Reddit
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=RedditAnalyzerBot/1.0

# OpenAI (optional)
OPENAI_API_KEY=sk-xxx

# Airtable (optional)
AIRTABLE_API_KEY=your_key
AIRTABLE_BASE_ID=your_base

# Bot Settings
INITIAL_FREE_COINS=10
COINS_EXPIRY_DAYS=30
```

### 5. Set Telegram Webhook

After deployment, set the webhook for your bot:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-vercel-app.vercel.app/webhook"}'
```

Or visit in your browser:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-vercel-app.vercel.app/webhook
```

### 6. Verify Deployment

1. Send `/start` to your bot on Telegram
2. Check Vercel logs for any errors
3. Test a command like `/balance`
4. Verify database connection at: `https://your-app.vercel.app/database-health`

## Available Commands

### User Commands
- `/start` - Welcome message and registration
- `/help` - Show all commands
- `/balance` - Check coin balance
- `/buy` - Purchase coin packages
- `/analyze <subreddit>` - Analyze subreddit (2 coins)
- `/search <topic>` - Search for subreddits (1 coin)
- `/niche <topic>` - Find niche communities (3 coins)
- `/compare <sub1,sub2,sub3>` - Compare subreddits (5 coins)
- `/rules <subreddit>` - Get posting rules (1 coin)
- `/requirements <subreddit>` - Check karma requirements (2 coins)

### Admin Commands
- `/admin` - Admin panel
- `/users` - List all users
- `/stats` - Bot statistics

## Coin Packages

Default packages (configurable in database):
- **Starter Pack**: 20 coins - $9.99
- **Basic Pack**: 50 + 5 bonus coins - $19.99
- **Pro Pack**: 100 + 15 bonus coins - $34.99
- **Premium Pack**: 250 + 50 bonus coins - $74.99
- **Ultimate Pack**: 500 + 150 bonus coins - $139.99

## Development

### Local Development

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in values
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the Flask app:
   ```bash
   python api/index.py
   ```
5. Use ngrok to expose local server for webhooks:
   ```bash
   ngrok http 5000
   ```

### Adding New Commands

1. Open `api/bot_handler.py`
2. Add a new command handler function:
   ```python
   async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
       # Your command logic here
       await update.message.reply_text("Hello!")
   ```
3. Register the handler in `init_application()`:
   ```python
   application.add_handler(CommandHandler("mycommand", my_command))
   ```

### Database Migrations

The database schema is automatically created on first run. To modify the schema:

1. Edit `lib/database.py`
2. Modify the `_init_db()` method
3. Redeploy to Vercel

## Extending Reddit API Features

The current bot handler has placeholder commands for Reddit analysis. To implement full Reddit functionality:

1. Copy your existing Reddit analysis code from `reddit-analyzer-bot-main 2/reddit_api.py`
2. Create a new file `api/reddit_analyzer.py` with the analysis logic
3. Import and use in `bot_handler.py` command handlers
4. Or create additional Flask endpoints in `api/index.py` for Reddit analysis

Example:
```python
# In api/index.py, add:
@app.route('/analyze', methods=['POST'])
def analyze_subreddit():
    data = request.get_json()
    subreddit = data.get('subreddit')
    # Reddit analysis logic here
    return jsonify(result)

# In bot_handler.py, call the endpoint:
async def analyze_command(update, context):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://your-app.vercel.app/analyze',
            json={'subreddit': subreddit}
        ) as resp:
            result = await resp.json()
```

## Monitoring & Logs

- **Vercel Logs**: Dashboard > Your Project > Logs
- **Database Logs**: Supabase Dashboard > Database > Logs
- **Stripe Events**: Stripe Dashboard > Developers > Events

## Troubleshooting

### Bot not responding
- Check Vercel function logs
- Verify webhook is set correctly: `/getWebhookInfo` in Telegram
- Check environment variables are set

### Database connection errors
- Verify DATABASE_URL is correct
- Check Supabase connection pooling is enabled
- Ensure database allows connections from Vercel IPs

### Payment not working
- Verify Stripe webhook secret is correct
- Check Stripe webhook endpoint is receiving events
- View Stripe Dashboard > Events for webhook delivery status

### Commands cost coins but don't work
- Check Vercel function timeout (increase if needed)
- Verify Reddit API credentials are correct
- Check function logs for specific errors

## Security Notes

- Never commit `.env` file with actual credentials
- Use Vercel environment variables for sensitive data
- Stripe webhook signatures are verified automatically
- Database uses connection pooling for security

## Cost Estimation

- **Vercel**: Free tier supports ~100K requests/month
- **Supabase**: Free tier includes 500MB database + 2GB bandwidth
- **Stripe**: 2.9% + $0.30 per successful transaction
- **Reddit API**: Free (with rate limits)
- **OpenAI**: Pay per token (optional)

## Support

For issues or questions:
1. Check Vercel function logs
2. Review Supabase database logs
3. Test endpoints individually: `/health`, `/database-health`

## License

MIT License - Feel free to modify and use for your own projects!

---

Made with Vercel + Supabase + Telegram Bot API
