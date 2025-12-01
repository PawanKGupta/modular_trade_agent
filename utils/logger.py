import logging
import sys

# Try to ensure UTF-8 capable stdout to avoid Unicode errors in console
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Create a logger object
logger = logging.getLogger("TradeAgent")
logger.setLevel(logging.DEBUG)  # Set to DEBUG for full detail, change to INFO or WARNING in prod


# Unicode-safe formatter (replaces unsupported chars for the active console encoding)
class UnicodeSafeFormatter(logging.Formatter):
    def format(self, record):
        s = super().format(record)
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            return s.encode(enc, errors="replace").decode(enc, errors="replace")
        except Exception:
            return s


# Formatter for logs
formatter = UnicodeSafeFormatter(
    "%(asctime)s - %(levelname)s - %(module)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)  # Info+ to console
console_handler.setFormatter(formatter)

# Date-based file handler for better log management
from datetime import datetime
import os

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Use date-based log filename
today = datetime.now().strftime("%Y%m%d")
log_filename = f"logs/trade_agent_{today}.log"

# File handler keeps full Unicode (explicit utf-8)
file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
# Use base formatter that preserves characters for file
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(levelname)s - %(module)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
)

logger.addHandler(console_handler)
logger.addHandler(file_handler)
