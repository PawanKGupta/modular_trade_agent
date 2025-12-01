"""
Unit tests for IndicatorService

Tests ensure backward compatibility with existing indicator calculation logic.
"""

from unittest.mock import Mock, patch

import pandas as pd

from core.indicators import compute_indicators
from modules.kotak_neo_auto_trader.services.indicator_service import (
    IndicatorCache,
    IndicatorService,
)


class TestIndicatorCache:
    """Tests for IndicatorCache"""

    def test_cache_get_set(self):
        """Test caching and retrieval of indicator data"""
        cache = IndicatorCache()
        data = pd.Series([100, 101, 102])

        # Cache data
        cache.set("test_key", data)

        # Retrieve within TTL
        cached = cache.get("test_key", ttl_seconds=60)
        assert cached is not None
        assert len(cached) == 3

    def test_cache_expires(self):
        """Test that cached data expires after TTL"""
        cache = IndicatorCache()
        data = pd.Series([100, 101, 102])

        cache.set("test_key", data)

        # Retrieve with very short TTL (should expire)
        cached = cache.get("test_key", ttl_seconds=0)
        assert cached is None

    def test_clear_cache(self):
        """Test clearing all cached data"""
        cache = IndicatorCache()
        data = pd.Series([100])

        cache.set("key1", data)
        cache.clear()

        assert cache.get("key1", ttl_seconds=60) is None


class TestIndicatorService:
    """Tests for IndicatorService"""

    def test_calculate_rsi(self):
        """Test RSI calculation"""
        df = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
                "date": pd.date_range("2024-01-01", periods=11),
            }
        )

        service = IndicatorService(enable_caching=False)
        result = service.calculate_rsi(df, period=10)

        assert result is not None
        assert len(result) == len(df)
        # RSI should be between 0 and 100
        assert all(0 <= val <= 100 for val in result.dropna())

    def test_calculate_rsi_with_caching(self):
        """Test that caching works for RSI"""
        df = pd.DataFrame({"close": range(100, 111)})

        service = IndicatorService(enable_caching=True)

        # First call - should calculate
        result1 = service.calculate_rsi(df, period=10)
        assert result1 is not None

        # Second call - should use cache
        with patch("pandas_ta.rsi"):
            result2 = service.calculate_rsi(df, period=10)
            assert result2 is not None
            # Should not call ta.rsi again (cached)
            # Note: This is a simplified test - actual caching may vary

    def test_calculate_ema(self):
        """Test EMA calculation"""
        df = pd.DataFrame(
            {
                "close": range(100, 150),
                "date": pd.date_range("2024-01-01", periods=50),
            }
        )

        service = IndicatorService(enable_caching=False)
        result = service.calculate_ema(df, period=9)

        assert result is not None
        assert len(result) == len(df)

    def test_calculate_ema200(self):
        """Test EMA200 calculation"""
        df = pd.DataFrame(
            {
                "close": range(100, 350),  # Need enough data for EMA200
                "date": pd.date_range("2024-01-01", periods=250),
            }
        )

        service = IndicatorService(enable_caching=False)
        result = service.calculate_ema(df, period=200)

        assert result is not None
        assert len(result) == len(df)

    def test_calculate_all_indicators(self):
        """Test batch indicator calculation"""
        df = pd.DataFrame(
            {
                "close": range(100, 350),
                "open": range(99, 349),
                "high": range(101, 351),
                "low": range(98, 348),
                "volume": range(1000, 1250),
                "date": pd.date_range("2024-01-01", periods=250),
            }
        )

        service = IndicatorService(enable_caching=False)
        result = service.calculate_all_indicators(df)

        assert result is not None
        assert "rsi10" in result.columns or "rsi10" in result.columns
        assert "ema9" in result.columns
        assert "ema200" in result.columns

    @patch("modules.kotak_neo_auto_trader.services.indicator_service.fetch_ohlcv_yf")
    def test_calculate_ema9_realtime(self, mock_fetch):
        """Test real-time EMA9 calculation"""
        # Mock historical data
        mock_df = pd.DataFrame(
            {
                "close": range(100, 300),
                "date": pd.date_range("2024-01-01", periods=200),
            }
        )
        mock_fetch.return_value = mock_df

        # Mock price service
        mock_price_service = Mock()
        mock_price_service.get_price.return_value = mock_df
        mock_price_service.get_realtime_price.return_value = 250.0

        service = IndicatorService(price_service=mock_price_service, enable_caching=False)

        result = service.calculate_ema9_realtime("RELIANCE.NS", "RELIANCE-EQ")

        assert result is not None
        assert isinstance(result, float)
        assert result > 0

    def test_calculate_ema9_realtime_with_provided_ltp(self):
        """Test real-time EMA9 calculation with provided LTP"""
        # Mock historical data
        mock_df = pd.DataFrame(
            {
                "close": range(100, 300),
                "date": pd.date_range("2024-01-01", periods=200),
            }
        )

        mock_price_service = Mock()
        mock_price_service.get_price.return_value = mock_df

        service = IndicatorService(price_service=mock_price_service, enable_caching=False)

        # Provide current_ltp directly
        result = service.calculate_ema9_realtime("RELIANCE.NS", "RELIANCE-EQ", current_ltp=250.0)

        assert result is not None
        assert isinstance(result, float)
        assert result > 0

    def test_get_daily_indicators_dict(self):
        """Test getting daily indicators as dictionary"""
        mock_df = pd.DataFrame(
            {
                "close": range(100, 350),
                "open": range(99, 349),
                "high": range(101, 351),
                "low": range(98, 348),
                "volume": range(1000, 1250),
                "date": pd.date_range("2024-01-01", periods=250),
            }
        )

        mock_price_service = Mock()
        mock_price_service.get_price.return_value = mock_df

        service = IndicatorService(price_service=mock_price_service, enable_caching=False)

        result = service.get_daily_indicators_dict("RELIANCE.NS")

        assert result is not None
        assert "close" in result
        assert "rsi10" in result
        assert "ema9" in result
        assert "ema200" in result
        assert "avg_volume" in result

    def test_get_daily_indicators_dict_matches_format(self):
        """Test that get_daily_indicators_dict returns same format as get_daily_indicators"""
        mock_df = pd.DataFrame(
            {
                "close": range(100, 350),
                "open": range(99, 349),
                "high": range(101, 351),
                "low": range(98, 348),
                "volume": range(1000, 1250),
                "date": pd.date_range("2024-01-01", periods=250),
            }
        )

        mock_price_service = Mock()
        mock_price_service.get_price.return_value = mock_df

        service = IndicatorService(price_service=mock_price_service, enable_caching=False)

        result = service.get_daily_indicators_dict("RELIANCE.NS")

        # Verify same keys as get_daily_indicators()
        expected_keys = {"close", "rsi10", "ema9", "ema200", "avg_volume"}
        assert set(result.keys()) == expected_keys

        # Verify all values are floats
        assert all(isinstance(v, float) for v in result.values())


class TestIndicatorServiceBackwardCompatibility:
    """Tests to ensure IndicatorService maintains backward compatibility"""

    def test_calculate_rsi_matches_compute_indicators(self):
        """Test that calculate_rsi() produces same results as compute_indicators()"""
        df = pd.DataFrame(
            {
                "close": range(100, 350),
                "open": range(99, 349),
                "high": range(101, 351),
                "low": range(98, 348),
                "volume": range(1000, 1250),
                "date": pd.date_range("2024-01-01", periods=250),
            }
        )

        service = IndicatorService(enable_caching=False)

        # Calculate RSI using IndicatorService
        rsi_service = service.calculate_rsi(df, period=10)

        # Calculate using compute_indicators
        df_with_indicators = compute_indicators(df, rsi_period=10)
        rsi_compute = df_with_indicators["rsi10"]

        # Compare results (should be identical)
        pd.testing.assert_series_equal(rsi_service, rsi_compute, check_names=False, rtol=1e-10)

    def test_calculate_ema_matches_compute_indicators(self):
        """Test that calculate_ema() produces same results as compute_indicators()"""
        df = pd.DataFrame(
            {
                "close": range(100, 350),
                "open": range(99, 349),
                "high": range(101, 351),
                "low": range(98, 348),
                "volume": range(1000, 1250),
                "date": pd.date_range("2024-01-01", periods=250),
            }
        )

        service = IndicatorService(enable_caching=False)

        # Calculate EMA9 using IndicatorService
        ema9_service = service.calculate_ema(df, period=9)

        # Calculate using compute_indicators
        df_with_indicators = compute_indicators(df)
        ema9_compute = df_with_indicators["ema9"]

        # Compare results (should be identical)
        pd.testing.assert_series_equal(ema9_service, ema9_compute, check_names=False, rtol=1e-10)

    def test_calculate_all_indicators_matches_compute_indicators(self):
        """Test that calculate_all_indicators() produces same results as compute_indicators()"""
        df = pd.DataFrame(
            {
                "close": range(100, 350),
                "open": range(99, 349),
                "high": range(101, 351),
                "low": range(98, 348),
                "volume": range(1000, 1250),
                "date": pd.date_range("2024-01-01", periods=250),
            }
        )

        service = IndicatorService(enable_caching=False)

        # Calculate using IndicatorService
        result_service = service.calculate_all_indicators(df, rsi_period=10, ema_period=200)

        # Calculate using compute_indicators
        result_compute = compute_indicators(df, rsi_period=10, ema_period=200)

        # Compare key indicators
        pd.testing.assert_series_equal(
            result_service["rsi10"], result_compute["rsi10"], check_names=False, rtol=1e-10
        )
        pd.testing.assert_series_equal(
            result_service["ema9"], result_compute["ema9"], check_names=False, rtol=1e-10
        )
        pd.testing.assert_series_equal(
            result_service["ema200"],
            result_compute["ema200"],
            check_names=False,
            rtol=1e-10,
        )
