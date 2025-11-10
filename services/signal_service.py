"""
Signal Service

Handles signal detection and pattern recognition.
Extracted from core/analysis.py to improve modularity.
"""

import pandas as pd
from typing import List, Optional, Dict, Any

from core.patterns import is_hammer, is_bullish_engulfing, bullish_divergence
from core.timeframe_analysis import TimeframeAnalysis
from core.news_sentiment import analyze_news_sentiment
from utils.logger import logger
from config.strategy_config import StrategyConfig


class SignalService:
    """Service for detecting trading signals and patterns"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        Initialize signal service
        
        Args:
            config: Strategy configuration (uses default if None)
        """
        self.config = config or StrategyConfig.default()
        self.tf_analyzer = TimeframeAnalysis(config=self.config)
    
    def detect_pattern_signals(
        self, 
        df: pd.DataFrame, 
        last: pd.Series, 
        prev: Optional[pd.Series]
    ) -> List[str]:
        """
        Detect pattern-based signals (hammer, bullish engulfing, divergence)
        
        Args:
            df: DataFrame with price data
            last: Latest row
            prev: Previous row (if available)
            
        Returns:
            List of detected signal names
        """
        signals = []
        
        try:
            # Hammer pattern
            if is_hammer(last):
                signals.append("hammer")
            
            # Bullish engulfing pattern
            if prev is not None and is_bullish_engulfing(prev, last):
                signals.append("bullish_engulfing")
            
            # Bullish divergence - use configurable RSI period
            if bullish_divergence(df, rsi_period=self.config.rsi_period, lookback_period=10):
                signals.append("bullish_divergence")
                
        except Exception as e:
            logger.warning(f"Error detecting pattern signals: {e}")
        
        return signals
    
    def detect_rsi_oversold_signal(
        self, 
        last: pd.Series, 
        rsi_threshold: Optional[float] = None
    ) -> bool:
        """
        Detect RSI oversold signal
        
        Args:
            last: Latest row
            rsi_threshold: RSI threshold (uses config default if None)
            
        Returns:
            True if RSI oversold signal detected
        """
        if rsi_threshold is None:
            rsi_threshold = self.config.rsi_oversold
        
        try:
            rsi = last.get('rsi10')
            if pd.isna(rsi):
                return False
            return rsi < rsi_threshold
        except Exception as e:
            logger.warning(f"Error detecting RSI oversold: {e}")
            return False
    
    def get_timeframe_confirmation(
        self, 
        daily_df: pd.DataFrame, 
        weekly_df: Optional[pd.DataFrame]
    ) -> Optional[Dict[str, Any]]:
        """
        Get multi-timeframe confirmation analysis
        
        Args:
            daily_df: Daily timeframe DataFrame
            weekly_df: Weekly timeframe DataFrame (if available)
            
        Returns:
            Timeframe confirmation dict or None if analysis fails
        """
        if weekly_df is None:
            return None
        
        try:
            confirmation = self.tf_analyzer.get_dip_buying_confirmation(
                daily_df, weekly_df
            )
            logger.debug(
                f"MTF analysis: {confirmation.get('confirmation')} "
                f"(score: {confirmation.get('alignment_score')})"
            )
            return confirmation
        except Exception as e:
            logger.warning(f"Multi-timeframe analysis failed: {e}")
            return None
    
    def add_timeframe_signals(
        self, 
        signals: List[str], 
        timeframe_confirmation: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        Add timeframe-based signals to signal list
        
        Args:
            signals: Existing signal list
            timeframe_confirmation: Timeframe confirmation dict
            
        Returns:
            Updated signal list with timeframe signals
        """
        if not timeframe_confirmation:
            return signals
        
        confirmation_type = timeframe_confirmation.get('confirmation', '')
        
        if confirmation_type == 'excellent_uptrend_dip':
            signals.append("excellent_uptrend_dip")
        elif confirmation_type == 'good_uptrend_dip':
            signals.append("good_uptrend_dip")
        elif confirmation_type == 'fair_uptrend_dip':
            signals.append("fair_uptrend_dip")
        
        return signals
    
    def get_news_sentiment(
        self, 
        ticker: str, 
        as_of_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get news sentiment analysis for a ticker
        
        Args:
            ticker: Stock ticker symbol
            as_of_date: Date for sentiment analysis
            
        Returns:
            News sentiment dict or None if analysis fails
        """
        if not self.config.news_sentiment_enabled:
            return None
        
        try:
            sentiment = analyze_news_sentiment(ticker, as_of_date=as_of_date)
            return sentiment
        except Exception as e:
            logger.warning(f"News sentiment analysis failed for {ticker}: {e}")
            return None
    
    def detect_all_signals(
        self,
        ticker: str,
        df: pd.DataFrame,
        last: pd.Series,
        prev: Optional[pd.Series],
        weekly_df: Optional[pd.DataFrame] = None,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Detect all signals for a ticker
        
        Args:
            ticker: Stock ticker symbol
            df: Daily DataFrame with price data
            last: Latest row
            prev: Previous row
            weekly_df: Weekly DataFrame (if available)
            as_of_date: Date for analysis
            
        Returns:
            Dict with all detected signals and analysis
        """
        # Pattern signals
        pattern_signals = self.detect_pattern_signals(df, last, prev)
        
        # RSI oversold signal
        rsi_oversold = self.detect_rsi_oversold_signal(last)
        if rsi_oversold:
            pattern_signals.append("rsi_oversold")
        
        # Timeframe confirmation
        timeframe_confirmation = None
        if weekly_df is not None:
            timeframe_confirmation = self.get_timeframe_confirmation(df, weekly_df)
            pattern_signals = self.add_timeframe_signals(pattern_signals, timeframe_confirmation)
        
        # News sentiment
        news_sentiment = self.get_news_sentiment(ticker, as_of_date)
        
        return {
            'signals': pattern_signals,
            'timeframe_confirmation': timeframe_confirmation,
            'news_sentiment': news_sentiment,
        }
