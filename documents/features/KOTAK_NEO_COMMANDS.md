# 🤖 Kotak Neo Auto Trader - Command Reference

Complete guide to all Kotak Neo automated trading commands.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Setup](#setup)
3. [Buy Orders (AMO)](#buy-orders-amo)
4. [Sell Orders](#sell-orders)
5. [Position Monitoring](#position-monitoring)
6. [End-of-Day Cleanup](#end-of-day-cleanup)
7. [Complete Workflow](#complete-workflow)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Kotak Neo Auto Trader provides automated order placement and position management for the trading system. It includes:

- ✅ **AMO Buy Orders** - Place after-market orders at 4 PM
- ✅ **Sell Order Management** - Automated profit-taking with EMA9 targets
- ✅ **Position Monitoring** - Real-time position tracking during market hours
- ✅ **EOD Cleanup** - Daily reconciliation and reporting

---

## Setup

### Prerequisites

1. **Kotak Neo API Credentials**
   - Consumer Key
   - Consumer Secret
   - Mobile Number
   - Password
   - MPIN or TOTP Secret

2. **Configuration File**

Create `modules/kotak_neo_auto_trader/kotak_neo.env`:

```env
KOTAK_CONSUMER_KEY=your_consumer_key
KOTAK_CONSUMER_SECRET=your_consumer_secret
KOTAK_MOBILE_NUMBER=9876543210
KOTAK_PASSWORD=your_password
KOTAK_MPIN=123456
# OR
KOTAK_TOTP_SECRET=your_totp_secret
KOTAK_ENVIRONMENT=prod

# Optional Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

3. **Trading Parameters**

Edit `modules/kotak_neo_auto_trader/config.py`:

```python
CAPITAL_PER_TRADE = 100000       # ₹1 lakh per position
MAX_PORTFOLIO_SIZE = 6           # Max 6 concurrent positions
MIN_COMBINED_SCORE = 25          # Minimum signal score
```

---

## Buy Orders (AMO)

### Command: `run_place_amo`

Places After Market Orders (AMO) for buy recommendations from analysis CSV.

### Basic Usage

```powershell
# Use latest CSV automatically
python -m modules.kotak_neo_auto_trader.run_place_amo

# Specify CSV file
python -m modules.kotak_neo_auto_trader.run_place_amo --csv analysis_results\bulk_analysis_final_20251029_160000.csv

# Custom env file
python -m modules.kotak_neo_auto_trader.run_place_amo --env path\to\kotak_neo.env

# Logout after completion
python -m modules.kotak_neo_auto_trader.run_place_amo --logout
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--env` | Path to credentials file | `modules/kotak_neo_auto_trader/kotak_neo.env` |
| `--csv` | Path to analysis CSV | Auto-detects latest |
| `--logout` | Logout after placing orders | Keep session active |

### What It Does

1. ✅ **Pre-Flight Checks:**
   - Verifies portfolio cap (MAX_PORTFOLIO_SIZE)
   - Checks if symbol already in holdings
   - Cancels duplicate pending BUY orders
   - Verifies sufficient account balance

2. ✅ **Order Placement:**
   - Places AMO MARKET orders
   - Calculates quantity: `floor(CAPITAL_PER_TRADE / last_close)`
   - Uses NSE/BSE tick size rounding
   - Orders execute next trading day at market open

3. ✅ **Notifications:**
   - Telegram alerts for each order
   - Insufficient funds warnings
   - Order status updates

### Example Output

```
2025-10-29 16:05:00 — INFO — Authenticating with Kotak Neo...
2025-10-29 16:05:02 — INFO — ✅ Login successful
2025-10-29 16:05:03 — INFO — Loading recommendations from CSV...
2025-10-29 16:05:04 — INFO — Found 3 BUY candidates
2025-10-29 16:05:05 — INFO — Portfolio: 4/6 positions
2025-10-29 16:05:06 — INFO — ✅ AMO placed: RELIANCE x 50 @ ₹2850
2025-10-29 16:05:07 — INFO — ✅ AMO placed: TCS x 30 @ ₹3500
2025-10-29 16:05:08 — INFO — ⚠️  Skipped INFY (already in holdings)
2025-10-29 16:05:09 — INFO — AMO placement summary: {'placed': 2, 'skipped': 1}
```

---

## Sell Orders

### Command: `run_sell_orders`

Automated sell order management with EMA9 profit targets.

### Basic Usage

```powershell
# Standard run (wait for market open, then monitor)
python -m modules.kotak_neo_auto_trader.run_sell_orders

# Custom env file
python -m modules.kotak_neo_auto_trader.run_sell_orders --env kotak_neo.env

# Place once and exit (no monitoring)
python -m modules.kotak_neo_auto_trader.run_sell_orders --run-once

# Skip waiting for market open (testing)
python -m modules.kotak_neo_auto_trader.run_sell_orders --skip-wait

# Custom monitoring interval
python -m modules.kotak_neo_auto_trader.run_sell_orders --monitor-interval 30
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--env` | Path to credentials file | `kotak_neo.env` |
| `--monitor-interval` | Monitor interval in seconds | `60` |
| `--skip-wait` | Skip waiting for market open | Wait until 9:15 AM |
| `--run-once` | Place orders once and exit | Continuous monitoring |

### What It Does

**Phase 1: Market Open (9:15 AM)**
1. ✅ Fetches all open positions from portfolio
2. ✅ Calculates current EMA9 for each position
3. ✅ Places LIMIT sell orders at EMA9 price
4. ✅ Records order details in trade history

**Phase 2: Continuous Monitoring (9:15 AM - 3:30 PM)**
1. ✅ Checks positions every minute
2. ✅ Updates sell orders if lower EMA9 found
3. ✅ Marks positions as closed when orders execute
4. ✅ Stops when all positions closed or market closes

### Execution Flow

```
9:15 AM  → Place sell orders at EMA9
9:16 AM  → Check for lower EMA9, update if found
9:17 AM  → Check execution status
...
3:30 PM  → Market close - stop monitoring
```

### Example Output

```
=============================================================
SELL ORDER MANAGEMENT SYSTEM
=============================================================
2025-10-29 09:15:00 — INFO — Market opened - starting sell order placement
2025-10-29 09:15:01 — INFO — Authenticating with Kotak Neo...
2025-10-29 09:15:03 — INFO — ✅ Authentication successful
2025-10-29 09:15:04 — INFO — ✅ Sell Order Manager initialized

=============================================================
PHASE 1: PLACING SELL ORDERS AT MARKET OPEN
=============================================================
2025-10-29 09:15:05 — INFO — Found 4 open positions
2025-10-29 09:15:06 — INFO — RELIANCE: EMA9 = ₹2950, placing sell order for 50 qty
2025-10-29 09:15:07 — INFO — ✅ Order placed: RELIANCE x 50 @ ₹2950
2025-10-29 09:15:08 — INFO — TCS: EMA9 = ₹3600, placing sell order for 30 qty
2025-10-29 09:15:09 — INFO — ✅ Order placed: TCS x 30 @ ₹3600
2025-10-29 09:15:10 — INFO — ✅ Phase 1 complete: 4 sell orders placed

=============================================================
PHASE 2: CONTINUOUS MONITORING
=============================================================
Monitoring every 60 seconds until market close (3:30 PM)
Press Ctrl+C to stop

--- Monitor Cycle #1 (09:16:15) ---
2025-10-29 09:16:15 — INFO — Checking 4 positions...
2025-10-29 09:16:16 — INFO — RELIANCE: EMA9 still ₹2950 (no update needed)
2025-10-29 09:16:17 — INFO — TCS: EMA9 dropped to ₹3580, updating order
2025-10-29 09:16:18 — INFO — ✅ Order updated: TCS x 30 @ ₹3580

--- Monitor Cycle #2 (09:17:15) ---
2025-10-29 09:17:15 — INFO — Checking 4 positions...
2025-10-29 09:17:16 — INFO — ✅ RELIANCE order executed! Position closed.
2025-10-29 09:17:17 — INFO — 3 positions remaining

=============================================================
SESSION SUMMARY
=============================================================
Total monitor cycles: 124
Positions checked: 496
Orders updated: 15
Orders executed: 4
=============================================================
```

---

## Position Monitoring

### Command: `run_position_monitor`

Real-time monitoring of open positions during market hours.

### Basic Usage

```powershell
# Standard monitoring (market hours only)
python -m modules.kotak_neo_auto_trader.run_position_monitor

# Custom history file
python -m modules.kotak_neo_auto_trader.run_position_monitor --history data\trades_history.json

# Disable Telegram alerts
python -m modules.kotak_neo_auto_trader.run_position_monitor --no-alerts

# Force run outside market hours
python -m modules.kotak_neo_auto_trader.run_position_monitor --force
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--history` | Path to trades history | `data/trades_history.json` |
| `--no-alerts` | Disable Telegram alerts | Alerts enabled |
| `--force` | Run outside market hours | Market hours only |

### What It Does

1. ✅ **Monitors Positions:**
   - Checks current RSI and EMA levels
   - Tracks distance to stop-loss
   - Monitors profit/loss

2. ✅ **Exit Signals:**
   - Detects when RSI > 50 or price < EMA9
   - Sends imminent exit warnings
   - Tracks position health

3. ✅ **Averaging Opportunities:**
   - Identifies oversold conditions (RSI < 30)
   - Suggests position averaging
   - Calculates new average entry price

4. ✅ **Telegram Alerts:**
   - Exit imminent notifications
   - Averaging opportunity alerts
   - Position status updates

### Example Output

```
======================================================================
POSITION MONITOR RUNNER
======================================================================
Time: 2025-10-29 10:30:00

2025-10-29 10:30:01 — INFO — Initializing position monitor...
2025-10-29 10:30:02 — INFO — Monitoring 4 open positions

Position: RELIANCE
  Entry: ₹2850, Current: ₹2920
  P/L: +₹3,500 (+2.46%)
  RSI: 45.2, EMA9: ₹2880
  Status: ✅ Healthy

Position: TCS
  Entry: ₹3500, Current: ₹3480
  P/L: -₹600 (-0.57%)
  RSI: 52.1, EMA9: ₹3490
  Status: ⚠️  EXIT IMMINENT (RSI > 50)
  → Telegram alert sent

Position: INFY
  Entry: ₹1450, Current: ₹1380
  P/L: -₹2,100 (-4.83%)
  RSI: 25.3, EMA9: ₹1420
  Status: 🔄 AVERAGING OPPORTUNITY (RSI < 30)
  → Telegram alert sent

======================================================================
MONITORING COMPLETE
======================================================================
Positions Monitored: 4
Exit Imminent: 1
Averaging Opportunities: 1
Alerts Sent: 2
======================================================================
```

---

## End-of-Day Cleanup

### Command: `run_eod_cleanup`

Daily reconciliation and reporting at market close.

### Basic Usage

```powershell
# Standard EOD cleanup
python -m modules.kotak_neo_auto_trader.run_eod_cleanup

# Custom env file
python -m modules.kotak_neo_auto_trader.run_eod_cleanup --env path\to\kotak_neo.env
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--env` | Path to credentials file | `kotak_neo.env` |

### What It Does

1. ✅ **Portfolio Reconciliation:**
   - Compares broker holdings vs trade history
   - Detects manual trades
   - Updates position status

2. ✅ **Order Status Check:**
   - Verifies all pending orders
   - Marks executed orders
   - Cancels stale orders

3. ✅ **Trade History Update:**
   - Updates P/L for open positions
   - Marks closed positions
   - Calculates daily returns

4. ✅ **Daily Report:**
   - Portfolio summary
   - Open positions
   - Daily P/L
   - Performance metrics

5. ✅ **Telegram Summary:**
   - End-of-day portfolio status
   - Daily performance
   - Action items for next day

6. ✅ **Data Backup:**
   - Backs up trade history
   - Archives order logs
   - Saves daily snapshots

### Example Output

```
======================================================================
STARTING EOD CLEANUP RUNNER
======================================================================
2025-10-29 15:35:00 — INFO — Authenticating...
2025-10-29 15:35:02 — INFO — Login successful

Step 1/6: Portfolio Reconciliation
  - Broker holdings: 4 positions
  - Trade history: 4 positions
  - ✅ Reconciled successfully

Step 2/6: Order Status Check
  - Pending orders: 2
  - Executed today: 3
  - ✅ Updated order statuses

Step 3/6: Trade History Update
  - Open positions: 4
  - Closed today: 1
  - ✅ Updated P/L values

Step 4/6: Daily Report Generation
  - Total positions: 4
  - Total P/L: +₹12,450 (+3.12%)
  - Win rate: 75%
  - ✅ Report generated

Step 5/6: Telegram Summary
  - Portfolio value: ₹4,12,450
  - Open positions: 4
  - Daily gain: +₹12,450
  - ✅ Summary sent

Step 6/6: Data Backup
  - Backed up: data/trades_history_20251029.json
  - ✅ Backup complete

======================================================================
EOD CLEANUP SUMMARY
======================================================================
Success: True
Duration: 15.3s
Steps Completed: 6/6
Steps Failed: 0/6
======================================================================
```

---

## Complete Workflow

### Daily Trading Cycle

```
4:00 PM  → Generate analysis (trade_agent.py --backtest)
4:05 PM  → Place AMO buy orders (run_place_amo)
9:15 AM  → AMO orders execute at market open
9:15 AM  → Place sell orders (run_sell_orders) [runs until 3:30 PM]
10:00 AM → Position monitoring (run_position_monitor) [hourly]
3:30 PM  → Market closes, sell monitoring stops
3:35 PM  → EOD cleanup (run_eod_cleanup)
```

### Automated Execution (Windows Task Scheduler)

**Task 1: Analysis & Buy Orders (4:00 PM)**
```batch
cd C:\TradingAgent
.venv\Scripts\python.exe trade_agent.py --backtest
.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_place_amo
```

**Task 2: Sell Orders (9:15 AM)**
```batch
cd C:\TradingAgent
.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_sell_orders
```

**Task 3: Position Monitoring (Every hour 10:00 AM - 3:00 PM)**
```batch
cd C:\TradingAgent
.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_position_monitor
```

**Task 4: EOD Cleanup (3:35 PM)**
```batch
cd C:\TradingAgent
.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_eod_cleanup
```

---

## Troubleshooting

### Authentication Failures

**Problem:** Login fails or 2FA errors

**Solutions:**
```powershell
# Delete session cache
Remove-Item modules\kotak_neo_auto_trader\session_cache.json

# Verify credentials
cat modules\kotak_neo_auto_trader\kotak_neo.env

# Test authentication
python -m modules.kotak_neo_auto_trader.auth
```

### Portfolio Cap Reached

**Problem:** "Portfolio cap reached" message

**Solution:**
```python
# Edit config.py
MAX_PORTFOLIO_SIZE = 10  # Increase from 6 to 10
```

### Insufficient Funds

**Problem:** "Insufficient funds" notification

**Solutions:**
- Check account balance via broker platform
- Reduce CAPITAL_PER_TRADE in config.py
- Close some positions to free up capital

### Order Rejections

**Problem:** Orders rejected by exchange

**Common causes:**
- Invalid tick size (fixed automatically)
- Insufficient margin
- Stock circuit limits
- Order size limits

**Solution:**
Check logs for specific rejection reason

### Sell Orders Not Updating

**Problem:** Sell orders not updating with new EMA9

**Solutions:**
```powershell
# Check if sell monitoring is running
Get-Process python

# Check logs
cat logs\trade_agent.log | Select-String "sell"

# Restart sell monitoring
python -m modules.kotak_neo_auto_trader.run_sell_orders --skip-wait
```

---

## Advanced Usage

### Manual Order Placement

```python
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

auth = KotakNeoAuth("kotak_neo.env")
auth.login()

orders = KotakNeoOrders(auth)
order_id = orders.place_order(
    symbol="RELIANCE",
    exchange="NSE",
    quantity=50,
    price=2850.0,
    order_type="LIMIT",
    side="BUY",
    product="CNC"
)
```

### Custom Monitoring Script

```python
from modules.kotak_neo_auto_trader.position_monitor import PositionMonitor
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

auth = KotakNeoAuth("kotak_neo.env")
auth.login()

monitor = PositionMonitor(auth, history_path="data/trades_history.json")
results = monitor.monitor_all_positions()

print(f"Monitored: {results['monitored']}")
print(f"Exit signals: {results['exit_imminent']}")
```

---

## Security Best Practices

1. **Never commit credentials:**
   ```bash
   # Add to .gitignore
   kotak_neo.env
   session_cache.json
   ```

2. **Use environment variables:**
   ```powershell
   $env:KOTAK_CONSUMER_KEY = "your_key"
   ```

3. **Rotate credentials regularly**

4. **Monitor API usage limits**

5. **Keep session cache secure:**
   - Located at `modules/kotak_neo_auto_trader/session_cache.json`
   - Contains daily auth tokens
   - Auto-expires end-of-day

---

## Performance Optimization

### Reduce API Calls

```python
# config.py
CACHE_DURATION = 60  # Cache portfolio for 60 seconds
```

### Batch Operations

```powershell
# Run all operations in sequence
python -m modules.kotak_neo_auto_trader.run_place_amo && ^
python -m modules.kotak_neo_auto_trader.run_sell_orders --run-once
```

### Monitoring Intervals

```powershell
# Reduce frequency during slow markets
python -m modules.kotak_neo_auto_trader.run_sell_orders --monitor-interval 120
```

---

## Logging

All commands log to:
- **Console:** Real-time output
- **File:** `logs/trade_agent.log`

**View logs:**
```powershell
# View latest logs
Get-Content logs\trade_agent.log -Tail 50

# Filter by module
Select-String -Path logs\trade_agent.log -Pattern "kotak_neo"

# Follow live
Get-Content logs\trade_agent.log -Wait
```

---

## Support

**Need help?**
1. Check [KOTAK_NEO_ARCHITECTURE_PLAN.md](../architecture/KOTAK_NEO_ARCHITECTURE_PLAN.md)
2. Review logs in `logs/trade_agent.log`
3. Test individual components
4. Check broker platform for order status

---

**Last Updated:** 2025-10-29  
**Version:** 1.0.0
