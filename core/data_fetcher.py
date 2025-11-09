import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import threading
import time

from utils.logger import logger
from utils.retry_handler import exponential_backoff_retry
from utils.circuit_breaker import CircuitBreaker
from config.settings import (
    RETRY_MAX_ATTEMPTS, RETRY_BASE_DELAY, RETRY_MAX_DELAY, RETRY_BACKOFF_MULTIPLIER,
    CIRCUITBREAKER_FAILURE_THRESHOLD, CIRCUITBREAKER_RECOVERY_TIMEOUT,
    API_RATE_LIMIT_DELAY
)

# Thread lock for yfinance to prevent concurrent data fetching issues
_yfinance_lock = threading.Lock()

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
    recovery_timeout=CIRCUITBREAKER_RECOVERY_TIMEOUT
)

# Create retry decorator with configurable parameters
api_retry_configured = exponential_backoff_retry(
    max_retries=RETRY_MAX_ATTEMPTS,
    base_delay=RETRY_BASE_DELAY,
    max_delay=RETRY_MAX_DELAY,
    backoff_multiplier=RETRY_BACKOFF_MULTIPLIER,
    jitter=True,
    exceptions=(Exception,)
)

def _get_current_day_data(ticker):
    """
    Get current day trading data from live ticker info
    Returns dict with current day OHLCV data or None if not available
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="2d")  # Get last 2 days to find today's data
        
        # Check if we have today's data in history
        today = datetime.now().date()
        if not hist.empty and hist.index[-1].date() == today:
            # Use today's data from history
            latest = hist.iloc[-1]
            return {
                'date': today,
                'open': latest['Open'],
                'high': latest['High'], 
                'low': latest['Low'],
                'close': latest['Close'],
                'volume': latest['Volume']
            }
        
        # Fallback: construct current day data from live info
        current_price = info.get('currentPrice')
        prev_close = info.get('previousClose')
        volume = info.get('volume')
        
        if current_price and prev_close and volume:
            # Estimate OHLC from available data
            day_high = info.get('dayHigh', current_price)
            day_low = info.get('dayLow', current_price)
            
            return {
                'date': today,
                'open': prev_close,  # Approximate - actual open not always available
                'high': day_high,
                'low': day_low,
                'close': current_price,
                'volume': volume
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
        new_row = pd.DataFrame([{
            'date': pd.to_datetime(live_data['date']),
            'open': live_data['open'],
            'high': live_data['high'],
            'low': live_data['low'], 
            'close': live_data['close'],
            'volume': live_data['volume']
        }])
        
        # Append to existing dataframe
        df_updated = pd.concat([df, new_row], ignore_index=True)
        
        # Sort by date to ensure proper order
        df_updated = df_updated.sort_values('date').reset_index(drop=True)
        
        return df_updated
        
    except Exception as e:
        logger.warning(f"Error appending current day data: {e}")
        return df  # Return original df if append fails


@yfinance_circuit_breaker
@api_retry_configured
def fetch_ohlcv_yf(ticker, days=365, interval='1d', end_date=None, add_current_day=True):
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
        logger.debug(f"Fetching data for {ticker} from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} [{interval}]")
        
        # Rate limiting: Enforce minimum delay between API calls to prevent rate limiting
        _enforce_rate_limit(api_type=f"OHLCV ({ticker})")
        
        # Use lock to prevent concurrent yfinance calls (not thread-safe)
        with _yfinance_lock:
            df = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval=interval,
                progress=False,
                auto_adjust=True
            )
        
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
        required_cols = {'Open', 'High', 'Low', 'Close', 'Volume'}
        available_cols = set(df.columns)
        
        if not required_cols.issubset(available_cols):
            error_msg = f"Missing required columns for {ticker}: got {list(available_cols)}, need {list(required_cols)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Select and rename columns
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].rename(columns=str.lower)
        
        # Ensure index is datetime and handle timezone properly
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            # Convert timezone-aware to timezone-naive (local time)
            df.index = df.index.tz_convert('UTC').tz_localize(None)
        
        # Reset index to create date column
        df = df.reset_index()
        
        # Handle different possible index column names
        if 'Date' in df.columns:
            df = df.rename(columns={'Date': 'date'})
        elif 'index' in df.columns and df['index'].dtype == 'datetime64[ns]':
            df = df.rename(columns={'index': 'date'})
        elif df.index.name == 'Date' or pd.api.types.is_datetime64_any_dtype(df.iloc[:, 0]):
            # If first column looks like dates, rename it
            df = df.rename(columns={df.columns[0]: 'date'})
        else:
            error_msg = f"Cannot find date column in dataframe for {ticker}. Columns: {list(df.columns)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Only add current day data if explicitly requested (avoid data leakage in backtests)
        if add_current_day:
            today_str = datetime.now().strftime('%Y-%m-%d')
            latest_date_str = df['date'].iloc[-1].strftime('%Y-%m-%d')
            
            if latest_date_str < today_str and interval == '1d':
                logger.debug(f"Historical data for {ticker} is outdated (latest: {latest_date_str}, today: {today_str})")
                try:
                    # Try to get current day data from live ticker
                    live_data = _get_current_day_data(ticker)
                    if live_data is not None:
                        df = _append_current_day_data(df, live_data)
                        logger.debug(f"Added current day data for {ticker} from live ticker")
                except Exception as e:
                    logger.warning(f"Failed to get current day data for {ticker}: {e}")
        
        # Additional validation - different requirements for different intervals
        # For dip-buying strategy: Daily is PRIMARY (needs 30 rows for EMA200), Weekly is SECONDARY (flexible)
        # Weekly data is used for trend confirmation, but analysis can proceed with limited weekly data
        min_required_daily = 30  # Daily needs minimum for EMA200 calculation
        min_required_weekly = 20  # Weekly: Reduced from 50 to 20 for newer stocks (dip-buying can work with less)
        
        min_required = min_required_weekly if interval == '1wk' else min_required_daily
        
        if len(df) < min_required:
            # For weekly data, be more permissive - log warning but don't fail for dip-buying strategy
            if interval == '1wk':
                # Weekly data is optional for dip-buying (daily is primary)
                # Log as INFO instead of WARNING for newer stocks with limited data
                if len(df) >= 10:  # At least 10 weeks (2.5 months) - still useful
                    logger.info(f"Weekly data for {ticker}: {len(df)} rows (minimum recommended: {min_required}, but continuing with available data for dip-buying strategy)")
                    # Return data even if below minimum - MTF analysis will handle gracefully
                    logger.debug(f"Successfully processed data for {ticker} [{interval}]: {len(df)} rows (below recommended minimum but usable)")
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
        weekly_days = min(max(days * 3, weekly_min_days), weekly_max_years * 365)  # Weekly needs more days for same period
        
        # Fetch daily data first (ensure enough history for EMA200)
        try:
            daily_data = fetch_ohlcv_yf(ticker, days=daily_days, interval='1d', end_date=end_date, add_current_day=add_current_day)
            logger.debug(f"Fetched {len(daily_data)} daily candles for {ticker} (requested: {daily_days} days, max_years: {daily_max_years})")
        except Exception as e:
            logger.warning(f"Failed to fetch daily data for {ticker}: {e}")
            return None
        
        # Fetch weekly data (need more days for sufficient weekly candles)
        # For dip-buying strategy: Weekly is optional, daily is primary
        # Try to fetch weekly data, but continue with daily-only if weekly fails
        try:
            weekly_data = fetch_ohlcv_yf(ticker, days=weekly_days, interval='1wk', end_date=end_date, add_current_day=add_current_day)
            logger.debug(f"Fetched {len(weekly_data)} weekly candles for {ticker} (requested: {weekly_days} days, max_years: {weekly_max_years})")
            
            # Validate weekly data quality (but don't fail if below ideal)
            if len(weekly_data) < 20:
                logger.info(f"Weekly data for {ticker}: {len(weekly_data)} rows (below ideal 20, but usable for dip-buying strategy)")
        except ValueError as e:
            # ValueError means insufficient data - check if it's recoverable
            error_str = str(e)
            if 'Insufficient weekly data' in error_str:
                # Extract the number of rows from error message if possible
                logger.info(f"Weekly data unavailable for {ticker}: {e} - continuing with daily-only analysis (dip-buying strategy)")
            else:
                logger.info(f"Weekly data insufficient for {ticker}: {e} - continuing with daily-only analysis")
            # Return with daily data only, weekly will be None - MTF analysis will handle gracefully
            return {
                'daily': daily_data,
                'weekly': None
            }
        except Exception as e:
            # Other errors (API issues, etc.) - log and continue with daily-only
            logger.info(f"Failed to fetch weekly data for {ticker}: {e} - continuing with daily-only analysis (dip-buying strategy)")
            # Return with daily data only, weekly will be None
            return {
                'daily': daily_data,
                'weekly': None
            }
        
        return {
            'daily': daily_data,
            'weekly': weekly_data
        }
    except Exception as e:
        logger.error(f"Failed to fetch multi-timeframe data for {ticker}: {e}")
        return None
