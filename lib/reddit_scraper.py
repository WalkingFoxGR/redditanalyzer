"""
Reddit Scraper using PRAW for Vercel serverless functions
Handles all Reddit data collection and analysis
"""

import praw
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import Counter
import statistics

logger = logging.getLogger(__name__)


class RedditScraper:
    """Reddit scraper using PRAW"""

    def __init__(self):
        """Initialize Reddit client"""
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT', 'RedditAnalyzerBot/1.0')
        )
        logger.info("Reddit client initialized")

    async def analyze_subreddit(self, subreddit_name: str, days: int = 7) -> Dict[str, Any]:
        """Analyze a subreddit's performance"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            # Get subreddit info
            subscribers = subreddit.subscribers

            # Collect posts (reduced to 100 for speed on Vercel)
            posts = []
            cutoff_time = datetime.now() - timedelta(days=days)

            for post in subreddit.hot(limit=100):
                post_time = datetime.fromtimestamp(post.created_utc)
                if post_time < cutoff_time:
                    continue

                posts.append({
                    'title': post.title,
                    'score': post.score,
                    'comments': post.num_comments,
                    'author': str(post.author) if post.author else '[deleted]',
                    'created': post.created_utc,
                    'flair': post.link_flair_text or 'No Flair',
                    'url': post.url
                })

            if not posts:
                return {
                    'success': False,
                    'error': f'No posts found in the last {days} days'
                }

            # Calculate metrics
            scores = [p['score'] for p in posts]
            comments = [p['comments'] for p in posts]

            avg_score = statistics.mean(scores)
            median_score = statistics.median(scores)
            avg_comments = statistics.mean(comments)
            posts_per_day = len(posts) / days

            # Calculate effectiveness score
            engagement_score = min(100, (median_score / 100) * 100)
            frequency_score = min(100, (posts_per_day / 10) * 100)
            consistency_score = min(100, (len([s for s in scores if s >= median_score * 0.5]) / len(scores)) * 100)

            effectiveness_score = int((engagement_score + frequency_score + consistency_score) / 3)

            # Get top post
            top_post = max(posts, key=lambda x: x['score'])

            # Analyze posting times
            hours = [datetime.fromtimestamp(p['created']).hour for p in posts]
            hour_scores = {}
            for p in posts:
                hour = datetime.fromtimestamp(p['created']).hour
                if hour not in hour_scores:
                    hour_scores[hour] = []
                hour_scores[hour].append(p['score'])

            best_hours = sorted(
                [{'hour': h, 'avg_score': statistics.mean(scores)} for h, scores in hour_scores.items()],
                key=lambda x: x['avg_score'],
                reverse=True
            )

            return {
                'success': True,
                'subreddit': subreddit_name,
                'subscribers': subscribers,
                'effectiveness_score': effectiveness_score,
                'avg_score_per_post': round(avg_score, 1),
                'median_score_per_post': round(median_score, 1),
                'avg_comments_per_post': round(avg_comments, 1),
                'avg_posts_per_day': round(posts_per_day, 1),
                'posts_analyzed_for_scoring': len(posts),
                'days_analyzed': days,
                'top_post': {
                    'title': top_post['title'],
                    'score': top_post['score'],
                    'comments': top_post['comments'],
                    'author': top_post['author'],
                    'flair': top_post['flair']
                },
                'posting_times': {
                    'best_hours': best_hours[:3]
                },
                'effectiveness_breakdown': {
                    'engagement_score': int(engagement_score),
                    'frequency_score': int(frequency_score),
                    'consistency_score': int(consistency_score)
                },
                'consistency_analysis': {
                    'good_posts_ratio': round((len([s for s in scores if s >= 50]) / len(scores)) * 100, 1),
                    'great_posts_ratio': round((len([s for s in scores if s >= 100]) / len(scores)) * 100, 1),
                    'distribution': 'varied'
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing subreddit {subreddit_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def search_subreddits(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Search for subreddits"""
        try:
            subreddits = []

            for subreddit in self.reddit.subreddits.search(query, limit=limit):
                subreddits.append({
                    'display_name': subreddit.display_name,
                    'subscribers': subreddit.subscribers,
                    'public_description': subreddit.public_description,
                    'over18': subreddit.over18
                })

            # Sort by subscribers
            subreddits.sort(key=lambda x: x['subscribers'], reverse=True)

            return {
                'success': True,
                'results': subreddits,
                'count': len(subreddits)
            }

        except Exception as e:
            logger.error(f"Error searching subreddits: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def get_rules(self, subreddit_name: str) -> Dict[str, Any]:
        """Get subreddit rules"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            rules = []
            for rule in subreddit.rules:
                rules.append({
                    'title': rule.short_name,
                    'description': rule.description
                })

            return {
                'success': True,
                'subreddit': subreddit_name,
                'rules': rules,
                'submission_text': subreddit.submit_text,
                'subscribers': subreddit.subscribers
            }

        except Exception as e:
            logger.error(f"Error getting rules for {subreddit_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def analyze_requirements(self, subreddit_name: str) -> Dict[str, Any]:
        """Analyze karma and account age requirements"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            # Analyze recent posts to estimate requirements
            successful_authors = []

            for post in subreddit.new(limit=50):
                if post.author:
                    successful_authors.append({
                        'post_karma': post.author.link_karma,
                        'comment_karma': post.author.comment_karma,
                        'account_age': (datetime.now() - datetime.fromtimestamp(post.author.created_utc)).days
                    })

            if not successful_authors:
                return {
                    'success': False,
                    'error': 'Could not analyze requirements'
                }

            # Calculate minimums (10th percentile)
            post_karmas = sorted([a['post_karma'] for a in successful_authors])
            comment_karmas = sorted([a['comment_karma'] for a in successful_authors])
            ages = sorted([a['account_age'] for a in successful_authors])

            percentile_10 = int(len(successful_authors) * 0.1)

            return {
                'success': True,
                'subreddit': subreddit_name,
                'karma_requirements': {
                    'post_karma_min': post_karmas[percentile_10] if post_karmas else 0,
                    'comment_karma_min': comment_karmas[percentile_10] if comment_karmas else 0,
                    'account_age_days': ages[percentile_10] if ages else 0,
                    'confidence': 'estimated',
                    'requires_verification': False
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing requirements: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def analyze_flairs(self, subreddit_name: str) -> Dict[str, Any]:
        """Analyze flair performance"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            flair_data = {}

            for post in subreddit.hot(limit=200):
                flair = post.link_flair_text or 'No Flair'

                if flair not in flair_data:
                    flair_data[flair] = {
                        'scores': [],
                        'comments': []
                    }

                flair_data[flair]['scores'].append(post.score)
                flair_data[flair]['comments'].append(post.num_comments)

            # Calculate averages
            flair_analysis = []
            for flair, data in flair_data.items():
                flair_analysis.append({
                    'flair': flair,
                    'post_count': len(data['scores']),
                    'avg_score': round(statistics.mean(data['scores']), 1),
                    'avg_comments': round(statistics.mean(data['comments']), 1)
                })

            # Sort by avg score
            flair_analysis.sort(key=lambda x: x['avg_score'], reverse=True)

            return {
                'success': True,
                'subreddit': subreddit_name,
                'flair_analysis': flair_analysis
            }

        except Exception as e:
            logger.error(f"Error analyzing flairs: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def scrape_posts(self, subreddit_name: str, limit: int, sort: str, time_filter: str) -> Dict[str, Any]:
        """Scrape posts from subreddit"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            posts = []

            if sort == 'hot':
                post_list = subreddit.hot(limit=limit)
            elif sort == 'top':
                post_list = subreddit.top(time_filter=time_filter, limit=limit)
            elif sort == 'new':
                post_list = subreddit.new(limit=limit)
            else:
                post_list = subreddit.hot(limit=limit)

            for post in post_list:
                posts.append({
                    'title': post.title,
                    'score': post.score,
                    'num_comments': post.num_comments,
                    'author': str(post.author) if post.author else '[deleted]',
                    'url': post.url,
                    'created_utc': post.created_utc,
                    'flair': post.link_flair_text
                })

            return {
                'success': True,
                'subreddit': subreddit_name,
                'posts': posts,
                'count': len(posts)
            }

        except Exception as e:
            logger.error(f"Error scraping posts: {e}")
            return {
                'success': False,
                'error': str(e)
            }
