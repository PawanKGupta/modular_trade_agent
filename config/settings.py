import os
from dotenv import load_dotenv

load_dotenv()

# Config constants
LOOKBACK_DAYS = 90
# RELAXED VOLUME REQUIREMENTS (2025-11-09): Reduced from 1.0 to 0.7 for dip-buying strategy
# Oversold conditions often have lower volume (selling pressure), so we allow lower volume requirements
# For RSI < 30 (oversold), volume requirement is further reduced to 0.5x (see volume_analysis.py)
MIN_VOLUME_MULTIPLIER = 0.7  # Relaxed from 1.0 - current volume >= 70% of average
VOLUME_LOOKBACK_DAYS = 50  # Days to average for volume calculation (liquidity assessment)
# Absolute minimum average volume to consider a stock liquid enough (20-day avg)
# Lowered to 10000 (2025-11-09) to allow more stocks to pass liquidity filter
# Actual capital adjustment handled by LiquidityCapitalService
MIN_ABSOLUTE_AVG_VOLUME = int(os.getenv("MIN_ABSOLUTE_AVG_VOLUME", "10000"))

# Position-to-volume ratio limits (based on stock price category)
# Only filters out truly illiquid stocks to avoid missing good opportunities
# Format: (price_threshold, max_ratio)
POSITION_VOLUME_RATIO_TIERS = [
    (5000, 0.02),  # Large caps (>Rs 5000): 2% max
    (1000, 0.05),  # Mid-large caps (Rs 1000-5000): 5% max
    (500, 0.10),  # Mid caps (Rs 500-1000): 10% max
    (0, 0.20),  # Small caps (<Rs 500): 20% max - only filter worst cases
]

# DEPRECATED: Use StrategyConfig.rsi_oversold instead
# This constant is kept for backward compatibility but will be removed in a future version
import warnings
from config.strategy_config import StrategyConfig

_strategy_config = StrategyConfig.default()
RSI_OVERSOLD = _strategy_config.rsi_oversold  # Default: 30.0
RSI_NEAR_OVERSOLD = _strategy_config.rsi_near_oversold  # Default: 40.0


def _warn_deprecated_rsi_constant(name: str):
    """Issue deprecation warning for RSI constants"""
    warnings.warn(
        f"{name} from config.settings is deprecated. "
        f"Use StrategyConfig.{name.lower()} instead. "
        f"This will be removed in a future version.",
        DeprecationWarning,
        stacklevel=3,
    )


# Note: Direct constant access won't trigger warnings automatically
# Importers should migrate to StrategyConfig for new code
# See migration guide in StrategyConfig docstring

VOLUME_MULTIPLIER_FOR_STRONG = 1.2

# Volume analysis configuration
VOLUME_INTRADAY_MULTIPLIER = 0.6  # Lower threshold for intraday analysis
VOLUME_MARKET_CLOSE_HOUR = 15.5  # 3:30 PM IST (Indian market close)
VOLUME_FLEXIBLE_THRESHOLD = 0.4  # Minimum acceptable volume ratio
VOLUME_QUALITY_EXCELLENT = 1.5  # Excellent volume threshold
VOLUME_QUALITY_GOOD = 1.0  # Good volume threshold
VOLUME_QUALITY_FAIR = 0.6  # Fair volume threshold

# News/Sentiment configuration
NEWS_SENTIMENT_ENABLED = os.getenv("NEWS_SENTIMENT_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
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

# Rate Limiting Configuration
# Minimum delay between API calls to prevent rate limiting
# Yahoo Finance typically allows ~2000 requests/hour = ~1 request every 1.8 seconds
# Using 1.0 seconds for more conservative rate limiting (reduces HTTP 401 errors)
# Can be decreased to 0.5s for faster execution if errors are not an issue
API_RATE_LIMIT_DELAY = float(os.getenv("API_RATE_LIMIT_DELAY", "1.0"))  # seconds between API calls

# Concurrency Configuration
# Maximum concurrent API calls/analyses
# Lower values reduce API rate limiting but slower execution
# Higher values faster execution but more API rate limiting risk
# Default: 5 for regular backtesting (balanced), can be increased to 10 for ML training
# For ML training with >3000 stocks, set MAX_CONCURRENT_ANALYSES=10 in .env for faster processing
MAX_CONCURRENT_ANALYSES = int(os.getenv("MAX_CONCURRENT_ANALYSES", "5"))  # concurrent analyses

# Telegram API config (put real tokens in .env)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "xxxxxx")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "xxxx")
