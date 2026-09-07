"""
Telegram Bot Command Handlers

This module provides handlers for bot commands and
displays data from Grist.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from utils.logger import logger
from datetime import datetime, timedelta

# Create a router for command handlers
router = Router()

def _value(record, field, default=None):
    """Read a field from either a Grist dict or a record-like object."""
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)

def _as_int(value, default=0):
    """Convert Grist numeric fields safely for bot responses."""
    if value in (None, ''):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default

def _parse_datetime(value):
    """Parse Grist ISO dates and Unix timestamps into a comparable datetime."""
    if value in (None, ''):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value).strip()
            try:
                parsed = datetime.fromtimestamp(float(text))
            except ValueError:
                parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
        if parsed.tzinfo:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError, OverflowError):
        return None

async def setup_command_handlers(grist_client):
    """Set up command handlers with the provided storage."""

    @router.message(CommandStart())
    async def cmd_start(message: Message):
        """Handle the /start command."""
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name

        # Make sure the user exists in the Users table (identity only — a
        # private /start creates no membership in any monitored chat)
        grist_client.upsert_user(user_id,
                                 username=username or '',
                                 first_name=first_name or '',
                                 last_name=last_name or '')
        logger.info(f"Upserted user from /start command: {user_id}")

        await message.answer(
            f"👋 Welcome, {first_name}!\n\n"
            f"I am a Telegram bot that tracks channel subscriber activity and reactions.\n\n"
            f"Use /help to see available commands."
        )

    @router.message(Command("help"))
    async def cmd_help(message: Message):
        """Handle the /help command."""
        await message.answer(
            "📚 <b>Available Commands</b>\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/stats - Show subscriber statistics\n"
            "/reactions - Show reaction statistics\n"
            "/status - Show bot status\n"
            "\n"
            "🔶 <b>Admin Commands</b>\n"
            "/sync - Sync channel admins into Grist (admin only)\n"
        )

    @router.message(Command("stats"))
    async def cmd_stats(message: Message):
        """Handle the /stats command."""
        try:
            # Get all memberships (across all monitored chats)
            memberships = grist_client.get_all_memberships()

            # Calculate statistics
            total_count = len(memberships)
            active_count = sum(1 for sub in memberships if _value(sub, 'current_status') == 'active')
            inactive_count = sum(1 for sub in memberships if _value(sub, 'current_status') == 'inactive')
            admin_count = sum(1 for sub in memberships if _value(sub, 'is_admin', False))

            # Calculate recent joins
            one_day_ago = datetime.now() - timedelta(days=1)
            recent_joins = sum(1 for sub in memberships
                               if _value(sub, 'join_date') and
                               _value(sub, 'current_status') == 'active' and
                               _parse_datetime(_value(sub, 'join_date')) and
                               _parse_datetime(_value(sub, 'join_date')) > one_day_ago)

            # Format the response
            response = (
                "📊 <b>Subscriber Statistics</b>\n\n"
                f"👥 Total subscribers: {total_count}\n"
                f"✅ Active subscribers: {active_count}\n"
                f"❌ Inactive subscribers: {inactive_count}\n"
                f"👑 Admins: {admin_count}\n"
                f"🆕 New subscribers (24h): {recent_joins}\n"
            )

            await message.answer(response)
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await message.answer("❌ Error fetching statistics. Please try again later.")

    @router.message(Command("reactions"))
    async def cmd_reactions(message: Message):
        """Handle the /reactions command."""
        try:
            # Get all memberships
            memberships = grist_client.get_all_memberships()

            # Calculate total reactions
            total_reactions = sum(_as_int(_value(sub, 'reaction_counter', 0)) for sub in memberships)

            # Find top reactors
            reactors = [(_value(sub, 'tg_userid', ''),
                        _value(sub, 'username', '') or _value(sub, 'first_name', ''),
                        _as_int(_value(sub, 'reaction_counter', 0)))
                      for sub in memberships
                       if _as_int(_value(sub, 'reaction_counter', 0)) > 0]

            # Sort by reaction count (descending)
            reactors.sort(key=lambda x: x[2], reverse=True)

            # Format the response
            response = (
                "🔥 <b>Reaction Statistics</b>\n\n"
                f"💯 Total reactions: {total_reactions}\n\n"
            )

            # Add top reactors (up to 5)
            if reactors:
                response += "<b>Top Reactors:</b>\n"
                for i, (user_id, name, count) in enumerate(reactors[:5], 1):
                    # Check if it's a channel record
                    if str(user_id).startswith('channel_'):
                        response += f"{i}. 📺 {name}: {count} reactions\n"
                    else:
                        response += f"{i}. 👤 {name}: {count} reactions\n"
            else:
                response += "No reactions recorded yet."

            await message.answer(response)
        except Exception as e:
            logger.error(f"Error in reactions command: {e}")
            await message.answer("❌ Error fetching reaction statistics. Please try again later.")

    @router.message(Command("status"))
    async def cmd_status(message: Message):
        """Handle the /status command."""
        await message.answer(
            "✅ <b>Bot Status</b>\n\n"
            "The bot is running and tracking channel activity.\n\n"
            f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Grist integration: Active"
        )

    @router.message(Command("sync"))
    async def cmd_sync(message: Message):
        """Handle the /sync command to synchronize channel admins into Grist."""
        user_id = message.from_user.id
        chat_id = message.chat.id
        chat_title = getattr(message.chat, 'title', '') or ''
        chat_type = message.chat.type

        try:
            # Check if user is an admin of this chat
            membership = grist_client.get_membership(user_id, chat_id)
            is_admin = membership and _value(membership, 'is_admin', False)

            if not is_admin:
                await message.answer("⛔ This command is only available to channel administrators.")
                return

            await message.answer("🔄 Synchronizing channel admins...")

            # Fetch the chat administrator roster and upsert every non-bot
            # admin into Grist with is_admin=True on their membership.
            admins = await message.bot.get_chat_administrators(chat_id)

            added_count = 0
            updated_count = 0
            skipped_bots = 0

            for admin in admins:
                user = admin.user
                if user.is_bot:
                    skipped_bots += 1
                    continue

                admin_user_id = str(user.id)
                existing = grist_client.get_membership(admin_user_id, chat_id)

                if existing:
                    # Mark as admin; reactivate if previously marked inactive
                    try:
                        grist_client.set_admin(admin_user_id, chat_id, True)
                        logger.info(f"✅ Marked existing member {admin_user_id} as admin")
                    except Exception as e:
                        logger.error(f"❌ Error marking {admin_user_id} as admin: {e}")

                    if _value(existing, 'current_status') != 'active':
                        grist_client.update_subscriber_rejoin(admin_user_id, chat_id,
                                                              _value(existing, 'id'))
                    updated_count += 1
                else:
                    # Add new membership as an active admin
                    user_data = {
                        'user_id': admin_user_id,
                        'username': user.username or '',
                        'first_name': user.first_name or '',
                        'last_name': user.last_name or '',
                        'join_date': datetime.now(),
                        'current_status': 'active',
                        'reaction_counter': 0,
                        'is_admin': True
                    }
                    grist_client.add_subscriber(user_data, chat_id=chat_id,
                                                chat_title=chat_title, chat_type=chat_type)
                    added_count += 1

            logger.info(
                f"Sync completed for chat {chat_id}: {len(admins)} admins, "
                f"{added_count} added, {updated_count} updated, {skipped_bots} bots skipped"
            )
            await message.answer(
                "✅ <b>Channel admin sync complete</b>\n\n"
                f"👑 Admins found: {len(admins)}\n"
                f"➕ Added: {added_count}\n"
                f"🔄 Updated: {updated_count}\n"
                f"🤖 Bots skipped: {skipped_bots}"
            )

        except Exception as e:
            logger.error(f"Error in sync command: {e}")
            await message.answer("❌ Error synchronizing channel data. Please try again later.")

    return router
