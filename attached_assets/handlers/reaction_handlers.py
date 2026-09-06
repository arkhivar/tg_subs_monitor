from aiogram import Router, F
from aiogram.types import MessageReactionUpdated, MessageReactionCountUpdated
from storage.memory_storage import MemoryStorage
from utils.logger import logger
from config import TRACKED_REACTIONS

# Create a router for reaction handlers
router = Router()

async def setup_reaction_handlers(storage: MemoryStorage):
    """Set up reaction handlers with the provided storage."""
    
    @router.message_reaction()
    async def handle_message_reaction(reaction_update: MessageReactionUpdated):
        """Handle individual user reactions on messages."""
        chat_id = reaction_update.chat.id
        message_id = reaction_update.message_id
        user_id = reaction_update.user.id if reaction_update.user else None
        
        # Process old reactions (removed)
        for reaction_type in reaction_update.old_reaction:
            emoji = reaction_type.emoji
            if emoji in TRACKED_REACTIONS:
                storage.remove_reaction(chat_id, message_id, emoji)
                logger.info(f"User {user_id} removed reaction {emoji} from message {message_id} in chat {chat_id}")
        
        # Process new reactions (added)
        for reaction_type in reaction_update.new_reaction:
            emoji = reaction_type.emoji
            if emoji in TRACKED_REACTIONS:
                storage.add_reaction(chat_id, message_id, emoji)
                logger.info(f"User {user_id} added reaction {emoji} to message {message_id} in chat {chat_id}")
    
    @router.message_reaction_count()
    async def handle_reaction_count_updated(count_update: MessageReactionCountUpdated):
        """Handle updates to reaction counts (aggregated data)."""
        chat_id = count_update.chat.id
        message_id = count_update.message_id
        
        # Clear existing reactions for this message (we'll rebuild from the update)
        for reaction in TRACKED_REACTIONS:
            if storage.get_message_reactions(chat_id, message_id).get(reaction, 0) > 0:
                storage.remove_reaction(chat_id, message_id, reaction, 
                                       storage.get_message_reactions(chat_id, message_id).get(reaction, 0))
        
        # Update with new reaction counts
        for reaction in count_update.reactions:
            emoji = reaction.emoji
            if emoji in TRACKED_REACTIONS:
                storage.add_reaction(chat_id, message_id, emoji, reaction.total_count)
                
        logger.debug(f"Updated reaction counts for message {message_id} in chat {chat_id}")
    
    return router
