import os
from dotenv import load_dotenv

load_dotenv()

# Config constants
LOOKBACK_DAYS = 90
MIN_VOLUME_MULTIPLIER = 1.0
VOLUME_LOOKBACK_DAYS = 50  # Days to average for volume calculation (liquidity assessment)

# Position-to-volume ratio limits (based on stock price category)
# Only filters out truly illiquid stocks to avoid missing good opportunities
# Format: (price_threshold, max_ratio)
POSITION_VOLUME_RATIO_TIERS = [
    (5000, 0.02),   # Large caps (>₹5000): 2% max
    (1000, 0.05),   # Mid-large caps (₹1000-5000): 5% max
    (500, 0.10),    # Mid caps (₹500-1000): 10% max
    (0, 0.20)       # Small caps (<₹500): 20% max - only filter worst cases
]

RSI_OVERSOLD = 30
RSI_NEAR_OVERSOLD = 40
VOLUME_MULTIPLIER_FOR_STRONG = 1.2

# Volume analysis configuration
VOLUME_INTRADAY_MULTIPLIER = 0.6  # Lower threshold for intraday analysis
VOLUME_MARKET_CLOSE_HOUR = 15.5   # 3:30 PM IST (Indian market close)
VOLUME_FLEXIBLE_THRESHOLD = 0.4   # Minimum acceptable volume ratio
VOLUME_QUALITY_EXCELLENT = 1.5    # Excellent volume threshold
VOLUME_QUALITY_GOOD = 1.0         # Good volume threshold
VOLUME_QUALITY_FAIR = 0.6         # Fair volume threshold

# News/Sentiment configuration
NEWS_SENTIMENT_ENABLED = os.getenv("NEWS_SENTIMENT_ENABLED", "true").lower() in ("1", "true", "yes", "on")
NEWS_SENTIMENT_LOOKBACK_DAYS = int(os.getenv("NEWS_SENTIMENT_LOOKBACK_DAYS", "30"))
NEWS_SENTIMENT_MIN_ARTICLES = int(os.getenv("NEWS_SENTIMENT_MIN_ARTICLES", "2"))
NEWS_SENTIMENT_POS_THRESHOLD = float(os.getenv("NEWS_SENTIMENT_POS_THRESHOLD", "0.25"))
NEWS_SENTIMENT_NEG_THRESHOLD = float(os.getenv("NEWS_SENTIMENT_NEG_THRESHOLD", "-0.25"))
NEWS_SENTIMENT_CACHE_TTL_SEC = int(os.getenv("NEWS_SENTIMENT_CACHE_TTL_SEC", "900"))  # 15 min

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
