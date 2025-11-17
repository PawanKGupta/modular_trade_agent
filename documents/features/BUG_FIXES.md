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

*Last Updated: January 2025*
