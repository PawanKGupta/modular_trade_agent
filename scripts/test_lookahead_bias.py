#!/usr/bin/env python3
"""
Test for look-ahead bias in training data extraction

Compares features extracted using:
1. Entry date's close data (WRONG - look-ahead bias)
2. Previous day's close data (CORRECT - what you had at decision time)
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from services.data_service import DataService
from services.indicator_service import IndicatorService


def test_lookahead_bias(ticker='RELIANCE.NS', entry_date='2024-01-15'):
    """
    Test look-ahead bias by comparing features from entry_date vs previous day

    Scenario:
    - Evening of 2024-01-14: Market closed, you analyze and decide to buy
    - Morning of 2024-01-15: You place order at market open
    - entry_date in backtest = 2024-01-15 (execution day)

    Question: Should features use 2024-01-14 or 2024-01-15 data?
    Answer: 2024-01-14 (what you had when making decision!)
    """

    print("="*80)
    print("TESTING LOOK-AHEAD BIAS")
    print("="*80)
    print(f"\nScenario:")
    print(f"  Ticker: {ticker}")
    print(f"  Entry date: {entry_date} (morning open)")
    print(f"  Analysis date: {(datetime.strptime(entry_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')} (previous evening)")
    print()

    data_service = DataService()
    indicator_service = IndicatorService()

    # Method 1: WRONG - Using entry_date's close data
    print("-" * 80)
    print("METHOD 1 (CURRENT - WITH LOOK-AHEAD BIAS):")
    print(f"  Using data from {entry_date} (entry day's close)")
    print("-" * 80)

    df_wrong = data_service.fetch_single_timeframe(
        ticker=ticker,
        end_date=entry_date,
        add_current_day=False
    )

    if df_wrong is not None and not df_wrong.empty:
        df_wrong = indicator_service.compute_indicators(df_wrong)
        last_wrong = df_wrong.iloc[-1]

        print(f"  Date of last row: {last_wrong.name.strftime('%Y-%m-%d') if hasattr(last_wrong.name, 'strftime') else last_wrong.name}")
        print(f"  Close: ₹{last_wrong['close']:.2f}")
        print(f"  Volume: {last_wrong['volume']:,.0f}")
        print(f"  RSI(10): {last_wrong.get('rsi10', 0):.2f}")
        print(f"  High: ₹{last_wrong['high']:.2f}")
        print(f"  Low: ₹{last_wrong['low']:.2f}")
        print()
        print(f"  ❌ Problem: You DON'T have this data at 9:15 AM on {entry_date}!")
        print(f"     Market hasn't closed yet - you don't know:")
        print(f"     - Final close price (₹{last_wrong['close']:.2f})")
        print(f"     - Total volume ({last_wrong['volume']:,.0f})")
        print(f"     - Day's high/low")

    # Method 2: CORRECT - Using previous day's close data
    print("\n" + "-" * 80)
    analysis_date = (datetime.strptime(entry_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
    print("METHOD 2 (CORRECT - NO LOOK-AHEAD BIAS):")
    print(f"  Using data from {analysis_date} (previous day's close)")
    print("-" * 80)

    df_correct = data_service.fetch_single_timeframe(
        ticker=ticker,
        end_date=analysis_date,
        add_current_day=False
    )

    if df_correct is not None and not df_correct.empty:
        df_correct = indicator_service.compute_indicators(df_correct)
        last_correct = df_correct.iloc[-1]

        print(f"  Date of last row: {last_correct.name.strftime('%Y-%m-%d') if hasattr(last_correct.name, 'strftime') else last_correct.name}")
        print(f"  Close: ₹{last_correct['close']:.2f}")
        print(f"  Volume: {last_correct['volume']:,.0f}")
        print(f"  RSI(10): {last_correct.get('rsi10', 0):.2f}")
        print(f"  High: ₹{last_correct['high']:.2f}")
        print(f"  Low: ₹{last_correct['low']:.2f}")
        print()
        print(f"  ✅ Correct: This is what you HAD when making the decision!")
        print(f"     At evening of {analysis_date}, you knew this data")
        print(f"     Next morning ({entry_date}), you placed the order")

    # Compare differences
    if df_wrong is not None and df_correct is not None:
        print("\n" + "=" * 80)
        print("COMPARISON - HOW MUCH FUTURE INFO ARE WE LEAKING?")
        print("=" * 80)

        close_diff = last_wrong['close'] - last_correct['close']
        close_diff_pct = (close_diff / last_correct['close']) * 100

        volume_diff = last_wrong['volume'] - last_correct['volume']
        volume_diff_pct = (volume_diff / last_correct['volume']) * 100 if last_correct['volume'] > 0 else 0

        rsi_diff = last_wrong.get('rsi10', 0) - last_correct.get('rsi10', 0)

        print(f"\n  Close price difference: ₹{close_diff:+.2f} ({close_diff_pct:+.2f}%)")
        print(f"  Volume difference: {volume_diff:+,.0f} ({volume_diff_pct:+.2f}%)")
        print(f"  RSI(10) difference: {rsi_diff:+.2f}")

        print(f"\n  🎯 Impact on ML:")
        if abs(close_diff_pct) > 0.5:
            print(f"     HIGH IMPACT - Price moved {abs(close_diff_pct):.1f}% on entry day!")
        else:
            print(f"     Low impact - Price only moved {abs(close_diff_pct):.1f}% on entry day")

        if abs(rsi_diff) > 2:
            print(f"     HIGH IMPACT - RSI changed by {abs(rsi_diff):.1f} points!")
        else:
            print(f"     Low impact - RSI only changed by {abs(rsi_diff):.1f} points")

    print("\n" + "=" * 80)
    print("CONCLUSION:")
    print("=" * 80)
    print("""
  Your trading workflow:
  1. Evening of Day N: Analyze stocks using Day N's close data
  2. Morning of Day N+1: Place orders at market open
  3. Backtest entry_date = Day N+1

  Correct feature extraction:
  - Use Day N's data (entry_date - 1 day)
  - This matches what you had when making the decision

  Current implementation:
  - Uses Day N+1's data (entry_date)
  - This includes future information you didn't have!
  - Creates optimistic bias in ML model
""")
    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Test for look-ahead bias in training data')
    parser.add_argument('--ticker', default='RELIANCE.NS', help='Stock ticker to test')
    parser.add_argument('--entry-date', default='2024-01-15', help='Entry date (YYYY-MM-DD)')

    args = parser.parse_args()

    test_lookahead_bias(ticker=args.ticker, entry_date=args.entry_date)

