# Sell Order Monitoring Not Running - Issue Analysis & Fix

**Note**: This document describes a historical fix for v1.0 (separate task architecture).
v2.1+ uses the unified continuous service (run_trading_service.py).

**Date**: October 31, 2024
**Issue**: EMA9 target updates not happening - sell orders not being modified with lower prices

---

## Problem Identified

###  1. Monitoring Script Exits After Placing Orders
From logs at 09:38 AM:
```
2025-10-31 09:38:43 — INFO — run_sell_orders — ✅ Phase 1 complete: 2 sell orders placed
2025-10-31 09:38:43 — INFO — run_sell_orders — Run-once mode - exiting after order placement
2025-10-31 09:38:43 — INFO — run_sell_orders — Sell order management session ended
```

**Root Cause**: Script running in "run-once" mode instead of continuous monitoring mode.

### 2. LTP Fetching Works Fine
- Position monitor shows LTP is being fetched correctly:
  - DALBHARAT: ₹2,096.90
  - GALLANTT: ₹521.95
- EMA9 calculation working:
  - DALBHARAT EMA9: ₹2,124.19
  - GALLANTT EMA9: ₹543.86

### 3. Scheduled Task Status
```
LastRunTime: 30-11-1999 12:00:00 AM (Never ran)
LastTaskResult: 267011 (Error)
NextRunTime: 03-11-2025 09:00:00 AM
```

**The scheduled task has never successfully run!**

---

## Why Monitoring Isn't Working

### Phase 1: Order Placement ✅ WORKING
- Runs at 9:15 AM
- Places sell orders with initial EMA9 targets
- DALBHARAT: Placed @ ₹2,131.10
- GALLANTT: Placed @ ₹2,549.35

### Phase 2: Continuous Monitoring ❌ NOT RUNNING
- **Should** monitor every 60 seconds
- **Should** calculate new EMA9 with real-time LTP
- **Should** modify orders if lower EMA9 found
- **Currently**: Script exits immediately after Phase 1

---

## Expected Behavior

### Normal Workflow:
1. ✅ Script starts at 9:00 AM
2. ✅ Waits until 9:15 AM
3. ✅ Places sell orders (Phase 1)
4. ❌ **Enters monitoring loop (Phase 2)** ← THIS IS MISSING
5. ❌ Every 60 seconds:
   - Get current LTP
   - Calculate new EMA9
   - If new EMA9 < current target:
     - Modify sell order with new lower price
     - Log: "New lower EMA9 found"
6. ❌ Continue until 3:30 PM or all orders executed

---

## Solutions

### Solution 1: Ensure Scheduled Task Runs Correctly ✅ RECOMMENDED

**Check current task configuration:**
```powershell
Get-ScheduledTask -TaskName "TradingBot-SellMonitor" | Select-Object -ExpandProperty Actions
```

**Expected output** (should NOT have `--run-once`):
```
Arguments: -m modules.kotak_neo_auto_trader.run_sell_orders
           --env modules\kotak_neo_auto_trader\kotak_neo.env
           --monitor-interval 60
```

**If task has issues, recreate it:**
```powershell
# Remove old task
Unregister-ScheduledTask -TaskName "TradingBot-SellMonitor" -Confirm:$false

# Create new task
$action = New-ScheduledTaskAction `
    -Execute "C:\Personal\Projects\TradingView\modular_trade_agent\.venv\Scripts\python.exe" `
    -Argument "-m modules.kotak_neo_auto_trader.run_sell_orders --env modules\kotak_neo_auto_trader\kotak_neo.env --monitor-interval 60" `
    -WorkingDirectory "C:\Personal\Projects\TradingView\modular_trade_agent"

$trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 8) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "TradingBot-SellMonitor" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Monitor and update sell orders with EMA9 targets"
```

---

### Solution 2: Manual Test Run

**Test monitoring immediately** (without waiting):
```powershell
cd C:\Personal\Projects\TradingView\modular_trade_agent
.\.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_sell_orders `
    --env modules\kotak_neo_auto_trader\kotak_neo.env `
    --monitor-interval 60 `
    --skip-wait
```

**Expected output**:
```
==========================================================
PHASE 1: PLACING SELL ORDERS AT MARKET OPEN
==========================================================
⏭️ Skipping DALBHARAT: Existing sell order found...
⏭️ Skipping GALLANTT: Existing sell order found...
✅ Phase 1 complete: 2 sell orders placed

==========================================================
PHASE 2: CONTINUOUS MONITORING
==========================================================
Monitoring every 60 seconds until market close (3:30 PM)
Press Ctrl+C to stop

--- Monitor Cycle #1 (11:45:30) ---
Monitor cycle: 2 checked, 0 updated, 0 executed

--- Monitor Cycle #2 (11:46:30) ---
DALBHARAT: New lower EMA9 found - ₹2120.50 (was ₹2131.10)
Modifying order 251031000083038: DALBHARAT-EQ x233 @ ₹2120.50
✅ Order modified successfully: DALBHARAT-EQ @ ₹2120.50
Monitor cycle: 2 checked, 1 updated, 0 executed
```

---

### Solution 3: Check for Running Process

**See if script is already running:**
```powershell
Get-Process python | Where-Object {$_.CommandLine -like "*run_sell_orders*"}
```

**If found, check its output/logs:**
```powershell
# The script should be actively writing to logs
Get-Content logs\trade_agent_$(Get-Date -Format "yyyyMMdd").log -Tail 20 -Wait
```

---

## Verification Steps

### 1. Check if Monitoring Loop is Active
Look for these log patterns every 60 seconds:
```
--- Monitor Cycle #X (HH:MM:SS) ---
Monitor cycle: N checked, M updated, P executed
```

### 2. Verify EMA9 Calculations
Should see DEBUG logs like:
```
DALBHARAT.NS - Yesterday EMA9: ₹2139.59, LTP: ₹2096.90, Current EMA9: ₹2131.05
```

### 3. Check for Order Modifications
When lower EMA9 found:
```
DALBHARAT: New lower EMA9 found - ₹2120.50 (was ₹2131.10)
Modifying order 251031000083038...
✅ Order modified successfully
```

### 4. Verify Orders in Broker
```powershell
# Check current sell orders
.\.venv\Scripts\python.exe -c "
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
auth = KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env')
auth.login()
orders = KotakNeoOrders(auth)
print(orders.get_pending_orders())
"
```

---

## Current State Analysis

### What's Working ✅
1. LTP fetching via Kotak Neo API
2. EMA9 calculation with real-time data
3. Order placement at market open
4. modify_order API (tested successfully)

### What's NOT Working ❌
1. **Continuous monitoring loop not running**
2. Orders not being updated with lower EMA9
3. Scheduled task never successfully executed
4. Script exits after placing orders

---

## Immediate Action Required

### Today (Oct 31):
1. ✅ **Manually start monitoring** for remaining market hours:
   ```powershell
   .\.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_sell_orders `
       --env modules\kotak_neo_auto_trader\kotak_neo.env `
       --monitor-interval 60 `
       --skip-wait
   ```

2. ⏳ **Monitor logs** to confirm it's working:
   ```powershell
   Get-Content logs\trade_agent_20251031.log -Tail 50 -Wait
   ```

3. ⏳ **Verify order updates** happen when EMA9 drops

### Tomorrow (Nov 1):
1. ✅ **Fix scheduled task** (use Solution 1)
2. ✅ **Test task execution** before market open
3. ✅ **Verify monitoring starts automatically** at 9:00 AM

---

## Root Cause Summary

**The sell order monitoring script is configured correctly**, but:
- Scheduled task has never run successfully (error code 267011)
- Manual runs might have been with `--run-once` flag
- Script exits after Phase 1 instead of continuing to Phase 2
- No continuous monitoring = no EMA9 target updates = no order modifications

**Fix**: Ensure scheduled task runs without `--run-once` and stays active until market close.

---

## Success Criteria

After fix, you should see in logs:
```
09:00:00 — Script started, waiting for 9:15 AM
09:15:00 — Phase 1: Placed 2 sell orders
09:15:01 — Phase 2: Continuous monitoring started
09:16:01 — Monitor Cycle #1: 2 checked, 0 updated
09:17:01 — Monitor Cycle #2: 2 checked, 1 updated (DALBHARAT modified)
09:18:01 — Monitor Cycle #3: 2 checked, 0 updated
...
15:30:00 — Market closed, monitoring stopped
```

---

*Last Updated: October 31, 2024*
*Status: ISSUE IDENTIFIED - FIX PENDING*
