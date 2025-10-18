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
def fetch_ohlcv_yf(ticker, days=365):
    end = datetime.now()
    start = end - timedelta(days=days + 5)

    try:
        logger.debug(f"Fetching data for {ticker} from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
        
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
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
        
        # Additional validation
        if len(df) < 20:  # Need at least 20 days for indicators
            error_msg = f"Insufficient data for {ticker}: only {len(df)} rows"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        
        logger.debug(f"Successfully processed data for {ticker}: {len(df)} rows")
        return df

    except ValueError as e:
        # Re-raise ValueError for data quality issues
        raise e
    except Exception as e:
        error_msg = f"Unexpected error fetching data for {ticker}: {type(e).__name__}: {e}"
        logger.error(error_msg)
        raise Exception(error_msg) from e
