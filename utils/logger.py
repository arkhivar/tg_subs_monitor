import logging
import sys
from config import NUMERIC_LOG_LEVEL

# Configure the logger
logging.basicConfig(
    level=NUMERIC_LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create a logger instance
logger = logging.getLogger('tg_grist_bot')

# Export the logger
__all__ = ['logger']