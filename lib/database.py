"""
PostgreSQL Database module for Reddit Analyzer Bot with Supabase
Migrated from SQLite to PostgreSQL for serverless deployment
"""

import asyncio
import asyncpg
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, database_url: str = None):
        """Initialize database connection pool"""
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL not found in environment variables")

        self.pool = None
        self._lock = asyncio.Lock()

    async def init_pool(self):
        """Initialize connection pool"""
        if not self.pool:
            async with self._lock:
                if not self.pool:
                    self.pool = await asyncpg.create_pool(
                        self.database_url,
                        min_size=1,
                        max_size=10,
                        command_timeout=60
                    )
                    await self._init_db()

    async def close_pool(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None

    @asynccontextmanager
    async def _get_connection(self):
        """Get a database connection from pool"""
        if not self.pool:
            await self.init_pool()

        async with self.pool.acquire() as conn:
            yield conn

    async def _init_db(self):
        """Initialize database tables"""
        async with self._get_connection() as conn:
            # Users table (enhanced with coin fields)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    added_by BIGINT,
                    last_seen TIMESTAMP,
                    coin_balance INTEGER DEFAULT 10,
                    coins_expire_at TIMESTAMP,
                    total_coins_purchased INTEGER DEFAULT 0,
                    free_coins_claimed BOOLEAN DEFAULT TRUE
                )
            """)

            # Coin transactions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS coin_transactions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    transaction_type TEXT,
                    amount INTEGER,
                    balance_after INTEGER,
                    description TEXT,
                    stripe_payment_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index on user_id for faster lookups
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_coin_transactions_user_id
                ON coin_transactions(user_id)
            """)

            # Coin packages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS coin_packages (
                    id SERIAL PRIMARY KEY,
                    package_name TEXT,
                    coins INTEGER,
                    price_usd DECIMAL(10, 2),
                    stripe_price_id TEXT,
                    bonus_coins INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Payment history table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS payment_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    stripe_payment_intent TEXT UNIQUE,
                    stripe_session_id TEXT,
                    amount_usd DECIMAL(10, 2),
                    coins_purchased INTEGER,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            # Command costs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS command_costs (
                    command TEXT PRIMARY KEY,
                    cost INTEGER,
                    description TEXT
                )
            """)

            # Usage logs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    username TEXT,
                    first_name TEXT,
                    command TEXT,
                    params TEXT,
                    coins_spent INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for faster log queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_logs_timestamp
                ON usage_logs(timestamp DESC)
            """)

            # Admin actions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_actions (
                    id SERIAL PRIMARY KEY,
                    admin_id BIGINT REFERENCES users(user_id),
                    action TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Bot statistics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id SERIAL PRIMARY KEY,
                    stat_name TEXT UNIQUE,
                    stat_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert default coin packages
            default_packages = [
                ('Starter Pack', 20, 9.99, None, 0),
                ('Basic Pack', 50, 19.99, None, 5),
                ('Pro Pack', 100, 34.99, None, 15),
                ('Premium Pack', 250, 74.99, None, 50),
                ('Ultimate Pack', 500, 139.99, None, 150),
            ]

            for package in default_packages:
                await conn.execute("""
                    INSERT INTO coin_packages
                    (package_name, coins, price_usd, stripe_price_id, bonus_coins)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT DO NOTHING
                """, *package)

            # Insert default command costs
            default_costs = [
                ('analyze', 2, 'Full subreddit analysis'),
                ('requirements', 2, 'Posting requirements check'),
                ('compare', 5, 'Compare multiple subreddits'),
                ('search', 1, 'Search for subreddits'),
                ('niche', 3, 'Niche community analysis'),
                ('scrape', 0, 'Basic post scraping (free)'),
                ('scrape_ai_10', 2, 'AI recreation for 10 posts'),
                ('scrape_ai_20', 4, 'AI recreation for 20 posts'),
                ('scrape_ai_30', 6, 'AI recreation for 30 posts'),
                ('rules', 1, 'Get subreddit rules'),
                ('flairs', 1, 'Analyze flair performance'),
                ('discover', 10, 'Discover related subreddits (admin only)'),
            ]

            for cost_data in default_costs:
                await conn.execute("""
                    INSERT INTO command_costs (command, cost, description)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (command) DO UPDATE SET
                        cost = EXCLUDED.cost,
                        description = EXCLUDED.description
                """, *cost_data)

            # Add initial admins with unlimited coins
            initial_admins = [
                (5028346767, 'panagiotis_krb', 'Panagiotis', 'Karampetsos'),
                (6150863409, None, 'Admin2', None),
                (5157639618, None, 'Admin3', None),
                (6923635816, None, 'Admin4', None)
            ]

            for admin_id, username, first_name, last_name in initial_admins:
                await conn.execute("""
                    INSERT INTO users
                    (user_id, username, first_name, last_name, is_admin, is_active,
                     coin_balance, coins_expire_at, free_coins_claimed)
                    VALUES ($1, $2, $3, $4, TRUE, TRUE, 999999,
                            CURRENT_TIMESTAMP + INTERVAL '10 years', TRUE)
                    ON CONFLICT (user_id) DO UPDATE SET
                        is_admin = TRUE,
                        coin_balance = 999999,
                        coins_expire_at = CURRENT_TIMESTAMP + INTERVAL '10 years'
                """, admin_id, username, first_name, last_name)

    # ========== USER MANAGEMENT METHODS ==========

    async def add_user(self, user_id: int, username: str = None,
                      first_name: str = None, last_name: str = None,
                      added_by: int = None) -> bool:
        """Add a new user with initial free coins"""
        try:
            async with self._get_connection() as conn:
                initial_coins = int(os.getenv('INITIAL_FREE_COINS', '10'))
                expiry_days = int(os.getenv('COINS_EXPIRY_DAYS', '30'))
                expiry_date = datetime.now() + timedelta(days=expiry_days)

                await conn.execute("""
                    INSERT INTO users
                    (user_id, username, first_name, last_name, added_by,
                     coin_balance, coins_expire_at, free_coins_claimed)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        is_active = TRUE,
                        last_seen = CURRENT_TIMESTAMP
                """, user_id, username, first_name, last_name, added_by,
                     initial_coins, expiry_date)

                # Log the transaction
                await self.add_coins(
                    user_id, initial_coins, 'initial_signup',
                    'Welcome bonus coins', extend_expiry=False
                )

                logger.info(f"User {user_id} added with {initial_coins} coins")
                return True

        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False

    async def check_user_access(self, user_id: int) -> bool:
        """Check if user is active"""
        try:
            async with self._get_connection() as conn:
                result = await conn.fetchval("""
                    SELECT is_active FROM users WHERE user_id = $1
                """, user_id)
                return result if result is not None else False
        except Exception as e:
            logger.error(f"Error checking user access: {e}")
            return False

    async def is_admin(self, user_id: int) -> bool:
        """Check if user has admin privileges"""
        try:
            async with self._get_connection() as conn:
                result = await conn.fetchval("""
                    SELECT is_admin FROM users WHERE user_id = $1
                """, user_id)
                return result if result is not None else False
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    async def make_admin(self, user_id: int) -> bool:
        """Grant admin status and unlimited coins"""
        try:
            async with self._get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET
                        is_admin = TRUE,
                        coin_balance = 999999,
                        coins_expire_at = CURRENT_TIMESTAMP + INTERVAL '10 years'
                    WHERE user_id = $1
                """, user_id)
                return True
        except Exception as e:
            logger.error(f"Error making user admin: {e}")
            return False

    async def remove_admin(self, user_id: int) -> bool:
        """Remove admin status"""
        try:
            async with self._get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET is_admin = FALSE WHERE user_id = $1
                """, user_id)
                return True
        except Exception as e:
            logger.error(f"Error removing admin: {e}")
            return False

    async def deactivate_user(self, user_id: int) -> bool:
        """Deactivate user (soft delete)"""
        try:
            async with self._get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET is_active = FALSE WHERE user_id = $1
                """, user_id)
                return True
        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users sorted by admin status and date"""
        try:
            async with self._get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT user_id, username, first_name, last_name,
                           is_admin, is_active, added_date, coin_balance
                    FROM users
                    ORDER BY is_admin DESC, added_date DESC
                """)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []

    # ========== COIN SYSTEM METHODS ==========

    async def get_user_coins(self, user_id: int) -> Dict[str, Any]:
        """Get user coins"""
        try:
            async with self._get_connection() as conn:
                result = await conn.fetchrow("""
                    SELECT coin_balance, coins_expire_at, is_admin
                    FROM users WHERE user_id = $1
                """, user_id)

                if not result:
                    return {
                        'balance': 0,
                        'expires_at': None,
                        'is_expired': False,
                        'is_admin': False
                    }

                balance, expire_at, is_admin = result['coin_balance'], result['coins_expire_at'], result['is_admin']

                # Admins have unlimited coins
                if is_admin:
                    return {
                        'balance': 999999,
                        'expires_at': None,
                        'is_expired': False,
                        'is_admin': True
                    }

                # Check if coins expired
                is_expired = False
                if expire_at and datetime.now() > expire_at:
                    is_expired = True
                    balance = 0

                return {
                    'balance': balance,
                    'expires_at': expire_at.isoformat() if expire_at else None,
                    'is_expired': is_expired,
                    'is_admin': False
                }

        except Exception as e:
            logger.error(f"Error getting user coins: {e}")
            return {
                'balance': 0,
                'expires_at': None,
                'is_expired': False,
                'is_admin': False
            }

    async def deduct_coins(self, user_id: int, amount: int, command: str,
                          description: str = None) -> bool:
        """Deduct coins from user"""
        try:
            async with self._get_connection() as conn:
                # Check if admin (unlimited coins)
                is_admin = await conn.fetchval("""
                    SELECT is_admin FROM users WHERE user_id = $1
                """, user_id)

                if is_admin:
                    # Log the transaction but don't deduct
                    await self._log_transaction(
                        user_id, 'spend', -amount, 999999,
                        description or f"Used {command} command"
                    )
                    return True

                # Get current balance
                coins_data = await self.get_user_coins(user_id)

                if coins_data['is_expired'] or coins_data['balance'] < amount:
                    return False

                # Deduct coins
                new_balance = coins_data['balance'] - amount
                await conn.execute("""
                    UPDATE users SET
                        coin_balance = $1,
                        last_seen = CURRENT_TIMESTAMP
                    WHERE user_id = $2
                """, new_balance, user_id)

                # Log transaction
                await self._log_transaction(
                    user_id, 'spend', -amount, new_balance,
                    description or f"Used {command} command"
                )

                return True

        except Exception as e:
            logger.error(f"Error deducting coins: {e}")
            return False

    async def add_coins(self, user_id: int, amount: int,
                       transaction_type: str = 'admin_add',
                       description: str = None,
                       extend_expiry: bool = True) -> bool:
        """Add coins to user"""
        try:
            async with self._get_connection() as conn:
                # Check if admin
                is_admin = await conn.fetchval("""
                    SELECT is_admin FROM users WHERE user_id = $1
                """, user_id)

                if is_admin:
                    # Admins always have unlimited coins
                    return True

                # Get current balance
                current_balance = await conn.fetchval("""
                    SELECT coin_balance FROM users WHERE user_id = $1
                """, user_id)

                if current_balance is None:
                    current_balance = 0

                new_balance = current_balance + amount

                # Update balance
                if extend_expiry:
                    expiry_days = int(os.getenv('COINS_EXPIRY_DAYS', '30'))
                    new_expiry = datetime.now() + timedelta(days=expiry_days)

                    await conn.execute("""
                        UPDATE users SET
                            coin_balance = $1,
                            coins_expire_at = $2,
                            last_seen = CURRENT_TIMESTAMP,
                            total_coins_purchased = total_coins_purchased + $3
                        WHERE user_id = $4
                    """, new_balance, new_expiry, amount, user_id)
                else:
                    await conn.execute("""
                        UPDATE users SET
                            coin_balance = $1,
                            last_seen = CURRENT_TIMESTAMP
                        WHERE user_id = $2
                    """, new_balance, user_id)

                # Log transaction
                await self._log_transaction(
                    user_id, transaction_type, amount, new_balance,
                    description or f"Added {amount} coins"
                )

                return True

        except Exception as e:
            logger.error(f"Error adding coins: {e}")
            return False

    async def _log_transaction(self, user_id: int, transaction_type: str,
                              amount: int, balance_after: int,
                              description: str, stripe_payment_id: str = None):
        """Log a coin transaction"""
        try:
            async with self._get_connection() as conn:
                await conn.execute("""
                    INSERT INTO coin_transactions
                    (user_id, transaction_type, amount, balance_after,
                     description, stripe_payment_id)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, user_id, transaction_type, amount, balance_after,
                     description, stripe_payment_id)
        except Exception as e:
            logger.error(f"Error logging transaction: {e}")

    async def get_user_transaction_history(self, user_id: int,
                                          limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's transaction history"""
        try:
            async with self._get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT transaction_type, amount, balance_after,
                           description, created_at
                    FROM coin_transactions
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, user_id, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting transaction history: {e}")
            return []

    # ========== COMMAND & PRICING METHODS ==========

    async def get_command_cost(self, command: str) -> int:
        """Get coin cost for a command"""
        try:
            async with self._get_connection() as conn:
                cost = await conn.fetchval("""
                    SELECT cost FROM command_costs WHERE command = $1
                """, command)
                return cost if cost is not None else 0
        except Exception as e:
            logger.error(f"Error getting command cost: {e}")
            return 0

    async def get_coin_packages(self) -> List[Dict[str, Any]]:
        """Get available coin packages"""
        try:
            async with self._get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT package_name, coins, price_usd, bonus_coins
                    FROM coin_packages
                    WHERE is_active = TRUE
                    ORDER BY price_usd ASC
                """)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting packages: {e}")
            return []

    # ========== PAYMENT METHODS ==========

    async def add_payment_history(self, user_id: int, session_id: str,
                                 amount_usd: float, coins_purchased: int,
                                 status: str = 'pending') -> bool:
        """Add payment history record"""
        try:
            async with self._get_connection() as conn:
                await conn.execute("""
                    INSERT INTO payment_history
                    (user_id, stripe_session_id, amount_usd, coins_purchased, status)
                    VALUES ($1, $2, $3, $4, $5)
                """, user_id, session_id, amount_usd, coins_purchased, status)
                return True
        except Exception as e:
            logger.error(f"Error adding payment history: {e}")
            return False

    async def update_payment_status(self, session_id: str, status: str,
                                   payment_intent: str = None) -> bool:
        """Update payment status"""
        try:
            async with self._get_connection() as conn:
                await conn.execute("""
                    UPDATE payment_history SET
                        status = $1,
                        stripe_payment_intent = $2,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE stripe_session_id = $3
                """, status, payment_intent, session_id)
                return True
        except Exception as e:
            logger.error(f"Error updating payment status: {e}")
            return False

    # ========== LOGGING & ANALYTICS METHODS ==========

    async def log_usage(self, user_id: int, username: str, first_name: str,
                       command: str, params: str = None, coins_spent: int = 0):
        """Log command usage"""
        try:
            async with self._get_connection() as conn:
                await conn.execute("""
                    INSERT INTO usage_logs
                    (user_id, username, first_name, command, params, coins_spent)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, user_id, username, first_name, command, params, coins_spent)
        except Exception as e:
            logger.error(f"Error logging usage: {e}")

    async def log_admin_action(self, admin_id: int, action: str, details: str):
        """Log admin actions"""
        try:
            async with self._get_connection() as conn:
                await conn.execute("""
                    INSERT INTO admin_actions (admin_id, action, details)
                    VALUES ($1, $2, $3)
                """, admin_id, action, details)
        except Exception as e:
            logger.error(f"Error logging admin action: {e}")

    async def get_bot_statistics(self) -> Dict[str, Any]:
        """Get overall bot statistics"""
        try:
            async with self._get_connection() as conn:
                total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
                active_users = await conn.fetchval("""
                    SELECT COUNT(*) FROM users WHERE is_active = TRUE
                """)
                total_commands = await conn.fetchval("""
                    SELECT COUNT(*) FROM usage_logs
                    WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '24 hours'
                """)

                # Get top commands
                top_commands = await conn.fetch("""
                    SELECT command, COUNT(*) as count
                    FROM usage_logs
                    WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '7 days'
                    GROUP BY command
                    ORDER BY count DESC
                    LIMIT 5
                """)

                return {
                    'total_users': total_users,
                    'active_users': active_users,
                    'commands_24h': total_commands,
                    'top_commands': [dict(row) for row in top_commands]
                }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    async def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent usage logs"""
        try:
            async with self._get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT user_id, username, first_name, command,
                           params, coins_spent, timestamp
                    FROM usage_logs
                    ORDER BY timestamp DESC
                    LIMIT $1
                """, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting recent logs: {e}")
            return []
