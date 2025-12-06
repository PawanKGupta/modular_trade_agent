# Order Management Flow - Complete Documentation

**Date**: 2025-12-06
**Status**: ✅ All Edge Cases Fixed
**Version**: Post-Edge-Case-Fixes

---

## Overview

This document describes the complete order management flow after fixing all identified edge cases. The system now handles:

- ✅ Buy order placement and execution (new entries & reentries)
- ✅ Sell order placement and execution
- ✅ Position tracking with database persistence
- ✅ Reentry tracking with full audit trail
- ✅ Manual trade detection and reconciliation
- ✅ Partial execution handling
- ✅ Order status updates with timestamps
- ✅ Sell order quantity updates on reentry
- ✅ Pending reentry cancellation on position closure

---

## Table of Contents

1. [Buy Order Flow](#1-buy-order-flow)
2. [Sell Order Flow](#2-sell-order-flow)
3. [Position Tracking](#3-position-tracking)
4. [Reentry Management](#4-reentry-management)
5. [Manual Trade Reconciliation](#5-manual-trade-reconciliation)
6. [Database Schema](#6-database-schema)
7. [Edge Cases Fixed](#7-edge-cases-fixed)

---

## 1. Buy Order Flow

### 1.1 New Entry Order Placement

**Trigger**: `AutoTradeEngine.place_new_entries()` (4:05 PM daily)

**Flow**:

```
1. Load Buy Recommendations
   └─> Query signals table for BUY/STRONG_BUY signals
   └─> Filter by strategy criteria (RSI, price, chart quality, etc.)

2. Duplicate Check
   └─> OrderValidationService.check_duplicate_order()
   └─> Checks:
       ├─> Broker holdings (via portfolio.get_holdings())
       ├─> Database positions table (open positions)
       └─> Active orders (PENDING/ONGOING status)
   └─> If duplicate found:
       ├─> Skip order placement
       └─> Send Telegram notification (ORDER_SKIPPED)

3. Validation
   └─> Check available balance
   └─> Check portfolio capacity limits
   └─> Validate order quantity

4. Place AMO Order
   └─> Broker API: place_amo_order()
   └─> Get broker_order_id

5. Database Persistence
   └─> OrdersRepository.create_amo()
   └─> Fields set:
       ├─> status = PENDING
       ├─> placed_at = current_time
       ├─> updated_at = current_time
       ├─> entry_type = "entry"
       ├─> order_metadata = {ticker, signal_type, entry_rsi, ...}
       └─> reason = "Order placed - waiting for market open"

6. Order Tracking
   └─> OrderTracker.add_pending_order()
   └─> OrderStateManager.register_buy_order()
   └─> JSON backup (if not db_only_mode)
```

**Database Tables Updated**:
- `orders` table: New row with `status=PENDING`

---

### 1.2 Reentry Order Placement

**Trigger**: `AutoTradeEngine.place_reentry_orders()` (during market hours)

**Flow**:

```
1. Check Reentry Conditions
   └─> Position exists (open position in database)
   └─> RSI drops to reentry level (RSI10 < 30, 25, 20, etc.)
   └─> Price > EMA200 (uptrend filter)
   └─> Daily reentry cap not exceeded (reentries_today() < max_reentries_per_day)

2. Duplicate Check (with allow_reentry=True)
   └─> OrderValidationService.check_duplicate_order(allow_reentry=True)
   └─> Bypasses holdings check (allows reentry for existing positions)
   └─> Still checks for active orders to prevent duplicate reentry orders

3. Place Reentry Order
   └─> Broker API: place_order() (market order during market hours)
   └─> Get broker_order_id

4. Database Persistence
   └─> OrdersRepository.create_amo() or update()
   └─> Fields set:
       ├─> status = PENDING (if AMO) or ONGOING (if market order)
       ├─> entry_type = "reentry"
       ├─> order_metadata = {
           │   reentry_level: int,
           │   reentry_rsi: float,
           │   reentry_price: float,
           │   ...
           │ }
       └─> updated_at = current_time

5. JSON Backup (for archival)
   └─> Update trades_history.json
   └─> Add to reentries array (matches DB structure)
```

**Database Tables Updated**:
- `orders` table: New row with `entry_type="reentry"`

---

### 1.3 Buy Order Execution

**Trigger**: `UnifiedOrderMonitor.check_buy_order_status()` (continuous monitoring)

**Flow**:

```
1. Check Order Status
   └─> Broker API: order_report() or order_history()
   └─> Get order status and filled quantity

2. Execution Quantity Reconciliation (Edge Case #2 Fix)
   └─> Priority order:
       1. fldQty from order_report() (same-day orders)
       2. fldQty from order_history() (historical orders)
       3. Holdings quantity (fallback)
       4. DB order quantity (last resort)
   └─> Handles partial execution correctly

3. If Order Executed:
   └─> UnifiedOrderMonitor._handle_buy_order_execution()
   └─> Steps:
       ├─> Update order status in DB
       │   └─> OrdersRepository.mark_executed()
       │       ├─> status = ONGOING
       │       ├─> execution_price = filled_price
       │       ├─> execution_qty = filled_qty
       │       ├─> filled_at = current_time
       │       ├─> execution_time = current_time
       │       ├─> updated_at = current_time
       │       └─> reason = "Order executed at Rs {price:.2f}"
       │
       ├─> Create/Update Position
       │   └─> UnifiedOrderMonitor._create_position_from_executed_order()
       │       ├─> Check if position exists
       │       ├─> If new position:
       │       │   └─> PositionsRepository.upsert()
       │       │       ├─> quantity = execution_qty
       │       │       ├─> avg_price = execution_price
       │       │       ├─> opened_at = current_time
       │       │       ├─> entry_rsi = from order_metadata
       │       │       ├─> initial_entry_price = execution_price
       │       │       └─> reentry_count = 0
       │       │
       │       └─> If existing position (reentry):
       │           ├─> Calculate weighted average price
       │           ├─> Update quantity (add execution_qty)
       │           ├─> Extract reentry data from order_metadata
       │           ├─> Validate reentry data (_validate_reentry_data)
       │           ├─> Check for duplicate reentry (by order_id)
       │           ├─> Check if position is closed (prevent adding to closed)
       │           ├─> Append to reentries array
       │           ├─> Increment reentry_count
       │           ├─> Update last_reentry_price
       │           └─> PositionsRepository.upsert()
       │               └─> Updates: quantity, avg_price, reentry_count,
       │                   reentries, last_reentry_price
       │
       ├─> Data Integrity Check
       │   └─> Verify reentry_count == len(reentries)
       │   └─> If mismatch: Fix automatically
       │
       ├─> Update Sell Order (Edge Case #1 Fix)
       │   └─> If reentry detected:
       │       ├─> Check for existing sell order
       │       ├─> If found:
       │       │   └─> SellOrderManager.update_sell_order()
       │       │       └─> Update quantity to match new position quantity
       │       │       └─> Keep same target price (EMA9)
       │       └─> If not found:
       │           └─> Will be placed next day at market open
       │
       └─> Send Notification
           └─> TelegramNotifier.notify_order_execution()
```

**Database Tables Updated**:
- `orders` table: `status=ONGOING`, execution fields set
- `positions` table: Created or updated with new quantity/avg_price
- `positions.reentries` array: Updated with reentry data

---

### 1.4 Buy Order Status Updates

**Other Status Changes**:

```
Order Rejected:
  └─> OrdersRepository.mark_rejected()
      ├─> status = FAILED
      ├─> reason = "Broker rejected: {reason}"
      ├─> first_failed_at = current_time (if not set)
      └─> updated_at = current_time

Order Cancelled:
  └─> OrdersRepository.mark_cancelled()
      ├─> status = CANCELLED
      ├─> closed_at = current_time
      ├─> reason = cancellation_reason
      └─> updated_at = current_time

Order Failed:
  └─> OrdersRepository.mark_failed()
      ├─> status = FAILED
      ├─> reason = failure_reason
      ├─> first_failed_at = current_time (if not set)
      ├─> retry_count += 1
      └─> updated_at = current_time
```

---

## 2. Sell Order Flow

### 2.1 Sell Order Placement (Market Open)

**Trigger**: `SellOrderManager.run_at_market_open()` (9:15 AM daily)

**Flow**:

```
1. Reconcile Positions with Broker Holdings (Edge Cases #14, #15, #17 Fix)
   └─> SellOrderManager._reconcile_positions_with_broker_holdings()
   └─> Logic:
       ├─> Fetch broker holdings
       ├─> Compare with positions table
       ├─> If broker_qty < positions_qty:
       │   └─> Manual sell detected
       │       ├─> If broker_qty = 0:
       │       │   └─> PositionsRepository.mark_closed()
       │       │       └─> Mark position as closed
       │       └─> If broker_qty > 0:
       │           └─> PositionsRepository.reduce_quantity()
       │               └─> Reduce quantity by (positions_qty - broker_qty)
       └─> If broker_qty > positions_qty:
           └─> Manual buy detected (ignore - don't update)

2. Get Open Positions
   └─> SellOrderManager.get_open_positions()
   └─> Query positions table (closed_at IS NULL)
   └─> For each position:
       ├─> Get broker holdings quantity
       ├─> Use min(positions_qty, broker_qty) for sell order quantity
       └─> Return list of positions with validated quantities

3. For Each Open Position:
   └─> Calculate Target Price (EMA9)
   └─> Check for Existing Sell Order
       ├─> Query broker: get_order_by_symbol()
       └─> If existing order found:
           ├─> If existing["qty"] == current_qty:
           │   └─> Log and track (no action needed)
           ├─> If existing["qty"] < current_qty:
           │   └─> Edge Case #1 Fix: Update sell order
           │       └─> SellOrderManager.update_sell_order()
           │           └─> Modify broker order with new quantity
           │           └─> Keep same target price
           └─> If existing["qty"] > current_qty:
               └─> Log warning (potential partial sell or manual adjustment)
               └─> Track existing order with current quantity
       └─> If no existing order:
           └─> Place New Sell Order
               ├─> Broker API: place_limit_order()
               ├─> Get broker_order_id
               └─> Track in OrderStateManager
```

**Database Tables Updated**:
- `positions` table: May be updated if manual sells detected
- No direct `orders` table entry (sell orders tracked in-memory and JSON)

---

### 2.2 Sell Order Monitoring

**Trigger**: `SellOrderManager.monitor_and_update()` (every 60 seconds during market hours)

**Flow**:

```
1. For Each Active Sell Order:
   └─> Check Current EMA9 Price
   └─> If EMA9 < current_target_price:
       └─> Update Sell Order Price
           └─> SellOrderManager.update_sell_order()
           └─> Lower price (never raise)
   └─> Check Order Execution
       └─> Broker API: has_completed_sell_order()
       └─> Returns: (filled_qty, order_qty)

2. If Order Executed:
   └─> Check if Full or Partial Execution
   └─> If Full Execution (filled_qty == order_qty):
       ├─> PositionsRepository.mark_closed()
       │   ├─> closed_at = current_time
       │   ├─> exit_price = execution_price
       │   └─> quantity = 0
       │
       ├─> Close Corresponding Buy Orders (Edge Case #12 Fix)
       │   └─> SellOrderManager._close_buy_orders_for_symbol()
       │       └─> Find all ONGOING buy orders for symbol
       │       └─> OrdersRepository.update()
       │           └─> status = CLOSED
       │           └─> closed_at = current_time
       │
       ├─> Cancel Pending Reentry Orders (Edge Case #12 Fix)
       │   └─> SellOrderManager._cancel_pending_reentry_orders()
       │       └─> Find all PENDING reentry orders for symbol
       │       └─> Broker API: cancel_order()
       │       └─> OrdersRepository.update()
       │           └─> status = CANCELLED
       │           └─> reason = "Position closed"
       │
       └─> Remove from Tracking
           └─> OrderStateManager.mark_order_executed()

   └─> If Partial Execution (filled_qty < order_qty):
       ├─> PositionsRepository.reduce_quantity()
       │   ├─> quantity -= filled_qty
       │   └─> If quantity becomes 0:
       │       └─> Mark as closed
       │
       └─> Update Sell Order Quantity
           └─> Modify order with remaining quantity
```

**Database Tables Updated**:
- `positions` table: `closed_at` set or `quantity` reduced
- `orders` table: Buy orders marked as `CLOSED`, reentry orders marked as `CANCELLED`

---

## 3. Position Tracking

### 3.1 Position Creation

**When**: Buy order executes (new entry)

**Database Operation**:
```sql
INSERT INTO positions (
    user_id, symbol, quantity, avg_price,
    opened_at, entry_rsi, initial_entry_price,
    reentry_count, reentries, last_reentry_price
) VALUES (...)
```

**Fields**:
- `quantity`: Execution quantity
- `avg_price`: Execution price
- `opened_at`: Execution time
- `entry_rsi`: RSI10 at entry (from order_metadata)
- `initial_entry_price`: First entry price
- `reentry_count`: 0 (new entry)
- `reentries`: [] (empty array)
- `last_reentry_price`: NULL

---

### 3.2 Position Update (Reentry)

**When**: Reentry order executes

**Database Operation**:
```sql
UPDATE positions SET
    quantity = new_total_qty,
    avg_price = weighted_avg_price,
    reentry_count = reentry_count + 1,
    reentries = JSON_ARRAY_APPEND(reentries, new_reentry_data),
    last_reentry_price = execution_price
WHERE user_id = ? AND symbol = ?
```

**Reentry Data Structure**:
```json
{
    "qty": 10,
    "level": 1,
    "rsi": 28.5,
    "price": 9.50,
    "time": "2025-12-06T10:30:00+05:30",
    "order_id": "250122000624384"
}
```

**Data Integrity Check**:
- After update, verify `reentry_count == len(reentries)`
- If mismatch: Auto-fix by updating `reentry_count`

---

### 3.3 Position Closure

**When**: Sell order fully executes

**Database Operation**:
```sql
UPDATE positions SET
    closed_at = current_time,
    exit_price = execution_price,
    quantity = 0
WHERE user_id = ? AND symbol = ?
```

**Related Actions**:
- Close all ONGOING buy orders for symbol
- Cancel all PENDING reentry orders for symbol

---

### 3.4 Position Partial Sell

**When**: Sell order partially executes

**Database Operation**:
```sql
UPDATE positions SET
    quantity = quantity - sold_qty
WHERE user_id = ? AND symbol = ?

-- If quantity becomes 0:
UPDATE positions SET
    closed_at = current_time,
    exit_price = execution_price,
    quantity = 0
```

---

## 4. Reentry Management

### 4.1 Reentry Detection

**Conditions**:
1. Position exists (open position in database)
2. RSI drops to reentry level:
   - Level 1: RSI10 < 30
   - Level 2: RSI10 < 25
   - Level 3: RSI10 < 20
   - Level 4: RSI10 < 15
3. Price > EMA200 (uptrend filter)
4. Daily reentry cap not exceeded

**Daily Reentry Count**:
```python
def reentries_today():
    # Query positions table
    # Count reentries in reentries array where time is today
    # Return count
```

---

### 4.2 Reentry Tracking

**When Reentry Executes**:

1. **Extract Reentry Data**:
   - From `order_metadata`: `reentry_level`, `reentry_rsi`, `reentry_price`
   - Fallback to execution data if metadata missing

2. **Validate Reentry Data**:
   - Required fields: `qty`, `price`, `time`
   - Type validation: `qty` (int), `price` (float), `time` (ISO format)
   - Value validation: `qty > 0`, `price > 0`

3. **Check for Duplicates**:
   - By `order_id`: If same order_id already in reentries array
   - By combination: `time`, `qty`, `price` (fallback)

4. **Check Position Status**:
   - If position is closed (`closed_at IS NOT NULL`): Skip (log warning)

5. **Append to Reentries Array**:
   - Add validated reentry data
   - Increment `reentry_count`
   - Update `last_reentry_price`

6. **Data Integrity Check**:
   - Verify `reentry_count == len(reentries)`
   - Auto-fix if mismatch

---

### 4.3 Reentry Cancellation

**When**: Sell order fully executes and closes position

**Action**:
```python
_cancel_pending_reentry_orders(symbol)
  └─> Find all PENDING reentry orders for symbol
  └─> For each order:
      ├─> Broker API: cancel_order(broker_order_id)
      └─> OrdersRepository.update()
          ├─> status = CANCELLED
          └─> reason = "Position closed"
```

**Prevents**: Position from being reopened by pending reentry orders

---

## 5. Manual Trade Reconciliation

### 5.1 Manual Sell Detection

**Trigger**: `SellOrderManager.run_at_market_open()` (before placing sell orders)

**Logic**:
```python
_reconcile_positions_with_broker_holdings()
  └─> Fetch broker holdings
  └─> For each open position:
      ├─> If broker_qty == 0 and positions_qty > 0:
      │   └─> Manual full sell detected
      │       └─> PositionsRepository.mark_closed()
      │
      ├─> If broker_qty < positions_qty:
      │   └─> Manual partial sell detected
      │       └─> PositionsRepository.reduce_quantity()
      │
      └─> If broker_qty > positions_qty:
          └─> Manual buy detected (ignore - don't update)
```

**Edge Cases Fixed**:
- #14: Manual partial sell of system holdings
- #15: Manual full sell of system holdings
- #17: Sell order quantity validation

---

### 5.2 Manual Buy Handling

**Behavior**: System ignores manual buys
- Manual buys don't affect system-tracked positions
- Reentry logic still works (system averages down its own holdings)
- Reconciliation doesn't update positions for manual buys

**Edge Case**: #18 - Manual Buy of System-Tracked Symbol (By Design)

---

## 6. Database Schema

### 6.1 Orders Table

**Key Fields**:
```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,  -- 'buy' | 'sell'
    order_type VARCHAR(16) NOT NULL,  -- 'market' | 'limit'
    quantity FLOAT NOT NULL,
    price FLOAT,
    status VARCHAR(16) NOT NULL,  -- PENDING | ONGOING | CLOSED | FAILED | CANCELLED
    entry_type VARCHAR(16),  -- 'entry' | 'reentry'

    -- Execution fields
    execution_price FLOAT,
    execution_qty FLOAT,
    filled_at DATETIME,
    execution_time DATETIME,

    -- Timestamps
    placed_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,  -- ✅ Added (Edge Case Fix)
    closed_at DATETIME,

    -- Failure tracking
    first_failed_at DATETIME,
    last_retry_attempt DATETIME,
    retry_count INTEGER DEFAULT 0,

    -- Metadata
    order_metadata JSON,  -- Stores reentry_level, reentry_rsi, ticker, etc.
    reason VARCHAR(512),

    -- Broker fields
    broker_order_id VARCHAR(64),
    order_id VARCHAR(64),
    last_status_check DATETIME
);
```

---

### 6.2 Positions Table

**Key Fields**:
```sql
CREATE TABLE positions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    quantity FLOAT NOT NULL,
    avg_price FLOAT NOT NULL,

    -- Reentry tracking
    reentry_count INTEGER DEFAULT 0,
    reentries JSON,  -- Array of reentry objects
    initial_entry_price FLOAT,
    last_reentry_price FLOAT,
    entry_rsi FLOAT,  -- RSI10 at initial entry

    -- Timestamps
    opened_at DATETIME NOT NULL,
    closed_at DATETIME,

    -- P&L
    unrealized_pnl FLOAT DEFAULT 0.0,
    exit_price FLOAT,

    UNIQUE(user_id, symbol)
);
```

---

## 7. Edge Cases Fixed

### ✅ Edge Case #1: Sell Order Quantity Not Updated After Reentry
**Fix**: Immediate update when reentry executes + next-day update in `run_at_market_open()`

### ✅ Edge Case #2: Partial Execution Reconciliation
**Fix**: Priority-based reconciliation using `fldQty` from `order_report()` and `order_history()`

### ✅ Edge Case #7: Existing Sell Order Quantity Check Logic
**Fix**: Handles quantity increase, decrease, and equality cases correctly

### ✅ Edge Case #8: Sell Order Execution Doesn't Update Positions Table
**Fix**: `mark_closed()` and `reduce_quantity()` called in `monitor_and_update()`

### ✅ Edge Case #9: Partial Sell Execution Not Handled
**Fix**: Handled as part of Edge Case #8 fix

### ✅ Edge Case #10: Position Quantity Not Reduced After Sell
**Fix**: `reduce_quantity()` method handles partial sells

### ✅ Edge Case #11: Reentry Daily Cap Check Discrepancy
**Fix**: `reentries_today()` now queries database `reentries` array directly

### ✅ Edge Case #12: Sell Order Execution While Reentry Pending
**Fix**: `_cancel_pending_reentry_orders()` cancels pending reentries when position closes

### ✅ Edge Case #13: Multiple Reentries Same Day Bypass
**Fix**: Fixed as part of Edge Case #11 fix

### ✅ Edge Case #14: Manual Partial Sell of System Holdings
**Fix**: `_reconcile_positions_with_broker_holdings()` detects and updates

### ✅ Edge Case #15: Manual Full Sell of System Holdings
**Fix**: `_reconcile_positions_with_broker_holdings()` marks position as closed

### ✅ Edge Case #17: Sell Order Quantity Validation Missing
**Fix**: `get_open_positions()` uses `min(positions_qty, broker_qty)` for validation

### ✅ By Design (Not Bugs):
- **Edge Case #3**: Manual Holdings Not Reflected in Sell Orders
- **Edge Case #16**: Reentry on Mixed Holdings (Average Price Calculation)
- **Edge Case #18**: Manual Buy of System-Tracked Symbol

---

## Summary

The order management system now provides:

1. **Complete Audit Trail**: All order lifecycle events tracked with timestamps
2. **Database-First**: Database is single source of truth, JSON is backup only
3. **Robust Reconciliation**: Handles partial executions, manual trades, and edge cases
4. **Reentry Tracking**: Full tracking of reentries with data integrity checks
5. **Position Management**: Accurate position tracking with automatic updates
6. **Error Handling**: Graceful handling of errors with clear logging

All identified edge cases have been fixed, and the system is production-ready.
