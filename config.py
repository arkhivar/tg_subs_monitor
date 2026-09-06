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

if not GRIST_API_KEY or not GRIST_DOC_ID:
    raise ValueError("Grist API credentials (GRIST_API_KEY, GRIST_DOC_ID) are not set")

# Webhook configuration (if using webhook mode)
WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST', 'https://tg-grist-tracker.replit.app')
WEBHOOK_PATH = f'/webhook/{TELEGRAM_BOT_TOKEN}'
WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}'

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

# Table name in Grist
SUBSCRIBERS_TABLE = "Table1"

# Bot mode: 'polling' or 'webhook'
BOT_MODE = os.environ.get('BOT_MODE', 'polling')