"""
Flask Server to Receive Telegram Webhook Updates

This module provides a lightweight Flask server that receives webhook updates
from Telegram and forwards them to our aiogram handler for processing.
This separates the webhook handling from the bot logic.
"""

import os
import logging
import json
import threading
import time
from flask import Flask, request, jsonify
from aiogram import Bot, types
from grist_simple_client import GristSimpleClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Initialize Grist client for database access
db_client = GristSimpleClient()

# Get bot token from environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable is not set")

# Initialize bot for webhook verification
bot = Bot(token=BOT_TOKEN)

# Start aiogram bot in a separate thread
def start_aiogram_polling():
    """Start the aiogram bot in polling mode in a separate thread."""
    import subprocess
    import sys
    
    logger.info("Starting aiogram bot in polling mode...")
    try:
        # Run the bot in a new process
        process = subprocess.Popen([sys.executable, "aiogram_polling.py"], 
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,
                                  universal_newlines=True)
        
        # Log output from the bot process
        for line in process.stdout:
            logger.info(f"Bot: {line.strip()}")
        
        # Wait for process to complete
        process.wait()
        
        logger.warning(f"Bot process exited with code {process.returncode}")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

# Home route for health check
@app.route('/')
def index():
    """Home route for application status."""
    try:
        # Initialize table if needed
        db_client.init_table()
        
        # Get subscriber stats
        subscribers = db_client.get_all_subscribers()
        
        # Count active and inactive subscribers
        active_count = 0
        inactive_count = 0
        total_reactions = 0
        
        for s in subscribers:
            if hasattr(s, 'current_status'):
                if s.current_status == 'active':
                    active_count += 1
                elif s.current_status == 'inactive':
                    inactive_count += 1
                
                if hasattr(s, 'reaction_counter'):
                    total_reactions += s.reaction_counter or 0
            elif isinstance(s, dict):
                if s.get('current_status') == 'active':
                    active_count += 1
                elif s.get('current_status') == 'inactive':
                    inactive_count += 1
                
                total_reactions += s.get('reaction_counter', 0) or 0
        
        # Calculate stats
        display_stats = {
            'active_count': active_count,
            'inactive_count': inactive_count,
            'total_count': len(subscribers),
            'total_reactions': total_reactions
        }
        
        # Return application status
        return jsonify({
            'status': 'online',
            'message': 'Telegram bot is running in polling mode',
            'stats': display_stats,
            'webhook_mode': 'disabled',
            'database': 'connected',
            'database_type': 'Grist',
            'subscriber_count': len(subscribers)
        })
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Run the application
if __name__ == '__main__':
    # Initialize database
    try:
        logger.info("Initializing database...")
        db_client.init_table()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    
    # Start the aiogram bot in a separate thread
    bot_thread = threading.Thread(target=start_aiogram_polling)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Give the bot time to start up
    time.sleep(2)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)