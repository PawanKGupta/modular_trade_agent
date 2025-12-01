# System Holdings Tracking in Database

## Overview

System holdings are tracked in **two places** in the database:
1. **`orders` table** - Order lifecycle tracking (status = `ONGOING` when executed)
2. **`positions` table** - Actual holdings/positions tracking

## Database Schema

### 1. Orders Table (`orders`)

**Purpose**: Tracks order lifecycle from placement to execution/closure

**Key Fields**:
- `status`: Order status (AMO, PENDING_EXECUTION, ONGOING, CLOSED, etc.)
- `execution_price`: Price at which order executed
- `execution_qty`: Quantity executed
- `execution_time`: When order was executed
- `filled_at`: When order was filled

**Status Flow**:
```
AMO → PENDING_EXECUTION → ONGOING (when executed) → CLOSED (when sold)
```

**When Status = ONGOING**:
- Order has been executed
- User has the stock in holdings
- This is the indicator that system order was executed

### 2. Positions Table (`positions`)

**Purpose**: Tracks actual holdings/positions (aggregated view)

**Key Fields**:
- `symbol`: Stock symbol
- `quantity`: Total quantity held
- `avg_price`: Average purchase price
- `unrealized_pnl`: Unrealized profit/loss
- `opened_at`: When position was opened
- `closed_at`: When position was closed (NULL = open position)

**Unique Constraint**: `(user_id, symbol)` - One position per symbol per user

## How Holdings Are Tracked

### Flow 1: Order Execution → Positions Table (Optimized)

**Step 1: Order Executed**
- Broker confirms order execution
- `orders_repo.mark_executed()` is called
- Order status changes to `ONGOING`
- Execution details saved: `execution_price`, `execution_qty`, `execution_time`

**Step 2: Trade History Entry Created & Position Updated Directly**
- Trade entry added to `trades_history.json` (or DB equivalent) via `_append_trade()`
- Status: `"open"`
- Contains: symbol, qty, entry_price, entry_time, etc.
- **Optimization**: `_update_position_from_trade()` is called immediately to update positions table
  - No need to sync all trades - only the new trade is processed
  - Calls `positions_repo.upsert()` directly
  - If position exists → updates quantity and avg_price
  - If position doesn't exist → creates new position

**Location**: 
- `modules/kotak_neo_auto_trader/auto_trade_engine.py` - `_append_trade()` (Line 392-405)
- `modules/kotak_neo_auto_trader/auto_trade_engine.py` - `_update_position_from_trade()` (Line 320-383)

```python
if status == "open":
    # Upsert open position
    self.positions_repo.upsert(
        user_id=self.user_id,
        symbol=symbol,
        quantity=qty,
        avg_price=entry_price,
        opened_at=entry_time,
    )
```

### Flow 2: Holdings Reconciliation

**Method**: `reconcile_holdings_to_history()`

**Purpose**: Sync broker holdings to trade history (for system-tracked stocks only)

**Process**:
1. Fetches holdings from broker API
2. For each holding:
   - Checks if stock is system-tracked (was recommended by system)
   - If tracked → adds to trade history with status `"open"`
   - If not tracked → skips (system doesn't track manual holdings)

**Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Line 1062-1190

**Key Point**: Only system-recommended stocks are added to trade history

## Current Implementation Status

### ✅ What's Tracked

1. **Orders Table**:
   - All orders placed by system (AMO, PENDING_EXECUTION, ONGOING, etc.)
   - Order execution details
   - Status = `ONGOING` indicates order executed (user has holdings)

2. **Positions Table**:
   - Synced from trade history entries with status `"open"`
   - Represents actual holdings from system orders
   - One row per symbol per user

3. **Trade History**:
   - File-based: `trades_history.json`
   - Contains entries with status `"open"` (active positions)
   - Synced to positions table

### ❌ What's NOT Tracked

1. **Manual Holdings**:
   - If user manually bought stock (not through system) → NOT in trade history
   - NOT synced to positions table
   - System doesn't track holdings it didn't place

2. **Existing Holdings**:
   - If user had stock before system started → NOT tracked
   - System only tracks orders it places itself

## Key Methods

### OrdersRepository.mark_executed()
- **Location**: `src/infrastructure/persistence/orders_repository.py` - Line 309-322
- **What it does**: Updates order status to `ONGOING`, saves execution details
- **Does NOT create position**: Only updates order record

### PositionsRepository.upsert()
- **Location**: `src/infrastructure/persistence/positions_repository.py` - Line 32-57
- **What it does**: Creates or updates position in positions table
- **When called**: From `_update_position_from_trade()` when a trade is added/updated

### _update_position_from_trade()
- **Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Line 320-383
- **What it does**: Updates positions table directly from a single trade entry
- **When called**: 
  - From `_append_trade()` when a new trade is added (optimized path)
  - From `_save_trades_history()` for bulk sync operations (initial load/reconciliation)
- **Process**: 
  - For status `"open"` → calls `positions_repo.upsert()` to create/update position
  - For status `"closed"` → sets `closed_at` timestamp on position

### _append_trade()
- **Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Line 392-405
- **What it does**: Adds trade to history and immediately updates positions table
- **Optimization**: Calls `_update_position_from_trade()` directly (no bulk sync needed)

### _save_trades_history()
- **Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Line 385-410
- **What it does**: Saves trade history and optionally bulk syncs all trades to positions
- **When used**: For initial load, reconciliation, or bulk operations
- **Note**: Individual trade updates use `_append_trade()` which is more efficient

## Summary

**System Holdings Tracking**:
- **Orders Table**: Tracks order lifecycle, status `ONGOING` = executed (user has holdings)
- **Positions Table**: Tracks actual holdings, synced from trade history
- **Trade History**: Source of truth for positions, contains entries with status `"open"`

**Key Point**: 
- System only tracks holdings from orders it placed
- Manual holdings are NOT tracked
- **Optimization**: Positions table is updated directly when trades are added/updated (no bulk sync needed)
- Positions are updated immediately when `_append_trade()` is called
- For position closures, `SellOrderManager.mark_position_closed()` also updates positions table directly if `positions_repo` is available

