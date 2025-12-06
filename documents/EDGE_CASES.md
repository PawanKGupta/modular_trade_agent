# Edge Cases in Trading Flow

**Date Created**: 2025-01-22
**Status**: ⚠️ Identified - Needs Resolution

---

## Overview

This document identifies edge cases in the current trading flow that could lead to incorrect order placement, quantity mismatches, or data inconsistencies.

---

## Edge Case #1: Sell Order Quantity Not Updated After Reentry

**Severity**: 🔴 **CRITICAL**
**Status**: ✅ **FIXED** (2025-01-22)

### Problem

When a reentry order executes (averaging down), the positions table is updated with the new total quantity, but existing sell orders are **not updated** to reflect the increased quantity.

### Current Flow (Before Fix)

```
Day 1: Initial Entry
  - Buy: 35 shares @ Rs 9.00
  - Positions table: quantity=35
  - Sell order placed: 35 shares @ Rs 9.50 ✅

Day 2: Reentry Executes
  - Buy: 10 shares @ Rs 9.50
  - Positions table updated: quantity=45 ✅
  - Sell order: Still 35 shares ❌ (NOT UPDATED!)

Day 3: run_at_market_open() runs
  - Checks existing sell order: 35 shares
  - Current position: 45 shares
  - existing["qty"] != qty → Doesn't match
  - Skips placing new order (line 1451)
  - But doesn't update existing order! ❌
```

### Impact

- **Partial position exits**: Only original quantity sold, remaining shares not tracked
- **Incomplete trade execution**: Shares remain unsold
- **Data inconsistency**: Positions table shows 45, but sell order shows 35
- **Lost profit opportunity**: Remaining shares not sold at target price

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 1449-1520
- **Method**: `run_at_market_open()`

### Solution

1. **Immediate update when reentry executes**: When a reentry order executes during market hours, `UnifiedOrderMonitor._create_position_from_executed_order()` now checks for existing sell orders and updates them immediately.
2. **Next-day update in `run_at_market_open()`**: When `run_at_market_open()` detects an existing sell order with quantity less than current position quantity, it updates the order instead of skipping.

### Implementation

**Fixed on**: 2025-01-22

**Changes Made**:

1. **Updated `run_at_market_open()` in `sell_engine.py`**:
   - Added logic to detect when existing sell order quantity is less than current position quantity
   - Calls `update_sell_order()` to modify the broker order with new quantity
   - Handles quantity decrease gracefully (might indicate partial sell)
   - Keeps same price when updating quantity

2. **Updated `_create_position_from_executed_order()` in `unified_order_monitor.py`**:
   - After updating position quantity (reentry scenario), checks for existing sell orders
   - Updates sell order immediately with new quantity if found
   - Handles errors gracefully (logs warning, order will be updated next day)

**Files Modified**:
- `modules/kotak_neo_auto_trader/sell_engine.py` - Updated `run_at_market_open()` to update existing orders
- `modules/kotak_neo_auto_trader/unified_order_monitor.py` - Added sell order update logic in `_create_position_from_executed_order()`

**Test Files**:
- `tests/unit/kotak/test_sell_engine_edge_case_1.py` - Tests for `run_at_market_open()` updates
- `tests/unit/kotak/test_unified_order_monitor_edge_case_1.py` - Tests for immediate updates on reentry execution

### Related Code

- `evaluate_reentries_and_exits()` has similar logic to update sell orders (lines 4863-4933)
- `update_sell_order()` method handles order modification via `modify_order()` API

---

## Edge Case #2: Partial Execution Reconciliation

**Severity**: 🟡 **MEDIUM**
**Status**: ✅ **FIXED** (2025-12-06)

### Problem

When reconciling orders that executed while service was down, the code uses **order quantity from DB** instead of **actual filled quantity from broker**. This can cause incorrect position updates if partial execution occurred.

### Current Flow (Before Fix)

```
Order placed: 10 shares
Partial execution: Only 7 shares executed (fldQty=7)
Service down during execution
Service restarts:
  - Reconciliation finds order in holdings
  - Uses order_qty = 10 (from DB) ❌
  - Should use fldQty = 7 (from broker) ✅
  - Position updated with wrong quantity: 10 instead of 7
```

### Impact

- **Incorrect position quantity**: Positions table shows more shares than actually owned
- **Sell order quantity mismatch**: Sell orders try to sell more than available
- **Data inconsistency**: Positions table doesn't match broker holdings

### Code Location

- **File**: `modules/kotak_neo_auto_trader/unified_order_monitor.py`
- **Lines**: 189-266 (new method), 320-500 (reconciliation logic), 568-594 (status update)
- **Method**: `check_buy_order_status()` - Reconciliation logic

### Solution

Implemented priority-based fallback logic to extract actual filled quantity (`fldQty`) from broker APIs:

1. **Priority 1**: `fldQty` from `order_report()` (same-day orders)
2. **Priority 2**: `fldQty` from `order_history()` (historical orders)
3. **Priority 3**: Holdings quantity (actual broker position)
4. **Priority 4**: DB order quantity (last resort)

### Implementation

**Fixed on**: 2025-12-06

**Changes Made**:

1. **Added `_get_filled_quantity_from_order_history()` method**:
   - Extracts `fldQty` from `order_history()` API response
   - Handles nested response structure: `response["data"]["data"]`
   - Finds latest "complete" entry (highest `updRecvTm`)
   - Returns `filled_qty` and `execution_price`

2. **Updated reconciliation logic in `check_buy_order_status()`**:
   - Implements priority order for execution quantity extraction
   - Uses `fldQty` from `order_report()` when order is found
   - Falls back to `order_history()` if not in `order_report()`
   - Falls back to holdings quantity if not in history
   - Falls back to DB quantity as last resort
   - Logs which source was used for reconciliation

3. **Updated `_update_buy_order_status()` method**:
   - Uses `fldQty` (filled quantity) instead of order quantity
   - Handles partial execution correctly

4. **Updated `_handle_buy_order_execution()` method**:
   - Uses `fldQty` when available (handles partial execution)
   - Falls back to order quantity if `fldQty` not available

**Files Modified**:
- `modules/kotak_neo_auto_trader/unified_order_monitor.py` - Added priority-based reconciliation logic

**Test Files**:
- `tests/unit/kotak/test_unified_order_monitor_edge_case_2.py` - Comprehensive tests for partial execution reconciliation

### Broker API Response

From `client.order_report()` and `client.order_history()`, the `fldQty` field indicates filled quantity:
```json
{
    "fldQty": 7,  // Actual filled quantity
    "qty": 10,    // Order quantity
    "avgPrc": "9.50"  // Average execution price
}
```

**Note**: `order_history()` response has nested structure: `response["data"]["data"]` contains the orders array.

---

## Edge Case #3: Manual Holdings Not Reflected in Sell Orders

**Severity**: 🟡 **MEDIUM**
**Status**: ⚠️ **Not Fixed**

### Problem

If user has manual holdings (bought outside the system) that are not in the positions table, sell orders use positions table quantity which is **less than actual holdings**. This causes selling less than what's actually owned.

### Current Flow

```
Manual holdings: 10 shares (bought manually, not tracked)
System holdings: 35 shares (tracked in positions table)
Total broker holdings: 45 shares

Sell order placement:
  - get_open_positions() reads from positions table
  - Gets qty = 35 (from positions table) ❌
  - Should use qty = 45 (from broker holdings) ✅
  - Places sell order for 35 shares
  - Result: Only 35 shares sold, 10 shares remain unsold
```

### Impact

- **Partial position exits**: Not selling all available shares
- **Remaining shares not tracked**: Manual holdings remain unsold
- **Lost profit opportunity**: Shares not sold at target price

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 400-461
- **Method**: `get_open_positions()`

### Current Code

```python
def get_open_positions(self) -> list[dict[str, Any]]:
    """
    Get all open positions from database (positions table).
    Database-only: No file fallback. Uses positions table as single source of truth.
    """
    positions = self.positions_repo.list(self.user_id)
    for pos in positions:
        if pos.closed_at is None:
            open_positions.append({
                "qty": pos.quantity,  # ❌ Uses positions table quantity only
                # ...
            })
```

### Solution

1. **Reconcile with broker holdings** before placing sell orders
2. **Use broker holdings quantity** if it's greater than positions table
3. **Update positions table** to match broker holdings (or track separately)

---

## Edge Case #4: Holdings vs Positions Mismatch

**Severity**: 🟡 **MEDIUM**
**Status**: ⚠️ **Not Fixed**

### Problem

If positions table has different quantity than broker holdings (due to reconciliation issues, manual trades, or data inconsistencies), sell orders use positions table quantity which might be **incorrect**.

### Scenarios

1. **Manual sell executed**: User manually sold 5 shares
   - Broker holdings: 30 shares
   - Positions table: 35 shares (not updated)
   - Sell order uses: 35 shares ❌ (tries to sell more than available)

2. **Reconciliation failure**: Reconciliation didn't update positions table correctly
   - Broker holdings: 45 shares
   - Positions table: 35 shares (stale)
   - Sell order uses: 35 shares ❌ (sells less than available)

3. **Partial execution not tracked**: Partial execution not properly recorded
   - Broker holdings: 7 shares
   - Positions table: 10 shares (full order quantity)
   - Sell order uses: 10 shares ❌ (tries to sell more than available)

### Impact

- **Order rejection**: Sell order rejected due to insufficient quantity
- **Incomplete exits**: Not selling all available shares
- **Data inconsistency**: Positions table doesn't match reality

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 400-461, 509-560
- **Methods**: `get_open_positions()`, `place_sell_order()`

### Solution

1. **Validate positions table against broker holdings** before placing sell orders
2. **Use broker holdings quantity** as source of truth
3. **Update positions table** to match broker holdings if mismatch detected
4. **Add reconciliation check** in `run_at_market_open()`

---

## Edge Case #5: Reentry Order Edge Case - Quantity Mismatch

**Severity**: 🟡 **MEDIUM**
**Status**: ⚠️ **Not Fixed**

### Problem

If a reentry order executes while service is down, reconciliation uses **order quantity from DB** instead of checking if partial execution occurred or if holdings quantity matches.

### Current Flow

```
Day 1: Reentry order placed: 10 shares
Day 2: Service down, order executes: 10 shares
Day 3: Service restarts:
  - Reconciliation finds order in holdings
  - Uses order_qty = 10 (from DB) ✅ (correct in this case)
  - But what if partial execution? ❌
  - Or what if holdings quantity doesn't match? ❌
```

### Impact

- **Incorrect position update**: If partial execution, position updated with wrong quantity
- **Quantity mismatch**: Positions table doesn't match actual holdings

### Code Location

- **File**: `modules/kotak_neo_auto_trader/unified_order_monitor.py`
- **Lines**: 326-337
- **Method**: `check_buy_order_status()` - Reconciliation logic

### Solution

1. **Check `fldQty` from broker** (if available) for actual filled quantity
2. **Compare with holdings quantity** to detect discrepancies
3. **Use actual filled quantity** instead of order quantity

---

## Edge Case #6: Sell Order Update Timing

**Severity**: 🟠 **LOW**
**Status**: ⚠️ **Not Fixed**

### Problem

If reentry executes and position is updated, but `run_at_market_open()` runs **before the position update completes**, it might use old quantity for sell order placement.

### Current Flow

```
Time T1: Reentry order executes
Time T2: Position update starts (async)
Time T3: run_at_market_open() runs (before T2 completes)
  - Reads positions table: Still shows old quantity (35) ❌
  - Places sell order: 35 shares ❌
  - Should wait for position update or use broker holdings
```

### Impact

- **Race condition**: Sell order placed with stale quantity
- **Incorrect quantity**: Sell order doesn't reflect latest position

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 1380-1460
- **Method**: `run_at_market_open()`

### Solution

1. **Use broker holdings** as source of truth (not positions table)
2. **Add validation** to ensure positions table is up-to-date
3. **Reconcile before placing sell orders**

---

## Edge Case #7: Existing Sell Order Quantity Check Logic

**Severity**: 🔴 **CRITICAL**
**Status**: ✅ **FIXED** (2025-01-22, as part of Edge Case #1 fix)

### Problem

`run_at_market_open()` only checked if `existing["qty"] == qty`. If quantity changed (due to reentry), it **skipped without updating** the existing order.

### Original Code (Before Fix)

```python
# Check for existing order with same symbol and quantity (avoid duplicate)
if symbol.upper() in existing_orders:
    existing = existing_orders[symbol.upper()]
    if existing["qty"] == qty:
        # Skip - order exists with same quantity ✅
        continue
    # ❌ PROBLEM: If qty changed, skips without updating!
```

### Impact

- **Stale sell orders**: Sell orders don't reflect current position
- **Partial exits**: Only original quantity sold
- **Data inconsistency**: Sell order quantity doesn't match position

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 1449-1523
- **Method**: `run_at_market_open()`

### Solution

This issue was fixed as part of **Edge Case #1** fix. The code now handles all three scenarios:

1. **Same quantity**: Skip (already correct)
2. **Quantity increased**: Update existing sell order with new quantity
3. **Quantity decreased**: Handle gracefully (might indicate partial sell)

### Implementation

**Fixed on**: 2025-01-22 (as part of Edge Case #1)

**Current Code** (After Fix):

```python
if symbol.upper() in existing_orders:
    existing = existing_orders[symbol.upper()]
    existing_qty = existing["qty"]
    existing_price = existing["price"]

    if existing_qty == qty:
        # Same quantity - just track the existing order ✅
        continue
    elif qty > existing_qty:
        # Quantity increased (reentry happened) - update existing order ✅
        self.update_sell_order(
            order_id=existing["order_id"],
            symbol=symbol,
            qty=qty,
            new_price=existing_price  # Keep same price
        )
        continue
    else:
        # Quantity decreased (partial sell or manual adjustment) ✅
        # Handle gracefully - keep existing order, log warning
        continue
```

**Files Modified**:
- `modules/kotak_neo_auto_trader/sell_engine.py` - Updated `run_at_market_open()` to handle all quantity change scenarios

**Related**:
- This fix is part of the same implementation as Edge Case #1
- See Edge Case #1 for complete implementation details and tests

---

## Edge Case #8: Sell Order Execution Doesn't Update Positions Table

**Severity**: 🔴 **CRITICAL**
**Status**: ✅ **FIXED** (2025-01-22)

### Problem

When a sell order executes, the system only marks the position as closed in **trade history JSON** (`mark_position_closed()`), but **does NOT update the positions table** in the database. The `closed_at` field remains `NULL` and `quantity` is not reduced.

### Current Flow

```
Sell order executes: 35 shares @ Rs 9.50
  - mark_position_closed() updates trades_history.json ✅
  - Position marked as "closed" in JSON ✅
  - Positions table: closed_at = NULL ❌ (NOT UPDATED!)
  - Positions table: quantity = 35 ❌ (NOT REDUCED!)
  - Result: Position still appears as "open" in database queries
```

### Impact

- **Position appears open**: Database queries show position as open (`closed_at IS NULL`)
- **Incorrect portfolio view**: Frontend/API shows position as still open
- **Data inconsistency**: Trade history says closed, but positions table says open
- **Reentry logic broken**: System might try to place reentry orders for "closed" positions
- **Sell order placement**: System might try to place another sell order for already-sold position

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 1860-1906
- **Method**: `monitor_and_update()`

### Current Code

```python
if completed_order_info:
    logger.info(f"{symbol} sell order completed - removing from monitoring")
    # Mark position as closed in trade history
    if self.state_manager:
        if self._mark_order_executed(symbol, completed_order_id, order_price):
            symbols_executed.append(symbol)
            logger.info(f"Position closed: {symbol} - removing from tracking")
    elif self.mark_position_closed(symbol, order_price, completed_order_id):
        # ❌ PROBLEM: Only updates trade history JSON, not positions table!
        symbols_executed.append(symbol)
        logger.info(f"Position closed: {symbol} - removing from tracking")
```

### Solution

1. **Update positions table** when sell order executes:
   - Set `closed_at = execution_time`
   - Set `quantity = 0` (or reduce by sold quantity if partial)
2. **Add method to positions_repo**: `mark_closed(user_id, symbol, closed_at, exit_price)`
3. **Call positions_repo.mark_closed()** after `mark_position_closed()`

### Implementation

**Fixed on**: 2025-01-22

**Changes Made**:
1. Added `mark_closed()` method to `PositionsRepository`:
   - Sets `closed_at` timestamp
   - Sets `quantity = 0` for full execution
   - Called when sell order fully executes

2. Added `reduce_quantity()` method to `PositionsRepository`:
   - Reduces position quantity for partial sells
   - Automatically marks as closed if quantity becomes 0
   - Keeps position open if quantity > 0

3. Updated `OrderFieldExtractor`:
   - Separated `get_quantity()` (order quantity) from `get_filled_quantity()` (filled quantity)
   - Enables detection of partial vs full execution

4. Updated `SellOrderManager.monitor_and_update()`:
   - Calls `positions_repo.mark_closed()` for full executions
   - Calls `positions_repo.reduce_quantity()` for partial executions
   - Handles both execution detection paths

**Files Modified**:
- `src/infrastructure/persistence/positions_repository.py` - Added `mark_closed()` and `reduce_quantity()` methods
- `modules/kotak_neo_auto_trader/utils/order_field_extractor.py` - Added `get_filled_quantity()` method
- `modules/kotak_neo_auto_trader/sell_engine.py` - Updated `monitor_and_update()` to update positions table

### Related Code

- `src/infrastructure/persistence/positions_repository.py` - `mark_closed()` and `reduce_quantity()` methods added
- `Positions` model `closed_at` field is now properly set on sell execution

---

## Edge Case #9: Partial Sell Execution Not Handled

**Severity**: 🟡 **MEDIUM**
**Status**: ⚠️ **Not Fixed**

### Problem

If a sell order **partially executes** (e.g., 20 out of 35 shares), the system treats it as **fully executed** and marks the position as closed. The remaining 15 shares are still in holdings but not tracked.

### Current Flow

```
Sell order placed: 35 shares @ Rs 9.50
Partial execution: Only 20 shares executed (fldQty=20)
  - System detects "completed" order
  - Marks position as closed ❌ (should remain open!)
  - Remaining 15 shares: Still in holdings but not tracked ❌
  - Result: Position closed, but 15 shares remain unsold
```

### Impact

- **Position incorrectly closed**: Position marked as closed even though shares remain
- **Remaining shares not tracked**: 15 shares remain unsold and untracked
- **Lost profit opportunity**: Remaining shares not sold at target price
- **Data inconsistency**: Holdings show 15 shares, but position shows closed

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 1864-1886
- **Method**: `monitor_and_update()`

### Current Code

```python
completed_order_info = self.has_completed_sell_order(symbol)
if completed_order_info:
    # ❌ PROBLEM: Treats as fully executed, doesn't check partial fill
    logger.info(f"{symbol} sell order completed - removing from monitoring")
    # Marks position as closed
    if self.mark_position_closed(symbol, order_price, completed_order_id):
        symbols_executed.append(symbol)
```

### Solution

1. **Check `fldQty` vs `qty`** to detect partial execution
2. **If partial**: Update position quantity (reduce by `fldQty`), keep position open
3. **If full**: Mark position as closed
4. **Update sell order quantity** if partial execution detected

### Broker API Response

From `client.order_report()`, check `fldQty` vs `qty`:
```json
{
    "fldQty": 20,  // Actual filled quantity (partial)
    "qty": 35,     // Order quantity
    "stat": "open" // Still open (partial fill)
}
```

---

## Edge Case #10: Position Quantity Not Reduced After Sell

**Severity**: 🔴 **CRITICAL**
**Status**: ✅ **FIXED** (2025-01-22, as part of Edge Case #8 fix)

### Problem

When a sell order executes (fully or partially), the **position quantity in the positions table was NOT reduced**. It remained at the original quantity even though shares were sold.

### Original Flow (Before Fix)

```
Initial position: 35 shares
Sell order executes: 35 shares @ Rs 9.50
  - Trade history: Position marked as "closed" ✅
  - Positions table: quantity = 35 ❌ (NOT REDUCED!)
  - Positions table: closed_at = NULL ❌ (NOT SET!)
  - Result: Position still shows 35 shares in database
```

### Impact

- **Incorrect position quantity**: Database shows wrong quantity
- **Sell order placement**: System might try to place another sell order
- **Portfolio view**: Frontend shows incorrect holdings
- **Data inconsistency**: Positions table doesn't match reality

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 1960-1993
- **Method**: `monitor_and_update()`

### Solution

This issue was fixed as part of **Edge Case #8** fix. The code now properly updates the positions table for both full and partial sell executions.

### Implementation

**Fixed on**: 2025-01-22 (as part of Edge Case #8)

**Current Code** (After Fix):

```python
# Update positions table (Edge Case #8 fix)
if self.positions_repo and self.user_id:
    if filled_qty >= order_qty:
        # Full execution - mark position as closed
        self.positions_repo.mark_closed(
            user_id=self.user_id,
            symbol=base_symbol,
            closed_at=ist_now(),
            exit_price=order_price,
        )
        # Sets quantity = 0 and closed_at ✅
    else:
        # Partial execution - reduce quantity, keep position open
        self.positions_repo.reduce_quantity(
            user_id=self.user_id,
            symbol=base_symbol,
            sold_quantity=float(filled_qty),
        )
        # Reduces quantity, marks closed if quantity becomes 0 ✅
```

**How It Works**:

1. **Full Execution**:
   - Calls `mark_closed()` which sets `quantity = 0` and `closed_at = execution_time`
   - Position is properly marked as closed

2. **Partial Execution**:
   - Calls `reduce_quantity()` which subtracts `sold_quantity` from current quantity
   - If quantity becomes 0, automatically marks as closed
   - If quantity > 0, keeps position open with reduced quantity

**Files Modified**:
- `src/infrastructure/persistence/positions_repository.py` - Added `mark_closed()` and `reduce_quantity()` methods
- `modules/kotak_neo_auto_trader/sell_engine.py` - Updated `monitor_and_update()` to call these methods

**Related**:
- This fix is part of the same implementation as Edge Case #8
- See Edge Case #8 for complete implementation details and tests

---

## Edge Case #11: Reentry Daily Cap Check Discrepancy

**Severity**: 🟡 **MEDIUM**
**Status**: ✅ **FIXED** (2025-01-22)

### Problem

The `reentries_today()` method looked for **separate trade entries** with `entry_type == 'reentry'`, but reentries are actually recorded in the **`reentries` array** within existing trade entries. This meant the daily cap check **didn't work correctly**.

### Original Flow (Before Fix)

```
Day 1: Initial entry at RSI 25
  - Trade entry created: entry_type="initial" ✅

Day 1: Reentry at RSI 18
  - Reentry added to reentries array ✅
  - reentries_today() checks for entry_type=="reentry" ❌
  - Finds 0 reentries (wrong!) ❌
  - Allows another reentry (should block!) ❌

Day 1: Another reentry at RSI 10
  - reentries_today() still finds 0 ❌
  - Allows reentry (should block!) ❌
```

### Impact

- **Daily cap bypassed**: Multiple reentries allowed in same day
- **Risk exposure**: More capital deployed than intended
- **Logic broken**: Daily cap feature doesn't work as designed

### Code Location

- **File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- **Lines**: 1953-1980
- **Method**: `reentries_today()`

### Solution

This issue was fixed by updating `reentries_today()` to check the `reentries` array within trade entries instead of looking for separate entries.

### Implementation

**Fixed on**: 2025-01-22

**Current Code** (After Fix):

```python
def reentries_today(self, base_symbol: str) -> int:
    """
    Count successful re-entries recorded today for this symbol (base symbol).

    Edge Case #11 Fix: Checks the 'reentries' array within trade entries
    instead of looking for separate entries with entry_type == 'reentry'.
    Reentries are stored in the reentries array of existing trade entries.
    """
    try:
        hist = self._load_trades_history()
        trades = hist.get("trades") or []
        today = datetime.now().date()
        cnt = 0
        for t in trades:
            sym = str(t.get("symbol") or "").upper()
            if sym != base_symbol.upper():
                continue
            # ✅ FIX: Check reentries array within the trade
            reentries = t.get("reentries", [])
            for reentry in reentries:
                reentry_time = reentry.get("time")
                if not reentry_time:
                    continue
                try:
                    d = datetime.fromisoformat(reentry_time).date()
                except Exception:
                    try:
                        d = datetime.strptime(reentry_time.split("T")[0], "%Y-%m-%d").date()
                    except Exception:
                        continue
                if d == today:
                    cnt += 1
        return cnt
    except Exception:
        return 0
```

**How It Works**:

1. **Iterates through all trades** for the symbol (not just entries with `entry_type == "reentry"`)
2. **Checks the `reentries` array** within each trade entry
3. **Filters by date** - only counts reentries from today
4. **Handles errors gracefully** - returns 0 on exception

**Files Modified**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Fixed `reentries_today()` method

**Test Files**:
- `tests/unit/kotak/test_reentries_today_edge_case_11.py` - Comprehensive tests for the fix

### Related

- Edge Case #13 (Multiple Reentries Same Day Bypass) is a consequence of this issue and is also fixed by this implementation

---

## Edge Case #12: Sell Order Execution While Reentry Pending

**Severity**: 🟡 **MEDIUM**
**Status**: ⚠️ **Not Fixed**

### Problem

If a sell order executes while a reentry order is still pending, the reentry order should be cancelled, but the position might already be marked as closed. This can lead to:
1. Reentry order executing after position is closed
2. Position reopened with reentry shares
3. Data inconsistency

### Current Flow

```
Time T1: Reentry order placed: 10 shares (pending)
Time T2: Sell order executes: 35 shares (full position)
  - Position marked as closed ✅
  - Reentry order: Still pending ❌ (NOT CANCELLED!)

Time T3: Reentry order executes: 10 shares
  - Position reopened with 10 shares ❌ (shouldn't happen!)
  - Position shows as "open" again ❌
  - Data inconsistency: Position closed then reopened
```

### Impact

- **Position reopened**: Closed position reopened by pending reentry
- **Data inconsistency**: Position closed_at set, then cleared
- **Unexpected behavior**: System might place another sell order
- **Logic confusion**: Position state unclear (closed or open?)

### Code Location

- **File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- **Lines**: 3061-3083
- **Method**: `evaluate_reentries_and_exits()`

### Current Code

```python
# Check if position is closed - cancel re-entry order if closed
if position and position.closed_at is not None:
    # Cancel reentry order
    # ✅ This check exists, but what if position closes AFTER reentry is placed?
```

### Solution

1. **Check position status** before placing reentry order
2. **Cancel pending reentry orders** when sell order executes
3. **Add validation** in reentry placement: Skip if position is closed
4. **Monitor pending reentry orders** and cancel if position closes

---

## Edge Case #13: Multiple Reentries Same Day Bypass

**Severity**: 🟡 **MEDIUM**
**Status**: ⚠️ **Not Fixed**

### Problem

Due to Edge Case #11 (reentry daily cap check discrepancy), multiple reentries can be placed in the same day, bypassing the daily cap of 1 reentry per symbol per day.

### Current Flow

```
Day 1: Initial entry at RSI 25
Day 1: Reentry at RSI 18
  - reentries_today() returns 0 (wrong!) ❌
  - Daily cap check: 0 < 1 → Allows reentry ✅ (should block!)

Day 1: Another reentry at RSI 10
  - reentries_today() still returns 0 ❌
  - Daily cap check: 0 < 1 → Allows reentry ✅ (should block!)

Result: 2 reentries in same day (should be max 1) ❌
```

### Impact

- **Daily cap bypassed**: Multiple reentries allowed
- **Risk exposure**: More capital deployed than intended
- **Feature broken**: Daily cap feature doesn't work

### Code Location

- **File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- **Lines**: 4765-4767
- **Method**: `place_reentry_orders()`

### Current Code

```python
# Daily cap: allow max 1 re-entry per symbol per day
if self.reentries_today(symbol) >= 1:
    logger.info(f"Re-entry daily cap reached for {symbol}; skipping today")
    continue
# ❌ PROBLEM: reentries_today() doesn't work correctly (see Edge Case #11)
```

### Solution

1. **Fix `reentries_today()`** (see Edge Case #11 solution)
2. **Add validation** to ensure daily cap is enforced
3. **Test daily cap** with multiple reentries in same day

---

## Edge Case #14: Manual Partial Sell of System Holdings

**Severity**: 🔴 **CRITICAL**
**Status**: ⚠️ **Not Fixed**

### Problem

If user manually sells **some of the system's holdings** (not all), the positions table is **not updated** to reflect the reduced quantity. The system still thinks it owns the full quantity and tries to place sell orders for more shares than are actually available.

### Current Flow

```
System holdings: 35 shares (tracked in positions table)
User manually sells: 5 shares of system's holdings
Broker holdings: 30 shares (35 - 5)
Positions table: 35 shares (NOT UPDATED!) ❌

Next day: run_at_market_open() runs
  - Reads positions table: qty = 35 ✅
  - Places sell order: 35 shares ❌
  - Broker only has 30 shares
  - Order rejected or partially executed ❌
```

### Impact

- **Order rejection**: Sell order rejected due to insufficient quantity
- **Partial execution**: Order might partially execute (30 shares) but system expects 35
- **Data inconsistency**: Positions table shows 35, but broker only has 30
- **Lost tracking**: System loses track of actual holdings

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 400-461, 1380-1520
- **Methods**: `get_open_positions()`, `run_at_market_open()`

### Solution

1. **Validate against broker holdings** before placing sell orders
2. **Detect manual partial sells** by comparing positions table vs broker holdings
3. **Update positions table** when manual sell detected (reduce quantity)
4. **Use broker holdings quantity** as source of truth for sell orders

### Business Logic Consideration

**Current Logic**: System doesn't interfere with manual holdings
**Issue**: System doesn't detect when manual trades affect **system's own holdings**

**Clarification Needed**:
- Should system detect manual sells of **system holdings**?
- Should system update positions table when manual sell detected?
- Or should system only validate before placing orders (without updating)?

---

## Edge Case #15: Manual Full Sell of System Holdings

**Severity**: 🔴 **CRITICAL**
**Status**: ⚠️ **Not Fixed**

### Problem

If user manually sells **all of the system's holdings**, the positions table still shows the position as **open**. The system tries to place sell orders for shares that no longer exist.

### Current Flow

```
System holdings: 35 shares (tracked in positions table)
User manually sells: 35 shares (all system holdings)
Broker holdings: 0 shares
Positions table: 35 shares, closed_at = NULL (STILL OPEN!) ❌

Next day: run_at_market_open() runs
  - Reads positions table: qty = 35, status = open ✅
  - Places sell order: 35 shares ❌
  - Broker has 0 shares
  - Order rejected ❌
```

### Impact

- **Order rejection**: Sell order rejected (no shares available)
- **Wasted API calls**: System keeps trying to place orders
- **Data inconsistency**: Positions table shows open position, but broker has 0
- **Resource waste**: System monitors non-existent positions

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 400-461, 1380-1520
- **Methods**: `get_open_positions()`, `run_at_market_open()`

### Solution

1. **Detect position closure** by comparing positions table vs broker holdings
2. **Mark position as closed** when broker holdings = 0
3. **Skip sell order placement** for closed positions
4. **Reconcile before placing orders** to detect manual closures

### Business Logic Consideration

**Current Logic**: System doesn't interfere with manual holdings
**Issue**: System doesn't detect when manual trades **close system positions**

**Clarification Needed**:
- Should system detect manual closure of system positions?
- Should system mark positions as closed when broker holdings = 0?
- Or should system only skip orders when holdings = 0 (without updating DB)?

---

## Edge Case #16: Reentry on Mixed Holdings (Average Price Calculation)

**Severity**: 🟡 **MEDIUM**
**Status**: ⚠️ **Not Fixed**

### Problem

If user has manual holdings and system places a reentry, the average price calculation might be incorrect because it doesn't account for manual holdings when calculating the weighted average.

### Current Flow

```
Manual holdings: 10 shares @ Rs 9.00 (bought manually)
System holdings: 35 shares @ Rs 9.00 (tracked in positions table)
Total broker holdings: 45 shares

System places reentry: 10 shares @ Rs 8.50
  - Positions table: Calculates avg_price for system holdings only
  - Formula: (35 * 9.00 + 10 * 8.50) / 45 = Rs 8.94 ✅
  - But broker's actual avg_price might be different if manual holdings have different price
  - Broker avg_price: (10 * 9.00 + 35 * 9.00 + 10 * 8.50) / 55 = Rs 8.95 ❌
```

### Impact

- **Incorrect average price**: Positions table avg_price doesn't match broker's actual avg_price
- **P&L calculation errors**: Unrealized P&L calculations might be wrong
- **Data inconsistency**: Positions table doesn't reflect true cost basis

### Code Location

- **File**: `modules/kotak_neo_auto_trader/unified_order_monitor.py`
- **Lines**: 562-800
- **Method**: `_create_position_from_executed_order()`

### Solution

1. **Use broker holdings avg_price** as source of truth (if available)
2. **Calculate weighted average** considering all holdings (manual + system)
3. **Or track system holdings separately** from manual holdings

### Business Logic Consideration

**Current Logic**: System only tracks its own holdings
**Issue**: Average price calculation doesn't account for manual holdings in the same symbol

**Clarification Needed**:
- Should system use broker's avg_price (includes manual holdings)?
- Or should system track only system holdings' avg_price (current behavior)?
- Is current behavior acceptable (system avg_price separate from broker avg_price)?

---

## Edge Case #17: Sell Order Quantity Validation Missing

**Severity**: 🔴 **CRITICAL**
**Status**: ⚠️ **Not Fixed**

### Problem

The system places sell orders based on positions table quantity **without validating** against broker holdings. If manual trades occurred, the order might be rejected or partially executed.

### Current Flow

```
Positions table: 35 shares
Broker holdings: 30 shares (user manually sold 5)
System places sell order: 35 shares ❌
  - No validation against broker holdings
  - Order might be rejected
  - Or partially executed (30 shares)
  - System expects 35, but only 30 executed
```

### Impact

- **Order rejection**: Sell order rejected due to insufficient quantity
- **Partial execution**: Order partially executes, system doesn't track correctly
- **Data inconsistency**: Positions table shows 35, but only 30 sold
- **Lost profit**: Remaining 5 shares not sold

### Code Location

- **File**: `modules/kotak_neo_auto_trader/sell_engine.py`
- **Lines**: 1380-1520
- **Method**: `run_at_market_open()`

### Solution

1. **Validate quantity against broker holdings** before placing sell orders
2. **Use min(positions_qty, broker_holdings_qty)** for sell order quantity
3. **Update positions table** if broker holdings < positions table
4. **Log warning** when discrepancy detected

### Business Logic Consideration

**Current Logic**: System doesn't interfere with manual holdings
**Issue**: System doesn't validate that it can actually sell the quantity it thinks it owns

**Clarification Needed**:
- Should system validate against broker holdings before placing orders?
- Should system use broker holdings quantity if less than positions table?
- Or should system only place orders and let broker reject if insufficient?

---

## Edge Case #18: Manual Buy of System-Tracked Symbol (Reentry Confusion)

**Severity**: 🟡 **MEDIUM**
**Status**: ⚠️ **Not Fixed**

### Problem

If user manually buys more shares of a symbol the system is tracking, the system might incorrectly treat it as a reentry or might not account for it when calculating reentry levels.

### Current Flow

```
System holdings: 35 shares @ Rs 9.00 (tracked)
User manually buys: 10 shares @ Rs 8.50
Total broker holdings: 45 shares

System checks for reentry:
  - Reads positions table: 35 shares ✅
  - Checks RSI: 18 (below 20, reentry level)
  - Places reentry order: 10 shares @ Rs 8.50
  - But user already manually bought 10 shares!
  - System now owns: 45 shares (35 + 10 reentry)
  - But broker has: 55 shares (35 + 10 manual + 10 reentry) ❌
```

### Impact

- **Quantity mismatch**: System thinks it owns less than it actually does
- **Reentry confusion**: System might place reentry when user already manually bought
- **Average price calculation**: Incorrect if manual buy price differs

### Code Location

- **File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- **Lines**: 4168-5000
- **Method**: `place_reentry_orders()`

### Solution

1. **Reconcile with broker holdings** before placing reentry orders
2. **Detect manual buys** by comparing positions table vs broker holdings
3. **Skip reentry** if holdings already increased (user might have manually bought)
4. **Or update positions table** to include manual buys (if business logic allows)

### Business Logic Consideration

**Current Logic**: System doesn't interfere with manual holdings
**Issue**: System doesn't detect manual buys that might affect reentry decisions

**Clarification Needed**:
- Should system detect manual buys before placing reentry?
- Should system skip reentry if holdings already increased?
- Or should system proceed with reentry regardless of manual buys?

---

## Summary

### Critical Issues (🔴)

1. ~~**Edge Case #1**: Sell order quantity not updated after reentry~~ ✅ **FIXED**
2. ~~**Edge Case #7**: Existing sell order quantity check logic~~ ✅ **FIXED** (as part of Edge Case #1)
3. ~~**Edge Case #8**: Sell order execution doesn't update positions table~~ ✅ **FIXED**
4. ~~**Edge Case #10**: Position quantity not reduced after sell~~ ✅ **FIXED** (as part of Edge Case #8)

### Medium Issues (🟡)

5. ~~**Edge Case #2**: Partial execution reconciliation~~ ✅ **FIXED**
6. **Edge Case #3**: Manual holdings not reflected in sell orders
7. **Edge Case #4**: Holdings vs positions mismatch
8. **Edge Case #5**: Reentry order edge case - quantity mismatch
9. **Edge Case #9**: Partial sell execution not handled
10. ~~**Edge Case #11**: Reentry daily cap check discrepancy~~ ✅ **FIXED**
11. **Edge Case #12**: Sell order execution while reentry pending
12. ~~**Edge Case #13**: Multiple reentries same day bypass~~ ✅ **FIXED** (as part of Edge Case #11)

### Low Issues (🟠)

13. **Edge Case #6**: Sell order update timing

---

## Recommended Fixes Priority

1. **Priority 1 (Critical)**:
   - ~~Fix Edge Case #8: Update positions table when sell order executes~~ ✅ **FIXED**
   - ~~Fix Edge Case #1: Update sell order quantity after reentry~~ ✅ **FIXED**
   - ~~Fix Edge Case #7: Improve existing sell order check logic~~ ✅ **FIXED** (as part of Edge Case #1)
   - Fix Edge Case #10: Reduce position quantity after sell

2. **Priority 2 (Medium)**:
   - Fix Edge Case #14: Detect and handle manual partial sell of system holdings (CRITICAL)
   - Fix Edge Case #15: Detect and handle manual full sell of system holdings (CRITICAL)
   - Fix Edge Case #17: Validate sell order quantity against broker holdings (CRITICAL)
   - Fix Edge Case #4: Validate positions table against broker holdings
   - Fix Edge Case #12: Cancel pending reentry orders when position closes
   - Fix Edge Case #9: Handle partial sell execution
   - Fix Edge Case #18: Handle manual buy of system-tracked symbol
   - Fix Edge Case #16: Reentry on mixed holdings (average price calculation)

3. **Priority 3 (Low)**:
   - Fix Edge Case #3: Reconcile manual holdings
   - Fix Edge Case #5: Improve reentry reconciliation
   - Fix Edge Case #6: Add timing validation

---

## Related Files

- `modules/kotak_neo_auto_trader/sell_engine.py` - Sell order placement
- `modules/kotak_neo_auto_trader/unified_order_monitor.py` - Order reconciliation
- `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Reentry logic
- `modules/kotak_neo_auto_trader/services/order_validation_service.py` - Duplicate checking

---

## Notes

- Some edge cases might be acceptable trade-offs depending on business requirements
- Manual holdings tracking might be intentionally excluded from system tracking
- Partial execution handling might require broker API support for filled quantity
