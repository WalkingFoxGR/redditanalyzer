"""
Button continuation system for Reddit Analyzer Bot
"""

from typing import Dict, List, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import logging

logger = logging.getLogger(__name__)

class ButtonContinuationManager:
    """Manages button continuations after analyze command"""
    
    def create_continuation_keyboard(self, subreddit: str, completed_actions: List[str] = None) -> InlineKeyboardMarkup:
        """Create keyboard with remaining actions"""
        if completed_actions is None:
            completed_actions = []
        
        buttons = []
        
        # Available actions
        actions = {
            'requirements': ('📋 Requirements', f'continue_req_{subreddit}'),
            'rules': ('📜 Rules', f'continue_rules_{subreddit}'),
            'flairs': ('🏷️ Flairs', f'continue_flairs_{subreddit}'),
            'compare': ('🆚 Compare Similar', f'continue_compare_{subreddit}'),
            'done': ('✅ Done', f'continue_done_{subreddit}')
        }
        
        # Add buttons for uncompleted actions
        for action_key, (label, callback_data) in actions.items():
            if action_key not in completed_actions:
                if action_key == 'done':
                    # Done button on separate row
                    buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])
                else:
                    # Other buttons, 2 per row
                    if len(buttons) == 0 or len(buttons[-1]) == 2:
                        buttons.append([])
                    if len(buttons[-1]) < 2:
                        buttons[-1].append(InlineKeyboardButton(label, callback_data=callback_data))
        
        return InlineKeyboardMarkup(buttons) if buttons else None
    
    def store_analyze_context(self, context, subreddit: str, analyze_data: Dict):
        """Store analyze data for button continuations"""
        if 'analyze_sessions' not in context.user_data:
            context.user_data['analyze_sessions'] = {}
        
        context.user_data['analyze_sessions'][subreddit] = {
            'data': analyze_data,
            'completed_actions': [],
            'timestamp': analyze_data.get('analyzed_at')
        }
    
    def get_analyze_context(self, context, subreddit: str) -> Dict:
        """Retrieve stored analyze data"""
        sessions = context.user_data.get('analyze_sessions', {})
        return sessions.get(subreddit, {})
    
    def mark_action_complete(self, context, subreddit: str, action: str):
        """Mark an action as completed"""
        if 'analyze_sessions' in context.user_data:
            if subreddit in context.user_data['analyze_sessions']:
                completed = context.user_data['analyze_sessions'][subreddit].get('completed_actions', [])
                if action not in completed:
                    completed.append(action)
                context.user_data['analyze_sessions'][subreddit]['completed_actions'] = completed