"""
Main entry point for the Telegram bot application 

This module runs the Flask web application with Aiogram bot in parallel.
"""

import logging
from flask import Flask
from app import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add a route to start the bot
@app.route('/start-bot')
def start_bot():
    """Start the aiogram bot."""
    try:
        # Import and start the Aiogram bot
        from aiogram_extension import start_bot
        start_bot()
        return {'status': 'success', 'message': 'Bot started'}
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        return {'status': 'error', 'message': str(e)}

# Run the Flask app
if __name__ == '__main__':
    # Start the app with the bot
    try:
        # Try to start the bot automatically
        from aiogram_extension import start_bot
        start_bot()
        logger.info("Aiogram bot started successfully")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)