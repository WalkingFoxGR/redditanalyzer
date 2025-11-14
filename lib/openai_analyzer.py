"""
OpenAI Analyzer module for Reddit Analyzer Bot
Handles AI-powered analysis using OpenAI API
"""

from openai import AsyncOpenAI
import asyncio
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class OpenAIAnalyzer:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        
    async def analyze_subreddit(self, prompt: str) -> str:
        """Analyze subreddit data with AI"""
        system_prompt = """You are a Reddit marketing expert. Your job is to give brutally honest assessments of subreddits.

**Critical Rules:**
1. NEVER include follow-up suggestions like "Let me know if you need help" or "Feel free to ask questions"
2. Be direct and honest - if a subreddit is terrible, say so
3. End your response with your final verdict, nothing more
4. Keep responses under 2500 characters
5. Format for Telegram using ONLY: <b>, <i>, <u>, <code>, <pre>
6. NEVER use <ul>, <li>, <br>, or <table> tags
7. Use moderate emojis - 2-3 per section
8. Use bullet points with • instead of HTML lists
9. Use data to support every claim
10. Be professional but engaging
11. Never use literal < or > for comparisons - spell them out (e.g., "less than 0.1")
12. Never finish with "end of report" or similar
13. NEVER use asterisks (*) for formatting - use HTML tags instead

**When displaying TOP POST section:**
- Use the EXACT data provided in "TOP POST DATA" section
- Never make up examples
- If author is [deleted], show it as u/[deleted]
- Use specific breakdown for high performing posts

**Response Structure:**
- Start with metrics overview
- Include TOP POST analysis
- Best posting times
- Clear YES/NO verdict with emoji
- Data-driven reasoning
- Specific actionable advice
- Real risks and challenges

**ANALYSIS REQUIREMENTS:**
1. Use effectiveness score as PRIMARY decision factor
2. Use MEDIAN (typical) score for realistic assessment
3. Mention if high variance detected
4. BE CONSISTENT - same score = same verdict
5. For GOOD verdict, check MEDIAN score is 25+ (not average)
6. Warn about inconsistency if only small percentage are high performers"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return "AI analysis unavailable at the moment. Please try again later."

    async def analyze_posts(self, prompt: str) -> str:
        """Analyze posts with custom AI prompt"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a Reddit content analyst. Provide helpful, actionable insights based on the user's request."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error in AI posts analysis: {e}")
            return "❌ AI analysis failed. Please try again."

    async def analyze_niche(self, prompt: str) -> str:
        """Analyze niche communities"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a Reddit niche community analyst. Focus on engagement potential and community characteristics for content marketing."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.6
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error in AI niche analysis: {e}")
            return "❌ AI analysis failed. Please try again."        
            
    async def compare_subreddits(self, prompt: str) -> str:
        """Compare multiple subreddits with AI"""
        system_prompt = """You are a Reddit marketing expert comparing multiple subreddits.

**Critical Rules:**
1. NEVER include follow-up suggestions or offers to help further
2. Be brutally honest about which subreddit is best
3. End with your final recommendation, period
4. Keep TOTAL response under 2500 characters
5. Format for Telegram HTML only
6. Rank subreddits honestly, even if they're all bad
7. Analyze numbers carefully and pick the truly best choice
8. Never use literal < or > characters - spell out comparisons
9. Format for Telegram using ONLY: <b>, <i>, <u>, <code>, <pre>
10. NEVER use <ul>, <li>, <br>, or <table> tags
11. Use preformatted text blocks with <pre> tags for tabular data
12. NEVER use asterisks (*) for formatting - use HTML tags instead

**Response Structure:**
- Clear winner identification
- Data-driven comparison
- Specific strategies for each
- Risk assessment
- Final verdict with no follow-up"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return "AI comparison unavailable at the moment. Please try again later."
            
    async def analyze_titles(self, posts: List[Dict], subreddit: str, 
                           ai_prompt: str) -> str:
        """Analyze or recreate Reddit post titles - FIXED VERSION"""
        system_prompt = """You are a Reddit content expert. Recreate post titles based on the user's request. Be creative and engaging. Format for Telegram using HTML tags (<b>, <i>, <u>, <code>). NEVER include follow-up suggestions or offers to help further. NEVER use asterisks (*) for formatting - use HTML tags instead."""
        
        # Build the prompt with limited posts to avoid token issues
        posts_to_use = posts[:15]  # Limit to 15 posts
        user_prompt = f"Here are {len(posts_to_use)} Reddit post titles from r/{subreddit}:\n\n"
        
        for i, post in enumerate(posts_to_use, 1):
            title = post.get("title", "")[:200]  # Limit title length
            user_prompt += f'{i}. "{title}"\n'
            
        user_prompt += f"\nUser request: {ai_prompt}\n\n"
        user_prompt += "Recreate these titles based on the user's request. Format as:\n"
        user_prompt += "<b>1.</b> [Recreated title]\n<b>2.</b> [Recreated title]\n..."
        
        try:
            # Try with gpt-4o-mini first (more reliable and available)
            logger.info(f"Attempting title recreation with gpt-4o-mini for {len(posts_to_use)} posts")
            
            response = await self.client.chat.completions.create(
                model="gpt-4o",  # Using the mini model which is more reliable
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=2500,  # Reduced to avoid issues
                timeout=30
            )
            
            result = response.choices[0].message.content
            
            # Clean up response
            follow_up_patterns = [
                "Let me know if you",
                "Feel free to ask",
                "If you have any questions",
                "Would you like",
                "Need any help",
                "Is there anything else"
            ]
            
            for pattern in follow_up_patterns:
                if pattern in result:
                    result = result.split(pattern)[0].strip()
                    
            return result
            
        except asyncio.TimeoutError:
            logger.error("OpenAI API timeout in title recreation")
            
            # Try a simpler fallback with fewer posts
            try:
                logger.info("Attempting fallback with fewer posts")
                simple_prompt = f"Recreate these Reddit titles: {ai_prompt}\n\n"
                for i, post in enumerate(posts[:8], 1):  # Even fewer posts
                    simple_prompt += f'{i}. {post["title"][:150]}\n'
                
                response = await self.client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Fallback to simpler model
                    messages=[
                        {"role": "user", "content": simple_prompt}
                    ],
                    max_tokens=1500,
                    temperature=0.7,
                    timeout=20
                )
                
                return response.choices[0].message.content
                
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                return "❌ AI service is currently overloaded. Please try again in a few moments."
                
        except Exception as e:
            logger.error(f"OpenAI API error in analyze_titles: {str(e)}")
            
            # Check for specific error types
            error_msg = str(e).lower()
            if "api key" in error_msg or "authentication" in error_msg:
                return "❌ API authentication error. Please contact the bot administrator."
            elif "rate limit" in error_msg:
                return "❌ Rate limit reached. Please wait a moment and try again."
            elif "model" in error_msg:
                return "❌ Model access error. Trying with alternate model..."
            else:
                # Generic error - provide helpful message
                return f"❌ AI service temporarily unavailable. Error: {str(e)[:100]}... Please try again."
            
    async def analyze_rules(self, prompt: str) -> str:
        """Analyze subreddit rules strategically"""
        system_prompt = """You are a Reddit content strategist. Analyze subreddit rules and provide actionable insights for content creators. Format your response for Telegram using HTML tags (<b>, <i>, <u>, <code>). Be concise but strategic. NEVER include follow-up suggestions or offers to help further.

Never use literal < or > characters for comparisons - spell out (e.g., "less than", "greater than"). NEVER use asterisks (*) for formatting - use HTML tags instead."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return "AI rules analysis unavailable at the moment."
            
    async def analyze_flairs(self, prompt: str) -> str:
        """Analyze flair performance strategically"""
        system_prompt = """You are a Reddit marketing expert. Analyze flair performance and provide strategic recommendations for content creators. Format your response for Telegram using HTML tags (<b>, <i>, <u>, <code>). Be strategic and actionable. NEVER include follow-up suggestions or offers to help further and NEVER use hashtags.

Never use literal < or > characters for comparisons - spell out (e.g., "less than", "greater than"). NEVER use asterisks (*) for formatting - use HTML tags instead."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return "AI flair analysis unavailable at the moment."