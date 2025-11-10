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
    
    def assess_fundamentals(
        self,
        pe: Optional[float],
        pb: Optional[float]
    ) -> Dict[str, Any]:
        """
        Assess fundamental quality with flexible logic for growth stocks
        
        FLEXIBLE FUNDAMENTAL FILTER (2025-11-09):
        - Keep negative PE filter for "avoid" (loss-making companies)
        - But allow "watch" verdict for growth stocks (negative PE) if PB ratio is reasonable (< 5.0)
        - Allow "buy" verdicts only for profitable companies (PE >= 0)
        
        Args:
            pe: Price-to-Earnings ratio (None if unavailable)
            pb: Price-to-Book ratio (None if unavailable)
            
        Returns:
            Dict with:
            - fundamental_ok: bool - True if PE >= 0 (allows "buy" verdicts)
            - fundamental_growth_stock: bool - True if PE < 0 AND PB < 5.0 (allows "watch" verdicts)
            - fundamental_avoid: bool - True if PE < 0 AND (PB is None OR PB >= 5.0) (forces "avoid")
            - fundamental_reason: str - Reason for the assessment
        """
        # Default: profitable company (PE >= 0)
        if pe is None or pe >= 0:
            return {
                'fundamental_ok': True,
                'fundamental_growth_stock': False,
                'fundamental_avoid': False,
                'fundamental_reason': 'profitable' if pe is not None else 'pe_unavailable'
            }
        
        # Negative PE (loss-making or growth stock)
        if pe < 0:
            # Check PB ratio to distinguish growth stocks from expensive loss-makers
            # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Use configurable PB threshold
            pb_threshold = getattr(self.config, 'pb_max_for_growth_stock', 5.0)
            if pb is not None and pb < pb_threshold:
                # Growth stock with reasonable PB ratio - allow "watch" verdict
                return {
                    'fundamental_ok': False,  # Cannot give "buy" verdict
                    'fundamental_growth_stock': True,  # Allow "watch" verdict
                    'fundamental_avoid': False,  # Don't force "avoid"
                    'fundamental_reason': f'pb={pb:.2f}<{pb_threshold}'
                }
            else:
                # Expensive loss-making company or unknown PB - force "avoid"
                pb_reason = f'pb={pb:.2f}' if pb is not None else 'pb_unavailable'
                return {
                    'fundamental_ok': False,
                    'fundamental_growth_stock': False,
                    'fundamental_avoid': True,  # Force "avoid" verdict
                    'fundamental_reason': f'loss_making_expensive({pb_reason}>={pb_threshold})'
                }
        
        # Should not reach here, but return safe default
        return {
            'fundamental_ok': True,
            'fundamental_growth_stock': False,
            'fundamental_avoid': False,
            'fundamental_reason': 'unknown'
        }
    
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
        disable_liquidity_filter: bool = False,
        rsi_value: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Assess volume quality for a stock
        
        Args:
            df: DataFrame with volume data
            last: Latest row
            disable_liquidity_filter: If True, skip the absolute volume liquidity filter
                                     (useful for backtesting where we want to see all opportunities)
            rsi_value: Optional RSI value for RSI-based volume threshold adjustment
                       If RSI < 30 (oversold), volume requirement is reduced to 0.5x
                       Otherwise, uses base threshold (0.7x after relaxation)
            
        Returns:
            Dict with volume analysis results
        """
        avg_vol = avg_volume(df)  # Uses config volume_lookback_days
        
        # Intelligent volume analysis with time-awareness and RSI-based adjustment
        # RELAXED VOLUME REQUIREMENTS (2025-11-09): RSI-based volume threshold adjustment
        # For dip-buying (RSI < 30), volume requirement is further reduced to 0.5x
        volume_analysis = assess_volume_quality_intelligent(
            current_volume=last['volume'],
            avg_volume=avg_vol,
            enable_time_adjustment=True,
            disable_liquidity_filter=disable_liquidity_filter,
            rsi_value=rsi_value
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
        chart_quality_passed: bool = True,
        fundamental_assessment: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[str]]:
        """
        Determine verdict (strong_buy/buy/watch/avoid) and justification
        
        Args:
            signals: List of detected signals
            rsi_value: Current RSI value
            is_above_ema200: Whether price is above EMA200
            vol_ok: Whether volume is adequate
            vol_strong: Whether volume is strong
            fundamental_ok: Whether fundamentals are acceptable (backward compatibility)
            timeframe_confirmation: MTF confirmation data
            news_sentiment: News sentiment data
            chart_quality_passed: Whether chart quality check passed (hard filter)
            fundamental_assessment: Optional fundamental assessment dict from assess_fundamentals()
                                    If provided, overrides fundamental_ok for more flexible logic
            
        Returns:
            Tuple of (verdict, justification_list)
        """
        # Hard filter: Chart quality check
        if not chart_quality_passed:
            return "avoid", ["Chart quality failed - too many gaps/extreme candles/flat movement"]
        
        # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Use fundamental_assessment if provided
        # Otherwise, fall back to fundamental_ok for backward compatibility
        if fundamental_assessment is not None:
            fundamental_ok_for_buy = fundamental_assessment.get('fundamental_ok', fundamental_ok)
            fundamental_growth_stock = fundamental_assessment.get('fundamental_growth_stock', False)
            fundamental_avoid = fundamental_assessment.get('fundamental_avoid', False)
            fundamental_reason = fundamental_assessment.get('fundamental_reason', 'unknown')
        else:
            # Backward compatibility: use fundamental_ok
            fundamental_ok_for_buy = fundamental_ok
            fundamental_growth_stock = False
            fundamental_avoid = False
            fundamental_reason = 'profitable' if fundamental_ok else 'loss_making'
        
        # Hard filter: Force "avoid" for expensive loss-making companies
        if fundamental_avoid:
            return "avoid", [f"Fundamental filter: {fundamental_reason}"]
        
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
        # Use fundamental_ok_for_buy for "buy" verdicts (requires profitable company)
        if rsi_oversold and decent_volume and fundamental_ok_for_buy:
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
            # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Allow "watch" for growth stocks
            if fundamental_growth_stock:
                # Growth stock (negative PE but reasonable PB) - allow "watch" verdict
                verdict = "watch"
            elif not fundamental_ok_for_buy and not fundamental_growth_stock:
                # Loss-making company but not a growth stock - "avoid"
                verdict = "avoid"
            else:
                # Normal case: partial signals
                verdict = "watch"
        
        else:
            # No significant signals
            # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Allow "watch" for growth stocks with strong conditions
            if fundamental_growth_stock and (rsi_oversold or vol_strong):
                # Growth stock with some strong conditions - allow "watch"
                verdict = "watch"
            else:
                # No signals and not a growth stock - "avoid"
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
            # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Add growth stock justification
            if fundamental_growth_stock:
                # Growth stock - add to justification
                justification.append(f"growth_stock({fundamental_reason})")
            elif not fundamental_ok_for_buy:
                justification.append("fundamental_red_flag")
            
            if len(signals) > 0:
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
        df: pd.DataFrame,
        rsi_value: Optional[float] = None,
        is_above_ema200: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate trading parameters (buy_range, target, stop)
        
        CRITICAL REQUIREMENT (2025-11-09): RSI10 < 30 is a key requirement for the dip-buying strategy.
        Trading parameters are ONLY calculated when RSI < 30 (or RSI < 20 if below EMA200).
        
        Args:
            current_price: Current stock price
            verdict: Verdict (strong_buy/buy)
            recent_low: Recent low price
            recent_high: Recent high price
            timeframe_confirmation: MTF confirmation data
            df: DataFrame with price data
            rsi_value: Current RSI value (required for RSI check)
            is_above_ema200: Whether price is above EMA200 (for threshold selection)
            
        Returns:
            Dict with buy_range, target, stop values or None if verdict doesn't require trading params or RSI >= 30
        """
        # CRITICAL: Only calculate trading parameters for buy/strong_buy verdicts
        if verdict not in ["buy", "strong_buy"]:
            return None
        
        # CRITICAL REQUIREMENT (2025-11-09): RSI10 < 30 is a key requirement
        # Do NOT calculate trading parameters when RSI >= 30
        if rsi_value is not None:
            # Determine RSI threshold based on EMA200 position
            if is_above_ema200:
                rsi_threshold = self.config.rsi_oversold  # 30 - Standard oversold in uptrend
            else:
                rsi_threshold = self.config.rsi_extreme_oversold  # 20 - Extreme oversold when below trend
            
            # Only calculate trading parameters if RSI < threshold
            if rsi_value >= rsi_threshold:
                logger.warning(f"Trading parameters NOT calculated: RSI {rsi_value:.1f} >= {rsi_threshold} (RSI10 < {rsi_threshold} required for dip-buying strategy)")
                return None
        else:
            # If RSI is None/unavailable, log warning and don't calculate
            logger.warning(f"Trading parameters NOT calculated: RSI value is None (RSI10 < 30 required for dip-buying strategy)")
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

