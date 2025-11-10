# Live Position Monitoring - Phase 3

**Status:** Production Ready  
**Date:** 2025-01-28  

---

## Overview

Live Position Monitoring provides hourly health checks for all open positions during market hours (9:30 AM - 3:30 PM).

**What It Does:**
- 📊 Monitors position health every hour
- 🎯 Alerts when exit conditions approaching
- 🔄 Detects averaging opportunities
- 💰 Tracks unrealized P&L
- 📱 Sends Telegram alerts for important events

---

## Features

### 1. Exit Proximity Alerts

Warns when positions are approaching exit conditions:

- **🎯 EXIT**: Price >= EMA9 or RSI10 > 50 (critical)
- **⚠️ EXIT APPROACHING**: Price within 2% of EMA9 (warning)
- **⚠️ EXIT APPROACHING**: RSI10 > 45 (warning)

### 2. Averaging Opportunity Detection

Alerts when RSI10 drops to next averaging level:

- **🔄 AVERAGING OPPORTUNITY**: RSI10 < 20 (second entry available)
- **🔄 AVERAGING OPPORTUNITY**: RSI10 < 10 (third entry available)

### 3. Large Price Movement Alerts

Notifies on significant price changes:

- **📈 GAIN**: Unrealized profit > 3%
- **📉 LOSS**: Unrealized loss > 3%

### 4. Position Health Tracking

For each position, monitors:
- Current price vs entry price
- Unrealized P&L (₹ and %)
- RSI10 current value
- Distance to EMA9 (%)
- Days held

---

## Installation

### Step 1: Files Already Created

```
modules/kotak_neo_auto_trader/
  ├── position_monitor.py       ✓ Live monitoring module
  └── run_position_monitor.py   ✓ Runner script

scripts/deploy/windows/
  └── add_position_monitoring.ps1  ✓ Task setup script
```

### Step 2: Add Scheduled Task

```powershell
# Navigate to deployment folder
cd C:\Personal\Projects\TradingView\modular_trade_agent\scripts\deploy\windows

# Run setup (as Administrator)
.\add_position_monitoring.ps1
```

**This creates:**
- Task: `TradingBot-PositionMonitor`
- Schedule: Every hour from 9:30 AM to 3:30 PM
- Days: Monday - Friday
- Auto-skips outside market hours

---

## Usage

### Automatic (Recommended)

Task runs automatically every hour during market hours. No action needed!

### Manual Testing

```powershell
# Test now (force run outside market hours)
python -m modules.kotak_neo_auto_trader.run_position_monitor --force

# Run without Telegram alerts
python -m modules.kotak_neo_auto_trader.run_position_monitor --no-alerts --force

# Check specific history file
python -m modules.kotak_neo_auto_trader.run_position_monitor --history data/trades_history.json
```

### Check Task Status

```powershell
# View task details
Get-ScheduledTask -TaskName "TradingBot-PositionMonitor" | Format-List

# Check last run result
Get-ScheduledTaskInfo -TaskName "TradingBot-PositionMonitor"

# Manually trigger
Start-ScheduledTask -TaskName "TradingBot-PositionMonitor"
```

---

## Telegram Alerts

### Alert Levels:

**🚨 CRITICAL** (Red)
- Exit condition MET (price >= EMA9 or RSI10 > 50)
- Immediate action required

**⚠️ WARNING** (Orange)
- Exit approaching (within 2% of EMA9 or RSI10 > 45)
- Averaging opportunity available
- Large price movement (>3%)

**ℹ️ INFO** (Blue)
- General position status updates

### Sample Alert:

```
🚨 POSITION ALERT

📊 Symbol: RELIANCE
💰 Current: ₹2,450.00
📦 Quantity: 50
💵 P&L: ₹12,500 (+5.38%)

📈 RSI10: 48.5
📉 EMA9: ₹2,445.00
📍 Distance to EMA9: +0.20%

*Alerts:*
  • ⚠️ EXIT APPROACHING: RSI10 (48.5) near 50
  • 📈 GAIN: 5.4% (₹12,500)

⏰ Time: 2025-01-28 11:30:00
```

---

## Configuration

### Alert Thresholds

Edit in `position_monitor.py`:

```python
class PositionMonitor:
    def __init__(self, ...):
        # Alert thresholds
        self.large_move_threshold = 3.0  # 3% price move
        self.exit_proximity_threshold = 2.0  # Within 2% of EMA9
        self.rsi_exit_warning = 45.0  # Alert when RSI > 45
```

### Monitoring Frequency

Default: Every 1 hour during market hours

To change frequency, edit trigger in `add_position_monitoring.ps1`:

```powershell
# Change from hourly to every 30 minutes
-RepetitionInterval (New-TimeSpan -Minutes 30)
```

---

## Monitoring Workflow

### 9:30 AM - Market Opens
- First monitoring run executes
- Checks all open positions
- Sends alerts if any conditions met

### Hourly During Market Hours
- 10:30 AM - Check positions
- 11:30 AM - Check positions
- 12:30 PM - Check positions
- 1:30 PM - Check positions
- 2:30 PM - Check positions
- 3:30 PM - Final check before close

### After 3:30 PM
- Task still runs but script auto-skips
- Logs "Outside market hours"
- No API calls made

---

## Logs

### Check Monitoring Logs

```powershell
# View recent monitoring activity
Get-Content logs\*.log | Select-String "POSITION" -Context 5

# Watch logs in real-time
Get-Content logs\*.log -Wait -Tail 50

# Check for specific symbol
Get-Content logs\*.log | Select-String "RELIANCE"
```

### Expected Log Output

```
======================================================================
LIVE POSITION MONITORING
======================================================================
Time: 2025-01-28 11:30:00

Monitoring 3 position(s)

Position: RELIANCE
  Price: ₹2,450.00 (Entry: ₹2,320.00)
  Quantity: 50
  P&L: ₹6,500 (+5.60%)
  RSI10: 48.5
  EMA9: ₹2,445.00 (Distance: +0.20%)
  Days Held: 5
  Alerts (WARNING):
    ⚠️ EXIT APPROACHING: RSI10 (48.5) near 50
    📈 GAIN: 5.6% (₹6,500)
  ✓ Telegram alert sent for RELIANCE

======================================================================
MONITORING SUMMARY
======================================================================
Positions Monitored: 3
Exit Imminent: 1
Averaging Opportunities: 0
Alerts Sent: 1
======================================================================
```

---

## Troubleshooting

### Issue: No Alerts Received

**Check:**
```powershell
# 1. Verify Telegram configured
echo $env:TELEGRAM_BOT_TOKEN
echo $env:TELEGRAM_CHAT_ID

# 2. Test Telegram connection
python -c "from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier; t = get_telegram_notifier(); t.send_message('Position monitor test')"

# 3. Check if alerts disabled
Get-Content logs\*.log | Select-String "alerts.*disabled"
```

### Issue: Task Not Running

**Check:**
```powershell
# 1. Verify task exists
Get-ScheduledTask -TaskName "TradingBot-PositionMonitor"

# 2. Check task state
Get-ScheduledTaskInfo -TaskName "TradingBot-PositionMonitor"

# 3. View last run result (0 = success)
(Get-ScheduledTaskInfo -TaskName "TradingBot-PositionMonitor").LastTaskResult
```

### Issue: "Outside market hours" in Logs

**This is normal!** Task still runs but script exits early when:
- Before 9:15 AM
- After 3:30 PM
- Saturday/Sunday

To force run for testing:
```powershell
python -m modules.kotak_neo_auto_trader.run_position_monitor --force
```

---

## Integration with Existing System

### Works Seamlessly With:

**Phase 1 - Order Tracking** ✅
- Reads from `trades_history.json`
- Uses same tracking data

**Phase 2 - Telegram Notifications** ✅
- Uses existing Telegram notifier
- Same notification style

**Existing Exit Logic** ✅
- Monitoring is **read-only**
- Does NOT place exit orders
- Only alerts when conditions detected
- Actual exits still handled by `evaluate_reentries_and_exits()`

---

## Performance Impact

- **API Calls:** Read-only (positions data from history + yfinance for indicators)
- **Execution Time:** ~5-30 seconds per run (depends on # of positions)
- **Resource Usage:** Minimal (<50MB RAM, <1% CPU)
- **No Impact on Trading:** Monitoring is completely separate from order execution

---

## Daily Workflow

### Your Complete Daily Schedule:

| Time | Task | Purpose |
|------|------|---------|
| **8:00 AM** | PreMarketRetry | Retry failed orders |
| **9:30 AM** | **PositionMonitor** | **First position check** |
| **10:30 AM** | **PositionMonitor** | **Hourly check** |
| **11:30 AM** | **PositionMonitor** | **Hourly check** |
| **12:30 PM** | **PositionMonitor** | **Hourly check** |
| **1:30 PM** | **PositionMonitor** | **Hourly check** |
| **2:30 PM** | **PositionMonitor** | **Hourly check** |
| **3:30 PM** | **PositionMonitor** | **Final check** |
| **4:00 PM** | Analysis | Generate recommendations |
| **4:05 PM** | PlaceOrders | Place AMO orders |
| **6:00 PM** | EOD Cleanup | End-of-day tasks |

---

## What's Next

Position monitoring is now active! Other Phase 3 enhancements to consider:

1. **Performance Dashboard** - Visual reports and charts
2. **Portfolio Analytics** - Historical performance tracking
3. **Advanced Alerts** - Custom alert conditions
4. **Risk Metrics** - Real-time risk tracking

---

**Version:** 3.0 (Phase 3 - Live Monitoring)  
**Last Updated:** 2025-01-28  
**Status:** ✅ Production Ready
