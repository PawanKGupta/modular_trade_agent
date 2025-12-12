# Sell Order Implementation - Complete Documentation

**Date**: 2025-01-27
**Status**: ✅ Current Implementation
**Version**: Database-Based (Post-Unified-Service)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Schema](#database-schema)
4. [Sell Order Placement Flow](#sell-order-placement-flow)
5. [Sell Order Monitoring Flow](#sell-order-monitoring-flow)
6. [Integration with Unified Service](#integration-with-unified-service)
7. [Position Reconciliation](#position-reconciliation)
8. [Blocking Issues & Recommendations](#blocking-issues--recommendations)
9. [Configuration & Usage](#configuration--usage)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

The Sell Order Management System is an automated profit-taking system that:
- Places limit sell orders at market open (9:15 AM) for all open positions
- Monitors daily EMA9 (Exponential Moving Average 9) every minute
- Updates sell orders with the lowest EMA9 value seen during the day
- Tracks order execution and marks positions as closed in the database
- Handles partial executions and manual trade reconciliation

### Key Features

1. **Market Open Execution** - Places limit sell orders at 9:15 AM for all open positions
2. **Dynamic Target Tracking** - Monitors daily EMA9 every minute and updates orders with lowest value
3. **Automatic Execution Tracking** - Marks positions as closed in database when orders execute
4. **Safe Order Management** - Prevents duplicate orders and validates entries
5. **Manual Trade Detection** - Reconciles positions with broker holdings to detect manual sells
6. **Partial Execution Handling** - Updates position quantity and sell order quantity on partial fills
7. **Unified Monitoring** - Integrates with UnifiedOrderMonitor for both buy and sell order tracking

### Exit Strategy

**Target**: EMA9 (Exponential Moving Average 9) - Daily timeframe
**Order Type**: LIMIT orders (not market orders)
**Order Variety**: REGULAR (placed during market hours, not AMO)
**Update Rule**: Only lower the price (never raise) - tracks lowest EMA9 seen

**Safety Check**: EMA9 must be >= 95% of entry price (prevents selling at loss > 5%)

---

## Architecture

### Components

```
Unified Trading Service (run_trading_service.py)
    ↓
SellOrderManager (sell_engine.py)
    ├─→ get_open_positions() - Query positions table (closed_at IS NULL)
    ├─→ _reconcile_positions_with_broker_holdings() - Detect manual trades
    ├─→ get_current_ema9() - Calculate real-time EMA9 with LTP
    ├─→ place_sell_order() - Place limit sell via KotakNeoOrders
    ├─→ update_sell_order() - Modify order with new price/quantity
    ├─→ monitor_and_update() - Continuous monitoring loop
    └─→ check_order_execution() - Monitor order status

UnifiedOrderMonitor (unified_order_monitor.py)
    ├─→ Extends SellOrderManager functionality
    ├─→ monitor_all_orders() - Unified monitoring for buy + sell orders
    ├─→ _create_position_from_executed_order() - Create position on buy execution
    └─→ _handle_sell_order_execution() - Handle sell order execution
```

### Key Classes

1. **SellOrderManager** (`modules/kotak_neo_auto_trader/sell_engine.py`)
   - Core sell order management
   - Database-based position tracking
   - EMA9 calculation and tracking
   - Order placement and monitoring

2. **UnifiedOrderMonitor** (`modules/kotak_neo_auto_trader/unified_order_monitor.py`)
   - Extends SellOrderManager
   - Monitors both buy and sell orders
   - Creates positions from executed buy orders
   - Handles sell order execution

3. **TradingService** (`modules/kotak_neo_auto_trader/run_trading_service.py`)
   - Unified service that runs all trading tasks
   - Integrates SellOrderManager and UnifiedOrderMonitor
   - Schedules sell order placement at market open
   - Continuous monitoring during market hours

---

## Database Schema

### Positions Table

**Table**: `positions`

**Key Fields for Sell Orders**:
- `id`: Primary key
- `user_id`: User identifier
- `symbol`: Base symbol (e.g., "RELIANCE")
- `quantity`: Current position quantity
- `avg_price`: Average entry price
- `opened_at`: Position opening timestamp
- `closed_at`: Position closing timestamp (NULL for open positions)
- `entry_rsi`: RSI10 at initial entry
- `initial_entry_price`: First entry price
- `reentry_count`: Number of re-entries
- `reentries`: JSON array of re-entry data
- `last_reentry_price`: Last re-entry price

**Query for Open Positions**:
```sql
SELECT * FROM positions
WHERE user_id = ? AND closed_at IS NULL
```

**Position Status**:
- **Open**: `closed_at IS NULL` and `quantity > 0`
- **Closed**: `closed_at IS NOT NULL` or `quantity = 0`

### Orders Table

**Table**: `orders`

**Key Fields**:
- `id`: Primary key
- `user_id`: User identifier
- `symbol`: Base symbol
- `broker_order_id`: Broker's order ID
- `status`: Order status (PENDING, ONGOING, EXECUTED, CLOSED, CANCELLED, REJECTED)
- `placed_at`: Order placement timestamp
- `executed_at`: Order execution timestamp
- `entry_type`: "entry" or "reentry"
- `order_metadata`: JSON with entry_rsi, ticker, etc.

**Note**: Sell orders are tracked in-memory and via broker API, not directly in `orders` table.

---

## Sell Order Placement Flow

### Trigger

**When**: Market open (9:15 AM)
**Method**: `SellOrderManager.run_at_market_open()`
**Called By**: `TradingService.run_sell_monitor()`

### Flow Diagram

```
1. Reconcile Positions with Broker Holdings
   └─> _reconcile_positions_with_broker_holdings()
   └─> Detect manual sells/buys
   └─> Update positions table if needed

2. Get Open Positions
   └─> get_open_positions()
   └─> Query positions table (closed_at IS NULL)
   └─> For each position:
       ├─> Get broker holdings quantity
       ├─> Use min(positions_qty, broker_qty) for sell order quantity
       └─> Return list of positions with validated quantities

3. For Each Open Position:
   └─> Calculate Target Price (EMA9)
       └─> get_current_ema9(ticker, broker_symbol)
       └─> Real-time calculation with LTP (Last Traded Price)

   └─> Validate EMA9
       └─> Check: EMA9 >= 95% of entry price
       └─> If not: Skip position (safety check)

   └─> Check for Existing Sell Order
       ├─> Query broker: get_order_by_symbol()
       └─> If existing order found:
           ├─> If existing["qty"] == current_qty:
           │   └─> Log and track (no action needed)
           ├─> If existing["qty"] < current_qty:
           │   └─> Update sell order quantity
           │       └─> update_sell_order() - Modify order
           └─> If existing["qty"] > current_qty:
               └─> Log warning (potential partial sell)
               └─> Track existing order with current quantity
       └─> If no existing order:
           └─> Place New Sell Order
               ├─> Broker API: place_limit_order()
               ├─> Get broker_order_id
               └─> Register in OrderStateManager
```

### Code Location

**File**: `modules/kotak_neo_auto_trader/sell_engine.py`

**Key Methods**:
- `run_at_market_open()`: Lines ~2040-2250
- `get_open_positions()`: Lines ~430-600
- `_reconcile_positions_with_broker_holdings()`: Lines ~600-800
- `get_current_ema9()`: Lines ~2190-2200
- `place_sell_order()`: Lines ~900-1000

### Database Updates

**During Placement**:
- `positions` table: May be updated if manual sells detected (via reconciliation)
- No direct `orders` table entry (sell orders tracked in-memory and JSON)

---

## Sell Order Monitoring Flow

### Trigger

**When**: Every 60 seconds during market hours (9:15 AM - 3:30 PM)
**Method**: `SellOrderManager.monitor_and_update()` or `UnifiedOrderMonitor.monitor_all_orders()`
**Called By**: `TradingService.run_sell_monitor()`

### Flow Diagram

```
1. For Each Active Sell Order:
   └─> Check Current EMA9 Price
       └─> get_current_ema9(ticker, broker_symbol)
       └─> Real-time calculation with LTP

   └─> If EMA9 < current_target_price:
       └─> Update Sell Order Price
           └─> update_sell_order()
           └─> Modify broker order with new price
           └─> Lower price (never raise)
           └─> Track lowest EMA9 seen

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
       ├─> Close Corresponding Buy Orders
       │   └─> _close_buy_orders_for_symbol()
       │       └─> Find all ONGOING buy orders for symbol
       │       └─> OrdersRepository.update()
       │           └─> status = CLOSED
       │           └─> closed_at = current_time
       │
       ├─> Cancel Pending Reentry Orders
       │   └─> _cancel_pending_reentry_orders()
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

### Code Location

**File**: `modules/kotak_neo_auto_trader/sell_engine.py`

**Key Methods**:
- `monitor_and_update()`: Lines ~2740-2900
- `update_sell_order()`: Lines ~1000-1100
- `check_order_execution()`: Lines ~1100-1200
- `_close_buy_orders_for_symbol()`: Lines ~1200-1300
- `_cancel_pending_reentry_orders()`: Lines ~1300-1400

### Database Updates

**During Monitoring**:
- `positions` table: `closed_at` set or `quantity` reduced
- `orders` table: Buy orders marked as `CLOSED`, reentry orders marked as `CANCELLED`

---

## Integration with Unified Service

### Unified Trading Service

**File**: `modules/kotak_neo_auto_trader/run_trading_service.py`

**Service Flow**:
```
TradingService.run_sell_monitor()
    ├─> Market Open (9:15 AM):
    │   └─> sell_manager.run_at_market_open()
    │       └─> Place sell orders for all open positions
    │
    └─> Market Hours (Every 60 seconds):
        ├─> If unified_order_monitor available:
        │   └─> unified_order_monitor.monitor_all_orders()
        │       └─> Monitors both buy and sell orders
        │
        └─> Else (fallback):
            └─> sell_manager.monitor_and_update()
                └─> Monitors sell orders only
```

### UnifiedOrderMonitor

**File**: `modules/kotak_neo_auto_trader/unified_order_monitor.py`

**Key Features**:
- Extends `SellOrderManager` functionality
- Monitors both buy (AMO) and sell orders in a unified loop
- Creates positions from executed buy orders
- Handles sell order execution and position closure

**Position Creation**:
- When a buy order executes, `_create_position_from_executed_order()` is called
- Creates or updates position in `positions` table
- Stores entry metadata (entry_rsi, initial_entry_price, etc.)
- Tracks re-entries in `reentries` JSON array

**Code Location**:
- `_create_position_from_executed_order()`: Lines ~780-1150
- `monitor_all_orders()`: Lines ~1380-1500

---

## Position Reconciliation

### Purpose

Reconciles positions in the database with actual broker holdings to detect:
- Manual sells (broker holdings < database quantity)
- Manual buys (broker holdings > database quantity)
- Holdings fetch failures

### When It Runs

1. **Market Open** (before placing sell orders)
   - `SellOrderManager.run_at_market_open()` calls `_reconcile_positions_with_broker_holdings()`

2. **Before Re-entry Placement** (during market hours)
   - `AutoTradeEngine.place_reentry_orders()` calls reconciliation if `sell_manager` is available

### Reconciliation Logic

**File**: `modules/kotak_neo_auto_trader/sell_engine.py`
**Method**: `_reconcile_positions_with_broker_holdings()` (Lines ~558-700)

**When Reconciliation Runs**:

1. **At Market Open** (~9:15 AM):
   - `run_at_market_open()` calls reconciliation before placing sell orders
   - Ensures positions table is up-to-date before order placement

2. **During Market Hours** (Every 30 minutes):
   - `monitor_and_update()` runs reconciliation at :00 and :30 minutes of each hour
   - Periodic reconciliation to detect manual trades during market hours
   - Example: 10:00, 10:30, 11:00, 11:30, etc.

3. **Before Reentry Orders**:
   - `place_reentry_orders()` calls reconciliation before placing reentry orders
   - Ensures accurate position data for reentry decisions

**Flow**:
```
1. Fetch Broker Holdings
   └─> portfolio.get_holdings()
   └─> Get current holdings from broker API

2. For Each Open Position:
   └─> Compare positions_qty vs broker_qty

   └─> If broker_qty < positions_qty:
       └─> Manual sell detected
       ├─> If broker_qty = 0:
       │   └─> PositionsRepository.mark_closed()
       │       └─> Mark position as closed
       └─> If broker_qty > 0:
           └─> PositionsRepository.reduce_quantity()
               └─> Reduce quantity by (positions_qty - broker_qty)

   └─> If broker_qty > positions_qty:
       └─> Manual buy detected
       └─> Ignore (don't update - user may have bought manually)
```

**When Positions Table is Updated**:
- **Market Open**: Once at ~9:15 AM when `run_at_market_open()` executes
- **During Market Hours**: Every 30 minutes (at :00 and :30 minutes) during `monitor_and_update()`
- **Before Reentry**: When reentry logic runs to ensure accurate position data

### Edge Cases Handled

1. **Manual Sell Detection**: Automatically closes or reduces position quantity
2. **Holdings Fetch Failure**: Logs warning but continues with database quantity
3. **Quantity Mismatch**: Uses `min(positions_qty, broker_qty)` for sell order quantity

---

## Blocking Issues & Recommendations

### Critical Issues

#### Issue #1: Position Creation Failure ✅ **FIXED**

**Location**: `modules/kotak_neo_auto_trader/unified_order_monitor.py:93-150`

**Status**: ✅ **FIXED** (2025-01-27)

**Problem**: If `_create_position_from_executed_order()` returns early, position is never created in database.

**Blocking Conditions** (Before Fix):
- `positions_repo` is `None`
- `user_id` is `None`
- `orders_repo` is `None`
- `symbol` is missing from `order_info`

**Impact**: Buy order executes successfully, but position is not created → Sell order is never placed.

**Solution Implemented**:

1. **Required Parameters Validation**:
   - `db_session` and `user_id` are now **required** when `DB_AVAILABLE` is `True`
   - Raises `ValueError` if missing during initialization (fails fast)

2. **Repository Initialization with Exception Handling**:
   - `OrdersRepository` and `PositionsRepository` initialization wrapped in try-except
   - Raises `RuntimeError` if initialization fails (prevents silent failures)
   - Object is never created in invalid state

3. **Final Validation**:
   - After initialization, validates that critical dependencies exist
   - Raises `RuntimeError` if repositories or `user_id` are missing
   - Ensures object is never in invalid state

**Code Changes**:
- Lines 93-104: Validate required parameters when `DB_AVAILABLE` is `True`
- Lines 106-130: Initialize repositories with exception handling
- Lines 132-150: Final validation of critical dependencies

**Tests Added**:
- `test_initialization_raises_value_error_when_db_session_none`
- `test_initialization_raises_value_error_when_user_id_none`
- `test_initialization_raises_runtime_error_when_orders_repo_fails`
- `test_initialization_raises_runtime_error_when_positions_repo_fails`
- `test_initialization_raises_runtime_error_when_repos_missing_after_init`
- `test_initialization_raises_value_error_when_user_id_zero`
- `test_initialization_succeeds_with_all_required_params`

**Impact**: Position creation failures now fail fast during initialization, preventing silent failures that would block sell order placement.

#### Issue #2: Zero Quantity After Validation ✅ **FIXED**

**Location**: `modules/kotak_neo_auto_trader/sell_engine.py:523-541, 921-923`

**Status**: ✅ **FIXED** (2025-01-27)

**Problem**: If `sell_qty` becomes 0 after validation, position is still added to `open_positions`, but `place_sell_order()` rejects it.

**Impact**: Position exists in database, but sell order is not placed.

**Solution Implemented**:

1. **Zero Quantity Filtering**:
   - Added check in `get_open_positions()`: `if sell_qty <= 0: continue`
   - Filters out zero quantity positions before adding to `open_positions` list
   - Logs warning when zero quantity position is skipped

2. **Broker Holdings Map Enhancement**:
   - Changed from `if base_symbol and qty > 0` to `if base_symbol` to track all holdings
   - Now tracks zero quantity holdings (detects when broker has 0 shares)
   - Ensures proper detection of manual full sells

**Code Changes**:
- Lines 480-481: Track all holdings including zero quantity in `broker_holdings_map`
- Lines 523-530: Filter zero quantity positions with warning log

**Tests Added**:
- `test_get_open_positions_filters_zero_quantity_issue_2` - Tests filtering when broker has 0 shares
- `test_get_open_positions_filters_zero_quantity_when_positions_zero` - Tests filtering when positions_qty is 0

**Impact**: Zero quantity positions are no longer added to `open_positions`, preventing unnecessary processing and repeated order placement attempts.

### Medium Issues

#### Issue #3: EMA9 Calculation Failure

**Location**: `modules/kotak_neo_auto_trader/sell_engine.py:2193-2198`

**Problem**: If `get_current_ema9()` returns `None`, sell order is skipped.

**Impact**: Position exists, but sell order is not placed.

**Recommendation**:
- Add retry mechanism for EMA9 calculation
- Use previous day's EMA9 as fallback
- Add alerting when EMA9 calculation fails

#### Issue #4: EMA9 Validation Failure

**Location**: `modules/kotak_neo_auto_trader/sell_engine.py:2200-2206`

**Problem**: If EMA9 < 95% of entry price, sell order is skipped (safety check).

**Impact**: Position exists, but sell order is not placed (prevents selling at loss > 5%).

**Note**: This is a **safety feature**, but it blocks monitoring for these positions.

**Recommendation**:
- Consider if 5% threshold is appropriate for all scenarios
- Add configuration option to adjust threshold
- Consider allowing sell order placement with warning instead of blocking

#### Issue #5: No Active Sell Orders

**Location**: `modules/kotak_neo_auto_trader/sell_engine.py:2742-2744`

**Problem**: If `active_sell_orders` is empty, monitoring returns early.

**Impact**: Position exists, but no sell order was placed → Position is not monitored.

**Recommendation**:
- Add separate monitoring for positions that don't have sell orders
- Track why sell orders weren't placed
- Provide dashboard/alerts for positions without sell orders

---

## Configuration & Usage

### Environment Variables

**File**: `kotak_neo.env`

```env
KOTAK_CONSUMER_KEY=your_key
KOTAK_CONSUMER_SECRET=your_secret
KOTAK_MOBILE_NUMBER=your_mobile
KOTAK_PASSWORD=your_password
KOTAK_MPIN=your_mpin
KOTAK_ENVIRONMENT=prod
```

### Unified Service Configuration

**File**: `docker/docker-compose.yml` or `server/app/main.py`

```yaml
environment:
  RUN_UNIFIED_IN_API: false  # Set to false to disable auto-start
  UNIFIED_USER_IDS: "1,2,3"  # Comma-separated user IDs
```

### Standalone Usage (Deprecated)

**Note**: The standalone `run_sell_orders.py` script is deprecated. Use the unified service instead.

**If needed** (for testing):
```bash
python -m modules.kotak_neo_auto_trader.run_sell_orders \
  --env modules/kotak_neo_auto_trader/kotak_neo.env \
  --skip-wait \
  --run-once
```

### Monitoring Interval

**Default**: 60 seconds (1 minute)
**Location**: `SellOrderManager.__init__()` or `TradingService.run_sell_monitor()`

**Adjustment**: Modify the monitoring loop interval in `TradingService.run_sell_monitor()`

---

## Troubleshooting

### "No open positions to place sell orders"

**Cause**: No positions with `closed_at IS NULL` in database.

**Check**:
1. Query positions table: `SELECT * FROM positions WHERE user_id = ? AND closed_at IS NULL`
2. Verify positions were created when buy orders executed
3. Check `UnifiedOrderMonitor._create_position_from_executed_order()` logs

**Fix**:
- Ensure `positions_repo` and `user_id` are initialized in `UnifiedOrderMonitor`
- Check if buy orders executed successfully
- Verify position creation logs

### "Failed to fetch EMA9"

**Cause**: EMA9 calculation failed.

**Check**:
1. Verify ticker format (e.g., "RELIANCE.NS" not "RELIANCE")
2. Check indicator service availability
3. Verify price data service is running
4. Check network connectivity

**Fix**:
- Verify ticker format in position metadata
- Check indicator service logs
- Retry EMA9 calculation
- Use fallback to previous day's EMA9

### "Order placement failed"

**Cause**: Broker API call failed.

**Check**:
1. Verify Kotak Neo credentials
2. Check if market is open (9:15 AM - 3:30 PM)
3. Verify sufficient holdings to sell
4. Check broker API logs

**Fix**:
- Re-authenticate if session expired
- Verify market hours
- Check holdings quantity
- Review broker API error messages

### "Skipping: EMA9 is too low"

**Cause**: EMA9 < 95% of entry price (safety check).

**Check**:
1. Calculate: `EMA9 / entry_price < 0.95`
2. Verify entry price in position
3. Check current EMA9 value

**Fix**:
- This is a safety feature to prevent selling at loss > 5%
- Wait for price recovery
- Manually adjust if needed
- Consider adjusting threshold in configuration

### "Invalid quantity 0 for {symbol}"

**Cause**: `sell_qty` became 0 after validation.

**Check**:
1. Verify broker holdings quantity
2. Check reconciliation logs
3. Verify position quantity in database

**Fix**:
- Run reconciliation manually
- Check for manual sells
- Verify holdings fetch succeeded
- Filter zero quantity positions in `get_open_positions()`

### "Position not created after buy order execution"

**Cause**: `_create_position_from_executed_order()` returned early.

**Check**:
1. Check logs for position creation errors
2. Verify `positions_repo` and `user_id` are initialized
3. Check `orders_repo` availability
4. Verify symbol extraction from `order_info`

**Fix**:
- Ensure `UnifiedOrderMonitor` is properly initialized
- Check database connection
- Verify order metadata contains symbol
- Add retry mechanism for position creation

### "No active sell orders to monitor"

**Cause**: No sell orders were placed or registered.

**Check**:
1. Verify sell orders were placed at market open
2. Check `active_sell_orders` dictionary
3. Review placement logs
4. Check for blocking conditions (Issues #1-5)

**Fix**:
- Review sell order placement logs
- Check for blocking conditions
- Verify positions exist in database
- Ensure EMA9 calculation succeeded

---

## Summary

### Key Points

1. **Database-Based**: All positions are stored in `positions` table (not JSON files)
2. **Unified Service**: Sell orders are managed by `TradingService` via `SellOrderManager` or `UnifiedOrderMonitor`
3. **EMA9 Target**: Sell orders are placed at EMA9 price and updated only if EMA9 drops
4. **Safety Check**: EMA9 must be >= 95% of entry price to prevent selling at loss > 5%
5. **Reconciliation**: Positions are reconciled with broker holdings to detect manual trades
6. **Monitoring**: Continuous monitoring every 60 seconds during market hours
7. **Execution Handling**: Full and partial executions are handled, with position closure and buy order cancellation

### Integration Points

- **Buy Orders**: When buy orders execute, positions are created via `UnifiedOrderMonitor._create_position_from_executed_order()`
- **Re-entries**: Re-entry orders update position quantity and `reentries` array
- **Sell Orders**: When sell orders execute, positions are closed and pending buy/reentry orders are cancelled
- **Manual Trades**: Reconciliation detects manual sells and updates positions accordingly

### Future Enhancements

- [ ] Telegram alerts for order execution
- [ ] Trailing stop-loss option (update on price increase)
- [ ] Multi-level profit taking (partial exits)
- [ ] Performance analytics dashboard
- [ ] EMA9 calculation fallback mechanism
- [ ] Comprehensive alerting for blocking conditions

---

**Last Updated**: 2025-01-27
**Maintained By**: Trading System Team
