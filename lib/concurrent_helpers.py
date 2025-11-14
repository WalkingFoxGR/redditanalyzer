"""
Concurrent execution helpers for Reddit Analyzer Bot
Place this file in the same directory as reddit_bot.py
"""

import asyncio
import time
import uuid
from functools import wraps
from typing import Dict, Any, Callable
from collections import defaultdict

class EnhancedRateLimiter:
    def __init__(self):
        self.user_limits: Dict[int, Dict] = defaultdict(lambda: {
            'requests': [],
            'last_request': 0,
            'burst_used': 0
        })
    
    async def can_proceed(self, user_id: int, requests_per_second: float = 1.0,
                         burst_allowance: int = 3) -> tuple[bool, float]:
        """Check if request can proceed"""
        current_time = time.time()
        user_data = self.user_limits[user_id]
        
        # Clean old requests
        user_data['requests'] = [
            req for req in user_data['requests'] 
            if current_time - req < 60
        ]
        
        time_since_last = current_time - user_data['last_request']
        min_interval = 1.0 / requests_per_second
        
        if time_since_last < min_interval:
            if user_data['burst_used'] >= burst_allowance:
                wait_time = min_interval - time_since_last
                return False, wait_time
            else:
                user_data['burst_used'] += 1
        else:
            user_data['burst_used'] = max(0, user_data['burst_used'] - 1)
        
        return True, 0.0
    
    async def record_request(self, user_id: int):
        """Record successful request"""
        current_time = time.time()
        self.user_limits[user_id]['requests'].append(current_time)
        self.user_limits[user_id]['last_request'] = current_time

# Global rate limiter instance
rate_limiter = EnhancedRateLimiter()

def enhanced_rate_limit(requests_per_second: float = 1.0, burst_allowance: int = 3):
    """Enhanced rate limiting decorator"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context):
            user_id = update.effective_user.id
            
            can_proceed, wait_time = await rate_limiter.can_proceed(
                user_id, requests_per_second, burst_allowance
            )
            
            if not can_proceed:
                await update.message.reply_text(
                    f"⏳ Please wait {wait_time:.1f}s before next request"
                )
                return
            
            await rate_limiter.record_request(user_id)
            return await func(update, context)
        return wrapper
    return decorator