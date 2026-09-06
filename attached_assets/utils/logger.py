import logging
import sys
from config import LOG_LEVEL

# Configure logging
def setup_logger():
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Create a logger instance
    logger = logging.getLogger("TelegramBot")
    
    return logger

# Create and export logger instance
logger = setup_logger()
