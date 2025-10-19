import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

from utils.logger import logger
from utils.retry_handler import exponential_backoff_retry
from utils.circuit_breaker import CircuitBreaker
from config.settings import (
    RETRY_MAX_ATTEMPTS, RETRY_BASE_DELAY, RETRY_MAX_DELAY, RETRY_BACKOFF_MULTIPLIER,
    CIRCUITBREAKER_FAILURE_THRESHOLD, CIRCUITBREAKER_RECOVERY_TIMEOUT
)

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


@yfinance_circuit_breaker
@api_retry_configured
def fetch_ohlcv_yf(ticker, days=365, interval='1d', end_date=None):
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

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required_cols = {'Open', 'High', 'Low', 'Close', 'Volume'}
        if not required_cols.issubset(df.columns):
            error_msg = f"Missing required columns for {ticker}: got {df.columns.tolist()}, need {list(required_cols)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].rename(columns=str.lower)
        df.index = pd.to_datetime(df.index)
        df = df.reset_index().rename(columns={'index': 'date'})
        
        # Additional validation - different requirements for different intervals
        min_required = 50 if interval == '1wk' else 30  # Weekly needs more history, daily needs 30
        if len(df) < min_required:
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


def fetch_multi_timeframe_data(ticker, days=365, end_date=None):
    """
    Fetch data for multiple timeframes (daily and weekly)
    Returns dict with 'daily' and 'weekly' dataframes
    """
    try:
        # Fetch daily data first
        try:
            daily_data = fetch_ohlcv_yf(ticker, days=days, interval='1d', end_date=end_date)
        except Exception as e:
            logger.warning(f"Failed to fetch daily data for {ticker}: {e}")
            return None
        
        # Fetch weekly data (need more days for sufficient weekly candles)
        try:
            weekly_days = max(days * 3, 1095)  # At least 3 years for weekly analysis
            weekly_data = fetch_ohlcv_yf(ticker, days=weekly_days, interval='1wk', end_date=end_date)
        except Exception as e:
            logger.warning(f"Failed to fetch weekly data for {ticker}: {e}")
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
