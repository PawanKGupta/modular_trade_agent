"""
Candle Analysis Module

Analyzes recent candle patterns to assess reversal potential.
Large red body candles with minimal wicks often indicate continued selling pressure
despite oversold RSI conditions, reducing reversal probability.
"""

import pandas as pd
import numpy as np
from datetime import datetime, time

# Robust logging import
try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)


def calculate_candle_metrics(row):
    """
    Calculate basic candle metrics for a single candle.

    Args:
        row: DataFrame row with OHLC data

    Returns:
        dict: Candle metrics including body size, wicks, etc.
    """
    try:
        open_price = row["open"]
        high_price = row["high"]
        low_price = row["low"]
        close_price = row["close"]

        # Basic measurements
        total_range = high_price - low_price
        body_size = abs(close_price - open_price)
        upper_wick = high_price - max(open_price, close_price)
        lower_wick = min(open_price, close_price) - low_price

        # Handle zero division
        if total_range == 0:
            total_range = 1e-6

        # Calculate ratios
        body_ratio = body_size / total_range
        upper_wick_ratio = upper_wick / total_range
        lower_wick_ratio = lower_wick / total_range

        # Determine candle type
        is_red = close_price < open_price
        is_green = close_price > open_price
        is_doji = body_ratio < 0.1

        return {
            "total_range": total_range,
            "body_size": body_size,
            "body_ratio": body_ratio,
            "upper_wick": upper_wick,
            "lower_wick": lower_wick,
            "upper_wick_ratio": upper_wick_ratio,
            "lower_wick_ratio": lower_wick_ratio,
            "is_red": is_red,
            "is_green": is_green,
            "is_doji": is_doji,
            "close": close_price,
            "open": open_price,
            "high": high_price,
            "low": low_price,
        }

    except Exception as e:
        logger.warning(f"Error calculating candle metrics: {e}")
        return None


def calculate_market_context(df, lookback_days=20):
    """
    Calculate market context for better candle size assessment.

    Args:
        df: DataFrame with OHLC data
        lookback_days: Days to look back for context calculation

    Returns:
        dict: Market context metrics
    """
    try:
        recent_data = df.tail(lookback_days) if len(df) >= lookback_days else df

        # Calculate average daily ranges
        daily_ranges = recent_data["high"] - recent_data["low"]
        avg_daily_range = daily_ranges.mean()

        # Calculate average volume
        avg_volume = recent_data["volume"].mean() if "volume" in recent_data.columns else 1

        # Calculate average price level for percentage calculations
        avg_price_level = recent_data["close"].mean()

        return {
            "avg_daily_range": avg_daily_range,
            "avg_volume": avg_volume,
            "avg_price_level": avg_price_level,
            "volatility_pct": (avg_daily_range / avg_price_level) * 100,
            "lookback_days": len(recent_data),
        }

    except Exception as e:
        logger.warning(f"Error calculating market context: {e}")
        return {
            "avg_daily_range": 1,
            "avg_volume": 1,
            "avg_price_level": 100,
            "volatility_pct": 1.0,
            "lookback_days": 0,
        }


def is_truly_large_candle(metrics, market_context, volume_ratio=None):
    """
    Determine if a candle is truly 'large' using multiple criteria.

    Args:
        metrics: Candle metrics from calculate_candle_metrics()
        market_context: Market context from calculate_market_context()
        volume_ratio: Current volume / average volume (optional)

    Returns:
        dict: Assessment of candle size with reasoning
    """

    try:
        assessments = []
        large_score = 0
        max_score = 4  # Total possible score

        # 1. Body Size vs Recent Average Range (most important)
        avg_range = market_context["avg_daily_range"]
        if avg_range > 0:
            body_vs_avg_range = metrics["body_size"] / avg_range
            if body_vs_avg_range > 0.8:  # Body is 80% of average daily range
                large_score += 2
                assessments.append(f"Body {body_vs_avg_range:.1f}x avg range")
            elif body_vs_avg_range > 0.5:  # Body is 50% of average daily range
                large_score += 1
                assessments.append(f"Body {body_vs_avg_range:.1f}x avg range")

        # 2. Absolute Price Movement Percentage
        price_decline_pct = (
            (metrics["body_size"] / metrics["open"]) * 100 if metrics["open"] > 0 else 0
        )
        if price_decline_pct > 4.0:  # 4%+ decline
            large_score += 1
            assessments.append(f"{price_decline_pct:.1f}% price decline")
        elif price_decline_pct > 2.5:  # 2.5%+ decline
            large_score += 0.5
            assessments.append(f"{price_decline_pct:.1f}% price decline")

        # 3. High Body Ratio (within the candle's own range)
        if metrics["body_ratio"] > 0.85:  # 85%+ of the candle is body
            large_score += 0.5
            assessments.append(f"High body ratio {metrics['body_ratio']:.1%}")

        # 4. Volume Confirmation (if available)
        if volume_ratio is not None:
            if volume_ratio > 1.5:  # Above average volume
                large_score += 0.5
                assessments.append(f"High volume {volume_ratio:.1f}x")

        # Determine final assessment
        is_large = large_score >= 2.0  # Need at least 2 points to be considered "large"

        # Severity levels
        if large_score >= 3.5:
            severity = "extreme"
        elif large_score >= 2.5:
            severity = "high"
        elif large_score >= 1.5:
            severity = "moderate"
        else:
            severity = "low"

        return {
            "is_large": is_large,
            "large_score": large_score,
            "max_score": max_score,
            "severity": severity,
            "assessments": assessments,
            "body_vs_avg_range": body_vs_avg_range if avg_range > 0 else 0,
            "price_decline_pct": price_decline_pct,
        }

    except Exception as e:
        logger.warning(f"Error in large candle assessment: {e}")
        return {
            "is_large": False,
            "large_score": 0,
            "max_score": 4,
            "severity": "unknown",
            "assessments": ["Error in assessment"],
            "body_vs_avg_range": 0,
            "price_decline_pct": 0,
        }


def is_market_open():
    """
    Check if Indian stock market is currently open (9:15 AM - 3:30 PM IST, Mon-Fri).

    Returns:
        bool: True if market is currently open
    """
    try:
        now = datetime.now()

        # Check if it's a weekday (Monday=0, Sunday=6)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False

        # Market hours: 9:15 AM to 3:30 PM IST
        market_open = time(9, 15)
        market_close = time(15, 30)
        current_time = now.time()

        return market_open <= current_time <= market_close

    except Exception as e:
        logger.warning(f"Error checking market hours: {e}")
        # Default to assuming market is closed to be conservative
        return False


def is_today_candle(candle_date):
    """
    Check if a candle date is today.

    Args:
        candle_date: Date or datetime object

    Returns:
        bool: True if candle is from today
    """
    try:
        if isinstance(candle_date, pd.Timestamp):
            candle_date = candle_date.date()
        elif isinstance(candle_date, datetime):
            candle_date = candle_date.date()

        return candle_date == datetime.now().date()
    except Exception:
        return False


def analyze_recent_candle_quality(df, lookback_candles=3):
    """
    Analyze recent candle quality for reversal potential using enhanced large candle detection.

    Large red body candles often indicate strong selling pressure that continues
    into the next day despite oversold RSI conditions.

    IMPORTANT: During market hours, excludes today's incomplete candle to avoid misleading signals.
    Only analyzes completed candles (yesterday and before).

    Args:
        df: DataFrame with OHLC data
        lookback_candles: Number of recent candles to analyze (default: 3)

    Returns:
        dict: {
            'penalty_score': int (0-10),
            'quality_signal': str,
            'reversal_probability': str,
            'details': list,
            'candle_metrics': list,
            'market_context': dict,
            'excluded_today': bool
        }
    """

    try:
        if len(df) < lookback_candles:
            return {
                "penalty_score": 0,
                "quality_signal": "insufficient_data",
                "reversal_probability": "unknown",
                "details": ["Insufficient candle data"],
                "candle_metrics": [],
                "market_context": {},
                "excluded_today": False,
            }

        # Check if we should exclude today's incomplete candle
        excluded_today = False
        df_to_analyze = df.copy()

        if is_market_open() and "date" in df.columns:
            last_candle_date = df.iloc[-1]["date"]
            if is_today_candle(last_candle_date):
                # Exclude today's incomplete candle during market hours
                df_to_analyze = df.iloc[:-1]
                excluded_today = True
                logger.debug(f"Market open - excluding today's incomplete candle from analysis")

        # Ensure we still have enough data after exclusion
        if len(df_to_analyze) < lookback_candles:
            return {
                "penalty_score": 0,
                "quality_signal": "insufficient_data",
                "reversal_probability": "unknown",
                "details": ["Insufficient completed candle data"],
                "candle_metrics": [],
                "market_context": {},
                "excluded_today": excluded_today,
            }

        # Calculate market context for better large candle assessment
        market_context = calculate_market_context(df_to_analyze, lookback_days=20)

        # Get recent candles (most recent first)
        recent_candles = df_to_analyze.tail(lookback_candles).iloc[::-1]

        penalty_score = 0
        details = []
        candle_metrics = []

        # Analyze each recent candle
        for i, (_, candle) in enumerate(recent_candles.iterrows()):
            metrics = calculate_candle_metrics(candle)
            if metrics is None:
                continue

            candle_metrics.append(metrics)

            # Age weight (most recent candle has highest impact)
            age_weight = 1.0 if i == 0 else 0.7 if i == 1 else 0.4

            # Calculate volume ratio if available
            volume_ratio = None
            if "volume" in recent_candles.columns and market_context["avg_volume"] > 0:
                volume_ratio = candle["volume"] / market_context["avg_volume"]

            # 1. Enhanced Large Red Body Analysis
            if metrics["is_red"]:
                large_assessment = is_truly_large_candle(metrics, market_context, volume_ratio)

                if large_assessment["is_large"]:
                    # Scale penalty based on severity of large candle
                    if large_assessment["severity"] == "extreme":
                        base_penalty = 4
                    elif large_assessment["severity"] == "high":
                        base_penalty = 3
                    else:  # moderate
                        base_penalty = 2

                    penalty_score += int(base_penalty * age_weight)

                    # Create detailed message with reasoning
                    assessments_str = ", ".join(
                        large_assessment["assessments"][:2]
                    )  # Top 2 reasons
                    details.append(
                        f"Candle {i+1}: Large red candle ({large_assessment['severity']}) - {assessments_str}"
                    )

                elif metrics["body_ratio"] > 0.6:  # Still penalize moderate red bodies
                    base_penalty = 1
                    penalty_score += int(base_penalty * age_weight)
                    details.append(
                        f"Candle {i+1}: Moderate red body ({metrics['body_ratio']:.1%} of range)"
                    )

            # 2. Minimal Lower Wick (No Buyer Support)
            if metrics["lower_wick_ratio"] < 0.1:
                base_penalty = 2
                penalty_score += int(base_penalty * age_weight)
                details.append(
                    f"Candle {i+1}: Minimal lower wick ({metrics['lower_wick_ratio']:.1%}) - no buyer support"
                )

            # 3. Full Body Red Candle (Open=High, Close=Low or near)
            if (
                metrics["is_red"]
                and metrics["upper_wick_ratio"] < 0.05
                and metrics["lower_wick_ratio"] < 0.05
            ):
                base_penalty = 2
                penalty_score += int(base_penalty * age_weight)
                details.append(f"Candle {i+1}: Full body red candle - strong selling pressure")

        # 4. Consecutive Red Candles Pattern
        consecutive_red = 0
        for metrics in candle_metrics:
            if metrics["is_red"]:
                consecutive_red += 1
            else:
                break

        if consecutive_red >= 2:
            penalty_score += consecutive_red - 1  # Additional penalty for each consecutive red
            details.append(f"{consecutive_red} consecutive red candles - sustained selling")

        # 5. Volume-Price Analysis (if volume available)
        if "volume" in recent_candles.columns:
            try:
                recent_volumes = recent_candles["volume"].values
                if len(recent_volumes) >= 2:
                    # High volume on red candles = institutional selling
                    latest_vol = recent_volumes[0]
                    avg_vol = np.mean(recent_volumes[1:]) if len(recent_volumes) > 1 else latest_vol

                    if candle_metrics[0]["is_red"] and latest_vol > avg_vol * 1.5:
                        penalty_score += 1
                        details.append("High volume on latest red candle - institutional selling")
            except Exception:
                pass  # Volume analysis is optional

        # Cap penalty score
        penalty_score = min(penalty_score, 10)

        # Determine quality signals
        if penalty_score >= 7:
            quality_signal = "strong_selling_pressure"
            reversal_probability = "very_low"
        elif penalty_score >= 5:
            quality_signal = "moderate_selling_pressure"
            reversal_probability = "low"
        elif penalty_score >= 3:
            quality_signal = "weak_selling_pressure"
            reversal_probability = "moderate"
        else:
            quality_signal = "neutral_to_positive"
            reversal_probability = "good"

        return {
            "penalty_score": penalty_score,
            "quality_signal": quality_signal,
            "reversal_probability": reversal_probability,
            "details": details,
            "candle_metrics": candle_metrics,
            "consecutive_red_candles": consecutive_red,
            "market_context": market_context,
            "excluded_today": excluded_today,
        }

    except Exception as e:
        logger.error(f"Error in candle quality analysis: {e}")
        return {
            "penalty_score": 0,
            "quality_signal": "error",
            "reversal_probability": "unknown",
            "details": [f"Analysis error: {str(e)}"],
            "candle_metrics": [],
            "market_context": {},
            "excluded_today": False,
        }


def should_downgrade_signal(candle_analysis, current_verdict):
    """
    Determine if signal should be downgraded based on candle quality analysis.

    Args:
        candle_analysis: Result from analyze_recent_candle_quality()
        current_verdict: Current signal verdict ('strong_buy', 'buy', 'watch', 'avoid')

    Returns:
        tuple: (new_verdict, reason)
    """

    penalty_score = candle_analysis.get("penalty_score", 0)
    quality_signal = candle_analysis.get("quality_signal", "neutral")

    # Downgrade logic based on penalty score
    if penalty_score >= 7:
        # Severe selling pressure - significant downgrade
        if current_verdict == "strong_buy":
            return "watch", f"Downgraded due to strong selling pressure (penalty: {penalty_score})"
        elif current_verdict == "buy":
            return "watch", f"Downgraded due to strong selling pressure (penalty: {penalty_score})"
        # watch/avoid stay the same

    elif penalty_score >= 5:
        # Moderate selling pressure - moderate downgrade
        if current_verdict == "strong_buy":
            return "buy", f"Downgraded due to selling pressure (penalty: {penalty_score})"
        elif current_verdict == "buy":
            return "watch", f"Downgraded due to selling pressure (penalty: {penalty_score})"

    elif penalty_score >= 3:
        # Mild selling pressure - slight downgrade
        if current_verdict == "strong_buy":
            return "buy", f"Downgraded due to recent red candles (penalty: {penalty_score})"

    # No downgrade needed
    return current_verdict, None


def get_candle_quality_summary(candle_analysis, use_emojis=True):
    """
    Get a human-readable summary of candle quality analysis.

    Args:
        candle_analysis: Result from analyze_recent_candle_quality()
        use_emojis: Whether to use emoji characters (False for Windows console logging)

    Returns:
        str: Summary for logging/display
    """

    penalty = candle_analysis.get("penalty_score", 0)
    quality = candle_analysis.get("quality_signal", "unknown")
    probability = candle_analysis.get("reversal_probability", "unknown")
    details = candle_analysis.get("details", [])
    consecutive = candle_analysis.get("consecutive_red_candles", 0)

    summary_parts = []

    # Main assessment - with emoji control for Windows console compatibility
    if use_emojis:
        if penalty >= 7:
            summary_parts.append(f"? HIGH PENALTY ({penalty}/10)")
        elif penalty >= 5:
            summary_parts.append(f"? MODERATE PENALTY ({penalty}/10)")
        elif penalty >= 3:
            summary_parts.append(f"? LOW PENALTY ({penalty}/10)")
        else:
            summary_parts.append(f"? GOOD QUALITY ({penalty}/10)")
    else:
        # Console-safe version without emojis
        if penalty >= 7:
            summary_parts.append(f"HIGH PENALTY ({penalty}/10)")
        elif penalty >= 5:
            summary_parts.append(f"MODERATE PENALTY ({penalty}/10)")
        elif penalty >= 3:
            summary_parts.append(f"LOW PENALTY ({penalty}/10)")
        else:
            summary_parts.append(f"GOOD QUALITY ({penalty}/10)")

    # Key issues
    if consecutive >= 2:
        summary_parts.append(f"{consecutive} consecutive red candles")

    # Top issues
    key_details = details[:2] if len(details) > 2 else details
    for detail in key_details:
        # Simplify detail text
        simplified = detail.replace("Candle 1:", "Latest:").replace("Candle 2:", "Prev:")
        summary_parts.append(simplified)

    return " | ".join(summary_parts)


if __name__ == "__main__":
    # Simple test with mock data
    import pandas as pd

    # Create test data with truly large red candle (4% decline, high volume)
    test_data = pd.DataFrame(
        {
            "open": [100, 100, 100, 98, 96],  # Recent prices around 100
            "high": [102, 101, 102, 99, 97],  # Normal daily ranges ~2-3
            "low": [98, 99, 98, 92, 92],  # Last candle: large range
            "close": [101, 100, 99, 92, 93],  # Last candle: 4% decline (96->92)
            "volume": [1000, 1000, 1000, 2500, 1200],  # High volume on red candle
        }
    )

    result = analyze_recent_candle_quality(test_data)
    print("Enhanced Candle Analysis Test:")
    print(f"Penalty Score: {result['penalty_score']}/10")
    print(f"Quality Signal: {result['quality_signal']}")
    print(f"Market Context: Avg Range={result['market_context']['avg_daily_range']:.1f}")
    print(f"Details: {result['details']}")
    print(f"Summary: {get_candle_quality_summary(result)}")

    # Test what makes a candle "large"
    if result["candle_metrics"]:
        latest = result["candle_metrics"][0]
        print(f"\nLatest Candle Analysis:")
        print(
            f"Body Size: {latest['body_size']:.1f} vs Avg Range: {result['market_context']['avg_daily_range']:.1f}"
        )
        print(f"Price Decline: {((latest['open']-latest['close'])/latest['open']*100):.1f}%")
        print(f"Body Ratio: {latest['body_ratio']:.1%} of candle range")
