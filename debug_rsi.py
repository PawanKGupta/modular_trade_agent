"""
Debug RSI Calculation

This script checks if our RSI calculation matches TradingView values
for specific dates on ORIENTCEM.NS
"""

import sys
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.indicators import wilder_rsi
import pandas_ta as ta


def debug_rsi_calculation():
    """Debug RSI calculation for ORIENTCEM.NS"""
    
    symbol = "ORIENTCEM.NS"
    
    # Get data with extra buffer for RSI calculation
    start_date = datetime(2024, 12, 1)  # Start earlier for RSI calculation
    end_date = datetime(2025, 3, 1)     # End after Feb to capture both dates
    
    print(f"Fetching data for {symbol} from {start_date.date()} to {end_date.date()}")
    
    # Download data
    data = yf.download(symbol, start=start_date, end=end_date, progress=False, auto_adjust=True)
    
    if data.empty:
        print("No data available")
        return
        
    # Handle MultiIndex columns
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    print(f"Downloaded {len(data)} data points")
    
    # Calculate RSI using our method (Wilder's method)
    data['RSI10_Wilder'] = wilder_rsi(data['Close'], period=10)
    
    # Calculate RSI using pandas_ta default method
    data['RSI10_TA'] = ta.rsi(data['Close'], length=10)
    
    # Find the specific dates mentioned
    target_dates = ['2025-01-28', '2025-02-19']
    
    print(f"\n{'Date':<12} {'Close':<10} {'RSI10_Wilder':<15} {'RSI10_TA':<12} {'TradingView':<12}")
    print("-" * 65)
    
    for date_str in target_dates:
        try:
            target_date = pd.to_datetime(date_str)
            
            # Find closest trading day
            available_dates = data.index[data.index <= target_date]
            if len(available_dates) == 0:
                print(f"{date_str:<12} No data available")
                continue
                
            closest_date = available_dates[-1]
            row = data.loc[closest_date]
            
            close_price = row['Close']
            rsi_wilder = row['RSI10_Wilder']
            rsi_ta = row['RSI10_TA']
            
            # Expected values from TradingView
            expected_rsi = 28.65 if date_str == '2025-01-28' else 29.72
            
            print(f"{closest_date.strftime('%Y-%m-%d'):<12} "
                  f"{close_price:<10.2f} "
                  f"{rsi_wilder:<15.2f} "
                  f"{rsi_ta:<12.2f} "
                  f"{expected_rsi:<12.2f}")
                  
            # Check difference
            diff_wilder = abs(rsi_wilder - expected_rsi) if not pd.isna(rsi_wilder) else 999
            diff_ta = abs(rsi_ta - expected_rsi) if not pd.isna(rsi_ta) else 999
            
            print(f"             Difference: Wilder={diff_wilder:.2f}, TA={diff_ta:.2f}")
            
        except Exception as e:
            print(f"{date_str:<12} Error: {e}")
    
    # Show data around those dates for manual verification
    print(f"\n\nDetailed data around target dates:")
    print(f"{'Date':<12} {'Close':<10} {'RSI10_Wilder':<15} {'RSI10_TA':<12}")
    print("-" * 50)
    
    # Show January data
    jan_data = data[(data.index >= '2025-01-25') & (data.index <= '2025-01-31')]
    for date, row in jan_data.iterrows():
        print(f"{date.strftime('%Y-%m-%d'):<12} "
              f"{row['Close']:<10.2f} "
              f"{row['RSI10_Wilder']:<15.2f} "
              f"{row['RSI10_TA']:<12.2f}")
    
    print()
    
    # Show February data  
    feb_data = data[(data.index >= '2025-02-17') & (data.index <= '2025-02-21')]
    for date, row in feb_data.iterrows():
        print(f"{date.strftime('%Y-%m-%d'):<12} "
              f"{row['Close']:<10.2f} "
              f"{row['RSI10_Wilder']:<15.2f} "
              f"{row['RSI10_TA']:<12.2f}")


def manual_rsi_calculation(prices, period=10):
    """Manual RSI calculation for verification"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Simple moving average method (not Wilder's)
    avg_gain_sma = gain.rolling(window=period).mean()
    avg_loss_sma = loss.rolling(window=period).mean()
    
    rs_sma = avg_gain_sma / avg_loss_sma
    rsi_sma = 100 - (100 / (1 + rs_sma))
    
    # Wilder's smoothing method
    alpha = 1.0 / period
    avg_gain_wilder = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss_wilder = loss.ewm(alpha=alpha, adjust=False).mean()
    
    rs_wilder = avg_gain_wilder / avg_loss_wilder
    rsi_wilder = 100 - (100 / (1 + rs_wilder))
    
    return rsi_sma, rsi_wilder


if __name__ == "__main__":
    debug_rsi_calculation()