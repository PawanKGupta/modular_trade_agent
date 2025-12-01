"""
Cache Service

Provides caching layer for data fetching to reduce API calls and improve performance.
Supports both in-memory (default) and file-based caching.
"""

import pickle
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
import pandas as pd

from utils.logger import logger
from config.strategy_config import StrategyConfig


class CacheService:
    """
    Cache service for storing analysis data
    
    Provides:
    - In-memory caching (default, fast)
    - File-based caching (optional, persistent)
    - TTL (time-to-live) support
    - Automatic expiration
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        default_ttl_seconds: int = 3600,  # 1 hour default
        enable_file_cache: bool = True
    ):
        """
        Initialize cache service
        
        Args:
            cache_dir: Directory for file-based cache (None = memory only)
            default_ttl_seconds: Default TTL for cached items
            enable_file_cache: Enable file-based caching
        """
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl_seconds
        self.enable_file_cache = enable_file_cache
        
        if cache_dir:
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.cache_dir = None
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Create cache key from prefix and arguments
        
        Args:
            prefix: Key prefix (e.g., 'ohlcv', 'fundamentals')
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Cache key string
        """
        # Create deterministic key from arguments
        key_data = {
            'prefix': prefix,
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else []
        }
        key_str = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        # Check memory cache first
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            expires_at = entry.get('expires_at')
            
            if expires_at and datetime.now() < expires_at:
                logger.debug(f"Cache HIT (memory): {key}")
                return entry['value']
            else:
                # Expired, remove from cache
                del self.memory_cache[key]
                logger.debug(f"Cache EXPIRED (memory): {key}")
        
        # Check file cache if enabled
        if self.enable_file_cache and self.cache_dir:
            file_path = self.cache_dir / f"{key}.cache"
            if file_path.exists():
                try:
                    with open(file_path, 'rb') as f:
                        entry = pickle.load(f)
                    
                    expires_at = entry.get('expires_at')
                    if expires_at and datetime.now() < expires_at:
                        logger.debug(f"Cache HIT (file): {key}")
                        # Also add to memory cache for faster access
                        self.memory_cache[key] = entry
                        return entry['value']
                    else:
                        # Expired, remove file
                        file_path.unlink()
                        logger.debug(f"Cache EXPIRED (file): {key}")
                except Exception as e:
                    logger.warning(f"Error reading cache file {file_path}: {e}")
        
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Set cached value
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (uses default if None)
        """
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl
        
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        
        entry = {
            'value': value,
            'expires_at': expires_at,
            'cached_at': datetime.now()
        }
        
        # Store in memory cache
        self.memory_cache[key] = entry
        logger.debug(f"Cache SET (memory): {key}, TTL={ttl_seconds}s")
        
        # Store in file cache if enabled
        if self.enable_file_cache and self.cache_dir:
            file_path = self.cache_dir / f"{key}.cache"
            try:
                with open(file_path, 'wb') as f:
                    pickle.dump(entry, f)
                logger.debug(f"Cache SET (file): {key}")
            except Exception as e:
                logger.warning(f"Error writing cache file {file_path}: {e}")
    
    def delete(self, key: str) -> None:
        """
        Delete cached value
        
        Args:
            key: Cache key
        """
        # Remove from memory
        if key in self.memory_cache:
            del self.memory_cache[key]
        
        # Remove from file if exists
        if self.cache_dir:
            file_path = self.cache_dir / f"{key}.cache"
            if file_path.exists():
                file_path.unlink()
        
        logger.debug(f"Cache DELETE: {key}")
    
    def clear(self) -> None:
        """Clear all cached values"""
        self.memory_cache.clear()
        
        if self.cache_dir:
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.warning(f"Error deleting cache file {cache_file}: {e}")
        
        logger.info("Cache cleared")
    
    def get_ohlcv_key(
        self,
        ticker: str,
        timeframe: str = "daily",
        end_date: Optional[str] = None
    ) -> str:
        """
        Generate cache key for OHLCV data
        
        Args:
            ticker: Stock ticker
            timeframe: Timeframe (daily/weekly)
            end_date: End date for data
            
        Returns:
            Cache key
        """
        # Use today's date as part of key (data changes daily)
        today = datetime.now().date().isoformat()
        return self._make_key('ohlcv', ticker, timeframe, end_date, date=today)
    
    def get_fundamentals_key(self, ticker: str) -> str:
        """
        Generate cache key for fundamental data
        
        Args:
            ticker: Stock ticker
            
        Returns:
            Cache key
        """
        # Fundamentals change less frequently, use weekly key
        week = datetime.now().isocalendar()
        return self._make_key('fundamentals', ticker, week=week)
    
    def get_news_sentiment_key(
        self,
        ticker: str,
        lookback_days: int = 30
    ) -> str:
        """
        Generate cache key for news sentiment
        
        Args:
            ticker: Stock ticker
            lookback_days: Lookback period
            
        Returns:
            Cache key
        """
        # News sentiment changes daily
        today = datetime.now().date().isoformat()
        return self._make_key('news_sentiment', ticker, lookback_days, date=today)


class CachedDataService:
    """
    Wrapper around DataService that adds caching
    
    This decorator pattern allows us to add caching to existing
    DataService without modifying it.
    """
    
    def __init__(
        self,
        data_service,
        cache_service: Optional[CacheService] = None
    ):
        """
        Initialize cached data service
        
        Args:
            data_service: Underlying DataService instance
            cache_service: CacheService instance (creates default if None)
        """
        self.data_service = data_service
        self.cache_service = cache_service or CacheService()
    
    def fetch_single_timeframe(
        self,
        ticker: str,
        end_date: Optional[str] = None,
        add_current_day: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        Fetch single timeframe data with caching
        
        Args:
            ticker: Stock ticker
            end_date: End date for data
            add_current_day: Whether to include current day
            
        Returns:
            DataFrame or None
        """
        cache_key = self.cache_service.get_ohlcv_key(
            ticker, 'daily', end_date
        )
        
        # Check cache first
        cached_data = self.cache_service.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Using cached data for {ticker}")
            return cached_data
        
        # Fetch from data service
        data = self.data_service.fetch_single_timeframe(
            ticker, end_date, add_current_day
        )
        
        # Cache if successful (use shorter TTL for intraday data)
        if data is not None:
            ttl = 300 if add_current_day else 3600  # 5 min for intraday, 1 hour for historical
            self.cache_service.set(cache_key, data, ttl_seconds=ttl)
        
        return data
    
    def fetch_multi_timeframe(
        self,
        ticker: str,
        end_date: Optional[str] = None,
        add_current_day: bool = True
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Fetch multi-timeframe data with caching
        
        Args:
            ticker: Stock ticker
            end_date: End date for data
            add_current_day: Whether to include current day
            
        Returns:
            Dict with 'daily' and 'weekly' DataFrames or None
        """
        # Cache daily and weekly separately
        daily_key = self.cache_service.get_ohlcv_key(ticker, 'daily', end_date)
        weekly_key = self.cache_service.get_ohlcv_key(ticker, 'weekly', end_date)
        
        # Check cache for both
        cached_daily = self.cache_service.get(daily_key)
        cached_weekly = self.cache_service.get(weekly_key)
        
        if cached_daily is not None and cached_weekly is not None:
            logger.debug(f"Using cached multi-timeframe data for {ticker}")
            return {'daily': cached_daily, 'weekly': cached_weekly}
        
        # Fetch from data service
        data = self.data_service.fetch_multi_timeframe(
            ticker, end_date, add_current_day
        )
        
        # Cache if successful
        if data is not None:
            ttl = 300 if add_current_day else 3600
            if 'daily' in data:
                self.cache_service.set(daily_key, data['daily'], ttl_seconds=ttl)
            if 'weekly' in data:
                self.cache_service.set(weekly_key, data['weekly'], ttl_seconds=ttl)
        
        return data
