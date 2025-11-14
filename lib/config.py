"""
Configuration module for Reddit Analyzer Bot
Handles environment variables and configuration settings
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    def __init__(self):
        # Telegram Bot Token
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
            
        # Reddit API URL
        self.REDDIT_API_URL = os.getenv('REDDIT_API_URL', 'https://reddit-analyzer-api.onrender.com')
        
        # OpenAI API Key
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
            
        # Database path
        # Use platform-appropriate default
        import platform
        if platform.system() == 'Windows':
            default_path = 'reddit_bot.db'  # Local to script directory
        else:
            default_path = '/opt/render/project/data/reddit_bot.db'
        self.DATABASE_PATH = os.getenv('DATABASE_PATH', default_path) 
               
        # Bot settings
        self.MAX_SCRAPE_POSTS = int(os.getenv('MAX_SCRAPE_POSTS', '50'))
        self.DEFAULT_ANALYSIS_DAYS = int(os.getenv('DEFAULT_ANALYSIS_DAYS', '7'))
        self.DEFAULT_SEARCH_LIMIT = int(os.getenv('DEFAULT_SEARCH_LIMIT', '100'))
        
        # Rate limiting
        self.RATE_LIMIT_SECONDS = int(os.getenv('RATE_LIMIT_SECONDS', '1'))
        
        # Logging
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

        self.STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
        self.STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
        self.STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
        self.INITIAL_FREE_COINS = int(os.getenv('INITIAL_FREE_COINS', '10'))
        self.COINS_EXPIRY_DAYS = int(os.getenv('COINS_EXPIRY_DAYS', '30'))
        
    def __str__(self):
        """String representation for debugging (hide sensitive data)"""
        return f"""
Reddit Analyzer Bot Configuration:
- Telegram Bot Token: {'*' * 10}{self.TELEGRAM_BOT_TOKEN[-5:] if self.TELEGRAM_BOT_TOKEN else 'NOT SET'}
- Reddit API URL: {self.REDDIT_API_URL}
- OpenAI API Key: {'*' * 10}{self.OPENAI_API_KEY[-5:] if self.OPENAI_API_KEY else 'NOT SET'}
- Database Path: {self.DATABASE_PATH}
- Max Scrape Posts: {self.MAX_SCRAPE_POSTS}
- Default Analysis Days: {self.DEFAULT_ANALYSIS_DAYS}
- Default Search Limit: {self.DEFAULT_SEARCH_LIMIT}
- Rate Limit Seconds: {self.RATE_LIMIT_SECONDS}
- Log Level: {self.LOG_LEVEL}
"""