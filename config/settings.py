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

# Composite news: ``composite`` (default) = yfinance + Google RSS + APIs when keys are set.
# Or explicit list: ``yfinance,google_rss,marketaux,newsdata`` (Finnhub is excluded)
NEWS_SOURCES = os.getenv("NEWS_SOURCES", "composite").strip().lower()
NEWS_GOOGLE_RSS_ENABLED = os.getenv("NEWS_GOOGLE_RSS_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# cheap = yfinance + Google RSS; full = also Marketaux / NewsData when keys are set
NEWS_UNIVERSE_PROFILE = os.getenv("NEWS_UNIVERSE_PROFILE", "cheap").strip().lower()
NEWS_LIVE_PROFILE = os.getenv("NEWS_LIVE_PROFILE", "full").strip().lower()
NEWS_BACKTEST_PROFILE = os.getenv("NEWS_BACKTEST_PROFILE", "cheap").strip().lower()
NEWS_ENRICH_FILTERED_NEWS = os.getenv("NEWS_ENRICH_FILTERED_NEWS", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
MARKETAUX_NEWS_LIMIT = int(os.getenv("MARKETAUX_NEWS_LIMIT", "3"))
# Optional provider keys (set in local .env only — never commit)
MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY", "").strip()
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "").strip()

# Headline sentiment backend: auto (try local Transformer on CPU, else lexicon),
# transformer (same as auto), lexicon (word-list only; no torch/transformers).
_NEWS_SB = os.getenv("NEWS_SENTIMENT_BACKEND", "auto").strip().lower()
if _NEWS_SB not in ("auto", "transformer", "lexicon"):
    _NEWS_SB = "auto"
NEWS_SENTIMENT_BACKEND = _NEWS_SB

# Small DistilBERT SST-2 — fast on CPU (Oracle free tier / Ubuntu). Override for e.g. FinBERT.
NEWS_SENTIMENT_TRANSFORMER_MODEL = os.getenv(
    "NEWS_SENTIMENT_TRANSFORMER_MODEL",
    "distilbert-base-uncased-finetuned-sst-2-english",
)
NEWS_SENTIMENT_TRANSFORMER_BATCH_SIZE = int(os.getenv("NEWS_SENTIMENT_TRANSFORMER_BATCH_SIZE", "8"))
NEWS_SENTIMENT_TRANSFORMER_MAX_LENGTH = int(
    os.getenv("NEWS_SENTIMENT_TRANSFORMER_MAX_LENGTH", "128")
)

# Rule-based verdict: downgrade buy/strong_buy → watch only on strong aggregates (VerdictService).
# Score is [-1, 1] from core.news_sentiment; must be <= this threshold (more negative = stricter bar).
NEWS_SENTIMENT_DOWNGRADE_SCORE_THRESHOLD = float(
    os.getenv("NEWS_SENTIMENT_DOWNGRADE_SCORE_THRESHOLD", "-0.52")
)
NEWS_SENTIMENT_DOWNGRADE_MIN_CONFIDENCE = float(
    os.getenv("NEWS_SENTIMENT_DOWNGRADE_MIN_CONFIDENCE", "0.35")
)

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

# Postgres/SQLite OHLCV cache (bulk analysis + integrated backtest)
_db_url_present = bool(os.getenv("DB_URL", "sqlite:///./data/app.db"))
_ohlcv_cache_env = os.getenv("OHLCV_CACHE_ENABLED", "true" if _db_url_present else "false")
OHLCV_CACHE_ENABLED = _ohlcv_cache_env.lower() in ("1", "true", "yes", "on")
OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS = int(
    os.getenv("OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS", "10")
)
OHLCV_CACHE_MIN_COVERAGE_PCT = float(os.getenv("OHLCV_CACHE_MIN_COVERAGE_PCT", "85.0"))
# Reject Yahoo ingest when validation fails (do not upsert corrupt/empty fetches).
OHLCV_REJECT_INVALID_FETCH = os.getenv("OHLCV_REJECT_INVALID_FETCH", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# Minimum daily bars required for indicator-heavy paths (EMA200); partial cache below this warns.
OHLCV_MIN_DAILY_BARS_FOR_INDICATORS = int(os.getenv("OHLCV_MIN_DAILY_BARS_FOR_INDICATORS", "250"))
# Alternative: at least this many years of listing history (trading days / 252).
OHLCV_MIN_LISTING_YEARS_FOR_INDICATORS = float(
    os.getenv("OHLCV_MIN_LISTING_YEARS_FOR_INDICATORS", "1.0")
)
# When true, get_ohlcv returns None for daily fetches that fail bar-count / listing-age gates.
OHLCV_ENFORCE_INDICATOR_MIN_BARS = os.getenv(
    "OHLCV_ENFORCE_INDICATOR_MIN_BARS", "true"
).lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# Listing-window interior gap: refetch once when coverage in [MIN, MAX) and start window has holes.
OHLCV_LISTING_START_GAP_MAX_COVERAGE_PCT = float(
    os.getenv("OHLCV_LISTING_START_GAP_MAX_COVERAGE_PCT", "95.0")
)
OHLCV_LISTING_START_GAP_WINDOW_TRADING_DAYS = int(
    os.getenv("OHLCV_LISTING_START_GAP_WINDOW_TRADING_DAYS", "60")
)
OHLCV_LISTING_START_GAP_MIN_MISSING = int(os.getenv("OHLCV_LISTING_START_GAP_MIN_MISSING", "5"))
CHUNK_DELAY_SECONDS = float(os.getenv("CHUNK_DELAY_SECONDS", "30"))

# Daily OHLCV source for price_cache gap-fill (1d interval): nse | yahoo | nse_with_yahoo_fallback
OHLCV_DAILY_SOURCE = os.getenv("OHLCV_DAILY_SOURCE", "nse").strip().lower()
NSE_BHAVCOPY_CACHE_DIR = os.getenv("NSE_BHAVCOPY_CACHE_DIR", ".cache/nse_bhavcopy")
NSE_BHAVCOPY_REQUEST_DELAY_S = float(os.getenv("NSE_BHAVCOPY_REQUEST_DELAY_S", "0.15"))
NSE_BHAVCOPY_REQUEST_TIMEOUT_S = float(os.getenv("NSE_BHAVCOPY_REQUEST_TIMEOUT_S", "30"))


def daily_ohlcv_uses_nse() -> bool:
    """True when daily gap-fill should use NSE bhavcopy (nse or nse_with_yahoo_fallback)."""
    return OHLCV_DAILY_SOURCE in ("nse", "nse_with_yahoo_fallback")


def daily_ohlcv_yahoo_fallback() -> bool:
    """True when NSE gap-fill may fall back to Yahoo on failure."""
    return OHLCV_DAILY_SOURCE == "nse_with_yahoo_fallback"
