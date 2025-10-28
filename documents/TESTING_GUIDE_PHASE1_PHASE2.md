# Testing Guide: Phase 1 & Phase 2

**Purpose:** Validate all Phase 1 & 2 features before production deployment  
**Timeline:** 1 week of testing  
**Status:** Ready to begin  

---

## Testing Overview

### What We're Testing:
- ✅ Phase 1: Order tracking and reconciliation
- ✅ Phase 2: Automated verification, Telegram, manual trades, EOD cleanup

### Testing Phases:
1. **Day 1:** Setup & Configuration (Telegram, environment)
2. **Day 2:** Dry-Run Test (small order, basic flow)
3. **Day 3:** Manual Trade Detection Test
4. **Day 4:** Order Status Verification Test
5. **Day 5:** EOD Cleanup Test
6. **Day 6-7:** Monitoring & Issue Resolution

---

## Pre-Testing Checklist

### Environment Setup:
- [ ] `.venv` activated
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Broker credentials in `kotak_neo.env`
- [ ] Sufficient balance in test account
- [ ] Backup of existing data files

### Safety Measures:
- [ ] Using test/paper trading account (if available)
- [ ] Small order sizes configured (1-2 shares max)
- [ ] Stop-loss/risk management in place
- [ ] Backup of all JSON data files
- [ ] Git commit before testing

---

## Day 1: Setup & Configuration

### Step 1.1: Telegram Bot Setup

**Create Bot:**
```bash
# 1. Open Telegram
# 2. Search for @BotFather
# 3. Send: /newbot
# 4. Follow instructions
# 5. Copy bot token (looks like: 123456:ABC-DEF1234ghIJKLmno...)
```

**Get Chat ID:**
```bash
# 1. Search for @userinfobot in Telegram
# 2. Send: /start
# 3. Copy your chat ID (looks like: 123456789)
```

**Set Environment Variables (Windows PowerShell):**
```powershell
# Option 1: Session variables (temporary)
$env:TELEGRAM_BOT_TOKEN = "your_bot_token_here"
$env:TELEGRAM_CHAT_ID = "your_chat_id_here"

# Option 2: User environment variables (permanent)
[System.Environment]::SetEnvironmentVariable('TELEGRAM_BOT_TOKEN', 'your_token', 'User')
[System.Environment]::SetEnvironmentVariable('TELEGRAM_CHAT_ID', 'your_chat_id', 'User')

# Verify
echo $env:TELEGRAM_BOT_TOKEN
echo $env:TELEGRAM_CHAT_ID
```

**Test Telegram Connection:**
```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# Test connection
python -m modules.kotak_neo_auto_trader.example_phase2_integration 2
```

**Expected Output:**
```
======================================================================
EXAMPLE 2: Test Telegram Connection
======================================================================
[INFO] ✓ Telegram connection successful!
```

**You should receive a message in Telegram:**
```
🤖 Telegram Notifier Test

Connection successful! ✅
You will receive notifications here.
```

### Step 1.2: Configuration Review

**Check Configuration File:**
```powershell
# Review auto_trade_engine.py initialization
# Default configuration:
# - enable_verifier=True (30-min checks)
# - enable_telegram=True (notifications)
# - enable_eod_cleanup=True
# - verifier_interval=1800 (30 minutes)
```

**Adjust for Testing (Optional):**
```python
# For faster testing, reduce check interval to 5 minutes
engine = AutoTradeEngine(
    env_file="kotak_neo.env",
    enable_verifier=True,
    enable_telegram=True,
    enable_eod_cleanup=True,
    verifier_interval=300  # 5 minutes for testing
)
```

### Step 1.3: Backup Data Files

```powershell
# Create backup directory
mkdir -p data_backups/$(Get-Date -Format 'yyyyMMdd_HHmmss')

# Backup existing data files
Copy-Item data/*.json data_backups/$(Get-Date -Format 'yyyyMMdd_HHmmss')/ -ErrorAction SilentlyContinue

# Verify backup
ls data_backups/
```

### Step 1.4: Verify Unit Tests

```powershell
# Run Phase 1 unit tests
.\.venv\Scripts\python.exe -m unittest temp.test_tracking_scope temp.test_order_tracker -v

# Expected: All tests pass
# Ran 37 tests in ~0.8s
# OK (skipped=3)
```

**✅ Day 1 Complete Checklist:**
- [ ] Telegram bot created
- [ ] Chat ID obtained
- [ ] Environment variables set
- [ ] Telegram connection tested
- [ ] Configuration reviewed
- [ ] Data files backed up
- [ ] Unit tests passing

---

## Day 2: Dry-Run Test (Small Order)

### Objective:
Place 1 small test order and verify entire Phase 1 + Phase 2 workflow.

### Step 2.1: Prepare Test Order

**Create Test Recommendations CSV:**
```powershell
# Create test CSV with 1 small-cap stock
$testCSV = @"
ticker,verdict,last_close,final_verdict,combined_score,status
EXAMPLE.NS,strong_buy,100.00,strong_buy,80,success
"@

# Save to file
$testCSV | Out-File -FilePath "analysis_results/test_order_$(Get-Date -Format 'yyyyMMdd').csv" -Encoding utf8
```

**Or use existing CSV with 1 symbol:**
```powershell
# Just ensure CSV has only 1-2 symbols for testing
# Manually edit CSV to keep only 1 row
```

### Step 2.2: Run Order Placement

```powershell
# Run with test CSV
python -m modules.kotak_neo_auto_trader.run_place_amo `
    --env modules/kotak_neo_auto_trader/kotak_neo.env `
    --csv analysis_results/test_order_20250127.csv

# Monitor logs
Get-Content logs/auto_trade*.log -Tail 50 -Wait
```

### Step 2.3: Verify Phase 1 Tracking

**Check Tracking Scope:**
```powershell
# View tracking file
Get-Content data/system_recommended_symbols.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Expected Structure:**
```json
{
  "symbols": [
    {
      "id": "track-EXAMPLE-20250127...",
      "symbol": "EXAMPLE",
      "ticker": "EXAMPLE.NS",
      "tracking_status": "active",
      "system_qty": 2,
      "current_tracked_qty": 2,
      "pre_existing_qty": 0,
      "initial_order_id": "ORDER-12345",
      "all_related_orders": ["ORDER-12345"],
      "recommendation_source": "test_order_20250127.csv"
    }
  ]
}
```

**Check Pending Orders:**
```powershell
# View pending orders
Get-Content data/pending_orders.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Expected:**
```json
{
  "orders": [
    {
      "order_id": "ORDER-12345",
      "symbol": "EXAMPLE",
      "qty": 2,
      "status": "PENDING",
      "placed_at": "2025-01-27T09:00:00",
      "order_type": "MARKET",
      "variety": "AMO"
    }
  ]
}
```

### Step 2.4: Verify Telegram Notifications

**Expected Telegram Messages:**

**If Order Placed Successfully:**
```
✅ ORDER PLACED

📊 Symbol: EXAMPLE
📝 Order ID: ORDER-12345
📦 Quantity: 2
⏰ Time: 2025-01-27 09:00:00
```

**If Order Rejected:**
```
🚫 ORDER REJECTED

📊 Symbol: EXAMPLE
📝 Order ID: ORDER-12345
📦 Quantity: 2
⚠️ Reason: [Rejection reason from broker]
⏰ Time: 2025-01-27 09:00:00

Please review and take necessary action.
```

### Step 2.5: Wait for Order Verification (30 min or 5 min if interval reduced)

**Monitor Logs:**
```powershell
# Watch for verifier activity
Get-Content logs/auto_trade*.log | Select-String "verif" -Context 2
```

**Expected Log Messages:**
```
[INFO] Order status verifier started (check interval: 300s)
[INFO] Verifying 1 pending order(s)
[INFO] Order EXECUTED: EXAMPLE x2 (order_id: ORDER-12345)
[INFO] Telegram notification sent successfully
```

**Expected Telegram:**
```
✅ ORDER EXECUTED

📊 Symbol: EXAMPLE
📝 Order ID: ORDER-12345
📦 Quantity: 2
💰 Price: ₹100.00
💵 Total Value: ₹200.00
⏰ Time: 2025-01-27 09:30:00
```

### Step 2.6: Verify Trade History

```powershell
# Check trade history
Get-Content data/trades_history.json | ConvertFrom-Json | ConvertTo-Json -Depth 10 | Select-String "EXAMPLE"
```

**Expected:** Entry added for EXAMPLE symbol.

### Step 2.7: Verify Reconciliation

**Trigger Manual Reconciliation:**
```python
# In Python shell or script
from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

engine = AutoTradeEngine(env_file="modules/kotak_neo_auto_trader/kotak_neo.env")
if engine.login():
    engine.reconcile_holdings_to_history()
    engine.logout()
```

**Expected:** No discrepancies (qty matches).

**✅ Day 2 Complete Checklist:**
- [ ] Test order placed successfully
- [ ] Order ID extracted
- [ ] Tracking scope registered
- [ ] Pending order added
- [ ] Telegram notification received (placement)
- [ ] Order verifier detected status change
- [ ] Telegram notification received (execution/rejection)
- [ ] Trade added to history
- [ ] Reconciliation ran successfully
- [ ] No errors in logs

---

## Day 3: Manual Trade Detection Test

### Objective:
Verify system detects manual buy/sell of tracked symbols.

### Step 3.1: Manual Buy Test

**Prerequisites:** 
- Have 1 active tracked symbol (from Day 2)

**Action:**
```
1. Open broker app/website manually
2. Buy 1-2 MORE shares of the tracked symbol (EXAMPLE)
3. Wait for order execution
4. Note the quantity bought
```

**Run Reconciliation:**
```python
from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

engine = AutoTradeEngine(env_file="modules/kotak_neo_auto_trader/kotak_neo.env")
if engine.login():
    # Reconciliation includes manual trade detection
    engine.reconcile_holdings_to_history()
    engine.logout()
```

**Expected Logs:**
```
[INFO] Starting manual trade reconciliation
[INFO] Reconciling 1 tracked symbol(s)
[INFO] ⚠ EXAMPLE: Quantity mismatch detected
  Expected: 2 (system: 2, pre-existing: 0)
  Broker:   4
  Diff:     +2
[INFO] 📈 Manual BUY detected for EXAMPLE: +2 shares
[INFO] ✓ Updated tracking for EXAMPLE: 2 -> 4
============================================================
MANUAL TRADE RECONCILIATION SUMMARY
============================================================
Matched (no changes):     0
Manual Buys Detected:     1
Manual Sells Detected:    0
Symbols Updated:          1
============================================================
```

**Verify Tracking File Updated:**
```powershell
Get-Content data/system_recommended_symbols.json | ConvertFrom-Json | ConvertTo-Json -Depth 10 | Select-String "EXAMPLE" -Context 5
```

**Expected:** `current_tracked_qty` changed from 2 to 4.

### Step 3.2: Manual Sell Test (Partial)

**Action:**
```
1. Manually sell 1 share of EXAMPLE
2. Wait for execution
```

**Run Reconciliation:**
```python
# Same as above
engine.reconcile_holdings_to_history()
```

**Expected:**
```
[INFO] 📉 Manual SELL detected for EXAMPLE: -1 shares
[INFO] ✓ Updated tracking for EXAMPLE: 4 -> 3
```

### Step 3.3: Position Closure Test

**Action:**
```
1. Manually sell ALL remaining shares of EXAMPLE
2. Wait for execution
```

**Run Reconciliation:**
```python
engine.reconcile_holdings_to_history()
```

**Expected:**
```
[INFO] 🛑 Position closed detected: EXAMPLE (was tracking 3 shares)
[INFO] Stopped tracking EXAMPLE: Position fully closed (manual sell detected)
```

**Expected Telegram:**
```
🛑 TRACKING STOPPED

📊 Symbol: EXAMPLE
📝 Reason: Position fully closed (manual sell detected)
⏰ Time: 2025-01-27 15:30:00
```

**Verify Tracking File:**
```powershell
Get-Content data/system_recommended_symbols.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Expected:** EXAMPLE entry has `tracking_status: "completed"`.

**✅ Day 3 Complete Checklist:**
- [ ] Manual buy detected
- [ ] Quantity updated correctly (+2)
- [ ] Logs show manual buy message
- [ ] Manual sell detected
- [ ] Quantity updated correctly (-1)
- [ ] Logs show manual sell message
- [ ] Position closure detected
- [ ] Tracking stopped
- [ ] Telegram notification received
- [ ] Tracking status changed to "completed"

---

## Day 4: Order Status Verification Test

### Objective:
Verify automated order status checks work correctly.

### Step 4.1: Place Order and Monitor

**Place another test order:**
```powershell
# Use same CSV or create new one
python -m modules.kotak_neo_auto_trader.run_place_amo `
    --env modules/kotak_neo_auto_trader/kotak_neo.env `
    --csv analysis_results/test_order_20250127.csv
```

**Monitor Verifier Activity:**
```powershell
# Watch logs for verifier
Get-Content logs/auto_trade*.log -Wait | Select-String "verif"
```

**Expected Pattern:**
```
[INFO] Order status verifier started (check interval: 1800s)
# ... 30 minutes later ...
[INFO] Verifying 1 pending order(s)
[INFO] Final verification: 1 checked, 1 executed, 0 rejected, 0 still pending
[INFO] Order EXECUTED: [SYMBOL] x[QTY] (order_id: [ORDER_ID])
```

### Step 4.2: Test Rejection Scenario (if possible)

**Create intentional rejection:**
```
1. Empty broker account balance (transfer out)
2. Try placing order with insufficient funds
3. Wait for rejection
```

**Expected:**
```
[INFO] Order REJECTED: [SYMBOL] x[QTY] (order_id: [ORDER_ID], reason: [REASON])
[INFO] Stopped tracking [SYMBOL]: Order rejected: [REASON]
```

**Expected Telegram:**
```
🚫 ORDER REJECTED

📊 Symbol: [SYMBOL]
📝 Order ID: [ORDER_ID]
📦 Quantity: [QTY]
⚠️ Reason: Insufficient funds
⏰ Time: [TIME]

Please review and take necessary action.
```

### Step 4.3: Verify Pending Order Cleanup

**Check pending_orders.json:**
```powershell
Get-Content data/pending_orders.json | ConvertFrom-Json
```

**Expected:** Executed/rejected orders removed from pending list.

**✅ Day 4 Complete Checklist:**
- [ ] Verifier runs automatically
- [ ] Order status checked at intervals
- [ ] Execution detected
- [ ] Telegram notification sent
- [ ] Pending order removed after execution
- [ ] Rejection scenario tested (if possible)
- [ ] Tracking stopped on rejection
- [ ] Logs show all verifier activity

---

## Day 5: EOD Cleanup Test

### Objective:
Verify end-of-day cleanup workflow.

### Step 5.1: Manual EOD Cleanup Trigger

```python
from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

engine = AutoTradeEngine(env_file="modules/kotak_neo_auto_trader/kotak_neo.env")

if engine.login():
    if engine.eod_cleanup:
        print("Running EOD cleanup...")
        results = engine.eod_cleanup.run_eod_cleanup()
        
        print(f"\n{'=' * 70}")
        print("EOD Cleanup Results:")
        print(f"  Success: {results['success']}")
        print(f"  Duration: {results['duration_seconds']:.2f}s")
        print(f"  Steps Completed: {len(results['steps_completed'])}/6")
        if results['steps_failed']:
            print(f"  Failed Steps: {', '.join(results['steps_failed'])}")
        print(f"{'=' * 70}\n")
        
        # Print statistics
        if 'statistics' in results:
            print("\nStatistics:")
            import json
            print(json.dumps(results['statistics'], indent=2))
    
    engine.logout()
```

### Step 5.2: Verify 6-Step Workflow

**Expected Console Output:**
```
======================================================================
STARTING END-OF-DAY CLEANUP
======================================================================

[Step 1/6] Final order status verification...
✓ Order verification complete

[Step 2/6] Manual trade reconciliation...
============================================================
MANUAL TRADE RECONCILIATION SUMMARY
============================================================
Matched (no changes):     2
Manual Buys Detected:     0
Manual Sells Detected:    0
Symbols Updated:          0
============================================================
✓ Manual trade reconciliation complete

[Step 3/6] Cleaning up stale orders...
✓ Stale order cleanup complete

[Step 4/6] Generating daily statistics...
✓ Daily statistics generated

[Step 5/6] Sending Telegram summary...
✓ Telegram summary sent

[Step 6/6] Archiving completed entries...
✓ Archiving complete

======================================================================
END-OF-DAY CLEANUP COMPLETE
======================================================================
Duration: 5.32s
Steps Completed: 6/6
Steps Failed: 0/6
✓ All steps completed successfully
```

### Step 5.3: Verify Telegram Daily Summary

**Expected Telegram:**
```
📊 DAILY TRADING SUMMARY
📅 Date: 2025-01-27

Order Statistics:
  • Orders Placed: 3
  • ✅ Executed: 2
  • 🚫 Rejected: 1
  • ⏳ Pending: 0

Tracking Status:
  • Active Symbols: 2

Additional Stats:
  • Manual Buys: 0
  • Manual Sells: 0
  • Positions Closed: 1

📈 Success Rate: 66.7%
```

### Step 5.4: Verify Stale Order Cleanup

**Create stale order (for testing):**
```python
# Manually add old pending order (>24 hours) to pending_orders.json
# Then run cleanup
```

**Expected:** Old orders removed from pending_orders.json.

**✅ Day 5 Complete Checklist:**
- [ ] EOD cleanup runs all 6 steps
- [ ] Final verification completed
- [ ] Manual reconciliation completed
- [ ] Stale orders cleaned up
- [ ] Daily statistics generated
- [ ] Telegram summary sent
- [ ] Archiving completed
- [ ] All steps successful
- [ ] No errors in workflow

---

## Days 6-7: Monitoring & Issue Resolution

### Continuous Monitoring Checklist

**Daily Checks:**
```powershell
# 1. Check logs for errors
Get-Content logs/auto_trade*.log | Select-String "ERROR" | Select-Object -Last 20

# 2. Verify verifier is running
Get-Content logs/auto_trade*.log | Select-String "verifier" | Select-Object -Last 5

# 3. Check data file integrity
Get-Content data/system_recommended_symbols.json | ConvertFrom-Json
Get-Content data/pending_orders.json | ConvertFrom-Json

# 4. Verify Telegram connectivity
# Should receive periodic messages

# 5. Check tracking status
Get-Content data/system_recommended_symbols.json | ConvertFrom-Json | 
    Select-Object -ExpandProperty symbols | 
    Where-Object tracking_status -eq "active"
```

### Common Issues & Solutions

#### Issue 1: Telegram Not Sending
```powershell
# Re-test connection
python -m modules.kotak_neo_auto_trader.example_phase2_integration 2

# Check environment variables
echo $env:TELEGRAM_BOT_TOKEN
echo $env:TELEGRAM_CHAT_ID

# Check logs
Get-Content logs/auto_trade*.log | Select-String "telegram" -Context 3
```

#### Issue 2: Verifier Not Running
```powershell
# Check if verifier started
Get-Content logs/auto_trade*.log | Select-String "verifier started"

# Check for errors
Get-Content logs/auto_trade*.log | Select-String "verifier.*error" -Context 5

# Verify thread is alive (should see periodic checks)
Get-Content logs/auto_trade*.log | Select-String "Verifying.*pending"
```

#### Issue 3: Manual Trades Not Detected
```powershell
# Manually trigger reconciliation
python -c "from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine; e = AutoTradeEngine(env_file='modules/kotak_neo_auto_trader/kotak_neo.env'); e.login() and e.reconcile_holdings_to_history(); e.logout()"

# Check reconciliation logs
Get-Content logs/auto_trade*.log | Select-String "reconcil" -Context 5
```

#### Issue 4: JSON File Corruption
```powershell
# Restore from backup
Copy-Item data_backups/[latest]/*.json data/ -Force

# Verify JSON validity
Get-Content data/system_recommended_symbols.json | ConvertFrom-Json
Get-Content data/pending_orders.json | ConvertFrom-Json
```

---

## Testing Success Criteria

### Phase 1 Success:
- [✓] Orders tracked correctly
- [✓] Order IDs extracted (with fallback)
- [✓] Tracking scope maintained
- [✓] Pending orders managed
- [✓] Reconciliation adds only tracked symbols
- [✓] Pre-existing quantities separated

### Phase 2 Success:
- [✓] Verifier runs automatically
- [✓] Order status updates detected
- [✓] Telegram notifications sent
- [✓] Manual trades detected
- [✓] Position closures detected
- [✓] EOD cleanup runs successfully
- [✓] Daily summary generated

### Overall Success:
- [✓] No critical errors in logs
- [✓] All features working as designed
- [✓] Telegram responsive
- [✓] Data files valid and consistent
- [✓] Performance acceptable
- [✓] Ready for production

---

## Post-Testing Report Template

```markdown
# Phase 1 & 2 Testing Report

**Date:** [Date]  
**Tester:** [Name]  
**Duration:** [Days]  

## Summary
- Total Orders Placed: [#]
- Successful Executions: [#]
- Rejections: [#]
- Manual Trades Detected: [#]
- Telegram Notifications Sent: [#]
- EOD Cleanups Run: [#]

## Feature Test Results

### Phase 1 - Tracking:
- Order Tracking: [PASS/FAIL]
- Order ID Extraction: [PASS/FAIL]
- Reconciliation: [PASS/FAIL]

### Phase 2 - Automation:
- Order Verifier: [PASS/FAIL]
- Telegram Notifications: [PASS/FAIL]
- Manual Trade Detection: [PASS/FAIL]
- EOD Cleanup: [PASS/FAIL]

## Issues Found
1. [Issue description]
   - Severity: [Low/Medium/High]
   - Status: [Open/Resolved]
   
2. [Issue description]
   - Severity: [Low/Medium/High]
   - Status: [Open/Resolved]

## Recommendations
- [Recommendation 1]
- [Recommendation 2]

## Production Readiness
- [ ] All tests passed
- [ ] Critical issues resolved
- [ ] Documentation updated
- [ ] Team trained
- [ ] Monitoring in place
- [ ] Backup procedures tested

**Overall Status:** [READY/NOT READY]
```

---

## Next Steps After Testing

### If All Tests Pass:
1. ✅ Mark Phase 1 & 2 as production-ready
2. ✅ Deploy to production environment
3. ✅ Monitor closely for 1 week
4. ✅ Begin Phase 3 planning

### If Issues Found:
1. ⚠️ Document all issues
2. ⚠️ Prioritize by severity
3. ⚠️ Fix critical issues
4. ⚠️ Re-test affected features
5. ⚠️ Repeat until all tests pass

---

**Testing Guide Version:** 1.0  
**Last Updated:** 2025-01-27  
**Status:** Ready for use
