"""
Supabase-based Database module for Vercel serverless deployment
Uses Supabase REST API instead of direct PostgreSQL connections
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseDatabase:
    """Database wrapper using Supabase REST API for Vercel compatibility"""

    def __init__(self):
        """Initialize Supabase client"""
        # Extract Supabase URL and key from DATABASE_URL or environment
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY') or os.getenv('SUPABASE_SERVICE_KEY')

        # If not set, try to derive from DATABASE_URL
        if not self.supabase_url:
            database_url = os.getenv('DATABASE_URL', '')
            if 'supabase.co' in database_url:
                # Extract project ref from DATABASE_URL
                # Format: postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:6543/postgres
                import re
                match = re.search(r'@db\.([^.]+)\.supabase\.co', database_url)
                if match:
                    project_ref = match.group(1)
                    self.supabase_url = f'https://{project_ref}.supabase.co'

        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_ANON_KEY "
                "environment variables"
            )

        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info(f"Supabase client initialized for {self.supabase_url}")

    async def init_pool(self):
        """No-op for compatibility with existing code"""
        logger.info("Using Supabase REST API (no pool initialization needed)")
        # Tables should already exist in Supabase
        pass

    async def close_pool(self):
        """No-op for compatibility"""
        pass

    # ========== USER MANAGEMENT METHODS ==========

    async def add_user(self, user_id: int, username: str = None,
                      first_name: str = None, last_name: str = None,
                      added_by: int = None) -> bool:
        """Add a new user with initial free coins (or update existing user profile)"""
        try:
            # Check if user already exists
            existing = self.client.table('users')\
                .select('user_id, coin_balance')\
                .eq('user_id', user_id)\
                .execute()

            if existing.data:
                # User exists - only update profile info, NOT coins
                update_data = {
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_active': True,
                    'last_seen': datetime.now().isoformat()
                }

                self.client.table('users')\
                    .update(update_data)\
                    .eq('user_id', user_id)\
                    .execute()

                logger.info(f"User {user_id} profile updated")
                return True

            else:
                # New user - add with initial coins
                initial_coins = int(os.getenv('INITIAL_FREE_COINS', '10'))
                expiry_days = int(os.getenv('COINS_EXPIRY_DAYS', '30'))
                expiry_date = (datetime.now() + timedelta(days=expiry_days)).isoformat()

                data = {
                    'user_id': user_id,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'added_by': added_by,
                    'coin_balance': initial_coins,
                    'coins_expire_at': expiry_date,
                    'free_coins_claimed': True
                }

                self.client.table('users').insert(data).execute()

                logger.info(f"User {user_id} added with {initial_coins} coins")
                return True

        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False

    async def is_admin(self, user_id: int) -> bool:
        """Check if user has admin privileges"""
        try:
            result = self.client.table('users')\
                .select('is_admin')\
                .eq('user_id', user_id)\
                .single()\
                .execute()

            return result.data.get('is_admin', False) if result.data else False

        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    async def get_user_coins(self, user_id: int) -> Dict[str, Any]:
        """Get user coins"""
        try:
            result = self.client.table('users')\
                .select('coin_balance, coins_expire_at, is_admin')\
                .eq('user_id', user_id)\
                .single()\
                .execute()

            if not result.data:
                return {
                    'balance': 0,
                    'expires_at': None,
                    'is_expired': False,
                    'is_admin': False
                }

            balance = result.data.get('coin_balance', 0)
            expire_at = result.data.get('coins_expire_at')
            is_admin = result.data.get('is_admin', False)

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
            if expire_at:
                expire_dt = datetime.fromisoformat(expire_at.replace('Z', '+00:00'))
                if datetime.now() > expire_dt.replace(tzinfo=None):
                    is_expired = True
                    balance = 0

            return {
                'balance': balance,
                'expires_at': expire_at,
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
            # Check if admin
            is_admin = await self.is_admin(user_id)
            if is_admin:
                # Admins have unlimited coins - just log
                return True

            # Get current balance
            coins_data = await self.get_user_coins(user_id)

            if coins_data['is_expired'] or coins_data['balance'] < amount:
                return False

            # Deduct coins
            new_balance = coins_data['balance'] - amount

            self.client.table('users')\
                .update({'coin_balance': new_balance, 'last_seen': datetime.now().isoformat()})\
                .eq('user_id', user_id)\
                .execute()

            return True

        except Exception as e:
            logger.error(f"Error deducting coins: {e}")
            return False

    async def get_command_cost(self, command: str) -> int:
        """Get coin cost for a command"""
        try:
            result = self.client.table('command_costs')\
                .select('cost')\
                .eq('command', command)\
                .single()\
                .execute()

            return result.data.get('cost', 0) if result.data else 0

        except Exception as e:
            logger.error(f"Error getting command cost: {e}")
            return 0

    async def get_coin_packages(self) -> List[Dict[str, Any]]:
        """Get available coin packages"""
        try:
            result = self.client.table('coin_packages')\
                .select('*')\
                .eq('is_active', True)\
                .order('price_usd')\
                .execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error getting packages: {e}")
            return []

    async def add_payment_history(self, user_id: int, session_id: str,
                                 amount_usd: float, coins_purchased: int,
                                 status: str = 'pending') -> bool:
        """Add payment history record"""
        try:
            data = {
                'user_id': user_id,
                'stripe_session_id': session_id,
                'amount_usd': amount_usd,
                'coins_purchased': coins_purchased,
                'status': status
            }

            self.client.table('payment_history').insert(data).execute()
            return True

        except Exception as e:
            logger.error(f"Error adding payment history: {e}")
            return False

    async def update_payment_status(self, session_id: str, status: str,
                                   payment_intent: str = None) -> bool:
        """Update payment status"""
        try:
            data = {
                'status': status,
                'stripe_payment_intent': payment_intent,
                'completed_at': datetime.now().isoformat()
            }

            self.client.table('payment_history')\
                .update(data)\
                .eq('stripe_session_id', session_id)\
                .execute()

            return True

        except Exception as e:
            logger.error(f"Error updating payment status: {e}")
            return False

    async def add_coins(self, user_id: int, amount: int,
                       transaction_type: str = 'admin_add',
                       description: str = None,
                       extend_expiry: bool = True) -> bool:
        """Add coins to user"""
        try:
            # Check if admin
            is_admin = await self.is_admin(user_id)
            if is_admin:
                return True  # Admins always have unlimited

            # Get current balance
            user = self.client.table('users')\
                .select('coin_balance')\
                .eq('user_id', user_id)\
                .single()\
                .execute()

            current_balance = user.data.get('coin_balance', 0) if user.data else 0
            new_balance = current_balance + amount

            # Update balance
            update_data = {'coin_balance': new_balance}

            if extend_expiry:
                expiry_days = int(os.getenv('COINS_EXPIRY_DAYS', '30'))
                new_expiry = (datetime.now() + timedelta(days=expiry_days)).isoformat()
                update_data['coins_expire_at'] = new_expiry

            result = self.client.table('users')\
                .update(update_data)\
                .eq('user_id', user_id)\
                .execute()

            # Check if update was successful
            if result.data:
                logger.info(f"Successfully added {amount} coins to user {user_id}. New balance: {new_balance}")
                return True
            else:
                logger.warning(f"Update returned no data for user {user_id}. May be RLS issue.")
                logger.warning(f"Result: {result}")
                return False

        except Exception as e:
            logger.error(f"Error adding coins: {e}", exc_info=True)
            return False

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users"""
        try:
            result = self.client.table('users')\
                .select('*')\
                .order('added_date', desc=True)\
                .execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []

    async def get_bot_statistics(self) -> Dict[str, Any]:
        """Get overall bot statistics"""
        try:
            # Get user counts
            all_users = self.client.table('users').select('user_id', count='exact').execute()
            active_users = self.client.table('users')\
                .select('user_id', count='exact')\
                .eq('is_active', True)\
                .execute()

            return {
                'total_users': all_users.count if hasattr(all_users, 'count') else 0,
                'active_users': active_users.count if hasattr(active_users, 'count') else 0,
                'commands_24h': 0,  # Would need usage_logs query
                'top_commands': []
            }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'commands_24h': 0,
                'top_commands': []
            }
