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
        """
        Get cached historical data if not expired
        
        Phase 4.2: Adaptive TTL support
        """
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

        # Phase 4.1: Subscription management
        # Track which symbols are subscribed and by which services
        self._subscriptions: dict[str, set[str]] = {}  # symbol -> set of service_ids
        self._subscribed_symbols: set[str] = set()  # All currently subscribed symbols

        # Phase 4.2: Adaptive TTL tracking
        self._last_market_state: str | None = None  # 'open', 'closed', 'pre_market', 'post_market'
        self._base_historical_ttl = historical_cache_ttl
        self._base_realtime_ttl = realtime_cache_ttl

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

        # Phase 4.2: Use adaptive TTL if caching enabled
        if self.enable_caching:
            adaptive_ttl = self.get_adaptive_ttl(data_type="historical")
        else:
            adaptive_ttl = self.historical_cache_ttl

        # Check cache first (with adaptive TTL)
        if self._cache:
            cached_data = self._cache.get_historical(cache_key, ttl_seconds=adaptive_ttl)
            if cached_data is not None:
                logger.debug(f"Cache hit (adaptive TTL: {adaptive_ttl}s) for {ticker}")
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

        # Phase 4.2: Use adaptive TTL if caching enabled
        if self.enable_caching:
            adaptive_ttl = self.get_adaptive_ttl(data_type="realtime")
        else:
            adaptive_ttl = self.realtime_cache_ttl

        # Check cache first (with adaptive TTL)
        if self._cache:
            cached_price = self._cache.get_realtime(cache_key, ttl_seconds=adaptive_ttl)
            if cached_price is not None:
                logger.debug(f"Cache hit (adaptive TTL: {adaptive_ttl}s) for real-time price: {symbol}")
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

    def subscribe_to_symbols(
        self, symbols: list[str], service_id: str = "default"
    ) -> bool:
        """
        Subscribe to real-time price updates for symbols.

        Phase 4.1: Centralize Live Price Subscription
        - Subscription deduplication: Avoid subscribing to same symbol twice
        - Subscription lifecycle: Track which services subscribe to which symbols

        Args:
            symbols: List of symbols to subscribe to
            service_id: Identifier for the service requesting subscription (for tracking)

        Returns:
            True if subscription successful, False otherwise
        """
        if not self.live_price_manager:
            logger.debug("No live price manager available for subscription")
            return False

        if not symbols:
            return True  # No symbols to subscribe to

        try:
            # Phase 4.1: Track subscriptions per service
            normalized_symbols = [s.upper().strip() for s in symbols if s]

            # Find symbols that need new subscriptions (not already subscribed)
            symbols_to_subscribe = [
                symbol
                for symbol in normalized_symbols
                if symbol not in self._subscribed_symbols
            ]

            # Track all symbols for this service (even if already subscribed)
            for symbol in normalized_symbols:
                if symbol not in self._subscriptions:
                    self._subscriptions[symbol] = set()
                self._subscriptions[symbol].add(service_id)

            # Only subscribe to symbols that aren't already subscribed
            if symbols_to_subscribe:
                # Check if live_price_manager has subscribe method
                if hasattr(self.live_price_manager, "subscribe_to_positions"):
                    self.live_price_manager.subscribe_to_positions(symbols_to_subscribe)
                    logger.debug(
                        f"Subscribed to {len(symbols_to_subscribe)} new symbols via LivePriceManager "
                        f"(service: {service_id}, total subscribed: {len(self._subscribed_symbols) + len(symbols_to_subscribe)})"
                    )
                elif hasattr(self.live_price_manager, "subscribe"):
                    # LivePriceCache interface
                    for symbol in symbols_to_subscribe:
                        self.live_price_manager.subscribe(symbol)
                    logger.debug(
                        f"Subscribed to {len(symbols_to_subscribe)} new symbols via LivePriceCache "
                        f"(service: {service_id}, total subscribed: {len(self._subscribed_symbols) + len(symbols_to_subscribe)})"
                    )
                else:
                    logger.warning("Live price manager does not support subscription")
                    return False

                # Update subscribed symbols set
                self._subscribed_symbols.update(symbols_to_subscribe)
            else:
                logger.debug(
                    f"All {len(normalized_symbols)} symbols already subscribed "
                    f"(service: {service_id}, deduplication saved {len(normalized_symbols)} subscriptions)"
                )

            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to symbols: {e}")
            return False

    def unsubscribe_from_symbols(
        self, symbols: list[str], service_id: str = "default"
    ) -> bool:
        """
        Unsubscribe from real-time price updates for symbols.

        Phase 4.1: Centralize Live Price Subscription
        - Only unsubscribes if no other services need the symbol
        - Tracks subscription lifecycle

        Args:
            symbols: List of symbols to unsubscribe from
            service_id: Identifier for the service requesting unsubscription

        Returns:
            True if unsubscription successful, False otherwise
        """
        if not self.live_price_manager:
            return False

        if not symbols:
            return True  # No symbols to unsubscribe from

        try:
            normalized_symbols = [s.upper().strip() for s in symbols if s]

            # Remove service from subscription tracking
            symbols_to_unsubscribe = []
            for symbol in normalized_symbols:
                if symbol in self._subscriptions:
                    self._subscriptions[symbol].discard(service_id)

                    # Only unsubscribe if no other services need this symbol
                    if not self._subscriptions[symbol]:
                        symbols_to_unsubscribe.append(symbol)
                        self._subscriptions.pop(symbol, None)
                        self._subscribed_symbols.discard(symbol)

            # Only unsubscribe from symbols that no services need
            if symbols_to_unsubscribe:
                if hasattr(self.live_price_manager, "unsubscribe_from_positions"):
                    self.live_price_manager.unsubscribe_from_positions(symbols_to_unsubscribe)
                    logger.debug(
                        f"Unsubscribed from {len(symbols_to_unsubscribe)} symbols "
                        f"(service: {service_id}, total subscribed: {len(self._subscribed_symbols)})"
                    )
                    return True
                elif hasattr(self.live_price_manager, "unsubscribe"):
                    for symbol in symbols_to_unsubscribe:
                        self.live_price_manager.unsubscribe(symbol)
                    logger.debug(
                        f"Unsubscribed from {len(symbols_to_unsubscribe)} symbols "
                        f"(service: {service_id}, total subscribed: {len(self._subscribed_symbols)})"
                    )
                    return True
            else:
                logger.debug(
                    f"Symbols still needed by other services, not unsubscribing "
                    f"(service: {service_id})"
                )
                return True

            return False
        except Exception as e:
            logger.error(f"Failed to unsubscribe from symbols: {e}")
            return False

    def get_subscribed_symbols(self) -> set[str]:
        """
        Get all currently subscribed symbols.

        Phase 4.1: Subscription lifecycle tracking

        Returns:
            Set of subscribed symbols
        """
        return self._subscribed_symbols.copy()

    def get_subscriptions_by_service(self, service_id: str) -> set[str]:
        """
        Get symbols subscribed by a specific service.

        Phase 4.1: Subscription lifecycle tracking

        Args:
            service_id: Service identifier

        Returns:
            Set of symbols subscribed by the service
        """
        service_symbols = set()
        for symbol, services in self._subscriptions.items():
            if service_id in services:
                service_symbols.add(symbol)
        return service_symbols

    def get_all_subscriptions(self) -> dict[str, set[str]]:
        """
        Get all subscription mappings (symbol -> set of service_ids).

        Phase 4.1: Subscription lifecycle tracking

        Returns:
            Dict mapping symbols to sets of service IDs
        """
        return {symbol: services.copy() for symbol, services in self._subscriptions.items()}

    def get_adaptive_ttl(self, data_type: str = "historical") -> int:
        """
        Get adaptive cache TTL based on market conditions.

        Phase 4.2: Enhanced Caching Strategy
        - Longer TTL when market is closed (data doesn't change)
        - Shorter TTL during market hours (fresher data)
        - Medium TTL for pre-market/post-market hours

        Args:
            data_type: Type of data ('historical' or 'realtime')

        Returns:
            Adaptive TTL in seconds
        """
        from datetime import time as dt_time

        now = datetime.now().time()
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 30)

        # Determine market state
        if market_open <= now <= market_close:
            market_state = "open"
        elif now < market_open:
            market_state = "pre_market"
        else:
            market_state = "post_market"  # After market close

        self._last_market_state = market_state

        if data_type == "historical":
            # Historical data TTL based on market state
            if market_state == "open":
                # Market open: shorter TTL for fresher data
                return int(self._base_historical_ttl * 0.7)  # 70% of base (3.5 min)
            elif market_state == "post_market":
                # Market closed: longer TTL (data won't change)
                return int(self._base_historical_ttl * 3)  # 3x base (15 min)
            else:  # pre_market
                # Pre-market: medium TTL
                return int(self._base_historical_ttl * 1.5)  # 1.5x base (7.5 min)
        else:  # realtime
            # Real-time data TTL based on market state
            if market_state == "open":
                # Market open: shorter TTL for fresher prices
                return int(self._base_realtime_ttl * 0.7)  # 70% of base (21 sec)
            elif market_state == "post_market":
                # Market closed: longer TTL (prices won't change)
                return int(self._base_realtime_ttl * 5)  # 5x base (2.5 min)
            else:  # pre_market
                # Pre-market: medium TTL
                return int(self._base_realtime_ttl * 2)  # 2x base (1 min)

    def warm_cache_for_positions(
        self, positions: list[dict[str, Any]] | dict[str, list[dict[str, Any]]]
    ) -> dict[str, int]:
        """
        Warm cache for open positions.

        Phase 4.2: Cache Warming Strategies
        Pre-populates cache with price and indicator data for all open positions.

        Args:
            positions: List of position dicts or dict grouped by symbol

        Returns:
            Dict with warming statistics: {'warmed': int, 'failed': int}
        """
        if not positions:
            return {"warmed": 0, "failed": 0}

        warmed = 0
        failed = 0

        # Handle both list and dict formats
        if isinstance(positions, dict):
            # Grouped by symbol: {symbol: [trade1, trade2, ...]}
            symbols = list(positions.keys())
        else:
            # List of trades: extract unique symbols
            symbols = list(
                set(
                    trade.get("symbol", "").upper().replace("-EQ", "").replace("-BE", "").replace("-BL", "").replace("-BZ", "")
                    for trade in positions
                    if trade.get("symbol")
                )
            )

        logger.info(f"Warming cache for {len(symbols)} positions...")

        for symbol in symbols:
            try:
                # Get ticker from symbol (assume NSE)
                ticker = f"{symbol}.NS"

                # Warm historical price cache
                df = self.get_price(ticker, days=365, interval="1d", add_current_day=True)
                if df is not None and not df.empty:
                    warmed += 1
                    logger.debug(f"Cache warmed for {symbol} historical prices")
                else:
                    failed += 1
                    logger.debug(f"Failed to warm cache for {symbol} historical prices")

            except Exception as e:
                logger.debug(f"Error warming cache for {symbol}: {e}")
                failed += 1

        logger.info(
            f"Cache warming complete: {warmed} positions warmed, {failed} failed"
        )

        return {"warmed": warmed, "failed": failed}

    def warm_cache_for_recommendations(
        self, recommendations: list[Any]
    ) -> dict[str, int]:
        """
        Warm cache for recommendation symbols.

        Phase 4.2: Cache Warming Strategies
        Pre-populates cache with price data for symbols in recommendations.

        Args:
            recommendations: List of Recommendation objects or dicts with 'ticker' field

        Returns:
            Dict with warming statistics: {'warmed': int, 'failed': int}
        """
        if not recommendations:
            return {"warmed": 0, "failed": 0}

        warmed = 0
        failed = 0

        logger.info(f"Warming cache for {len(recommendations)} recommendations...")

        for rec in recommendations:
            try:
                # Extract ticker from recommendation
                if hasattr(rec, "ticker"):
                    ticker = rec.ticker
                elif isinstance(rec, dict):
                    ticker = rec.get("ticker", "")
                else:
                    continue

                if not ticker:
                    continue

                # Warm historical price cache
                df = self.get_price(ticker, days=365, interval="1d", add_current_day=True)
                if df is not None and not df.empty:
                    warmed += 1
                    logger.debug(f"Cache warmed for {ticker} historical prices")
                else:
                    failed += 1
                    logger.debug(f"Failed to warm cache for {ticker} historical prices")

            except Exception as e:
                logger.debug(f"Error warming cache for recommendation: {e}")
                failed += 1

        logger.info(
            f"Cache warming complete: {warmed} recommendations warmed, {failed} failed"
        )

        return {"warmed": warmed, "failed": failed}

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
