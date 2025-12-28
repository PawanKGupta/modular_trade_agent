"""Helper functions for integrating price cache with price fetching (Phase 0.6)"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from src.infrastructure.persistence.price_cache_repository import PriceCacheRepository

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


def get_price_from_cache_or_fetch(
    db: Session,
    symbol: str,
    target_date: date,
    fetch_func,
    *fetch_args,
    **fetch_kwargs,
) -> float | None:
    """
    Get price from cache or fetch from API if not cached.

    This is a helper function for services that have database access.
    It checks the database cache first, then falls back to the provided fetch function.

    Args:
        db: Database session
        symbol: Symbol to get price for (e.g., 'RELIANCE')
        target_date: Date to get price for
        fetch_func: Function to call if cache miss (should return price or DataFrame)
        *fetch_args: Positional arguments to pass to fetch_func
        **fetch_kwargs: Keyword arguments to pass to fetch_func

    Returns:
        Close price as float, or None if unavailable
    """
    cache_repo = PriceCacheRepository(db)

    # Check cache first
    cached = cache_repo.get(symbol, target_date)
    if cached:
        logger.debug(f"Price cache hit for {symbol} on {target_date}")
        return cached.close

    # Cache miss - fetch from API
    logger.debug(f"Price cache miss for {symbol} on {target_date}, fetching from API")
    try:
        result = fetch_func(*fetch_args, **fetch_kwargs)

        if result is None:
            return None

        # Handle DataFrame result (from yfinance)
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return None

            # Find the row for target_date
            result.index = pd.to_datetime(result.index)
            target_datetime = pd.Timestamp(target_date)

            # Find closest date (exact match or previous trading day)
            matching_rows = result[result.index.date == target_date]
            if not matching_rows.empty:
                row = matching_rows.iloc[-1]
            else:
                # No exact match, use closest previous date
                before_date = result[result.index.date <= target_date]
                if before_date.empty:
                    return None
                row = before_date.iloc[-1]

            # Cache the result
            cache_repo.create_or_update(
                symbol=symbol,
                date=target_date,
                open=float(row.get("Open", row.get("open", 0))) if pd.notna(row.get("Open", row.get("open"))) else None,
                high=float(row.get("High", row.get("high", 0))) if pd.notna(row.get("High", row.get("high"))) else None,
                low=float(row.get("Low", row.get("low", 0))) if pd.notna(row.get("Low", row.get("low"))) else None,
                close=float(row.get("Close", row.get("close", 0))),
                volume=int(row.get("Volume", row.get("volume", 0))) if pd.notna(row.get("Volume", row.get("volume"))) else None,
                source="yfinance",
            )

            return float(row.get("Close", row.get("close", 0)))

        # Handle float result (direct price)
        elif isinstance(result, (int, float)):
            # Cache the result (we only have close price)
            cache_repo.create_or_update(
                symbol=symbol,
                date=target_date,
                close=float(result),
                source="yfinance",
            )
            return float(result)

    except Exception as e:
        logger.error(f"Error fetching price for {symbol} on {target_date}: {e}")
        return None

    return None


def get_prices_from_cache_or_fetch(
    db: Session,
    symbol: str,
    start_date: date,
    end_date: date,
    fetch_func,
    *fetch_args,
    **fetch_kwargs,
) -> pd.DataFrame | None:
    """
    Get prices from cache or fetch from API for a date range.

    This function intelligently combines cached and fetched data:
    - Checks cache for all dates in range
    - Fetches only missing dates from API
    - Combines cached and fetched data into a single DataFrame
    - Caches newly fetched data

    Args:
        db: Database session
        symbol: Symbol to get prices for (e.g., 'RELIANCE')
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        fetch_func: Function to call for missing dates (should return DataFrame)
        *fetch_args: Positional arguments to pass to fetch_func
        **fetch_kwargs: Keyword arguments to pass to fetch_func

    Returns:
        DataFrame with OHLCV data, or None if unavailable
    """
    cache_repo = PriceCacheRepository(db)

    # Get cached prices for the date range
    cached_prices = cache_repo.get_range(symbol, start_date, end_date)
    cached_dates = {cache.date for cache in cached_prices}

    # Find missing dates
    missing_dates = cache_repo.get_missing_dates(symbol, start_date, end_date)

    # If all dates are cached, return cached data
    if not missing_dates:
        logger.debug(f"All prices cached for {symbol} from {start_date} to {end_date}")
        return _cached_prices_to_dataframe(cached_prices)

    # Fetch missing dates from API
    logger.debug(
        f"Fetching {len(missing_dates)} missing dates for {symbol} from {start_date} to {end_date}"
    )

    try:
        # Fetch full range (fetch_func may optimize internally)
        fetched_df = fetch_func(*fetch_args, **fetch_kwargs)

        if fetched_df is None or fetched_df.empty:
            # If fetch fails, return cached data if available
            if cached_prices:
                logger.warning(
                    f"Fetch failed for {symbol}, returning {len(cached_prices)} cached prices"
                )
                return _cached_prices_to_dataframe(cached_prices)
            return None

        # Cache newly fetched data
        fetched_df.index = pd.to_datetime(fetched_df.index)
        for idx, row in fetched_df.iterrows():
            row_date = idx.date() if hasattr(idx, "date") else pd.Timestamp(idx).date()
            if start_date <= row_date <= end_date and row_date not in cached_dates:
                cache_repo.create_or_update(
                    symbol=symbol,
                    date=row_date,
                    open=float(row.get("Open", row.get("open", 0))) if pd.notna(row.get("Open", row.get("open"))) else None,
                    high=float(row.get("High", row.get("high", 0))) if pd.notna(row.get("High", row.get("high"))) else None,
                    low=float(row.get("Low", row.get("low", 0))) if pd.notna(row.get("Low", row.get("low"))) else None,
                    close=float(row.get("Close", row.get("close", 0))),
                    volume=int(row.get("Volume", row.get("volume", 0))) if pd.notna(row.get("Volume", row.get("volume"))) else None,
                    source="yfinance",
                )

        # Combine cached and fetched data
        # Filter fetched data to date range
        fetched_df_filtered = fetched_df[
            (fetched_df.index.date >= start_date) & (fetched_df.index.date <= end_date)
        ]

        # Convert cached prices to DataFrame and combine
        if cached_prices:
            cached_df = _cached_prices_to_dataframe(cached_prices)
            # Combine and deduplicate (cached takes precedence for overlapping dates)
            combined_df = pd.concat([cached_df, fetched_df_filtered])
            combined_df = combined_df[~combined_df.index.duplicated(keep="first")]
            combined_df = combined_df.sort_index()
            return combined_df
        else:
            return fetched_df_filtered

    except Exception as e:
        logger.error(f"Error fetching prices for {symbol} from {start_date} to {end_date}: {e}")
        # Return cached data if available
        if cached_prices:
            logger.warning(
                f"Fetch failed, returning {len(cached_prices)} cached prices"
            )
            return _cached_prices_to_dataframe(cached_prices)
        return None


def _cached_prices_to_dataframe(cached_prices: list) -> pd.DataFrame:
    """Convert list of PriceCache objects to DataFrame"""
    if not cached_prices:
        return pd.DataFrame()

    data = []
    for cache in cached_prices:
        data.append(
            {
                "Open": cache.open,
                "High": cache.high,
                "Low": cache.low,
                "Close": cache.close,
                "Volume": cache.volume,
            }
        )

    df = pd.DataFrame(data)
    df.index = pd.to_datetime([cache.date for cache in cached_prices])
    df = df.sort_index()
    return df

