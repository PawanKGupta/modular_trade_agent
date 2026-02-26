import threading
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf

from config.settings import (
    API_RATE_LIMIT_DELAY,
    CIRCUITBREAKER_FAILURE_THRESHOLD,
    CIRCUITBREAKER_RECOVERY_TIMEOUT,
    RETRY_BACKOFF_MULTIPLIER,
    RETRY_BASE_DELAY,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY,
)
from utils.circuit_breaker import CircuitBreaker
from utils.logger import logger
from utils.retry_handler import exponential_backoff_retry

# Shared OHLCV cache across ALL users (paper + broker trading) - market data is public
# Format: {cache_key: (DataFrame, cached_time)}
_shared_ohlcv_cache: dict[str, tuple[pd.DataFrame, datetime]] = {}
_ohlcv_cache_lock = threading.Lock()
_ohlcv_cache_ttl_market_hours = (
    15  # Cache for 15 seconds during market hours (fresh data for exit conditions)
)
_ohlcv_cache_ttl_after_hours = 60  # Cache for 60 seconds after market hours (historical data)
_ohlcv_cache_max_size = 100  # Maximum number of cached entries

# Thread lock for yfinance to prevent concurrent data fetching issues
_yfinance_lock = threading.Lock()

# Shared session for yfinance to reduce 401/Invalid Crumb errors (Yahoo blocks anonymous requests)
# Session is recreated on 401/Invalid Crumb so next request gets fresh cookie/crumb
_yf_session_holder: list = [None]
_yf_session_lock = threading.Lock()

# LOCK ORDER (deadlock prevention): Never hold more than one of these at a time.
# - _rate_limit_lock: only in _enforce_rate_limit(); released before any other lock.
# - _yf_session_lock: only in _get_yfinance_session() / _invalidate_yfinance_session() (currently unused; yfinance uses curl_cffi).
# - _yfinance_lock: only around yf.download(); do not call session helpers while holding it.

# User-Agent that mimics a browser to reduce Yahoo Finance 401/Invalid Crumb rate
_YF_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _get_yfinance_session():
    """Return a shared requests.Session for yfinance with User-Agent. Recreated on 401/crumb."""
    with _yf_session_lock:
        if _yf_session_holder[0] is None:
            s = requests.Session()
            s.headers["User-Agent"] = _YF_USER_AGENT
            _yf_session_holder[0] = s
        return _yf_session_holder[0]


def _invalidate_yfinance_session():
    """Invalidate the shared yfinance session so next call uses a fresh one (fresh cookie/crumb)."""
    with _yf_session_lock:
        if _yf_session_holder[0] is not None:
            try:
                _yf_session_holder[0].close()
            except Exception:
                pass
            _yf_session_holder[0] = None


def _is_yfinance_auth_error(exc: BaseException) -> bool:
    """Return True if exception is Yahoo 401 Unauthorized or Invalid Crumb/Cookie.
    Intentionally narrow (401, invalid crumb/cookie, or response.status_code==401)
    to avoid false positives from other APIs that use 'unauthorized' in messages.
    """
    msg = str(exc).lower()
    if "401" in msg:
        return True
    if "invalid crumb" in msg or "invalid cookie" in msg:
        return True
    if hasattr(exc, "response") and getattr(exc.response, "status_code", None) == 401:
        return True
    return False


# Rate limiting: Track last API call time and enforce minimum delay between calls
# This prevents hitting Yahoo Finance rate limits by spacing out API calls
_last_api_call_time = 0
_rate_limit_lock = threading.Lock()
# Minimum delay between API calls (in seconds) - configurable via API_RATE_LIMIT_DELAY
# Yahoo Finance typically allows ~2000 requests/hour = ~1 request every 1.8 seconds
# Default: 0.5 seconds (can be increased if still hitting rate limits)
MIN_DELAY_BETWEEN_API_CALLS = API_RATE_LIMIT_DELAY


def _enforce_rate_limit(api_type: str = "OHLCV"):
    """
    Enforce rate limiting for Yahoo Finance API calls.

    This function spaces out API calls to prevent hitting rate limits.
    Should be called before making any Yahoo Finance API call.

    Args:
        api_type: Type of API call (for logging purposes)
    """
    global _last_api_call_time
    with _rate_limit_lock:
        current_time = time.time()
        time_since_last_call = current_time - _last_api_call_time
        if time_since_last_call < MIN_DELAY_BETWEEN_API_CALLS:
            delay_needed = MIN_DELAY_BETWEEN_API_CALLS - time_since_last_call
            logger.debug(f"Rate limiting: Waiting {delay_needed:.2f}s before {api_type} API call")
            time.sleep(delay_needed)
        _last_api_call_time = time.time()


# Create circuit breaker for yfinance API with configurable parameters
yfinance_circuit_breaker = CircuitBreaker(
    name="YFinance_API",
    failure_threshold=CIRCUITBREAKER_FAILURE_THRESHOLD,
    recovery_timeout=CIRCUITBREAKER_RECOVERY_TIMEOUT,
)

# Create retry decorator with configurable parameters
api_retry_configured = exponential_backoff_retry(
    max_retries=RETRY_MAX_ATTEMPTS,
    base_delay=RETRY_BASE_DELAY,
    max_delay=RETRY_MAX_DELAY,
    backoff_multiplier=RETRY_BACKOFF_MULTIPLIER,
    jitter=True,
    exceptions=(Exception,),
)


def _get_current_day_data(ticker, session=None):
    """
    Get current day trading data from live ticker info
    Returns dict with current day OHLCV data or None if not available
    session is ignored: yfinance now requires curl_cffi session; we use default (no session).
    """
    try:
        # Do not pass requests.Session - yfinance requires curl_cffi session or None (use its default)
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="2d")  # Get last 2 days to find today's data

        # Check if we have today's data in history
        today = datetime.now().date()
        if not hist.empty and hist.index[-1].date() == today:
            # Use today's data from history
            latest = hist.iloc[-1]
            return {
                "date": today,
                "open": latest["Open"],
                "high": latest["High"],
                "low": latest["Low"],
                "close": latest["Close"],
                "volume": latest["Volume"],
            }

        # Fallback: construct current day data from live info
        current_price = info.get("currentPrice")
        prev_close = info.get("previousClose")
        volume = info.get("volume")

        if current_price and prev_close and volume:
            # Estimate OHLC from available data
            day_high = info.get("dayHigh", current_price)
            day_low = info.get("dayLow", current_price)

            return {
                "date": today,
                "open": prev_close,  # Approximate - actual open not always available
                "high": day_high,
                "low": day_low,
                "close": current_price,
                "volume": volume,
            }

        return None

    except Exception as e:
        logger.debug(f"Error getting current day data for {ticker}: {e}")
        return None


def _append_current_day_data(df, live_data):
    """
    Append current day data to historical dataframe
    """
    try:
        # Create new row with current day data
        new_row = pd.DataFrame(
            [
                {
                    "date": pd.to_datetime(live_data["date"]),
                    "open": live_data["open"],
                    "high": live_data["high"],
                    "low": live_data["low"],
                    "close": live_data["close"],
                    "volume": live_data["volume"],
                }
            ]
        )

        # Append to existing dataframe
        df_updated = pd.concat([df, new_row], ignore_index=True)

        # Sort by date to ensure proper order
        df_updated = df_updated.sort_values("date").reset_index(drop=True)

        return df_updated

    except Exception as e:
        logger.warning(f"Error appending current day data: {e}")
        return df  # Return original df if append fails


@yfinance_circuit_breaker
@api_retry_configured
def fetch_ohlcv_yf(ticker, days=365, interval="1d", end_date=None, add_current_day=True):
    # Determine end date (exclusive in yfinance); include the requested day by adding 1 day
    if end_date is None:
        end = datetime.now()
    else:
        if isinstance(end_date, str):
            end = datetime.strptime(end_date, "%Y-%m-%d")
        elif isinstance(end_date, datetime):
            end = end_date
        else:
            raise ValueError("end_date must be None, str YYYY-MM-DD, or datetime")
        end = end + timedelta(days=1)

    start = end - timedelta(days=days + 5)

    try:
        logger.debug(
            f"Fetching data for {ticker} from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} [{interval}]"
        )

        # Rate limiting: Enforce minimum delay between API calls to prevent rate limiting
        _enforce_rate_limit(api_type=f"OHLCV ({ticker})")

        # Do not pass session= - yfinance requires curl_cffi session or None (use its default)
        max_auth_retries = 2  # Retry once on 401/Invalid Crumb

        for auth_attempt in range(max_auth_retries):
            try:
                # Use lock to prevent concurrent yfinance calls (not thread-safe)
                # NOTE: Using unadjusted prices (auto_adjust=False) to match TradingView
                with _yfinance_lock:
                    df = yf.download(
                        ticker,
                        start=start.strftime("%Y-%m-%d"),
                        end=end.strftime("%Y-%m-%d"),
                        interval=interval,
                        progress=False,
                        auto_adjust=False,
                    )
                break
            except Exception as e:
                # Lock already released (exited "with _yfinance_lock")
                if _is_yfinance_auth_error(e) and auth_attempt < max_auth_retries - 1:
                    logger.warning(
                        "yfinance 401/Invalid Crumb (attempt %s/%s), retrying: %s",
                        auth_attempt + 1,
                        max_auth_retries,
                        e,
                    )
                    time.sleep(2)  # Brief delay before retry
                else:
                    raise

        logger.debug(f"Downloaded data shape for {ticker}: {df.shape}")

        if df is None or df.empty:
            error_msg = f"No data returned from yfinance for {ticker}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Handle multi-index columns properly
        if isinstance(df.columns, pd.MultiIndex):
            # Flatten multi-index columns - take first level
            df.columns = df.columns.get_level_values(0)

        # Ensure we have the required columns
        required_cols = {"Open", "High", "Low", "Close", "Volume"}
        available_cols = set(df.columns)

        if not required_cols.issubset(available_cols):
            error_msg = f"Missing required columns for {ticker}: got {list(available_cols)}, need {list(required_cols)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Select and rename columns
        df = df[["Open", "High", "Low", "Close", "Volume"]].rename(columns=str.lower)

        # Ensure index is datetime and handle timezone properly
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            # Convert timezone-aware to timezone-naive (local time)
            df.index = df.index.tz_convert("UTC").tz_localize(None)

        # Reset index to create date column
        df = df.reset_index()

        # Handle different possible index column names
        if "Date" in df.columns:
            df = df.rename(columns={"Date": "date"})
        elif "index" in df.columns and df["index"].dtype == "datetime64[ns]":
            df = df.rename(columns={"index": "date"})
        elif df.index.name == "Date" or pd.api.types.is_datetime64_any_dtype(df.iloc[:, 0]):
            # If first column looks like dates, rename it
            df = df.rename(columns={df.columns[0]: "date"})
        else:
            error_msg = (
                f"Cannot find date column in dataframe for {ticker}. Columns: {list(df.columns)}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Only add current day data if explicitly requested (avoid data leakage in backtests)
        if add_current_day:
            today_str = datetime.now().strftime("%Y-%m-%d")
            latest_date_str = df["date"].iloc[-1].strftime("%Y-%m-%d")

            if latest_date_str < today_str and interval == "1d":
                logger.debug(
                    f"Historical data for {ticker} is outdated (latest: {latest_date_str}, today: {today_str})"
                )
                try:
                    # Try to get current day data from live ticker
                    live_data = _get_current_day_data(ticker)
                    if live_data is not None:
                        df = _append_current_day_data(df, live_data)
                        logger.debug(f"Added current day data for {ticker} from live ticker")
                except Exception as e:
                    if _is_yfinance_auth_error(e):
                        logger.warning(
                            "yfinance 401/Invalid Crumb when fetching current day data for %s: %s",
                            ticker,
                            e,
                        )
                    else:
                        logger.warning(f"Failed to get current day data for {ticker}: {e}")

        # Additional validation - different requirements for different intervals
        # For dip-buying strategy: Daily is PRIMARY (needs 30 rows for EMA200), Weekly is SECONDARY (flexible)
        # Weekly data is used for trend confirmation, but analysis can proceed with limited weekly data
        min_required_daily = 30  # Daily needs minimum for EMA200 calculation
        min_required_weekly = (
            20  # Weekly: Reduced from 50 to 20 for newer stocks (dip-buying can work with less)
        )

        min_required = min_required_weekly if interval == "1wk" else min_required_daily

        if len(df) < min_required:
            # For weekly data, be more permissive - log warning but don't fail for dip-buying strategy
            if interval == "1wk":
                # Weekly data is optional for dip-buying (daily is primary)
                # Log as INFO instead of WARNING for newer stocks with limited data
                if len(df) >= 10:  # At least 10 weeks (2.5 months) - still useful
                    logger.info(
                        f"Weekly data for {ticker}: {len(df)} rows (minimum recommended: {min_required}, but continuing with available data for dip-buying strategy)"
                    )
                    # Return data even if below minimum - MTF analysis will handle gracefully
                    logger.debug(
                        f"Successfully processed data for {ticker} [{interval}]: {len(df)} rows (below recommended minimum but usable)"
                    )
                    return df
                else:
                    # Very limited weekly data (< 10 weeks) - not useful for analysis
                    error_msg = f"Insufficient weekly data for {ticker}: only {len(df)} rows (minimum: 10 weeks for basic analysis)"
                    logger.warning(error_msg)
                    raise ValueError(error_msg)
            else:
                # Daily data is critical - must have minimum
                error_msg = f"Insufficient data for {ticker} [{interval}]: only {len(df)} rows (need {min_required})"
                logger.warning(error_msg)
                raise ValueError(error_msg)

        logger.debug(f"Successfully processed data for {ticker} [{interval}]: {len(df)} rows")
        return df

    except ValueError as e:
        # Re-raise ValueError for data quality issues
        raise e
    except Exception as e:
        error_msg = f"Unexpected error fetching data for {ticker}: {type(e).__name__}: {e}"
        logger.error(error_msg)
        raise Exception(error_msg) from e


def get_cached_ohlcv(
    ticker: str,
    days: int = 60,
    interval: str = "1d",
    add_current_day: bool = True,
    end_date: str | None = None,
) -> pd.DataFrame | None:
    """
    Get OHLCV data from shared cache or fetch if not available.

    This cache is shared across ALL users (paper + broker trading) since market data is public.
    Reduces redundant API calls when multiple users monitor the same symbol.

    Args:
        ticker: Stock ticker symbol (e.g., 'RELIANCE.NS')
        days: Number of days of data to fetch
        interval: Data interval ('1d', '1wk', etc.) - defaults to '1d'
        add_current_day: Whether to include current day data - defaults to True
        end_date: End date for data (None = today) - defaults to None

    Returns:
        DataFrame with OHLCV data, or None if fetch fails
    """
    from core.volume_analysis import is_market_hours
    from src.infrastructure.db.timezone_utils import ist_now

    # Use IST for consistency with codebase (all trading operations use IST)
    now = ist_now()

    # Determine TTL based on market hours and data type
    # During market hours: shorter TTL for current day data (fresh prices for exit conditions)
    # After market hours: longer TTL (historical data doesn't change)
    # For current day data during market hours: 15 seconds (ensures fresh data for exit checks)
    # For historical data or after hours: 60 seconds (acceptable for non-real-time data)
    if add_current_day and is_market_hours():
        ttl_seconds = _ohlcv_cache_ttl_market_hours  # 15 seconds during market hours
    else:
        ttl_seconds = _ohlcv_cache_ttl_after_hours  # 60 seconds after hours or for historical data

    # Include all parameters in cache key to avoid collisions
    # Format: ticker_days_interval_add_current_day_end_date
    end_date_str = end_date or "today"
    cache_key = f"{ticker}_{days}_{interval}_{add_current_day}_{end_date_str}"

    with _ohlcv_cache_lock:
        # Check cache
        if cache_key in _shared_ohlcv_cache:
            cached_data, cached_time = _shared_ohlcv_cache[cache_key]
            age = (now - cached_time).total_seconds()

            if age < ttl_seconds:
                # Cache hit - return cached data (copy to avoid mutations)
                logger.debug(
                    f"OHLCV cache hit for {ticker} (key: {cache_key[:50]}, age: {age:.1f}s, "
                    f"TTL: {ttl_seconds}s, market_hours: {is_market_hours()})"
                )
                return cached_data.copy()
            else:
                # Cache expired - remove it
                logger.debug(
                    f"OHLCV cache expired for {ticker} (key: {cache_key[:50]}, age: {age:.1f}s, "
                    f"TTL: {ttl_seconds}s, market_hours: {is_market_hours()})"
                )
                del _shared_ohlcv_cache[cache_key]

        # Cache miss or expired - fetch new data
        try:
            logger.debug(
                f"Fetching OHLCV data for {ticker} (days={days}, interval={interval}, "
                f"add_current_day={add_current_day}, end_date={end_date})"
            )
            data = fetch_ohlcv_yf(
                ticker,
                days=days,
                interval=interval,
                add_current_day=add_current_day,
                end_date=end_date,
            )
            if data is not None and not data.empty:
                # Update cache
                _shared_ohlcv_cache[cache_key] = (data.copy(), now)
                logger.debug(
                    f"Cached OHLCV data for {ticker} (key: {cache_key[:50]}, "
                    f"cache size: {len(_shared_ohlcv_cache)})"
                )

                # Cleanup old entries if cache is too large
                if len(_shared_ohlcv_cache) > _ohlcv_cache_max_size:
                    # Remove oldest entries (by cached_time)
                    sorted_entries = sorted(
                        _shared_ohlcv_cache.items(),
                        key=lambda x: x[1][1],  # Sort by cached_time
                    )
                    # Remove oldest entries to bring cache back to max_size
                    to_remove = len(sorted_entries) - _ohlcv_cache_max_size + 10
                    for key, _ in sorted_entries[:to_remove]:
                        del _shared_ohlcv_cache[key]
                    logger.debug(f"Cleaned up {to_remove} old cache entries")

                return data
        except Exception as e:
            logger.debug(f"Failed to fetch OHLCV for {ticker}: {e}")

    return None


def fetch_multi_timeframe_data(ticker, days=800, end_date=None, add_current_day=True, config=None):
    """
    Fetch data for multiple timeframes (daily and weekly) with configurable data fetching strategy

    Args:
        ticker: Stock ticker symbol
        days: Minimum days to fetch (will be adjusted based on config)
        end_date: End date for data fetching (None for current date)
        add_current_day: Whether to add current day data
        config: StrategyConfig instance (uses default if None)

    Returns:
        dict with 'daily' and 'weekly' dataframes
    """
    from config.strategy_config import StrategyConfig

    # Get config if not provided
    if config is None:
        config = StrategyConfig.default()

    try:
        # Configurable data fetching strategy
        daily_max_years = config.data_fetch_daily_max_years  # Default: 5
        weekly_max_years = config.data_fetch_weekly_max_years  # Default: 3

        # Calculate minimum days needed
        daily_min_days = max(800, daily_max_years * 365)  # At least 800 days or max_years
        weekly_min_days = max(20 * 7, weekly_max_years * 365)  # At least 20 weeks or max_years

        # Use the larger of requested days or minimum required, but cap at max_years
        # This prevents excessive data fetching when days parameter is very large
        daily_days = min(max(days, daily_min_days), daily_max_years * 365)
        weekly_days = min(
            max(days * 3, weekly_min_days), weekly_max_years * 365
        )  # Weekly needs more days for same period

        # Fetch daily data first (ensure enough history for EMA200)
        try:
            daily_data = fetch_ohlcv_yf(
                ticker,
                days=daily_days,
                interval="1d",
                end_date=end_date,
                add_current_day=add_current_day,
            )
            logger.debug(
                f"Fetched {len(daily_data)} daily candles for {ticker} (requested: {daily_days} days, max_years: {daily_max_years})"
            )
        except Exception as e:
            logger.warning(f"Failed to fetch daily data for {ticker}: {e}")
            return None

        # Fetch weekly data (need more days for sufficient weekly candles)
        # For dip-buying strategy: Weekly is optional, daily is primary
        # Try to fetch weekly data, but continue with daily-only if weekly fails
        try:
            weekly_data = fetch_ohlcv_yf(
                ticker,
                days=weekly_days,
                interval="1wk",
                end_date=end_date,
                add_current_day=add_current_day,
            )
            logger.debug(
                f"Fetched {len(weekly_data)} weekly candles for {ticker} (requested: {weekly_days} days, max_years: {weekly_max_years})"
            )

            # Validate weekly data quality (but don't fail if below ideal)
            if len(weekly_data) < 20:
                logger.info(
                    f"Weekly data for {ticker}: {len(weekly_data)} rows (below ideal 20, but usable for dip-buying strategy)"
                )
        except ValueError as e:
            # ValueError means insufficient data - check if it's recoverable
            error_str = str(e)
            if "Insufficient weekly data" in error_str:
                # Extract the number of rows from error message if possible
                logger.info(
                    f"Weekly data unavailable for {ticker}: {e} - continuing with daily-only analysis (dip-buying strategy)"
                )
            else:
                logger.info(
                    f"Weekly data insufficient for {ticker}: {e} - continuing with daily-only analysis"
                )
            # Return with daily data only, weekly will be None - MTF analysis will handle gracefully
            return {"daily": daily_data, "weekly": None}
        except Exception as e:
            # Other errors (API issues, etc.) - log and continue with daily-only
            logger.info(
                f"Failed to fetch weekly data for {ticker}: {e} - continuing with daily-only analysis (dip-buying strategy)"
            )
            # Return with daily data only, weekly will be None
            return {"daily": daily_data, "weekly": None}

        return {"daily": daily_data, "weekly": weekly_data}
    except Exception as e:
        logger.error(f"Failed to fetch multi-timeframe data for {ticker}: {e}")
        return None
