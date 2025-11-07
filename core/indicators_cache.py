"""
Indicator Calculation Cache

Provides caching for frequently used indicator calculations to improve performance.
"""

import functools
import hashlib
import pickle
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

from utils.logger import logger


class IndicatorCache:
    """
    Simple in-memory cache for indicator calculations.
    
    Uses LRU (Least Recently Used) eviction policy.
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum number of cached items
        """
        self.max_size = max_size
        self.cache: Dict[str, Any] = {}
        self.access_order: list = []  # Track access order for LRU
    
    def _generate_key(self, df: pd.DataFrame, rsi_period: int, ema_period: int, config_hash: str) -> str:
        """
        Generate cache key from DataFrame and parameters.
        
        Args:
            df: DataFrame to cache
            rsi_period: RSI period
            ema_period: EMA period
            config_hash: Hash of configuration
        
        Returns:
            Cache key string
        """
        # Use DataFrame hash (shape, columns, last few values)
        df_hash = f"{df.shape}_{list(df.columns)}_{df.iloc[-1].values.tobytes() if len(df) > 0 else b''}"
        key_data = f"{df_hash}_{rsi_period}_{ema_period}_{config_hash}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[pd.DataFrame]:
        """
        Get cached value.
        
        Args:
            key: Cache key
        
        Returns:
            Cached DataFrame or None
        """
        if key in self.cache:
            # Update access order
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None
    
    def set(self, key: str, value: pd.DataFrame):
        """
        Set cached value.
        
        Args:
            key: Cache key
            value: DataFrame to cache
        """
        # Evict if cache is full
        if len(self.cache) >= self.max_size:
            # Remove least recently used
            lru_key = self.access_order.pop(0)
            del self.cache[lru_key]
        
        # Add to cache
        self.cache[key] = value.copy()
        self.access_order.append(key)
    
    def clear(self):
        """Clear all cached values."""
        self.cache.clear()
        self.access_order.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


# Global cache instance
_indicator_cache = IndicatorCache(max_size=100)


def cached_compute_indicators(func):
    """
    Decorator to cache indicator calculations.
    
    Usage:
        @cached_compute_indicators
        def compute_indicators(df, rsi_period=None, ema_period=None, config=None):
            ...
    """
    @functools.wraps(func)
    def wrapper(df: pd.DataFrame, rsi_period: Optional[int] = None, 
                ema_period: Optional[int] = None, config: Optional[Any] = None):
        # Skip caching if DataFrame is too large or empty
        if df is None or df.empty or len(df) > 10000:
            return func(df, rsi_period, ema_period, config)
        
        # Generate config hash
        config_hash = ""
        if config is not None:
            try:
                config_dict = {
                    'rsi_period': getattr(config, 'rsi_period', None),
                    'support_resistance_lookback_daily': getattr(config, 'support_resistance_lookback_daily', None),
                    'volume_exhaustion_lookback_daily': getattr(config, 'volume_exhaustion_lookback_daily', None),
                }
                config_hash = hashlib.md5(str(config_dict).encode()).hexdigest()
            except Exception:
                pass
        
        # Generate cache key
        cache_key = _indicator_cache._generate_key(df, rsi_period or 10, ema_period or 200, config_hash)
        
        # Check cache
        cached_result = _indicator_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for indicators (key: {cache_key[:8]}...)")
            return cached_result
        
        # Compute indicators
        result = func(df, rsi_period, ema_period, config)
        
        # Cache result
        if result is not None and not result.empty:
            _indicator_cache.set(cache_key, result)
            logger.debug(f"Cached indicators (key: {cache_key[:8]}..., size: {_indicator_cache.size()})")
        
        return result
    
    return wrapper


def clear_indicator_cache():
    """Clear the indicator cache."""
    _indicator_cache.clear()
    logger.info("Indicator cache cleared")


def get_indicator_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.
    
    Returns:
        Dictionary with cache statistics
    """
    return {
        'size': _indicator_cache.size(),
        'max_size': _indicator_cache.max_size,
        'hit_rate': 'N/A'  # Would need to track hits/misses
    }

