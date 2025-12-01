# YESBANK Buy Order Test Guide

## Overview
This guide shows how to test the complete auto-trade buy flow for YESBANK with ₹100 capital using your real Kotak Neo account.

## Scenario
- **Yesterday**: Got YESBANK recommendation from backtest
- **Today**: Place AMO buy order for YESBANK with ₹100 capital
- **Opening Price**: ₹22.83
- **Expected Quantity**: 4 shares (₹100 / ₹22.83 ≈ 4.38)

## Setup

### 1. Mock Recommendation File
Already created: `analysis_results/bulk_analysis_final_test_yesbank.csv`

Contains:
```csv
ticker,verdict,last_close,final_verdict,combined_score,status
YESBANK.NS,buy,22.83,buy,35.5,success
```

### 2. Temporarily Update Capital (for test only)

Edit `modules/kotak_neo_auto_trader/config.py`:

```python
# Change from:
CAPITAL_PER_TRADE = 100000

# To:
CAPITAL_PER_TRADE = 100  # TEST ONLY
```

**IMPORTANT**: Remember to change it back after testing!

## Run the Test

### Option 1: Using the auto-trade runner
```powershell
python -m modules.kotak_neo_auto_trader.run_auto_trade --env modules\kotak_neo_auto_trader\kotak_neo.env
```

### Option 2: Specify the CSV explicitly
```powershell
python -m modules.kotak_neo_auto_trader.run_auto_trade --env modules\kotak_neo_auto_trader\kotak_neo.env --csv analysis_results\bulk_analysis_final_test_yesbank.csv
```

## What Happens

1. **Authentication**
   - Logs into Kotak Neo with 2FA
   - Initializes scrip master for symbol resolution

2. **Pre-flight Checks**
   - ✅ Checks if YESBANK already in holdings
   - ✅ Checks if active buy order exists
   - ✅ Validates portfolio size (< 6 stocks)
   - ✅ Checks available margin (≥ ₹100)

3. **Order Placement**
   - Resolves `YESBANK.NS` → `YESBANK-EQ` using scrip master
   - Calculates quantity: `₹100 / ₹22.83 = 4 shares`
   - Places **AMO (After Market Order)**
   - Records in `data/trades_history.json`

4. **Order Execution**
   - AMO order queued
   - Will execute tomorrow at **9:15 AM** market open
   - Order type: MARKET (buy at opening price)

## Expected Output

```
============================================================
KOTAK NEO AUTO TRADER
============================================================

🔐 Authenticating with Kotak Neo...
✅ Authentication successful!

📊 Loading recommendations from: analysis_results/bulk_analysis_final_test_yesbank.csv
✅ Loaded 1 BUY recommendations

🔍 Pre-flight checks...
  Current portfolio size: 0/6
  Available margin: ₹500,000.00

📋 Processing recommendation: YESBANK.NS
  Resolving symbol: YESBANK → YESBANK-EQ
  Price: ₹22.83
  Capital: ₹100
  Quantity: 4 shares

✅ AMO Buy Order Placed
  Symbol: YESBANK-EQ
  Quantity: 4
  Capital: ₹100
  Order ID: [order_id_here]

📊 Order Summary:
  Attempted: 1
  Placed: 1
  Skipped: 0
  Failed: 0

⏰ Order will execute at market open (9:15 AM)
============================================================
```

## Verify Order

### Method 1: Check in Kotak Neo App
1. Open Kotak Neo mobile app
2. Go to **Orders**
3. Look for **Pending AMO** orders
4. Should see: YESBANK x 4 @ MARKET

### Method 2: Check trades history file
```powershell
cat data/trades_history.json
```

Should contain:
```json
{
  "trades": [
    {
      "symbol": "YESBANK",
      "ticker": "YESBANK.NS",
      "placed_symbol": "YESBANK-EQ",
      "entry_price": 22.83,
      "qty": 4,
      "capital": 100,
      "entry_time": "2025-01-27T10:00:00",
      "status": "open",
      "signal_type": "buy",
      "rsi10": 28.5,
      "ema9": 22.50,
      "ema200": 21.00
    }
  ]
}
```

## After Test

### 1. Cancel Test Order (if needed)
If you don't want the order to execute:
1. Open Kotak Neo app/web
2. Go to Orders → Pending AMO
3. Cancel the YESBANK order

### 2. Restore Original Capital
Edit `modules/kotak_neo_auto_trader/config.py`:
```python
CAPITAL_PER_TRADE = 100000  # Restore original
```

### 3. Clean up test files (optional)
```powershell
# Remove test recommendation
Remove-Item analysis_results\bulk_analysis_final_test_yesbank.csv

# Or keep it for future tests
```

## Next Steps: Test Sell Flow

After the buy order executes tomorrow at 9:15 AM:

```powershell
# Run sell engine to place EMA9-based sell order
python -m modules.kotak_neo_auto_trader.sell_engine --env modules\kotak_neo_auto_trader\kotak_neo.env
```

This will:
- Detect YESBANK holding
- Calculate current EMA9
- Place limit sell order at EMA9 price
- Monitor and update as EMA9 changes

## Troubleshooting

### "No recommendations found"
- Check CSV file exists: `analysis_results/bulk_analysis_final_test_yesbank.csv`
- Verify CSV has correct format (headers and data)

### "Insufficient margin"
- Check available margin in Kotak Neo
- Ensure you have at least ₹100 available

### "Authentication failed"
- Verify credentials in `kotak_neo.env`
- Check 2FA TOTP secret is correct
- Try manual login in Kotak Neo app first

### "Symbol not found in scrip master"
- Scrip master initializes on first run
- If market closed, may use cached data
- Check logs for scrip master download status

## Safety Notes

⚠️ **This is a real account test with real money!**

- Order will execute with real ₹100 (~₹91-92 actual cost for 4 shares)
- AMO orders cannot be cancelled after market opens
- Test with small capital first
- Monitor the order in Kotak Neo app
- You can cancel AMO before 9:15 AM if needed

💡 **Best Practice**: Run this test after market hours (after 3:30 PM) so you have time to review and cancel if needed before next day's open.
