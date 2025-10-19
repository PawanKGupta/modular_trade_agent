import logging
import sys

# Create a logger object
logger = logging.getLogger("TradeAgent")
logger.setLevel(logging.DEBUG)  # Set to DEBUG for full detail, change to INFO or WARNING in prod

# Formatter for logs
formatter = logging.Formatter(
    '%(asctime)s — %(levelname)s — %(module)s — %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)  # Info+ to console
console_handler.setFormatter(formatter)

# Date-based file handler for better log management
from datetime import datetime
import os

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Use date-based log filename
today = datetime.now().strftime('%Y%m%d')
log_filename = f"logs/trade_agent_{today}.log"

file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)
