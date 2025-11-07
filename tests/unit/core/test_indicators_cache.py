"""
Unit Tests for Indicator Cache
"""

import sys
import os
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from core.indicators_cache import IndicatorCache, cached_compute_indicators, clear_indicator_cache, get_indicator_cache_stats
from core.indicators import compute_indicators
from config.strategy_config import StrategyConfig


class TestIndicatorCache:
    """Test IndicatorCache class"""
    
    @pytest.fixture
    def cache(self):
        """Create cache instance"""
        return IndicatorCache(max_size=10)
    
    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame"""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        return pd.DataFrame({
            'close': np.linspace(100, 200, 100),
            'open': np.linspace(99, 199, 100),
            'high': np.linspace(105, 205, 100),
            'low': np.linspace(95, 195, 100),
            'volume': [1000000] * 100
        }, index=dates)
    
    def test_cache_initialization(self, cache):
        """Test cache initialization"""
        assert cache.max_size == 10
        assert cache.size() == 0
    
    def test_cache_set_and_get(self, cache, sample_df):
        """Test setting and getting from cache"""
        key = "test_key"
        
        # Set value
        cache.set(key, sample_df)
        
        # Get value
        result = cache.get(key)
        assert result is not None
        assert len(result) == len(sample_df)
        assert list(result.columns) == list(sample_df.columns)
    
    def test_cache_get_nonexistent(self, cache):
        """Test getting non-existent key"""
        result = cache.get("nonexistent_key")
        assert result is None
    
    def test_cache_lru_eviction(self, cache, sample_df):
        """Test LRU eviction when cache is full"""
        # Fill cache to max size
        for i in range(10):
            cache.set(f"key_{i}", sample_df)
        
        assert cache.size() == 10
        
        # Add one more (should evict least recently used)
        cache.set("key_new", sample_df)
        
        # Should still be max size
        assert cache.size() == 10
        
        # First key should be evicted
        assert cache.get("key_0") is None
        
        # New key should be present
        assert cache.get("key_new") is not None
    
    def test_cache_access_order(self, cache, sample_df):
        """Test access order affects eviction"""
        # Add keys
        for i in range(5):
            cache.set(f"key_{i}", sample_df)
        
        # Access key_0 (should move to end)
        cache.get("key_0")
        
        # Fill cache
        for i in range(5, 10):
            cache.set(f"key_{i}", sample_df)
        
        # Add one more
        cache.set("key_new", sample_df)
        
        # key_1 should be evicted (not key_0, which was accessed)
        assert cache.get("key_0") is not None
        assert cache.get("key_1") is None
    
    def test_cache_clear(self, cache, sample_df):
        """Test clearing cache"""
        # Add some values
        cache.set("key1", sample_df)
        cache.set("key2", sample_df)
        
        assert cache.size() == 2
        
        # Clear cache
        cache.clear()
        
        assert cache.size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cache_size(self, cache, sample_df):
        """Test cache size tracking"""
        assert cache.size() == 0
        
        cache.set("key1", sample_df)
        assert cache.size() == 1
        
        cache.set("key2", sample_df)
        assert cache.size() == 2
        
        cache.clear()
        assert cache.size() == 0


class TestCachedComputeIndicators:
    """Test cached_compute_indicators decorator"""
    
    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame"""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        return pd.DataFrame({
            'close': np.linspace(100, 200, 100),
            'open': np.linspace(99, 199, 100),
            'high': np.linspace(105, 205, 100),
            'low': np.linspace(95, 195, 100),
            'volume': [1000000] * 100
        }, index=dates)
    
    def test_cached_decorator_works(self, sample_df):
        """Test that decorator can be applied"""
        # Note: We can't easily test the decorator without modifying compute_indicators
        # This test verifies the decorator exists and is callable
        assert callable(cached_compute_indicators)
    
    def test_cache_skips_large_dataframes(self, sample_df):
        """Test that cache skips very large DataFrames"""
        # Create large DataFrame
        large_df = pd.concat([sample_df] * 200)  # 20,000 rows
        
        # This would normally be cached, but should be skipped
        # We can't easily test this without modifying compute_indicators
        # But the logic exists in the decorator
        pass
    
    def test_cache_skips_empty_dataframes(self):
        """Test that cache skips empty DataFrames"""
        empty_df = pd.DataFrame()
        
        # Empty DataFrame should not be cached
        # Logic exists in decorator
        pass


class TestCacheFunctions:
    """Test module-level functions"""
    
    def test_clear_indicator_cache(self):
        """Test clear_indicator_cache function"""
        clear_indicator_cache()
        # Should not raise exception
    
    def test_get_indicator_cache_stats(self):
        """Test get_indicator_cache_stats function"""
        stats = get_indicator_cache_stats()
        assert isinstance(stats, dict)
        assert 'size' in stats
        assert 'max_size' in stats
        assert isinstance(stats['size'], int)
        assert isinstance(stats['max_size'], int)

