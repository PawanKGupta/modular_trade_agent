"""
Price Provider
Provides live/mock prices for paper trading simulation
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger  # noqa: E402

# Import existing data fetcher
try:
    from core.data_fetcher import DataFetcher

    HAS_DATA_FETCHER = True
except ImportError:
    HAS_DATA_FETCHER = False
    logger.warning("⚠️ DataFetcher not available, will attempt YFinance provider")

try:
    from src.infrastructure.data_providers.yfinance_provider import YFinanceProvider

    HAS_YFINANCE_PROVIDER = True
except ImportError:
    HAS_YFINANCE_PROVIDER = False
    logger.warning("⚠️ YFinance provider not available; live prices may be limited")


class PriceProvider:
    """
    Provides stock prices for paper trading

    Modes:
    - 'live': Fetch real-time prices from data source
    - 'mock': Generate random prices for testing
    - 'historical': Replay historical data (future enhancement)
    """

    def __init__(self, mode: str = "live", cache_duration_seconds: int = 5):
        """
        Initialize price provider

        Args:
            mode: 'live', 'mock', or 'historical'
            cache_duration_seconds: How long to cache prices
        """
        self.mode = mode
        self.cache_duration = timedelta(seconds=cache_duration_seconds)

        # Price cache
        self._price_cache: dict[str, tuple[float, datetime]] = {}
        self._lock = Lock()

        # Initialize data fetcher if available
        self.data_fetcher = None
        self.yfinance_provider = None
        if mode == "live":
            if HAS_DATA_FETCHER:
                try:
                    self.data_fetcher = DataFetcher()
                    logger.info("✅ Price provider initialized with broker data fetcher")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to initialize DataFetcher: {e}")
                    self.data_fetcher = None
            if self.data_fetcher is None and HAS_YFINANCE_PROVIDER:
                try:
                    self.yfinance_provider = YFinanceProvider()
                    logger.info("✅ Falling back to YFinance provider for live prices")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to initialize YFinance provider: {e}")
                    self.yfinance_provider = None
            if self.data_fetcher is None and self.yfinance_provider is None:
                logger.warning("⚠️ No live data providers available; using mock prices")
                self.mode = "mock"

    def get_price(self, symbol: str) -> float | None:
        """
        Get current price for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Current price or None if not available
        """
        # Check cache first
        with self._lock:
            if symbol in self._price_cache:
                price, timestamp = self._price_cache[symbol]
                if datetime.now() - timestamp < self.cache_duration:
                    return price

        # Fetch fresh price
        price = self._fetch_price(symbol)

        # Update cache
        if price is not None:
            with self._lock:
                self._price_cache[symbol] = (price, datetime.now())

        return price

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        """
        Get prices for multiple symbols

        Args:
            symbols: List of stock symbols

        Returns:
            Dictionary of {symbol: price}
        """
        prices = {}
        for symbol in symbols:
            price = self.get_price(symbol)
            if price is not None:
                prices[symbol] = price
        return prices

    def _fetch_price(self, symbol: str) -> float | None:
        """
        Fetch price based on mode

        Args:
            symbol: Stock symbol

        Returns:
            Price or None
        """
        if self.mode == "live":
            return self._fetch_live_price(symbol)
        elif self.mode == "mock":
            return self._fetch_mock_price(symbol)
        else:
            logger.error(f"❌ Unknown price mode: {self.mode}")
            return None

    def _fetch_live_price(self, symbol: str) -> float | None:
        """
        Fetch live price using data fetcher

        Args:
            symbol: Stock symbol

        Returns:
            Current price or None
        """
        price = None
        if self.data_fetcher:
            try:
                data = self.data_fetcher.fetch_data_yfinance(
                    symbol=symbol, period="1d", interval="1m"
                )

                if data is not None and not data.empty:
                    latest_price = float(data["close"].iloc[-1])
                    logger.debug(f"📊 Fetched live price for {symbol}: ₹{latest_price:.2f}")
                    return latest_price
                logger.warning(f"⚠️ No broker data available for {symbol}")
            except Exception as e:
                logger.error(f"❌ Error fetching broker price for {symbol}: {e}")

        price = self._fetch_yfinance_price(symbol)
        if price is not None:
            return price

        logger.warning(f"⚠️ Live providers unavailable for {symbol}; falling back to mock")
        return None

    def _fetch_yfinance_price(self, symbol: str) -> float | None:
        """Fetch live price via YFinance provider."""
        if not self.yfinance_provider:
            return None

        try:
            price = self.yfinance_provider.fetch_current_price(symbol)
            if price is not None:
                logger.debug(f"📊 YFinance price for {symbol}: ₹{price:.2f}")
            return price
        except Exception as exc:
            logger.error(f"❌ Error fetching YFinance price for {symbol}: {exc}")
            return None

    def _fetch_mock_price(self, symbol: str) -> float:
        """
        Generate mock price for testing

        Args:
            symbol: Stock symbol

        Returns:
            Mock price
        """
        # Generate deterministic mock price based on symbol
        # This ensures same symbol gets similar prices across calls
        base_price = sum(ord(c) for c in symbol) * 10

        # Add some randomness (±5%)
        variation = random.uniform(-0.05, 0.05)  # noqa: S311 - pseudo random acceptable for mock
        price = base_price * (1 + variation)

        logger.debug(f"📊 Generated mock price for {symbol}: ₹{price:.2f}")
        return round(price, 2)

    def set_mock_price(self, symbol: str, price: float) -> None:
        """
        Manually set a mock price (for testing)

        Args:
            symbol: Stock symbol
            price: Price to set
        """
        with self._lock:
            self._price_cache[symbol] = (price, datetime.now())
            logger.debug(f"📊 Set mock price for {symbol}: ₹{price:.2f}")

    def clear_cache(self) -> None:
        """Clear price cache"""
        with self._lock:
            self._price_cache.clear()
            logger.debug("🗑️ Price cache cleared")

    def get_cache_info(self) -> dict:
        """Get cache statistics"""
        with self._lock:
            now = datetime.now()
            valid_count = sum(
                1 for _, (_, ts) in self._price_cache.items() if now - ts < self.cache_duration
            )

            return {
                "total_cached": len(self._price_cache),
                "valid_entries": valid_count,
                "mode": self.mode,
                "cache_duration_seconds": self.cache_duration.total_seconds(),
            }
