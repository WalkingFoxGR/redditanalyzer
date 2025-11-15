"""
Reddit API module for Reddit Analyzer Bot
Handles all interactions with the Reddit Analyzer API
"""

import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class RedditAPI:
    def __init__(self, base_url: str):
        # Ensure URL has protocol
        if not base_url.startswith(('http://', 'https://')):
            base_url = f'https://{base_url}'
        self.base_url = base_url.rstrip('/')
        self._session = None
        self._lock = asyncio.Lock()
        
    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if not self._session:
            async with self._lock:
                if not self._session:
                    # Create session with better timeout and connector settings
                    timeout = aiohttp.ClientTimeout(total=300, connect=30, sock_read=30)
                    connector = aiohttp.TCPConnector(
                        limit=100,  # Increased for concurrent requests
                        limit_per_host=30,
                        force_close=True
                    )
                    self._session = aiohttp.ClientSession(
                        timeout=timeout, 
                        connector=connector
                    )
        return self._session
            
    async def _make_request(self, method: str, endpoint: str, 
                          json_data: Optional[Dict] = None,
                          timeout: int = 180) -> Dict[str, Any]:
        """Make HTTP request to API with improved error handling"""
        session = await self._ensure_session()
        
        url = f"{self.base_url}{endpoint}"
        
        # Retry logic for resilience
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                async with session.request(
                    method,
                    url,
                    json=json_data,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    data = await response.json()
                    
                    if response.status != 200:
                        logger.error(f"API error: {response.status} - {data}")
                        
                        # Handle specific error codes
                        if response.status == 400 and "error" in data:
                            # Don't retry for client errors
                            return data
                        elif response.status >= 500:
                            # Retry for server errors
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                        
                        return {"error": data.get("error", "Unknown API error")}
                    
                    return data
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout error for {url} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return {"error": "Request timeout. The subreddit might be very large or the API is busy. Please try again."}
                
            except aiohttp.ClientError as e:
                logger.error(f"Client error for {url}: {e} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return {"error": f"Connection error: {str(e)}"}
                
            except Exception as e:
                logger.error(f"Unexpected error for {url}: {e}")
                return {"error": f"Unexpected error: {str(e)}"}
                
        return {"error": "Max retries exceeded. Please try again later."}
            
    async def analyze_subreddit(self, subreddit: str, days: int = 7) -> Dict[str, Any]:
        """Analyze a single subreddit"""
        return await self._make_request(
            "POST",
            "/reddit/analyze",
            {"subreddit": subreddit, "days": days},
            timeout=400
        )
        
    async def search_subreddits(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Search for subreddits"""
        return await self._make_request(
            "POST",
            "/reddit/search",
            {"query": query, "limit": limit}
        )

    async def search_and_analyze(self, query: str, limit: int = 100,
                                days: int = 7) -> Dict[str, Any]:
        """Search and analyze subreddits (niche)"""
        return await self._make_request(
            "POST",
            "/reddit/search-and-analyze",
            {"query": query, "limit": limit, "days": days}
        )

    async def analyze_multiple(self, subreddits: str, days: int = 7) -> Dict[str, Any]:
        """Analyze multiple subreddits for comparison"""
        return await self._make_request(
            "POST",
            "/reddit/analyze-multiple",
            {"subreddits": subreddits, "days": days},
            timeout=400
        )

    async def scrape_posts(self, subreddit: str, limit: int,
                          sort: str, time_filter: str) -> Dict[str, Any]:
        """Scrape posts from a subreddit"""
        return await self._make_request(
            "POST",
            "/reddit/scrape",
            {
                "subreddit": subreddit,
                "limit": limit,
                "sort": sort,
                "time_filter": time_filter
            }
        )

    async def get_rules(self, subreddit: str) -> Dict[str, Any]:
        """Get subreddit rules"""
        return await self._make_request(
            "POST",
            "/reddit/rules",
            {"subreddit": subreddit}
        )

    async def analyze_flairs(self, subreddit: str) -> Dict[str, Any]:
        """Analyze flair performance"""
        return await self._make_request(
            "POST",
            "/reddit/flairs",
            {"subreddit": subreddit}
        )

    async def analyze_requirements(self, subreddit: str,
                                  post_limit: int = 150) -> Dict[str, Any]:
        """Analyze posting requirements"""
        return await self._make_request(
            "POST",
            "/reddit/requirements",
            {"subreddit": subreddit, "post_limit": post_limit},
            timeout=400
        )
        
    async def analyze_user(self, username: str, days: int = 30, 
                          limit: int = 100) -> Dict[str, Any]:
        """Analyze a Reddit user's posting activity"""
        return await self._make_request(
            "POST",
            "/analyze-user",
            {"username": username, "days": days, "limit": limit}
        )
        
    async def close(self):
        """Close the aiohttp session"""
        if self._session:
            await self._session.close()
            self._session = None