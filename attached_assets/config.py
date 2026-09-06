import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")

# Log level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Admin user IDs (comma-separated list of Telegram user IDs)
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []

# Define reaction emojis to track (can be customized)
TRACKED_REACTIONS = [
    "👍", "👎", "❤️", "🔥", "🎉", "😂", "😢", "😡", "🤔", "👏",
    "🙏", "🤩", "🤯", "💯", "⚡️", "🥰", "🤬", "🤨", "🤢", "🥱"
]
