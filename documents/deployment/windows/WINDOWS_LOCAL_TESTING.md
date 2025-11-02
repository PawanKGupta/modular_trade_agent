# Windows Local Testing Guide

## Automated Trading System - Local Deployment & Testing

This guide walks you through testing the complete automated trading workflow on your Windows machine before deploying to production (Oracle Cloud).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Testing Strategy](#testing-strategy)
4. [Phase 1: Analysis Engine Test](#phase-1-analysis-engine-test)
5. [Phase 2: Buy Order Test](#phase-2-buy-order-test)
6. [Phase 3: Sell Order Test](#phase-3-sell-order-test)
7. [Phase 4: Full Automation Test](#phase-4-full-automation-test)
8. [Windows Task Scheduler Setup](#windows-task-scheduler-setup)
9. [Monitoring & Logs](#monitoring--logs)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Files & Credentials

- [x] Virtual environment activated (`.venv`)
- [x] `cred.env` with Telegram credentials
- [x] `modules/kotak_neo_auto_trader/kotak_neo.env` with broker credentials
- [x] All dependencies installed (`requirements.txt`)

### Verify Installation

```powershell
# Activate virtual environment
.venv\Scripts\activate

# Check Python version (should be 3.8+)
python --version

# Verify key packages
python -c "import pandas, yfinance, neo_api_client; print('All packages OK')"
```

---

## Initial Setup

### 1. Create Log Directory

```powershell
# Create logs directory if not exists
New-Item -ItemType Directory -Force -Path logs
```

### 2. Verify Credentials

**Telegram credentials** (`cred.env`):
```powershell
# Check if file exists
Get-Content cred.env
```

Should contain:
```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**Kotak Neo credentials** (`modules/kotak_neo_auto_trader/kotak_neo.env`):
```powershell
Get-Content modules\kotak_neo_auto_trader\kotak_neo.env
```

Should contain:
```env
KOTAK_CONSUMER_KEY=your_key
KOTAK_CONSUMER_SECRET=your_secret
KOTAK_MOBILE_NUMBER=+91xxxxxxxxxx
KOTAK_PASSWORD=your_password
KOTAK_TOTP_SECRET=your_totp_secret
KOTAK_MPIN=your_mpin
KOTAK_ENVIRONMENT=prod
```

### 3. Test Telegram Connection

```powershell
python -c "from core.telegram import send_telegram; send_telegram('Windows test OK')"
```

**Expected output:**
```
Testing Telegram connection...
✅ Telegram message sent successfully!
```

---

## Testing Strategy

We'll test in **4 phases** to ensure each component works before testing the full workflow:

1. **Analysis Engine** - Verify stock analysis and recommendations work
2. **Buy Order Placement** - Test AMO order placement (dry run first)
3. **Sell Order Monitoring** - Test exit logic and order updates
4. **Full Automation** - End-to-end workflow test

---

## Phase 1: Analysis Engine Test

### Objective
Verify that the analysis engine correctly identifies stocks, runs backtests, and generates recommendations.

### Test Steps

#### 1.1 Basic Analysis (No Backtest)

```powershell
# Run analysis without backtest (faster)
python trade_agent.py --no-csv
```

**What to check:**
- [ ] Stocks fetched from ChartInk screener
- [ ] Data downloaded for each stock
- [ ] RSI, EMA200, volume calculations complete
- [ ] Signal classification (STRONG_BUY, BUY, WATCH, AVOID)
- [ ] Telegram message sent with recommendations

**Expected duration:** 2-5 minutes

#### 1.2 Full Analysis with Backtest

```powershell
# Run complete analysis with backtest scoring
python trade_agent.py --backtest
```

**What to check:**
- [ ] All Phase 1.1 checks pass
- [ ] Backtest runs for each candidate (2-year historical validation)
- [ ] Combined scores calculated (current + historical)
- [ ] Priority ranking applied
- [ ] CSV exported to `analysis_results/bulk_analysis_final_*.csv`

**Expected duration:** 5-15 minutes (depends on number of stocks)

#### 1.3 Review Results

```powershell
# Check latest CSV
Get-ChildItem analysis_results\bulk_analysis_final_*.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

**Key columns to verify:**
- `final_verdict`: Should have values (strong_buy, buy, watch, avoid)
- `combined_score`: Should be calculated (0-100)
- `backtest_score`: Should have historical performance data
- `buy_range_low/high`: Should have realistic prices
- `target`, `stop`: Should have reasonable values

---

## Phase 2: Buy Order Test

### Objective
Test AMO order placement logic without actually placing orders, then test with small real orders.

### Test Steps

#### 2.1 Dry Run (Simulation Mode)

**First, check what orders would be placed:**

```powershell
# Review the CSV from Phase 1
python -c "import pandas as pd; df = pd.read_csv('analysis_results/bulk_analysis_final_*.csv'); print(df[df['final_verdict'].isin(['strong_buy', 'buy'])][['ticker', 'final_verdict', 'combined_score', 'buy_range_high', 'target', 'stop']])"
```

**Expected output:**
```
         ticker final_verdict  combined_score  buy_range_high   target     stop
0  RELIANCE.NS      strong_buy           45.2         2456.80  2680.50  2320.00
1  YESBANK.NS             buy           32.8           23.45    25.80    22.10
```

#### 2.2 Test Authentication

```powershell
# Test Kotak Neo login
python -m modules.kotak_neo_auto_trader.auth --test
```

**Expected output:**
```
[INFO] Loading credentials from: modules/kotak_neo_auto_trader/kotak_neo.env
[INFO] Attempting login...
[SUCCESS] Login successful!
[INFO] Session cached to: modules/kotak_neo_auto_trader/session_cache.json
```

**What to check:**
- [ ] Login succeeds without errors
- [ ] Session cache created
- [ ] No 2FA errors

#### 2.3 Check Current Portfolio

```powershell
# View current holdings
python -c "from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio; from modules.kotak_neo_auto_trader.auth import KotakNeoAuth; auth = KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env'); auth.login(); portfolio = KotakNeoPortfolio(auth.client); print(portfolio.get_holdings())"
```

**What to check:**
- [ ] Current holdings displayed
- [ ] Portfolio count (ensure < 6 if MAX_PORTFOLIO_SIZE = 6)
- [ ] Available funds shown

#### 2.4 Test Buy Engine (Skip Actual Orders)

**IMPORTANT:** Before testing actual order placement, we'll do a dry run by temporarily modifying the code.

**Option A: Use Mock Client (Recommended)**

```powershell
# If mock client exists
python -m modules.kotak_neo_auto_trader.run_auto_trade_mock --env modules\kotak_neo_auto_trader\kotak_neo.env
```

**Option B: Manual Review**

Instead of placing orders immediately, let's review what would happen:

```powershell
# Run with --no-orders flag (if implemented) or manually review
python -m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env --dry-run
```

**Note:** If `--dry-run` flag doesn't exist, you can manually review by checking:
1. The CSV file candidates
2. Current portfolio status
3. Available funds

#### 2.5 Place Test Order (Small Quantity)

**⚠️ CAUTION: This will place REAL orders!**

**For safe testing, temporarily modify `config.py`:**

```powershell
notepad modules\kotak_neo_auto_trader\config.py
```

**Change:**
```python
# Original
CAPITAL_PER_TRADE = 100000  # ₹1 Lakh per trade

# For testing (change to small amount)
CAPITAL_PER_TRADE = 5000    # ₹5,000 per trade (minimum for testing)
```

**Then place AMO orders:**

```powershell
# Place orders from latest CSV
python -m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env
```

**What to check:**
- [ ] Orders placed successfully
- [ ] Telegram notification sent with order details
- [ ] Orders appear in Kotak Neo web/app under "AMO Orders"
- [ ] Quantity calculated correctly (qty = floor(5000 / price))
- [ ] Prices rounded to correct tick size (₹0.05 for NSE)

#### 2.6 Cancel Test Orders

**IMPORTANT:** After testing, cancel the AMO orders before market open!

```powershell
# Method 1: Via Kotak Neo web/app
# Go to Orders → AMO Orders → Cancel all test orders

# Method 2: Via API (if cancel function implemented)
python -c "from modules.kotak_neo_auto_trader.orders import KotakNeoOrders; from modules.kotak_neo_auto_trader.auth import KotakNeoAuth; auth = KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env'); auth.login(); orders_mgr = KotakNeoOrders(auth.client); print(orders_mgr.get_order_book())"
```

**Then manually cancel via Kotak Neo platform.**

---

## Phase 3: Sell Order Test

### Objective
Test the sell order monitoring and placement logic.

### Prerequisites
- Must have at least 1 holding in portfolio (from previous buy, or existing position)
- Must run during market hours (9:15 AM - 3:30 PM) for realistic testing

### Test Steps

#### 3.1 Check Holdings

```powershell
# View current holdings
python -c "from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio; from modules.kotak_neo_auto_trader.auth import KotakNeoAuth; auth = KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env'); auth.login(); portfolio = KotakNeoPortfolio(auth.client); holdings = portfolio.get_holdings(); import json; print(json.dumps(holdings, indent=2))"
```

**What to check:**
- [ ] Holdings list shows your positions
- [ ] Symbol names are correct
- [ ] Quantities and average prices shown

#### 3.2 Test Sell Engine (Single Run)

```powershell
# Run sell engine once (no monitoring loop)
python -m modules.kotak_neo_auto_trader.run_sell_orders --env modules\kotak_neo_auto_trader\kotak_neo.env --run-once --skip-wait
```

**What to check:**
- [ ] Holdings fetched successfully
- [ ] EMA9 calculated for each holding
- [ ] Sell conditions evaluated (price < EMA9)
- [ ] Orders placed if conditions met
- [ ] Log shows decision reasoning

**Expected output:**
```
[INFO] Fetching current holdings...
[INFO] Found 2 holdings
[INFO] Processing RELIANCE...
[INFO] Current price: 2450.00, EMA9: 2480.00
[INFO] Price above EMA9, holding position
[INFO] Processing YESBANK...
[INFO] Current price: 22.50, EMA9: 23.10
[INFO] Price below EMA9, placing sell order
[SUCCESS] Sell order placed: YESBANK, Qty: 222, Price: 22.50
```

#### 3.3 Test Monitoring Loop (Short Duration)

```powershell
# Run for 5 minutes with 60-second intervals
# Press Ctrl+C to stop after observing behavior

python -m modules.kotak_neo_auto_trader.run_sell_orders --env modules\kotak_neo_auto_trader\kotak_neo.env --monitor-interval 60
```

**What to check:**
- [ ] Loop runs every 60 seconds
- [ ] Holdings checked on each iteration
- [ ] EMA9 recalculated with fresh data
- [ ] Orders placed when conditions trigger
- [ ] No duplicate orders for same symbol
- [ ] Stops at 3:30 PM (if run during market hours)

**Press Ctrl+C to stop when satisfied.**

#### 3.4 Verify Sell Orders

```powershell
# Check order book
# Method: Via Kotak Neo web/app
# Go to Orders → Order Book → Check for sell orders
```

**What to verify:**
- [ ] Sell orders appear in order book
- [ ] Order type is correct (MARKET or LIMIT)
- [ ] Quantity matches holding quantity
- [ ] Symbol is correct

#### 3.5 Cancel Test Orders (If Not Filled)

Cancel any unfilled test sell orders via Kotak Neo platform before close.

---

## Phase 4: Full Automation Test

### Objective
Test the complete end-to-end workflow: Analysis → Buy Orders → Sell Monitoring

### Test Schedule

**Ideal test day:** Choose a non-critical trading day for testing.

**Timeline:**
- **4:00 PM**: Analysis runs, generates recommendations
- **4:01 PM**: Buy AMO orders placed (execute next day at open)
- **9:15 AM (Next Day)**: Sell monitoring starts
- **3:30 PM (Next Day)**: Sell monitoring stops

### Test Steps

#### 4.1 Schedule Analysis (4:00 PM)

**Option A: Run Manually at 4 PM**

```powershell
# At 4:00 PM, run:
python trade_agent.py --backtest
```

**Option B: Use Task Scheduler (Setup in next section)**

Set up Windows Task Scheduler to run automatically.

#### 4.2 Schedule Buy Orders (4:01 PM)

```powershell
# At 4:01 PM (or immediately after analysis completes), run:
python -m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env
```

**What to check:**
- [ ] Orders placed within 1-2 minutes of analysis completion
- [ ] CSV file automatically picked (latest file)
- [ ] Telegram notification sent
- [ ] Orders visible in Kotak Neo AMO section

#### 4.3 Verify AMO Orders (Before Market Open)

**Next morning before 9:15 AM:**

```powershell
# Check AMO orders
# Via Kotak Neo web/app: Orders → AMO Orders
```

**What to verify:**
- [ ] All AMO orders are queued
- [ ] Quantities and prices are correct
- [ ] No duplicate orders

**DECISION POINT:**
- **Keep orders**: Let them execute at market open
- **Cancel orders**: Cancel if testing only

#### 4.4 Monitor Market Open (9:15 AM)

**Watch for order execution:**

```powershell
# Check order status
# Via Kotak Neo: Orders → Order History
```

**What to check:**
- [ ] AMO orders executed at market open
- [ ] Fill prices reasonable (near market open price)
- [ ] Holdings updated with new positions

#### 4.5 Start Sell Monitoring (9:15 AM)

```powershell
# Start sell monitoring (runs until 3:30 PM)
python -m modules.kotak_neo_auto_trader.run_sell_orders --env modules\kotak_neo_auto_trader\kotak_neo.env --monitor-interval 60
```

**Or via Task Scheduler (recommended).**

**What to check:**
- [ ] Monitoring starts successfully
- [ ] Holdings reconciled every 60 seconds
- [ ] EMA9 calculated for each position
- [ ] Logs show decision process
- [ ] Stops automatically at 3:30 PM

#### 4.6 End of Day Review (After 3:30 PM)

**Check results:**

```powershell
# View trade history
Get-Content modules\kotak_neo_auto_trader\data\trades_history.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Review:**
- [ ] All trades logged correctly
- [ ] Entry and exit prices recorded
- [ ] P&L calculated (if exits occurred)
- [ ] No errors or exceptions in logs

**Check log files:**

```powershell
# View logs
Get-Content logs\trade_agent.log | Select-Object -Last 50
```

---

## Windows Task Scheduler Setup

### Automated Execution on Windows

#### Setup Analysis Task (4:00 PM Daily)

1. **Open Task Scheduler:**
   ```powershell
   taskschd.msc
   ```

2. **Create New Task:**
   - Click "Create Task" (not "Create Basic Task")
   - **Name:** `Trading Bot - Analysis`
   - **Description:** `Daily stock analysis at 4:00 PM`
   - **Security Options:**
     - ☑ Run whether user is logged on or not
     - ☑ Run with highest privileges

3. **Triggers Tab:**
   - Click "New"
   - **Begin the task:** On a schedule
   - **Settings:** Daily, start at 4:00 PM
   - **Advanced:**
     - ☑ Enabled
     - Repeat task every: (leave blank)
     - Stop task if it runs longer than: 1 hour

4. **Actions Tab:**
   - Click "New"
   - **Action:** Start a program
   - **Program/script:** `C:\Personal\Projects\TradingView\modular_trade_agent\.venv\Scripts\python.exe`
   - **Add arguments:** `trade_agent.py --backtest`
   - **Start in:** `C:\Personal\Projects\TradingView\modular_trade_agent`

5. **Conditions Tab:**
   - ☑ Start only if the computer is on AC power (uncheck if laptop)
   - ☑ Wake the computer to run this task

6. **Settings Tab:**
   - ☑ Allow task to be run on demand
   - ☑ Run task as soon as possible after a scheduled start is missed
   - If the task fails, restart every: 5 minutes, Attempt to restart up to: 3 times

7. **Click OK** and enter your Windows password.

#### Setup Buy Orders Task (4:05 PM Daily)

Repeat above steps with:
- **Name:** `Trading Bot - Buy Orders`
- **Time:** 4:05 PM (5 minutes after analysis)
- **Arguments:** `-m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env`

#### Setup Sell Monitoring Task (9:15 AM Daily)

Repeat above steps with:
- **Name:** `Trading Bot - Sell Monitor`
- **Time:** 9:15 AM
- **Arguments:** `-m modules.kotak_neo_auto_trader.run_sell_orders --env modules\kotak_neo_auto_trader\kotak_neo.env --monitor-interval 60`
- **Stop task if runs longer than:** 7 hours (runs until 3:30 PM automatically)

#### Test Scheduled Tasks

```powershell
# List all tasks
Get-ScheduledTask | Where-Object {$_.TaskName -like "*Trading Bot*"}

# Test run a task manually
Start-ScheduledTask -TaskName "Trading Bot - Analysis"

# Check last run result
Get-ScheduledTask -TaskName "Trading Bot - Analysis" | Get-ScheduledTaskInfo
```

---

## Monitoring & Logs

### Real-Time Log Monitoring

```powershell
# Monitor main log
Get-Content logs\trade_agent.log -Wait -Tail 50

# Monitor buy orders log (if exists)
Get-Content logs\buy_orders.log -Wait -Tail 50

# Monitor sell orders log (if exists)
Get-Content logs\sell_orders.log -Wait -Tail 50
```

### Daily Log Review

```powershell
# Check today's activity
Get-Content logs\trade_agent.log | Select-String (Get-Date -Format "yyyy-MM-dd")

# Count errors today
(Get-Content logs\trade_agent.log | Select-String "ERROR" | Select-String (Get-Date -Format "yyyy-MM-dd")).Count

# Find failed orders
Get-Content logs\trade_agent.log | Select-String "FAILED\|ERROR" | Select-Object -Last 10
```

### Analysis Results Review

```powershell
# List all analysis CSVs
Get-ChildItem analysis_results\bulk_analysis_final_*.csv | Sort-Object LastWriteTime -Descending

# Quick stats from latest CSV
python -c "import pandas as pd; import glob; files = glob.glob('analysis_results/bulk_analysis_final_*.csv'); df = pd.read_csv(sorted(files)[-1]); print('Total stocks:', len(df)); print('Strong Buys:', (df['final_verdict']=='strong_buy').sum()); print('Buys:', (df['final_verdict']=='buy').sum())"
```

### Trade History Review

```powershell
# View all trades
Get-Content modules\kotak_neo_auto_trader\data\trades_history.json | ConvertFrom-Json | Format-List

# Count total trades
(Get-Content modules\kotak_neo_auto_trader\data\trades_history.json | ConvertFrom-Json).Count

# Check recent trades
python -c "import json; data = json.load(open('modules/kotak_neo_auto_trader/data/trades_history.json')); print('Total trades:', len(data)); [print(f\"{t['symbol']}: {t['action']} @ {t['price']}\") for t in data[-5:]]"
```

---

## Troubleshooting

### Common Issues

#### 1. Task Scheduler Task Not Running

**Check last run result:**
```powershell
Get-ScheduledTaskInfo -TaskName "Trading Bot - Analysis"
```

**Common causes:**
- Computer was asleep/off at scheduled time
- Python path incorrect in task
- Working directory not set
- User credentials changed

**Fix:**
- Ensure computer is on and awake
- Verify paths in task settings
- Re-enter password for task
- Check "Run whether user is logged on or not"

#### 2. Authentication Failures

**Symptoms:**
- Login fails with 2FA errors
- Session cache errors

**Fix:**
```powershell
# Delete session cache
Remove-Item modules\kotak_neo_auto_trader\session_cache.json

# Test login fresh
python -m modules.kotak_neo_auto_trader.auth --test
```

**Verify credentials:**
```powershell
# Check TOTP secret generates valid codes
python -c "import pyotp; totp = pyotp.TOTP('YOUR_TOTP_SECRET'); print(totp.now())"
```

#### 3. Orders Not Placed

**Check logs:**
```powershell
Get-Content logs\trade_agent.log | Select-String "ERROR\|FAILED" | Select-Object -Last 20
```

**Common causes:**
- Insufficient funds
- Portfolio cap reached (max 6 positions)
- Symbol already in holdings
- Invalid ticker format
- Combined score below threshold (< 25)

**Debug:**
```powershell
# Check portfolio count
python -c "from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio; from modules.kotak_neo_auto_trader.auth import KotakNeoAuth; auth = KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env'); auth.login(); portfolio = KotakNeoPortfolio(auth.client); holdings = portfolio.get_holdings(); print('Holdings count:', len(holdings))"

# Check available funds
python -c "from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio; from modules.kotak_neo_auto_trader.auth import KotakNeoAuth; auth = KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env'); auth.login(); portfolio = KotakNeoPortfolio(auth.client); limits = portfolio.get_limits(); print(limits)"
```

#### 4. Sell Orders Not Triggering

**Verify EMA9 calculation:**
```powershell
# Check if price is actually below EMA9
python -c "import yfinance as yf; import pandas as pd; ticker = yf.Ticker('RELIANCE.NS'); df = ticker.history(period='1mo'); df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean(); print(df[['Close', 'EMA9']].tail(5))"
```

**Check monitoring logs:**
```powershell
Get-Content logs\sell_orders.log -Wait -Tail 50
```

**Common causes:**
- Price still above EMA9 (holding position correctly)
- Monitoring not running during market hours
- Holdings not fetched correctly
- Duplicate order prevention triggered

#### 5. CSV File Not Generated

**Check analysis completion:**
```powershell
# Verify CSV export flag
python trade_agent.py --backtest  # Should create CSV by default

# Check for errors
Get-Content logs\trade_agent.log | Select-String "CSV\|export"
```

**Manual CSV check:**
```powershell
Get-ChildItem analysis_results\bulk_analysis_final_*.csv | Select-Object Name, LastWriteTime, Length
```

#### 6. Telegram Notifications Not Sent

**Test connection:**
```powershell
python -c "from core.telegram import send_telegram; send_telegram('Windows test OK')"
```

**Check credentials:**
```powershell
Get-Content cred.env
```

**Verify bot token and chat ID are correct.**

---

## Safety Checklist Before Production

Before deploying to Oracle Cloud or running with full capital:

- [ ] All Phase 1-4 tests passed successfully
- [ ] Test orders placed and cancelled correctly
- [ ] Sell monitoring works as expected
- [ ] Task Scheduler tasks run automatically
- [ ] Logs are clean with no critical errors
- [ ] Tick size rounding validated
- [ ] Portfolio cap enforced correctly
- [ ] Duplicate order prevention working
- [ ] Telegram notifications reliable
- [ ] Trade history tracking accurate
- [ ] Weekend/holiday detection working
- [ ] Session caching functional
- [ ] 2FA authentication reliable

### Risk Management Settings

**Before production, verify in `config.py`:**
```python
CAPITAL_PER_TRADE = 100000      # ₹1 Lakh per trade (or your preferred amount)
MAX_PORTFOLIO_SIZE = 6          # Maximum 6 concurrent positions
MIN_COMBINED_SCORE = 25         # Minimum quality threshold
DEFAULT_ORDER_TYPE = "MARKET"   # Market orders for AMO
```

### Emergency Stop

**If something goes wrong:**

1. **Stop all scheduled tasks:**
   ```powershell
   Stop-ScheduledTask -TaskName "Trading Bot - Analysis"
   Stop-ScheduledTask -TaskName "Trading Bot - Buy Orders"
   Stop-ScheduledTask -TaskName "Trading Bot - Sell Monitor"
   ```

2. **Cancel all pending orders:**
   - Log into Kotak Neo platform
   - Go to Orders → Cancel all AMO/pending orders

3. **Disable tasks:**
   ```powershell
   Disable-ScheduledTask -TaskName "Trading Bot - Analysis"
   Disable-ScheduledTask -TaskName "Trading Bot - Buy Orders"
   Disable-ScheduledTask -TaskName "Trading Bot - Sell Monitor"
   ```

4. **Review logs and fix issues before re-enabling.**

---

## Next Steps

After successful local testing:

1. ✅ **Verify all tests pass** (Phases 1-4)
2. ✅ **Run for 1-2 weeks locally** with small capital
3. ✅ **Review performance** and fine-tune parameters
4. ✅ **Deploy to Oracle Cloud** using `documents/deployment/oracle/ORACLE_CLOUD_DEPLOYMENT.md`
5. ✅ **Monitor production** for first few trades
6. ✅ **Scale up capital** gradually once confident

---

## Support

**Logs location:**
- Main: `logs/trade_agent.log`
- Task Scheduler: Event Viewer → Task Scheduler logs

**Data files:**
- Analysis: `analysis_results/`
- Trade history: `modules/kotak_neo_auto_trader/data/trades_history.json`
- Session cache: `modules/kotak_neo_auto_trader/session_cache.json`

**Configuration files:**
- Trading parameters: `modules/kotak_neo_auto_trader/config.py`
- Settings: `config/settings.py`
- Credentials: `cred.env`, `modules/kotak_neo_auto_trader/kotak_neo.env`

---

**Testing Status:** Ready for Local Testing  
**Last Updated:** 2025-01-27  
**Platform:** Windows 10/11 with PowerShell  
**Next:** Oracle Cloud Production Deployment
