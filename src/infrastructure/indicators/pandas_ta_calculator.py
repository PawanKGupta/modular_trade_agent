"""
PandasTA Indicator Calculator

Implements IndicatorCalculator interface using pandas_ta library.
Wraps existing indicators.py functionality.
"""

import pandas as pd
from typing import Optional

# Import domain interface
from ...domain.interfaces.indicator_calculator import (
    IndicatorCalculator,
    IndicatorCalculationError
)
from ...domain.value_objects.indicators import (
    RSIIndicator,
    EMAIndicator,
    SupportResistanceLevel,
    IndicatorSet
)

# Import existing implementation
from core.indicators import compute_indicators, wilder_rsi
import pandas_ta as ta
from utils.logger import logger


class PandasTACalculator(IndicatorCalculator):
    """
    PandasTA implementation of IndicatorCalculator interface
    
    Wraps existing indicators.py functionality with clean interface.
    """
    
    def __init__(self):
        """Initialize PandasTA calculator"""
        logger.debug("PandasTACalculator initialized")
    
    def calculate_rsi(self, data: pd.DataFrame, period: int = 10) -> pd.Series:
        """
        Calculate RSI indicator
        
        Args:
            data: DataFrame with 'close' column
            period: RSI period
            
        Returns:
            Series with RSI values
        """
        try:
            if not self.validate_data(data):
                raise IndicatorCalculationError("Invalid data for RSI calculation")
            
            # Use pandas_ta RSI (matches TradingView)
            rsi = ta.rsi(data['close'], length=period)
            
            if rsi is None or rsi.empty:
                raise IndicatorCalculationError(f"RSI calculation returned empty result")
            
            return rsi
            
        except IndicatorCalculationError:
            raise
        except Exception as e:
            error_msg = f"Failed to calculate RSI: {e}"
            logger.error(error_msg)
            raise IndicatorCalculationError(error_msg) from e
    
    def calculate_ema(self, data: pd.DataFrame, period: int = 200) -> pd.Series:
        """
        Calculate EMA indicator
        
        Args:
            data: DataFrame with 'close' column
            period: EMA period
            
        Returns:
            Series with EMA values
        """
        try:
            if not self.validate_data(data):
                raise IndicatorCalculationError("Invalid data for EMA calculation")
            
            # Use pandas_ta EMA
            ema = ta.ema(data['close'], length=period)
            
            if ema is None or ema.empty:
                raise IndicatorCalculationError(f"EMA calculation returned empty result")
            
            return ema
            
        except IndicatorCalculationError:
            raise
        except Exception as e:
            error_msg = f"Failed to calculate EMA: {e}"
            logger.error(error_msg)
            raise IndicatorCalculationError(error_msg) from e
    
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
        try:
            if not self.validate_data(data):
                return (None, None)
            
            # Calculate support (recent low)
            recent_lows = data['low'].tail(lookback)
            support = recent_lows.min() if not recent_lows.empty else None
            
            # Calculate resistance (recent high)
            recent_highs = data['high'].tail(lookback)
            resistance = recent_highs.max() if not recent_highs.empty else None
            
            return (support, resistance)
            
        except Exception as e:
            logger.warning(f"Failed to calculate support/resistance: {e}")
            return (None, None)
    
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
        try:
            if not self.validate_data(data) or 'volume' not in data.columns:
                return 1.0
            
            if len(data) < period:
                return 1.0
            
            # Get current volume
            current_volume = data['volume'].iloc[-1]
            
            # Calculate average volume
            avg_volume = data['volume'].tail(period).mean()
            
            if avg_volume == 0:
                return 1.0
            
            return current_volume / avg_volume
            
        except Exception as e:
            logger.warning(f"Failed to calculate volume ratio: {e}")
            return 1.0
    
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
        try:
            if not self.validate_data(data):
                raise IndicatorCalculationError("Invalid data for indicator calculation")
            
            # Calculate RSI
            rsi_series = self.calculate_rsi(data, rsi_period)
            rsi_value = rsi_series.iloc[-1] if not rsi_series.empty else None
            rsi_indicator = RSIIndicator(value=rsi_value, period=rsi_period) if rsi_value is not None else None
            
            # Calculate EMA
            ema_series = self.calculate_ema(data, ema_period)
            ema_value = ema_series.iloc[-1] if not ema_series.empty else None
            ema_indicator = EMAIndicator(value=ema_value, period=ema_period) if ema_value is not None else None
            
            # Calculate support/resistance
            support_val, resistance_val = self.calculate_support_resistance(data)
            support = SupportResistanceLevel(level=support_val, strength="moderate") if support_val else None
            resistance = SupportResistanceLevel(level=resistance_val, strength="moderate") if resistance_val else None
            
            # Calculate volume ratio
            volume_ratio = self.calculate_volume_ratio(data)
            
            return IndicatorSet(
                rsi=rsi_indicator,
                ema=ema_indicator,
                support=support,
                resistance=resistance,
                volume_ratio=volume_ratio
            )
            
        except IndicatorCalculationError:
            raise
        except Exception as e:
            error_msg = f"Failed to calculate indicators: {e}"
            logger.error(error_msg)
            raise IndicatorCalculationError(error_msg) from e
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Validate that data has sufficient rows and required columns
        
        Args:
            data: DataFrame to validate
            
        Returns:
            True if data is valid for indicator calculation
        """
        if data is None or data.empty:
            return False
        
        # Check for required columns
        required_columns = ['close']
        if not all(col in data.columns for col in required_columns):
            return False
        
        # Check minimum rows
        if len(data) < 10:
            return False
        
        return True
