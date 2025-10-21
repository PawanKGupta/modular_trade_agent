import pandas as pd
import numpy as np
from ta.trend import ADXIndicator

from utils.logger import logger


def wilder_rsi(prices, period=10):
    """Calculate RSI using Wilder's original method (matches TradingView)"""
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

def compute_indicators(df):
    if df is None or df.empty:
        return None

    try:
        df = df.copy()
        
        # Handle column name case variations (yfinance uses Capital case)
        close_col = 'Close' if 'Close' in df.columns else 'close'
        high_col = 'High' if 'High' in df.columns else 'high'
        low_col = 'Low' if 'Low' in df.columns else 'low'
        
        # Use Wilder's RSI method (matches TradingView)
        df['rsi10'] = wilder_rsi(df[close_col], period=10)
        df['ema20'] = df[close_col].ewm(span=20).mean()
        df['ema50'] = df[close_col].ewm(span=50).mean()
        df['ema200'] = df[close_col].ewm(span=200).mean()  # For uptrend confirmation
        # df['adx'] = ta.adx(df[high_col], df[low_col], df[close_col], length=14)['ADX_14']
        # adx = ADXIndicator(high=df[high_col], low=df[low_col], close=df[close_col], window=14)
        # df['adx'] = adx.adx()

        return df
    except Exception as e:
        logger.exception("Error computing indicators")
        return None
