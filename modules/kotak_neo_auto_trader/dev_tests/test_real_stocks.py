#!/usr/bin/env python3
"""
Test volume filtering on real portfolio stocks
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import yfinance as yf
from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from config.settings import POSITION_VOLUME_RATIO_TIERS

print("Real Portfolio Stocks - Volume Filter Test")
print("=" * 80)
print("\nTier Configuration:")
for price_threshold, max_ratio in POSITION_VOLUME_RATIO_TIERS:
    if price_threshold > 0:
        print(f"  ₹{price_threshold}+: {max_ratio:.1%} max")
    else:
        print(f"  <₹500: {max_ratio:.1%} max")
print("\n" + "=" * 80)

# Real stocks to test
stocks = [
    "DREAMFOLKS.NS",
    "HCLTECH.NS",
    "ORIENTCEM.NS",
    "DALBHARAT.NS",
    "DHARMAJ.NS",
    "GLENMARK.NS",
    "NAVA.NS",
    "HYUNDAI.NS",
    "GOKULAGRO.NS",
    "GALLANTT.NS"
]

CAPITAL = 100000  # ₹1 lakh per trade

print("\nFetching real data from market...")
print("-" * 80)

results = []

for ticker in stocks:
    try:
        stock = yf.Ticker(ticker)
        
        # Get current price
        hist = stock.history(period="1d")
        if hist.empty:
            print(f"\n❌ {ticker}: No data available")
            continue
        
        price = hist['Close'].iloc[-1]
        
        # Get 50-day average volume
        hist_50d = stock.history(period="60d")
        avg_volume = hist_50d['Volume'].tail(50).mean()
        
        # Calculate position size
        qty = int(CAPITAL / price)
        
        # Check if it passes
        symbol = ticker.replace('.NS', '')
        passes = AutoTradeEngine.check_position_volume_ratio(qty, avg_volume, symbol, price)
        
        ratio = (qty / avg_volume) * 100 if avg_volume > 0 else 999
        
        results.append({
            'symbol': symbol,
            'price': price,
            'qty': qty,
            'avg_volume': int(avg_volume),
            'ratio': ratio,
            'passes': passes
        })
        
        status = "✅ PASS" if passes else "❌ FAIL"
        print(f"\n{symbol} ({ticker})")
        print(f"  Price: ₹{price:.2f} | Qty: {qty} shares")
        print(f"  50-day Avg Volume: {int(avg_volume):,} shares")
        print(f"  Position/Volume Ratio: {ratio:.2f}%")
        print(f"  Result: {status}")
        
    except Exception as e:
        print(f"\n❌ {ticker}: Error - {e}")

print("\n" + "=" * 80)
print("Summary:")
print("-" * 80)

if results:
    passed = sum(1 for r in results if r['passes'])
    failed = sum(1 for r in results if not r['passes'])
    
    print(f"\n✅ Passed: {passed}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")
    
    if failed > 0:
        print("\n⚠️  Filtered Stocks (Illiquid):")
        for r in results:
            if not r['passes']:
                print(f"  - {r['symbol']}: {r['ratio']:.1f}% of daily volume")
    
    if passed > 0:
        print(f"\n✅ Tradeable Stocks ({passed} stocks):")
        for r in results:
            if r['passes']:
                print(f"  - {r['symbol']}: {r['ratio']:.2f}% of daily volume")
else:
    print("No results to display")

print("\n" + "=" * 80)
