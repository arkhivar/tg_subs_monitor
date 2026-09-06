"""
Telegram Bot Reaction Handlers

This module provides handlers for Telegram message reactions
and stores reaction data in Grist.
"""
from aiogram import Router, F
from aiogram.types import MessageReactionUpdated, MessageReactionCountUpdated
from utils.logger import logger
from config import TRACKED_REACTIONS
from datetime import datetime

# Create a router for reaction handlers
router = Router()

def _first_tracked_emoji(reaction_update):
    """Extract the first tracked emoji from a reaction update ('' if none)."""
    for reaction_type in getattr(reaction_update, 'new_reaction', []) or []:
        emoji = getattr(reaction_type, 'emoji', None)
        if emoji is None:
            inner = getattr(reaction_type, 'type', None)
            emoji = getattr(inner, 'emoji', None)
        if emoji and emoji in TRACKED_REACTIONS:
            return emoji
    return ''

def _add_anonymous_reaction_event(grist_client, chat_id, message_id, reaction_update,
                                  user_id='', username='', first_name=''):
    """Record a reaction event row for anonymous (no from-user) reactions."""
    grist_client.add_event({
        'event_type': 'reaction',
        'user_id': str(user_id) if user_id else '',
        'username': username or '',
        'first_name': first_name or '',
        'chat_id': str(chat_id),
        'message_id': message_id,
        'reaction': _first_tracked_emoji(reaction_update),
        'comment_text': '',
        'event_date': datetime.now()
    })

async def setup_reaction_handlers(grist_client):
    """Set up reaction handlers with the provided storage."""
    logger.info("SETUP: Initializing reaction handlers")
    
    # Instead of using router.update(), we'll log in each specific handler
    logger.info("DEBUG: Added extensive logging to event handlers")
    
    # Log when the bot starts receiving updates
    logger.info("SETUP: Reaction handlers initialized and ready to receive updates")
    
    @router.message_reaction()
    async def handle_message_reaction(reaction_update: MessageReactionUpdated):
        """Handle individual user reactions on messages."""
        # Extract information from the update
        chat_id = reaction_update.chat.id
        message_id = reaction_update.message_id
        chat_type = reaction_update.chat.type
        chat_title = getattr(reaction_update.chat, 'title', 'Private Chat')
        
        # Enhanced debugging - Log entire update object
        try:
            import json
            from pprint import pformat
            
            # Create a serializable version of the update
            update_dict = {}
            for key in dir(reaction_update):
                if not key.startswith('_') and key != 'bot' and key != 'model_dump_json':
                    try:
                        value = getattr(reaction_update, key)
                        if not callable(value):
                            if hasattr(value, '__dict__'):
                                update_dict[key] = str(value)
                            else:
                                update_dict[key] = value
                    except Exception as e:
                        update_dict[key] = f"Error accessing: {e}"
            
            # Log the full structure
            logger.info(f"🔍 FULL REACTION UPDATE STRUCTURE: \n{pformat(update_dict)}")
        except Exception as e:
            logger.error(f"Error dumping update structure: {e}")
        
        # Log all available data for debugging
        logger.info(f"⚡ REACTION UPDATE: chat_id={chat_id}, message_id={message_id}")
        logger.info(f"📡 Chat type: {chat_type}, title: {chat_title}")
        
        # Check if we have user information
        if reaction_update.user:
            user_id = reaction_update.user.id
            username = reaction_update.user.username
            first_name = reaction_update.user.first_name
            last_name = reaction_update.user.last_name
            
            logger.info(f"👤 User info available: user_id={user_id}, username={username}")
            
            # Count new reactions added
            added_reactions = 0
            tracked_emojis = []
            for reaction_type in reaction_update.new_reaction:
                # Handle different reaction structure safely
                try:
                    if hasattr(reaction_type, 'emoji'):
                        emoji = reaction_type.emoji
                    elif hasattr(reaction_type, 'type') and hasattr(reaction_type.type, 'emoji'):
                        emoji = reaction_type.type.emoji
                    else:
                        emoji = '❓'
                except Exception as e:
                    logger.error(f"Error extracting emoji: {e}")
                    emoji = '❓'
                
                logger.info(f"➕ User {user_id} added reaction {emoji} to message {message_id} in chat {chat_id}")
                if emoji in TRACKED_REACTIONS:
                    added_reactions += 1
                    tracked_emojis.append(emoji)
            
            # Only proceed if we have reactions to track
            if added_reactions > 0:
                # Update the user's reaction count in Grist
                subscriber = grist_client.get_subscriber(user_id)
                if subscriber:
                    # Update existing subscriber
                    record_id = subscriber.get('id')
                    reaction_counter = subscriber.get('reaction_counter', 0) + added_reactions
                    current_time = datetime.now().isoformat()
                    
                    # Update the record with new reaction data
                    update_data = {
                        'id': record_id,
                        'reaction_counter': reaction_counter,
                        'last_reacted': current_time
                    }
                    
                    try:
                        grist_client.api.update_records(grist_client.table_name, [update_data])
                        logger.info(f"✅ Updated reaction count for user {user_id} to {reaction_counter}")
                        # Record one events-table row per tracked emoji added
                        for tracked_emoji in tracked_emojis:
                            grist_client.add_event({
                                'event_type': 'reaction',
                                'user_id': str(user_id),
                                'username': username or '',
                                'first_name': first_name or '',
                                'chat_id': str(chat_id),
                                'message_id': message_id,
                                'reaction': tracked_emoji,
                                'comment_text': '',
                                'event_date': datetime.now()
                            })
                    except Exception as e:
                        logger.error(f"❌ Error updating reaction count: {e}")
                else:
                    # Create a new subscriber record from this reaction
                    logger.info(f"📝 Creating new subscriber record from reaction data for {username}")
                    new_user = {
                        'user_id': str(user_id),
                        'username': username or '',
                        'first_name': first_name or '',
                        'last_name': last_name or '',
                        'join_date': datetime.now().isoformat(),
                        'current_status': 'active',
                        'reaction_counter': added_reactions,
                        'last_reacted': datetime.now().isoformat(),
                        'is_admin': False  # Default to not admin
                    }
                    
                    try:
                        if grist_client.add_subscriber(new_user):
                            logger.info(f"✅ Created new subscriber from reaction: {user_id}")
                            # Record one events-table row per tracked emoji added
                            for tracked_emoji in tracked_emojis:
                                grist_client.add_event({
                                    'event_type': 'reaction',
                                    'user_id': str(user_id),
                                    'username': username or '',
                                    'first_name': first_name or '',
                                    'chat_id': str(chat_id),
                                    'message_id': message_id,
                                    'reaction': tracked_emoji,
                                    'comment_text': '',
                                    'event_date': datetime.now()
                                })
                    except Exception as e:
                        logger.error(f"❌ Error creating subscriber from reaction: {e}")
        else:
            # No user information available - Telegram API limitation
            logger.warning(f"⚠️ No user information available in reaction update!")
            
            # Get the message that was reacted to - sometimes it has user information
            try:
                message = await reaction_update.bot.get_messages(chat_id=chat_id, message_ids=message_id)
                logger.info(f"Retrieved message: {message}")
                
                if message and message.from_user:
                    msg_user_id = message.from_user.id
                    msg_username = message.from_user.username
                    logger.info(f"Message author: {msg_user_id} ({msg_username})")
                    
                    # Found the message author, this could be the reactor in some cases
                    # especially for admin self-reactions
                    subscriber = grist_client.get_subscriber(msg_user_id)
                    if subscriber and subscriber.get('is_admin'):
                        record_id = subscriber.get('id')
                        reaction_counter = subscriber.get('reaction_counter', 0) + 1
                        current_time = datetime.now().isoformat()
                        
                        update_data = {
                            'id': record_id,
                            'reaction_counter': reaction_counter,
                            'last_reacted': current_time
                        }
                        
                        try:
                            grist_client.api.update_records(grist_client.table_name, [update_data])
                            logger.info(f"✅ Updated reaction count for message author (admin) {msg_user_id} to {reaction_counter}")
                            # Anonymous reaction: reactor identity unknown, user fields left empty
                            _add_anonymous_reaction_event(grist_client, chat_id, message_id, reaction_update)
                        except Exception as e:
                            logger.error(f"❌ Error updating message author reaction count: {e}")
            except Exception as e:
                logger.error(f"Error getting message: {e}")
            
            # For anonymous reactions, get the actor if available
            actor = getattr(reaction_update, 'actor', None)
            if actor and hasattr(actor, 'user_id'):
                user_id = actor.user_id
                logger.info(f"Found user ID through actor: {user_id}")
                
                # Try to update subscriber by user_id
                subscriber = grist_client.get_subscriber(user_id)
                if subscriber:
                    record_id = subscriber.get('id')
                    reaction_counter = subscriber.get('reaction_counter', 0) + 1
                    current_time = datetime.now().isoformat()
                    
                    # Update the record with new reaction data
                    update_data = {
                        'id': record_id,
                        'reaction_counter': reaction_counter,
                        'last_reacted': current_time
                    }
                    
                    try:
                        grist_client.api.update_records(grist_client.table_name, [update_data])
                        logger.info(f"✅ Updated reaction count for user {user_id} to {reaction_counter}")
                        # Record reaction event; actor user_id is known here
                        _add_anonymous_reaction_event(
                            grist_client, chat_id, message_id, reaction_update,
                            user_id=user_id,
                            username=getattr(actor, 'username', '') or '',
                            first_name=getattr(actor, 'first_name', '') or '')
                    except Exception as e:
                        logger.error(f"❌ Error updating reaction count: {e}")

            # Try to access the channel chat to get admin information
            try:
                # Get chat object for detailed information
                chat = await reaction_update.bot.get_chat(chat_id)
                if chat and hasattr(chat, 'permissions'):
                    logger.info(f"Chat permissions found: {chat.permissions}")
                    
                # Get all admin members from the chat
                admins = await reaction_update.bot.get_chat_administrators(chat_id)
                logger.info(f"Found {len(admins)} admins in the chat")
                
                # We can't determine which admin reacted, but update only the bot owner/creator
                # who is most likely to be reacting to test the functionality
                creator_found = False
                for admin in admins:
                    user_id = admin.user.id
                    username = admin.user.username
                    status = admin.status
                    
                    # Only update the channel creator/owner
                    if status == 'creator':
                        creator_found = True
                        logger.info(f"Channel creator found: {user_id} ({username})")
                        
                        # Update this admin's reaction count
                        subscriber = grist_client.get_subscriber(user_id)
                        if subscriber:
                            record_id = subscriber.get('id')
                            reaction_counter = subscriber.get('reaction_counter', 0) + 1
                            current_time = datetime.now().isoformat()
                            
                            update_data = {
                                'id': record_id,
                                'reaction_counter': reaction_counter,
                                'last_reacted': current_time
                            }
                            
                            try:
                                grist_client.api.update_records(grist_client.table_name, [update_data])
                                logger.info(f"✅ Updated reaction count for channel creator {user_id} to {reaction_counter}")
                                # Anonymous reaction: reactor identity unknown, user fields left empty
                                _add_anonymous_reaction_event(grist_client, chat_id, message_id, reaction_update)
                            except Exception as e:
                                logger.error(f"❌ Error updating creator reaction count: {e}")
                
                # If no creator was found, try bot admin as fallback
                if not creator_found:
                    bot_info = await reaction_update.bot.get_me()
                    bot_id = bot_info.id
                    logger.info(f"Using bot ID as fallback: {bot_id}")
                    
                    # Use a special record for the bot admin
                    subscriber = grist_client.get_subscriber(f"admin_{bot_id}")
                    if subscriber:
                        record_id = subscriber.get('id')
                        reaction_counter = subscriber.get('reaction_counter', 0) + 1
                        current_time = datetime.now().isoformat()
                        
                        update_data = {
                            'id': record_id,
                            'reaction_counter': reaction_counter,
                            'last_reacted': current_time
                        }
                        
                        try:
                            grist_client.api.update_records(grist_client.table_name, [update_data])
                            logger.info(f"✅ Updated reaction count for bot admin {bot_id} to {reaction_counter}")
                            # Anonymous reaction: reactor identity unknown, user fields left empty
                            _add_anonymous_reaction_event(grist_client, chat_id, message_id, reaction_update)
                        except Exception as e:
                            logger.error(f"❌ Error updating bot admin reaction count: {e}")
                    else:
                        # Create a new admin record
                        logger.info(f"Creating admin tracking record for bot: {bot_id}")
                        admin_data = {
                            'user_id': f"admin_{bot_id}",
                            'username': f"Admin: {bot_info.username}",
                            'first_name': bot_info.first_name,
                            'last_name': bot_info.last_name or '',
                            'join_date': datetime.now().isoformat(),
                            'current_status': 'active',
                            'reaction_counter': 1,
                            'last_reacted': datetime.now().isoformat(),
                            'is_admin': True
                        }
                        
                        try:
                            grist_client.add_subscriber(admin_data)
                            logger.info(f"✅ Created admin record for bot: {bot_id}")
                        except Exception as e:
                            logger.error(f"❌ Error creating admin record: {e}")
            except Exception as e:
                logger.error(f"Error handling channel admin data: {e}")
    
    @router.message_reaction_count()
    async def handle_reaction_count_updated(count_update: MessageReactionCountUpdated):
        """Handle updates to reaction counts (aggregated data)."""
        chat_id = count_update.chat.id
        message_id = count_update.message_id
        chat_type = count_update.chat.type
        chat_title = getattr(count_update.chat, 'title', 'Private Chat')
        
        # Enhanced debugging - Log entire update object
        try:
            import json
            from pprint import pformat
            
            # Create a serializable version of the update
            update_dict = {}
            for key in dir(count_update):
                if not key.startswith('_') and key != 'bot' and key != 'model_dump_json':
                    try:
                        value = getattr(count_update, key)
                        if not callable(value):
                            if hasattr(value, '__dict__'):
                                update_dict[key] = str(value)
                            else:
                                update_dict[key] = value
                    except Exception as e:
                        update_dict[key] = f"Error accessing: {e}"
            
            # Log the full structure
            logger.info(f"🔍 FULL REACTION COUNT UPDATE STRUCTURE: \n{pformat(update_dict)}")
            
            # Specifically look for user information in any nested objects
            if hasattr(count_update, 'reactions'):
                logger.info(f"Reactions object type: {type(count_update.reactions)}")
                for i, reaction in enumerate(count_update.reactions):
                    logger.info(f"Reaction {i+1} type: {type(reaction)}")
                    reaction_dict = {}
                    for key in dir(reaction):
                        if not key.startswith('_'):
                            try:
                                value = getattr(reaction, key)
                                if not callable(value):
                                    reaction_dict[key] = str(value)
                            except:
                                pass
                    logger.info(f"Reaction {i+1} structure: {reaction_dict}")
        except Exception as e:
            logger.error(f"Error dumping update structure: {e}")
        
        logger.info(f"📊 REACTION COUNT UPDATE: chat_id={chat_id}, message_id={message_id}")
        logger.info(f"📡 Chat type: {chat_type}, title: {chat_title}")
        
        # Handle channel reactions with a special channel_[chatid] record
        if chat_type == 'channel':
            channel_user_id = f"channel_{chat_id}"
            logger.info(f"📺 Processing channel reaction for {channel_user_id}")
            
            # Check if we have a channel record already
            channel_record = grist_client.get_subscriber(channel_user_id)
            
            # Count total reactions from this update
            total_reactions = 0
            for reaction in count_update.reactions:
                try:
                    # Handle ReactionTypeEmoji objects correctly
                    if hasattr(reaction, 'type') and hasattr(reaction.type, 'emoji'):
                        emoji = reaction.type.emoji
                    else:
                        emoji = getattr(reaction, 'emoji', None)
                    
                    count = getattr(reaction, 'total_count', 1)
                    
                    logger.debug(f"Reaction details: {reaction}")
                    logger.info(f"Processed reaction with emoji: {emoji}, count: {count}")
                    
                    if emoji and emoji in TRACKED_REACTIONS:
                        total_reactions += count
                        logger.info(f"Counted reaction {emoji} with count {count}")
                except Exception as e:
                    logger.error(f"Error processing reaction: {e}, reaction={reaction}")
            
            if channel_record:
                # Update existing channel record
                record_id = channel_record.get('id')
                current_count = channel_record.get('reaction_counter', 0)
                
                # Only update if we have new reactions
                if total_reactions > 0:
                    update_data = {
                        'id': record_id,
                        'reaction_counter': current_count + total_reactions,
                        'last_reacted': datetime.now().isoformat()
                    }
                    
                    try:
                        grist_client.api.update_records(grist_client.table_name, [update_data])
                        logger.info(f"✅ Updated reaction count for channel {chat_id} to {current_count + total_reactions}")
                    except Exception as e:
                        logger.error(f"❌ Error updating channel reaction count: {e}")
            else:
                # Create a new channel record
                new_channel = {
                    'user_id': channel_user_id,
                    'username': f"Channel: {chat_title}",
                    'first_name': chat_title,
                    'last_name': '',
                    'join_date': datetime.now().isoformat(),
                    'current_status': 'active',
                    'reaction_counter': total_reactions,
                    'last_reacted': datetime.now().isoformat(),
                    'is_admin': False
                }
                
                try:
                    grist_client.add_subscriber(new_channel)
                    logger.info(f"✅ Created new channel record with {total_reactions} reactions")
                except Exception as e:
                    logger.error(f"❌ Error creating channel record: {e}")
        
        # Log all reactions for this message
        for reaction in count_update.reactions:
            try:
                # Handle ReactionTypeEmoji objects correctly
                if hasattr(reaction, 'type') and hasattr(reaction.type, 'emoji'):
                    emoji = reaction.type.emoji
                else:
                    emoji = getattr(reaction, 'emoji', '❓')
                
                count = getattr(reaction, 'total_count', 1)
                logger.info(f"Reaction {emoji}: {count} times")
            except Exception as e:
                logger.error(f"Error logging reaction details: {e}")
            
    return router
