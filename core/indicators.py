import pandas as pd
import numpy as np
import pandas_ta as ta
from ta.trend import ADXIndicator
from typing import Optional

from utils.logger import logger
from config.strategy_config import StrategyConfig


def wilder_rsi(prices, period=10):
    """
    Calculate RSI using Wilder's original method (matches TradingView)
    
    NOTE: This function is kept for backward compatibility.
    For new code, use pandas_ta.rsi() for consistency.
    """
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Wilder's smoothing using exponential moving average with alpha = 1/period
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_indicators(df, rsi_period=None, ema_period=None, config=None):
    """
    Compute technical indicators with configurable parameters
    Uses pandas_ta for consistency with BacktestEngine
    
    Args:
        df: DataFrame with OHLCV data
        rsi_period: RSI calculation period (uses config if None)
        ema_period: EMA calculation period (uses config if None, default: 200)
        config: StrategyConfig instance (uses default if None)
    
    Returns:
        DataFrame with computed indicators
    """
    if df is None or df.empty:
        return None

    try:
        # Get config if not provided
        if config is None:
            config = StrategyConfig.default()
        
        # Use provided parameters or config defaults
        rsi_period = rsi_period if rsi_period is not None else config.rsi_period
        ema_period = ema_period if ema_period is not None else 200  # EMA200 is standard
        
        df = df.copy()
        
        # Handle column name case variations (yfinance uses Capital case)
        close_col = 'Close' if 'Close' in df.columns else 'close'
        high_col = 'High' if 'High' in df.columns else 'high'
        low_col = 'Low' if 'Low' in df.columns else 'low'
        
        # Use pandas_ta for RSI (standardized method - consistent with BacktestEngine)
        rsi_col = f'rsi{rsi_period}'
        df[rsi_col] = ta.rsi(df[close_col], length=rsi_period)
        
        # Also keep 'rsi10' for backward compatibility if period is 10
        if rsi_period == 10:
            df['rsi10'] = df[rsi_col]
        
        # Use pandas_ta for EMAs (standardized method - consistent with BacktestEngine)
        df['ema20'] = ta.ema(df[close_col], length=20)
        df['ema50'] = ta.ema(df[close_col], length=50)
        df['ema200'] = ta.ema(df[close_col], length=ema_period)  # For uptrend confirmation
        
        # ADX calculation (commented out, but available if needed)
        # df['adx'] = ta.adx(df[high_col], df[low_col], df[close_col], length=14)['ADX_14']
        # adx = ADXIndicator(high=df[high_col], low=df[low_col], close=df[close_col], window=14)
        # df['adx'] = adx.adx()

        return df
    except Exception as e:
        logger.exception("Error computing indicators")
        return None
