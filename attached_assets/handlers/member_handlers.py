from aiogram import Router, F
from aiogram.types import ChatMemberUpdated
from storage.memory_storage import MemoryStorage
from utils.logger import logger

# Create a router for member handlers
router = Router()

async def setup_member_handlers(storage: MemoryStorage):
    """Set up member handlers with the provided storage."""
    
    @router.chat_member()
    async def handle_chat_member_update(update: ChatMemberUpdated):
        """Handle updates to chat members (join/leave)."""
        chat_id = update.chat.id
        user_id = update.new_chat_member.user.id
        user_name = update.new_chat_member.user.full_name
        
        # Determine if user joined or left
        old_status = update.old_chat_member.status
        new_status = update.new_chat_member.status
        
        # Check if user joined
        if (old_status in ["left", "kicked", "banned"] and 
            new_status in ["member", "administrator", "creator"]):
            storage.add_member_event(chat_id, user_id, joined=True)
            logger.info(f"User {user_name} (ID: {user_id}) joined chat {chat_id}")
            
        # Check if user left
        elif (old_status in ["member", "administrator", "creator"] and 
              new_status in ["left", "kicked", "banned"]):
            storage.add_member_event(chat_id, user_id, joined=False)
            logger.info(f"User {user_name} (ID: {user_id}) left chat {chat_id}")
    
    return router
