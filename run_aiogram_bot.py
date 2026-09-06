"""
Standalone script to run the Aiogram bot in polling mode

This script just runs the Aiogram bot without starting a web server.
"""

import os
import sys
import logging
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run the bot directly."""
    logger.info("Starting the Aiogram bot...")
    
    try:
        # Execute the aiogram_polling.py script directly
        result = subprocess.run([sys.executable, "aiogram_polling.py"], 
                               capture_output=True, text=True)
        
        # Log the output
        for line in result.stdout.splitlines():
            logger.info(f"Bot: {line}")
        
        # Log any errors
        if result.stderr:
            for line in result.stderr.splitlines():
                logger.error(f"Bot error: {line}")
        
        # Check the return code
        if result.returncode != 0:
            logger.error(f"Bot process exited with code {result.returncode}")
        else:
            logger.info("Bot process completed successfully")
    
    except Exception as e:
        logger.error(f"Error running bot: {e}")

if __name__ == "__main__":
    main()