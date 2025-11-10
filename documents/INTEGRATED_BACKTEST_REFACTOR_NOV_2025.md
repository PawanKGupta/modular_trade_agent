# Integrated Backtest Refactor - November 2025

## Summary

Refactored `integrated_backtest.py` to use a single-pass daily iteration approach, eliminating redundancy and fixing multiple critical bugs in position tracking, level marking, and exit conditions.

## Critical Bugs Fixed

### Bug #1: Exit Conditions Not Checked During Daily Monitoring

**Previous Implementation (`integrated_backtest_old_buggy.py`):**
- Had a critical bug in `monitor_position_daily()` function (lines 361-366)
- Exit conditions were checked but never acted upon:
  ```python
  # Check exit conditions (same as auto trader: RSI > 50 or price >= EMA9)
  ema9 = row.get('EMA9')
  if not pd.isna(ema9) and (rsi > 50 or price >= ema9):
      # Position should exit - but we don't force exit here
      # Let track_position_to_exit handle it
      pass  # ❌ BUG: Does nothing!
  ```
- `track_position_to_exit()` was only called at the end of all signals, not between signals
- This caused positions to stay open indefinitely, accumulating re-entries when they should have exited
- **Example**: RELIANCE.NS position from 2022-01-28 stayed open for 840 days until 2024-05-17, accumulating $178k profit, when it should have exited on 2022-02-01 (4 days) with ~$1k profit

**New Implementation (`integrated_backtest.py`):**
- Checks exit conditions (High >= Target OR RSI > 50) on EVERY trading day
- Immediately closes positions and saves them to results when exit conditions are met
- Prevents false profit inflation from bug
- Results are now ACCURATE and match expected trading behavior

### Bug #2: Initial Entry Not Marking All Passed RSI Levels

**Problem:**
When initial entry occurred at RSI 19.8 (< 20), only level 30 was marked as taken. Level 20 should have also been marked as taken since RSI was already below 20.

**Before:**
```python
# Initial entry at RSI 19.8
self.levels_taken = {"30": True, "20": False, "10": False}  # ❌ Wrong!
```

**After:**
```python
# Initial entry at RSI 19.8 now correctly marks both 30 and 20 as taken
if entry_rsi < 10:
    self.levels_taken = {"30": True, "20": True, "10": True}
elif entry_rsi < 20:
    self.levels_taken = {"30": True, "20": True, "10": False}  # ✅ Fixed!
elif entry_rsi < 30:
    self.levels_taken = {"30": True, "20": False, "10": False}
```

**Impact:** Prevents invalid re-entries at already-passed RSI levels.

### Bug #3: Inconsistent Date Logging

**Problem:**
- Initial entry showed SIGNAL DATE (day before execution)
- Re-entries showed EXECUTION DATE
- Exit messages showed EXECUTION DATE

**Before:**
```
🔄 Initial Entry Signal: 2023-08-10     ← Signal date (confusing!)
   ✅ TRADE EXECUTED (INITIAL): Buy at 575.54
   ➕ RE-ENTRY on 2023-09-05              ← Execution date
```

**After:**
```
🔄 Signal #2 detected on 2023-08-10      ← Signal date (informative)
   ✅ INITIAL ENTRY on 2023-08-11: Buy at 575.54  ← Execution date (consistent!)
   ➕ RE-ENTRY on 2023-09-05              ← Execution date
```

**Impact:** All logs now consistently show execution dates, making it clear when positions were actually filled.

## Architecture Changes

### Before
1. BacktestEngine scans entire period and generates all RSI < 30 signals
2. Main loop processes each signal sequentially
3. `monitor_position_daily()` checks for re-entries between signals (but doesn't exit!)
4. `track_position_to_exit()` only called at end of all signals

**Problems:**
- Double scanning (BacktestEngine + daily monitoring)
- Redundant signal generation (consecutive RSI < 30 days create separate signals)
- Exit bug (no exit during monitoring)

### After
1. Single loop iterates through each trading day
2. Inline checks for initial entry conditions (RSI < 30 AND Close > EMA200)
3. Inline checks for re-entry conditions (RSI level progression, reset cycles)
4. Inline checks for exit conditions (High >= Target OR RSI > 50) **on every day**
5. Trade agent validation only for initial entries

**Benefits:**
- Single pass through data (more efficient)
- Exit conditions checked properly on every day
- Accurate P&L calculations
- Thread-safe (all state is local)
- Simpler logic flow

## Results Comparison

**Test Case**: RELIANCE.NS, 5-year backtest (2020-11-11 to 2025-11-10)

| Metric | Old (Buggy) | New (Fixed) |
|--------|-------------|-------------|
| Executed Trades | 18 | 10 |
| Total P&L | $183,865 | $10,655 |
| Total Return | +20.43% | +2.13% |
| Win Rate | 66.7% | 100.0% |
| Total Positions | 0 (bug!) | 7 |

**Why the difference?**
- Old implementation held positions for months/years due to exit bug
- New implementation correctly exits when target is hit or RSI > 50
- Old P&L was inflated by positions that should have been closed
- **New results are CORRECT** - they reflect proper trade management

**Test Case 2**: DREAMFOLKS.NS, 5-year backtest (2020-11-11 to 2025-11-10)

| Metric | Before Fixes | After Fixes |
|--------|--------------|-------------|
| Signals Found | 2 | 2 |
| Executed Trades | 3 | 2 |
| Total P&L | -$21,431 | -$10,556 |
| Total Return | -7.14% | -5.28% |
| Invalid Re-entries | 1 (Aug 14) | 0 |

**What was fixed:**
- ✅ Level 20 now marked on initial entry (RSI 19.8 < 20)
- ✅ Aug 14 re-entry correctly skipped (level 20 already taken)
- ✅ Sept 5 re-entry correctly executed (reset cycle, even below EMA200)
- ✅ Same-day exit allowed when High >= Target
- ✅ Consistent date logging (execution dates)

## Key Features

### Signal Numbering
All initial entry signals are now numbered for easy tracking:
```
🔄 Signal #1 detected on 2023-08-09
   ⏸️ SKIPPED: Trade agent rejected

🔄 Signal #2 detected on 2023-08-10
   ✅ INITIAL ENTRY on 2023-08-11: Buy at 575.54
```

### Re-Entry Logic
**IMPORTANT:** Re-entries do NOT check EMA200 - this is intentional!

| Condition | Initial Entry | Re-Entry |
|-----------|--------------|----------|
| RSI < 30 | ✅ Required | ✅ Required |
| Close > EMA200 | ✅ **Required** | ❌ **NOT checked** |
| RSI Level Logic | N/A | ✅ Required (20, 10, or reset) |
| Daily Cap | N/A | ✅ Max 1/day |

**Why?**
- Initial entry confirms UPTREND (Close > EMA200)
- Re-entries are "averaging down" on deeper dips while already in position
- Stock can temporarily fall below EMA200 during the dip
- You're already committed to the trade - continue adding on RSI levels
- This is a "committed pyramiding" strategy

**Example:**
```
Aug 10: Initial Signal
  RSI: 19.8 < 30 ✅
  Close: 561.65 > EMA200: 505.13 ✅  ← Confirms uptrend
  → ENTER

Sept 5: Re-entry Signal (Reset Cycle)  
  RSI: 29.1 < 30 ✅ (after going > 30)
  Close: 500.45 < EMA200: ~506 ❌  ← Now below, but still RE-ENTER
  → Averaging down on reset cycle (no EMA200 check)
```

### Exit Conditions
Positions exit when either condition is met:
1. **High >= Target** (EMA9 at entry/re-entry date)
2. **RSI > 50** (overbought exit)

**Note:** Can exit same day as re-entry if High hits target during the day.

## Key Position Example

**RELIANCE.NS Signal 3 (2022-01-27):**

| Implementation | Entry Date | Exit Date | Days | P&L | Behavior |
|----------------|-----------|-----------|------|-----|----------|
| Old (Buggy) | 2022-01-28 | 2024-05-17 | 840 | $178,945 | Stayed open 2+ years, accumulated 6 re-entries |
| New (Fixed) | 2022-01-28 | 2022-02-01 | 4 | $947 | Exited when target hit (correct!) |

**Old implementation:** Target (1096.69) was hit on 2022-02-01, but position stayed open due to bug. It then accumulated re-entries at lower prices, lowering the average and target, allowing it to stay open for 840 days.

**New implementation:** Target hit on 2022-02-01, position closed immediately as it should.

## Thread Safety

Both implementations are thread-safe:
- All state is local to function calls
- No shared/global variables
- Can be run in parallel for multiple stocks without interference

The `run_integrated_backtest()` function in both versions only uses:
- Function parameters
- Local variables
- Return values

No shared state between calls.

## Files

- **`integrated_backtest.py`**: New fixed implementation
- **`integrated_backtest_old_buggy.py`**: Old buggy implementation (backup)
- **Test Command**: 
  ```bash
  python scripts/run_single_stock_backtest.py RELIANCE.NS --mode scoring --years 5
  ```

## Log Format Examples

### Complete Trade Cycle
```
🔄 Signal #1 detected on 2023-08-09
   RSI: 28.5 < 30 | Close: 651.94 > EMA200: 504.57
   🤖 Trade Agent analyzing...
   ⏸️ SKIPPED: Trade agent rejected

🔄 Signal #2 detected on 2023-08-10
   RSI: 19.8 < 30 | Close: 561.65 > EMA200: 505.13
   🤖 Trade Agent analyzing...
   ✅ INITIAL ENTRY on 2023-08-11: Buy at 575.54
      Target: 682.01
      (RSI 19.8 marks levels: 30=True, 20=True, 10=False)
   
   ➕ RE-ENTRY on 2023-09-05: RSI 29.1 < 30 | Add at 499.80
      New Avg: 534.93 | New Target: 506.63
      (Reset cycle: RSI went >30 then <30 again)
   
   🎯 TARGET HIT on 2023-09-05: Exit at 506.63
      Entry: 2023-08-11 | Exit: 2023-09-05 | Days: 25
      P&L: $-10,556 (-5.3%)

============================================================
🏁 Integrated Backtest Complete!
Total Signals: 2
Executed Trades: 2 (1 initial + 1 re-entry)
Skipped Signals: 1
Total Positions: 1
```

### Date Terminology
- **Signal detected on X**: RSI < 30 condition detected on day X
- **INITIAL ENTRY on X+1**: Position filled at Open on next trading day
- **RE-ENTRY on Y**: Re-entry filled at Open on day Y
- **TARGET HIT on Z**: Exit executed at target price on day Z
- **Entry: A | Exit: B**: Actual position dates (execution to exit)

## Conclusion

The refactor successfully:
1. ✅ Fixed critical exit tracking bug (positions now exit when conditions met)
2. ✅ Fixed RSI level marking bug (all passed levels marked on entry)
3. ✅ Fixed logging consistency (all dates show execution times)
4. ✅ Added signal numbering for easy tracking
5. ✅ Eliminated redundancy (single-pass iteration)
6. ✅ Improved accuracy of backtest results
7. ✅ Maintained thread safety
8. ✅ Backward compatible API (`run_integrated_backtest`, `print_integrated_results`)
9. ✅ Documented re-entry logic (no EMA200 check by design)

The new implementation produces **lower but more accurate** returns that reflect proper trade management with timely exits and correct pyramiding behavior.

## Related Documentation

### Current (November 2025)
- **This document** - Complete refactor details
- `integrated_backtest.py` - Current implementation
- `documents/README.md` - Documentation index

### Superseded/Historical
- ~~`BACKTEST_DAILY_MONITORING_DESIGN.md`~~ - Deleted (replaced by this doc)
- `architecture/INTEGRATED_README.md` - Marked as outdated (describes old signal-based approach)
- `features/BACKTEST_INTEGRATION_FIX.md` - Historical fix (pre-refactor)

### Still Relevant
- `KOTAK_NEO_AUTO_TRADER_LOGIC.md` - Live trading logic (unchanged)
- `KOTAK_NEO_REENTRY_LOGIC_DETAILS.md` - Re-entry logic details (matches backtest)
- `DATA_FLOW_BACKTEST.md` - Data flow for `trade_agent.py --backtest` (still accurate)
- `backtest/README.md` - General backtest overview
