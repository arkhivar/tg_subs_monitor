import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from config import BOT_TOKEN
from utils.logger import logger
from storage.memory_storage import MemoryStorage
from handlers.reaction_handlers import setup_reaction_handlers
from handlers.member_handlers import setup_member_handlers
from handlers.command_handlers import setup_command_handlers

async def setup_bot():
    """Set up and configure the bot with all handlers."""
    # Initialize bot and dispatcher with proper parameters for aiogram 3.7.0+
    from aiogram.client.default import DefaultBotProperties
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Initialize storage
    storage = MemoryStorage()
    
    # Set up handlers
    reaction_router = await setup_reaction_handlers(storage)
    member_router = await setup_member_handlers(storage)
    command_router = await setup_command_handlers(storage)
    
    # Include routers in the dispatcher
    dp.include_router(reaction_router)
    dp.include_router(member_router)
    dp.include_router(command_router)
    
    # Set up error handling
    @dp.errors()
    async def handle_errors(event, error):
        """Global error handler."""
        logger.error(f"Error occurred: {error}")
        
        # Get the original update object
        update = getattr(event, 'update', None)
        if update:
            update_type = update.event_type
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
    
    return bot, dp

async def main():
    """Main entry point for the bot."""
    logger.info("Starting Telegram Reaction Tracker Bot")
    
    bot, dp = await setup_bot()
    
    # Run the bot until termination
    try:
        logger.info("Bot is running...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error during bot execution: {e}")
    finally:
        logger.info("Bot stopped")
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
