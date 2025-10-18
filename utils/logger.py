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

# Optional: File handler (uncomment if you want to log to a file)
file_handler = logging.FileHandler("logs/trade_agent.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)
