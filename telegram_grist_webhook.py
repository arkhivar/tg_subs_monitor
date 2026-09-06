"""
Telegram webhook handler for Grist database integration.

This module processes Telegram webhook events and records subscriber activity in Grist.
"""

import os
import json
import logging
from datetime import datetime
from flask import request, jsonify

from grist_simple_client import GristSimpleClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Grist client
db_client = GristSimpleClient()
db_client.init_table()

def handle_telegram_update(update_data):
    """
    Process a Telegram update and record subscriber activity in Grist.
    
    Args:
        update_data: Dict containing the Telegram update
        
    Returns:
        dict: Response with processing status
    """
    try:
        logger.info(f"Processing Telegram update: {json.dumps(update_data)}")
        
        # Check for new chat members (join event)
        if 'message' in update_data and 'new_chat_members' in update_data['message']:
            chat = update_data['message'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            # Only process updates from channels, supergroups, or groups
            logger.info(f"Received new chat members event for chat {chat_id} of type {chat_type}")
            
            if chat_type in ['channel', 'supergroup', 'group']:
                for member in update_data['message']['new_chat_members']:
                    user_id = str(member.get('id'))
                    username = member.get('username', '')
                    logger.info(f"Adding new subscriber: user_id={user_id}, username={username}")
                    
                    user_data = {
                        'user_id': user_id,
                        'username': username,
                        'first_name': member.get('first_name', ''),
                        'last_name': member.get('last_name', ''),
                        'join_date': datetime.now().isoformat(),
                        'current_status': 'active'
                    }
                    result = db_client.add_subscriber(user_data)
                    logger.info(f"Added new member {user_id}, result: {result}")
            
            return {'status': 'success', 'event': 'new_members_processed'}
        
        # Check for left chat member (leave event)
        elif 'message' in update_data and 'left_chat_member' in update_data['message']:
            chat = update_data['message'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            # Only process updates from channels, supergroups, or groups
            logger.info(f"Received left chat member event for chat {chat_id} of type {chat_type}")
            
            if chat_type in ['channel', 'supergroup', 'group']:
                member = update_data['message']['left_chat_member']
                user_id = str(member.get('id'))
                username = member.get('username', '')
                logger.info(f"Updating subscriber leave: user_id={user_id}, username={username}")
                
                result = db_client.update_subscriber_leave(user_id)
                logger.info(f"Processed leave event for {user_id}, result: {result}")
            
            return {'status': 'success', 'event': 'left_member_processed'}
        
        # Check for my_chat_member updates (join/leave events from bot perspective)
        elif 'my_chat_member' in update_data:
            chat = update_data['my_chat_member'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            new_status = update_data['my_chat_member'].get('new_chat_member', {}).get('status')
            old_status = update_data['my_chat_member'].get('old_chat_member', {}).get('status')
            
            logger.info(f"Received my_chat_member update for chat {chat_id}, status change from {old_status} to {new_status}")
            
            # This usually means a member was added/removed by admin rather than themselves
            if new_status in ['member', 'administrator'] and old_status in ['left', 'kicked']:
                # Someone added the user to the chat
                user = update_data['my_chat_member'].get('from', {})
                user_id = str(user.get('id'))
                username = user.get('username', '')
                
                logger.info(f"User was added to chat: user_id={user_id}, username={username}")
                
                user_data = {
                    'user_id': user_id,
                    'username': username,
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'join_date': datetime.now().isoformat(),
                    'current_status': 'active'
                }
                result = db_client.add_subscriber(user_data)
                logger.info(f"Add subscriber result: {result}")
                
            elif new_status in ['left', 'kicked'] and old_status in ['member', 'administrator']:
                # Someone removed the user from the chat
                user = update_data['my_chat_member'].get('from', {})
                user_id = str(user.get('id'))
                username = user.get('username', '')
                
                logger.info(f"User was removed from chat: user_id={user_id}, username={username}")
                
                result = db_client.update_subscriber_leave(user_id)
                logger.info(f"Update leave result: {result}")
            
            return {'status': 'success', 'event': 'my_chat_member_processed'}
        
        # Check for chat_member updates (status changes for regular members)
        elif 'chat_member' in update_data:
            chat = update_data['chat_member'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            new_status = update_data['chat_member'].get('new_chat_member', {}).get('status')
            old_status = update_data['chat_member'].get('old_chat_member', {}).get('status')
            
            logger.info(f"Received chat_member update for chat {chat_id}, status change from {old_status} to {new_status}")
            
            if new_status in ['member', 'administrator'] and old_status in ['left', 'kicked']:
                # Member joined
                member = update_data['chat_member'].get('new_chat_member', {})
                user = member.get('user', {})
                user_id = str(user.get('id'))
                username = user.get('username', '')
                
                logger.info(f"Member joined: user_id={user_id}, username={username}")
                
                user_data = {
                    'user_id': user_id,
                    'username': username,
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'join_date': datetime.now().isoformat(),
                    'current_status': 'active'
                }
                result = db_client.add_subscriber(user_data)
                logger.info(f"Add subscriber result: {result}")
                
            elif new_status in ['left', 'kicked'] and old_status in ['member', 'administrator']:
                # Member left
                member = update_data['chat_member'].get('old_chat_member', {})
                user = member.get('user', {})
                user_id = str(user.get('id'))
                username = user.get('username', '')
                
                logger.info(f"Member left: user_id={user_id}, username={username}")
                
                result = db_client.update_subscriber_leave(user_id)
                logger.info(f"Update leave result: {result}")
            
            return {'status': 'success', 'event': 'chat_member_processed'}
        
        # Check for message reactions
        elif 'message_reaction' in update_data:
            chat = update_data['message_reaction'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            
            logger.info(f"Received message_reaction for chat {chat_id} of type {chat_type}")
            
            if chat_type in ['channel', 'supergroup', 'group']:
                user = update_data['message_reaction'].get('user', {})
                if user:
                    user_id = str(user.get('id'))
                    username = user.get('username', '')
                    
                    logger.info(f"Updating reaction count: user_id={user_id}, username={username}")
                    
                    result = db_client.update_reaction_count(user_id)
                    logger.info(f"Updated reaction count for {user_id}, result: {result}")
            
            return {'status': 'success', 'event': 'reaction_processed'}
        
        # Check for message_reaction_count
        elif 'message_reaction_count' in update_data:
            chat = update_data['message_reaction_count'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            
            logger.info(f"Received message_reaction_count for chat {chat_id} of type {chat_type}")
            logger.info("Cannot process message_reaction_count as it doesn't include user information")
            
            return {'status': 'success', 'event': 'reaction_count_noted'}
        
        # Unknown update type
        else:
            logger.info(f"No relevant events found in update")
            return {'status': 'success', 'event': 'no_relevant_events'}
        
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}")
        return {'status': 'error', 'message': str(e)}

# Flask route handler
def webhook_handler():
    """Handle webhook requests from Telegram."""
    if request.method == 'POST':
        update = request.get_json()
        result = handle_telegram_update(update)
        return jsonify(result)
    else:
        return jsonify({'status': 'error', 'message': 'Only POST requests are allowed'})

# Command to manually add a user
def add_user_command(user_id, username=None, first_name=None, last_name=None):
    """Add a user manually via command."""
    user_data = {
        'user_id': str(user_id),
        'username': username or '',
        'first_name': first_name or '',
        'last_name': last_name or '',
        'join_date': datetime.now().isoformat(),
        'current_status': 'active'
    }
    
    success = db_client.add_subscriber(user_data)
    
    if success:
        return {'status': 'success', 'message': f"User {user_id} added successfully"}
    else:
        return {'status': 'error', 'message': f"Failed to add user {user_id}"}

# Function to sync channel members
def sync_channel_members(bot, chat_id):
    """
    Sync channel members by getting admin list.
    
    Args:
        bot: Telegram bot instance
        chat_id: Channel or group ID to sync
        
    Returns:
        dict: Status of the sync operation
    """
    try:
        admins = bot.get_chat_administrators(chat_id)
        
        added_count = 0
        updated_count = 0
        
        for admin in admins:
            user = admin.user
            if user.is_bot:
                continue
                
            user_id = str(user.id)
            
            # Check if user already exists
            existing_user = db_client.get_subscriber(user_id)
            
            if existing_user:
                # Update as active if previously inactive
                if existing_user.get('current_status') != 'active':
                    db_client.update_subscriber_rejoin(user_id, existing_user.get('id'))
                    updated_count += 1
            else:
                # Add new subscriber
                user_data = {
                    'user_id': user_id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'join_date': datetime.now().isoformat(),
                    'current_status': 'active',
                    'is_admin': True
                }
                db_client.add_subscriber(user_data)
                added_count += 1
        
        return {
            'status': 'success',
            'admins_count': len(admins),
            'added_count': added_count,
            'updated_count': updated_count
        }
    except Exception as e:
        logger.error(f"Error syncing channel members: {e}")
        return {'status': 'error', 'message': str(e)}