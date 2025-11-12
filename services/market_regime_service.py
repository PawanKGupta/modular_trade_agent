"""
Market Regime Service

Fetches and analyzes broader market context (Nifty 50, India VIX, sector trends)
to provide market regime features for ML predictions.

Features provided:
1. nifty_trend: bullish/neutral/bearish
2. nifty_vs_sma20_pct: % distance from 20-day SMA
3. nifty_vs_sma50_pct: % distance from 50-day SMA
4. india_vix: Current volatility index
5. sector_strength: Sector performance vs Nifty (if available)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MarketRegimeService:
    """Service to fetch and analyze market regime data"""

    # Cache duration (in seconds)
    CACHE_DURATION = 3600  # 1 hour

    def __init__(self):
        """Initialize the market regime service"""
        self._nifty_cache: Optional[pd.DataFrame] = None
        self._vix_cache: Optional[float] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_date: Optional[str] = None  # Track which date's data is cached

    def get_market_regime_features(
        self,
        date: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Get market regime features for a given date.

        Args:
            date: Date in YYYY-MM-DD format. If None, uses today.
            sector: Sector name for sector strength calculation (optional)

        Returns:
            Dictionary with market regime features:
            - nifty_trend: 1.0 (bullish), 0.0 (neutral), -1.0 (bearish)
            - nifty_vs_sma20_pct: % distance from 20-day SMA
            - nifty_vs_sma50_pct: % distance from 50-day SMA
            - india_vix: VIX value
            - sector_strength: Sector vs Nifty performance (0 if not available)
        """
        try:
            # Use current date if not specified
            if date is None:
                date = datetime.now().strftime("%Y-%m-%d")

            # Fetch market data
            nifty_data = self._get_nifty_data(date)
            if nifty_data is None:
                logger.warning(f"Could not fetch Nifty data for {date}, using defaults")
                return self._get_default_features()

            # Extract features
            features = {}

            # 1. Nifty trend (based on price vs SMAs)
            features["nifty_trend"] = self._calculate_trend(nifty_data)

            # 2 & 3. Distance from SMAs
            features["nifty_vs_sma20_pct"] = self._calculate_sma_distance(
                nifty_data, "SMA20"
            )
            features["nifty_vs_sma50_pct"] = self._calculate_sma_distance(
                nifty_data, "SMA50"
            )

            # 4. India VIX
            features["india_vix"] = self._get_vix(date)

            # 5. Sector strength (placeholder for now)
            features["sector_strength"] = 0.0  # TODO: Implement sector analysis

            logger.debug(f"Market regime features for {date}: {features}")
            return features

        except Exception as e:
            logger.error(f"Error getting market regime features: {e}")
            return self._get_default_features()

    def _get_nifty_data(self, target_date: str) -> Optional[pd.DataFrame]:
        """
        Fetch Nifty 50 data with SMAs for the given date.

        Uses caching to avoid repeated API calls within the same session.
        """
        try:
            # Parse target date
            target_dt = pd.to_datetime(target_date).normalize()

            # Check cache
            if self._is_cache_valid(target_date):
                logger.debug("Using cached Nifty data")
                return self._nifty_cache

            logger.debug(f"Fetching Nifty data for {target_date}")

            # Calculate date range (need extra days for SMA50)
            end_date = target_dt + timedelta(days=1)  # Include target date
            start_date = target_dt - timedelta(days=100)  # Buffer for SMA50

            # Fetch data
            # NOTE: Using unadjusted prices (auto_adjust=False) to match TradingView
            nifty = yf.download(
                "^NSEI",
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=False,
            )

            if nifty.empty:
                logger.warning("No Nifty data received")
                return None

            # Handle MultiIndex columns (yfinance behavior)
            if isinstance(nifty.columns, pd.MultiIndex):
                nifty.columns = nifty.columns.get_level_values(0)

            # Normalize index
            if nifty.index.tz is not None:
                nifty.index = nifty.index.tz_localize(None)
            nifty.index = pd.to_datetime(nifty.index).normalize()

            # Calculate SMAs
            nifty["SMA20"] = nifty["Close"].rolling(window=20).mean()
            nifty["SMA50"] = nifty["Close"].rolling(window=50).mean()

            # Get data for target date (or closest previous trading day)
            try:
                row = nifty.loc[target_dt]
            except KeyError:
                # Use asof to get closest previous trading day
                closest_date = nifty.index.asof(target_dt)
                if pd.isna(closest_date):
                    logger.warning(f"No Nifty data available for {target_date}")
                    return None
                row = nifty.loc[closest_date]
                logger.debug(f"Using closest date: {closest_date} for {target_date}")

            # Convert row to DataFrame for consistency
            if isinstance(row, pd.Series):
                result_df = pd.DataFrame([row])
            else:
                result_df = pd.DataFrame([row.iloc[0]])

            # Cache the result
            self._nifty_cache = result_df
            self._cache_date = target_date
            self._cache_timestamp = datetime.now()

            return result_df

        except Exception as e:
            logger.error(f"Error fetching Nifty data: {e}")
            return None

    def _get_vix(self, target_date: str) -> float:
        """
        Fetch India VIX for the given date.

        Note: India VIX historical data is limited on Yahoo Finance.
        Returns 20.0 as default if not available.
        """
        try:
            # Check cache
            if self._is_cache_valid(target_date) and self._vix_cache is not None:
                return self._vix_cache

            # Try to fetch VIX data
            target_dt = pd.to_datetime(target_date)
            end_date = target_dt + timedelta(days=1)
            start_date = target_dt - timedelta(days=5)  # Look back a few days

            # NOTE: Using unadjusted prices (auto_adjust=False) to match TradingView
            vix = yf.download(
                "^INDIAVIX",
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=False,
            )

            if not vix.empty:
                # Handle MultiIndex columns
                if isinstance(vix.columns, pd.MultiIndex):
                    vix.columns = vix.columns.get_level_values(0)

                # Normalize index
                if vix.index.tz is not None:
                    vix.index = vix.index.tz_localize(None)
                vix.index = pd.to_datetime(vix.index).normalize()

                # Get closest value
                target_dt_normalized = pd.to_datetime(target_date).normalize()
                if target_dt_normalized in vix.index:
                    vix_value = float(vix.loc[target_dt_normalized, "Close"])
                else:
                    closest_date = vix.index.asof(target_dt_normalized)
                    if not pd.isna(closest_date):
                        vix_value = float(vix.loc[closest_date, "Close"])
                    else:
                        vix_value = 20.0  # Default

                self._vix_cache = vix_value
                logger.debug(f"India VIX for {target_date}: {vix_value}")
                return vix_value

        except Exception as e:
            logger.debug(f"Could not fetch VIX data: {e}, using default")

        # Default VIX (neutral)
        return 20.0

    def _calculate_trend(self, nifty_data: pd.DataFrame) -> float:
        """
        Calculate trend: 1.0 (bullish), 0.0 (neutral), -1.0 (bearish)

        Bullish: Close > SMA20 AND Close > SMA50
        Bearish: Close < SMA20 AND Close < SMA50
        Neutral: Otherwise
        """
        try:
            close = float(nifty_data["Close"].iloc[0])
            sma20 = float(nifty_data["SMA20"].iloc[0])
            sma50 = float(nifty_data["SMA50"].iloc[0])

            if pd.isna(sma20) or pd.isna(sma50):
                return 0.0  # Neutral if SMAs not available

            if close > sma20 and close > sma50:
                return 1.0  # Bullish
            elif close < sma20 and close < sma50:
                return -1.0  # Bearish
            else:
                return 0.0  # Neutral

        except Exception as e:
            logger.error(f"Error calculating trend: {e}")
            return 0.0

    def _calculate_sma_distance(self, nifty_data: pd.DataFrame, sma_col: str) -> float:
        """
        Calculate percentage distance from SMA.

        Returns: (Close - SMA) / SMA * 100
        Positive = above SMA, Negative = below SMA
        """
        try:
            close = float(nifty_data["Close"].iloc[0])
            sma = float(nifty_data[sma_col].iloc[0])

            if pd.isna(sma) or sma == 0:
                return 0.0

            distance_pct = ((close - sma) / sma) * 100
            return round(distance_pct, 2)

        except Exception as e:
            logger.error(f"Error calculating SMA distance: {e}")
            return 0.0

    def _is_cache_valid(self, target_date: str) -> bool:
        """Check if cached data is still valid for the target date"""
        if (
            self._nifty_cache is None
            or self._cache_timestamp is None
            or self._cache_date != target_date
        ):
            return False

        # Check if cache has expired
        age = (datetime.now() - self._cache_timestamp).total_seconds()
        return age < self.CACHE_DURATION

    def _get_default_features(self) -> Dict[str, float]:
        """Return default features when data is not available"""
        return {
            "nifty_trend": 0.0,  # Neutral
            "nifty_vs_sma20_pct": 0.0,
            "nifty_vs_sma50_pct": 0.0,
            "india_vix": 20.0,  # Average VIX
            "sector_strength": 0.0,
        }

    def clear_cache(self) -> None:
        """Clear cached market data (useful for testing)"""
        self._nifty_cache = None
        self._vix_cache = None
        self._cache_timestamp = None
        self._cache_date = None
        logger.debug("Market regime cache cleared")


# Singleton instance
_market_regime_service: Optional[MarketRegimeService] = None


def get_market_regime_service() -> MarketRegimeService:
    """Get or create the singleton market regime service instance"""
    global _market_regime_service
    if _market_regime_service is None:
        _market_regime_service = MarketRegimeService()
    return _market_regime_service

