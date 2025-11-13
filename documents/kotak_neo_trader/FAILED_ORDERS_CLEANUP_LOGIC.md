# Failed Orders Cleanup - Logic and Fix

## Problem

Failed orders (e.g., CURAA from 2025-10-30) were not being automatically removed from trade history. The cleanup function existed but was never called by `run_trading_service.py`.

## Purpose

Failed orders are kept in `failed_orders` list for retry. Over time, these can accumulate and become stale (e.g., insufficient balance might persist). This logic removes expired failed orders automatically.

## Business Logic

Failed orders exist because the system should **retry** them at appropriate times:
- If a buy failed due to insufficient funds, retry when balance is available
- If a buy failed due to market conditions, retry under better conditions

But we can't retry indefinitely - failed orders should expire after a reasonable period.

## Cleanup Rules

### Rule 1: Today's Orders - Always Keep ✅
```
If order failed today → KEEP (retry today or next run)
```

**Rationale**: Very recent failures should be retried immediately.

**Example**:
- Today: 2025-11-04, 10:00 AM
- Failed at: 2025-11-04, 9:00 AM
- **Action**: KEEP (failed 1 hour ago)

### Rule 2: Yesterday's Orders - Keep Until Market Open ✅
```
If order failed yesterday → KEEP until 9:15 AM today, then REMOVE
```

**Rationale**: Yesterday's failures can be retried in pre-market or at market open, but after 9:15 AM today, they're stale and unlikely to succeed.

**Example 1** (Before Market Open):
- Today: 2025-11-04, 9:00 AM
- Failed at: 2025-11-03, 3:00 PM
- **Action**: KEEP (retry opportunity before market opens)

**Example 2** (After Market Open):
- Today: 2025-11-04, 10:00 AM
- Failed at: 2025-11-03, 3:00 PM
- **Action**: REMOVE (market already opened, too late to retry)

### Rule 3: Older Orders - Always Remove ✅
```
If order failed 2+ days ago → REMOVE immediately
```

**Rationale**: Orders older than 2 days are too stale to retry. Market conditions have changed, prices have moved, and the original signal is no longer valid.

**Example**:
- Today: 2025-11-04
- Failed at: 2025-11-02 (2 days ago)
- **Action**: REMOVE

### Rule 4: Orders Without Timestamp - Remove ❌
```
If order has no first_failed_at → REMOVE
```

**Rationale**: Invalid/malformed orders should be cleaned up.

**Example**:
- Failed order exists but `first_failed_at` is None or missing
- **Action**: REMOVE

## Timeline Examples

### Example 1: Order Failed on Monday
```
Monday 3:00 PM    → Order fails (insufficient balance)
Monday 3:30 PM    → CLEANUP → KEEP (today's order)
Tuesday 9:00 AM   → CLEANUP → KEEP (yesterday's order, before market open)
Tuesday 9:20 AM   → CLEANUP → REMOVE (yesterday's order, market opened)
```

### Example 2: Order Failed on Previous Week
```
Thursday (3 days ago) → Order failed
Today                  → CLEANUP → REMOVE (2+ days old)
```

### Example 3: Current Scenario (CURAA)
```
2025-10-30 (Thu)   → Order failed
2025-11-04 (Tue)   → CLEANUP → REMOVE (5 days old, far beyond limit)
```

## When Cleanup Runs

### Current Behavior:
- **Manually**: Can call `cleanup_expired_failed_orders()` anytime
- **Automatically**: 
  - EOD cleanup at 6:00 PM daily (after fix)
  - During buy order placement in `auto_trade_engine.py`

### Why EOD Cleanup?
Running at 6:00 PM ensures:
1. Market is closed (after 3:30 PM)
2. All retry opportunities for the day have passed
3. Stale orders are removed before next trading day
4. Fresh start for tomorrow

## Code Flow

```python
def cleanup_expired_failed_orders(path):
    failed_orders = load_history(path).get('failed_orders', [])
    now = datetime.now()
    today = now.date()
    current_time = now.time()
    
    kept_orders = []
    removed_count = 0
    
    for order in failed_orders:
        failed_date = parse(order.first_failed_at).date()
        
        if failed_date == today:
            # Rule 1: Today - KEEP
            kept_orders.append(order)
        elif failed_date == today - 1 day:
            # Rule 2: Yesterday - KEEP until 9:15 AM
            if current_time < 9:15 AM:
                kept_orders.append(order)
            else:
                removed_count += 1
        else:
            # Rule 3: Older - REMOVE
            removed_count += 1
    
    save_history(kept_orders)
    return removed_count
```

## Why This Logic?

### Retry Window Strategy:
- **Day 0**: Immediate retry (market conditions might improve)
- **Day 1**: Retry next day before market opens (overnight balance changes)
- **Day 2+**: No retry (signal is stale)

### Pre-Market Opportunity:
The system has a "premarket retry" task at 9:00 AM that retries failed orders from yesterday. Cleaning up at 9:15 AM allows:
1. Yesterday's failures get one retry attempt at 9:00 AM
2. If still not resolved by 9:15 AM, they're removed
3. No infinite accumulation of failed orders

## Impact

### Before Fix:
- Failed orders accumulated indefinitely
- Trade history became cluttered
- Manual cleanup required

### After Fix:
- Automatic daily cleanup at EOD
- Failed orders older than 1 day (after market open) are removed
- Clean, manageable trade history
- No manual intervention needed

## Fix Applied

Added failed orders cleanup to `run_trading_service.py` EOD cleanup task:

```python
def run_eod_cleanup(self):
    """6:00 PM - End-of-day cleanup"""
    # Clean up expired failed orders
    from .storage import cleanup_expired_failed_orders
    removed_count = cleanup_expired_failed_orders(config.TRADES_HISTORY_PATH)
    if removed_count > 0:
        logger.info(f"✅ Cleaned up {removed_count} expired failed order(s)")
```

This runs every day at 6:00 PM.

## Files Modified

- `modules/kotak_neo_auto_trader/run_trading_service.py`: Added cleanup call to `run_eod_cleanup()`

## Testing Results

**Before**:
```json
"failed_orders": [{"symbol": "CURAA", "first_failed_at": "2025-10-30T09:00:25"}]
```

**After cleanup**:
```json
"failed_orders": []
```

## Status

✅ **Logic is sound and production-ready**  
✅ **EOD cleanup now calls this function**  
✅ **CURAA (5 days old) successfully removed**  
✅ **Fix committed**

