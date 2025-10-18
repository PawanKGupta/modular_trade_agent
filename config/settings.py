import os
from dotenv import load_dotenv

load_dotenv()

# Config constants
LOOKBACK_DAYS = 90
MIN_VOLUME_MULTIPLIER = 1.0
RSI_OVERSOLD = 30
RSI_NEAR_OVERSOLD = 40
VOLUME_MULTIPLIER_FOR_STRONG = 1.2

# Retry and Circuit Breaker Configuration
RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.0"))
RETRY_MAX_DELAY = float(os.getenv("RETRY_MAX_DELAY", "30.0"))
RETRY_BACKOFF_MULTIPLIER = float(os.getenv("RETRY_BACKOFF_MULTIPLIER", "2.0"))

CIRCUITBREAKER_FAILURE_THRESHOLD = int(os.getenv("CIRCUITBREAKER_FAILURE_THRESHOLD", "3"))
CIRCUITBREAKER_RECOVERY_TIMEOUT = float(os.getenv("CIRCUITBREAKER_RECOVERY_TIMEOUT", "60.0"))

# Telegram API config (put real tokens in .env)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "xxxxxx")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "xxxx")
