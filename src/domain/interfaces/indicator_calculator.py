"""
IndicatorCalculator Interface - Domain Layer

Abstract interface for calculating technical indicators.
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional
from ..value_objects.indicators import RSIIndicator, EMAIndicator, IndicatorSet


class IndicatorCalculator(ABC):
    """
    Interface for calculating technical indicators
    
    This abstraction allows using different indicator libraries
    (pandas_ta, ta-lib, custom implementations) without changing business logic.
    """
    
    @abstractmethod
    def calculate_rsi(self, data: pd.DataFrame, period: int = 10) -> pd.Series:
        """
        Calculate RSI indicator
        
        Args:
            data: DataFrame with 'close' column
            period: RSI period
            
        Returns:
            Series with RSI values
        """
        pass
    
    @abstractmethod
    def calculate_ema(self, data: pd.DataFrame, period: int = 200) -> pd.Series:
        """
        Calculate EMA indicator
        
        Args:
            data: DataFrame with 'close' column
            period: EMA period
            
        Returns:
            Series with EMA values
        """
        pass
    
    @abstractmethod
    def calculate_support_resistance(
        self, 
        data: pd.DataFrame,
        lookback: int = 20
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Calculate support and resistance levels
        
        Args:
            data: DataFrame with OHLC data
            lookback: Lookback period for calculation
            
        Returns:
            Tuple of (support_level, resistance_level)
        """
        pass
    
    @abstractmethod
    def calculate_volume_ratio(
        self, 
        data: pd.DataFrame,
        period: int = 20
    ) -> float:
        """
        Calculate current volume ratio vs average
        
        Args:
            data: DataFrame with 'volume' column
            period: Period for average calculation
            
        Returns:
            Volume ratio (current / average)
        """
        pass
    
    @abstractmethod
    def calculate_all_indicators(
        self,
        data: pd.DataFrame,
        rsi_period: int = 10,
        ema_period: int = 200
    ) -> IndicatorSet:
        """
        Calculate complete set of indicators
        
        Args:
            data: DataFrame with OHLCV data
            rsi_period: RSI calculation period
            ema_period: EMA calculation period
            
        Returns:
            IndicatorSet with all calculated indicators
        """
        pass
    
    @abstractmethod
    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Validate that data has sufficient rows and required columns
        
        Args:
            data: DataFrame to validate
            
        Returns:
            True if data is valid for indicator calculation
        """
        pass


class IndicatorCalculationError(Exception):
    """Exception raised when indicator calculation fails"""
    pass
