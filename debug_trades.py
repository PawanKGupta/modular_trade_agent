"""
Debug Trade Execution

Analyze why trades weren't executed on specific dates when conditions appeared to be met
"""

import sys
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas_ta as ta


def debug_trade_execution():
    """Debug why trades weren't executed on specific dates"""
    
    symbol = "ORIENTCEM.NS"
    
    # Use same data range as backtest
    start_date = datetime(2024, 5, 10)  # Same as backtest buffer
    end_date = datetime(2025, 6, 25)    # Same as backtest buffer
    
    print(f"Fetching data for {symbol} (same range as backtest)")
    print(f"From: {start_date.date()} To: {end_date.date()}")
    
    # Download data exactly like backtest does
    data = yf.download(symbol, start=start_date, end=end_date, progress=False, auto_adjust=True)
    
    if data.empty:
        print("No data available")
        return
        
    # Handle MultiIndex columns
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    print(f"Raw data points: {len(data)}")
    
    # Calculate indicators exactly like backtest does
    data['RSI10'] = ta.rsi(data['Close'], length=10)
    data['EMA200'] = ta.ema(data['Close'], length=200)
    
    # Drop NaN values like backtest does
    data_before_dropna = len(data)
    data = data.dropna()
    data_after_dropna = len(data)
    
    print(f"Data points before dropna: {data_before_dropna}")
    print(f"Data points after dropna: {data_after_dropna}")
    print(f"Dropped due to NaN: {data_before_dropna - data_after_dropna}")
    
    # Filter to backtest period
    backtest_start = datetime(2025, 1, 15)
    backtest_end = datetime(2025, 6, 15)
    backtest_data = data.loc[backtest_start:backtest_end]
    
    print(f"Backtest period data points: {len(backtest_data)}")
    
    # Check specific dates
    target_dates = ['2025-01-28', '2025-02-19']
    
    print(f"\\n{'='*80}")
    print(f"DETAILED ANALYSIS OF MISSED TRADE DATES")
    print(f"{'='*80}")
    
    for date_str in target_dates:
        print(f"\\n--- Analyzing {date_str} ---")
        
        try:
            target_date = pd.to_datetime(date_str)
            
            # Check if date is in backtest period
            if target_date < backtest_start or target_date > backtest_end:
                print(f"❌ Date {date_str} is OUTSIDE backtest period ({backtest_start.date()} to {backtest_end.date()})")
                continue
                
            # Find closest trading day
            available_dates = data.index[data.index <= target_date]
            if len(available_dates) == 0:
                print(f"❌ No data available for {date_str}")
                continue
                
            closest_date = available_dates[-1]
            
            # Check if date exists in backtest filtered data
            if closest_date not in backtest_data.index:
                print(f"❌ Date {closest_date.strftime('%Y-%m-%d')} not in backtest data")
                continue
                
            row = backtest_data.loc[closest_date]
            
            close_price = row['Close']
            ema200 = row['EMA200']
            rsi10 = row['RSI10']
            
            print(f"✅ Date: {closest_date.strftime('%Y-%m-%d')}")
            print(f"   Close Price: ₹{close_price:.2f}")
            print(f"   EMA200: ₹{ema200:.2f}")
            print(f"   RSI10: {rsi10:.2f}")
            
            # Check individual conditions
            condition1 = close_price > ema200
            condition2 = rsi10 < 30
            should_trade = condition1 and condition2
            
            print(f"\\n   Condition Analysis:")
            print(f"   🔸 Price > EMA200: {condition1} ({close_price:.2f} > {ema200:.2f})")
            print(f"   🔸 RSI < 30: {condition2} ({rsi10:.2f} < 30)")
            print(f"   🔸 Should Trade: {should_trade}")
            
            if should_trade:
                print(f"   ✅ ALL CONDITIONS MET - Trade should have been executed!")
                
                # Check next trading day for execution price
                next_day_data = backtest_data.loc[backtest_data.index > closest_date]
                if not next_day_data.empty:
                    next_day = next_day_data.index[0]
                    next_open = next_day_data.iloc[0]['Open']
                    print(f"   📊 Next day execution: {next_day.strftime('%Y-%m-%d')} at Open ₹{next_open:.2f}")
                else:
                    print(f"   ❌ No next day data for execution")
            else:
                if not condition1:
                    print(f"   ❌ FAILED: Price ₹{close_price:.2f} was BELOW EMA200 ₹{ema200:.2f}")
                if not condition2:
                    print(f"   ❌ FAILED: RSI {rsi10:.2f} was NOT oversold (>= 30)")
                    
        except Exception as e:
            print(f"❌ Error analyzing {date_str}: {e}")
            import traceback
            traceback.print_exc()
    
    # Show all trading opportunities in the backtest period
    print(f"\\n{'='*80}")
    print(f"ALL TRADING OPPORTUNITIES IN BACKTEST PERIOD")
    print(f"{'='*80}")
    
    print(f"{'Date':<12} {'Close':<8} {'EMA200':<8} {'RSI10':<8} {'Price>EMA':<10} {'RSI<30':<8} {'Trade?'}")
    print("-" * 75)
    
    trade_opportunities = 0
    for date, row in backtest_data.iterrows():
        close_price = row['Close']
        ema200 = row['EMA200']
        rsi10 = row['RSI10']
        
        condition1 = close_price > ema200
        condition2 = rsi10 < 30
        should_trade = condition1 and condition2
        
        if rsi10 < 35:  # Show near-oversold conditions
            print(f"{date.strftime('%Y-%m-%d'):<12} "
                  f"{close_price:<8.2f} "
                  f"{ema200:<8.2f} "
                  f"{rsi10:<8.2f} "
                  f"{str(condition1):<10} "
                  f"{str(condition2):<8} "
                  f"{'YES' if should_trade else 'NO'}")
            
            if should_trade:
                trade_opportunities += 1
    
    print(f"\\nTotal trading opportunities found: {trade_opportunities}")


if __name__ == "__main__":
    debug_trade_execution()