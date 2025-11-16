"""
Indicator Service

Handles technical indicator calculation and analysis.
Extracted from core/analysis.py to improve modularity.

Phase 4: Updated to support infrastructure layer with backward compatibility.
"""

import pandas as pd
from typing import Optional, Dict, Any
import math

from utils.logger import logger
from config.strategy_config import StrategyConfig

# Phase 4: Support both core.* (backward compatible) and infrastructure
# Note: Currently using core.* as infrastructure still depends on it
# TODO Phase 4: Migrate to infrastructure once it's independent of core.*
from core.indicators import compute_indicators


class IndicatorService:
    """
    Service for calculating and analyzing technical indicators
    
    Phase 4: Currently uses core.* directly. Will migrate to infrastructure
    once infrastructure layer is independent of core.* modules.
    """
    
    def __init__(self, config: Optional[StrategyConfig] = None, indicator_calculator=None):
        """
        Initialize indicator service
        
        Args:
            config: Strategy configuration (uses default if None)
            indicator_calculator: Optional indicator calculator (for future infrastructure support)
        """
        self.config = config or StrategyConfig.default()
        # Phase 4: Support dependency injection for future infrastructure migration
        self.indicator_calculator = indicator_calculator
    
    def compute_indicators(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Compute technical indicators for a DataFrame
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with indicators added or None if computation fails
        """
        try:
            df_with_indicators = compute_indicators(df)
            if df_with_indicators is None or df_with_indicators.empty:
                logger.error("Failed to compute indicators")
                return None
            return df_with_indicators
        except Exception as e:
            logger.error(f"Error computing indicators: {e}")
            return None
    
    def get_rsi_value(self, row: pd.Series) -> Optional[float]:
        """
        Get RSI value from a row
        
        Args:
            row: Row containing indicator data
            
        Returns:
            RSI value or None if not available
        """
        try:
            rsi = row.get('rsi10')
            if pd.isna(rsi):
                return None
            return float(rsi)
        except Exception as e:
            logger.warning(f"Error getting RSI value: {e}")
            return None
    
    def is_rsi_oversold(
        self, 
        row: pd.Series, 
        threshold: Optional[float] = None
    ) -> bool:
        """
        Check if RSI is oversold
        
        Args:
            row: Row containing indicator data
            threshold: RSI threshold (uses config default if None)
            
        Returns:
            True if RSI is below threshold
        """
        if threshold is None:
            threshold = self.config.rsi_oversold
        
        rsi = self.get_rsi_value(row)
        if rsi is None:
            return False
        return rsi < threshold
    
    def is_above_ema200(self, row: pd.Series) -> bool:
        """
        Check if price is above EMA200
        
        Args:
            row: Row containing indicator data
            
        Returns:
            True if price > EMA200
        """
        try:
            close = row.get('close')
            ema200 = row.get('ema200')
            
            if pd.isna(close) or pd.isna(ema200):
                return False
            
            return close > ema200
        except Exception as e:
            logger.warning(f"Error checking EMA200: {e}")
            return False
    
    def get_ema200_value(self, row: pd.Series) -> Optional[float]:
        """
        Get EMA200 value from a row
        
        Args:
            row: Row containing indicator data
            
        Returns:
            EMA200 value or None if not available
        """
        try:
            ema200 = row.get('ema200')
            if pd.isna(ema200):
                return None
            return float(ema200)
        except Exception as e:
            logger.warning(f"Error getting EMA200 value: {e}")
            return None
    
    def get_indicators_summary(self, row: pd.Series) -> Dict[str, Any]:
        """
        Get summary of all indicators from a row
        
        Args:
            row: Row containing indicator data
            
        Returns:
            Dict with indicator values
        """
        return {
            'rsi10': self.get_rsi_value(row),
            'ema200': self.get_ema200_value(row),
            'is_oversold': self.is_rsi_oversold(row),
            'is_above_ema200': self.is_above_ema200(row),
        }
