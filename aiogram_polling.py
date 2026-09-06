"""
Telegram Bot with Aiogram Framework (Polling Mode)

This script runs the bot in polling mode, which is useful for testing
or when you can't set up a webhook.
"""

import os
import asyncio
import logging
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
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
    exit(1)

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
                current_status = None
                if hasattr(existing_user, 'current_status'):
                    current_status = existing_user.current_status
                elif isinstance(existing_user, dict):
                    current_status = existing_user.get('current_status')
                
                if current_status != 'active':
                    record_id = None
                    if hasattr(existing_user, 'id'):
                        record_id = existing_user.id
                    elif isinstance(existing_user, dict):
                        record_id = existing_user.get('id')
                    
                    db_client.update_subscriber_rejoin(user_id, record_id)
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
    logger.info(f"🔔 CHAT MEMBER UPDATE DETECTED 🔔")
    logger.info(f"Chat type: {event.chat.type}, Chat title: {event.chat.title}, Chat ID: {event.chat.id}")
    logger.info(f"User: {event.from_user.id} (@{event.from_user.username or 'no_username'})")
    logger.info(f"Old status: {event.old_chat_member.status} → New status: {event.new_chat_member.status}")
    
    # Extract user information
    user = event.from_user
    user_id = str(user.id)
    username = user.username or ''
    
    # Check status change type
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    
    # Debug more chat info
    try:
        chat_info = await bot.get_chat(event.chat.id)
        logger.info(f"Chat details: Type={chat_info.type}, Title={chat_info.title}")
        
        # Try to get chat member count
        if event.chat.type in ['group', 'supergroup', 'channel']:
            member_count = await bot.get_chat_member_count(event.chat.id)
            logger.info(f"Current member count: {member_count}")
    except Exception as e:
        logger.error(f"Error getting chat details: {e}")
    
    # Member joined - Handle all cases where user becomes active including creator status
    if (new_status in ['member', 'administrator', 'creator'] and 
        old_status in ['left', 'kicked']) or (old_status == 'left' and new_status == 'creator'):
        logger.info(f"👋 JOIN EVENT: User {user_id} (@{username}) joined chat {event.chat.id}")
        
        # Check if user already exists
        existing_user = db_client.get_subscriber(user_id)
        
        if existing_user:
            # User exists, update rejoin information
            result = db_client.update_subscriber_rejoin(user_id)
            logger.info(f"✅ DATABASE UPDATE: User {user_id} marked as rejoined, Result: {result}")
        else:
            # New user, add to database
            user_data = {
                'user_id': user_id,
                'username': username,
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
                'join_date': datetime.now().isoformat(),
                'current_status': 'active',
                'is_admin': new_status in ['administrator', 'creator']
            }
            result = db_client.add_subscriber(user_data)
            logger.info(f"✅ DATABASE INSERT: New subscriber {user_id} added, Result: {result}")
    
    # Member left - Handle all cases where user becomes inactive
    elif (new_status in ['left', 'kicked'] and 
          old_status in ['member', 'administrator', 'creator']) or (old_status == 'creator' and new_status == 'left'):
        logger.info(f"👋 LEAVE EVENT: User {user_id} (@{username}) left chat {event.chat.id}")
        
        # Mark user as inactive
        result = db_client.update_subscriber_leave(user_id)
        logger.info(f"✅ DATABASE UPDATE: User {user_id} marked as left, Result: {result}")
    
    # Other status changes
    else:
        logger.info(f"ℹ️ OTHER STATUS CHANGE: {old_status} → {new_status} for user {user_id}")

# Also add handler for my_chat_member updates (when bot joins/leaves)
@router.my_chat_member()
async def on_my_chat_member_updated(event: ChatMemberUpdated):
    """Handle updates to the bot's membership in chats."""
    logger.info(f"🤖 BOT MEMBERSHIP UPDATE 🤖")
    logger.info(f"Chat type: {event.chat.type}, Chat title: {event.chat.title}, Chat ID: {event.chat.id}")
    logger.info(f"User making change: {event.from_user.id} (@{event.from_user.username or 'no_username'})")
    logger.info(f"Old status: {event.old_chat_member.status} → New status: {event.new_chat_member.status}")
    
    # Bot was added to a new channel/group
    if event.new_chat_member.status in ['member', 'administrator'] and event.old_chat_member.status in ['left', 'kicked']:
        logger.info(f"✅ BOT ADDED to chat {event.chat.id} by user {event.from_user.id}")
        
        # Send a welcome message if it's a group chat
        if event.chat.type in ['group', 'supergroup']:
            try:
                await bot.send_message(
                    event.chat.id, 
                    "Thanks for adding me! I'll track member join/leave events and reactions."
                )
            except Exception as e:
                logger.error(f"Error sending welcome message: {e}")
    
    # Bot was removed from a channel/group
    elif event.new_chat_member.status in ['left', 'kicked'] and event.old_chat_member.status in ['member', 'administrator']:
        logger.info(f"❌ BOT REMOVED from chat {event.chat.id} by user {event.from_user.id}")

# Add debug handler for all channel posts
@router.channel_post()
async def on_channel_post(message: types.Message):
    """Debug handler for channel posts."""
    logger.info(f"📝 CHANNEL POST: Chat={message.chat.id}, Message ID={message.message_id}")

# Track reactions to messages
@router.message_reaction()
async def on_message_reaction(reaction_update: types.MessageReactionUpdated):
    """Handle message reaction updates."""
    logger.info(f"👍 INDIVIDUAL MESSAGE REACTION DETECTED 👍👍👍")
    logger.info(f"Complete reaction update: {reaction_update}")
    logger.info(f"Chat ID: {reaction_update.chat.id}, Chat type: {reaction_update.chat.type}")
    logger.info(f"Message ID: {reaction_update.message_id}")
    
    # Dump all attributes of the update for detailed debugging
    try:
        logger.info(f"Reaction update attributes: {dir(reaction_update)}")
        for attr in dir(reaction_update):
            if not attr.startswith('_') and attr not in ['dict', 'json', 'model_dump', 'update']:
                try:
                    logger.info(f"Attribute {attr}: {getattr(reaction_update, attr, 'Not available')}")
                except:
                    pass
    except Exception as e:
        logger.error(f"Error dumping reaction update attributes: {e}")
    
    # Log emoji reactions
    old_reaction = reaction_update.old_reaction
    new_reaction = reaction_update.new_reaction
    logger.info(f"Reactions change: {old_reaction} → {new_reaction}")
    
    # Get user information
    user = reaction_update.user
    if not user:
        logger.info(f"⚠️ No user information in reaction update - checking for other user identification methods")
        try:
            # Try to extract user info from other fields
            for field in dir(reaction_update):
                if 'user' in field.lower() or 'actor' in field.lower() or 'from' in field.lower():
                    possible_user = getattr(reaction_update, field, None)
                    if possible_user:
                        logger.info(f"Possible user information in field {field}: {possible_user}")
        except Exception as e:
            logger.error(f"Error looking for alternative user info: {e}")
        
        # Handle anonymous reaction - update the channel level stats
        chat_id = reaction_update.chat.id
        channel_user_id = f"channel_{abs(chat_id)}"
        logger.info(f"Updating channel level stats for {channel_user_id}")
        
        try:
            # Check if channel record exists
            existing = db_client.get_subscriber(channel_user_id)
            if existing:
                # Update existing record
                db_client.update_reaction_count(channel_user_id)
                logger.info(f"Updated channel reaction stats from individual reaction event")
            else:
                # Create new channel record
                try:
                    # Get channel details
                    chat_info = await bot.get_chat(chat_id)
                    chat_title = chat_info.title if hasattr(chat_info, 'title') else "Unknown Channel"
                    
                    # Create a record
                    user_data = {
                        'user_id': channel_user_id,
                        'username': chat_title,
                        'first_name': 'Channel',
                        'last_name': chat_title,
                        'join_date': datetime.now().isoformat(),
                        'current_status': 'active',
                        'reaction_counter': 1,
                        'is_admin': False
                    }
                    
                    db_client.add_subscriber(user_data)
                    logger.info(f"Created new channel record from individual reaction event")
                except Exception as e:
                    logger.error(f"Error creating channel record: {e}")
        except Exception as e:
            logger.error(f"Error processing anonymous reaction: {e}")
        
        return
    
    # We have user information
    user_id = str(user.id)
    username = user.username or 'no_username'
    logger.info(f"User who reacted: {user_id} (@{username})")
    logger.info(f"First name: {user.first_name}, Last name: {user.last_name}")
    
    # Log message details if possible
    try:
        message = await bot.get_message(reaction_update.chat.id, reaction_update.message_id)
        if message and message.text:
            preview = message.text[:50] + ("..." if len(message.text) > 50 else "")
            logger.info(f"Message text preview: '{preview}'")
    except Exception as e:
        logger.info(f"Could not get message details: {e}")
    
    # Update or create user record
    existing = db_client.get_subscriber(user_id)
    if existing:
        # Update existing user
        result = db_client.update_reaction_count(user_id)
        logger.info(f"✅ DATABASE UPDATE: Reaction count incremented for user {user_id}, Result: {result}")
    else:
        # Create new user record
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'join_date': datetime.now().isoformat(),
            'current_status': 'active',
            'reaction_counter': 1,
            'is_admin': user.is_premium if hasattr(user, 'is_premium') else False
        }
        
        result = db_client.add_subscriber(user_data)
        logger.info(f"✅ DATABASE INSERT: New user created from reaction, Result: {result}")

# Also add handler for message reaction count updates
@router.message_reaction_count()
async def on_message_reaction_count(reaction_count: types.MessageReactionCountUpdated):
    """Handle message reaction count updates (aggregate reactions)."""
    logger.info(f"📊 REACTION COUNT UPDATE DETECTED 🎯🎯🎯")
    logger.info(f"Chat ID: {reaction_count.chat.id}, Message ID: {reaction_count.message_id}")
    
    # IMPORTANT: Dump the entire reaction update for debugging
    try:
        logger.info(f"FULL REACTION UPDATE OBJECT: {reaction_count}")
        logger.info(f"REACTION UPDATE DIR: {dir(reaction_count)}")
    except Exception as e:
        logger.error(f"Error dumping reaction update object: {e}")
    
    # Extract channel information
    chat_id = reaction_count.chat.id
    is_channel = reaction_count.chat.type == "channel"
    logger.info(f"IS CHANNEL: {is_channel}, CHAT TYPE: {reaction_count.chat.type}")
    
    # Log total reactions - safely access reaction data attributes
    try:
        reaction_texts = []
        total_reaction_count = 0
        
        logger.info(f"REACTIONS LIST TYPE: {type(reaction_count.reactions)}")
        logger.info(f"REACTIONS COUNT: {len(reaction_count.reactions) if hasattr(reaction_count, 'reactions') else 'unknown'}")
        
        for reaction in reaction_count.reactions:
            # Check the actual structure of the object
            reaction_info = str(reaction)
            logger.info(f"REACTION RAW: {reaction_info}")
            logger.info(f"REACTION DIR: {dir(reaction)}")
            
            # Try to extract information safely
            try:
                # Different objects structure based on type
                emoji = None
                if hasattr(reaction, 'type') and reaction.type == 'emoji':
                    emoji = reaction.emoji
                    logger.info(f"EXTRACTED EMOJI FROM TYPE=emoji: {emoji}")
                elif hasattr(reaction, 'emoji'):
                    emoji = reaction.emoji
                    logger.info(f"EXTRACTED EMOJI DIRECTLY: {emoji}")
                else:
                    emoji = '?'
                    logger.info(f"COULD NOT EXTRACT EMOJI, USING PLACEHOLDER")
                
                count = 0
                if hasattr(reaction, 'total_count'):
                    count = reaction.total_count
                    logger.info(f"EXTRACTED COUNT: {count}")
                else:
                    logger.info(f"NO COUNT ATTRIBUTE, TRYING ALTERNATIVES")
                    # Try alternative attribute names
                    for attr in ['count', 'counter', 'total']:
                        if hasattr(reaction, attr):
                            count = getattr(reaction, attr)
                            logger.info(f"FOUND COUNT IN ALTERNATIVE ATTRIBUTE '{attr}': {count}")
                            break
                
                total_reaction_count += count
                reaction_texts.append(f"{count}× {emoji}")
            except Exception as e:
                logger.error(f"Error parsing reaction details: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                continue
        
        reactions_text = ", ".join(reaction_texts)
        logger.info(f"REACTION SUMMARY: {reactions_text} (Total: {total_reaction_count})")
        
        # Always track channel reactions regardless of chat type for testing
        logger.info(f"🚀 ATTEMPTING TO TRACK REACTION FROM CHAT {chat_id}")
        
        # Use a special user ID for the channel
        channel_user_id = f"channel_{abs(chat_id)}"
        logger.info(f"🔑 CHANNEL USER ID: {channel_user_id}")
        
        # Direct implementation to bypass any potential issues
        from datetime import datetime
        current_time = datetime.now().isoformat()
        
        try:
            # First, check if we have this channel already
            logger.info(f"🔍 LOOKING UP CHANNEL {channel_user_id} IN GRIST")
            
            # Manual database check and update
            from config import GRIST_TABLE_NAME
            import os
            from grist_api.grist_api import GristDocAPI
            
            # Get API credentials
            api_key = os.environ.get("GRIST_API_KEY")
            doc_id = os.environ.get("GRIST_DOC_ID")
            table_name = GRIST_TABLE_NAME
            
            logger.info(f"⚙️ GRIST CONFIG: doc_id={doc_id}, table={table_name}, api_key={'present' if api_key else 'missing'}")
            
            # Initialize direct API connection
            api = GristDocAPI(doc_id, api_key=api_key)
            logger.info(f"🔌 CREATED DIRECT GRIST API CONNECTION")
            
            # Fetch all records to find our channel
            logger.info(f"📥 FETCHING ALL RECORDS FROM GRIST TABLE")
            all_records = api.fetch_table(table_name)
            logger.info(f"📊 FOUND {len(all_records)} TOTAL RECORDS")
            
            # Try to find the channel record
            found_record = None
            for record in all_records:
                if hasattr(record, 'user_id') and getattr(record, 'user_id') == channel_user_id:
                    found_record = record
                    logger.info(f"✅ FOUND EXISTING CHANNEL RECORD: id={getattr(record, 'id', 'unknown')}")
                    break
            
            if found_record:
                # Update existing record
                record_id = getattr(found_record, 'id')
                current_count = getattr(found_record, 'reaction_counter', 0)
                new_count = int(current_count) + 1
                
                logger.info(f"📝 UPDATING REACTION COUNT: {current_count} → {new_count}")
                
                update_data = {
                    'id': record_id,
                    'reaction_counter': new_count,
                    'last_reacted': current_time
                }
                
                logger.info(f"📤 SENDING UPDATE TO GRIST: {update_data}")
                result = api.update_records(table_name, [update_data])
                logger.info(f"✅ UPDATE RESULT: {result}")
            else:
                # Create new channel record
                logger.info(f"🆕 CREATING NEW CHANNEL RECORD")
                
                # Get channel details if possible
                chat_title = "Unknown Channel"
                try:
                    chat_info = await bot.get_chat(chat_id)
                    if hasattr(chat_info, 'title'):
                        chat_title = chat_info.title
                except Exception as e:
                    logger.error(f"❌ Error getting chat info: {e}")
                
                logger.info(f"📛 CHANNEL TITLE: {chat_title}")
                
                # Create the record
                new_record = {
                    'user_id': channel_user_id,
                    'username': chat_title,
                    'first_name': 'Channel',
                    'last_name': chat_title,
                    'join_date': current_time,
                    'current_status': 'active',
                    'reaction_counter': 1,
                    'last_reacted': current_time,
                    'is_admin': False
                }
                
                logger.info(f"📤 ADDING NEW RECORD TO GRIST: {new_record}")
                result = api.add_records(table_name, [new_record])
                logger.info(f"✅ ADD RESULT: {result}")
        except Exception as e:
            logger.error(f"❌❌❌ CRITICAL ERROR PROCESSING REACTION: {e}")
            import traceback
            logger.error(f"DETAILED TRACEBACK: {traceback.format_exc()}")
    except Exception as e:
        logger.error(f"Error processing reaction count: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

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

# Main function to run the bot
async def main():
    """Start the bot with polling."""
    # Initialize database
    init_database()
    
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

# Entry point
if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())