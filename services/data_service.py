"""
Data Service

Handles data fetching and preparation for stock analysis.
Extracted from core/analysis.py to improve modularity and testability.

Phase 4: Updated to support infrastructure layer with backward compatibility.
"""

from typing import Any

import pandas as pd

from utils.logger import logger

# Phase 4: Support both core.* (backward compatible) and infrastructure
try:
    # Try importing infrastructure first (new way)
    from src.infrastructure.data_providers.yfinance_provider import YFinanceProvider

    _INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    _INFRASTRUCTURE_AVAILABLE = False
    YFinanceProvider = None

# Always import core.* functions for fallback (needed even when infrastructure is available)
try:
    from core.data_fetcher import fetch_multi_timeframe_data, fetch_ohlcv_yf
except ImportError:
    # If core.* is not available, we'll handle it in the methods
    fetch_ohlcv_yf = None
    fetch_multi_timeframe_data = None


class DataService:
    """
    Service for fetching and preparing market data

    Phase 4: Supports dependency injection - can use infrastructure layer
    or fall back to core.* modules for backward compatibility.
    """

    def __init__(self, data_provider=None, ohlcv_cache=None):
        """
        Initialize data service

        Args:
            data_provider: Optional data provider instance (if None, uses default)
            ohlcv_cache: Optional OhlcvCacheService (Postgres-backed OHLCV cache)
        """
        self.ohlcv_cache = ohlcv_cache
        # Phase 4: Use infrastructure if available, otherwise use core.*
        if data_provider is not None:
            self.data_provider = data_provider
        elif _INFRASTRUCTURE_AVAILABLE and YFinanceProvider is not None:
            self.data_provider = YFinanceProvider()
            self._use_infrastructure = True
        else:
            self.data_provider = None
            self._use_infrastructure = False

    def _fetch_via_cache_or_yahoo(
        self,
        ticker: str,
        *,
        days: int = 365,
        interval: str = "1d",
        end_date: str | None = None,
        add_current_day: bool = True,
    ) -> pd.DataFrame | None:
        """Use injected cache service when present, else fetch_ohlcv_yf."""
        if self.ohlcv_cache is not None:
            return self.ohlcv_cache.get_ohlcv(
                ticker,
                days=days,
                interval=interval,
                end_date=end_date,
                add_current_day=add_current_day,
            )
        if fetch_ohlcv_yf is None:
            return None
        return fetch_ohlcv_yf(
            ticker,
            days=days,
            interval=interval,
            end_date=end_date,
            add_current_day=add_current_day,
        )

    def fetch_single_timeframe(
        self, ticker: str, end_date: str | None = None, add_current_day: bool = True
    ) -> pd.DataFrame | None:
        """
        Fetch single timeframe (daily) data for a ticker

        Args:
            ticker: Stock ticker symbol
            end_date: End date for data (YYYY-MM-DD format)
            add_current_day: Whether to include current day data

        Returns:
            DataFrame with OHLCV data or None if fetch fails
        """
        try:
            # Phase 4: Use infrastructure if available
            # Note: Infrastructure still depends on core.*, so we use core.* for now
            # TODO Phase 4: Once infrastructure is independent, fully migrate to it
            if self._use_infrastructure and self.data_provider:
                try:
                    from datetime import datetime as dt

                    end_dt = None
                    if end_date:
                        end_dt = dt.strptime(end_date, "%Y-%m-%d")

                    df = self.data_provider.fetch_daily_data(
                        ticker=ticker, days=365, end_date=end_dt
                    )
                except Exception as e:
                    # Fallback to core.* if infrastructure fails
                    logger.debug(f"Infrastructure provider failed, using core.*: {e}")
                    if fetch_ohlcv_yf is None:
                        raise ImportError(
                            "Neither infrastructure provider nor core.data_fetcher.fetch_ohlcv_yf is available"
                        )
                    df = self._fetch_via_cache_or_yahoo(
                        ticker, end_date=end_date, add_current_day=add_current_day
                    )
            else:
                # Fallback to core.* for backward compatibility
                if fetch_ohlcv_yf is None and self.ohlcv_cache is None:
                    raise ImportError("core.data_fetcher.fetch_ohlcv_yf is not available")
                df = self._fetch_via_cache_or_yahoo(
                    ticker, end_date=end_date, add_current_day=add_current_day
                )

            if df is None or df.empty:
                logger.warning(f"No data available for {ticker}")
                return None
            return df
        except Exception as e:
            logger.error(f"Data fetching failed for {ticker}: {e}")
            return None

    def fetch_multi_timeframe(
        self,
        ticker: str,
        end_date: str | None = None,
        add_current_day: bool = True,
        config: Any | None = None,
    ) -> dict[str, pd.DataFrame] | None:
        """
        Fetch multi-timeframe (daily + weekly) data for a ticker

        Args:
            ticker: Stock ticker symbol
            end_date: End date for data (YYYY-MM-DD format)
            add_current_day: Whether to include current day data

        Returns:
            Dict with 'daily' and 'weekly' DataFrames or None if fetch fails
        """
        try:
            # Phase 4: Use infrastructure if available
            # Note: Infrastructure still depends on core.*, so we use core.* for now
            # TODO Phase 4: Once infrastructure is independent, fully migrate to it
            if self._use_infrastructure and self.data_provider:
                try:
                    from datetime import datetime as dt

                    end_dt = None
                    if end_date:
                        end_dt = dt.strptime(end_date, "%Y-%m-%d")

                    daily_df, weekly_df = self.data_provider.fetch_multi_timeframe_data(
                        ticker=ticker, daily_days=365, weekly_weeks=104, end_date=end_dt
                    )
                    multi_data = {"daily": daily_df, "weekly": weekly_df}
                except Exception as e:
                    # Fallback to core.* if infrastructure fails
                    logger.debug(f"Infrastructure provider failed, using core.*: {e}")
                    if fetch_multi_timeframe_data is None:
                        raise ImportError(
                            "Neither infrastructure provider nor core.data_fetcher.fetch_multi_timeframe_data is available"
                        )
                    multi_data = fetch_multi_timeframe_data(
                        ticker, end_date=end_date, add_current_day=add_current_day, config=config
                    )
            else:
                # Fallback to core.* for backward compatibility
                if fetch_multi_timeframe_data is None:
                    raise ImportError(
                        "core.data_fetcher.fetch_multi_timeframe_data is not available"
                    )
                multi_data = fetch_multi_timeframe_data(
                    ticker, end_date=end_date, add_current_day=add_current_day, config=config
                )

            if multi_data is None or multi_data.get("daily") is None:
                logger.warning(f"No multi-timeframe data available for {ticker}")
                return None
            return multi_data
        except Exception as e:
            logger.error(f"Multi-timeframe data fetching failed for {ticker}: {e}")
            return None

    def clip_to_date(self, df: pd.DataFrame, as_of_date: str | None) -> pd.DataFrame:
        """
        Clip DataFrame to exclude data after as_of_date

        Args:
            df: DataFrame to clip
            as_of_date: Date to clip to (YYYY-MM-DD format)

        Returns:
            Clipped DataFrame
        """
        if as_of_date is None:
            return df

        try:
            asof_ts = pd.to_datetime(as_of_date)
            if "date" in df.columns:
                df = df[df["date"] <= asof_ts]
            else:
                df = df.loc[df.index <= asof_ts]
        except Exception as e:
            logger.warning(f"Error clipping data to date {as_of_date}: {e}")

        return df

    def get_latest_row(self, df: pd.DataFrame) -> pd.Series | None:
        """
        Get the latest row from DataFrame

        Args:
            df: DataFrame to get row from

        Returns:
            Latest row as Series or None if empty
        """
        try:
            if df is None or df.empty:
                return None
            return df.iloc[-1]
        except (IndexError, KeyError) as e:
            logger.error(f"Error accessing latest row: {e}")
            return None

    def get_previous_row(self, df: pd.DataFrame) -> pd.Series | None:
        """
        Get the previous row from DataFrame

        Args:
            df: DataFrame to get row from

        Returns:
            Previous row as Series or None if not available
        """
        try:
            if df is None or len(df) < 2:
                return None
            return df.iloc[-2]
        except (IndexError, KeyError) as e:
            logger.error(f"Error accessing previous row: {e}")
            return None

    def get_recent_extremes(self, df: pd.DataFrame, lookback: int = 20) -> dict[str, float]:
        """
        Get recent high and low prices

        Args:
            df: DataFrame with price data
            lookback: Number of days to look back

        Returns:
            Dict with 'high' and 'low' values
        """
        try:
            recent_high = df["high"].tail(lookback).max()
            recent_low = df["low"].tail(lookback).min()
            return {"high": float(recent_high), "low": float(recent_low)}
        except Exception as e:
            logger.warning(f"Error getting recent extremes: {e}")
            return {"high": 0.0, "low": 0.0}
