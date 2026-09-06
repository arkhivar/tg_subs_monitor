"""
Telegram Bot with Aiogram Framework

This module implements a Telegram Bot using the Aiogram framework
to track and store subscriber activity in Grist.
"""

import os
import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import ChatMemberUpdated, User
from aiohttp import web

from grist_simple_client import GristSimpleClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get config from environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_HOST = os.environ.get("WEBHOOK_URL", "")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Initialize bot, dispatcher, and router
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Initialize Grist client
db_client = GristSimpleClient()

# Handler functions for different events
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
    active_count = sum(1 for s in subscribers if s.current_status == 'active')
    inactive_count = sum(1 for s in subscribers if s.current_status == 'inactive')
    
    # Format the response
    status_text = (
        f"📊 Bot Status:\n"
        f"Active subscribers: {active_count}\n"
        f"Inactive subscribers: {inactive_count}\n"
        f"Total tracked users: {len(subscribers)}\n"
        f"Grist database: Connected"
    )
    await message.answer(status_text)

@router.message(Command("sync"))
async def cmd_sync(message: types.Message):
    """Handle the /sync command. Synchronize channel admins."""
    await message.answer("Starting admin sync...")
    
    try:
        # Try to get the chat ID from the message
        chat_id = message.chat.id 
        
        # Get admins from the chat
        admins = await bot.get_chat_administrators(chat_id)
        admins_count = len(admins)
        
        added_count = 0
        updated_count = 0
        
        # Process admins
        for admin in admins:
            user = admin.user
            user_id = str(user.id)
            
            if user.is_bot:
                continue
                
            # Check if user already exists
            existing_user = db_client.get_subscriber(user_id)
            
            if existing_user:
                # Update as active if previously inactive
                if existing_user.current_status != 'active':
                    db_client.update_subscriber_rejoin(user_id, existing_user.id)
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
        
        # Send results
        await message.answer(
            f"Sync completed: {admins_count} admins found\n"
            f"Added {added_count} new admins\n"
            f"Updated {updated_count} existing admins"
        )
        
    except Exception as e:
        logger.error(f"Error in sync command: {e}")
        await message.answer(f"Error syncing: {str(e)}")

# Track chat member updates
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

# Track reactions to messages
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

# Setup webhook
async def set_webhook():
    """Set up the webhook."""
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set, webhook won't be configured")
        return False
    
    webhook_info = await bot.get_webhook_info()
    
    if webhook_info.url != WEBHOOK_URL:
        logger.info(f"Setting webhook to {WEBHOOK_URL}")
        await bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=[
                "message", "edited_message", "channel_post", "edited_channel_post",
                "message_reaction", "message_reaction_count", "chat_member", "my_chat_member"
            ]
        )
        return True
    else:
        logger.info(f"Webhook already set to {WEBHOOK_URL}")
        return True

# Delete webhook
async def delete_webhook():
    """Delete the webhook."""
    await bot.delete_webhook()
    logger.info("Webhook deleted")

# Initialize database
def init_database():
    """Initialize the database."""
    try:
        logger.info("Initializing database...")
        success = db_client.init_table()
        if success:
            logger.info("Database initialized successfully")
        else:
            logger.warning("Database initialization had issues")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

# Startup and shutdown handlers
@asynccontextmanager
async def bot_lifespan(app):
    """Lifespan manager for the bot."""
    # Initialize the database
    init_database()
    
    # Set up the webhook if URL is configured
    if WEBHOOK_URL:
        await set_webhook()
    
    # Do not delete webhook on startup
    # await delete_webhook() 
    
    yield
    
    # Cleanup on shutdown
    await bot.session.close()

# Create a web application
async def create_app():
    """Create a web application."""
    # Initialize database synchronously
    init_database()
    
    # Create app
    app = web.Application()
    
    # Setup webhook handling
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    
    # Setup application and routes
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Add home route for status check
    async def home_handler(request):
        return web.Response(text="Telegram bot is running")
    
    app.router.add_get("/", home_handler)
    
    # Setup app lifespan
    app.cleanup_ctx.append(bot_lifespan)
    
    return app

# For use with AioHTTP web server
async def start_webhook():
    """Start the bot with webhook."""
    app = await create_app()
    return app

# For running as standalone with polling
async def start_polling():
    """Start the bot with polling."""
    # Initialize database
    init_database()
    
    # Start the polling
    await dp.start_polling(bot)

# Main entry point
if __name__ == "__main__":
    # Check if webhook URL is set
    if WEBHOOK_URL:
        logger.info(f"Starting bot with webhook at {WEBHOOK_URL}")
        web.run_app(create_app(), host="0.0.0.0", port=5000)
    else:
        logger.info("Starting bot with polling")
        asyncio.run(start_polling())