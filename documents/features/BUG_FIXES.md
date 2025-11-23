# Bug Fixes Log

**Note**: This document tracks historical bugs fixed in v1.0-v2.0 (separate task architecture).
v2.1+ uses the unified continuous service (run_trading_service.py).

This document serves as an **index/summary** of all bugs discovered and fixed in the automated trading system.
For detailed documentation, architecture explanations, and examples, see the **Related Documentation** links in each bug entry.

---

## Bug #58: Orders Dashboard Price Precision (MEDIUM)

**Date Fixed**: November 17, 2025
**Status**: ✅ Fixed

### Description
The Orders dashboard rendered raw floating-point values returned by the API. Some prices showed arbitrary precision such as `1592.5355166940217`, which is confusing when operators expect two-decimal currency formatting.

### Root Cause
`web/src/routes/dashboard/OrdersPage.tsx` displayed `order.price` directly inside the table. Since the backend stores IEEE 754 floats, values kept the original binary precision and were not rounded or truncated before rendering.

### Expected Behavior
All monetary values shown on the Orders page should follow the product spec in the mockups:

1. Clamp/truncate to two decimal places (₹xx.yy)
2. Fall back to an em dash when `null`/`NaN`
3. Apply consistent formatting across all order tabs

### Fix Applied
Added a `formatPrice()` helper that truncates to two decimals and returns an em dash when the value is missing:

```tsx
const formatPrice = (value: number | null | undefined): string => {
	if (typeof value !== 'number' || Number.isNaN(value)) {
		return '—';
	}
	const truncated = Math.trunc(value * 100) / 100;
	return truncated.toFixed(2);
};
```

The Orders table now calls `formatPrice(o.price)` for every row.

### Test Coverage
- `web/src/routes/__tests__/OrdersPage.test.tsx` asserts the AMO tab renders `1500.00`, guarding against regressions.

### Impact
- Consistent currency formatting across AMO/ongoing/sell/closed tabs
- Better UX during manual QA and customer demos
- Prevents future regressions by codifying expected formatting in unit tests

---

## Bug #59: Session Lost After Browser Refresh (HIGH)

**Date Fixed**: November 17, 2025
**Status**: ✅ Fixed

### Description
Refreshing the dashboard wiped the in-memory Zustand session store and the UI immediately redirected to `/login`. Users had to re-enter credentials even though their refresh token was still valid.

### Root Cause
- The frontend only persisted the short-lived access token (`ta_access_token`) in `localStorage`.
- On reload, `useSessionStore.initialize()` looked for an access token only; if absent, it assumed the user was logged out.
- The API offered no `/auth/refresh` endpoint nor refresh tokens, so there was no way to mint a new access token without re-entering credentials.

### Fix Applied
- Backend:
  - Added long-lived refresh tokens via `create_jwt_token(..., expires_days=settings.jwt_refresh_days)` during signup/login.
  - Created `/api/v1/auth/refresh` endpoint with a dedicated `RefreshRequest` schema and verification logic (`type="refresh"` claims, user checks).
- Frontend:
  - Stored both `ta_access_token` and `ta_refresh_token` and added an Axios response interceptor that transparently exchanges a refresh token on 401s.
  - `useSessionStore.initialize()` now calls `requestTokenRefresh()` whenever only a refresh token is available, preventing logout on reload.
  - Added regression test `web/src/state/__tests__/sessionStore.test.ts` to ensure initialization falls back to the refresh token path.

### Impact
- Seamless session continuity across hard reloads.
- Reduced customer friction during demos and manual testing.
- Clearer contract between frontend and backend regarding token lifetimes and refresh cadence.

---

## Bug #60: Text Not Visible on White Backgrounds (HIGH)

**Date Fixed**: November 17, 2025
**Status**: ✅ Fixed

### Description
Across all dashboard pages, text was invisible because components used default Tailwind classes (`bg-white`, `bg-gray-50`, `border`) that created white/light backgrounds, while the app uses a dark theme with light text (`var(--text): #e6edf3`). This caused white text on white backgrounds, making all content unreadable.

### Root Cause
- Components like `AdminUsersPage`, `OrdersPage`, `PnlPage`, `TargetsPage`, and `ActivityPage` used default Tailwind utility classes that assume a light theme.
- Input fields, select dropdowns, table headers, and panel containers had white/light gray backgrounds without explicit text colors.
- The app's dark theme CSS variables (`--text`, `--panel`, `--muted`) were defined but not consistently applied across all components.

### Fix Applied
**Files Updated:**
- `web/src/routes/dashboard/AdminUsersPage.tsx`
- `web/src/routes/dashboard/OrdersPage.tsx`
- `web/src/routes/dashboard/PnlPage.tsx`
- `web/src/routes/dashboard/TargetsPage.tsx`
- `web/src/routes/dashboard/ActivityPage.tsx`
- `web/src/routes/AppShell.tsx`

**Changes:**
- Replaced `bg-white` and `bg-gray-50` with `bg-[var(--panel)]` and `bg-[#0f172a]` for dark backgrounds.
- Added explicit `text-[var(--text)]` to all text elements (headings, table cells, labels).
- Updated input/select fields to use `bg-[#0f1720] border border-[#1e293b] text-[var(--text)]`.
- Changed table headers from `bg-gray-50` to `bg-[#0f172a] text-[var(--muted)]`.
- Updated borders to use `border-[#1e293b]` for consistent dark theme styling.
- Added hover states to navigation links: `hover:text-[var(--accent)]`.

### Test Coverage
- Manual visual verification across all affected pages.
- Existing unit tests continue to pass (styling changes don't affect functionality).

### Impact
- All text is now visible and readable across the entire dashboard.
- Consistent dark theme styling throughout the application.
- Better UX with proper contrast ratios for accessibility.
- Navigation links now have clear hover feedback.

---

## Bug #61: Time Display Format in Service Status Page (MEDIUM)

**Date Fixed**: November 17, 2025
**Status**: ✅ Fixed

### Description
The Service Status page displayed time in raw seconds format (e.g., "4238s ago"), which was not user-friendly. Users expected a more readable format like "32 sec ago", "1 min ago", or "1hr ago" depending on the duration.

### Root Cause
- The time calculation used `Math.floor((Date.now() - timestamp.getTime()) / 1000)` to get seconds, then displayed it as `{seconds}s ago`.
- No formatting logic existed to convert seconds into human-readable units (seconds, minutes, hours).

### Fix Applied
**Files Updated:**
- `web/src/routes/dashboard/ServiceStatusPage.tsx`
- `web/src/routes/dashboard/ServiceTasksTable.tsx`
- `web/src/utils/time.ts` (new utility file)
- `web/src/utils/__tests__/time.test.ts` (new test file)

**Changes:**
- Created `formatTimeAgo()` utility function that formats seconds into:
  - `< 60 seconds`: "32 sec ago"
  - `>= 60 seconds but < 3600`: "1 min ago", "2 min ago", etc.
  - `>= 3600 seconds`: "1hr ago", "2hr ago", etc.
- Updated "Last Heartbeat" and "Last Task Execution" displays to use `formatTimeAgo()`.
- Added explicit text colors to ensure all text is visible in dark theme.
- Added comprehensive unit tests for the time formatting function.

### Test Coverage
- Unit tests in `web/src/utils/__tests__/time.test.ts` covering:
  - Seconds < 60: "32 sec ago"
  - Seconds 60-3599: "1 min ago", "2 min ago", etc.
  - Seconds >= 3600: "1hr ago", "2hr ago", etc.
- Manual verification with various time values (32s, 69s, 3678s, 4238s).

### Impact
- More intuitive and readable time displays.
- Consistent formatting across all time-related displays.
- Better user experience when monitoring service status.
- Reusable utility function for future time formatting needs.

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

## Bug #62: SQLAlchemy Mapper Conflicts in Parallel Test Execution (HIGH)

**Date Fixed**: November 18, 2025
**Status**: ✅ Fixed

### Description
When running tests in parallel using pytest-xdist, SQLAlchemy raised errors: "Multiple classes found for path 'UserSettings' in the registry of this declarative base." This prevented parallel test execution and caused test failures.

### Root Cause
- When pytest-xdist spawns worker processes, each worker imports models independently
- SQLAlchemy's registry can get confused when models are imported multiple times across different worker processes
- The `conftest.py` imported models at module level, but this wasn't sufficient for parallel execution

### Fix Applied
**Files Updated:**
- `tests/conftest.py`

**Changes:**
- Added `pytest_configure_node()` hook that runs when each worker node is set up
- Ensures models are imported once per worker process before any tests run
- Calls `configure_mappers()` to properly initialize SQLAlchemy's mapper registry

```python
def pytest_configure_node(node):
    """
    Called when a worker node is being set up for parallel execution.
    Ensures models are imported once per worker to avoid SQLAlchemy registry conflicts.
    """
    try:
        import src.infrastructure.db.models  # noqa: F401
        from sqlalchemy.orm import configure_mappers
        configure_mappers()
    except Exception:
        pass
```

### Test Coverage
- All tests now pass in parallel execution mode
- No more "Multiple classes found" errors
- 1393 tests passing in parallel execution

### Impact
- Tests can now run in parallel without conflicts
- Faster test execution with pytest-xdist
- Better CI/CD pipeline performance

---

## Bug #63: Migration Test Files Not Removed After One-Time Migration (LOW)

**Date Fixed**: November 18, 2025
**Status**: ✅ Fixed

### Description
Migration test files (`test_data_migration.py` and `test_migration_scripts.py`) were still present in the test suite even though data migration was a one-time task that has been completed.

### Root Cause
- Migration scripts were created for Phase 1.2 data migration
- Test files were created to validate migration logic
- After migration was complete, test files were not removed

### Fix Applied
**Files Removed:**
- `tests/integration/test_data_migration.py`
- `tests/unit/infrastructure/test_migration_scripts.py`

### Impact
- Cleaner test suite focused on current functionality
- Reduced test execution time
- No confusion about migration status

---

## Bug #64: Broker Test Endpoint Rejects Unsupported Brokers (MEDIUM)

**Date Fixed**: November 18, 2025
**Status**: ✅ Fixed

### Description
The `/api/v1/user/broker/test` endpoint returned HTTP 422 (Unprocessable Entity) when testing with unsupported broker names, even though the endpoint logic was designed to return HTTP 200 with `ok: false` in the response body.

### Root Cause
- `BrokerCredsRequest` schema used `Literal["kotak-neo"]` which enforced strict validation
- FastAPI rejected requests with any other broker name before the endpoint handler could process them
- The test expected HTTP 200 with error message in response body

### Fix Applied
**Files Updated:**
- `server/app/schemas/user.py`

**Changes:**
- Changed `broker: Literal["kotak-neo"]` to `broker: str` with default value
- Allows any broker name to be passed to the endpoint
- Endpoint logic now properly handles unsupported brokers and returns appropriate response

```python
class BrokerCredsRequest(BaseModel):
    broker: str = Field(default="kotak-neo", description="Broker name (e.g., 'kotak-neo')")
    # ... rest of fields
```

### Test Coverage
- `test_test_broker_connection_unsupported_broker` now passes
- Endpoint correctly returns HTTP 200 with `ok: false` for unsupported brokers

### Impact
- Consistent API behavior for all broker names
- Better error handling and user feedback
- Tests can properly validate unsupported broker scenarios

---

## Bug #65: Test Email Conflicts in Parallel Execution (MEDIUM)

**Date Fixed**: November 18, 2025
**Status**: ✅ Fixed

### Description
Test `test_activity_and_targets` failed with HTTP 409 (Conflict) error "Email already registered" when running tests in parallel. The test used a hardcoded email address that could conflict with other test runs.

### Root Cause
- Test used hardcoded email `pat_tester@example.com`
- When tests run in parallel, multiple workers could try to create users with the same email
- Database unique constraint on email caused conflicts

### Fix Applied
**Files Updated:**
- `tests/server/test_pnl_activity_targets.py`

**Changes:**
- Modified `_auth_client()` to generate unique email addresses using UUID
- Each test run now uses a different email, preventing conflicts

```python
def _auth_client() -> tuple[TestClient, dict]:
    import uuid
    client = TestClient(app)
    # Use unique email to avoid conflicts
    unique_email = f"pat_tester_{uuid.uuid4().hex[:8]}@example.com"
    # ... rest of function
```

### Test Coverage
- `test_activity_and_targets` now passes consistently
- No more email conflicts in parallel execution

### Impact
- Tests can run safely in parallel
- No test isolation issues
- More reliable CI/CD pipeline

---

## Bug #66: Migration Function Missing Trades Processed Counter (MEDIUM)

**Date Fixed**: November 18, 2025
**Status**: ✅ Fixed

### Description
The `migrate_trades_history()` function in `scripts/migration/migrate_trades_history.py` was not incrementing the `trades_processed` counter, causing test `test_migrate_single_trade` to fail with assertion `assert stats["trades_processed"] == 1` (got 0).

### Root Cause
- Function incremented `orders_created` and `fills_created` counters
- But forgot to increment `trades_processed` counter
- Test expected `trades_processed` to be incremented for each trade processed

### Fix Applied
**Files Updated:**
- `scripts/migration/migrate_trades_history.py`

**Changes:**
- Added `stats['trades_processed'] += 1` after successfully processing each trade
- Counter now correctly tracks number of trades processed

```python
stats['trades_processed'] += 1
stats['orders_created'] += 1
stats['fills_created'] += 1
```

### Test Coverage
- Migration tests now pass (though migration tests were later removed as one-time task)

### Impact
- Accurate migration statistics
- Better visibility into migration progress
- Correct test assertions

---

## Bug #67: Playwright E2E Tests Picked Up by Vitest (LOW)

**Date Fixed**: November 18, 2025
**Status**: ✅ Fixed

### Description
Playwright E2E tests in `tests/e2e/` were being picked up by Vitest when running `npm test`, causing errors: "Playwright Test did not expect test.describe() to be called here."

### Root Cause
- Vitest configuration didn't exclude E2E test directory
- Vitest tried to run Playwright test files as Vitest tests
- Playwright and Vitest have incompatible test APIs

### Fix Applied
**Files Updated:**
- `web/vitest.config.ts`

**Changes:**
- Added `exclude` pattern to exclude E2E tests from Vitest runs
- E2E tests should only be run with `npm run test:e2e` (Playwright)

```typescript
test: {
    exclude: ['**/node_modules/**', '**/dist/**', '**/tests/e2e/**'],
    // ... rest of config
}
```

### Test Coverage
- Vitest now only runs unit/integration tests
- Playwright E2E tests run separately without conflicts
- All 157 frontend unit tests passing

### Impact
- Clean separation between unit tests and E2E tests
- No more test runner conflicts
- Faster unit test execution (E2E tests excluded)

---

## Bug #68: Timezone Comparison Errors in Conflict Detection and Schedule Manager (HIGH)

**Date Fixed**: January 2025
**Status**: ✅ Fixed

### Description
Multiple services raised `TypeError: can't compare offset-naive and offset-aware datetimes` when comparing datetime objects. This occurred in:
- `ConflictDetectionService.check_conflict()` - comparing task execution times
- `ConflictDetectionService.is_task_running()` - checking recent task executions
- `ScheduleManager.calculate_next_execution()` - calculating next execution times

### Root Cause
- SQLite returns naive datetimes from the database (no timezone info)
- `ist_now()` returns timezone-aware datetimes (IST timezone)
- Python cannot directly compare naive and timezone-aware datetimes
- `datetime.combine()` creates naive datetimes, but comparisons were made with timezone-aware datetimes

### Fix Applied
**Files Updated:**
- `src/application/services/conflict_detection_service.py`
- `src/application/services/schedule_manager.py`

**Changes:**

1. **ConflictDetectionService** - Normalize database datetimes to timezone-aware before comparison:
```python
# Normalize executed_at to timezone-aware if it's naive
executed_at = task.executed_at
if executed_at.tzinfo is None:
    executed_at = executed_at.replace(tzinfo=IST)
if executed_at >= cutoff_time:
    # ... comparison logic
```

2. **ScheduleManager** - Preserve timezone when using `datetime.combine()`:
```python
result = datetime.combine(current_date, schedule.schedule_time)
schedule_datetime = result.replace(tzinfo=current_time.tzinfo) if current_time.tzinfo else result
```

### Test Coverage
- `test_check_conflict_recent_task_execution` - PASSING
- `test_list_schedules_success` - PASSING
- All schedule manager tests - PASSING

### Impact
- No more timezone comparison errors
- Proper conflict detection between unified and individual services
- Accurate next execution time calculations
- Better reliability in production

---

## Bug #69: Test Login Failures Due to Incorrect Password Hashing (MEDIUM)

**Date Fixed**: January 2025
**Status**: ✅ Fixed

### Description
Multiple test files failed with HTTP 401 (Unauthorized) errors during login. Tests in `test_admin_schedules_api.py` and `test_individual_service_api.py` were unable to authenticate users created by fixtures.

### Root Cause
- Test fixtures created users directly with `password_hash="hashed_password"` (plain string, not a real hash)
- Login helper tried to signup first, which would create a user with properly hashed password
- If user already existed (409 Conflict), login would fail because stored hash didn't match the password being used
- In parallel execution, this caused race conditions and authentication failures

### Fix Applied
**Files Updated:**
- `tests/unit/server/test_admin_schedules_api.py`
- `tests/unit/server/test_individual_service_api.py`

**Changes:**

1. **Fixtures** - Use `UserRepository.create_user()` with proper password hashing:
```python
@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing"""
    return UserRepository(db_session).create_user(
        email="admin@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
```

2. **Login Helper** - Handle existing users gracefully:
```python
def login(client: TestClient, email: str, password: str) -> str:
    """Helper to login and get token"""
    # Try signup first (in case user doesn't exist)
    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    # If user already exists (409), that's fine - just proceed to login
    if signup_response.status_code == 200:
        return signup_response.json()["access_token"]

    # User exists, so login
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]
```

### Test Coverage
- All admin schedule API tests - PASSING
- All individual service API tests - PASSING
- No more authentication failures in parallel execution

### Impact
- Reliable test authentication
- Proper password hashing in test fixtures
- Better test isolation
- No race conditions in parallel test execution

---

## Bug #70: Invalid Time Test Causing ValueError (LOW)

**Date Fixed**: January 2025
**Status**: ✅ Fixed

### Description
Test `test_validate_schedule_invalid_time` failed with `ValueError: hour must be in 0..23` because it tried to create `time(25, 0)`, which is invalid in Python's time constructor.

### Root Cause
- Test attempted to create an invalid time object to test validation logic
- Python's `time()` constructor validates hours (0-23) and raises ValueError before validation logic can run
- Test couldn't reach the actual validation code being tested

### Fix Applied
**Files Updated:**
- `tests/unit/application/test_schedule_manager.py`

**Changes:**
- Changed test to use a valid time that fails business hours validation instead:
```python
def test_validate_schedule_invalid_time(db_session, schedule_manager):
    """Test validation fails for time outside business hours"""
    # Test with time outside business hours (9:00 - 18:00) for non-continuous, non-hourly tasks
    is_valid, message = schedule_manager.validate_schedule(
        task_name="premarket_retry",
        schedule_time=time(8, 0),  # Before business hours
        is_hourly=False,
        is_continuous=False,
        end_time=None,
    )
    assert not is_valid
    assert "business hours" in message.lower() or "9:00" in message or "18:00" in message
```

### Test Coverage
- `test_validate_schedule_invalid_time` - PASSING
- Validates actual validation logic without triggering Python's time constructor error

### Impact
- Test properly validates schedule validation logic
- No more ValueError from invalid time construction
- Better test coverage of validation rules

---

## Bug #62: Rejected Orders Not Saved to Database (CRITICAL)

**Date Fixed**: November 22, 2025
**Status**: ✅ Fixed

### Description
When orders were rejected by the broker, they were not being saved to the database. Orders placed successfully (with order ID from broker) but immediately rejected were lost from tracking. The system would show "order placed" but never update the database with the rejection status, leaving orders in a pending state indefinitely.

### Root Cause
1. **No immediate status sync**: After placing an order, the system did not immediately fetch the order status from the broker to check if it was rejected.
2. **Missing order ID tracking**: The `db_order_id` was not consistently propagated to the tracking system, so when rejection was detected, the system couldn't find the DB row to update.

### Expected Behavior
1. After placing an order, immediately fetch order status from broker
2. If order is rejected, mark it as `REJECTED` in database with rejection reason
3. If order is pending, mark it as `PENDING_EXECUTION` in database
4. All order statuses should be visible in UI

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

1. **Added `_sync_order_status_snapshot()` method**:
   - Immediately fetches order status from broker after placement
   - Updates database with current status (REJECTED, CANCELLED, EXECUTED, PENDING_EXECUTION)
   - Handles edge cases (order not found, DB order not found, empty status)

2. **Integrated into `_attempt_place_order()`**:
   - After successful order placement, calls `_sync_order_status_snapshot()`
   - Ensures database reflects broker's initial response immediately

### Test Coverage
- `tests/unit/kotak/test_sync_order_status_snapshot.py` - 12 tests covering all status scenarios
- Tests cover: rejected, executed, cancelled, pending, partially filled, empty status, order not found, DB order not found, exception handling, fallback scenarios

### Impact
- All orders are now properly tracked in database
- Rejected orders are immediately marked as REJECTED with rejection reason
- Orders visible in UI with correct status
- Prevents orders from being lost in pending state

---

## Bug #63: Manual AMO Orders Not Detected (HIGH)

**Date Fixed**: November 22, 2025
**Status**: ✅ Fixed

### Description
When users manually placed AMO orders outside the system, the system would still attempt to place new orders or retry orders for the same symbol, leading to duplicate orders. The system had no way to detect manual orders and link them to database records.

### Root Cause
1. **No manual order detection**: System did not check for existing AMO orders before placing new orders
2. **No linking mechanism**: When manual orders were detected, they were not linked to database records

### Expected Behavior
1. Before placing new order, check for manual AMO orders
2. If manual order exists, skip placing new order and update DB with manual order details
3. Before retrying order, check for manual AMO orders
4. If manual order exists, link it to DB record and update status to PENDING_EXECUTION

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

1. **Added `_check_for_manual_orders()` method**:
   - Checks for pending AMO orders from broker that are not in our database
   - Returns manual orders with details (order_id, quantity, price)
   - Distinguishes between manual orders and system orders

2. **Added `_should_skip_retry_due_to_manual_order()` method**:
   - Determines if retry should be skipped based on manual order quantity
   - Handles edge cases (similar qty, larger qty, exact match)

3. **Integrated into `place_new_entries()`**:
   - Before placing new order, checks for manual orders
   - If found, creates/updates DB record with manual order details
   - Skips placing new order

4. **Integrated into `retry_pending_orders_from_db()`**:
   - Before retrying, checks for manual orders
   - If found, links manual order to DB record and updates status to PENDING_EXECUTION
   - Skips retry attempt

### Test Coverage
- `tests/unit/kotak/test_manual_order_detection.py` - 6 tests covering detection and integration
- `tests/unit/kotak/test_manual_order_detection_edge_cases.py` - 10 tests covering edge cases
- Tests cover: detection, system vs manual distinction, integration with place_new_entries, integration with retry, exception handling, non-BUY orders, different symbols, missing order ID

### Impact
- Prevents duplicate orders when manual orders exist
- Manual orders are properly tracked in database
- Seamless integration of manual and system orders
- Better user experience

---

## Bug #64: Capital Not Recalculated on Retry (MEDIUM)

**Date Fixed**: November 22, 2025
**Status**: ✅ Fixed

### Description
When capital was modified before retry, the system would retry with the old quantity instead of recalculating based on the new capital. This led to incorrect order sizes when capital was increased or decreased between order placement and retry.

### Root Cause
1. **Fixed quantity in retry**: System used the original quantity from the failed order
2. **No capital recalculation**: Did not recalculate execution capital and quantity based on current strategy config

### Expected Behavior
1. Before retrying, recalculate execution capital based on current strategy config
2. Recalculate quantity based on new capital and current price
3. Adapt to changes in user_capital config
4. Adapt to changes in stock price

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Modified `retry_pending_orders_from_db()` method**:
- Before retrying, calls `_calculate_execution_capital()` with current ticker, price, and volume
- Recalculates quantity: `qty = max(config.MIN_QTY, floor(execution_capital / close))`
- Adapts to changes in capital and price before retry

### Test Coverage
- `tests/unit/kotak/test_capital_recalculation_on_retry.py` - 4 tests covering all scenarios
- Tests cover: capital increased, capital decreased, price change, combined capital and price changes

### Impact
- Orders retry with correct quantity based on current capital
- Adapts to capital modifications before retry
- Adapts to price changes before retry
- More accurate order sizes

---

## Bug #65: Reentry Incorrectly Blocked When Holdings Exist (HIGH)

**Date Fixed**: November 22, 2025
**Status**: ✅ Fixed

### Description
The reentry logic was incorrectly blocking reentries when the user already had holdings for the symbol. Reentry should be allowed when holdings exist (for averaging down), and should only be blocked if there's an active pending buy order.

### Root Cause
The reentry logic checked `has_holding()` and skipped reentry if holdings existed. This was incorrect because:
1. Reentry is meant to add more shares to existing positions (averaging down)
2. Having holdings is not a reason to block reentry
3. Only active buy orders should block reentry (to prevent duplicates)

### Expected Behavior
1. Reentry should be allowed when holdings exist (for averaging down)
2. Reentry should only be blocked if there's an active pending buy order
3. Reentry should proceed if no active buy order exists, even if holdings exist

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Modified `evaluate_reentries_and_exits()` method**:
- Changed duplicate protection from `if self.has_holding(symbol)` to `if self.has_active_buy_order(symbol)`
- Added comment: "Having holdings is OK for reentry - reentry is meant to add more shares (averaging down)"
- Only checks for active buy orders to prevent duplicate orders

### Test Coverage
- `tests/unit/kotak/test_reentry_logic_fix.py` - 4 tests covering all scenarios
- Tests cover: reentry allowed when holding exists, reentry blocked when active buy order exists, reentry allowed even with holdings at RSI 30, logic verification

### Impact
- Reentry works correctly for averaging down
- Users can add more shares to existing positions
- Prevents duplicate orders (active buy order check)
- Aligns with mean reversion strategy

---

## Bug #66: Average Price Not Recalculated on Reentry (MEDIUM)

**Date Fixed**: November 22, 2025
**Status**: ✅ Fixed

### Description
When reentries were added to a position, the average entry price in trade history was not recalculated. The system updated the quantity but kept the old entry price, leading to incorrect average price calculations.

### Root Cause
The trade history update only updated quantity and added reentry metadata, but did not recalculate the weighted average entry price:
- Formula: `(prev_avg * prev_qty + new_price * new_qty) / total_qty`
- System was missing this recalculation step

### Expected Behavior
1. When reentry is added, recalculate weighted average entry price
2. Formula: `(old_entry_price * old_qty + reentry_price * reentry_qty) / new_total_qty`
3. Update both quantity and entry_price in trade history
4. Preserve initial_entry_price for tracking

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Modified `evaluate_reentries_and_exits()` method**:
- Added average price recalculation when updating trade history
- Formula: `new_avg_price = ((old_entry_price * old_qty) + (price * qty)) / new_total_qty`
- Updates both `entry_price` and `qty` in trade history
- Handles edge cases (invalid data, first entry)

### Test Coverage
- `tests/unit/infrastructure/test_avg_price_calculation_with_reentries.py` - 5 tests covering all scenarios
- `tests/integration/test_avg_price_recalculation_on_reentry.py` - 3 tests covering integration
- Tests cover: single reentry, multiple reentries, formula verification, reentry at higher price

### Impact
- Accurate average price calculations in trade history
- Correct P&L calculations
- Better position tracking
- Accurate reporting

---

## Bug #67: Duplicate Orders Created When Buy Order Service Runs Multiple Times (HIGH)

**Date Fixed**: November 22, 2025
**Status**: ✅ Fixed

### Description
When the buy order service was run multiple times (manually or via scheduled tasks), duplicate entries were being created in the orders table for the same stock. This occurred because the system only checked the broker API for pending orders, which might not return orders immediately after placement (sync delay), or might be unavailable.

### Root Cause
1. **No database check before placing orders**: `place_new_entries()` only checked the broker API via `has_active_buy_order()`, which didn't check the database for existing AMO/PENDING_EXECUTION orders.
2. **Broker API sync delay**: When an order was placed and saved to the database with AMO status, the broker API might not immediately return it in `get_pending_orders()`, causing subsequent service runs to create duplicate orders.
3. **Incomplete duplicate prevention**: The `has_active_buy_order()` method only checked the broker API and didn't have a database fallback.

### Expected Behavior
1. Before placing a new order, check the database for existing AMO/PENDING_EXECUTION/ONGOING orders for the same symbol.
2. If an order exists in the database, skip placing a new order to prevent duplicates.
3. Check the database first (most reliable), then fallback to broker API check.

### Fix Applied
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

1. **Enhanced `has_active_buy_order()` method**:
   - Added database fallback to check for AMO/PENDING_EXECUTION/ONGOING orders
   - Checks broker API first, then falls back to database check
   - Prevents duplicates when broker API doesn't return pending orders

2. **Enhanced `place_new_entries()` method**:
   - Added explicit database check BEFORE placing orders
   - Checks database first (most reliable source) for existing AMO/PENDING_EXECUTION/ONGOING orders
   - If database has an order, skips placing new order (prevents duplicate)
   - If database doesn't have order but broker API has one, cancels and replaces (normal behavior)
   - If neither has order, proceeds with placing new order

**Logic Flow**:
1. Check database for existing AMO/PENDING_EXECUTION/ONGOING orders
2. If found → Skip placing new order (prevent duplicate)
3. If not found → Check broker API for pending orders
4. If broker has pending order → Cancel and replace (normal behavior)
5. If neither has order → Proceed with placing new order

### Test Coverage
- `tests/unit/kotak/test_duplicate_prevention_multiple_runs.py` - 5 tests covering all scenarios
- Tests cover: database check for existing orders, broker API check, skipping when order exists, allowing when no order exists, handling PENDING_EXECUTION orders

### Impact
- Prevents duplicate orders when service runs multiple times
- Prevents duplicates when broker API has sync delays
- More reliable duplicate prevention using database as source of truth
- Better user experience - no duplicate entries in orders table

---

## Bug #68: Order Status Set to CLOSED Instead of CANCELLED When Parameters Change (MEDIUM)

**Date Fixed**: November 22, 2025
**Status**: ✅ Fixed

### Description
When an existing order's quantity or price changed (e.g., user updated capital per trade config or market price changed), the system would cancel the existing order and place a new one with updated parameters. However, the existing order's status was set to `CLOSED` instead of `CANCELLED`, which was incorrect since the order was cancelled due to parameter changes, not executed or naturally closed.

Additionally, the system only handled `AMO` and `PENDING_EXECUTION` orders for parameter updates. Orders with `FAILED`, `RETRY_PENDING`, or `REJECTED` status were not being updated when parameters changed, even though these orders could still be modified.

### Root Cause
1. **Incorrect status for cancelled orders**: When an order was replaced due to parameter changes, its status was set to `CLOSED` instead of `CANCELLED`.
2. **Missing CANCELLED status**: The `OrderStatus` enum did not have a `CANCELLED` status.
3. **Limited status handling**: Only `AMO` and `PENDING_EXECUTION` orders were handled for parameter updates, excluding `FAILED`, `RETRY_PENDING`, and `REJECTED` orders.

### Expected Behavior
1. When an order is replaced due to quantity or price changes, its status should be set to `CANCELLED` (not `CLOSED`).
2. The `CANCELLED` status should be added to the `OrderStatus` enum.
3. Orders with `AMO`, `PENDING_EXECUTION`, `FAILED`, `RETRY_PENDING`, or `REJECTED` status should be cancellable and replaceable when parameters change.
4. Orders with `ONGOING`, `CLOSED`, or `CANCELLED` status should be skipped (cannot be modified).

### Fix Applied
**Files**:
- `src/infrastructure/db/models.py`
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`

1. **Added `CANCELLED` status to `OrderStatus` enum**:
   ```python
   class OrderStatus(str, Enum):
       # ... existing statuses ...
       CANCELLED = "cancelled"
   ```

2. **Updated `place_new_entries()` method**:
   - Changed status from `CLOSED` to `CANCELLED` when order is replaced due to parameter changes
   - Added `FAILED`, `RETRY_PENDING`, and `REJECTED` to the list of cancellable statuses
   - Set `cancelled_reason` to "Order cancelled due to parameter update (qty/price changed)"
   - Added logic to skip `ONGOING`, `CLOSED`, and `CANCELLED` orders (cannot be modified)

3. **Updated order cancellation logic**:
   - Orders are marked as `CANCELLED` (not `CLOSED`) when replaced due to parameter changes
   - Cancellation reason is properly stored in `cancelled_reason` field

### Test Coverage
- `tests/unit/kotak/test_cancelled_status_on_order_update.py` - 10 tests covering all scenarios
- Tests cover:
  - AMO order marked as CANCELLED when quantity changes
  - PENDING_EXECUTION order marked as CANCELLED when price changes
  - FAILED order marked as CANCELLED when parameters change
  - RETRY_PENDING order marked as CANCELLED when parameters change
  - REJECTED order marked as CANCELLED when parameters change
  - ONGOING order NOT cancelled (already executed, skipped)
  - CLOSED order NOT cancelled (already finalized, skipped)
  - Already CANCELLED order NOT updated (skipped)
  - Order NOT cancelled when quantity and price unchanged
  - Cancellation reason properly set

### Impact
- Correct order status tracking (CANCELLED vs CLOSED)
- Proper handling of all cancellable order statuses
- Better order history and audit trail
- More accurate order state management

### Migration Notes
- **No migration required**: Since we're using SQLite and enums are stored as strings, the new `CANCELLED` status value will work without a database migration. However, for PostgreSQL deployments, a migration would be needed to add the enum value.

---

## Bug #69: CLOSED and CANCELLED Orders Blocking New Buy Opportunities (HIGH)

**Date Fixed**: November 22, 2025
**Status**: ✅ Fixed

### Description
When a stock was successfully bought and sold (order status = `CLOSED`), and later got a new buy opportunity, the system would incorrectly skip placing the new order because it found the old `CLOSED` order in the database. Similarly, `CANCELLED` orders were also blocking new buy opportunities.

### Root Cause
1. **CLOSED/CANCELLED orders included in active order check**: The initial database check for existing orders included `CLOSED` and `CANCELLED` statuses, treating them as "active" orders that could block new opportunities.
2. **Incorrect else block logic**: The `else` block assumed all non-updatable orders were `ONGOING`, but it was also catching `CLOSED` and `CANCELLED` orders and incorrectly skipping them.

### Expected Behavior
1. `CLOSED` orders (completed trades) should NOT block new buy opportunities - they represent historical completed trades.
2. `CANCELLED` orders should NOT block new buy opportunities - they represent cancelled orders that should allow new attempts.
3. Only active orders (`AMO`, `PENDING_EXECUTION`, `ONGOING`, `FAILED`, `RETRY_PENDING`, `REJECTED`) should be considered when checking for duplicates.
4. A stock that was previously bought and sold should be able to be bought again when a new opportunity arises.

### Fix Applied
**Files**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- `tests/unit/kotak/test_cancelled_status_on_order_update.py`

1. **Removed CLOSED and CANCELLED from active order check**:
   - Removed `DbOrderStatus.CLOSED` and `DbOrderStatus.CANCELLED` from the initial database check
   - Added comments explaining that CLOSED/CANCELLED orders represent completed/cancelled trades and should NOT block new opportunities

2. **Fixed else block logic**:
   - Changed `else:` to `elif existing_db_order.status == DbOrderStatus.ONGOING:` to explicitly check for ONGOING status
   - Added comment explaining that CLOSED/CANCELLED orders should allow new order placement

3. **Updated tests**:
   - Renamed and updated `test_closed_order_allows_new_buy_opportunity` to verify CLOSED orders allow new buy opportunities
   - Renamed and updated `test_cancelled_order_allows_new_buy_opportunity` to verify CANCELLED orders allow new buy opportunities

### Test Coverage
- `tests/unit/kotak/test_cancelled_status_on_order_update.py` - Updated 2 tests
- Tests verify:
  - CLOSED orders (completed trades) allow new buy opportunities
  - CANCELLED orders allow new buy opportunities
  - Historical orders don't block new opportunities

### Impact
- Stocks can be re-entered after previous trades are completed
- Better support for re-entry strategies (mean reversion)
- More accurate duplicate prevention (only active orders are checked)
- Improved user experience - no false blocking of legitimate new opportunities

### Order Status Behavior Summary

**All OrderStatus enum values and their behavior in `place_new_entries()`:**

| Status | Side | Behavior | Reason |
|--------|------|----------|--------|
| `AMO` | buy | Checked for duplicates, can be updated/cancelled if params change | Active pending order |
| `PENDING_EXECUTION` | buy | Checked for duplicates, can be updated/cancelled if params change | Active pending order |
| `ONGOING` | buy | Checked, skipped (position exists, cannot update) | Already executed |
| `FAILED` | buy | Checked for duplicates, can be updated/cancelled if params change | Can be retried with new params |
| `RETRY_PENDING` | buy | Checked for duplicates, can be updated/cancelled if params change | Can be retried with new params |
| `REJECTED` | buy | Checked for duplicates, can be updated/cancelled if params change | Can be retried with new params |
| `CLOSED` | buy | **NOT checked** - allows new buy opportunity | Completed trade, historical record |
| `CANCELLED` | buy | **NOT checked** - allows new buy opportunity | Cancelled order, historical record |
| `SELL` | sell | **NOT checked** - excluded by `side == "buy"` filter | Only for sell orders, irrelevant for buy placement |

**Key Points:**
1. Only `side == "buy"` orders are checked (sell orders are irrelevant)
2. Active orders (`AMO`, `PENDING_EXECUTION`, `FAILED`, `RETRY_PENDING`, `REJECTED`) can be updated if quantity/price changes
3. `ONGOING` orders are skipped (already executed, position exists)
4. `CLOSED` and `CANCELLED` orders don't block new opportunities (historical records)
5. `SELL` status is only for sell orders and is excluded by the side filter

---

---

## Bug #71: Order Status Simplification and Unified Reason Field (ENHANCEMENT)

**Date Fixed**: November 23, 2025
**Status**: ✅ Fixed

### Description
The system had 9 order statuses (`AMO`, `PENDING_EXECUTION`, `ONGOING`, `SELL`, `CLOSED`, `FAILED`, `RETRY_PENDING`, `REJECTED`, `CANCELLED`) which created complexity and confusion. Additionally, reason information was scattered across multiple fields (`failure_reason`, `rejection_reason`, `cancelled_reason`). This enhancement simplifies the status system to 5 statuses and introduces a unified `reason` field.

### Root Cause
1. **Status proliferation**: Multiple statuses represented similar states (e.g., `AMO` and `PENDING_EXECUTION` both meant pending orders)
2. **Status confusion**: `RETRY_PENDING` and `REJECTED` were both failure states but treated differently
3. **SELL status redundancy**: `SELL` status was redundant since `side='sell'` column already distinguishes sell orders
4. **Scattered reason fields**: Failure, rejection, and cancellation reasons were stored in separate fields, making it difficult to track order history

### Expected Behavior
1. **Simplified statuses**: 5 statuses instead of 9:
   - `PENDING` (merged: `AMO` + `PENDING_EXECUTION`)
   - `ONGOING` (unchanged)
   - `CLOSED` (unchanged)
   - `FAILED` (merged: `FAILED` + `RETRY_PENDING` + `REJECTED`)
   - `CANCELLED` (unchanged)
2. **Unified reason field**: Single `reason` field replaces `failure_reason`, `rejection_reason`, `cancelled_reason`
3. **Side column for sell orders**: Use `side='sell'` instead of `SELL` status
4. **Retry filtration**: All `FAILED` orders are retriable until expiry (next trading day market close)

### Fix Applied

**1. Database Schema Changes**:
- Added `reason` column (String(512), nullable) to `orders` table
- Migrated existing reason data to unified field
- Created migration script: `873e86bc5772_order_status_simplification_and_unified_reason`

**2. Status Migration**:
- `AMO` → `PENDING`
- `PENDING_EXECUTION` → `PENDING`
- `RETRY_PENDING` → `FAILED`
- `REJECTED` → `FAILED`
- `SELL` → `PENDING` (for orders with `side='sell'`)

**3. Repository Updates**:
- Updated `create_amo()` to set `status='pending'` and `reason`
- Updated `mark_failed()` to always use `FAILED` status and unified `reason` field
- Updated `mark_rejected()` to use `FAILED` status with `reason="Broker rejected: {reason}"`
- Updated `mark_cancelled()` to use unified `reason` field
- Updated `mark_executed()` to set `reason="Order executed at Rs {price}"`
- Implemented `get_retriable_failed_orders()` with expiry filtering

**4. Business Logic Updates**:
- Updated `AutoTradeEngine` to use new statuses
- Updated `OrderTracker` to use new statuses
- Updated sell order logic to use `side='sell'` instead of `SELL` status
- Implemented expiry logic using `get_next_trading_day_close()`

**5. API Updates**:
- Updated `GET /api/v1/user/orders` to accept new statuses
- Updated `POST /api/v1/user/orders/{id}/retry` to work with `FAILED` status
- Updated response schema to include unified `reason` field

**6. Frontend Updates**:
- Updated `OrdersPage` to show 5 tabs (Pending, Ongoing, Failed, Closed, Cancelled)
- Updated order status types and filters
- Updated reason field display

**7. Retry Filtration Logic**:
- No max retry count
- Expiry: Next trading day market close (excluding weekends/holidays)
- Expired orders automatically marked as `CANCELLED`
- All `FAILED` orders are retriable until expiry

### Test Coverage
- ✅ 1820 unit tests passing
- ✅ UI tests passing (OrdersPage verified)
- ✅ New tests for expiry filtering (14 tests)
- ✅ New tests for trading day utilities (9 tests)
- ✅ All order status transition tests updated

### Impact
- ✅ Simplified order status system (9 → 5 statuses)
- ✅ Unified reason field for better tracking
- ✅ Improved retry logic with expiry handling
- ✅ Better user experience with clearer status labels
- ✅ Reduced complexity in codebase
- ✅ Backward compatibility maintained (legacy reason fields retained)

### Related Documentation
- `documents/implementation/ORDER_STATUS_SIMPLIFICATION_IMPLEMENTATION.md`
- `documents/implementation/ORDER_STATUS_SIMPLIFICATION_PHASE_WISE_PLAN.md`
- `documents/analysis/ORDER_STATUS_SIMPLIFICATION_IMPACT_ANALYSIS.md`
- `documents/architecture/RETRY_FILTRATION_LOGIC.md`
- `documents/deployment/ORDER_STATUS_SIMPLIFICATION_DEPLOYMENT.md`

---

*Last Updated: November 23, 2025*
