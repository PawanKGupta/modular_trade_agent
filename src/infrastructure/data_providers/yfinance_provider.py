"""
YFinance Data Provider

Implements DataProvider interface using yfinance library.
Wraps existing data_fetcher.py functionality.
"""

from datetime import date, datetime

import pandas as pd

# Import existing implementation
import yfinance as yf

from core.data_fetcher import fetch_multi_timeframe_data as legacy_fetch_multi_timeframe
from core.data_fetcher import fetch_ohlcv_yf
from src.infrastructure.db.timezone_utils import is_market_open_window, ist_now
from utils.logger import logger

# Import domain interface
from ...domain.interfaces.data_provider import DataFetchError, DataProvider


class YFinanceProvider(DataProvider):
    """
    YFinance implementation of DataProvider interface

    Wraps existing data_fetcher.py functionality with clean interface.
    """

    def __init__(self):
        """Initialize YFinance provider"""
        logger.debug("YFinanceProvider initialized")
        # Per-ticker cache of today's opening price: {ticker: (date, open_price)}.
        # The session open is immutable, so this avoids repeated yfinance calls
        # when AMO fills are (re)processed during the market-open window.
        self._open_price_cache: dict[str, tuple[date, float]] = {}

    def fetch_daily_data(
        self, ticker: str, days: int = 365, end_date: datetime | None = None
    ) -> pd.DataFrame:
        """
        Fetch daily OHLCV data for a ticker

        Args:
            ticker: Stock symbol
            days: Number of days of historical data
            end_date: End date for data fetch (None = today)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume

        Raises:
            DataFetchError: If data cannot be fetched
        """
        try:
            logger.debug(f"Fetching daily data for {ticker} ({days} days)")

            df = fetch_ohlcv_yf(
                ticker=ticker,
                days=days,
                interval="1d",
                end_date=end_date,
                add_current_day=(end_date is None),
            )

            if df is None or df.empty:
                raise DataFetchError(f"No daily data available for {ticker}")

            return df

        except DataFetchError:
            raise
        except Exception as e:
            error_msg = f"Failed to fetch daily data for {ticker}: {e}"
            logger.error(error_msg)
            raise DataFetchError(error_msg) from e

    def fetch_weekly_data(
        self, ticker: str, weeks: int = 104, end_date: datetime | None = None
    ) -> pd.DataFrame:
        """
        Fetch weekly OHLCV data for a ticker

        Args:
            ticker: Stock symbol
            weeks: Number of weeks of historical data
            end_date: End date for data fetch (None = today)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume

        Raises:
            DataFetchError: If data cannot be fetched
        """
        try:
            logger.debug(f"Fetching weekly data for {ticker} ({weeks} weeks)")

            # Convert weeks to days for yfinance
            days = weeks * 7

            df = fetch_ohlcv_yf(
                ticker=ticker,
                days=days,
                interval="1wk",
                end_date=end_date,
                add_current_day=(end_date is None),
            )

            if df is None or df.empty:
                raise DataFetchError(f"No weekly data available for {ticker}")

            return df

        except DataFetchError:
            raise
        except Exception as e:
            error_msg = f"Failed to fetch weekly data for {ticker}: {e}"
            logger.error(error_msg)
            raise DataFetchError(error_msg) from e

    def fetch_multi_timeframe_data(
        self,
        ticker: str,
        daily_days: int = 365,
        weekly_weeks: int = 104,
        end_date: datetime | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Fetch both daily and weekly data in one call

        Args:
            ticker: Stock symbol
            daily_days: Days of daily data
            weekly_weeks: Weeks of weekly data
            end_date: End date for data fetch

        Returns:
            Tuple of (daily_df, weekly_df)

        Raises:
            DataFetchError: If data cannot be fetched
        """
        try:
            logger.debug(f"Fetching multi-timeframe data for {ticker}")

            result = legacy_fetch_multi_timeframe(
                ticker=ticker, end_date=end_date, add_current_day=(end_date is None)
            )

            if result is None or result.get("daily") is None:
                raise DataFetchError(f"No multi-timeframe data available for {ticker}")

            daily_df = result["daily"]
            weekly_df = result.get("weekly")

            if weekly_df is None or weekly_df.empty:
                raise DataFetchError(f"No weekly data in multi-timeframe fetch for {ticker}")

            return (daily_df, weekly_df)

        except DataFetchError:
            raise
        except Exception as e:
            error_msg = f"Failed to fetch multi-timeframe data for {ticker}: {e}"
            logger.error(error_msg)
            raise DataFetchError(error_msg) from e

    def fetch_current_price(self, ticker: str, at_open: bool = False) -> float | None:
        """
        Fetch current/latest price for a ticker

        Args:
            ticker: Stock symbol
            at_open: Whether to fetch the opening price for AMO orders

        Returns:
            Current price or None if unavailable
        """
        try:
            stock = yf.Ticker(ticker)

            # If we want the open price (during market open window)
            if at_open:
                now = ist_now()
                if is_market_open_window(now):
                    open_price = self._get_open_price(stock, ticker, now)
                    if open_price is not None:
                        return open_price

            info = stock.info
            # Try different price fields
            price = info.get("currentPrice") or info.get("regularMarketPrice")

            return float(price) if price else None

        except Exception as e:
            logger.warning(f"Failed to fetch current price for {ticker}: {e}")
            return None

    def _get_open_price(self, stock: yf.Ticker, ticker: str, now: datetime) -> float | None:
        """Fetch today's open price from 1m history or info, cached per ticker per day.

        The session open is immutable, so a successful lookup is cached to avoid
        repeated yfinance calls when AMO fills are (re)processed within the
        market-open window.
        """
        today = now.date()
        cached = self._open_price_cache.get(ticker)
        if cached is not None and cached[0] == today:
            return cached[1]

        open_price: float | None = None
        try:
            if hasattr(stock, "history"):
                hist = stock.history(period="1d", interval="1m")
                if hist is not None and not hist.empty:
                    # Verify if the latest bar's date is today (IST date)
                    if hist.index[-1].date() == today:
                        open_price = float(hist["Open"].iloc[0])
                        logger.info(f"Using today's 1m open price from history: {open_price}")
        except Exception as e:
            logger.debug(f"Failed to fetch 1m history for open price: {e}")

        if open_price is None:
            try:
                info = stock.info
                raw_open = info.get("regularMarketOpen") or info.get("open")
                if raw_open is not None:
                    open_price = float(raw_open)
                    logger.info(f"Using stock.info open price: {open_price}")
            except Exception as e:
                logger.debug(f"Failed to fetch stock.info for open price: {e}")

        if open_price is not None:
            self._open_price_cache[ticker] = (today, open_price)
        return open_price

    def fetch_fundamental_data(self, ticker: str) -> dict:
        """
        Fetch fundamental data (PE, PB, etc.)

        Args:
            ticker: Stock symbol

        Returns:
            Dictionary with fundamental metrics
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            return {
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
                "market_cap": info.get("marketCap"),
                "dividend_yield": info.get("dividendYield"),
                "beta": info.get("beta"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            }

        except Exception as e:
            logger.warning(f"Failed to fetch fundamental data for {ticker}: {e}")
            return {}

    def is_available(self) -> bool:
        """
        Check if data provider is available/healthy

        Returns:
            True if provider is operational
        """
        try:
            # Try a simple test fetch
            test = yf.Ticker("SPY")
            info = test.info
            return bool(info)
        except Exception:
            return False
