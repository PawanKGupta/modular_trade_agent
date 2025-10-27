"""
DataProvider Interface - Domain Layer

Abstract interface for data fetching operations.
This allows the domain layer to remain independent of specific data sources.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime
import pandas as pd


class DataProvider(ABC):
    """
    Interface for providing market data
    
    This abstraction allows swapping data sources (yfinance, APIs, CSV, etc.)
    without changing business logic.
    """
    
    @abstractmethod
    def fetch_daily_data(
        self, 
        ticker: str, 
        days: int = 365,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch daily OHLCV data for a ticker
        
        Args:
            ticker: Stock symbol
            days: Number of days of historical data
            end_date: End date for data fetch (None = today)
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
            
        Raises:
            DataFetchError: If data cannot be fetched
        """
        pass
    
    @abstractmethod
    def fetch_weekly_data(
        self, 
        ticker: str, 
        weeks: int = 104,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch weekly OHLCV data for a ticker
        
        Args:
            ticker: Stock symbol
            weeks: Number of weeks of historical data
            end_date: End date for data fetch (None = today)
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
            
        Raises:
            DataFetchError: If data cannot be fetched
        """
        pass
    
    @abstractmethod
    def fetch_multi_timeframe_data(
        self, 
        ticker: str,
        daily_days: int = 365,
        weekly_weeks: int = 104,
        end_date: Optional[datetime] = None
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Fetch both daily and weekly data in one call
        
        Args:
            ticker: Stock symbol
            daily_days: Days of daily data
            weekly_weeks: Weeks of weekly data
            end_date: End date for data fetch
            
        Returns:
            Tuple of (daily_df, weekly_df)
            
        Raises:
            DataFetchError: If data cannot be fetched
        """
        pass
    
    @abstractmethod
    def fetch_current_price(self, ticker: str) -> Optional[float]:
        """
        Fetch current/latest price for a ticker
        
        Args:
            ticker: Stock symbol
            
        Returns:
            Current price or None if unavailable
        """
        pass
    
    @abstractmethod
    def fetch_fundamental_data(self, ticker: str) -> dict:
        """
        Fetch fundamental data (PE, PB, etc.)
        
        Args:
            ticker: Stock symbol
            
        Returns:
            Dictionary with fundamental metrics
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if data provider is available/healthy
        
        Returns:
            True if provider is operational
        """
        pass


class DataFetchError(Exception):
    """Exception raised when data fetching fails"""
    pass
