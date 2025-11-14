"""
Utilities module for Reddit Analyzer Bot
Helper functions and utilities
"""

import html
from typing import Union


def format_number(num: Union[int, float]) -> str:
    """Format number with thousands separator"""
    if isinstance(num, (int, float)):
        return f"{num:,}"
    return str(num)


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram"""
    if not text:
        return ""
    return html.escape(str(text))


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_time_12h(hour: int) -> str:
    """Convert 24-hour time to 12-hour format"""
    if hour == 0:
        return "12 AM"
    elif hour < 12:
        return f"{hour} AM"
    elif hour == 12:
        return "12 PM"
    else:
        return f"{hour - 12} PM"


def calculate_difficulty(post_karma: int, comment_karma: int, 
                        account_age: int, requires_verification: bool,
                        is_optional: bool = False) -> tuple[str, str]:
    """Calculate posting difficulty based on requirements"""
    # Don't count optional verification as "very hard"
    has_hard_verification = requires_verification and not is_optional
    
    if post_karma >= 1000 or comment_karma >= 1000 or account_age >= 365 or has_hard_verification:
        return "Very Hard", "🔴"
    elif post_karma >= 100 or comment_karma >= 100 or account_age >= 90:
        return "Hard", "🟠"
    elif post_karma >= 10 or comment_karma >= 10 or account_age >= 30:
        return "Medium", "🟡"
    else:
        return "Easy", "🟢"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a float as percentage"""
    return f"{value:.{decimals}f}%"


def sanitize_subreddit_name(name: str) -> str:
    """Sanitize subreddit name (remove r/ prefix if present)"""
    if name.startswith("r/"):
        return name[2:]
    return name