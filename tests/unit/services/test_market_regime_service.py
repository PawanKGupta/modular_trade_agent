"""
Unit tests for MarketRegimeService
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from services.market_regime_service import (
    MarketRegimeService,
    get_market_regime_service,
)


class TestMarketRegimeService:
    """Test cases for MarketRegimeService"""

    def setup_method(self):
        """Setup for each test"""
        self.service = MarketRegimeService()

    def teardown_method(self):
        """Cleanup after each test"""
        self.service.clear_cache()

    def test_get_default_features(self):
        """Test that default features are returned correctly"""
        defaults = self.service._get_default_features()

        assert defaults['nifty_trend'] == 0.0
        assert defaults['nifty_vs_sma20_pct'] == 0.0
        assert defaults['nifty_vs_sma50_pct'] == 0.0
        assert defaults['india_vix'] == 20.0
        assert defaults['sector_strength'] == 0.0

    def test_calculate_trend_bullish(self):
        """Test trend calculation for bullish market"""
        # Close > SMA20 and Close > SMA50 = Bullish
        nifty_data = pd.DataFrame({
            'Close': [18000.0],
            'SMA20': [17500.0],
            'SMA50': [17000.0]
        })

        trend = self.service._calculate_trend(nifty_data)
        assert trend == 1.0  # Bullish

    def test_calculate_trend_bearish(self):
        """Test trend calculation for bearish market"""
        # Close < SMA20 and Close < SMA50 = Bearish
        nifty_data = pd.DataFrame({
            'Close': [16000.0],
            'SMA20': [17500.0],
            'SMA50': [18000.0]
        })

        trend = self.service._calculate_trend(nifty_data)
        assert trend == -1.0  # Bearish

    def test_calculate_trend_neutral(self):
        """Test trend calculation for neutral market"""
        # Close > SMA20 but < SMA50 = Neutral
        nifty_data = pd.DataFrame({
            'Close': [17500.0],
            'SMA20': [17000.0],
            'SMA50': [18000.0]
        })

        trend = self.service._calculate_trend(nifty_data)
        assert trend == 0.0  # Neutral

    def test_calculate_trend_missing_sma(self):
        """Test trend calculation with missing SMA values"""
        nifty_data = pd.DataFrame({
            'Close': [18000.0],
            'SMA20': [np.nan],
            'SMA50': [17000.0]
        })

        trend = self.service._calculate_trend(nifty_data)
        assert trend == 0.0  # Neutral (default for missing data)

    def test_calculate_sma_distance_above(self):
        """Test SMA distance calculation when price is above SMA"""
        nifty_data = pd.DataFrame({
            'Close': [18000.0],
            'SMA20': [17000.0]
        })

        distance = self.service._calculate_sma_distance(nifty_data, 'SMA20')
        expected = ((18000 - 17000) / 17000) * 100
        assert abs(distance - expected) < 0.01

    def test_calculate_sma_distance_below(self):
        """Test SMA distance calculation when price is below SMA"""
        nifty_data = pd.DataFrame({
            'Close': [16000.0],
            'SMA20': [17000.0]
        })

        distance = self.service._calculate_sma_distance(nifty_data, 'SMA20')
        expected = ((16000 - 17000) / 17000) * 100
        assert abs(distance - expected) < 0.01
        assert distance < 0  # Negative when below SMA

    def test_calculate_sma_distance_missing(self):
        """Test SMA distance with missing SMA"""
        nifty_data = pd.DataFrame({
            'Close': [18000.0],
            'SMA20': [np.nan]
        })

        distance = self.service._calculate_sma_distance(nifty_data, 'SMA20')
        assert distance == 0.0

    @patch('services.market_regime_service.yf.download')
    def test_get_nifty_data_success(self, mock_download):
        """Test successful Nifty data fetch"""
        # Create mock data
        dates = pd.date_range(start='2024-10-01', periods=60, freq='D')
        mock_data = pd.DataFrame({
            'Close': np.random.uniform(17000, 18000, 60),
            'Open': np.random.uniform(17000, 18000, 60),
            'High': np.random.uniform(17000, 18000, 60),
            'Low': np.random.uniform(17000, 18000, 60),
            'Volume': np.random.uniform(1000000, 2000000, 60)
        }, index=dates)

        mock_download.return_value = mock_data

        # Test
        result = self.service._get_nifty_data('2024-11-10')

        assert result is not None
        assert 'Close' in result.columns
        assert 'SMA20' in result.columns
        assert 'SMA50' in result.columns

    @patch('services.market_regime_service.yf.download')
    def test_get_nifty_data_empty_response(self, mock_download):
        """Test handling of empty Nifty data response"""
        mock_download.return_value = pd.DataFrame()

        result = self.service._get_nifty_data('2024-11-10')
        assert result is None

    @patch('services.market_regime_service.yf.download')
    def test_get_nifty_data_exception(self, mock_download):
        """Test handling of exception during Nifty data fetch"""
        mock_download.side_effect = Exception("API Error")

        result = self.service._get_nifty_data('2024-11-10')
        assert result is None

    @patch('services.market_regime_service.yf.download')
    def test_get_vix_success(self, mock_download):
        """Test successful VIX fetch"""
        dates = pd.date_range(start='2024-11-05', periods=5, freq='D')
        mock_data = pd.DataFrame({
            'Close': [22.5, 23.0, 21.5, 20.0, 19.5]
        }, index=dates)

        mock_download.return_value = mock_data

        vix = self.service._get_vix('2024-11-10')
        assert isinstance(vix, float)
        assert vix > 0

    @patch('services.market_regime_service.yf.download')
    def test_get_vix_fallback_to_default(self, mock_download):
        """Test VIX fallback to default when data unavailable"""
        mock_download.return_value = pd.DataFrame()

        vix = self.service._get_vix('2024-11-10')
        assert vix == 20.0  # Default value

    @patch('services.market_regime_service.yf.download')
    def test_get_market_regime_features_complete(self, mock_download):
        """Test getting complete market regime features"""
        # Mock Nifty data
        dates = pd.date_range(start='2024-10-01', periods=60, freq='D')
        nifty_data = pd.DataFrame({
            'Close': [17500.0] * 60,  # Constant for simplicity
            'Open': [17400.0] * 60,
            'High': [17600.0] * 60,
            'Low': [17300.0] * 60,
            'Volume': [1000000] * 60
        }, index=dates)

        # Mock VIX data
        vix_data = pd.DataFrame({
            'Close': [22.5]
        }, index=[dates[-1]])

        # Set up mock to return different data based on ticker
        def mock_download_side_effect(ticker, **kwargs):
            if ticker == '^NSEI':
                return nifty_data
            elif ticker == '^INDIAVIX':
                return vix_data
            return pd.DataFrame()

        mock_download.side_effect = mock_download_side_effect

        # Test
        features = self.service.get_market_regime_features(date='2024-11-10')

        assert 'nifty_trend' in features
        assert 'nifty_vs_sma20_pct' in features
        assert 'nifty_vs_sma50_pct' in features
        assert 'india_vix' in features
        assert 'sector_strength' in features

        # Check value ranges
        assert features['nifty_trend'] in [-1.0, 0.0, 1.0]
        assert isinstance(features['nifty_vs_sma20_pct'], (int, float))
        assert isinstance(features['nifty_vs_sma50_pct'], (int, float))
        assert features['india_vix'] > 0

    @patch('services.market_regime_service.yf.download')
    def test_get_market_regime_features_with_error(self, mock_download):
        """Test fallback to defaults when fetch fails"""
        mock_download.side_effect = Exception("Network error")

        features = self.service.get_market_regime_features(date='2024-11-10')

        # Should return defaults
        assert features['nifty_trend'] == 0.0
        assert features['nifty_vs_sma20_pct'] == 0.0
        assert features['nifty_vs_sma50_pct'] == 0.0
        assert features['india_vix'] == 20.0
        assert features['sector_strength'] == 0.0

    def test_cache_validity(self):
        """Test cache validity checking"""
        # Initially invalid
        assert not self.service._is_cache_valid('2024-11-10')

        # Set cache
        self.service._nifty_cache = pd.DataFrame({'Close': [18000]})
        self.service._cache_date = '2024-11-10'
        self.service._cache_timestamp = datetime.now()

        # Should be valid
        assert self.service._is_cache_valid('2024-11-10')

        # Different date should be invalid
        assert not self.service._is_cache_valid('2024-11-11')

        # Expired cache should be invalid
        self.service._cache_timestamp = datetime.now() - timedelta(hours=2)
        assert not self.service._is_cache_valid('2024-11-10')

    def test_clear_cache(self):
        """Test cache clearing"""
        # Set cache
        self.service._nifty_cache = pd.DataFrame({'Close': [18000]})
        self.service._vix_cache = 22.5
        self.service._cache_timestamp = datetime.now()
        self.service._cache_date = '2024-11-10'

        # Clear
        self.service.clear_cache()

        # Verify all cleared
        assert self.service._nifty_cache is None
        assert self.service._vix_cache is None
        assert self.service._cache_timestamp is None
        assert self.service._cache_date is None

    @patch('services.market_regime_service.yf.download')
    def test_get_market_regime_features_uses_current_date_if_none(self, mock_download):
        """Test that current date is used when date parameter is None"""
        # Mock data
        dates = pd.date_range(start=datetime.now() - timedelta(days=60), periods=60, freq='D')
        mock_data = pd.DataFrame({
            'Close': [17500.0] * 60,
            'Open': [17400.0] * 60,
            'High': [17600.0] * 60,
            'Low': [17300.0] * 60,
            'Volume': [1000000] * 60
        }, index=dates)

        mock_download.return_value = mock_data

        # Call without date (should use current date)
        features = self.service.get_market_regime_features()

        assert 'nifty_trend' in features
        assert features is not None

    def test_singleton_pattern(self):
        """Test that get_market_regime_service returns singleton"""
        service1 = get_market_regime_service()
        service2 = get_market_regime_service()

        assert service1 is service2  # Same instance

    @patch('services.market_regime_service.yf.download')
    def test_multiindex_column_handling(self, mock_download):
        """Test handling of MultiIndex columns from yfinance"""
        # Create mock data with MultiIndex columns
        dates = pd.date_range(start='2024-10-01', periods=60, freq='D')
        columns = pd.MultiIndex.from_tuples([
            ('Close', '^NSEI'),
            ('Open', '^NSEI'),
            ('High', '^NSEI'),
            ('Low', '^NSEI'),
            ('Volume', '^NSEI')
        ])
        mock_data = pd.DataFrame(
            np.random.uniform(17000, 18000, (60, 5)),
            index=dates,
            columns=columns
        )

        mock_download.return_value = mock_data

        result = self.service._get_nifty_data('2024-11-10')

        # Should flatten MultiIndex columns
        assert result is not None
        assert isinstance(result.columns, pd.Index)
        assert not isinstance(result.columns, pd.MultiIndex)
        assert 'Close' in result.columns

    @patch('services.market_regime_service.yf.download')
    def test_timezone_aware_index_handling(self, mock_download):
        """Test handling of timezone-aware datetime index"""
        # Create mock data with timezone
        dates = pd.date_range(start='2024-10-01', periods=60, freq='D', tz='US/Eastern')
        mock_data = pd.DataFrame({
            'Close': np.random.uniform(17000, 18000, 60),
            'Open': np.random.uniform(17000, 18000, 60),
            'High': np.random.uniform(17000, 18000, 60),
            'Low': np.random.uniform(17000, 18000, 60),
            'Volume': np.random.uniform(1000000, 2000000, 60)
        }, index=dates)

        mock_download.return_value = mock_data

        result = self.service._get_nifty_data('2024-11-10')

        # Should convert to timezone-naive
        assert result is not None
        assert result.index.tz is None

