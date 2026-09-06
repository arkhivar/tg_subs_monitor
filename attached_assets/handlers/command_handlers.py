import time
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from storage.memory_storage import MemoryStorage
from utils.logger import logger
from config import ADMIN_IDS
import asyncio
from datetime import datetime, timedelta

# Create a router for command handlers
router = Router()

async def setup_command_handlers(storage: MemoryStorage):
    """Set up command handlers with the provided storage."""
    
    @router.message(Command("start"))
    async def handle_start(message: Message):
        """Handle the /start command."""
        await message.reply(
            "👋 Hello! I'm a Reaction Tracker Bot.\n\n"
            "I track reactions on messages and member changes in channels/groups.\n\n"
            "Available commands:\n"
            "/stats - Show reaction statistics\n"
            "/members - Show member statistics\n"
            "/help - Show help information"
        )
    
    @router.message(Command("help"))
    async def handle_help(message: Message):
        """Handle the /help command."""
        help_text = (
            "📚 <b>Bot Commands</b>\n\n"
            "Basic commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/stats - Show reaction statistics\n"
            "/members - Show member statistics\n\n"
            
            "Admin-only commands:\n"
            "/reset - Reset all data for this chat\n"
            "/export - Export statistics (coming soon)\n\n"
            
            "This bot automatically tracks:\n"
            "• Reactions on messages\n"
            "• Members joining and leaving"
        )
        await message.reply(help_text, parse_mode="HTML")
    
    @router.message(Command("stats"))
    async def handle_stats(message: Message):
        """Handle the /stats command to show reaction statistics."""
        chat_id = message.chat.id
        
        # Get reaction statistics
        total_reactions = storage.get_total_reactions_by_emoji(chat_id)
        
        if not total_reactions:
            await message.reply("No reactions have been tracked in this chat yet.")
            return
        
        # Format the statistics
        stats_text = "📊 <b>Reaction Statistics</b>\n\n"
        
        # Sort reactions by count (descending)
        sorted_reactions = sorted(total_reactions.items(), key=lambda x: x[1], reverse=True)
        
        for emoji, count in sorted_reactions:
            stats_text += f"{emoji}: {count}\n"
        
        total_count = sum(total_reactions.values())
        stats_text += f"\n<b>Total Reactions:</b> {total_count}"
        
        await message.reply(stats_text, parse_mode="HTML")
    
    @router.message(Command("members"))
    async def handle_members(message: Message):
        """Handle the /members command to show member statistics."""
        chat_id = message.chat.id
        
        # Get member statistics
        member_stats = storage.get_join_leave_stats(chat_id)
        
        if not member_stats["joins"] and not member_stats["leaves"]:
            await message.reply("No member changes have been tracked in this chat yet.")
            return
        
        # Format the statistics
        stats_text = "👥 <b>Member Statistics</b>\n\n"
        stats_text += f"Current Members: {member_stats['current_members']}\n"
        stats_text += f"Total Joins: {member_stats['joins']}\n"
        stats_text += f"Total Leaves: {member_stats['leaves']}\n"
        
        # Get recent events
        recent_events = storage.get_member_events(chat_id, limit=5)
        
        if recent_events:
            stats_text += "\n<b>Recent Activity:</b>\n"
            for timestamp, user_id, joined in reversed(recent_events):
                event_type = "joined" if joined else "left"
                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                stats_text += f"• User {user_id} {event_type} at {time_str}\n"
        
        await message.reply(stats_text, parse_mode="HTML")
    
    @router.message(Command("reset"))
    async def handle_reset(message: Message):
        """Handle the /reset command to clear all data (admin only)."""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Check if user is admin
        if user_id not in ADMIN_IDS:
            await message.reply("⚠️ This command is restricted to bot administrators.")
            return
        
        # Clear data
        storage.clear_chat_data(chat_id)
        logger.info(f"Admin {user_id} reset data for chat {chat_id}")
        
        await message.reply("✅ All tracking data for this chat has been reset.")
    
    @router.message(Command("export"))
    async def handle_export(message: Message):
        """Handle the /export command to export statistics (admin only)."""
        user_id = message.from_user.id
        
        # Check if user is admin
        if user_id not in ADMIN_IDS:
            await message.reply("⚠️ This command is restricted to bot administrators.")
            return
        
        # For now, just inform that this feature is not implemented
        await message.reply("📝 The export feature is coming soon.")
    
    return router
