# Bug Fixes Log

**Note**: This document tracks historical bugs fixed in v1.0-v2.0 (separate task architecture).  
v2.1+ uses the unified continuous service (run_trading_service.py).

This document serves as an **index/summary** of all bugs discovered and fixed in the automated trading system.  
For detailed documentation, architecture explanations, and examples, see the **Related Documentation** links in each bug entry.

---

## Bug #1: Reentry Logic After RSI Reset (CRITICAL)

**Date Fixed**: October 31, 2024  
**Severity**: Critical  
**Status**: ✅ Fixed

### Description
After RSI reset cycle (RSI > 30 → RSI < 30), the system was not triggering reentry at the RSI < 30 level. Instead, it waited for RSI < 20 because levels were incorrectly preserved as `{"30": True, "20": False, "10": False}` after reset.

### Root Cause
The reset logic was setting `reset_ready = True` when RSI > 30, but when RSI dropped below 30 again, it didn't reset the `levels_taken` dictionary. The level 30 remained marked as taken, so the system waited for the next level (RSI < 20).

### Expected Behavior
After a reset cycle:
1. RSI > 30 → Set `reset_ready = True`
2. RSI < 30 again → **NEW CYCLE** starts
3. Reset `levels_taken = {"30": False, "20": False, "10": False}`
4. Immediately trigger reentry at RSI < 30

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`  
**Lines**: 1330-1344

```python
# If reset_ready and rsi drops below 30 again, trigger NEW CYCLE reentry at RSI<30
if rsi < 30 and any(e.get('reset_ready') for e in entries):
    # This is a NEW CYCLE - treat RSI<30 as a fresh reentry opportunity
    for e in entries:
        e['levels_taken'] = {"30": False, "20": False, "10": False}  # Reset all levels
        e['reset_ready'] = False
    levels = entries[0]['levels_taken']
    # Immediately trigger reentry at this RSI<30 level
    next_level = 30
else:
    # Normal progression through levels
    next_level = None
    if levels.get('30') and not levels.get('20') and rsi < 20:
        next_level = 20
    if levels.get('20') and not levels.get('10') and rsi < 10:
        next_level = 10
```

### Test Case
**Symbol**: DALBHARAT
- Oct 28: RSI 31.75 (initial entry taken)
- Oct 29: RSI 32.73 (> 30, should set reset_ready=True)
- Oct 30: RSI 27.71 (< 30, should trigger new cycle at level 30) ✅
- Oct 31: RSI 29.01 (reentry executed)

### Impact
- Reentries now trigger correctly after reset cycles
- Maximizes position building opportunities
- Aligns with documented trading strategy

---

## Bug #2: Order Validation - nOrdNo Not Recognized (HIGH)

**Date Fixed**: October 31, 2024  
**Severity**: High  
**Status**: ✅ Fixed

### Description
System was logging successful orders as "failed" even though orders were executed on Kotak Neo. Orders placed successfully (with status 'Ok' and order number) were not being recognized by the validation logic.

### Root Cause
The validation logic at line 1375 only accepted responses with 'data', 'order', or 'raw' keys. However, Kotak Neo API returns successful orders with a direct `nOrdNo` field:

```python
{'nOrdNo': '251031000141476', 'stat': 'Ok', 'stCode': 200}
```

This response structure was not in the validation check, causing false negatives.

### Expected Behavior
System should recognize any response containing:
- `nOrdNo` or `nordno` (case-insensitive)
- Status 'Ok'
- Valid HTTP status code

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`  
**Line**: 1375

**Before**:
```python
resp_valid = isinstance(resp, dict) and ('data' in resp or 'order' in resp or 'raw' in resp) and 'error' not in resp and 'not_ok' not in str(resp).lower()
```

**After**:
```python
resp_valid = isinstance(resp, dict) and ('data' in resp or 'order' in resp or 'raw' in resp or 'nOrdNo' in resp or 'nordno' in str(resp).lower()) and 'error' not in resp and 'not_ok' not in str(resp).lower()
```

### Test Case
**Order**: #251031000141476 (DALBHARAT BUY 47 shares)
- Response: `{'nOrdNo': '251031000141476', 'stat': 'Ok', 'stCode': 200}`
- Previous behavior: Logged as failed ❌
- Current behavior: Recognized as successful ✅

### Impact
- Accurate order tracking
- Prevents duplicate order attempts
- Correct logging and audit trail

---

## Bug #3: Sell Order Not Updated After Reentry (CRITICAL)

**Date Fixed**: October 31, 2024  
**Severity**: Critical  
**Status**: ✅ Fixed

### Description
After a successful reentry order, the existing sell order quantity was not updated to reflect the new total position size. This caused:
- Sell orders to remain at original quantity
- Incomplete position closure when target hit
- Manual intervention required

### Root Cause
The reentry logic only:
1. Placed the buy order
2. Updated `levels_taken` tracking
3. Did NOT update the existing sell order

There was no code to:
- Find the existing sell order
- Calculate new total quantity
- Modify the sell order

### Expected Behavior
After reentry:
1. Calculate new total quantity: `old_qty + reentry_qty`
2. Find existing sell order for symbol
3. Modify order with new quantity via `modify_order()` API
4. Log the update for audit

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/orders.py`  
**Lines**: 191-235 (new method)

Added `modify_order()` method:
```python
def modify_order(self, order_id: str, price: float = None, quantity: int = None, 
                 trigger_price: float = 0, validity: str = "DAY") -> Optional[Dict]:
    """Modify an existing order's price and/or quantity."""
    client = self.auth.get_client()
    if not client:
        return None
    
    try:
        payload = {"order_id": order_id}
        if price is not None:
            payload["price"] = price
        if quantity is not None:
            payload["quantity"] = quantity
        if trigger_price:
            payload["trigger_price"] = trigger_price
        if validity:
            payload["validity"] = validity
        payload["disclosed_quantity"] = 0
        
        logger.info(f"📝 Modifying order {order_id}: qty={quantity}, price={price}")
        
        if hasattr(client, 'modify_order'):
            response = client.modify_order(**payload)
            # Validation and logging...
            return response
    except Exception as e:
        logger.error(f"Error modifying order: {e}")
        return None
```

**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`  
**Lines**: 1383-1421

Added automatic sell order update after reentry:
```python
# Update existing sell order with new total quantity
try:
    logger.info(f"Checking for existing sell order to update after reentry for {symbol}...")
    all_orders = self.orders.get_orders()
    if all_orders and isinstance(all_orders, dict) and 'data' in all_orders:
        for order in all_orders.get('data', []):
            # Find active sell order for this symbol
            if order_symbol == symbol.upper() and order_type in ['S', 'SELL'] and order_status in ['open', 'pending']:
                old_order_id = order.get('neoOrdNo') or order.get('nOrdNo') or order.get('orderId')
                old_qty = int(order.get('quantity') or order.get('qty') or 0)
                old_price = float(order.get('price') or order.get('prc') or 0)
                
                if old_order_id and old_qty > 0:
                    new_total_qty = old_qty + qty
                    logger.info(f"Found existing sell order for {symbol}: {old_qty} shares @ ₹{old_price:.2f}")
                    logger.info(f"Updating to new total: {old_qty} + {qty} (reentry) = {new_total_qty} shares")
                    
                    # Modify order with new quantity
                    modify_resp = self.orders.modify_order(
                        order_id=str(old_order_id),
                        quantity=new_total_qty,
                        price=old_price
                    )
                    
                    if modify_resp:
                        logger.info(f"✅ Sell order updated: {symbol} x{new_total_qty} @ ₹{old_price:.2f}")
                    break
except Exception as e:
    logger.error(f"Error updating sell order after reentry: {e}")
```

### Test Case
**Symbol**: DALBHARAT
- Original position: 186 shares
- Sell order: 186 shares @ ₹2,131.10
- Reentry: +47 shares @ market
- Expected: Sell order → 233 shares @ ₹2,131.10 ✅

### Impact
- Complete position closure when target hit
- No manual intervention required
- Accurate order management

---

## Bug #4: Trade History Not Updated After Reentry (HIGH)

**Date Fixed**: October 31, 2024  
**Severity**: High  
**Status**: ✅ Fixed

### Description
After a successful reentry, the trade history (tracked in `trade_engine_state.json`) was not updated with the new total quantity. This caused:
- Incorrect position tracking
- Mismatch between actual holdings and recorded history
- Manual reconciliation required

### Root Cause
The reentry logic updated `levels_taken` tracking but did NOT update the `qty` field in the trade entry. Reconciliation logic only ADDS new positions, it doesn't update quantities of existing tracked positions.

### Expected Behavior
After reentry:
1. Update `qty` field: `old_qty + reentry_qty`
2. Add reentry metadata for audit trail
3. Maintain complete history of position builds

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`  
**Lines**: 1423-1442

Added automatic trade history update:
```python
# Update trade history with new total quantity
try:
    logger.info(f"Updating trade history quantity after reentry for {symbol}...")
    for e in entries:
        old_qty = e.get('qty', 0)
        new_total_qty = old_qty + qty
        e['qty'] = new_total_qty
        logger.info(f"Trade history updated: {symbol} qty {old_qty} → {new_total_qty}")
        
        # Also add reentry metadata for tracking
        if 'reentries' not in e:
            e['reentries'] = []
        e['reentries'].append({
            'qty': qty,
            'level': next_level,
            'rsi': rsi,
            'price': price,
            'time': datetime.now().isoformat()
        })
except Exception as e:
    logger.error(f"Error updating trade history after reentry: {e}")
```

### Test Case
**Symbol**: DALBHARAT
- Original: 186 shares
- Reentry: +47 shares at RSI 29.01, level 30
- Expected: Trade history qty → 233 shares ✅
- Expected: Reentry metadata logged ✅

### Impact
- Accurate position tracking
- Complete audit trail
- No manual updates required
- Historical reentry data preserved

---

## Bug #5: Scheduled Task Timeout Configuration (MEDIUM)

**Date Fixed**: October 31, 2024  
**Severity**: Medium  
**Status**: ✅ Fixed

### Description
The `TradingBot-SellMonitor` scheduled task was failing with timeout error (code 2147946720). Task configuration had:
- Start time: 5:15 AM
- Wait until: 9:15 AM (4-hour wait)
- Timeout: Unlimited (default)

The combination of long wait time and unlimited timeout caused Windows Task Scheduler issues.

### Root Cause
Windows Task Scheduler best practices:
- Use explicit timeouts (not unlimited)
- Start task close to execution time
- Avoid very long wait periods before actual work

### Expected Behavior
- Task starts close to execution time
- Explicit timeout prevents hanging
- Clear separation between task start and work start

### Fix Applied
**Task**: TradingBot-SellMonitor

**Before**:
- Start: 5:15 AM
- Wait: 4 hours (until 9:15 AM)
- Timeout: Unlimited

**After**:
- Start: 9:00 AM
- Wait: 15 minutes (until 9:15 AM)
- Timeout: 8 hours (PT8H)

**Task**: TradingBot-BuyOrders

**Updated**:
- Runs at: 4:05 PM AND 9:00 AM (dual triggers)
- Timeout: 2 hours (PT2H)
- Removed: Duplicate `TradingBot-PlaceOrders` task

### Test Case
- Next run: Nov 3, 2025 at 9:00 AM
- Expected: Task runs successfully ✅
- Expected: Sell orders placed at 9:15 AM ✅

### Impact
- Reliable task execution
- No timeout errors
- Proper scheduling alignment

---

## Summary Statistics

**Total Bugs Fixed**: 5  
**Critical Severity**: 3  
**High Severity**: 1  
**Medium Severity**: 1  

**Components Affected**:
- Reentry logic (auto_trade_engine.py)
- Order validation (auto_trade_engine.py)
- Order modification (orders.py)
- Trade history tracking (auto_trade_engine.py)
- Scheduled tasks (Windows Task Scheduler)

**Files Modified**:
1. `modules/kotak_neo_auto_trader/auto_trade_engine.py`
2. `modules/kotak_neo_auto_trader/orders.py`
3. Windows Task Scheduler configuration

**Lines of Code Changed**: ~150 lines

---

## Testing & Validation

All fixes have been tested with:
- ✅ Real trading scenario (DALBHARAT reentry)
- ✅ Manual verification of order placement
- ✅ Trade history reconciliation
- ✅ Scheduled task execution

**Current System Status**: Fully Operational ✅

**Date**: October 31, 2024  
**Version**: 2.0 (Post-Bug Fixes)

---

## Future Monitoring

### Key Metrics to Watch
1. Reentry trigger accuracy after RSI resets
2. Order validation success rate
3. Sell order modification success rate
4. Trade history accuracy
5. Scheduled task reliability

### Recommended Checks
- Daily: Review logs for order validation
- Weekly: Verify trade history matches holdings
- Monthly: Audit reentry metadata completeness

### Potential Edge Cases
- Multiple reentries on same day (max 1 per symbol enforced)
- Network failures during order modification
- Rapid RSI fluctuations around reset threshold (30)
- Concurrent order modifications from multiple sources

---

## Test Results

**Test Suite**: `tests/test_bug_fixes_oct31.py`  
**Status**: ✅ All tests passing  
**Tests Run**: 22  
**Tests Passed**: 22  
**Tests Failed**: 0  

### Test Coverage by Bug

#### Bug #1: Reentry Logic After RSI Reset
- ✅ `test_reset_cycle_triggers_new_entry_at_rsi_30` - Verifies new cycle starts at RSI < 30
- ✅ `test_normal_progression_without_reset` - Verifies normal 30→20→10 progression
- ✅ `test_no_reentry_when_all_levels_taken` - Verifies no reentry when exhausted
- ✅ `test_reset_ready_flag_set_when_rsi_above_30` - Verifies reset_ready flag

#### Bug #2: Order Validation - nOrdNo Recognition
- ✅ `test_validate_response_with_nOrdNo_field` - Validates direct nOrdNo responses
- ✅ `test_validate_response_with_data_field` - Validates backward compatibility
- ✅ `test_reject_response_with_error` - Rejects error responses
- ✅ `test_reject_response_with_not_ok_status` - Rejects Not_Ok status

#### Bug #3: Sell Order Update After Reentry
- ✅ `test_modify_order_updates_quantity` - Tests modify_order API
- ✅ `test_sell_order_quantity_calculation_after_reentry` - Validates quantity math
- ✅ `test_find_existing_sell_order_for_symbol` - Tests order lookup logic

#### Bug #4: Trade History Update After Reentry
- ✅ `test_trade_history_quantity_update` - Validates quantity update + metadata
- ✅ `test_multiple_reentries_tracking` - Tests multiple reentry tracking
- ✅ `test_reentry_metadata_structure` - Validates metadata fields

#### Bug #5: Scheduled Task Configuration
- ✅ `test_sell_monitor_task_timing` - Validates task timing configuration
- ✅ `test_buy_orders_task_dual_triggers` - Validates dual trigger setup
- ✅ `test_timeout_format_validation` - Validates ISO 8601 format
- ✅ `test_task_schedule_no_overlap` - Validates intentional overlap handling

### Integration & Edge Cases
- ✅ `test_complete_reentry_workflow` - End-to-end reentry workflow
- ✅ `test_reentry_with_zero_rsi` - Extreme RSI value handling
- ✅ `test_concurrent_reentry_same_day` - Single reentry per day enforcement
- ✅ `test_order_modification_with_none_values` - None value handling

### Running the Tests

```powershell
# Run all bug fix tests
.\.venv\Scripts\python.exe -m pytest tests/test_bug_fixes_oct31.py -v

# Run specific test class
.\.venv\Scripts\python.exe -m pytest tests/test_bug_fixes_oct31.py::TestReentryLogicAfterReset -v

# Run with coverage
.\.venv\Scripts\python.exe -m pytest tests/test_bug_fixes_oct31.py --cov=modules.kotak_neo_auto_trader -v
```

---

## Bug #6: Duplicate Order Registration (HIGH)

**Date Fixed**: November 7, 2025  
**Severity**: High  
**Status**: ✅ Fixed

### Description
Same order_id was being registered multiple times in `pending_orders.json`, creating duplicate entries. Example: DALBHARAT order_id `251106000008974` appeared 3 times with different timestamps and prices (including ₹0.0).

### Root Cause
- `add_pending_order()` in `order_tracker.py` didn't check for existing orders before adding
- `register_sell_order()` in `order_state_manager.py` always called `add_pending_order()` without checking if order already exists
- When `run_at_market_open()` found existing orders from broker, it re-registered them

### Fix Applied
**Files**: 
- `modules/kotak_neo_auto_trader/order_tracker.py` - Added duplicate check in `add_pending_order()`
- `modules/kotak_neo_auto_trader/order_state_manager.py` - Added duplicate check and proper return after price update in `register_sell_order()`

### Impact
- Prevents duplicate order entries
- Prevents zero price overwriting correct price
- Ensures proper price updates with `last_updated` timestamp

### Related Documentation
- **[Pending Order Maintenance Logic](../architecture/PENDING_ORDER_MAINTENANCE_LOGIC.md)** - Detailed explanation of how pending orders are maintained

---

## Bug #7: Target and Lowest EMA9 Showing ₹0.00 (MEDIUM)

**Date Fixed**: November 7, 2025  
**Severity**: Medium  
**Status**: ✅ Fixed

### Description
When monitoring sell orders, Target and Lowest EMA9 values showed ₹0.00 instead of actual values. Example log: `DALBHARAT: Current EMA9=₹2095.30, Target=₹0.00, Lowest=₹0.00`

### Root Cause
- When syncing orders from `OrderStateManager`, `lowest_ema9` dictionary was not initialized
- If `target_price` was 0 (from duplicate bug), both Target and Lowest showed 0.00
- `lowest_ema9` was only set when orders were placed, not when syncing existing orders

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- `_get_active_orders()`: Initialize `lowest_ema9` from `target_price` when syncing (if > 0)
- `_check_and_update_single_stock()`: Initialize `lowest_ema9` from `target_price` or current EMA9 if missing
- Handle zero `target_price` by using `lowest_ema9` or current EMA9 for display

### Impact
- Target and Lowest always show meaningful values
- Better visibility for monitoring
- Prevents unnecessary first update when EMA9 hasn't changed

### Related Documentation
- **[Target/Lowest Same Value Impact Analysis](../analysis/TARGET_LOWEST_SAME_VALUE_IMPACT.md)** - Detailed impact analysis showing why Target == Lowest is safe
- **[Target/Lowest EMA9 Fix Example](../examples/TARGET_LOWEST_EMA9_FIX_EXAMPLE.md)** - Step-by-step example with before/after scenarios

---

## Bug #8: Unknown Broker Status Warning for CANCELLED Orders (MEDIUM)

**Date Fixed**: November 7, 2025  
**Severity**: Medium  
**Status**: ✅ Fixed

### Description
System logged warnings "Unknown broker status: CANCELLED" when orders were cancelled. The status parser correctly mapped "cancelled" to "CANCELLED", but the verification logic didn't handle it.

### Root Cause
- `order_status_verifier.py` had status map with `'cancelled': 'CANCELLED'` but didn't handle `'CANCELLED'` status in `verify_pending_orders()`
- Only handled: EXECUTED, REJECTED, PARTIALLY_FILLED, OPEN, PENDING
- CANCELLED status fell into "Unknown broker status" branch

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/order_status_verifier.py`
- Added `_handle_cancellation()` method to properly handle cancelled orders
- Added CANCELLED status handling in `verify_pending_orders()` and `verify_order_by_id()`
- Added cancelled count to verification statistics

### Impact
- No more "Unknown broker status" warnings for cancelled orders
- Proper tracking and cleanup of cancelled orders
- Better visibility in verification statistics

---

*Last Updated: November 7, 2025*
