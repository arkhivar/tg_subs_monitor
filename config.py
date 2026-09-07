import os
import logging
from typing import List

# Bot configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

# Grist configuration
GRIST_API_KEY = os.environ.get('GRIST_API_KEY')
GRIST_DOC_ID = os.environ.get('GRIST_DOC_ID')

# Grist server base URL. For a self-hosted Grist instance set this to the
# instance URL (e.g. 'https://grist.internal.example.com'). Do NOT append an
# '/api' suffix: the grist-api client (GristDocAPI) builds '/api/docs/...'
# paths itself, so config.py and grist_simple_client.py stay consistent.
GRIST_SERVER = os.environ.get('GRIST_SERVER', 'https://api.getgrist.com')

if not GRIST_API_KEY or not GRIST_DOC_ID:
    raise ValueError("Grist API credentials (GRIST_API_KEY, GRIST_DOC_ID) are not set")

# Webhook configuration (only used when BOT_MODE='webhook')
# WEBHOOK_HOST has no default: webhook mode requires it to be set explicitly.
# WEBHOOK_PATH/WEBHOOK_URL are only built when WEBHOOK_HOST is set, so polling
# mode works without any webhook configuration.
WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST')
WEBHOOK_PATH = f'/webhook/{TELEGRAM_BOT_TOKEN}' if WEBHOOK_HOST else None
WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}' if WEBHOOK_HOST else None

# Server configuration
SERVER_HOST = '0.0.0.0'
SERVER_PORT = int(os.environ.get('PORT', 5000))

# Logging configuration
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
NUMERIC_LOG_LEVEL = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

# Define reaction emojis to track
TRACKED_REACTIONS = [
    "👍", "👎", "❤️", "🔥", "🎉", "😂", "😢", "😡", "🤔", "👏",
    "🙏", "🤩", "🤯", "💯", "⚡️", "🥰", "🤬", "🤨", "🤢", "🥱"
]

# Table names in Grist (API names, not UI display names).
# Users/Chats hold identities; Membership holds per user-per-chat state and
# references both via Ref columns; Events is the append-only timeline and
# references Users/Chats the same way.
USERS_TABLE = os.environ.get('USERS_TABLE', 'Users')
CHATS_TABLE = os.environ.get('CHATS_TABLE', 'Chats')
MEMBERSHIP_TABLE = os.environ.get('MEMBERSHIP_TABLE', 'Membership')

# Events table: append-only timeline with one row per event.
# event_type (Text: join/leave/rejoin/reaction/comment), tg_user (Ref:Users,
# empty for anonymous reactions), chat (Ref:Chats), message_id (Numeric,
# 0 when n/a), reaction (Text - emoji, only for reaction events),
# comment_text (Text - excerpt, only for comments), event_date (Date).
EVENTS_TABLE = os.environ.get('EVENTS_TABLE', 'Events')

# Bot mode: 'polling' or 'webhook'
BOT_MODE = os.environ.get('BOT_MODE', 'polling')
