"""
Aiogram Extension for the Flask App

This module provides functionality to run the Aiogram bot alongside the Flask app.
"""

import os
import logging
import threading
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, User

from grist_simple_client import GristSimpleClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get bot token from environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Initialize bot, dispatcher, and router
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Initialize Grist client
db_client = GristSimpleClient()

# Bot handlers

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle the /start command."""
    await message.answer(
        "Hi! I'm a Telegram channel subscriber tracker. "
        "I'll record when users join, leave, or rejoin the channel."
    )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Handle the /help command."""
    help_text = (
        "I'm a Telegram channel subscriber tracker. "
        "I can help track user activity in your channel.\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/status - Show bot status\n"
        "/sync - Sync channel members"
    )
    await message.answer(help_text)

@router.message(Command("status"))
async def cmd_status(message: types.Message):
    """Handle the /status command."""
    # Initialize table if needed
    db_client.init_table()
    
    # Get stats
    subscribers = db_client.get_all_subscribers()
    
    # Count active and inactive subscribers
    active_count = 0
    inactive_count = 0
    for s in subscribers:
        if hasattr(s, 'current_status'):
            if s.current_status == 'active':
                active_count += 1
            elif s.current_status == 'inactive':
                inactive_count += 1
        elif isinstance(s, dict):
            if s.get('current_status') == 'active':
                active_count += 1
            elif s.get('current_status') == 'inactive':
                inactive_count += 1
    
    # Format the response
    status_text = (
        f"📊 Bot Status:\n"
        f"Active subscribers: {active_count}\n"
        f"Inactive subscribers: {inactive_count}\n"
        f"Total tracked users: {len(subscribers)}\n"
        f"Grist database: Connected"
    )
    await message.answer(status_text)

@router.chat_member()
async def on_chat_member_updated(event: ChatMemberUpdated):
    """Handle chat member updates (join/leave events)."""
    logger.info(f"Chat member update: {event.chat.id} - {event.from_user.id} - Old: {event.old_chat_member.status} -> New: {event.new_chat_member.status}")
    
    # Extract user information
    user = event.from_user
    user_id = str(user.id)
    username = user.username or ''
    
    # Check status change type
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    
    # Member joined
    if new_status in ['member', 'administrator'] and old_status in ['left', 'kicked']:
        logger.info(f"User {user_id} ({username}) joined the chat {event.chat.id}")
        
        # Check if user already exists
        existing_user = db_client.get_subscriber(user_id)
        
        if existing_user:
            # User exists, update rejoin information
            db_client.update_subscriber_rejoin(user_id)
            logger.info(f"Updated existing user {user_id} as rejoined")
        else:
            # New user, add to database
            user_data = {
                'user_id': user_id,
                'username': username,
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
                'join_date': datetime.now().isoformat(),
                'current_status': 'active',
                'is_admin': new_status == 'administrator'
            }
            db_client.add_subscriber(user_data)
            logger.info(f"Added new subscriber {user_id}")
    
    # Member left
    elif new_status in ['left', 'kicked'] and old_status in ['member', 'administrator']:
        logger.info(f"User {user_id} ({username}) left the chat {event.chat.id}")
        
        # Mark user as inactive
        db_client.update_subscriber_leave(user_id)
        logger.info(f"Updated user {user_id} as left")

@router.message_reaction()
async def on_message_reaction(reaction_update: types.MessageReactionUpdated):
    """Handle message reaction updates."""
    logger.info(f"Message reaction: {reaction_update.chat.id} - User: {reaction_update.user}")
    
    # Get user information
    user = reaction_update.user
    if not user:
        logger.info(f"No user information in reaction update")
        return
    
    user_id = str(user.id)
    logger.info(f"Updating reaction count for user {user_id}")
    
    # Update reaction count
    db_client.update_reaction_count(user_id)

# Async function to run the bot
async def run_bot():
    """Run the bot in polling mode."""
    # Print bot info
    me = await bot.get_me()
    logger.info(f"Starting bot @{me.username} ({me.first_name})")
    logger.info(f"Bot ID: {me.id}")
    
    # Enable sending chat_member updates
    await bot.get_updates(offset=-1, allowed_updates=[
        "message", "edited_message", "channel_post", "edited_channel_post",
        "message_reaction", "message_reaction_count", "chat_member", "my_chat_member"
    ])
    
    # Start the polling
    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=[
        "message", "edited_message", "channel_post", "edited_channel_post",
        "message_reaction", "message_reaction_count", "chat_member", "my_chat_member"
    ])

# Function to start the bot in a separate thread
def start_bot_in_thread():
    """Start the bot in a separate thread."""
    # Create a new event loop for the thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run the bot
    loop.run_until_complete(run_bot())

# Function to start the bot
def start_bot():
    """Start the bot in a separate thread."""
    # Initialize database
    db_client.init_table()
    
    # Start the bot in a thread
    bot_thread = threading.Thread(target=start_bot_in_thread)
    bot_thread.daemon = True
    bot_thread.start()
    
    logger.info("Bot started in background thread")