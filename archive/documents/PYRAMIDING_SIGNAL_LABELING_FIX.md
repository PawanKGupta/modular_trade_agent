# Pyramiding Signal Labeling Fix

## Problem Statement

**Issue**: Signals are being labeled as "Pyramiding" even when no trades were executed.

**Example**:
```
Signal 2/12: 2024-10-10
Reason: Pyramiding: RSI 28.1 < 30 (after reset)
Result: WATCH (trade skipped)
```

## Root Cause

The backtest engine's state (`first_entry_made`) was being updated during **signal detection**, not during **trade execution**. This caused:

1. **Signal 1** detected → `engine.first_entry_made = True` (even if trade not executed)
2. **Signal 2** detected → Engine sees `first_entry_made = True` → Labels as "Pyramiding"
3. **Signal 2** gets "watch" verdict → Trade not executed
4. **Result**: Signal labeled as "Pyramiding" but no previous trade executed

## The Fix

### Change 1: Don't Update Engine State During Signal Detection

**File**: `integrated_backtest.py`

**Before**:
```python
potential_signals.append(signal)
# Update engine state to track subsequent entries properly
engine.first_entry_made = True  # ❌ Wrong - updates state during detection
```

**After**:
```python
potential_signals.append(signal)
# NOTE: DO NOT update engine.first_entry_made here!
# The engine state should only be updated when trades are ACTUALLY EXECUTED,
# not when signals are just detected. This prevents labeling signals as "Pyramiding"
# when no previous trade was actually executed.
# State will be updated in run_integrated_backtest when trades are executed.
```

### Change 2: Correct Signal Labeling Based on Actual Positions

**File**: `integrated_backtest.py`

**Before**:
```python
# If this is labeled as Pyramiding but we have no open position, treat as potential initial
if signal['reason'].startswith('Pyramiding') and not has_open_position:
    derived_reason = 'Initial entry'
else:
    derived_reason = signal['reason']
```

**After**:
```python
# Fix: Correctly label signals based on ACTUAL trade execution, not engine state
if has_open_position:
    # We have an open position, so this could be pyramiding
    derived_reason = signal['reason']
else:
    # No open position, so this should be an initial entry (if executed)
    if signal['reason'].startswith('Pyramiding'):
        # Signal says pyramiding but no position exists - this is a state mismatch
        derived_reason = 'Initial entry (corrected from Pyramiding - no open position)'
    else:
        derived_reason = signal['reason']
```

### Change 3: Clarify Trade Execution Logging

**File**: `integrated_backtest.py`

**Before**:
```python
print(f"   ✅ TRADE EXECUTED: Buy at {signal['execution_price']:.2f}")
print(f"   ➕ RE-ENTRY: Add at {signal['execution_price']:.2f}")
```

**After**:
```python
print(f"   ✅ TRADE EXECUTED (INITIAL): Buy at {signal['execution_price']:.2f}")
print(f"   ➕ RE-ENTRY (PYRAMIDING): Add at {signal['execution_price']:.2f}")
```

## How It Works Now

### Signal Detection Phase (`run_backtest`)
1. Engine detects signals based on RSI/EMA200 conditions
2. Engine state (`first_entry_made`) is **NOT** updated during detection
3. Signals are labeled based on engine's current state (may be incorrect)
4. All signals are returned for validation

### Trade Execution Phase (`run_integrated_backtest`)
1. Each signal is validated by trade agent
2. If trade agent returns "BUY", trade is executed
3. Signal labeling is **corrected** based on actual positions:
   - If no open position exists → Label as "Initial entry"
   - If open position exists → Label as "Pyramiding"
4. Trade execution logging clarifies initial vs pyramiding

## Expected Behavior After Fix

### Scenario 1: No Trades Executed
```
Signal 1: Initial entry → WATCH (skipped)
Signal 2: Pyramiding → WATCH (skipped) ❌ Wrong label
Signal 2: Initial entry (corrected) → WATCH (skipped) ✅ Correct label
```

### Scenario 2: First Trade Executed
```
Signal 1: Initial entry → BUY (executed) ✅
Signal 2: Pyramiding → BUY (executed) ✅ Correct label (has open position)
```

### Scenario 3: Mixed Execution
```
Signal 1: Initial entry → WATCH (skipped)
Signal 2: Pyramiding → BUY (executed) ❌ Wrong label
Signal 2: Initial entry (corrected) → BUY (executed) ✅ Correct label
```

## Benefits

1. **Accurate Labeling**: Signals are labeled based on actual trade execution, not detection state
2. **Clear Logging**: Trade execution logs clearly show "INITIAL" vs "PYRAMIDING"
3. **State Consistency**: Engine state only updates when trades are actually executed
4. **Better Debugging**: Easier to understand why signals are labeled as "Pyramiding"

## Testing

### Test Case 1: No Trades Executed
- **Input**: 12 signals, all get "watch" verdicts
- **Expected**: All signals labeled as "Initial entry" (corrected from "Pyramiding" if needed)
- **Result**: ✅ Signals correctly labeled

### Test Case 2: First Trade Executed
- **Input**: Signal 1 executed, Signal 2 detected
- **Expected**: Signal 2 labeled as "Pyramiding" (has open position)
- **Result**: ✅ Signals correctly labeled

### Test Case 3: Mixed Execution
- **Input**: Signal 1 skipped, Signal 2 executed
- **Expected**: Signal 2 labeled as "Initial entry" (no open position)
- **Result**: ✅ Signals correctly labeled

## Related Issues

- **Issue**: Signals labeled as "Pyramiding" when no trades executed
- **Root Cause**: Engine state updated during signal detection
- **Fix**: Only update state during trade execution, correct labeling based on actual positions

## Conclusion

The fix ensures that:
1. Engine state is only updated when trades are actually executed
2. Signal labeling is corrected based on actual positions
3. Trade execution logging clearly shows initial vs pyramiding
4. Users can understand why signals are labeled as "Pyramiding"

---

**Last Updated**: 2025-11-09
**Status**: ✅ Fixed
