"""
Direct API check for channel reactions

This script directly queries Telegram for the latest channel posts
and checks if there are any reactions on them.
"""
import os
import asyncio
import logging
from datetime import datetime
from telegram.ext import Application
from telegram import Bot
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct_reaction_check")

# Get bot token from env
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_USERNAME = "@nochacha"  # Your channel username with @ symbol

async def check_reactions():
    """Check for reactions on recent channel posts."""
    # Create a bot instance
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Get channel info
        logger.info(f"Getting info for channel: {CHANNEL_USERNAME}")
        channel = await bot.get_chat(CHANNEL_USERNAME)
        channel_id = channel.id
        logger.info(f"Channel ID: {channel_id}")
        
        # Get recent channel posts
        logger.info("Getting recent channel posts...")
        updates = await bot.get_updates(limit=100, timeout=10, allowed_updates=["channel_post", "message_reaction", "message_reaction_count"])
        
        # Log all updates received
        logger.info(f"Received {len(updates)} updates total")
        for update in updates:
            logger.info(f"Update ID: {update.update_id}, Type: {update.to_dict().keys()}")
        
        # Specifically look for channel posts
        channel_posts = [u for u in updates if u.channel_post]
        logger.info(f"Found {len(channel_posts)} channel posts")
        
        # Check for reactions on each post
        for post in channel_posts:
            message_id = post.channel_post.message_id
            logger.info(f"Checking reactions for message {message_id}")
            
            # Try to get reaction count directly if possible
            try:
                # This API call is a direct attempt to get message reactions
                logger.info(f"Trying direct API call for message {message_id} reactions...")
                # This is a custom API call - it's not perfect but helps for testing
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMessageReactionCount?chat_id={channel_id}&message_id={message_id}"
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"API Response: {result}")
                        else:
                            logger.warning(f"API returned status {response.status}")
            except Exception as e:
                logger.error(f"Error making direct API call: {e}")
            
            # Alternatively, try to get the message itself to see reactions
            try:
                logger.info(f"Getting message {message_id} details...")
                # Try to get the message to check if it has reactions
                message = await bot.forward_message(
                    chat_id=channel_id,  # Forward to same channel
                    from_chat_id=channel_id, 
                    message_id=message_id,
                    disable_notification=True
                )
                logger.info(f"Message details: {message.to_dict()}")
                
                # Check for any reactions in the message object
                if hasattr(message, 'reactions'):
                    logger.info(f"Reactions found: {message.reactions}")
                else:
                    logger.info("No reactions attribute in the message object")
            except Exception as e:
                logger.error(f"Error getting message details: {e}")
        
        # Also check if the bot can successfully get message reaction updates
        reaction_updates = [u for u in updates if hasattr(u, 'message_reaction')]
        logger.info(f"Found {len(reaction_updates)} message reaction updates")
        for update in reaction_updates:
            logger.info(f"Reaction update: {update.to_dict()}")
        
        # Check if the bot can successfully get message reaction count updates
        reaction_count_updates = [u for u in updates if hasattr(u, 'message_reaction_count')]
        logger.info(f"Found {len(reaction_count_updates)} message reaction count updates")
        for update in reaction_count_updates:
            logger.info(f"Reaction count update: {update.to_dict()}")
    
    except Exception as e:
        logger.error(f"Error checking reactions: {e}")
    
    # Clean up
    await bot.close()
    
async def main():
    await check_reactions()

if __name__ == "__main__":
    # Run the async function
    asyncio.run(main())