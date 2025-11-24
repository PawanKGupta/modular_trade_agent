"""
Price Service

Unified service for fetching stock prices from multiple sources.
Consolidates price fetching logic from across the codebase.

Features:
- Historical price data (yfinance)
- Real-time LTP (WebSocket/LivePriceManager)
- Automatic fallback mechanisms
- Caching layer to reduce API calls
- Subscription management
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd  # noqa: E402

from core.data_fetcher import fetch_ohlcv_yf  # noqa: E402
from modules.kotak_neo_auto_trader.utils.price_manager_utils import (  # noqa: E402
    get_ltp_from_manager,
)
from modules.kotak_neo_auto_trader.utils.symbol_utils import (  # noqa: E402
    extract_ticker_base,
    get_lookup_symbol,
)
from utils.logger import logger  # noqa: E402


class PriceCache:
    """Simple in-memory cache for price data with TTL"""

    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}
        self._realtime_cache: dict[str, dict[str, Any]] = {}

    def get_historical(self, key: str, ttl_seconds: int = 300) -> pd.DataFrame | None:
        """Get cached historical data if not expired"""
        if key in self._cache:
            entry = self._cache[key]
            age = (datetime.now() - entry["timestamp"]).total_seconds()
            if age < ttl_seconds:
                logger.debug(f"Cache hit for historical price: {key} (age: {age:.1f}s)")
                return entry["data"]
            else:
                # Expired, remove from cache
                del self._cache[key]
        return None

    def set_historical(self, key: str, data: pd.DataFrame):
        """Cache historical data"""
        self._cache[key] = {
            "data": data,
            "timestamp": datetime.now(),
        }

    def get_realtime(self, key: str, ttl_seconds: int = 30) -> float | None:
        """Get cached real-time price if not expired"""
        if key in self._realtime_cache:
            entry = self._realtime_cache[key]
            age = (datetime.now() - entry["timestamp"]).total_seconds()
            if age < ttl_seconds:
                logger.debug(f"Cache hit for real-time price: {key} (age: {age:.1f}s)")
                return entry["price"]
            else:
                # Expired, remove from cache
                del self._realtime_cache[key]
        return None

    def set_realtime(self, key: str, price: float):
        """Cache real-time price"""
        self._realtime_cache[key] = {
            "price": price,
            "timestamp": datetime.now(),
        }

    def clear(self):
        """Clear all cached data"""
        self._cache.clear()
        self._realtime_cache.clear()


class PriceService:
    """
    Unified service for fetching stock prices.

    This service consolidates price fetching logic from across the codebase,
    providing a single interface for both historical and real-time prices.
    """

    def __init__(
        self,
        live_price_manager=None,
        enable_caching: bool = True,
        historical_cache_ttl: int = 300,  # 5 minutes for historical
        realtime_cache_ttl: int = 30,  # 30 seconds for real-time
    ):
        """
        Initialize PriceService.

        Args:
            live_price_manager: Optional LivePriceManager or LivePriceCache instance
            enable_caching: Enable price caching (default: True)
            historical_cache_ttl: Cache TTL for historical data in seconds (default: 300)
            realtime_cache_ttl: Cache TTL for real-time data in seconds (default: 30)
        """
        self.live_price_manager = live_price_manager
        self.enable_caching = enable_caching
        self.historical_cache_ttl = historical_cache_ttl
        self.realtime_cache_ttl = realtime_cache_ttl
        self._cache = PriceCache() if enable_caching else None

        logger.debug(
            f"PriceService initialized (caching: {enable_caching}, "
            f"historical_ttl: {historical_cache_ttl}s, realtime_ttl: {realtime_cache_ttl}s)"
        )

    def get_price(
        self,
        ticker: str,
        days: int = 365,
        interval: str = "1d",
        end_date: str | None = None,
        add_current_day: bool = True,
    ) -> pd.DataFrame | None:
        """
        Get historical OHLCV data for a ticker.

        This method wraps fetch_ohlcv_yf() with caching support.
        Maintains exact same behavior as direct fetch_ohlcv_yf() calls.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            days: Number of days of historical data (default: 365)
            interval: Data interval ('1d', '1wk', '1m', etc.) (default: '1d')
            end_date: End date in 'YYYY-MM-DD' format or None for current date
            add_current_day: Whether to add current day data (default: True)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
            Returns None if data cannot be fetched

        Example:
            >>> service = PriceService()
            >>> df = service.get_price('RELIANCE.NS', days=30)
            >>> print(df.head())
        """
        # Create cache key
        cache_key = f"{ticker}_{days}_{interval}_{end_date}_{add_current_day}"

        # Check cache first
        if self._cache:
            cached_data = self._cache.get_historical(cache_key, self.historical_cache_ttl)
            if cached_data is not None:
                return cached_data.copy()

        # Fetch from yfinance (same as original fetch_ohlcv_yf call)
        try:
            df = fetch_ohlcv_yf(
                ticker=ticker,
                days=days,
                interval=interval,
                end_date=end_date,
                add_current_day=add_current_day,
            )

            # Cache the result
            if self._cache and df is not None:
                self._cache.set_historical(cache_key, df)

            return df

        except Exception as e:
            logger.error(f"Failed to fetch historical price data for {ticker}: {e}")
            return None

    def get_realtime_price(
        self,
        symbol: str,
        ticker: str | None = None,
        broker_symbol: str | None = None,
    ) -> float | None:
        """
        Get real-time Last Traded Price (LTP) for a symbol.

        Priority:
        1. LivePriceManager/LivePriceCache (WebSocket) if available
        2. yfinance fallback (delayed ~15-20 min)

        This method maintains exact same behavior as existing get_current_ltp() methods.

        Args:
            symbol: Base symbol name (e.g., 'RELIANCE')
            ticker: Yahoo Finance ticker (e.g., 'RELIANCE.NS') - used for fallback
            broker_symbol: Broker symbol (e.g., 'RELIANCE-EQ') - used for WebSocket lookup

        Returns:
            Current LTP as float, or None if unavailable

        Example:
            >>> service = PriceService(live_price_manager=price_mgr)
            >>> ltp = service.get_realtime_price('RELIANCE', 'RELIANCE.NS', 'RELIANCE-EQ')
            >>> print(f"Current price: Rs {ltp}")
        """
        # Create cache key
        cache_key = f"{symbol}_{ticker}_{broker_symbol}"

        # Check cache first
        if self._cache:
            cached_price = self._cache.get_realtime(cache_key, self.realtime_cache_ttl)
            if cached_price is not None:
                return cached_price

        # Try LivePriceManager/LivePriceCache first (real-time WebSocket prices)
        if self.live_price_manager:
            try:
                # Extract base symbol if needed
                if not symbol and ticker:
                    symbol = extract_ticker_base(ticker)

                # Get appropriate lookup symbol
                # (prioritize broker_symbol for correct instrument token)
                lookup_symbol = get_lookup_symbol(broker_symbol, symbol)

                # Use utility function to handle different price manager interfaces
                ltp = get_ltp_from_manager(self.live_price_manager, lookup_symbol, ticker)

                if ltp is not None and ltp > 0:
                    logger.debug(f"{symbol} LTP from WebSocket: Rs {ltp:.2f}")

                    # Cache the result
                    if self._cache:
                        self._cache.set_realtime(cache_key, ltp)

                    return ltp
            except Exception as e:
                logger.debug(f"WebSocket LTP failed for {symbol}: {e}")

        # Fallback to yfinance (delayed ~15-20 min)
        if ticker:
            try:
                # Use 1-minute interval for most recent price
                df = fetch_ohlcv_yf(ticker, days=1, interval="1m", add_current_day=True)

                if df is None or df.empty:
                    logger.warning(f"No LTP data for {ticker} from yfinance")
                    return None

                ltp = float(df["close"].iloc[-1])
                logger.debug(f"{symbol} LTP from yfinance (delayed ~15min): Rs {ltp:.2f}")

                # Cache the result
                if self._cache:
                    self._cache.set_realtime(cache_key, ltp)

                return ltp

            except Exception as e:
                logger.error(f"Error fetching LTP for {ticker} from yfinance: {e}")

        logger.warning(f"Could not get real-time price for {symbol}")
        return None

    def subscribe_to_symbols(self, symbols: list[str]) -> bool:
        """
        Subscribe to real-time price updates for symbols.

        Args:
            symbols: List of symbols to subscribe to

        Returns:
            True if subscription successful, False otherwise
        """
        if not self.live_price_manager:
            logger.debug("No live price manager available for subscription")
            return False

        try:
            # Check if live_price_manager has subscribe method
            if hasattr(self.live_price_manager, "subscribe_to_positions"):
                self.live_price_manager.subscribe_to_positions(symbols)
                logger.debug(f"Subscribed to {len(symbols)} symbols via LivePriceManager")
                return True
            elif hasattr(self.live_price_manager, "subscribe"):
                # LivePriceCache interface
                for symbol in symbols:
                    self.live_price_manager.subscribe(symbol)
                logger.debug(f"Subscribed to {len(symbols)} symbols via LivePriceCache")
                return True
            else:
                logger.warning("Live price manager does not support subscription")
                return False
        except Exception as e:
            logger.error(f"Failed to subscribe to symbols: {e}")
            return False

    def unsubscribe_from_symbols(self, symbols: list[str]) -> bool:
        """
        Unsubscribe from real-time price updates for symbols.

        Args:
            symbols: List of symbols to unsubscribe from

        Returns:
            True if unsubscription successful, False otherwise
        """
        if not self.live_price_manager:
            return False

        try:
            if hasattr(self.live_price_manager, "unsubscribe_from_positions"):
                self.live_price_manager.unsubscribe_from_positions(symbols)
                logger.debug(f"Unsubscribed from {len(symbols)} symbols")
                return True
            elif hasattr(self.live_price_manager, "unsubscribe"):
                for symbol in symbols:
                    self.live_price_manager.unsubscribe(symbol)
                logger.debug(f"Unsubscribed from {len(symbols)} symbols")
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Failed to unsubscribe from symbols: {e}")
            return False

    def clear_cache(self):
        """Clear all cached price data"""
        if self._cache:
            self._cache.clear()
            logger.debug("Price cache cleared")


# Singleton instance
_price_service_instance: PriceService | None = None


def get_price_service(
    live_price_manager=None, enable_caching: bool = True, **kwargs
) -> PriceService:
    """
    Get or create singleton PriceService instance.

    Args:
        live_price_manager: Optional LivePriceManager instance
        enable_caching: Enable price caching (default: True)
        **kwargs: Additional arguments passed to PriceService

    Returns:
        PriceService instance
    """
    global _price_service_instance  # noqa: PLW0603

    if _price_service_instance is None:
        _price_service_instance = PriceService(
            live_price_manager=live_price_manager, enable_caching=enable_caching, **kwargs
        )
    elif (
        live_price_manager is not None
        and _price_service_instance.live_price_manager != live_price_manager
    ):
        # Update live_price_manager if provided and different
        _price_service_instance.live_price_manager = live_price_manager

    return _price_service_instance
