"""
Indicator Service

Unified service for calculating technical indicators (RSI, EMA, etc.).
Consolidates indicator calculation logic from across the codebase.

Features:
- RSI calculation (configurable period)
- EMA calculation (configurable period: 9, 20, 50, 200)
- Real-time EMA9 calculation with current LTP
- Batch indicator calculation
- Caching layer to reduce redundant calculations
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
import pandas_ta as ta  # noqa: E402

from config.settings import VOLUME_LOOKBACK_DAYS  # noqa: E402
from config.strategy_config import StrategyConfig  # noqa: E402
from core.data_fetcher import fetch_ohlcv_yf  # noqa: E402
from core.indicators import compute_indicators  # noqa: E402
from modules.kotak_neo_auto_trader.utils.symbol_utils import (  # noqa: E402
    extract_ticker_base,
)
from utils.logger import logger  # noqa: E402

# Constants
EMA9_PERIOD = 9
MIN_DATA_POINTS_FOR_EMA9 = 9


class IndicatorCache:
    """Simple in-memory cache for indicator calculations with TTL"""

    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}

    def get(self, key: str, ttl_seconds: int = 60) -> Any | None:
        """Get cached indicator data if not expired"""
        if key in self._cache:
            entry = self._cache[key]
            age = (datetime.now() - entry["timestamp"]).total_seconds()
            if age < ttl_seconds:
                logger.debug(f"Cache hit for indicator: {key} (age: {age:.1f}s)")
                return entry["data"]
            else:
                # Expired, remove from cache
                del self._cache[key]
        return None

    def set(self, key: str, data: Any):
        """Cache indicator data"""
        self._cache[key] = {
            "data": data,
            "timestamp": datetime.now(),
        }

    def clear(self):
        """Clear all cached data"""
        self._cache.clear()


class IndicatorService:
    """
    Unified service for calculating technical indicators.

    This service consolidates indicator calculation logic from across the codebase,
    providing a single interface for RSI, EMA, and other indicators.
    """

    def __init__(
        self,
        price_service=None,
        enable_caching: bool = True,
        cache_ttl: int = 60,  # 1 minute for indicators
    ):
        """
        Initialize IndicatorService.

        Args:
            price_service: Optional PriceService instance for real-time price fetching
            enable_caching: Enable indicator caching (default: True)
            cache_ttl: Cache TTL for indicators in seconds (default: 60)
        """
        self.price_service = price_service
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        self._cache = IndicatorCache() if enable_caching else None

        logger.debug(f"IndicatorService initialized (caching: {enable_caching}, ttl: {cache_ttl}s)")

    def calculate_rsi(
        self, df: pd.DataFrame, period: int = 10, config: StrategyConfig | None = None
    ) -> pd.Series | None:
        """
        Calculate RSI indicator.

        Uses pandas_ta.rsi() to match existing compute_indicators() behavior.
        Maintains exact same calculation as core/indicators.py.

        Args:
            df: DataFrame with OHLCV data (must have 'close' column)
            period: RSI calculation period (default: 10)
            config: Optional StrategyConfig (uses default if None)

        Returns:
            Series with RSI values, or None if calculation fails

        Example:
            >>> service = IndicatorService()
            >>> rsi_series = service.calculate_rsi(df, period=10)
        """
        if df is None or df.empty:
            return None

        # Create cache key
        cache_key = f"rsi_{hash(str(df.index[-5:]))}_{period}"

        # Check cache first
        if self._cache:
            cached = self._cache.get(cache_key, self.cache_ttl)
            if cached is not None:
                return cached.copy()

        try:
            # Get config if not provided
            if config is None:
                config = StrategyConfig.default()

            # Use provided period or config default
            rsi_period = period if period is not None else config.rsi_period

            # Handle column name case variations
            close_col = "Close" if "Close" in df.columns else "close"

            # Use pandas_ta for RSI (same as compute_indicators)
            rsi_series = ta.rsi(df[close_col], length=rsi_period)

            # Cache the result
            if self._cache and rsi_series is not None:
                self._cache.set(cache_key, rsi_series)

            return rsi_series

        except Exception as e:
            logger.error(f"Failed to calculate RSI: {e}")
            return None

    def calculate_ema(
        self,
        df: pd.DataFrame,
        period: int = 200,
        adjust: bool = False,
    ) -> pd.Series | None:
        """
        Calculate EMA (Exponential Moving Average) indicator.

        Uses pandas_ta.ema() or pandas ewm() to match existing behavior.
        Maintains exact same calculation as core/indicators.py.

        Args:
            df: DataFrame with OHLCV data (must have 'close' column)
            period: EMA period (default: 200)
            adjust: Whether to use adjust parameter in ewm (default: False)

        Returns:
            Series with EMA values, or None if calculation fails

        Example:
            >>> service = IndicatorService()
            >>> ema200_series = service.calculate_ema(df, period=200)
            >>> ema9_series = service.calculate_ema(df, period=9)
        """
        if df is None or df.empty:
            return None

        # Create cache key
        cache_key = f"ema_{hash(str(df.index[-5:]))}_{period}_{adjust}"

        # Check cache first
        if self._cache:
            cached = self._cache.get(cache_key, self.cache_ttl)
            if cached is not None:
                return cached.copy()

        try:
            # Handle column name case variations
            close_col = "Close" if "Close" in df.columns else "close"

            # Use pandas_ta for EMA (same as compute_indicators)
            # For consistency with existing code, use pandas_ta.ema()
            ema_series = ta.ema(df[close_col], length=period)

            # Cache the result
            if self._cache and ema_series is not None:
                self._cache.set(cache_key, ema_series)

            return ema_series

        except Exception as e:
            logger.error(f"Failed to calculate EMA{period}: {e}")
            return None

    def calculate_ema9_realtime(
        self,
        ticker: str,
        broker_symbol: str | None = None,
        current_ltp: float | None = None,
    ) -> float | None:
        """
        Calculate real-time daily EMA9 value using current LTP.

        This method maintains EXACT same logic as sell_engine.get_current_ema9():
        1. Get historical daily data (exclude current day)
        2. Calculate EMA9 on historical data
        3. Get current LTP (today's price)
        4. Calculate today's EMA9 with current LTP using formula:
           EMA_today = (Price_today x k) + (EMA_yesterday x (1 - k))
           where k = 2 / (period + 1) = 2 / (9 + 1) = 0.2

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            broker_symbol: Broker symbol for LTP fetch (e.g., 'RELIANCE-EQ')
            current_ltp: Optional current LTP (if None, will fetch via price_service)

        Returns:
            Current real-time EMA9 value or None if failed

        Example:
            >>> service = IndicatorService(price_service=price_svc)
            >>> ema9 = service.calculate_ema9_realtime('RELIANCE.NS', 'RELIANCE-EQ')
        """
        try:
            # Step 1: Get historical daily data (exclude current day for past EMA)
            if self.price_service:
                df = self.price_service.get_price(
                    ticker, days=200, interval="1d", add_current_day=False
                )
            else:
                # Fallback to direct fetch if price_service not available
                df = fetch_ohlcv_yf(ticker, days=200, interval="1d", add_current_day=False)

            if df is None or df.empty:
                logger.warning(f"No historical data for {ticker}")
                return None

            # Step 2: Calculate EMA9 on historical data
            if len(df) < MIN_DATA_POINTS_FOR_EMA9:
                logger.warning(f"Insufficient data for EMA9 calculation: {len(df)} days")
                return None

            # Calculate EMA9 using exponential weighted mean (same as sell_engine)
            ema_series = df["close"].ewm(span=EMA9_PERIOD, adjust=False).mean()
            yesterday_ema9 = float(ema_series.iloc[-1])

            # Step 3: Get current LTP (today's price)
            if current_ltp is None:
                if self.price_service:
                    # Extract base symbol for price service
                    base_symbol = extract_ticker_base(ticker)
                    current_ltp = self.price_service.get_realtime_price(
                        base_symbol, ticker, broker_symbol
                    )
                else:
                    logger.warning(
                        f"No price_service available and no current_ltp provided for {ticker}"
                    )
                    return yesterday_ema9

            if current_ltp is None:
                logger.warning(f"No LTP available for {ticker}, using yesterday's EMA9")
                return yesterday_ema9

            # Step 4: Calculate today's EMA9 with current LTP
            # EMA formula: EMA_today = (Price_today x k) + (EMA_yesterday x (1 - k))
            # where k = 2 / (period + 1) = 2 / (9 + 1) = 0.2
            # (EXACT same formula as sell_engine.get_current_ema9())
            k = 2.0 / (EMA9_PERIOD + 1)
            current_ema9 = (current_ltp * k) + (yesterday_ema9 * (1 - k))

            logger.debug(
                f"{ticker.replace('.NS', '')}: LTP=Rs {current_ltp:.2f}, "
                f"Yesterday EMA9=Rs {yesterday_ema9:.2f} -> "
                f"Current EMA9=Rs {current_ema9:.2f}"
            )
            return current_ema9

        except Exception as e:
            logger.error(f"Error calculating real-time EMA9 for {ticker}: {e}")
            return None

    def calculate_all_indicators(
        self,
        df: pd.DataFrame,
        rsi_period: int | None = None,
        ema_period: int | None = None,
        config: StrategyConfig | None = None,
    ) -> pd.DataFrame | None:
        """
        Calculate all indicators (RSI, EMA9, EMA200, etc.) in batch.

        This method wraps compute_indicators() with caching support.
        Maintains exact same behavior as direct compute_indicators() calls.

        Args:
            df: DataFrame with OHLCV data
            rsi_period: RSI calculation period (uses config if None)
            ema_period: EMA calculation period (uses config if None, default: 200)
            config: Optional StrategyConfig (uses default if None)

        Returns:
            DataFrame with computed indicators added, or None if calculation fails

        Example:
            >>> service = IndicatorService()
            >>> df_with_indicators = service.calculate_all_indicators(df)
        """
        if df is None or df.empty:
            return None

        # Create cache key
        cache_key = f"all_indicators_{hash(str(df.index[-10:]))}_rsi{rsi_period}_ema{ema_period}"

        # Check cache first
        if self._cache:
            cached = self._cache.get(cache_key, self.cache_ttl)
            if cached is not None:
                return cached.copy()

        try:
            # Use existing compute_indicators() function (maintains exact same logic)
            result_df = compute_indicators(
                df, rsi_period=rsi_period, ema_period=ema_period, config=config
            )

            # Cache the result
            if self._cache and result_df is not None:
                self._cache.set(cache_key, result_df)

            return result_df

        except Exception as e:
            logger.error(f"Failed to calculate all indicators: {e}")
            return None

    def get_daily_indicators_dict(
        self,
        ticker: str,
        rsi_period: int | None = None,
        config: StrategyConfig | None = None,
    ) -> dict[str, Any] | None:
        """
        Get daily indicators as a dictionary (matches get_daily_indicators() return format).

        This method maintains exact same return structure as AutoTradeEngine.get_daily_indicators()
        for backward compatibility.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            rsi_period: RSI calculation period (uses config if None)
            config: Optional StrategyConfig (uses default if None)

        Returns:
            Dict with keys: close, rsi10, ema9, ema200, avg_volume
            Returns None if calculation fails

        Example:
            >>> service = IndicatorService(price_service=price_svc)
            >>> indicators = service.get_daily_indicators_dict('RELIANCE.NS')
            >>> print(indicators['rsi10'], indicators['ema9'])
        """
        try:
            # Get price data
            if self.price_service:
                df = self.price_service.get_price(
                    ticker, days=800, interval="1d", add_current_day=False
                )
            else:
                # Fallback to direct fetch
                df = fetch_ohlcv_yf(ticker, days=800, interval="1d", add_current_day=False)

            if df is None or df.empty:
                return None

            # Calculate indicators
            df = self.calculate_all_indicators(
                df, rsi_period=rsi_period, ema_period=200, config=config
            )

            if df is None or df.empty:
                return None

            last = df.iloc[-1]

            # Calculate average volume
            avg_vol = (
                df["volume"].tail(VOLUME_LOOKBACK_DAYS).mean() if "volume" in df.columns else 0
            )

            # Get config for RSI column name
            if config is None:
                config = StrategyConfig.default()

            rsi_period_used = rsi_period if rsi_period is not None else config.rsi_period
            rsi_col = f"rsi{rsi_period_used}"

            # Fallback to 'rsi10' for backward compatibility
            if rsi_col not in last.index and "rsi10" in last.index:
                rsi_col = "rsi10"

            # Build result dict (same structure as get_daily_indicators())
            result = {
                "close": float(last["close"]),
                "rsi10": (
                    float(last[rsi_col]) if rsi_col in last.index else 0.0
                ),  # Keep 'rsi10' key for backward compatibility
                "ema9": (
                    float(df["close"].ewm(span=EMA9_PERIOD, adjust=False).mean().iloc[-1])
                    if "ema9" not in df.columns
                    else float(last.get("ema9", 0))
                ),
                "ema200": (
                    float(last["ema200"])
                    if "ema200" in df.columns
                    else float(df["close"].ewm(span=200, adjust=False).mean().iloc[-1])
                ),
                "avg_volume": float(avg_vol),
            }

            return result

        except Exception as e:
            logger.warning(f"Failed to get indicators for {ticker}: {e}")
            return None

    def clear_cache(self):
        """Clear all cached indicator data"""
        if self._cache:
            self._cache.clear()
            logger.debug("Indicator cache cleared")


# Singleton instance
_indicator_service_instance: IndicatorService | None = None


def get_indicator_service(
    price_service=None, enable_caching: bool = True, **kwargs
) -> IndicatorService:
    """
    Get or create singleton IndicatorService instance.

    Args:
        price_service: Optional PriceService instance
        enable_caching: Enable indicator caching (default: True)
        **kwargs: Additional arguments passed to IndicatorService

    Returns:
        IndicatorService instance
    """
    global _indicator_service_instance  # noqa: PLW0603

    if _indicator_service_instance is None:
        _indicator_service_instance = IndicatorService(
            price_service=price_service, enable_caching=enable_caching, **kwargs
        )
    elif price_service is not None and _indicator_service_instance.price_service != price_service:
        # Update price_service if provided and different
        _indicator_service_instance.price_service = price_service

    return _indicator_service_instance
