"""
Unit tests for PriceService

Tests ensure backward compatibility with existing price fetching logic.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd

from modules.kotak_neo_auto_trader.services.price_service import PriceCache, PriceService


class TestPriceCache:
    """Tests for PriceCache"""

    def test_cache_historical_data(self):
        """Test caching and retrieval of historical data"""
        cache = PriceCache()
        df = pd.DataFrame({"close": [100, 101, 102]})

        # Cache data
        cache.set_historical("test_key", df)

        # Retrieve within TTL
        cached = cache.get_historical("test_key", ttl_seconds=300)
        assert cached is not None
        assert len(cached) == 3

    def test_cache_expires_historical(self):
        """Test that cached historical data expires after TTL"""
        cache = PriceCache()
        df = pd.DataFrame({"close": [100, 101, 102]})

        cache.set_historical("test_key", df)

        # Retrieve with very short TTL (should expire)
        cached = cache.get_historical("test_key", ttl_seconds=0)
        assert cached is None

    def test_cache_realtime_price(self):
        """Test caching and retrieval of real-time price"""
        cache = PriceCache()

        # Cache price
        cache.set_realtime("RELIANCE", 2500.50)

        # Retrieve within TTL
        cached = cache.get_realtime("RELIANCE", ttl_seconds=30)
        assert cached == 2500.50

    def test_cache_expires_realtime(self):
        """Test that cached real-time price expires after TTL"""
        cache = PriceCache()

        cache.set_realtime("RELIANCE", 2500.50)

        # Retrieve with very short TTL (should expire)
        cached = cache.get_realtime("RELIANCE", ttl_seconds=0)
        assert cached is None

    def test_clear_cache(self):
        """Test clearing all cached data"""
        cache = PriceCache()
        df = pd.DataFrame({"close": [100]})

        cache.set_historical("key1", df)
        cache.set_realtime("RELIANCE", 2500.50)

        cache.clear()

        assert cache.get_historical("key1", ttl_seconds=300) is None
        assert cache.get_realtime("RELIANCE", ttl_seconds=30) is None


class TestPriceService:
    """Tests for PriceService"""

    @patch("modules.kotak_neo_auto_trader.services.price_service.fetch_ohlcv_yf")
    def test_get_price_historical(self, mock_fetch):
        """Test fetching historical price data"""
        # Mock yfinance response
        mock_df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=5),
                "close": [100, 101, 102, 103, 104],
                "open": [99, 100, 101, 102, 103],
                "high": [101, 102, 103, 104, 105],
                "low": [98, 99, 100, 101, 102],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )
        mock_fetch.return_value = mock_df

        service = PriceService(enable_caching=False)
        result = service.get_price("RELIANCE.NS", days=30)

        assert result is not None
        assert len(result) == 5
        mock_fetch.assert_called_once()

    @patch("modules.kotak_neo_auto_trader.services.price_service.fetch_ohlcv_yf")
    def test_get_price_with_caching(self, mock_fetch):
        """Test that caching works for historical data"""
        mock_df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=5),
                "close": [100, 101, 102, 103, 104],
                "open": [99, 100, 101, 102, 103],
                "high": [101, 102, 103, 104, 105],
                "low": [98, 99, 100, 101, 102],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )
        mock_fetch.return_value = mock_df

        service = PriceService(enable_caching=True)

        # First call - should fetch from API
        result1 = service.get_price("RELIANCE.NS", days=30)
        assert result1 is not None
        assert mock_fetch.call_count == 1

        # Second call - should use cache
        result2 = service.get_price("RELIANCE.NS", days=30)
        assert result2 is not None
        assert mock_fetch.call_count == 1  # Should not call again

    @patch("modules.kotak_neo_auto_trader.services.price_service.fetch_ohlcv_yf")
    def test_get_price_fallback_on_error(self, mock_fetch):
        """Test that get_price returns None on error"""
        mock_fetch.side_effect = Exception("API error")

        service = PriceService(enable_caching=False)
        result = service.get_price("RELIANCE.NS", days=30)

        assert result is None

    def test_get_realtime_price_with_live_manager(self):
        """Test getting real-time price from LivePriceManager"""
        # Mock LivePriceManager
        mock_manager = Mock()
        mock_manager.get_ltp = Mock(return_value=2500.50)

        service = PriceService(live_price_manager=mock_manager, enable_caching=False)

        with patch(
            "modules.kotak_neo_auto_trader.services.price_service.get_ltp_from_manager"
        ) as mock_get_ltp:
            mock_get_ltp.return_value = 2500.50

            result = service.get_realtime_price("RELIANCE", "RELIANCE.NS", "RELIANCE-EQ")

            assert result == 2500.50
            mock_get_ltp.assert_called_once()

    @patch("modules.kotak_neo_auto_trader.services.price_service.fetch_ohlcv_yf")
    def test_get_realtime_price_fallback_to_yfinance(self, mock_fetch):
        """Test fallback to yfinance when LivePriceManager unavailable"""
        # Mock yfinance response
        mock_df = pd.DataFrame(
            {
                "close": [2500.50],
                "date": [datetime.now()],
            }
        )
        mock_fetch.return_value = mock_df

        service = PriceService(live_price_manager=None, enable_caching=False)

        result = service.get_realtime_price("RELIANCE", "RELIANCE.NS")

        assert result == 2500.50
        mock_fetch.assert_called_once()

    def test_subscribe_to_symbols(self):
        """Test subscribing to symbols"""
        mock_manager = Mock()
        mock_manager.subscribe_to_positions = Mock()

        service = PriceService(live_price_manager=mock_manager)
        result = service.subscribe_to_symbols(["RELIANCE", "TCS"])

        assert result is True
        mock_manager.subscribe_to_positions.assert_called_once_with(["RELIANCE", "TCS"])

    def test_subscribe_without_manager(self):
        """Test subscription fails gracefully without live price manager"""
        service = PriceService(live_price_manager=None)
        result = service.subscribe_to_symbols(["RELIANCE"])

        assert result is False

    def test_clear_cache(self):
        """Test clearing cache"""
        service = PriceService(enable_caching=True)

        # Add some data to cache
        with patch(
            "modules.kotak_neo_auto_trader.services.price_service.fetch_ohlcv_yf"
        ) as mock_fetch:
            mock_df = pd.DataFrame({"close": [100]})
            mock_fetch.return_value = mock_df

            service.get_price("RELIANCE.NS", days=30)

        # Clear cache
        service.clear_cache()

        # Verify cache is empty (next call should fetch again)
        with patch(
            "modules.kotak_neo_auto_trader.services.price_service.fetch_ohlcv_yf"
        ) as mock_fetch:
            mock_df = pd.DataFrame({"close": [100]})
            mock_fetch.return_value = mock_df

            service.get_price("RELIANCE.NS", days=30)
            # Should call fetch again after cache clear
            assert mock_fetch.call_count >= 1


class TestPriceServiceBackwardCompatibility:
    """Tests to ensure PriceService maintains backward compatibility"""

    @patch("modules.kotak_neo_auto_trader.services.price_service.fetch_ohlcv_yf")
    def test_get_price_matches_fetch_ohlcv_yf_behavior(self, mock_fetch):
        """Test that get_price() returns same data as fetch_ohlcv_yf()"""
        mock_df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=10),
                "close": range(100, 110),
                "open": range(99, 109),
                "high": range(101, 111),
                "low": range(98, 108),
                "volume": range(1000, 1010),
            }
        )
        mock_fetch.return_value = mock_df

        service = PriceService(enable_caching=False)

        # Call through PriceService
        result = service.get_price("RELIANCE.NS", days=30, interval="1d", add_current_day=True)

        # Verify same parameters passed to fetch_ohlcv_yf
        mock_fetch.assert_called_once_with(
            ticker="RELIANCE.NS",
            days=30,
            interval="1d",
            end_date=None,
            add_current_day=True,
        )

        # Verify same data returned
        assert result is not None
        assert len(result) == 10
        pd.testing.assert_frame_equal(result, mock_df)

    @patch("modules.kotak_neo_auto_trader.services.price_service.fetch_ohlcv_yf")
    def test_get_price_with_end_date(self, mock_fetch):
        """Test get_price with end_date parameter"""
        mock_df = pd.DataFrame({"close": [100]})
        mock_fetch.return_value = mock_df

        service = PriceService(enable_caching=False)
        service.get_price("RELIANCE.NS", days=30, end_date="2024-01-15")

        mock_fetch.assert_called_once_with(
            ticker="RELIANCE.NS",
            days=30,
            interval="1d",
            end_date="2024-01-15",
            add_current_day=True,
        )
