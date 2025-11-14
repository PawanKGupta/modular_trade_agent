import numpy as np
from ta.trend import ADXIndicator
from typing import Optional
from config.strategy_config import StrategyConfig


def is_hammer(row):
    op, cl, hi, lo = row['open'], row['close'], row['high'], row['low']
    body = abs(cl - op)
    lower_shadow = min(op, cl) - lo
    upper_shadow = hi - max(op, cl)
    if (body == 0):
        body = 1e-6
    return (lower_shadow > 2 * body) and (upper_shadow < body * 0.8)


def is_bullish_engulfing(prev, curr):
    try:
        return (prev['close'] < prev['open']) and (curr['close'] > curr['open']) and (curr['close'] >= prev['open']) and (curr['open'] <= prev['close'])
    except Exception:
        return False


def bullish_divergence(df, rsi_period: int = 10, lookback_period: int = 10):
    """
    Detect bullish divergence pattern
    
    Args:
        df: DataFrame with price and RSI data
        rsi_period: RSI calculation period (default: 10)
        lookback_period: Lookback period for divergence detection (default: 10)
    
    Returns:
        bool: True if bullish divergence detected, False otherwise
    """
    look = lookback_period
    if len(df) < look + 1:
        return False

    sub = df.tail(look)
    price_ll = sub['low'].min()
    idx_price_ll = sub['low'].idxmin()

    prev_window = df.tail(look + 5).head(look)
    if prev_window.empty:
        return False

    price_prev_min = prev_window['low'].min()
    if price_ll >= price_prev_min:
        return False

    # Use configurable RSI column name
    rsi_col = f'rsi{rsi_period}'
    # Fallback to 'rsi10' for backward compatibility
    if rsi_col not in sub.columns and 'rsi10' in sub.columns:
        rsi_col = 'rsi10'
    elif rsi_col not in sub.columns:
        return False  # RSI column doesn't exist
    
    rsi_now = sub.loc[idx_price_ll, rsi_col]
    earlier_idx = prev_window['low'].idxmin()
    rsi_earlier = prev_window.loc[earlier_idx, rsi_col]

    if np.isnan(rsi_now) or np.isnan(rsi_earlier):
        return False

    return rsi_now > rsi_earlier

def is_adx_bullish(df):

    adx = ADXIndicator(df['high'], df['low'], df['close'], window=14)
    df['adx'] = adx.adx()
    df['plus_di'] = adx.adx_pos()
    df['minus_di'] = adx.adx_neg()
