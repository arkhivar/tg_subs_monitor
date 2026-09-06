"""
Telegram Bot Member Handlers

This module provides handlers for tracking Telegram chat member
join and leave events and stores the data in Grist.
"""
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated
from utils.logger import logger
from datetime import datetime

# Create a router for member handlers
router = Router()

async def setup_member_handlers(grist_client):
    """Set up member handlers with the provided storage."""
    
    @router.chat_member()
    async def handle_chat_member_update(update: ChatMemberUpdated):
        """Handle updates to chat members (join/leave)."""
        chat_id = update.chat.id
        chat_type = update.chat.type
        chat_title = getattr(update.chat, 'title', 'Private Chat')
        user = update.new_chat_member.user
        user_id = user.id
        
        # Compose user information
        user_info = {
            'user_id': str(user_id),
            'username': user.username or '',
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'is_admin': False  # Will be set based on status
        }
        
        # Determine if user joined or left
        old_status = update.old_chat_member.status
        new_status = update.new_chat_member.status
        
        logger.info(f"👥 MEMBER UPDATE: chat_id={chat_id}, user_id={user_id}")
        logger.info(f"📡 Chat type: {chat_type}, title: {chat_title}")
        logger.info(f"🔄 Status change: {old_status} → {new_status}")
        
        # Check if admin status changed
        is_admin_now = new_status in ["administrator", "creator"]
        was_admin_before = old_status in ["administrator", "creator"]
        
        # Special case: check if this is an admin status change
        if old_status not in ["left", "kicked", "banned"] and new_status not in ["left", "kicked", "banned"]:
            if is_admin_now != was_admin_before:
                # This is just an admin status change, update the record
                subscriber = grist_client.get_subscriber(user_id)
                if subscriber:
                    record_id = subscriber.get('id')
                    logger.info(f"🔰 Admin status changed for user {user_id}: {is_admin_now}")
                    
                    # Update admin status
                    update_data = {
                        'id': record_id,
                        'is_admin': is_admin_now
                    }
                    
                    try:
                        grist_client.api.update_records(grist_client.table_name, [update_data])
                        logger.info(f"✅ Updated admin status for user {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Error updating admin status: {e}")
                else:
                    # No existing record, create one
                    user_info['is_admin'] = is_admin_now
                    user_info['join_date'] = datetime.now().isoformat()
                    user_info['current_status'] = 'active'
                    user_info['reaction_counter'] = 0
                    
                    try:
                        grist_client.add_subscriber(user_info)
                        logger.info(f"✅ Created new subscriber with admin status: {is_admin_now}")
                    except Exception as e:
                        logger.error(f"❌ Error creating subscriber: {e}")
                
                return
        
        # Check if user joined
        if (old_status in ["left", "kicked", "banned"] and 
            new_status in ["member", "administrator", "creator"]):
            # Set admin status based on new status
            user_info['is_admin'] = is_admin_now
            
            # Check if the user already exists in Grist
            subscriber = grist_client.get_subscriber(user_id)
            if subscriber:
                # User exists, update as rejoin
                record_id = subscriber.get('id')
                logger.info(f"♻️ User {user_id} rejoined chat {chat_id}")
                if grist_client.update_subscriber_rejoin(user_id, record_id):
                    grist_client.add_event({
                        'event_type': 'rejoin',
                        'user_id': str(user_id),
                        'username': user_info['username'],
                        'first_name': user_info['first_name'],
                        'chat_id': str(chat_id),
                        'message_id': 0,
                        'reaction': '',
                        'comment_text': '',
                        'event_date': datetime.now()
                    })
            else:
                # New user, add to Grist
                logger.info(f"➕ User {user_id} joined chat {chat_id}")

                # Add join date and status
                user_info['join_date'] = datetime.now().isoformat()
                user_info['current_status'] = 'active'
                user_info['reaction_counter'] = 0

                if grist_client.add_subscriber(user_info):
                    grist_client.add_event({
                        'event_type': 'join',
                        'user_id': str(user_id),
                        'username': user_info['username'],
                        'first_name': user_info['first_name'],
                        'chat_id': str(chat_id),
                        'message_id': 0,
                        'reaction': '',
                        'comment_text': '',
                        'event_date': datetime.now()
                    })
            
        # Check if user left
        elif (old_status in ["member", "administrator", "creator"] and 
              new_status in ["left", "kicked", "banned"]):
            logger.info(f"➖ User {user_id} left chat {chat_id}")
            
            # Check if the user exists in Grist
            subscriber = grist_client.get_subscriber(user_id)
            leave_recorded = False
            if subscriber:
                # User exists, update as left
                record_id = subscriber.get('id')
                leave_recorded = grist_client.update_subscriber_leave(user_id, record_id)
            else:
                logger.warning(f"⚠️ User {user_id} left but wasn't in the database")

                # Add them with left status for historical record
                user_info['join_date'] = datetime.now().isoformat()
                user_info['leave_date'] = datetime.now().isoformat()
                user_info['current_status'] = 'inactive'
                user_info['reaction_counter'] = 0

                leave_recorded = grist_client.add_subscriber(user_info)

            if leave_recorded:
                grist_client.add_event({
                    'event_type': 'leave',
                    'user_id': str(user_id),
                    'username': user_info['username'],
                    'first_name': user_info['first_name'],
                    'chat_id': str(chat_id),
                    'message_id': 0,
                    'reaction': '',
                    'comment_text': '',
                    'event_date': datetime.now()
                })
    
    return router
