# Order Management - Complete Guide

**Last Updated:** 2025-12-14
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Order Flow Documentation](#order-flow-documentation)
3. [Flaw Analysis & Fixes](#flaw-analysis--fixes)
4. [Flow Validation](#flow-validation)
5. [Order Lifecycle Audit](#order-lifecycle-audit)
6. [Transaction Safety](#transaction-safety)
7. [Race Condition Fixes](#race-condition-fixes)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This document consolidates all order management documentation including:
- Complete order flow documentation
- Flaw analysis and fixes
- Flow validation
- Order lifecycle audit
- Transaction safety implementation
- Race condition fixes

### Key Features

- ✅ Buy order placement and execution (new entries & reentries)
- ✅ Sell order placement and execution
- ✅ Position tracking with database persistence
- ✅ Reentry tracking with full audit trail
- ✅ Manual trade detection and reconciliation
- ✅ Partial execution handling
- ✅ Order status updates with timestamps
- ✅ Sell order quantity updates on reentry
- ✅ Pending reentry cancellation on position closure
- ✅ Transaction safety (all multi-step operations wrapped)
- ✅ Database-level locking (prevents race conditions)

---

## Order Flow Documentation

### Buy Order Flow

#### New Entry Order Placement

**Trigger**: `AutoTradeEngine.place_new_entries()` (4:05 PM daily)

**Flow**:
1. Load Buy Recommendations
2. Duplicate Check
3. Validation
4. Place AMO Order
5. Database Persistence
6. Order Tracking

#### Reentry Order Placement

**Trigger**: `AutoTradeEngine.place_reentry_orders()` (during market hours)

**Flow**:
1. Check Reentry Conditions
2. Duplicate Check
3. Validation
4. Place Order
5. Database Persistence

### Sell Order Flow

**Trigger**: `AutoTradeEngine.check_and_place_sell_orders_for_new_holdings()` (continuous monitoring)

**Flow**:
1. Load Open Positions
2. Check Exit Conditions
3. Place Sell Order
4. Database Persistence
5. Order Tracking

### Position Tracking

- Positions created from executed buy orders
- Positions updated on reentry
- Positions closed on sell execution
- Full audit trail maintained

### Reentry Management

- Reentry detection based on RSI continuation
- Daily cap (max 1 reentry per symbol per day)
- Sell order quantity updates on reentry
- Pending reentry cancellation on position closure

### Manual Trade Reconciliation

- Periodic reconciliation (every 30 minutes)
- Lightweight reconciliation before critical operations
- Holdings API caching to reduce broker API calls
- Automatic detection of manual trades
- Position synchronization with broker holdings

### Analysis Deduplication

**Location:** `src/application/services/analysis_deduplication_service.py`

**Purpose:** Prevents duplicate signals within the same trading day window.

**Key Features:**
- Trading day window detection (9AM to next day 9AM, excluding weekends)
- Duplicate signal detection based on trading day
- Integration with signal persistence
- Prevents redundant analysis runs

---

## Flaw Analysis & Fixes

### Critical Flaws Fixed

#### Flaw #1: Lack of Transaction Safety ✅ FIXED

**Problem**: Multi-step operations committed separately, causing inconsistent state on failures.

**Solution**: All multi-step operations wrapped in transactions.

**Implementation**: Transaction utility implemented with automatic rollback on errors.

#### Flaw #2: Race Condition - Concurrent Reentry Executions ✅ FIXED

**Problem**: Multiple threads could process the same order concurrently, causing lost updates.

**Solution**: Database-level locking (`SELECT ... FOR UPDATE`).

**Implementation**: `get_by_symbol_for_update()` method added to `PositionsRepository`.

#### Flaw #3: Race Condition - Reentry During Sell Order Update ✅ FIXED

**Problem**: Sell order update could use stale position quantity if reentry executes concurrently.

**Solution**: Re-read position with locked read before updating sell order.

#### Flaw #4: Race Condition - Sell Execution During Reentry ✅ FIXED

**Problem**: Closed positions could be reopened by concurrent reentry.

**Solution**: Re-check `closed_at` with locked read before position update.

#### Flaw #5: Manual Trade Detection Timing ✅ FIXED

**Problem**: Manual trades detected too late, causing duplicate orders.

**Solution**:
- Reconciliation before reentry placement
- Periodic reconciliation every 30 minutes
- Lightweight reconciliation before sell order updates

### Medium Flaws Fixed

- ✅ Flaw #6: Partial Sell Execution + Reentry Race
- ✅ Flaw #7: Sell Order Update Failure Handling
- ✅ Flaw #8: Duplicate Reentry Detection Timing
- ✅ Flaw #9: No Rollback on Broker API Failure

---

## Flow Validation

### Buy Order Execution Flow (New Entry)

1. Order Placement (4:05 PM)
2. Order Monitoring (Market Hours)
3. Order Execution Processing
   - ✅ TRANSACTION START
   - ✅ LOCKED READ: `get_by_symbol_for_update()`
   - ✅ TRANSACTION COMMIT

### Reentry Order Execution Flow

1. Reentry Detection (4:05 PM)
2. Order Placement
3. Order Execution Processing
   - ✅ TRANSACTION START
   - ✅ LOCKED READ: `get_by_symbol_for_update()`
   - ✅ Sell order quantity update
   - ✅ TRANSACTION COMMIT

### Sell Order Execution Flow

1. Exit Condition Detection
2. Order Placement
3. Order Execution Processing
   - ✅ TRANSACTION START
   - ✅ Position closure
   - ✅ Pending reentry cancellation
   - ✅ TRANSACTION COMMIT

---

## Order Lifecycle Audit

### Order Creation/Placement

- ✅ `placed_at` - Set when order is created
- ✅ `status` - Set to `PENDING`
- ✅ `reason` - Set to "Order placed - waiting for market open"

### Order Status Check

- ✅ `last_status_check` - Updated on each status check

### Order Execution

- ✅ `execution_time` - Set when order is executed
- ✅ `filled_at` - Set when order is filled
- ✅ `status` - Updated to `EXECUTED`

### Order Cancellation

- ✅ `cancelled_at` - Set when order is cancelled
- ✅ `status` - Updated to `CANCELLED`
- ✅ `reason` - Updated with cancellation reason

### Order Rejection

- ✅ `rejected_at` - Set when order is rejected
- ✅ `status` - Updated to `REJECTED`
- ✅ `reason` - Updated with rejection reason

---

## Transaction Safety

### Implementation

All multi-step operations are wrapped in transactions:

```python
from src.infrastructure.db.transaction import transaction

@transaction
def process_order_execution(self, order_id: str):
    # Step 1: Update order status
    self.orders_repo.mark_executed(order_id)

    # Step 2: Create/update position
    self.positions_repo.upsert(...)

    # Step 3: Update sell order
    self.orders_repo.update_sell_order(...)

    # If any step fails, ALL changes are rolled back
```

### Benefits

- ✅ Atomicity: All operations succeed or fail together
- ✅ Consistency: Database always in valid state
- ✅ Error Recovery: Automatic rollback on failures

---

## Race Condition Fixes

### Database-Level Locking

**Implementation**: `SELECT ... FOR UPDATE`

```python
def get_by_symbol_for_update(self, user_id: int, symbol: str) -> Positions | None:
    """
    Get position by symbol with row-level lock.
    Prevents concurrent modifications.
    """
    stmt = (
        select(Positions)
        .where(Positions.user_id == user_id, Positions.symbol == symbol)
        .with_for_update()
    )
    return self.db.execute(stmt).scalar_one_or_none()
```

### Updated Operations

All position update operations now use locking:
- `_create_position_from_executed_order()`
- `upsert()`
- `update_quantity()`
- `close_position()`

---

## Troubleshooting

### Issue: Order Status Not Updating

**Solution**: Check order monitoring service is running and broker API is accessible.

### Issue: Position Quantity Mismatch

**Solution**: Run manual reconciliation to sync with broker holdings.

### Issue: Duplicate Orders

**Solution**: Check duplicate detection logic and ensure reconciliation runs before order placement.

---

## Related Documentation

- [Transaction Safety Explanation](./TRANSACTION_SAFETY_EXPLANATION.md) - Detailed transaction safety explanation
- [Race Condition Fix](./RACE_CONDITION_FIX.md) - Detailed race condition fix explanation
- [Re-entry Implementation](../reentry_implementation_complete.md) - Re-entry implementation details

---

**Note**: This document consolidates content from:
- `ORDER_MANAGEMENT_FLOW.md` - Complete flow documentation
- `ORDER_MANAGEMENT_FLOW_ANALYSIS.md` - Flaw analysis
- `ORDER_MANAGEMENT_FLOW_VALIDATION.md` - Flow validation
- `ORDER_MANAGEMENT_AUDIT.md` - Order lifecycle audit
