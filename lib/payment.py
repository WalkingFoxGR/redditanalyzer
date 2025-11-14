"""
Payment module for Reddit Analyzer Bot
Handles Stripe integration and coin purchases
"""

import stripe
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import sqlite3

logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self, stripe_secret_key: str, stripe_webhook_secret: str, database):
        """Initialize payment processor with Stripe"""
        self.stripe_secret_key = stripe_secret_key
        self.stripe_webhook_secret = stripe_webhook_secret
        self.db = database
        
        # Configure Stripe
        stripe.api_key = stripe_secret_key
        
        # Coin packages configuration
        self.packages = {
            'starter': {
                'name': 'Starter Pack',
                'coins': 20,
                'bonus': 0,
                'price': 9.99,
                'description': '20 coins - Perfect for trying out'
            },
            'basic': {
                'name': 'Basic Pack',
                'coins': 50,
                'bonus': 5,
                'price': 19.99,
                'description': '50 coins + 5 bonus coins'
            },
            'pro': {
                'name': 'Pro Pack',
                'coins': 100,
                'bonus': 10,
                'price': 34.99,
                'description': '100 coins + 10 bonus coins'
            },
            'premium': {
                'name': 'Premium Pack',
                'coins': 250,
                'bonus': 15,
                'price': 79.99,
                'description': '250 coins + 15 bonus coins'
            },
            'ultimate': {
                'name': 'Ultimate Pack',
                'coins': 500,
                'bonus': 20,
                'price': 139.99,
                'description': '500 coins + 20 bonus coins - Best value!'
            }
        }
    
    async def create_checkout_session(self, user_id: int, package_key: str, 
                                    success_url: str, cancel_url: str) -> Optional[str]:
        try:
            package = self.packages.get(package_key)
            if not package:
                return None
            
            total_coins = package['coins'] + package['bonus']
            
            # Create Stripe checkout session (this is synchronous, it's fine)
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': package['name'],
                            'description': package['description'],
                            'metadata': {
                                'type': 'coins',
                                'amount': str(total_coins)
                            }
                        },
                        'unit_amount': int(package['price'] * 100),  # Stripe uses cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=str(user_id),
                metadata={
                    'user_id': str(user_id),
                    'package': package_key,
                    'coins': str(package['coins']),
                    'bonus': str(package['bonus']),
                    'total_coins': str(total_coins)
                }
            )
            
            await self.db.add_payment_history(
                user_id, session.id, package['price'], total_coins, 'pending'
            )
            
            return session.url
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            return None
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.stripe_webhook_secret
            )
            
            # Handle the checkout.session.completed event
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                
                # Get user and package info from metadata
                user_id = int(session['metadata']['user_id'])
                total_coins = int(session['metadata']['total_coins'])
                package_key = session['metadata']['package']
                
                # Update payment status
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE payment_history 
                        SET status = 'completed',
                            completed_at = CURRENT_TIMESTAMP,
                            stripe_payment_intent = ?
                        WHERE stripe_session_id = ?
                    """, (session.get('payment_intent'), session['id']))
                    conn.commit()
                
                # Add coins to user with 30-day extension
                success = await self.db.add_coins(
                    user_id=user_id,
                    amount=total_coins,
                    transaction_type='purchase',
                    description=f"Purchased {self.packages[package_key]['name']}",
                    extend_expiry=True
                )
                
                if success:
                    # Update total purchased
                    with self.db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE users 
                            SET total_coins_purchased = total_coins_purchased + ?
                            WHERE user_id = ?
                        """, (total_coins, user_id))
                        conn.commit()
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'coins_added': total_coins,
                    'package': package_key
                }
            
            # Handle failed payment
            elif event['type'] == 'checkout.session.expired' or event['type'] == 'payment_intent.payment_failed':
                session_id = event['data']['object'].get('id')
                
                # Update payment status
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE payment_history 
                        SET status = 'failed'
                        WHERE stripe_session_id = ?
                    """, (session_id,))
                    conn.commit()
                
                return {'success': False, 'reason': 'payment_failed'}
            
            return {'success': True, 'event': event['type']}
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return {'success': False, 'error': 'Invalid payload'}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_package_details(self, package_key: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific package"""
        return self.packages.get(package_key)
    
    def get_all_packages(self) -> Dict[str, Dict[str, Any]]:
        """Get all available packages"""
        return self.packages


class CoinManager:
    """Manages coin operations and command costs"""
    
    # Command costs configuration
    COMMAND_COSTS = {
        'analyze': 2,
        'requirements': 2,
        'compare': 5,
        'search': 1,
        'niche': 3,
        'scrape': 0,  # Free
        'rules': 1,
        'flairs': 1,
        'discover': 10,  # Admin only anyway
        'user': 2,  # For analyze_user command
    }
    
    # AI recreation costs based on post count
    AI_RECREATION_COSTS = {
        10: 2,
        20: 4,
        30: 6,
        40: 8,
        50: 10
    }
    
    @staticmethod
    def get_command_cost(command: str) -> int:
        """Get the cost for a specific command"""
        return CoinManager.COMMAND_COSTS.get(command, 0)
    
    @staticmethod
    def get_ai_recreation_cost(post_count: int) -> int:
        """Get the cost for AI recreation based on post count"""
        # Find the appropriate tier
        for count, cost in sorted(CoinManager.AI_RECREATION_COSTS.items()):
            if post_count <= count:
                return cost
        # If more than 50 posts, charge 10 + 2 for every additional 10 posts
        return 10 + ((post_count - 50) // 10) * 2
    
    @staticmethod
    def check_coins(required_coins: int, user_balance: int) -> bool:
        """Check if user has enough coins"""
        return user_balance >= required_coins
    
    @staticmethod
    def format_coin_display(coins: int) -> str:
        """Format coin display with emoji"""
        return f"🪙 {coins} coin{'s' if coins != 1 else ''}"