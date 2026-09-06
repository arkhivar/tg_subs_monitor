"""
Main entry point for the hybrid Telegram bot application

This module runs both the Flask server for API endpoints and the Aiogram
bot in polling mode for reliable event handling.
"""

import os
import sys
import logging
import threading
import time
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def start_flask_server():
    """Start the Flask server in a subprocess."""
    logger.info("Starting Flask server...")
    try:
        # Run Flask server in a separate process
        process = subprocess.Popen([sys.executable, "flask_webhook_server.py"],
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.STDOUT,
                                  universal_newlines=True)
        
        # Log output from the Flask process
        for line in process.stdout:
            logger.info(f"Flask: {line.strip()}")
        
        # Wait for process to complete
        process.wait()
        
        logger.warning(f"Flask server exited with code {process.returncode}")
    except Exception as e:
        logger.error(f"Error starting Flask server: {e}")

def start_aiogram_bot():
    """Start the Aiogram bot in a subprocess."""
    logger.info("Starting Aiogram bot...")
    try:
        # Run Aiogram bot in a separate process
        process = subprocess.Popen([sys.executable, "aiogram_polling.py"],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, 
                                  universal_newlines=True)
        
        # Log output from the bot process
        for line in process.stdout:
            logger.info(f"Bot: {line.strip()}")
        
        # Wait for process to complete
        process.wait()
        
        logger.warning(f"Bot exited with code {process.returncode}")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

# Main entry point
if __name__ == "__main__":
    logger.info("Starting Telegram bot application...")
    
    # Start Flask server in a thread
    flask_thread = threading.Thread(target=start_flask_server)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Wait a moment for Flask to start
    time.sleep(2)
    
    # Start Aiogram bot in the main thread
    start_aiogram_bot()