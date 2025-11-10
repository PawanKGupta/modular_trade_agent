"""
Intelligent Volume Analysis Module

Provides time-aware and context-sensitive volume analysis for trading decisions.
"""

import pandas as pd
from datetime import datetime, time
from typing import Dict, Tuple, Optional
from utils.logger import logger
from config.settings import (
    MIN_VOLUME_MULTIPLIER,
    MIN_ABSOLUTE_AVG_VOLUME,
    VOLUME_MULTIPLIER_FOR_STRONG,
    VOLUME_INTRADAY_MULTIPLIER,
    VOLUME_MARKET_CLOSE_HOUR,
    VOLUME_FLEXIBLE_THRESHOLD,
    VOLUME_QUALITY_EXCELLENT,
    VOLUME_QUALITY_GOOD,
    VOLUME_QUALITY_FAIR
)


def get_current_market_time() -> float:
    """Get current time as fractional hour in IST (e.g., 15.5 for 3:30 PM)"""
    try:
        now = datetime.now()
        # If running in UTC, convert to IST (+5:30)
        # For simplicity, assuming local time is IST
        return now.hour + now.minute / 60.0
    except Exception:
        return 15.5  # Default to market close hour

def get_current_market_hour() -> int:
    """Get current hour in IST for backward compatibility"""
    return int(get_current_market_time())


def is_market_hours() -> bool:
    """Check if current time is during market hours (9:15 AM to 3:30 PM IST)"""
    current_time = get_current_market_time()
    # Market is open from 9:15 AM (9.25) to 3:30 PM (15.5) IST
    return 9.25 <= current_time <= 15.5


def get_intraday_volume_factor(current_time: Optional[float] = None) -> float:
    """
    Calculate volume adjustment factor based on time of day
    
    Args:
        current_time: Current time as fractional hour (e.g., 15.5 for 3:30 PM)
    
    Returns multiplier to adjust volume expectations for intraday analysis
    """
    if current_time is None:
        current_time = get_current_market_time()
    
    # Volume typically builds throughout the day
    # Adjust expectations based on market hours (using fractional hours)
    if current_time <= 10.0:  # Early morning (9:15-10:00 AM)
        return 0.3  # Expect only 30% of daily volume
    elif current_time <= 12.0:  # Mid-morning (10:00-12:00 PM)
        return 0.5  # Expect 50% of daily volume
    elif current_time <= 14.0:  # Afternoon (12:00-2:00 PM)
        return 0.7  # Expect 70% of daily volume
    elif current_time <= 15.5:  # Late afternoon (2:00-3:30 PM)
        return 0.85  # Expect 85% of daily volume
    else:  # After market hours (after 3:30 PM)
        return 1.0  # Full daily volume expected
        

def assess_volume_quality_intelligent(
    current_volume: float, 
    avg_volume: float,
    current_hour: Optional[int] = None,
    enable_time_adjustment: bool = True,
    disable_liquidity_filter: bool = False,
    rsi_value: Optional[float] = None
) -> Dict[str, any]:
    """
    Intelligent volume quality assessment with time-awareness and RSI-based adjustment
    
    Args:
        current_volume: Current/today's volume
        avg_volume: Average volume (typically 20-day)
        current_hour: Current market hour (None for auto-detect)
        enable_time_adjustment: Enable time-based adjustments
        disable_liquidity_filter: If True, skip the absolute volume liquidity filter
                                  (useful for backtesting where we want to see all opportunities)
        rsi_value: Optional RSI value for RSI-based volume threshold adjustment
                   If RSI < 30 (oversold), volume requirement is reduced to 0.5x
                   Otherwise, uses base threshold (MIN_VOLUME_MULTIPLIER, default: 0.7x)
        
    Returns:
        Dict with volume analysis results
    """
    if avg_volume <= 0:
        return {
            'ratio': 0,
            'quality': 'unknown',
            'score': 0,
            'threshold_used': MIN_VOLUME_MULTIPLIER,
            'passes': False,
            'time_adjusted': False,
            'avg_volume': 0,
            'reason': 'No historical volume data'
        }
    
    # Check absolute volume first (liquidity filter) - now minimal safety net only
    # Actual capital adjustment handled by LiquidityCapitalService
    # This check is kept as a minimal safety net for truly illiquid stocks
    # Skip this check if disable_liquidity_filter is True (for backtesting)
    if not disable_liquidity_filter and avg_volume < MIN_ABSOLUTE_AVG_VOLUME:
        return {
            'ratio': round(current_volume / avg_volume, 2) if avg_volume > 0 else 0,
            'quality': 'illiquid',
            'score': 0,
            'threshold_used': MIN_VOLUME_MULTIPLIER,
            'passes': False,
            'time_adjusted': False,
            'avg_volume': int(avg_volume),
            'reason': f'Low liquidity: avg_volume={int(avg_volume)} < {MIN_ABSOLUTE_AVG_VOLUME}'
        }
    
    base_ratio = current_volume / avg_volume
    
    # RSI-based volume threshold adjustment (2025-11-09)
    # For dip-buying (RSI < 30), volume requirement is further reduced to 0.5x
    # Oversold conditions often have lower volume (selling pressure)
    base_threshold = MIN_VOLUME_MULTIPLIER  # Default: 0.7x (relaxed from 1.0x)
    
    # Apply RSI-based adjustment if RSI is provided and indicates oversold condition
    if rsi_value is not None:
        try:
            rsi_float = float(rsi_value)
            if rsi_float < 30:
                # Oversold condition: reduce volume requirement to 0.5x
                base_threshold = 0.5
                logger.debug(f"Volume threshold adjusted for oversold (RSI={rsi_float:.1f}): {base_threshold}x")
        except (TypeError, ValueError):
            # If RSI value cannot be converted to float, use default threshold
            logger.debug(f"RSI value invalid for volume adjustment: {rsi_value}, using default threshold")
    
    # Time adjustment
    time_adjusted = False
    adjusted_threshold = base_threshold
    
    if enable_time_adjustment:
        # Get the time to use for analysis (support both hour int and fractional time)
        if current_hour is not None:
            analysis_time = float(current_hour)  # Convert int hour to float
        else:
            analysis_time = get_current_market_time()  # Get precise fractional time
        
        # Apply time adjustment if time is during market hours or explicitly provided
        is_market_time = 9.25 <= analysis_time <= 15.5  # 9:15 AM to 3:30 PM
        should_adjust = current_hour is not None or is_market_hours()
        
        if should_adjust and is_market_time and analysis_time < VOLUME_MARKET_CLOSE_HOUR:
            time_factor = get_intraday_volume_factor(analysis_time)
            adjusted_threshold = base_threshold * time_factor
            # Ensure adjusted threshold doesn't go below flexible threshold (0.4x)
            adjusted_threshold = max(adjusted_threshold, VOLUME_FLEXIBLE_THRESHOLD)
            time_adjusted = True
            current_hour = int(analysis_time)  # Store as int for return value
            
            logger.debug(f"Volume time adjustment: time={analysis_time:.1f}, factor={time_factor:.2f}, base={base_threshold:.2f}, threshold={adjusted_threshold:.2f}")
    
    # Volume quality assessment
    # RELAXED VOLUME REQUIREMENTS (2025-11-09): Use adjusted_threshold (which includes RSI-based adjustment)
    # The threshold has already been adjusted based on RSI (0.5x for RSI < 30, 0.7x otherwise)
    quality = 'poor'
    score = 0
    passes = False
    
    if base_ratio >= VOLUME_QUALITY_EXCELLENT:
        quality = 'excellent'
        score = 3
        passes = True
    elif base_ratio >= VOLUME_QUALITY_GOOD:
        quality = 'good' 
        score = 2
        passes = True
    elif base_ratio >= VOLUME_QUALITY_FAIR:
        quality = 'fair'
        score = 1
        # For fair quality, check if it meets the adjusted threshold (RSI-aware)
        passes = base_ratio >= adjusted_threshold
    elif base_ratio >= adjusted_threshold:
        # Volume meets the adjusted threshold (which may be 0.5x for oversold or 0.7x normally)
        quality = 'minimal'
        score = 1
        passes = True
    else:
        quality = 'poor'
        score = 0
        passes = False
    
    # Build reason
    reasons = []
    if time_adjusted:
        reasons.append(f"intraday_adjusted(hour={current_hour})")
    
    if passes:
        reasons.append(f"meets_threshold({adjusted_threshold:.2f})")
    else:
        reasons.append(f"below_threshold({adjusted_threshold:.2f})")
        
    if base_ratio >= VOLUME_MULTIPLIER_FOR_STRONG:
        reasons.append("strong_volume")
    
    return {
        'ratio': round(base_ratio, 2),
        'quality': quality,
        'score': score,
        'threshold_used': round(adjusted_threshold, 2),
        'passes': passes,
        'time_adjusted': time_adjusted,
        'current_hour': current_hour if time_adjusted else None,
        'avg_volume': int(avg_volume),
        'reason': ' + '.join(reasons) if reasons else 'low_volume'
    }


def get_volume_verdict(volume_analysis: Dict) -> Tuple[bool, bool, str]:
    """
    Get volume-based trading verdict
    
    Args:
        volume_analysis: Result from assess_volume_quality_intelligent
        
    Returns:
        Tuple of (vol_ok, vol_strong, description)
    """
    vol_ok = volume_analysis['passes']
    vol_strong = volume_analysis['ratio'] >= VOLUME_MULTIPLIER_FOR_STRONG
    
    # Create descriptive text
    ratio = volume_analysis['ratio']
    quality = volume_analysis['quality']
    
    if vol_strong:
        description = f"Strong volume ({ratio}x avg, {quality})"
    elif vol_ok:
        description = f"Adequate volume ({ratio}x avg, {quality})"
    else:
        description = f"Low volume ({ratio}x avg, {quality})"
        
    if volume_analysis['time_adjusted']:
        description += f" [intraday adj.]"
    
    return vol_ok, vol_strong, description


def analyze_volume_pattern(df: pd.DataFrame, lookback_days: int = 20) -> Dict:
    """
    Analyze volume patterns over time to provide additional context
    
    Args:
        df: DataFrame with volume data
        lookback_days: Number of days to analyze
        
    Returns:
        Dict with volume pattern analysis
    """
    try:
        if df is None or df.empty or 'volume' not in df.columns:
            return {'pattern': 'unknown', 'context': 'No data'}
        
        recent_volumes = df['volume'].tail(lookback_days)
        if len(recent_volumes) < 5:
            return {'pattern': 'insufficient_data', 'context': 'Not enough volume history'}
        
        avg_volume = recent_volumes.mean()
        current_volume = recent_volumes.iloc[-1]
        
        # Calculate volume trends
        recent_5day_avg = recent_volumes.tail(5).mean()
        previous_5day_avg = recent_volumes.iloc[-10:-5].mean() if len(recent_volumes) >= 10 else avg_volume
        
        trend_ratio = recent_5day_avg / previous_5day_avg if previous_5day_avg > 0 else 1.0
        
        # Volume volatility
        volume_std = recent_volumes.std()
        volume_cv = volume_std / avg_volume if avg_volume > 0 else 0  # Coefficient of variation
        
        # Pattern classification
        if trend_ratio > 1.2:
            pattern = 'increasing'
        elif trend_ratio < 0.8:
            pattern = 'decreasing'
        else:
            pattern = 'stable'
            
        # Volatility assessment
        if volume_cv > 1.0:
            volatility = 'high'
        elif volume_cv > 0.5:
            volatility = 'moderate'
        else:
            volatility = 'low'
        
        context_parts = [f"trend: {pattern}", f"volatility: {volatility}"]
        
        return {
            'pattern': pattern,
            'trend_ratio': round(trend_ratio, 2),
            'volatility': volatility,
            'volume_cv': round(volume_cv, 2),
            'context': ', '.join(context_parts),
            'avg_volume': avg_volume,
            'current_volume': current_volume
        }
        
    except Exception as e:
        logger.warning(f"Error analyzing volume pattern: {e}")
        return {'pattern': 'error', 'context': f'Analysis failed: {str(e)}'}
