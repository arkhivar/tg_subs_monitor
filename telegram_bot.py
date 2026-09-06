import logging
from datetime import datetime
import os
import config
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, MessageReactionHandler, CallbackContext
from grist_simple_client import GristSimpleClient

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Grist is the single source of truth used by the dashboard and webhook.
db_client = GristSimpleClient()
db_client.init_table()

# Global bot instance that can be used by Flask app
bot = Bot(token=config.TELEGRAM_BOT_TOKEN)

# Global application instance
application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text('Hello! I am a bot that tracks subscribers. Use /help to see available commands.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
    Available commands:
    /start - Start the bot
    /help - Show this help message
    /stats - Show subscriber statistics
    /sync - Sync all current channel members to Grist
    """
    await update.message.reply_text(help_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show subscriber statistics."""
    active_subscribers = db_client.get_all_subscribers(status='active')
    inactive_subscribers = db_client.get_all_subscribers(status='inactive')
    
    # Calculate total reactions
    total_reactions = 0
    top_reactors = []
    
    for subscriber in active_subscribers + inactive_subscribers:
        reaction_count = subscriber.get('reaction_counter', 0)
        # Handle case when reaction_counter might be empty or not an integer
        if reaction_count == '':
            reaction_count = 0
        try:
            reaction_count = int(reaction_count)
        except (ValueError, TypeError):
            reaction_count = 0
            
        total_reactions += reaction_count
        
        # Track top reactors
        if reaction_count > 0:
            username = subscriber.get('username', '')
            first_name = subscriber.get('first_name', '')
            name = username if username else first_name
            if name:
                top_reactors.append((name, reaction_count))
    
    # Sort and get top 3 reactors
    top_reactors.sort(key=lambda x: x[1], reverse=True)
    top_reactors = top_reactors[:3]  # Get top 3
    
    # Build top reactors text
    top_reactors_text = ""
    for i, (name, count) in enumerate(top_reactors):
        if i == 0:
            top_reactors_text += f"🥇 {name}: {count} reactions\n"
        elif i == 1:
            top_reactors_text += f"🥈 {name}: {count} reactions\n"
        elif i == 2:
            top_reactors_text += f"🥉 {name}: {count} reactions\n"
    
    stats_text = f"""
    📊 Subscriber Statistics 📊
    
    Active subscribers: {len(active_subscribers)}
    Inactive subscribers: {len(inactive_subscribers)}
    Total subscribers: {len(active_subscribers) + len(inactive_subscribers)}
    
    💯 Reaction Statistics 💯
    Total reactions: {total_reactions}
    
    🏆 Top Reactors 🏆
    {top_reactors_text if top_reactors else "No reactions recorded yet!"}
    """
    await update.message.reply_text(stats_text)

async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sync all current channel members to Grist."""
    # Get the chat ID of the channel
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID") or "@nochacha"
    
    try:
        # Let the user know we're starting
        message = await update.message.reply_text("Starting to sync channel members, this might take a moment...")
        
        # Detailed diagnostic information to debug channel access
        chat_info = await context.bot.get_chat(chat_id)
        logger.info(f"Channel info: {chat_info.to_dict()}")
        await update.message.reply_text(f"Connected to channel: {chat_info.title} (ID: {chat_info.id})")
        
        # Test if the Grist connection works
        try:
            # Create a test user record
            test_user_id = update.effective_user.id
            test_user_name = update.effective_user.username or update.effective_user.first_name
            
            await update.message.reply_text(f"Testing Grist with your user ID: {test_user_id}")
            
            test_user_data = {
                'user_id': test_user_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'last_name': update.effective_user.last_name,
                'join_date': datetime.now().isoformat(),
                'current_status': 'active',
                'reaction_counter': 1
            }
            
            # Try to find the user first
            logger.info(f"Looking for user {test_user_id} in database")
            existing_user = db_client.get_subscriber(test_user_id)
            
            if existing_user:
                logger.info(f"User {test_user_id} already exists in database: {existing_user}")
                await update.message.reply_text(f"Your user record already exists in Grist. Updating reaction count.")
                
                # Update the user's reaction count
                result = db_client.update_reaction_count(test_user_id)
                if result:
                    await update.message.reply_text("Successfully updated your reaction count!")
                else:
                    await update.message.reply_text("Failed to update reaction count. Check server logs.")
            else:
                logger.info(f"User {test_user_id} not found, adding to database")
                await update.message.reply_text(f"Adding you as a test user to Grist...")
                
                # Add the user
                result = db_client.add_subscriber(test_user_data)
                if result:
                    await update.message.reply_text("Successfully added your user record to database!")
                else:
                    await update.message.reply_text("Failed to add user record. Check server logs.")
        except Exception as e:
            logger.error(f"Error testing database: {e}", exc_info=True)
            await update.message.reply_text(f"Error testing database: {str(e)}")
        
        # Get all current chat members
        # Note: This can only get up to 200 members at a time due to Telegram API limitations
        # For channels with more than 200 members, you'd need to implement pagination
        admins_count = 0
        members_count = 0
        added_count = 0
        updated_count = 0
        
        # Get admins first
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            admins_count = len(admins)
            
            logger.info(f"Found {admins_count} admins in channel {chat_id}")
            await update.message.reply_text(f"Found {admins_count} admins in channel")
            
            # Process admins
            for admin in admins:
                user = admin.user
                user_id = user.id
                
                if user.is_bot:
                    logger.info(f"Skipping bot admin: {user.username}")
                    continue
                    
                logger.info(f"Processing admin: {user.username} ({user_id})")
                
                # Check if user already exists
                existing_user = db_client.get_subscriber(user_id)
                
                if existing_user:
                    logger.info(f"Admin {user_id} already exists in database")
                    # Update as active if previously inactive
                    if existing_user.get('current_status') != 'active':
                        db_client.update_subscriber_rejoin(user_id, existing_user.get('id'))
                        updated_count += 1
                else:
                    logger.info(f"Adding new admin {user_id} to database")
                    # Add new subscriber
                    user_data = {
                        'user_id': user_id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'join_date': datetime.now().isoformat(),
                        'current_status': 'active',
                        'reaction_counter': 0
                    }
                    db_client.add_subscriber(user_data)
                    added_count += 1
                    
        except Exception as e:
            logger.error(f"Error getting admins: {e}", exc_info=True)
            await update.message.reply_text(f"Error getting admins: {str(e)}")
        
        # For channels, use getChatMemberCount and then get a list of members
        # This is a simplified version - in real channels you'd need a different approach
        # as Telegram doesn't provide a direct way to get all members of a channel
        try:
            # This will only work if the bot has admin rights
            members_count = await context.bot.get_chat_member_count(chat_id) - admins_count
            logger.info(f"Channel has approximately {members_count} regular members")
            
            # Note: For actual implementation with large channels, 
            # you would need to use a different approach such as:
            # 1. Using Telethon or Pyrogram libraries which provide more functionality
            # 2. Tracking join/leave events over time
            # 3. Using custom export tools from Telegram desktop app
            
            # Update the message with results
            sync_complete_text = f"""
             ✅ Sync completed!
            
            Admins processed: {admins_count}
            Other members (estimated): {members_count}
            
             Added to Grist: {added_count}
             Updated in Grist: {updated_count}
            
            Note: Due to Telegram API limitations, only admins can be fully synced. 
            Regular members will be tracked when they join or leave the channel.
            """
            await update.message.reply_text(sync_complete_text)
            
        except Exception as e:
            logger.error(f"Error getting member count: {e}", exc_info=True)
            await update.message.reply_text(f"Partial sync completed (admins only). Error: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error syncing channel members: {e}", exc_info=True)
        await update.message.reply_text(f"Error syncing channel members: {str(e)}")

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle new chat members."""
    chat = update.effective_chat
    for new_member in update.message.new_chat_members:
        user_id = new_member.id
        
        if new_member.is_bot:
            logger.info(f"Bot {new_member.username} added to chat {chat.id}")
            continue
            
        logger.info(f"New member joined: {user_id} in chat {chat.id}")
        
        # Check if the user already exists in our database
        existing_user = db_client.get_subscriber(user_id)
        
        if existing_user:
            # User exists, update their rejoin status
            db_client.update_subscriber_rejoin(user_id, existing_user.get('id'))
            logger.info(f"Updated existing subscriber {user_id} as rejoined")
        else:
            # Add new subscriber
            user_data = {
                'id': user_id,
                'username': new_member.username,
                'first_name': new_member.first_name,
                'last_name': new_member.last_name
            }
            db_client.add_subscriber(user_data)
            logger.info(f"Added new subscriber {user_id}")

async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle members that left the chat."""
    chat = update.effective_chat
    left_member = update.message.left_chat_member
    
    if left_member.is_bot:
        logger.info(f"Bot {left_member.username} removed from chat {chat.id}")
        return
        
    user_id = left_member.id
    logger.info(f"Member left: {user_id} from chat {chat.id}")
    
    # Check if the user exists in our database
    existing_user = db_client.get_subscriber(user_id)
    
    if existing_user:
        # Update user as left
        db_client.update_subscriber_leave(user_id, existing_user.get('id'))
        logger.info(f"Updated subscriber {user_id} as left")
        
async def handle_message_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle when users react to messages with emojis."""
    try:
        logger.info(f"Received reaction update type: {type(update).__name__}")
        
        # Enhanced logging for diagnostic purposes
        logger.info(f"Update object attributes: {dir(update)}")
        logger.info(f"Update JSON: {update.to_dict() if hasattr(update, 'to_dict') else 'No to_dict method'}")
        
        # Check for different reaction event types
        message_reaction = None
        user = None
        chat = None
        
        # Handle new message_reaction_count update type
        if hasattr(update, 'message_reaction_count'):
            logger.info("Found message_reaction_count in update")
            reaction_count = update.message_reaction_count
            
            # For message_reaction_count, we need to handle it differently as it doesn't have user info
            # We can only track the total count, not individual users
            chat = reaction_count.chat
            
            # Log all reaction details for debugging
            logger.info(f"Reaction count update in chat {chat.id} ({chat.title})")
            logger.info(f"Reactions: {reaction_count.reactions}")
            
            # Get chat member count - we could use this for analytics
            try:
                if context and hasattr(context, 'bot'):
                    chat_info = await context.bot.get_chat(chat.id)
                    logger.info(f"Chat info: {chat_info.to_dict()}")
            except Exception as e:
                logger.error(f"Error getting chat info: {e}")
                
            # Since we don't have user info here, we can't process this event type
            # for individual user tracking. This is a limitation of Telegram API.
            logger.info("Cannot track individual users from message_reaction_count events")
            return
            
        # Handle the regular message_reaction update type (user-specific)
        elif hasattr(update, 'message_reaction'):
            message_reaction = update.message_reaction
            logger.info("Found message_reaction attribute directly in update")
            
        # Fallback for command-based testing
        elif hasattr(update, 'effective_chat') and hasattr(update, 'effective_user'):
            logger.info(f"Using effective_chat and effective_user from update for testing")
            
            class SimpleReaction:
                def __init__(self, chat, user):
                    self.chat = chat
                    self.user = user
                    self.new_reaction = ["👍"]  # Simulated reaction for testing
                    self.old_reaction = []
            
            message_reaction = SimpleReaction(update.effective_chat, update.effective_user)
        
        if not message_reaction:
            logger.warning("Could not extract message reaction data from update")
            return
        
        logger.info(f"Processing reaction: {message_reaction}")
        
        # Verify the channel is the one we want to track
        chat = message_reaction.chat
        # IMPORTANT: Support both username and numeric ID formats for the channel
        target_channel = os.environ.get("TELEGRAM_CHANNEL_ID") or "@nochacha"
        
        # Track all chat details to diagnose channel matching issues
        chat_details = {
            "id": getattr(chat, "id", None),
            "username": getattr(chat, "username", None),
            "title": getattr(chat, "title", None),
            "type": getattr(chat, "type", None)
        }
        logger.info(f"Chat details: {chat_details}")
        
        # Handle channel identification flexibly 
        # For public channels, username is prefixed with @, for private/supergroups, we use numeric ID
        channel_match = False
        
        # Try to match by chat ID
        if hasattr(chat, 'id') and str(chat.id) == target_channel.lstrip('@'):
            channel_match = True
            logger.info(f"Channel matched by numeric ID: {chat.id}")
        
        # Try to match by username
        elif hasattr(chat, 'username') and chat.username:
            if f"@{chat.username}" == target_channel:
                channel_match = True
                logger.info(f"Channel matched by username: @{chat.username}")
        
        # ALWAYS accept updates for now for testing - we'll record reactions from all chats 
        # to debug the issue, and can filter later
        channel_match = True
        logger.info(f"Accepting reaction from any chat for testing purposes")
                
        # For debugging, log if we would have rejected this channel
        if not channel_match:
            logger.info(f"Would have ignored reaction from non-target channel: {chat_details}")
        
        # Process the user reaction
        user = message_reaction.user
        if user.is_bot:
            logger.info(f"Ignoring reaction from bot: {user.id}")
            return
        
        user_id = user.id
        logger.info(f"Processing reaction from user ID: {user_id}")
        
        if hasattr(message_reaction, 'new_reaction'):
            new_reactions = message_reaction.new_reaction
            old_reactions = getattr(message_reaction, 'old_reaction', [])
        else:
            # For testing - assume there's a new reaction
            new_reactions = ["👍"]
            old_reactions = []
        
        logger.info(f"Reaction from user {user_id} ({user.first_name}): added {new_reactions}, removed {old_reactions}")
        
        # For testing (TEMPORARY): Skip the check for new reactions to see if events are being processed
        # if not new_reactions:
        #     logger.info(f"No new reactions added, skipping database update")
        #     return
            
        # Update reaction count in Grist
        logger.info(f"Looking for existing subscriber with user_id: {user_id}")
        existing_user = db_client.get_subscriber(user_id)
        
        if existing_user:
            logger.info(f"Found existing user in Grist: {existing_user}")
            # Add to reaction counter
            result = db_client.update_reaction_count(user_id)
            logger.info(f"Updated reaction counter for user {user_id}, result: {result}")
        else:
            # If this is the first time we're seeing this user, add them
            logger.info(f"New user {user_id} from reaction, adding to Grist")
            try:
                user_data = {
                    'user_id': user_id,
                    'username': getattr(user, 'username', ''),
                    'first_name': getattr(user, 'first_name', ''),
                    'last_name': getattr(user, 'last_name', ''),
                    'join_date': datetime.now().isoformat(),
                    'current_status': 'active',
                    'reaction_counter': 0  # Start with 0, will be incremented in update_reaction_count
                }
                logger.info(f"Creating user record with data: {user_data}")
                
                add_result = db_client.add_subscriber(user_data)
                logger.info(f"Added new subscriber {user_id} from reaction event, result: {add_result}")
                
                # Then update reaction count
                update_result = db_client.update_reaction_count(user_id)
                logger.info(f"Updated reaction counter for new user {user_id}, result: {update_result}")
            except Exception as e:
                logger.error(f"Error handling new user from reaction: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error in handle_message_reaction: {e}", exc_info=True)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error("Exception while handling an update", exc_info=context.error)
    # You can send a message to a specific chat ID when an error occurs
    # admin_chat_id = 123456789  # Replace with your chat ID
    # await context.bot.send_message(chat_id=admin_chat_id, text=f"An error occurred: {context.error}")

def setup_application():
    """Set up the application with handlers."""
    # Initialize the Grist table
    db_client.init_table()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("sync", sync_command))
    
    # Add chat member handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member))
    
    # Add message reaction handler
    application.add_handler(MessageReactionHandler(handle_message_reaction))
    logger.info("Registered MessageReactionHandler successfully")
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    return application

def create_app():
    """Create and configure the bot application for webhook."""
    # Setup handlers
    app = setup_application()
    
    # Initialize other components
    db_client.init_table()
    
    return app

def get_bot_app():
    """Get the bot application for use with a webhook."""
    return create_app()

def start_polling():
    """Start the bot in polling mode."""
    app = setup_application()
    logger.info("Starting bot in polling mode")
    
    # Configure to get reaction updates and all available event types
    logger.info("Configuring bot to receive all message reactions and events")
    app.run_polling(
        allowed_updates=[
            "message", 
            "edited_message", 
            "channel_post", 
            "edited_channel_post",
            "message_reaction", 
            "message_reaction_count",
            "chat_member", 
            "my_chat_member"
        ],
        drop_pending_updates=False
    )

if __name__ == "__main__":
    logger.info("Testing Grist connection first...")
    try:
        db_client.init_table()
        logger.info("Grist connection test successful")
        
        # Test retrieving subscribers
        all_subscribers = db_client.get_all_subscribers()
        logger.info(f"Retrieved {len(all_subscribers)} subscribers from Grist")
        
        # If we have any subscribers, test the reaction_counter field
        if all_subscribers:
            sample_subscriber = all_subscribers[0]
            subscriber_id = sample_subscriber.get('id')
            user_id = sample_subscriber.get('user_id')
            
            logger.info(f"Testing reaction counter update for user {user_id} (record ID: {subscriber_id})")
            
            # Test reaction counter update
            update_result = db_client.update_reaction_count(user_id)
            logger.info(f"Update reaction count test result: {update_result}")
    except Exception as e:
        logger.error(f"Error testing Grist connection: {e}", exc_info=True)
    
    logger.info("Starting bot polling...")
    start_polling()
