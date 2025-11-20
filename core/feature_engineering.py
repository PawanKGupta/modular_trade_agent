#!/usr/bin/env python3
"""
Feature Engineering for ML Training
Calculates advanced features for dip-buying strategy ML model.

Features focus on:
1. Dip characteristics (depth, speed, duration)
2. Reversal/exhaustion signals
3. Risk indicators
"""

import pandas as pd
import numpy as np
from typing import Optional


def calculate_dip_depth(df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Calculate percentage dip from recent high.

    Tells ML: "How deep is this dip?" (5% correction vs 30% crash)

    Args:
        df: DataFrame with OHLCV data
        lookback: Days to look back for recent high

    Returns:
        Dip depth percentage (positive number, e.g., 15.5 means 15.5% below high)

    Example:
        20-day high: Rs 2850
        Current price: Rs 2565
        Result: 10.0% (dipped 10% from recent high)
    """
    if df is None or df.empty or len(df) < lookback:
        return 0.0

    try:
        recent_high = df["high"].tail(lookback).max()
        current_price = df["close"].iloc[-1]

        if recent_high <= 0:
            return 0.0

        dip_depth_pct = ((recent_high - current_price) / recent_high) * 100
        return max(0.0, dip_depth_pct)  # Return 0 if price is above high

    except Exception:
        return 0.0


def calculate_consecutive_red_days(df: pd.DataFrame) -> int:
    """
    Count consecutive red (down) candles from most recent day.

    Tells ML: "How long has it been falling?" (fresh dip vs prolonged decline)

    Args:
        df: DataFrame with OHLCV data

    Returns:
        Number of consecutive red days

    Example:
        Last 7 days: Red, Red, Red, Red, Green, Red, Red
        Result: 4 (stops at first green candle)
    """
    if df is None or df.empty:
        return 0

    try:
        consecutive_red = 0

        for i in range(len(df) - 1, -1, -1):  # Start from most recent, include index 0
            if df["close"].iloc[i] < df["open"].iloc[i]:  # Red candle
                consecutive_red += 1
            else:
                break  # Stop at first green candle

        return consecutive_red

    except Exception:
        return 0


def calculate_dip_speed(df: pd.DataFrame, max_lookback: int = 20) -> float:
    """
    Calculate average daily decline rate (% per day).

    Tells ML: "Is this a gradual correction or panic crash?"

    Args:
        df: DataFrame with OHLCV data
        max_lookback: Maximum days to look back

    Returns:
        Average decline rate in % per day (positive number)

    Example:
        Day 1: Down 1.5%
        Day 2: Down 2.0%
        Day 3: Down 1.8%
        Result: 1.77% per day (gradual decline)
    """
    if df is None or df.empty or len(df) < 2:
        return 0.0

    try:
        days_falling = 0
        total_decline_pct = 0.0

        # Count consecutive falling days and accumulate decline
        for i in range(len(df) - 1, max(0, len(df) - max_lookback - 1), -1):
            if i == 0:
                break

            current_close = df["close"].iloc[i]
            prev_close = df["close"].iloc[i - 1]

            if current_close < prev_close:  # Falling day
                days_falling += 1
                decline_pct = ((prev_close - current_close) / prev_close) * 100
                total_decline_pct += decline_pct
            else:
                break  # Stop at first up day

        if days_falling > 0:
            return total_decline_pct / days_falling
        else:
            return 0.0

    except Exception:
        return 0.0


def is_decline_rate_slowing(
    df: pd.DataFrame, recent_period: int = 5, previous_period: int = 5
) -> bool:
    """
    Check if decline rate is decelerating (exhaustion signal).

    Tells ML: "Is selling pressure weakening?" (key reversal indicator)

    Args:
        df: DataFrame with OHLCV data
        recent_period: Recent period to compare (days)
        previous_period: Previous period to compare (days)

    Returns:
        True if decline is slowing (exhaustion), False otherwise

    Example:
        Previous 5 days: Down 5.0%
        Recent 5 days: Down 2.6%
        Result: True (decline slowing = exhaustion)
    """
    if df is None or df.empty or len(df) < (recent_period + previous_period + 1):
        return False

    try:
        # Calculate recent period decline
        recent_start = df["close"].iloc[-(recent_period + 1)]
        recent_end = df["close"].iloc[-1]
        recent_decline_pct = abs(((recent_end - recent_start) / recent_start) * 100)

        # Calculate previous period decline
        previous_start = df["close"].iloc[-(recent_period + previous_period + 1)]
        previous_end = df["close"].iloc[-(recent_period + 1)]
        previous_decline_pct = abs(((previous_end - previous_start) / previous_start) * 100)

        # Decline is slowing if recent decline is less than previous
        # Convert to Python bool to avoid numpy.bool_ type
        return bool(recent_decline_pct < previous_decline_pct)

    except Exception:
        return False


def calculate_volume_green_vs_red_ratio(df: pd.DataFrame, lookback: int = 10) -> float:
    """
    Compare average volume on green days vs red days.

    Tells ML: "Are buyers or sellers more aggressive?" (volume conviction)

    Args:
        df: DataFrame with OHLCV data
        lookback: Days to look back

    Returns:
        Ratio of green candle volume to red candle volume
        > 1.0 = Buyers more aggressive (good for reversals)
        < 1.0 = Sellers more aggressive (wait)

    Example:
        Last 10 days:
        - Red candles (6 days): Avg volume = 8.5M
        - Green candles (4 days): Avg volume = 12.2M
        Result: 1.43 (buyers 43% more aggressive)
    """
    if df is None or df.empty or len(df) < lookback:
        return 1.0  # Neutral default

    try:
        recent_data = df.tail(lookback)

        # Separate green and red candles
        green_candles = recent_data[recent_data["close"] > recent_data["open"]]
        red_candles = recent_data[recent_data["close"] <= recent_data["open"]]

        if len(green_candles) == 0 or len(red_candles) == 0:
            return 1.0  # Can't compare if only one type

        avg_green_volume = green_candles["volume"].mean()
        avg_red_volume = red_candles["volume"].mean()

        if avg_red_volume > 0:
            return avg_green_volume / avg_red_volume
        else:
            return 1.0

    except Exception:
        return 1.0


def count_support_holds(df: pd.DataFrame, lookback: int = 20, tolerance_pct: float = 2.0) -> int:
    """
    Count how many times price tested and held support level.

    Tells ML: "Is this support level reliable?" (multiple tests = strong support)

    Args:
        df: DataFrame with OHLCV data
        lookback: Days to look back for support level
        tolerance_pct: Tolerance for support test (% above/below)

    Returns:
        Number of times support was tested and held

    Example:
        Support at Rs 950:
        Day 1: Low Rs 945, Close Rs 955 [OK] (held)
        Day 5: Low Rs 940, Close Rs 952 [OK] (held)
        Day 8: Low Rs 948, Close Rs 960 [OK] (held)
        Result: 3 (strong support)
    """
    if df is None or df.empty or len(df) < lookback:
        return 0

    try:
        recent_data = df.tail(lookback)

        # Find support level (lowest low in period)
        support_level = recent_data["low"].min()

        if support_level <= 0:
            return 0

        tolerance = support_level * (tolerance_pct / 100)
        support_hold_count = 0

        # Count how many times price tested and held support
        for i in range(len(recent_data)):
            day_low = recent_data["low"].iloc[i]
            day_close = recent_data["close"].iloc[i]

            # Check if low tested support (within tolerance)
            if abs(day_low - support_level) <= tolerance:
                # Check if it held (closed above support)
                if day_close > support_level:
                    support_hold_count += 1

        return support_hold_count

    except Exception:
        return 0


def calculate_all_dip_features(df: pd.DataFrame) -> dict:
    """
    Calculate all dip-related features at once.

    Convenience function to get all features in one call.

    Args:
        df: DataFrame with OHLCV data (must have: open, high, low, close, volume)

    Returns:
        Dictionary with all calculated features

    Example:
        features = calculate_all_dip_features(df)
        print(features['dip_depth_from_20d_high_pct'])  # 15.2
        print(features['decline_rate_slowing'])  # True
    """
    return {
        "dip_depth_from_20d_high_pct": calculate_dip_depth(df),
        "consecutive_red_days": calculate_consecutive_red_days(df),
        "dip_speed_pct_per_day": calculate_dip_speed(df),
        "decline_rate_slowing": is_decline_rate_slowing(df),
        "volume_green_vs_red_ratio": calculate_volume_green_vs_red_ratio(df),
        "support_hold_count": count_support_holds(df),
    }


# Outcome features (calculated from backtest results, not from market data)
def calculate_max_drawdown(entry_price: float, daily_lows: list) -> float:
    """
    Calculate maximum adverse excursion (worst unrealized loss).

    NOTE: This is calculated during/after backtest, not from live data.

    Args:
        entry_price: Entry price of position
        daily_lows: List of daily low prices during position lifetime

    Returns:
        Maximum drawdown percentage (negative number)

    Example:
        Entry: Rs 1000
        Daily lows: [Rs 985, Rs 970, Rs 990]
        Result: -3.0% (worst was Rs 970)
    """
    if not daily_lows or entry_price <= 0:
        return 0.0

    try:
        worst_price = min(daily_lows)
        max_drawdown = ((worst_price - entry_price) / entry_price) * 100
        return min(0.0, max_drawdown)  # Return 0 or negative

    except Exception:
        return 0.0
