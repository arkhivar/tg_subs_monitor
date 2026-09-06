"""
Telegram Bot Worker Module

This module provides functions to work with the Telegram bot.
Instead of running in a thread, we'll use a more robust approach by setting up
a webhook handler and processing updates via HTTP requests.
"""

import os
import logging
import sys
import multiprocessing
import signal
import time
from multiprocessing import Process

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global process object
bot_process = None

def run_bot_process():
    """Function to run the bot in a separate process."""
    try:
        logger.info("Starting Telegram bot in separate process...")
        
        # Import here to avoid circular imports
        from telegram_bot import start_polling
        
        # Run the bot polling in this process
        logger.info("Starting polling...")
        start_polling()
        
    except Exception as e:
        logger.error(f"Error in bot process: {e}", exc_info=True)
        
def start_bot_process():
    """Start the Telegram bot in a separate process if not already running."""
    global bot_process
    
    if bot_process and bot_process.is_alive():
        logger.info(f"Bot process already running with PID: {bot_process.pid}")
        return
    
    logger.info("Starting new bot process...")
    
    # Create and start a new process
    bot_process = Process(target=run_bot_process)
    bot_process.daemon = True  # Process will exit when main process exits
    bot_process.start()
    
    # Give the process a moment to initialize
    time.sleep(2)
    
    if bot_process.is_alive():
        logger.info(f"Bot process started successfully with PID: {bot_process.pid}")
    else:
        logger.error("Bot process failed to start")

# Make sure we clean up the process on shutdown
def cleanup():
    global bot_process
    if bot_process and bot_process.is_alive():
        logger.info(f"Terminating bot process (PID: {bot_process.pid})...")
        bot_process.terminate()
        bot_process.join(timeout=5)
        logger.info("Bot process terminated")

# Register signal handlers for cleanup
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(sig, lambda signum, frame: cleanup())

# Start the bot process when this module is imported
start_bot_process()