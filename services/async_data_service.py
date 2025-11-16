"""
Async Data Service

Provides async versions of data fetching operations for parallel processing.
Significantly reduces analysis time when processing multiple stocks.
"""

import asyncio
import pandas as pd
from typing import Optional, Dict, List, Any
from datetime import datetime
import yfinance as yf

from services.data_service import DataService
from services.cache_service import CachedDataService, CacheService
from utils.logger import logger
from config.strategy_config import StrategyConfig


class AsyncDataService:
    """
    Async version of DataService for parallel data fetching
    
    Provides async methods that can be run concurrently, significantly
    reducing analysis time for batch operations.
    """
    
    def __init__(
        self,
        data_service: Optional[DataService] = None,
        cache_service: Optional[CacheService] = None,
        max_concurrent: int = 10
    ):
        """
        Initialize async data service
        
        Args:
            data_service: Underlying DataService (creates default if None)
            cache_service: CacheService for caching (creates default if None)
            max_concurrent: Maximum concurrent requests
        """
        self.data_service = data_service or DataService()
        self.cache_service = cache_service or CacheService()
        self.cached_service = CachedDataService(self.data_service, self.cache_service)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
    
    async def fetch_single_timeframe_async(
        self,
        ticker: str,
        end_date: Optional[str] = None,
        add_current_day: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        Async fetch single timeframe data
        
        Args:
            ticker: Stock ticker
            end_date: End date for data
            add_current_day: Whether to include current day
            
        Returns:
            DataFrame or None
        """
        async with self.semaphore:
            # Run blocking operation in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            try:
                data = await loop.run_in_executor(
                    None,
                    self.cached_service.fetch_single_timeframe,
                    ticker,
                    end_date,
                    add_current_day
                )
                logger.debug(f"Async fetched data for {ticker}")
                return data
            except Exception as e:
                logger.error(f"Error async fetching data for {ticker}: {e}")
                return None
    
    async def fetch_multi_timeframe_async(
        self,
        ticker: str,
        end_date: Optional[str] = None,
        add_current_day: bool = True
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Async fetch multi-timeframe data
        
        Args:
            ticker: Stock ticker
            end_date: End date for data
            add_current_day: Whether to include current day
            
        Returns:
            Dict with 'daily' and 'weekly' DataFrames or None
        """
        async with self.semaphore:
            # Run blocking operation in executor
            loop = asyncio.get_event_loop()
            try:
                data = await loop.run_in_executor(
                    None,
                    self.cached_service.fetch_multi_timeframe,
                    ticker,
                    end_date,
                    add_current_day
                )
                logger.debug(f"Async fetched multi-timeframe data for {ticker}")
                return data
            except Exception as e:
                logger.error(f"Error async fetching multi-timeframe data for {ticker}: {e}")
                return None
    
    async def fetch_fundamentals_async(self, ticker: str) -> Dict[str, Optional[float]]:
        """
        Async fetch fundamental data (PE, PB ratios)
        
        Args:
            ticker: Stock ticker
            
        Returns:
            Dict with pe and pb values
        """
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            try:
                # Check cache first
                cache_key = self.cache_service.get_fundamentals_key(ticker)
                cached = self.cache_service.get(cache_key)
                if cached is not None:
                    logger.debug(f"Using cached fundamentals for {ticker}")
                    return cached
                
                # Fetch from yfinance in executor
                def fetch_fundamentals():
                    try:
                        stock = yf.Ticker(ticker)
                        info = stock.info
                        return {
                            'pe': info.get('trailingPE', None),
                            'pb': info.get('priceToBook', None)
                        }
                    except Exception as e:
                        logger.warning(f"Error fetching fundamentals for {ticker}: {e}")
                        return {'pe': None, 'pb': None}
                
                fundamentals = await loop.run_in_executor(None, fetch_fundamentals)
                
                # Cache if successful (longer TTL for fundamentals - they change less frequently)
                if fundamentals:
                    self.cache_service.set(cache_key, fundamentals, ttl_seconds=86400)  # 24 hours
                
                return fundamentals
            except Exception as e:
                logger.error(f"Error async fetching fundamentals for {ticker}: {e}")
                return {'pe': None, 'pb': None}
    
    async def fetch_batch_async(
        self,
        tickers: List[str],
        enable_multi_timeframe: bool = True,
        end_date: Optional[str] = None,
        add_current_day: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch data for multiple tickers in parallel
        
        Args:
            tickers: List of ticker symbols
            enable_multi_timeframe: Enable multi-timeframe fetching
            end_date: End date for data
            add_current_day: Whether to include current day
            
        Returns:
            Dict mapping ticker to fetched data
        """
        logger.info(f"Fetching data for {len(tickers)} tickers in parallel (max {self.max_concurrent} concurrent)")
        
        if enable_multi_timeframe:
            tasks = [
                self.fetch_multi_timeframe_async(t, end_date, add_current_day)
                for t in tickers
            ]
        else:
            tasks = [
                self.fetch_single_timeframe_async(t, end_date, add_current_day)
                for t in tickers
            ]
        
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Map results to tickers
        data_map = {}
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching data for {ticker}: {result}")
                data_map[ticker] = None
            else:
                data_map[ticker] = result
        
        successful = sum(1 for v in data_map.values() if v is not None)
        logger.info(f"Fetched data for {successful}/{len(tickers)} tickers")
        
        return data_map
