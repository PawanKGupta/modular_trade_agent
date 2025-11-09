"""
Verdict Service

Handles verdict determination and trading parameter calculation.
Extracted from core/analysis.py to improve modularity.
"""

import pandas as pd
from typing import Optional, Dict, Any, Tuple, List
import math
import threading

from core.volume_analysis import assess_volume_quality_intelligent, get_volume_verdict, analyze_volume_pattern
from core.candle_analysis import analyze_recent_candle_quality, should_downgrade_signal
from core.analysis import (
    avg_volume,
    calculate_smart_buy_range,
    calculate_smart_stop_loss,
    calculate_smart_target
)
import yfinance as yf

from utils.logger import logger
from utils.circuit_breaker import CircuitBreaker
from utils.retry_handler import exponential_backoff_retry
from config.strategy_config import StrategyConfig
from config.settings import (
    RETRY_MAX_ATTEMPTS, RETRY_BASE_DELAY, RETRY_MAX_DELAY, RETRY_BACKOFF_MULTIPLIER,
    CIRCUITBREAKER_FAILURE_THRESHOLD, CIRCUITBREAKER_RECOVERY_TIMEOUT,
    API_RATE_LIMIT_DELAY
)
from services.chart_quality_service import ChartQualityService
from services.liquidity_capital_service import LiquidityCapitalService

# Rate limiting for fundamental data API calls
# IMPORTANT: Share the same rate limiter as OHLCV data since they hit the same Yahoo Finance API
# This prevents hitting rate limits by spacing out ALL API calls (OHLCV + fundamental)
import time
# Import the rate limiting function from data_fetcher to share the same limiter
from core.data_fetcher import _enforce_rate_limit

# Circuit breaker configuration for fundamental data API calls
# Use same configuration as OHLCV data fetching for consistency
# Create circuit breaker for yfinance fundamental API with configurable parameters
yfinance_fundamental_circuit_breaker = CircuitBreaker(
    name="YFinance_Fundamental_API",
    failure_threshold=CIRCUITBREAKER_FAILURE_THRESHOLD,
    recovery_timeout=CIRCUITBREAKER_RECOVERY_TIMEOUT
)

# Create retry decorator with configurable parameters (same as OHLCV data fetching)
api_retry_configured = exponential_backoff_retry(
    max_retries=RETRY_MAX_ATTEMPTS,
    base_delay=RETRY_BASE_DELAY,
    max_delay=RETRY_MAX_DELAY,
    backoff_multiplier=RETRY_BACKOFF_MULTIPLIER,
    jitter=True,
    exceptions=(Exception,)
)

# In-memory cache for fundamental data (FIX 3: Cache fundamental data)
_fundamental_cache = {}
_cache_lock = threading.Lock()


class VerdictService:
    """Service for determining verdicts and calculating trading parameters"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        Initialize verdict service
        
        Args:
            config: Strategy configuration (uses default if None)
        """
        self.config = config or StrategyConfig.default()
        self.chart_quality_service = ChartQualityService(config=self.config)
        self.liquidity_capital_service = LiquidityCapitalService(config=self.config)
    
    def fetch_fundamentals(self, ticker: str) -> Dict[str, Optional[float]]:
        """
        Fetch fundamental data (PE, PB ratios)
        
        FIX 2: Protected with circuit breaker and retry handler
        FIX 3: Cached to avoid duplicate API calls
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dict with pe and pb values
        """
        # FIX 3: Check cache first
        with _cache_lock:
            if ticker in _fundamental_cache:
                logger.debug(f"Using cached fundamental data for {ticker}")
                return _fundamental_cache[ticker].copy()
        
        # FIX 2: Fetch with circuit breaker and retry protection
        try:
            data = self._fetch_fundamentals_protected(ticker)
            
            # FIX 3: Store in cache
            with _cache_lock:
                _fundamental_cache[ticker] = data.copy()
            
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch fundamental data for {ticker}: {e}")
            return {'pe': None, 'pb': None}
    
    @yfinance_fundamental_circuit_breaker
    @api_retry_configured
    def _fetch_fundamentals_protected(self, ticker: str) -> Dict[str, Optional[float]]:
        """
        Protected method to fetch fundamental data with circuit breaker and retry
        
        FIX 2: This method is protected by circuit breaker and retry handler
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dict with pe and pb values
        """
        try:
            # Rate limiting: Use same rate limiter as OHLCV data (shared API endpoint)
            # This ensures all Yahoo Finance API calls (OHLCV + fundamental) are spaced out
            _enforce_rate_limit(api_type=f"Fundamental ({ticker})")
            
            logger.debug(f"Fetching fundamental data for {ticker}")
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            
            # Handle case where info is None or empty
            if not info or not isinstance(info, dict):
                logger.warning(f"Fundamental data for {ticker}: Empty or invalid response from YFinance API")
                return {'pe': None, 'pb': None}
            
            pe = info.get('trailingPE', None)
            pb = info.get('priceToBook', None)
            
            # Log if values are missing (but not an error)
            if pe is None or pb is None:
                logger.debug(f"Fundamental data for {ticker}: PE={pe}, PB={pb} (some values may be unavailable)")
            else:
                logger.debug(f"Fundamental data for {ticker}: PE={pe}, PB={pb}")
            
            return {'pe': pe, 'pb': pb}
        except KeyError as e:
            logger.warning(f"Could not fetch fundamental data for {ticker}: Missing key in API response - {e}")
            return {'pe': None, 'pb': None}
        except AttributeError as e:
            # Handle "argument of type 'NoneType' is not iterable" or similar
            logger.warning(f"Could not fetch fundamental data for {ticker}: API response format issue - {e}")
            return {'pe': None, 'pb': None}
        except Exception as e:
            error_msg = str(e)
            # Provide more specific error messages
            if 'NoneType' in error_msg:
                logger.warning(f"Could not fetch fundamental data for {ticker}: API returned None (data may be unavailable for this ticker)")
            elif '401' in error_msg or 'Unauthorized' in error_msg:
                logger.warning(f"Could not fetch fundamental data for {ticker}: API authentication error (rate limiting or access issue)")
            else:
                logger.warning(f"Could not fetch fundamental data for {ticker}: {error_msg}")
            # Re-raise to trigger circuit breaker
            raise
    
    def assess_chart_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Assess chart quality for a stock
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Dict with chart quality analysis results
        """
        return self.chart_quality_service.assess_chart_quality(df)
    
    def check_chart_quality(self, df: pd.DataFrame) -> bool:
        """
        Check if chart quality is acceptable (hard filter)
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            True if chart is acceptable, False otherwise
        """
        return self.chart_quality_service.is_chart_acceptable(df)
    
    def calculate_execution_capital(
        self,
        avg_volume: float,
        stock_price: float,
        user_capital: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate execution capital based on liquidity
        
        Args:
            avg_volume: Average daily volume
            stock_price: Current stock price
            user_capital: User's configured capital (optional, uses config default)
            
        Returns:
            Dict with execution capital details
        """
        return self.liquidity_capital_service.calculate_execution_capital(
            user_capital=user_capital,
            avg_volume=avg_volume,
            stock_price=stock_price
        )
    
    def assess_volume(
        self, 
        df: pd.DataFrame, 
        last: pd.Series,
        disable_liquidity_filter: bool = False
    ) -> Dict[str, Any]:
        """
        Assess volume quality for a stock
        
        Args:
            df: DataFrame with volume data
            last: Latest row
            disable_liquidity_filter: If True, skip the absolute volume liquidity filter
                                     (useful for backtesting where we want to see all opportunities)
            
        Returns:
            Dict with volume analysis results
        """
        avg_vol = avg_volume(df)  # Uses config volume_lookback_days
        
        # Intelligent volume analysis with time-awareness
        volume_analysis = assess_volume_quality_intelligent(
            current_volume=last['volume'],
            avg_volume=avg_vol,
            enable_time_adjustment=True,
            disable_liquidity_filter=disable_liquidity_filter
        )
        
        vol_ok, vol_strong, volume_description = get_volume_verdict(volume_analysis)
        
        # Log low liquidity stocks
        if volume_analysis.get('quality') == 'illiquid':
            logger.info(f"Filtered out - {volume_analysis.get('reason')}")
        
        # Additional volume pattern context
        volume_pattern = analyze_volume_pattern(df)
        
        # Calculate execution capital based on liquidity
        stock_price = last['close']
        execution_capital_data = self.calculate_execution_capital(
            avg_volume=avg_vol,
            stock_price=stock_price
        )
        
        return {
            'volume_analysis': volume_analysis,
            'vol_ok': vol_ok,
            'vol_strong': vol_strong,
            'volume_description': volume_description,
            'volume_pattern': volume_pattern,
            'avg_vol': avg_vol,
            'today_vol': last['volume'],
            'execution_capital': execution_capital_data.get('execution_capital', 0.0),
            'max_capital': execution_capital_data.get('max_capital', 0.0),
            'capital_adjusted': execution_capital_data.get('capital_adjusted', False),
            'liquidity_recommendation': execution_capital_data,
        }
    
    def determine_verdict(
        self,
        signals: List[str],
        rsi_value: Optional[float],
        is_above_ema200: bool,
        vol_ok: bool,
        vol_strong: bool,
        fundamental_ok: bool,
        timeframe_confirmation: Optional[Dict[str, Any]],
        news_sentiment: Optional[Dict[str, Any]],
        chart_quality_passed: bool = True
    ) -> Tuple[str, List[str]]:
        """
        Determine verdict (strong_buy/buy/watch/avoid) and justification
        
        Args:
            signals: List of detected signals
            rsi_value: Current RSI value
            is_above_ema200: Whether price is above EMA200
            vol_ok: Whether volume is adequate
            vol_strong: Whether volume is strong
            fundamental_ok: Whether fundamentals are acceptable
            timeframe_confirmation: MTF confirmation data
            news_sentiment: News sentiment data
            chart_quality_passed: Whether chart quality check passed (hard filter)
            
        Returns:
            Tuple of (verdict, justification_list)
        """
        # Hard filter: Chart quality check
        if not chart_quality_passed:
            return "avoid", ["Chart quality failed - too many gaps/extreme candles/flat movement"]
        
        verdict = "avoid"
        justification = []
        
        # Adaptive RSI threshold based on EMA200 position
        if is_above_ema200:
            rsi_threshold = self.config.rsi_oversold  # 30 - Standard oversold in uptrend
        else:
            rsi_threshold = self.config.rsi_extreme_oversold  # 20 - Extreme oversold required when below trend
        
        rsi_oversold = rsi_value is not None and rsi_value < rsi_threshold
        decent_volume = vol_ok
        
        # Entry logic: Works for both above and below EMA200 with appropriate RSI thresholds
        if rsi_oversold and decent_volume and fundamental_ok:
            # Simple quality-based classification using MTF and patterns
            alignment_score = timeframe_confirmation.get('alignment_score', 0) if timeframe_confirmation else 0
            
            # Determine signal strength based on EMA200 position and RSI level
            if is_above_ema200:
                # Above EMA200: Standard uptrend dip buying (RSI < 30)
                if alignment_score >= self.config.mtf_alignment_excellent or "excellent_uptrend_dip" in signals:
                    verdict = "strong_buy"
                elif (alignment_score >= self.config.mtf_alignment_fair or 
                      any(s in signals for s in ["good_uptrend_dip", "fair_uptrend_dip", "hammer", "bullish_engulfing"]) or
                      vol_strong):
                    verdict = "buy"
                else:
                    verdict = "buy"  # Default for valid uptrend reversal conditions
            else:
                # Below EMA200: Extreme oversold reversal (RSI < 20)
                # More conservative - only buy with strong confirmation
                if (alignment_score >= self.config.mtf_alignment_good or 
                    any(s in signals for s in ["hammer", "bullish_engulfing", "bullish_divergence"]) or
                    vol_strong):
                    verdict = "buy"  # Require stronger signals when below trend
                else:
                    verdict = "watch"  # Default to watch for below-trend stocks
        
        elif len(signals) > 0 and vol_ok:
            # Has some signals and volume but not core reversal conditions
            verdict = "watch"
        
        else:
            # No significant signals
            verdict = "avoid"
        
        # Build justification based on what was found
        if verdict in ["buy", "strong_buy"]:
            # Add core reversal justification with adaptive threshold info
            if rsi_oversold and rsi_value is not None:
                trend_status = "above_ema200" if is_above_ema200 else "below_ema200"
                justification.append(f"rsi:{rsi_value:.1f}({trend_status})")
            
            # Add pattern signals (excluding MTF signals)
            pattern_signals = [s for s in signals if s not in ["excellent_uptrend_dip", "good_uptrend_dip", "fair_uptrend_dip"]]
            if pattern_signals:
                justification.append("pattern:" + ",".join(pattern_signals))
            
            # Add MTF uptrend dip confirmation
            if "excellent_uptrend_dip" in signals:
                justification.append("excellent_uptrend_dip_confirmation")
            elif "good_uptrend_dip" in signals:
                justification.append("good_uptrend_dip_confirmation")
            elif "fair_uptrend_dip" in signals:
                justification.append("fair_uptrend_dip_confirmation")
            
            # Add volume information
            if vol_strong:
                justification.append(f"volume_strong")
            elif decent_volume:
                justification.append(f"volume_adequate")
        
        elif verdict == "watch":
            if not fundamental_ok:
                justification.append("fundamental_red_flag")
            elif len(signals) > 0:
                justification.append("signals:" + ",".join(signals))
            else:
                justification.append("partial_reversal_setup")
        
        # Apply news sentiment adjustment (downgrade on negative news)
        if news_sentiment and news_sentiment.get('enabled') and verdict in ["buy", "strong_buy"]:
            sc = float(news_sentiment.get('score', 0.0))
            used = int(news_sentiment.get('used', 0))
            if used >= 1 and sc <= self.config.news_sentiment_neg_threshold:
                verdict = "watch"
                justification.append("news_negative")
        
        return verdict, justification
    
    def apply_candle_quality_check(
        self,
        df: pd.DataFrame,
        verdict: str
    ) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
        """
        Apply candle quality analysis and potentially downgrade verdict
        
        Args:
            df: DataFrame with price data
            verdict: Current verdict
            
        Returns:
            Tuple of (updated_verdict, candle_analysis_dict, downgrade_reason)
        """
        if verdict not in ["buy", "strong_buy"]:
            return verdict, None, None
        
        try:
            candle_analysis = analyze_recent_candle_quality(df, lookback_candles=3)
            
            # Apply candle-based verdict downgrade if needed
            original_verdict = verdict
            verdict, downgrade_reason = should_downgrade_signal(candle_analysis, verdict)
            
            if downgrade_reason:
                logger.info(f"Candle quality downgrade: {downgrade_reason}")
            
            return verdict, candle_analysis, downgrade_reason
            
        except Exception as e:
            logger.warning(f"Candle quality analysis failed: {e}")
            return verdict, None, None
    
    def calculate_trading_parameters(
        self,
        current_price: float,
        verdict: str,
        recent_low: float,
        recent_high: float,
        timeframe_confirmation: Optional[Dict[str, Any]],
        df: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate trading parameters (buy_range, target, stop)
        
        Args:
            current_price: Current stock price
            verdict: Verdict (strong_buy/buy)
            recent_low: Recent low price
            recent_high: Recent high price
            timeframe_confirmation: MTF confirmation data
            df: DataFrame with price data
            
        Returns:
            Dict with buy_range, target, stop values or None if verdict doesn't require trading params
        """
        if verdict not in ["buy", "strong_buy"]:
            return None
        
        # Enhanced buy range based on support levels
        buy_range = calculate_smart_buy_range(current_price, timeframe_confirmation)
        
        # Enhanced stop loss based on uptrend context and support
        stop = calculate_smart_stop_loss(current_price, recent_low, timeframe_confirmation, df)
        
        # Enhanced target based on MTF quality and resistance levels
        target = calculate_smart_target(current_price, stop, verdict, timeframe_confirmation, recent_high)
        
        return {
            'buy_range': buy_range,
            'target': target,
            'stop': stop
        }

