import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

def compute_rsi(series, period=10):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rsi = 100 - (100 / (1 + (avg_gain / avg_loss)))
    return rsi

def compute_ema(series, span=50):
    return series.ewm(span=span, adjust=False).mean()

# Test with one stock
ticker = "RELIANCE.NS"
date = pd.Timestamp("2024-01-15")
start = date - timedelta(days=365)
end = date + timedelta(days=30)
end = min(end, pd.Timestamp.now())

print(f"Downloading data for {ticker} from {start} to {end}")
data = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
print(f"Downloaded {len(data)} rows")
print(f"Columns: {data.columns.tolist()}")

# Handle MultiIndex columns
if isinstance(data.columns, pd.MultiIndex):
    print("Flattening MultiIndex columns...")
    data.columns = data.columns.get_level_values(0)
    print(f"Flattened columns: {data.columns.tolist()}")
    
print(f"First few rows:")
print(data.head())

if not data.empty and "Close" in data.columns:
    print("Computing RSI and EMA...")
    data["RSI10"] = compute_rsi(data["Close"], 10)
    data["EMA50"] = compute_ema(data["Close"], 50)
    
    print(f"After calculations, shape: {data.shape}")
    print(f"NaN counts:")
    print(data[["Close", "RSI10", "EMA50"]].isna().sum())
    
    print("Dropping NaN values...")
    data_clean = data.dropna(subset=["Close", "RSI10", "EMA50"])
    print(f"After dropna, shape: {data_clean.shape}")
    
    print("Sample data:")
    print(data_clean[["Close", "RSI10", "EMA50"]].head())