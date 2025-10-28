# Windows Deployment Update - Phase 1 & 2 Complete

**Status:** Ready to Deploy  
**Date:** 2025-01-28  

---

## Changes Summary

### ✅ What Changed:

1. **Removed:** `run_sell_orders.py` (old design)
2. **Added:** `run_eod_cleanup.py` (Phase 2 feature)
3. **Updated:** Scheduled task configuration
4. **Added:** New task for EOD cleanup (6:00 PM)

### 🆕 New Files Created:

- `run_eod_cleanup.py` - EOD cleanup runner
- `setup_scheduled_tasks_phase2.ps1` - Updated task scheduler

---

## Deployment Steps

### Step 1: Update Existing Tasks (If Already Deployed)

```powershell
# Navigate to deployment guide folder
cd C:\Personal\Projects\TradingView\modular_trade_agent\win_local_deployment_guide

# Run updated setup (as Administrator)
.\setup_scheduled_tasks_phase2.ps1
```

**This will:**
- ✅ Keep existing: Analysis, PlaceOrders, PreMarketRetry
- ✅ Remove: TradingBot-SellMonitor (old)
- ✅ Add: TradingBot-EODCleanup (new)

### Step 2: Verify Tasks Created

```powershell
# Check task status
.\manage_tasks.ps1 status
```

**Expected Output:**
```
Task: TradingBot-Analysis
  State       : Ready
  Next Run    : [Date Time]

Task: TradingBot-PlaceOrders
  State       : Ready
  Next Run    : [Date Time]

Task: TradingBot-PreMarketRetry
  State       : Ready
  Next Run    : [Date Time]

Task: TradingBot-EODCleanup
  State       : Ready
  Next Run    : [Date Time]
```

---

## Task Schedule (Updated)

### Daily Workflow:

| Time | Task | Description | Phase |
|------|------|-------------|-------|
| **8:00 AM** | PreMarketRetry | Retry failed orders from previous day | 1 |
| **4:00 PM** | Analysis | Analyze stocks, generate recommendations | - |
| **4:05 PM** | PlaceOrders | Place AMO orders with tracking | 1 & 2 |
| **6:00 PM** | **EODCleanup** | **End-of-day cleanup (6 steps)** | **2** |

---

## Phase 2 Features Active

### Order Placement (4:05 PM):
- ✅ Tracking scope registers orders (Phase 1)
- ✅ Order IDs extracted (Phase 1)
- ✅ Pending orders tracked (Phase 1)
- ✅ **Order verifier starts automatically (Phase 2)**
  - Checks every 30 minutes
  - Detects execution/rejection
  - Sends Telegram notifications

### EOD Cleanup (6:00 PM):
- ✅ **Step 1:** Final order verification
- ✅ **Step 2:** Manual trade reconciliation
- ✅ **Step 3:** Stale order cleanup
- ✅ **Step 4:** Daily statistics generation
- ✅ **Step 5:** Telegram daily summary
- ✅ **Step 6:** Archive completed entries

---

## Telegram Notifications

You will now receive:

### During Market Hours:
- 📦 **Order Placed** - When AMO order is placed
- ✅ **Order Executed** - When order is filled (30-min checks)
- 🚫 **Order Rejected** - When order fails

### End of Day (6:00 PM):
- 📊 **Daily Summary** - Statistics, performance, alerts
- 📈 **Manual Buy Detected** - If you bought manually
- 📉 **Manual Sell Detected** - If you sold manually
- 🛑 **Tracking Stopped** - If position was closed

---

## Testing Your Deployment

### Test 1: Verify EOD Cleanup Works

```powershell
# Manually trigger EOD cleanup
Start-ScheduledTask -TaskName "TradingBot-EODCleanup"

# Monitor progress
Get-Content logs\*.log -Wait -Tail 50
```

**Expected:**
- 6 steps complete
- Telegram summary received
- No errors in logs

### Test 2: Check Task History

```powershell
# Open Task Scheduler
taskschd.msc

# Navigate to: Task Scheduler Library
# Find: TradingBot-* tasks
# Check: Last Run Result should be "Success (0x0)"
```

---

## Troubleshooting

### Issue: Task Not Running

**Check:**
```powershell
# Verify task exists
Get-ScheduledTask -TaskName "TradingBot-EODCleanup"

# Check task info
Get-ScheduledTaskInfo -TaskName "TradingBot-EODCleanup"

# View last run details
Get-ScheduledTaskInfo -TaskName "TradingBot-EODCleanup" | 
    Select-Object LastRunTime, LastTaskResult, NextRunTime
```

### Issue: Telegram Not Sending

**Check:**
```powershell
# Verify environment variables
echo $env:TELEGRAM_BOT_TOKEN
echo $env:TELEGRAM_CHAT_ID

# Test Telegram connectivity
python -c "from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier; t = get_telegram_notifier(); t.send_message('Test from deployment')"
```

### Issue: Order Verifier Not Working

**Check logs:**
```powershell
# Search for verifier activity
Get-Content logs\*.log | Select-String "verifier" | Select-Object -Last 20
```

**Expected log messages:**
```
Order status verifier started (check interval: 1800s)
Verifying X pending order(s)
Order EXECUTED: [SYMBOL] x[QTY]
```

---

## Monitoring Commands

### Daily Health Check:

```powershell
# 1. Check task status
.\manage_tasks.ps1 status

# 2. Check recent logs for errors
Get-Content logs\*.log | Select-String "ERROR" | Select-Object -Last 10

# 3. Check active tracking
Get-Content data\system_recommended_symbols.json | ConvertFrom-Json

# 4. Check pending orders
Get-Content data\pending_orders.json | ConvertFrom-Json

# 5. Verify Telegram working
# Check your Telegram for recent messages
```

---

## Rollback (If Needed)

If you need to revert to old setup:

```powershell
# Remove all tasks
.\manage_tasks.ps1 remove

# Recreate using old setup
.\setup_scheduled_tasks.ps1  # Old version (without EOD cleanup)
```

**Note:** This will remove Phase 2 features (order verifier, EOD cleanup, Telegram notifications will stop)

---

## Next: Phase 3 Preparation

When Phase 3 is ready, you'll add:

**New Task: Exit Evaluation**
- **Time:** Every hour during market (9:30 AM - 3:30 PM)
- **Purpose:** Check exit conditions (EMA9, RSI50, stop-loss)
- **Action:** Automatically place sell orders when conditions met

**Task will be added via:**
```powershell
.\setup_scheduled_tasks_phase3.ps1  # Coming soon
```

---

## Summary

✅ **Phase 1 & 2 deployed and working**  
✅ **4 scheduled tasks active**  
✅ **Order tracking automatic**  
✅ **Telegram notifications enabled**  
✅ **EOD cleanup running daily**  
✅ **Manual trade detection active**  

**Your system is now production-ready for Phase 1 & 2!** 🚀

---

**Version:** 2.0 (Phase 1 & 2 Complete)  
**Last Updated:** 2025-01-28  
**Next:** Phase 3 (Exit Strategy & Risk Management)
