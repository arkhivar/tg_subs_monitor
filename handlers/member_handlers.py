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

        # Shared event payload; the client resolves user/chat to Refs
        event_base = {
            'user_id': str(user_id),
            'username': user_info['username'],
            'first_name': user_info['first_name'],
            'last_name': user_info['last_name'],
            'chat_id': str(chat_id),
            'chat_title': chat_title,
            'chat_type': chat_type,
            'message_id': 0,
            'reaction': '',
            'comment_text': '',
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
                membership = grist_client.get_membership(user_id, chat_id)
                if membership:
                    logger.info(f"🔰 Admin status changed for user {user_id}: {is_admin_now}")
                    try:
                        grist_client.set_admin(user_id, chat_id, is_admin_now)
                        logger.info(f"✅ Updated admin status for user {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Error updating admin status: {e}")
                else:
                    # No existing record, create one
                    user_info['is_admin'] = is_admin_now
                    user_info['join_date'] = datetime.now()
                    user_info['current_status'] = 'active'
                    user_info['reaction_counter'] = 0

                    try:
                        grist_client.add_subscriber(user_info, chat_id=chat_id,
                                                    chat_title=chat_title, chat_type=chat_type)
                        logger.info(f"✅ Created new membership with admin status: {is_admin_now}")
                    except Exception as e:
                        logger.error(f"❌ Error creating membership: {e}")

                return

        # Check if user joined
        if (old_status in ["left", "kicked", "banned"] and
            new_status in ["member", "administrator", "creator"]):
            # Set admin status based on new status
            user_info['is_admin'] = is_admin_now

            # Check if the user already has a membership in this chat
            membership = grist_client.get_membership(user_id, chat_id)
            if membership:
                # User exists, update as rejoin
                logger.info(f"♻️ User {user_id} rejoined chat {chat_id}")
                if grist_client.update_subscriber_rejoin(user_id, chat_id, membership.get('id')):
                    grist_client.add_event({**event_base, 'event_type': 'rejoin',
                                            'event_date': datetime.now()})
            else:
                # New member in this chat, add to Grist
                logger.info(f"➕ User {user_id} joined chat {chat_id}")

                # Add join date and status
                user_info['join_date'] = datetime.now()
                user_info['current_status'] = 'active'
                user_info['reaction_counter'] = 0

                if grist_client.add_subscriber(user_info, chat_id=chat_id,
                                               chat_title=chat_title, chat_type=chat_type):
                    grist_client.add_event({**event_base, 'event_type': 'join',
                                            'event_date': datetime.now()})

        # Check if user left
        elif (old_status in ["member", "administrator", "creator"] and
              new_status in ["left", "kicked", "banned"]):
            logger.info(f"➖ User {user_id} left chat {chat_id}")

            # Check if the user has a membership in this chat
            membership = grist_client.get_membership(user_id, chat_id)
            leave_recorded = False
            if membership:
                # User exists, update as left
                leave_recorded = grist_client.update_subscriber_leave(
                    user_id, chat_id, membership.get('id'))
            else:
                logger.warning(f"⚠️ User {user_id} left chat {chat_id} but had no membership")

                # Add them with left status for historical record
                user_info['join_date'] = datetime.now()
                user_info['leave_date'] = datetime.now()
                user_info['current_status'] = 'inactive'
                user_info['reaction_counter'] = 0

                leave_recorded = grist_client.add_subscriber(
                    user_info, chat_id=chat_id, chat_title=chat_title, chat_type=chat_type)

            if leave_recorded:
                grist_client.add_event({**event_base, 'event_type': 'leave',
                                        'event_date': datetime.now()})

    return router
