# Pending Order Maintenance Logic

## Overview

The system maintains pending orders from placement through execution/rejection/cancellation. Orders are tracked in `data/pending_orders.json` and verified periodically.

---

## Order Lifecycle

```
Order Placement
    ↓
add_pending_order() → Status: PENDING
    ↓
Periodic Verification (every 30 min)
    ↓
┌─────────────┬──────────────┬──────────────┐
│  EXECUTED   │   REJECTED   │  CANCELLED   │
│     ↓       │      ↓       │      ↓       │
│  Remove     │   Remove     │   Remove     │
└─────────────┴──────────────┴──────────────┘
```

---

## Components

### 1. OrderTracker (`order_tracker.py`)

**Purpose**: Manages pending orders persistence and status updates.

**Storage**: `data/pending_orders.json`
```json
{
  "orders": [
    {
      "order_id": "251106000008974",
      "symbol": "DALBHARAT-EQ",
      "ticker": "DALBHARAT.NS",
      "qty": 233,
      "order_type": "MARKET",
      "variety": "AMO",
      "price": 0.0,
      "placed_at": "2025-11-06T09:15:08",
      "last_status_check": "2025-11-06T09:15:08",
      "status": "PENDING",
      "rejection_reason": null,
      "check_count": 0,
      "executed_qty": 0
    }
  ]
}
```

**Key Methods**:

1. **`add_pending_order()`** (Lines 107-171)
   - Adds order to `pending_orders.json`
   - **Duplicate Prevention**: Checks if `order_id` already exists before adding
   - Sets initial status: `PENDING`
   - Initializes: `placed_at`, `last_status_check`, `check_count=0`

2. **`get_pending_orders()`** (Lines 173-198)
   - Retrieves orders with optional filters:
     - `status_filter`: PENDING/OPEN/EXECUTED/REJECTED/CANCELLED
     - `symbol_filter`: Filter by symbol

3. **`update_order_status()`** (Lines 200-244)
   - Updates order status in file
   - Increments `check_count`
   - Updates `last_status_check` timestamp
   - Can set `executed_qty` and `rejection_reason`

4. **`remove_pending_order()`** (Lines 246-267)
   - Removes order from tracking (when executed/rejected/cancelled)

---

### 2. OrderStatusVerifier (`order_status_verifier.py`)

**Purpose**: Periodically verifies pending orders with broker API.

**Verification Cycle**:
- Runs every **30 minutes** (configurable, default: 1800s)
- Background thread (`_verification_loop()`)
- Checks all orders with status `PENDING`

**Process** (`verify_pending_orders()`, Lines 124-250):

1. **Fetch Pending Orders**
   ```python
   pending_orders = self.order_tracker.get_pending_orders(status_filter="PENDING")
   ```

2. **Fetch Broker Orders**
   ```python
   broker_orders = self._fetch_broker_orders()  # From broker API
   ```

3. **Match & Verify**
   - For each pending order:
     - Find matching order in broker's order book
     - Parse broker status: `EXECUTED`, `REJECTED`, `CANCELLED`, `PARTIALLY_FILLED`, `OPEN`, `PENDING`
     - Handle based on status:
       - **EXECUTED**: `_handle_execution()` → Update status → Remove from tracking
       - **REJECTED**: `_handle_rejection()` → Update status → Remove from tracking
       - **CANCELLED**: `_handle_cancellation()` → Update status → Remove from tracking
       - **PARTIALLY_FILLED**: `_handle_partial_fill()` → Update status & executed_qty
       - **OPEN/PENDING**: No action (still pending)

**Status Handlers**:

- **`_handle_execution()`** (Lines 380-420)
  - Updates order status to `EXECUTED`
  - Updates `executed_qty`
  - Removes from `pending_orders.json`
  - Calls `on_execution_callback` if provided

- **`_handle_rejection()`** (Lines 422-462)
  - Updates order status to `REJECTED`
  - Sets `rejection_reason`
  - Removes from `pending_orders.json`
  - Calls `on_rejection_callback` if provided

- **`_handle_cancellation()`** (Lines 464-504)
  - Updates order status to `CANCELLED`
  - Removes from `pending_orders.json`

- **`_handle_partial_fill()`** (Lines 506-546)
  - Updates order status to `PARTIALLY_FILLED`
  - Updates `executed_qty`
  - Keeps order in tracking (not removed)

---

### 3. OrderStateManager (`order_state_manager.py`)

**Purpose**: Unified order state management (in-memory cache + persistence).

**Dual Storage**:
- **In-Memory**: `self.active_sell_orders` (for sell orders)
- **Persistent**: `pending_orders.json` (via OrderTracker)

**`register_sell_order()`** (Lines 77-161):
1. Checks if order already exists (duplicate prevention)
2. Updates in-memory cache (`active_sell_orders`)
3. Adds to `pending_orders.json` via `OrderTracker.add_pending_order()`
4. Handles price updates for existing orders

**`mark_order_executed()`** (Lines 161-216):
1. Removes from `active_sell_orders`
2. Updates `pending_orders.json` status to `EXECUTED`
3. Updates trade history

---

### 4. EODCleanup (`eod_cleanup.py`)

**Purpose**: End-of-day cleanup and reconciliation.

**Cleanup Process** (`_cleanup_stale_orders()`, Lines 224-277):

1. **Stale Order Detection**
   - Finds orders with status `PENDING` older than **24 hours**
   - Cutoff: `datetime.now() - timedelta(hours=24)`

2. **Removal**
   - Removes stale orders from `pending_orders.json`
   - Logs warning with order age

**EOD Workflow** (`run_eod_cleanup()`, Lines 66-173):
1. Final order verification
2. Manual trade reconciliation
3. **Stale order cleanup** (removes orders > 24h old)
4. Generate daily statistics
5. Send Telegram summary
6. Archive completed entries

---

## Order Addition Flow

### Buy Orders (`auto_trade_engine.py`)

```python
# In _attempt_place_order() (Lines 773-975)
1. Place order via broker API
2. Extract order_id from response
3. Add to tracking scope (tracking_scope.py)
4. add_pending_order() → pending_orders.json
   - order_id, symbol, ticker, qty, order_type, variety, price
   - Status: PENDING
```

### Sell Orders (`sell_engine.py`)

```python
# In _register_order() → register_sell_order()
1. OrderStateManager.register_sell_order()
   - Updates active_sell_orders (in-memory)
   - Calls OrderTracker.add_pending_order()
   - Status: PENDING
```

---

## Order Status Updates

### Automatic Updates (OrderStatusVerifier)

**Every 30 minutes**:
1. Fetch all `PENDING` orders from `pending_orders.json`
2. Fetch current orders from broker API
3. Match orders by `order_id`
4. Parse broker status
5. Update status in `pending_orders.json`:
   - `EXECUTED` → Remove from tracking
   - `REJECTED` → Remove from tracking
   - `CANCELLED` → Remove from tracking
   - `PARTIALLY_FILLED` → Keep in tracking, update `executed_qty`
   - `OPEN/PENDING` → No change

### Manual Updates

**From OrderStateManager**:
- `mark_order_executed()` → Updates status to `EXECUTED`
- `sync_with_broker()` → Syncs status from broker orders

---

## Order Removal

Orders are removed from `pending_orders.json` when:

1. **Executed** (`_handle_execution()`)
   - Status: `EXECUTED`
   - Removed immediately after verification

2. **Rejected** (`_handle_rejection()`)
   - Status: `REJECTED`
   - Removed immediately after verification

3. **Cancelled** (`_handle_cancellation()`)
   - Status: `CANCELLED`
   - Removed immediately after verification

4. **Stale** (`_cleanup_stale_orders()`)
   - Status: `PENDING`
   - Age: > 24 hours
   - Removed during EOD cleanup (6:00 PM)

---

## Duplicate Prevention

### Layer 1: OrderStateManager
- `register_sell_order()` checks if order already exists in `active_sell_orders`
- If exists with same `order_id`:
  - Updates price if changed
  - Returns `True` (skips duplicate registration)

### Layer 2: OrderTracker
- `add_pending_order()` checks if `order_id` already exists in `pending_orders.json`
- If exists:
  - Logs warning
  - Returns without adding (prevents duplicate)

---

## Key Features

### 1. Persistence
- All orders stored in `data/pending_orders.json`
- Survives service restarts
- JSON format for easy inspection

### 2. Status Tracking
- Initial: `PENDING`
- Updated via verification: `EXECUTED`, `REJECTED`, `CANCELLED`, `PARTIALLY_FILLED`, `OPEN`
- Tracks: `check_count`, `last_status_check`, `executed_qty`, `rejection_reason`

### 3. Periodic Verification
- Background thread runs every 30 minutes
- Verifies all `PENDING` orders with broker
- Updates status automatically

### 4. Cleanup
- EOD cleanup removes stale orders (> 24h old)
- Executed/rejected/cancelled orders removed immediately
- Prevents `pending_orders.json` from growing indefinitely

### 5. Filtering
- Get orders by status: `get_pending_orders(status_filter="PENDING")`
- Get orders by symbol: `get_pending_orders(symbol_filter="RELIANCE")`
- Combined filters supported

---

## Example Flow

### Scenario: Buy Order Placement

```
1. 09:15:00 - Order placed
   → add_pending_order(order_id="12345", status="PENDING")
   → pending_orders.json: [{"order_id": "12345", "status": "PENDING", ...}]

2. 09:15:30 - OrderStatusVerifier checks (every 30 min)
   → Broker status: OPEN
   → No change (still PENDING)

3. 09:45:30 - OrderStatusVerifier checks again
   → Broker status: EXECUTED
   → _handle_execution()
   → Update status: EXECUTED
   → Remove from pending_orders.json
   → pending_orders.json: [] (empty)

4. 18:00:00 - EOD Cleanup
   → No stale orders (already removed)
```

### Scenario: Stale Order

```
1. Day 1, 09:15:00 - Order placed
   → add_pending_order(order_id="12345", status="PENDING")
   → Broker never confirms (network issue)

2. Day 1, 18:00:00 - EOD Cleanup
   → Order age: 8.75 hours (< 24h)
   → Not removed

3. Day 2, 18:00:00 - EOD Cleanup
   → Order age: 32.75 hours (> 24h)
   → _cleanup_stale_orders()
   → Remove stale order
   → pending_orders.json: [] (empty)
```

---

## Configuration

**Verification Interval**: Default 30 minutes (1800s)
```python
OrderStatusVerifier(check_interval_seconds=1800)
```

**Stale Order Threshold**: Default 24 hours
```python
_cleanup_stale_orders(max_age_hours=24)
```

**Storage Location**: `data/pending_orders.json`
```python
OrderTracker(data_dir="data")
```

---

## Summary

The pending order maintenance system provides:

✅ **Persistence**: Orders survive service restarts  
✅ **Automatic Verification**: Checks status every 30 minutes  
✅ **Status Tracking**: Tracks order lifecycle from PENDING to final state  
✅ **Duplicate Prevention**: Prevents same order_id being added twice  
✅ **Cleanup**: Removes stale orders (> 24h) and completed orders  
✅ **Filtering**: Query orders by status or symbol  
✅ **Reconciliation**: EOD cleanup reconciles with broker state  

This ensures orders are tracked accurately from placement through execution/rejection, with automatic cleanup to prevent data accumulation.





