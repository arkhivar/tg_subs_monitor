"""
Main entry point for the Telegram bot application with Aiogram

This module sets up and starts the Telegram bot using the Aiogram framework.
"""

import os
import logging
from aiohttp import web
from aiogram_bot import start_webhook, init_database, create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Check if webhook URL is available
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    
    if webhook_url:
        logger.info(f"Starting bot with webhook at {webhook_url}")
        # Start the application with webhook
        web.run_app(create_app(), host="0.0.0.0", port=5000)
    else:
        # If no webhook URL is provided, we'll use the existing Flask app
        logger.info("No webhook URL provided, starting Flask app instead")
        # Import the Flask app
        from app import app
        # Initialize database with our new client first
        init_database()
        # Run the Flask app
        app.run(host="0.0.0.0", port=5000, debug=True)