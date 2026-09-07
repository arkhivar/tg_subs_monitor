"""
Enhanced Telegram Bot with Aiogram and Grist Integration

This module implements a Telegram Bot using the Aiogram framework
with a modular architecture to track subscriber activity in Grist.
"""
import asyncio
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Import configuration
from config import TELEGRAM_BOT_TOKEN, BOT_MODE, WEBHOOK_URL, WEBHOOK_PATH, SERVER_HOST, SERVER_PORT
from utils.logger import logger

# Import handlers
from handlers.reaction_handlers import setup_reaction_handlers
from handlers.member_handlers import setup_member_handlers
from handlers.command_handlers import setup_command_handlers
from handlers.comment_handlers import setup_comment_handlers

# Import Grist client for data storage
from grist_simple_client import GristSimpleClient

async def setup_bot():
    """Set up and configure the bot with all handlers."""
    # Initialize the Grist client
    grist_client = GristSimpleClient()
    if not grist_client.init_tables():
        logger.error("Failed to initialize Grist tables (Users/Chats/Membership)")
        sys.exit(1)

    # The events table is additive: warn but keep running if it's missing
    if not grist_client.init_events_table():
        logger.warning("Events table not initialized — event logging will fail until it is created in Grist")
    
    # Initialize bot and dispatcher with proper parameters
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Set up handlers
    reaction_router = await setup_reaction_handlers(grist_client)
    member_router = await setup_member_handlers(grist_client)
    command_router = await setup_command_handlers(grist_client)
    comment_router = await setup_comment_handlers(grist_client)

    # Include routers in the dispatcher
    dp.include_router(reaction_router)
    dp.include_router(member_router)
    dp.include_router(command_router)
    dp.include_router(comment_router)
    
    # Set up error handling
    @dp.errors()
    async def handle_errors(event, error):
        """Global error handler."""
        logger.error(f"Error occurred: {error}")
        
        # Log additional details about the error if available
        error_details = getattr(error, '__dict__', {})
        if error_details:
            logger.error(f"Error details: {error_details}")
        
        # Get the original update object
        update = getattr(event, 'update', None)
        if update:
            update_type = getattr(update, 'event_type', 'unknown')
            logger.error(f"Error in update type: {update_type}")
            
            # Try to send a message about the error if possible
            if hasattr(event, 'message') and event.message:
                try:
                    await event.message.reply(
                        "Sorry, an error occurred while processing your request. "
                        "The bot administrator has been notified."
                    )
                except Exception as e:
                    logger.error(f"Failed to send error notification: {e}")
    
    return bot, dp, grist_client

async def setup_webhook(bot):
    """Set up the webhook for the bot."""
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")
    else:
        logger.info(f"Webhook already set to {WEBHOOK_URL}")

async def start_polling():
    """Start the bot in polling mode."""
    logger.info("Starting the bot in polling mode")
    
    bot, dp, grist_client = await setup_bot()
    
    # Delete any existing webhook
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Run the bot in polling mode
    try:
        logger.info("Bot is running in polling mode...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error during bot execution: {e}")
    finally:
        logger.info("Bot stopped")
        await bot.session.close()

async def start_webhook():
    """Start the bot in webhook mode."""
    from aiohttp import web
    
    if not WEBHOOK_URL:
        logger.error("BOT_MODE is 'webhook' but WEBHOOK_HOST is not set. "
                     "Set WEBHOOK_HOST or switch BOT_MODE to 'polling'.")
        sys.exit(1)
    
    logger.info("Starting the bot in webhook mode")
    
    bot, dp, grist_client = await setup_bot()
    
    # Set up the webhook
    await setup_webhook(bot)
    
    # Create an aiohttp application for the webhook
    app = web.Application()
    
    # Configure routes
    async def handle_webhook(request):
        """Handle incoming webhook updates."""
        try:
            update_data = await request.json()
            await dp.feed_update(bot=bot, update=update_data)
            return web.Response(status=200)
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            return web.Response(status=500)
    
    async def handle_index(request):
        """Simple route for checking if the server is up."""
        return web.Response(text="Bot is running in webhook mode")
    
    # Add routes
    app.router.add_get('/', handle_index)
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    
    # Run the server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, SERVER_HOST, SERVER_PORT)
    
    try:
        await site.start()
        logger.info(f"Webhook server started at {SERVER_HOST}:{SERVER_PORT}")
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    except Exception as e:
        logger.error(f"Error running webhook server: {e}")
    finally:
        # Cleanup
        await bot.delete_webhook()
        await runner.cleanup()
        await bot.session.close()
        logger.info("Bot stopped")

async def main():
    """Main entry point for the bot."""
    logger.info("Starting Telegram Reaction Tracker Bot")
    
    # Start the bot based on configured mode
    if BOT_MODE.lower() == 'webhook':
        await start_webhook()
    else:
        await start_polling()

if __name__ == "__main__":
    asyncio.run(main())
