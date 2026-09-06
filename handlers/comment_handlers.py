"""
Telegram Bot Comment Handlers

This module persists discussion-group comments (messages) to the Grist
events table.

NOTE: comments on channel posts arrive as regular messages in the channel's
LINKED DISCUSSION GROUP, not in the channel itself. To see them, the bot must
be a member of that discussion group with message access (added as an admin,
or with group privacy mode disabled via BotFather).
"""
from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.types import Message
from utils.logger import logger
from datetime import datetime

# Create a router for comment handlers
router = Router()

async def setup_comment_handlers(grist_client):
    """Set up comment handlers with the provided storage."""
    logger.info("SETUP: Initializing comment handlers")

    @router.message(
        F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
        F.text,
        ~F.text.startswith('/'),
    )
    async def handle_group_comment(message: Message):
        """Persist a discussion-group text message as a comment event."""
        # Ignore messages sent by bots (including the bot itself)
        sender = message.from_user
        if sender is None or sender.is_bot:
            return

        chat_id = message.chat.id
        user_id = sender.id

        logger.info(f"💬 COMMENT: user {user_id} in chat {chat_id}, message_id={message.message_id}")

        grist_client.add_event({
            'event_type': 'comment',
            'user_id': str(user_id),
            'username': sender.username or '',
            'first_name': sender.first_name or '',
            'chat_id': str(chat_id),
            'message_id': message.message_id,
            'reaction': '',
            'comment_text': message.text[:500],
            'event_date': datetime.now()
        })

    logger.info("SETUP: Comment handlers initialized and ready to receive messages")
    return router
