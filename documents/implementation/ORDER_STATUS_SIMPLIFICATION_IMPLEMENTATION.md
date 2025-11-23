# Order Status Simplification & Retry Filtration Implementation Guide

## Overview

This document provides a step-by-step guide for implementing:
1. **Order Status Simplification**: Reduce 9 statuses to 5 by merging similar statuses and using `side` column
2. **Retry Filtration Logic**: Implement expiry-based retry filtering (no keyword checks)

---

## Part 1: Order Status Simplification

### Current Statuses (9 - Before Simplification)
```python
class OrderStatus(str, Enum):
    AMO = "amo"
    PENDING_EXECUTION = "pending_execution"
    ONGOING = "ongoing"
    SELL = "sell"                    # ⚠️ Will be removed - use side='sell' instead
    CLOSED = "closed"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
```

### Target Statuses (5 - After Simplification)
```python
class OrderStatus(str, Enum):
    PENDING = "pending"              # Merged: AMO + PENDING_EXECUTION
    ONGOING = "ongoing"              # Unchanged
    CLOSED = "closed"                # Unchanged
    FAILED = "failed"                # Merged: FAILED + RETRY_PENDING + REJECTED
    CANCELLED = "cancelled"          # Unchanged
```

**Note**: `SELL` status is removed. Use `side` column (`'buy'` or `'sell'`) to distinguish order type.

### Changes Summary

| Merge | From | To | Rationale |
|-------|------|-----|-----------|
| 1 | `AMO` + `PENDING_EXECUTION` | `PENDING` | Both mean "order pending execution", no functional difference |
| 2 | `FAILED` + `RETRY_PENDING` + `REJECTED` | `FAILED` | All are failure states, distinction via `reason` field |
| 3 | `SELL` | **Removed** | Use `side` column (`'buy'`/`'sell'`) instead of separate status |

### Order Type vs Status

**Before**: Used `SELL` status to track sell orders
- Buy order: `PENDING` → `ONGOING` → `CLOSED`
- Sell order: `SELL` → `CLOSED`

**After**: Use `side` column to distinguish order type
- Buy order (`side='buy'`): `PENDING` → `ONGOING` → `CLOSED`
- Sell order (`side='sell'`): `PENDING` → `ONGOING` → `CLOSED`

**Benefits**:
- ✅ Unified status flow for both buy and sell orders
- ✅ Simpler logic (no special handling for SELL status)
- ✅ Uses existing `side` column (already in schema)
- ✅ Reduces from 9 to 5 statuses

---

## Part 1.1: Using Side Column for Order Type

### Current Approach (SELL Status)
```python
# Sell order tracked with SELL status
order.status = OrderStatus.SELL
order.side = "sell"
```

### New Approach (Side Column Only)
```python
# Sell order tracked with side column + standard status
order.status = OrderStatus.PENDING  # Same statuses as buy orders
order.side = "sell"  # Use side column to distinguish
```

### Querying Orders by Type

**Before**:
```python
# Get sell orders
sell_orders = [o for o in orders if o.status == OrderStatus.SELL]

# Get buy orders
buy_orders = [o for o in orders if o.status != OrderStatus.SELL]
```

**After**:
```python
# Get sell orders
sell_orders = [o for o in orders if o.side == "sell"]

# Get buy orders
buy_orders = [o for o in orders if o.side == "buy"]

# Get pending sell orders
pending_sell_orders = [
    o for o in orders
    if o.side == "sell" and o.status == OrderStatus.PENDING
]

# Get ongoing buy orders
ongoing_buy_orders = [
    o for o in orders
    if o.side == "buy" and o.status == OrderStatus.ONGOING
]
```

### Benefits
- ✅ Unified status flow for both buy and sell orders
- ✅ Simpler queries (filter by `side` instead of checking status)
- ✅ Consistent status semantics (PENDING means pending, regardless of buy/sell)
- ✅ One less status to manage

---

## Part 2: Unified Reason Field

### Current Fields
```python
class Orders(Base):
    failure_reason: str | None      # For FAILED/RETRY_PENDING
    rejection_reason: str | None     # For REJECTED
    cancelled_reason: str | None    # For CANCELLED
```

### Target Field
```python
class Orders(Base):
    reason: str | None  # Unified reason field for all states
```

### Migration Strategy
- Migrate `failure_reason` → `reason` (for FAILED/RETRY_PENDING orders)
- Migrate `rejection_reason` → `reason` (for REJECTED orders)
- Migrate `cancelled_reason` → `reason` (for CANCELLED orders)
- Set default `reason` for other states if needed (optional)

---

## Part 3: Retry Filtration Logic

### Key Principles
1. **All FAILED orders are retriable** until expiry
2. **No keyword-based filtering** (no "invalid_symbol", "not retryable" checks)
3. **Expiry-based**: Orders expire at next trading day market close (3:30 PM IST)
4. **Expired orders** are marked as `CANCELLED`

### Expiry Calculation
- Calculate next trading day from `first_failed_at`
- Skip weekends (Saturday, Sunday)
- Skip holidays (TODO: implement holiday calendar)
- Expiry time: 3:30 PM IST on next trading day

---

## Implementation Steps

### Step 1: Database Schema Changes

#### 1.1 Update OrderStatus Enum
**File**: `src/infrastructure/db/models.py`

**Important**: Remove `SELL` status entirely. Use `side` column (`'buy'` or `'sell'`) to distinguish order type.

```python
# Before (Current - 9 statuses)
class OrderStatus(str, Enum):
    AMO = "amo"
    PENDING_EXECUTION = "pending_execution"
    ONGOING = "ongoing"
    SELL = "sell"                    # ⚠️ REMOVE THIS - use side='sell' instead
    CLOSED = "closed"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

# After (Target - 5 statuses)
class OrderStatus(str, Enum):
    PENDING = "pending"              # Merged: AMO + PENDING_EXECUTION
    ONGOING = "ongoing"              # Unchanged
    CLOSED = "closed"                # Unchanged
    FAILED = "failed"                # Merged: FAILED + RETRY_PENDING + REJECTED
    CANCELLED = "cancelled"          # Unchanged
    # ✅ SELL removed - use side='sell' column to identify sell orders
```

#### 1.2 Add Unified Reason Field
**File**: `src/infrastructure/db/models.py`

```python
class Orders(Base):
    # ... existing fields ...

    # Add new unified reason field
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Keep old fields temporarily for migration (mark as deprecated)
    # failure_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)  # Deprecated
    # rejection_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)  # Deprecated
    # cancelled_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)  # Deprecated
```

#### 1.3 Create Alembic Migration
**File**: `alembic/versions/XXXXX_order_status_simplification.py`

```python
"""Order status simplification and unified reason field

Revision ID: XXXXX
Revises: YYYYY
Create Date: 2025-11-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

def upgrade() -> None:
    # Step 1: Add unified reason field
    op.add_column("orders", sa.Column("reason", sa.String(512), nullable=True))

    # Step 2: Migrate existing reason data
    # Migrate failure_reason → reason
    op.execute(sa.text("""
        UPDATE orders
        SET reason = failure_reason
        WHERE failure_reason IS NOT NULL AND reason IS NULL
    """))

    # Migrate rejection_reason → reason
    op.execute(sa.text("""
        UPDATE orders
        SET reason = rejection_reason
        WHERE rejection_reason IS NOT NULL AND reason IS NULL
    """))

    # Migrate cancelled_reason → reason
    op.execute(sa.text("""
        UPDATE orders
        SET reason = cancelled_reason
        WHERE cancelled_reason IS NOT NULL AND reason IS NULL
    """))

    # Step 3: Migrate status values
    # AMO → PENDING
    op.execute(sa.text("""
        UPDATE orders
        SET status = 'pending'
        WHERE status = 'amo'
    """))

    # PENDING_EXECUTION → PENDING
    op.execute(sa.text("""
        UPDATE orders
        SET status = 'pending'
        WHERE status = 'pending_execution'
    """))

    # RETRY_PENDING → FAILED
    op.execute(sa.text("""
        UPDATE orders
        SET status = 'failed'
        WHERE status = 'retry_pending'
    """))

    # REJECTED → FAILED
    op.execute(sa.text("""
        UPDATE orders
        SET status = 'failed'
        WHERE status = 'rejected'
    """))

    # SELL → PENDING (sell orders use side='sell' + status, not separate SELL status)
    op.execute(sa.text("""
        UPDATE orders
        SET status = 'pending'
        WHERE status = 'sell'
    """))

def downgrade() -> None:
    # Reverse migration (if needed)
    # Note: This may lose data if reason field had unified data
    op.execute(sa.text("""
        UPDATE orders
        SET status = 'amo'
        WHERE status = 'pending' AND placed_at < '2025-11-23'
    """))
    # ... reverse other status migrations ...

    op.drop_column("orders", "reason")
```

---

### Step 2: Update Repository Methods

#### 2.1 Update create_amo() Method
**File**: `src/infrastructure/persistence/orders_repository.py`

```python
# Before
def create_amo(...) -> Orders:
    order = Orders(
        ...
        status=OrderStatus.AMO,
        ...
    )

# After
def create_amo(
    ...,
    reason: str | None = None,  # Add reason parameter
) -> Orders:
    order = Orders(
        ...
        status=OrderStatus.PENDING,  # Changed from AMO
        reason=reason or "Order placed - waiting for market open",  # Set default reason
        ...
    )
```

#### 2.2 Update mark_failed() Method
**File**: `src/infrastructure/persistence/orders_repository.py`

```python
# Before
def mark_failed(
    self,
    order: Orders,
    failure_reason: str,
    retry_pending: bool = False,
) -> Orders:
    order.status = OrderStatus.RETRY_PENDING if retry_pending else OrderStatus.FAILED
    order.failure_reason = failure_reason
    ...

# After
def mark_failed(
    self,
    order: Orders,
    failure_reason: str,
    retry_pending: bool = False,  # Keep for backward compatibility, but not used
) -> Orders:
    order.status = OrderStatus.FAILED  # Always FAILED (no RETRY_PENDING)
    order.reason = failure_reason  # Use unified reason field
    if not order.first_failed_at:
        order.first_failed_at = ist_now()
    order.last_retry_attempt = ist_now()
    # Note: retry_pending parameter is ignored - all FAILED orders are retriable
    return self.update(order)
```

#### 2.3 Update mark_rejected() Method
**File**: `src/infrastructure/persistence/orders_repository.py`

```python
# Before
def mark_rejected(self, order: Orders, rejection_reason: str) -> Orders:
    order.status = OrderStatus.REJECTED
    order.rejection_reason = rejection_reason
    ...

# After
def mark_rejected(self, order: Orders, rejection_reason: str) -> Orders:
    order.status = OrderStatus.FAILED  # Changed from REJECTED
    order.reason = f"Broker rejected: {rejection_reason}"  # Use unified reason field
    ...
```

#### 2.4 Update mark_cancelled() Method
**File**: `src/infrastructure/persistence/orders_repository.py`

```python
# Before
def mark_cancelled(self, order: Orders, cancelled_reason: str | None = None) -> Orders:
    order.status = OrderStatus.CANCELLED
    order.cancelled_reason = cancelled_reason or "Cancelled"
    ...

# After
def mark_cancelled(self, order: Orders, cancelled_reason: str | None = None) -> Orders:
    order.status = OrderStatus.CANCELLED
    order.reason = cancelled_reason or "Cancelled"  # Use unified reason field
    ...
```

#### 2.5 Update mark_executed() Method
**File**: `src/infrastructure/persistence/orders_repository.py`

```python
# Before
def mark_executed(...) -> Orders:
    order.status = OrderStatus.ONGOING
    ...

# After
def mark_executed(
    self,
    order: Orders,
    execution_price: float,
    execution_qty: float | None = None,
) -> Orders:
    order.status = OrderStatus.ONGOING
    order.reason = f"Order executed at Rs {execution_price:.2f}"  # Set reason
    ...
```

#### 2.6 Update get_pending_amo_orders() Method
**File**: `src/infrastructure/persistence/orders_repository.py`

```python
# Before
def get_pending_amo_orders(self, user_id: int) -> list[Orders]:
    return self.list(user_id, status=OrderStatus.AMO) + \
           self.list(user_id, status=OrderStatus.PENDING_EXECUTION)

# After
def get_pending_amo_orders(self, user_id: int) -> list[Orders]:
    return self.list(user_id, status=OrderStatus.PENDING)
```

#### 2.7 Update get_failed_orders() Method
**File**: `src/infrastructure/persistence/orders_repository.py`

```python
# Before
def get_failed_orders(self, user_id: int) -> list[Orders]:
    return self.list(user_id, status=OrderStatus.RETRY_PENDING) + \
           self.list(user_id, status=OrderStatus.FAILED)

# After
def get_failed_orders(self, user_id: int) -> list[Orders]:
    return self.list(user_id, status=OrderStatus.FAILED)
```

#### 2.8 Add get_retriable_failed_orders() Method
**File**: `src/infrastructure/persistence/orders_repository.py`

```python
def get_retriable_failed_orders(self, user_id: int) -> list[Orders]:
    """
    Get FAILED orders that are eligible for retry.
    Applies expiry filter - excludes expired orders.

    Returns:
        List of FAILED orders that haven't expired yet
    """
    from datetime import datetime, time, timedelta
    from src.infrastructure.db.timezone_utils import ist_now

    # Get all FAILED orders
    all_failed = self.list(user_id, status=OrderStatus.FAILED)

    # Apply expiry filter
    retriable_orders = []
    now = ist_now()
    MARKET_CLOSE_TIME = time(15, 30)  # 3:30 PM IST

    for order in all_failed:
        if not order.first_failed_at:
            # No expiry date - include (shouldn't happen, but handle gracefully)
            retriable_orders.append(order)
            continue

        # Calculate next trading day market close
        next_day = order.first_failed_at.date() + timedelta(days=1)

        # Skip weekends (Saturday=5, Sunday=6)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)

        # TODO: Skip holidays (add holiday checking logic)

        # Calculate expiry datetime
        next_trading_day_close = datetime.combine(next_day, MARKET_CLOSE_TIME)

        # Check if expired
        if now > next_trading_day_close:
            # Order expired - mark as CANCELLED
            self.mark_cancelled(
                order,
                f"Order expired - past next trading day market close ({next_trading_day_close.strftime('%Y-%m-%d %H:%M')})"
            )
            continue

        # Order hasn't expired - eligible for retry
        retriable_orders.append(order)

    return retriable_orders
```

---

### Step 3: Update AutoTradeEngine

#### 3.1 Update place_new_entries() Method
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Changes**:
1. Update status checks from `AMO`/`PENDING_EXECUTION` to `PENDING`
2. Update status checks from `RETRY_PENDING`/`REJECTED` to `FAILED`
3. Remove `CLOSED` and `CANCELLED` from blocking status set
4. Ensure all status checks filter by `side == "buy"` (sell orders don't block buy orders)

```python
# Before
if existing_order.status in {
    DbOrderStatus.AMO,
    DbOrderStatus.PENDING_EXECUTION,
    DbOrderStatus.ONGOING,
    DbOrderStatus.FAILED,
    DbOrderStatus.RETRY_PENDING,
    DbOrderStatus.REJECTED,
}:

# After
if existing_order.status in {
    DbOrderStatus.PENDING,  # Merged: AMO + PENDING_EXECUTION
    DbOrderStatus.ONGOING,
    DbOrderStatus.FAILED,   # Merged: FAILED + RETRY_PENDING + REJECTED
    # Note: CLOSED and CANCELLED are NOT included (allow new orders)
}:
```

#### 3.2 Update retry_pending_orders_from_db() Method
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

```python
# Before
def retry_pending_orders_from_db(self) -> dict[str, int]:
    retry_pending_orders = self.orders_repo.get_failed_orders(self.user_id)
    retry_pending_orders = [
        o for o in retry_pending_orders
        if o.status == DbOrderStatus.RETRY_PENDING
    ]

# After
def retry_pending_orders_from_db(self) -> dict[str, int]:
    # Get retriable FAILED orders (expiry filter applied)
    retry_pending_orders = self.orders_repo.get_retriable_failed_orders(self.user_id)

    # No need to filter by status - all returned orders are retriable
    # Expired orders are already marked as CANCELLED by get_retriable_failed_orders()
```

#### 3.3 Update _sync_order_status_snapshot() Method
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

```python
# Before
elif status_lower in {
    "pending", "open", "trigger_pending", "partially_filled", "partially filled",
}:
    if db_order.status != DbOrderStatus.PENDING_EXECUTION:
        self.orders_repo.update(db_order, status=DbOrderStatus.PENDING_EXECUTION)

# After
elif status_lower in {
    "pending", "open", "trigger_pending", "partially_filled", "partially filled",
}:
    if db_order.status != DbOrderStatus.PENDING:
        self.orders_repo.update(db_order, status=DbOrderStatus.PENDING)
```

#### 3.4 Update _add_failed_order() Method
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

```python
# Before
self.orders_repo.mark_failed(
    order=order,
    failure_reason=failure_reason_str,
    retry_pending=retry_pending,
)

# After
self.orders_repo.mark_failed(
    order=order,
    failure_reason=failure_reason_str,
    # retry_pending parameter is ignored - all FAILED orders are retriable
)
```

---

### Step 4: Update Sell Order Logic

#### 4.1 Update Sell Order Placement
**File**: `modules/kotak_neo_auto_trader/sell_engine.py` (or similar)

```python
# Before: Create sell order with SELL status
sell_order = orders_repo.create_amo(
    ...,
    side="sell",
    status=OrderStatus.SELL,  # Special status for sell
)

# After: Create sell order with PENDING status
sell_order = orders_repo.create_amo(
    ...,
    side="sell",
    status=OrderStatus.PENDING,  # Same status as buy orders
    reason="Sell order placed at EMA9 target",
)
```

#### 4.2 Update Sell Order Monitoring
**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` (or similar)

```python
# Before: Query sell orders by status
sell_orders = [o for o in orders if o.status == OrderStatus.SELL]

# After: Query sell orders by side
sell_orders = [
    o for o in orders
    if o.side == "sell" and o.status == OrderStatus.PENDING
]
```

### Step 5: Update OrderTracker

#### 5.1 Update add_pending_order() Method
**File**: `modules/kotak_neo_auto_trader/order_tracker.py`

```python
# Before
db_order = self.orders_repo.create_amo(...)
if variety == "AMO":
    db_order.status = DbOrderStatus.PENDING_EXECUTION
    self.orders_repo.update(db_order)

# After
db_order = self.orders_repo.create_amo(
    ...,
    reason="Order placed - waiting for market open",  # Set reason
)
# No need to update status - create_amo() already sets PENDING
```

#### 5.2 Update update_order_status() Method
**File**: `modules/kotak_neo_auto_trader/order_tracker.py`

```python
# Before
status_map = {
    "EXECUTED": DbOrderStatus.ONGOING,
    "REJECTED": DbOrderStatus.REJECTED,
    "CANCELLED": DbOrderStatus.CLOSED,
    "PENDING": DbOrderStatus.PENDING_EXECUTION,
    "OPEN": DbOrderStatus.PENDING_EXECUTION,
}

# After
status_map = {
    "EXECUTED": DbOrderStatus.ONGOING,
    "REJECTED": DbOrderStatus.FAILED,  # Changed from REJECTED
    "CANCELLED": DbOrderStatus.CANCELLED,  # Changed from CLOSED
    "PENDING": DbOrderStatus.PENDING,  # Changed from PENDING_EXECUTION
    "OPEN": DbOrderStatus.PENDING,  # Changed from PENDING_EXECUTION
}
```

---

### Step 6: Update OrderStateManager

#### 6.1 Update sync_with_broker() Method
**File**: `modules/kotak_neo_auto_trader/order_state_manager.py`

```python
# Before
elif status == OrderStatus.REJECTED:
    self.orders_repo.mark_rejected(db_order, rejection_reason)

# After
elif status == OrderStatus.REJECTED:
    # REJECTED is now mapped to FAILED
    self.orders_repo.mark_rejected(db_order, rejection_reason)
    # mark_rejected() now sets status to FAILED internally
```

---

### Step 7: Update API/Frontend

#### 7.1 Update API Schema
**File**: `src/api/schemas/orders.py` (or similar)

```python
# Before
class OrderStatus(str, Enum):
    amo = "amo"
    pending_execution = "pending_execution"
    ongoing = "ongoing"
    sell = "sell"
    closed = "closed"
    failed = "failed"
    retry_pending = "retry_pending"
    rejected = "rejected"
    cancelled = "cancelled"

# After
class OrderStatus(str, Enum):
    pending = "pending"
    ongoing = "ongoing"
    closed = "closed"
    failed = "failed"
    cancelled = "cancelled"
    # Note: SELL removed - use side='sell' to identify sell orders
```

#### 7.2 Update Frontend Types
**File**: `web/src/api/orders.ts` (or similar)

```typescript
// Before
export type OrderStatus =
  | 'amo'
  | 'pending_execution'
  | 'ongoing'
  | 'sell'
  | 'closed'
  | 'failed'
  | 'retry_pending'
  | 'rejected'
  | 'cancelled';

// After
export type OrderStatus =
  | 'pending'
  | 'ongoing'
  | 'closed'
  | 'failed'
  | 'cancelled';
  // Note: 'sell' removed - use side='sell' to identify sell orders
```

#### 7.3 Update Frontend Filtering Logic
**File**: `web/src/routes/dashboard/OrdersPage.tsx` (or similar)

```typescript
// Before: Filter by status
const sellOrders = orders.filter(o => o.status === 'sell');

// After: Filter by side
const sellOrders = orders.filter(o => o.side === 'sell');
const buyOrders = orders.filter(o => o.side === 'buy');
```

---

### Step 8: Update Tests

#### 8.1 Update Test Fixtures
- Replace `OrderStatus.AMO` with `OrderStatus.PENDING`
- Replace `OrderStatus.PENDING_EXECUTION` with `OrderStatus.PENDING`
- Replace `OrderStatus.RETRY_PENDING` with `OrderStatus.FAILED`
- Replace `OrderStatus.REJECTED` with `OrderStatus.FAILED`
- Replace `OrderStatus.SELL` with `OrderStatus.PENDING` (for sell orders, use `side='sell'`)

#### 8.2 Update Test Assertions
- Update all status assertions to use new statuses
- Update reason field assertions (use `reason` instead of `failure_reason`/`rejection_reason`/`cancelled_reason`)

#### 8.3 Add Tests for Retry Filtration
- Test expiry calculation (next trading day, skip weekends)
- Test expired orders are marked as CANCELLED
- Test non-expired orders remain FAILED and retriable

---

## Part 3: Retry Filtration Implementation

### 3.1 Helper Function: get_next_trading_day_close()

**File**: `modules/kotak_neo_auto_trader/utils/trading_day_utils.py` (new file)

```python
"""Trading day utility functions"""

from datetime import datetime, time, timedelta
from src.infrastructure.db.timezone_utils import ist_now

MARKET_CLOSE_TIME = time(15, 30)  # 3:30 PM IST

def get_next_trading_day_close(failed_at: datetime) -> datetime:
    """
    Calculate next trading day market close from failure time.
    Excludes weekends and holidays.

    Args:
        failed_at: When order failed (datetime)

    Returns:
        datetime: Next trading day market close (3:30 PM IST)

    Example:
        - failed_at: Monday 4:05 PM → Returns: Tuesday 3:30 PM
        - failed_at: Friday 4:05 PM → Returns: Monday 3:30 PM (skip weekend)
    """
    # Start from day after failure
    next_day = failed_at.date() + timedelta(days=1)

    # Skip weekends (Saturday=5, Sunday=6)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)

    # TODO: Skip holidays (add holiday checking logic)
    # For now, just skip weekends

    # Return market close time on next trading day
    return datetime.combine(next_day, MARKET_CLOSE_TIME)

def is_trading_day(check_date: datetime | None = None) -> bool:
    """
    Check if a date is a trading day (Mon-Fri, excluding holidays).

    Args:
        check_date: Date to check (defaults to today)

    Returns:
        True if trading day, False otherwise
    """
    if check_date is None:
        check_date = ist_now()

    # Check if weekday (Monday=0, Sunday=6)
    weekday = check_date.weekday()
    if weekday >= 5:  # Saturday or Sunday
        return False

    # TODO: Add holiday checking logic
    # For now, just check weekday

    return True
```

### 3.2 Update retry_pending_orders_from_db()

**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

```python
def retry_pending_orders_from_db(self) -> dict[str, int]:
    """
    Retry FAILED orders that haven't expired.
    Called by premarket retry task at scheduled time (8:00 AM).

    Returns:
        Summary dict with retry statistics
    """
    summary = {
        "retried": 0,
        "placed": 0,
        "failed": 0,
        "skipped": 0,
    }

    if not self.orders_repo or not self.user_id:
        logger.debug("Cannot retry orders: DB not available or user_id not set")
        return summary

    try:
        # Get retriable FAILED orders (expiry filter applied)
        retriable_orders = self.orders_repo.get_retriable_failed_orders(self.user_id)

        if not retriable_orders:
            logger.info("No retriable FAILED orders to retry")
            return summary

        logger.info(
            f"Found {len(retriable_orders)} retriable FAILED orders to retry"
        )

        # Check portfolio limit
        try:
            current_count = len(self.current_symbols_in_portfolio())
        except Exception:
            current_count = self.portfolio_size()

        for db_order in retriable_orders:
            summary["retried"] += 1
            symbol = db_order.symbol

            # Runtime filters (same as current logic):
            # 1. Portfolio limit check
            # 2. Already in holdings check
            # 3. Missing indicators check
            # 4. Invalid price check
            # 5. Manual order check
            # 6. Active order check
            # 7. Position-to-volume ratio check
            # 8. Balance check

            # ... (rest of retry logic remains the same)

            # If retry succeeds:
            #   - Update status to PENDING
            #   - Update reason: "Order retried successfully"
            # If retry fails:
            #   - Keep status as FAILED
            #   - Increment retry_count
            #   - Update last_retry_attempt

        logger.info(
            f"Retry summary: {summary['placed']} placed, {summary['failed']} failed, "
            f"{summary['skipped']} skipped"
        )

    except Exception as e:
        logger.error(f"Error during retry: {e}", exc_info=e)

    return summary
```

---

## Part 4: Testing Checklist

### 4.1 Status Migration Tests
- [ ] Test AMO → PENDING migration
- [ ] Test PENDING_EXECUTION → PENDING migration
- [ ] Test RETRY_PENDING → FAILED migration
- [ ] Test REJECTED → FAILED migration
- [ ] Test reason field migration (failure_reason → reason)
- [ ] Test reason field migration (rejection_reason → reason)
- [ ] Test reason field migration (cancelled_reason → reason)

### 4.2 Retry Filtration Tests
- [ ] Test expiry calculation (next trading day)
- [ ] Test weekend skipping (Friday → Monday)
- [ ] Test expired orders marked as CANCELLED
- [ ] Test non-expired orders remain FAILED
- [ ] Test retry logic with expired orders (should skip)
- [ ] Test retry logic with non-expired orders (should retry)

### 4.3 Integration Tests
- [ ] Test buy order placement flow (AMO → PENDING, side='buy')
- [ ] Test sell order placement flow (PENDING, side='sell')
- [ ] Test order execution flow (PENDING → ONGOING, for both buy and sell)
- [ ] Test order failure flow (PENDING → FAILED)
- [ ] Test order rejection flow (PENDING → FAILED with rejection reason)
- [ ] Test retry flow (FAILED → PENDING on successful retry)
- [ ] Test expiry flow (FAILED → CANCELLED on expiry)
- [ ] Test sell order monitoring (filter by side='sell' + status)

### 4.4 Regression Tests
- [ ] Test duplicate prevention still works
- [ ] Test portfolio limit still works
- [ ] Test balance check still works
- [ ] Test holdings check still works
- [ ] Test manual order detection still works

---

## Part 5: Rollout Plan

### Phase 1: Database Migration (Low Risk)
1. Add `reason` column (nullable)
2. Migrate existing reason data
3. Verify data migration

### Phase 2: Code Updates (Medium Risk)
1. Update enum definition
2. Update repository methods
3. Update AutoTradeEngine
4. Update OrderTracker
5. Update OrderStateManager

### Phase 3: API/Frontend Updates (Medium Risk)
1. Update API schema
2. Update frontend types
3. Update UI components

### Phase 4: Testing (High Priority)
1. Run unit tests
2. Run integration tests
3. Run regression tests
4. Manual testing

### Phase 5: Deployment
1. Deploy database migration
2. Deploy code changes
3. Monitor for issues
4. Rollback plan ready

---

## Part 6: Rollback Plan

### If Issues Detected

#### Database Rollback
```sql
-- Reverse status migrations
UPDATE orders SET status = 'amo' WHERE status = 'pending' AND placed_at < '2025-11-23';
UPDATE orders SET status = 'pending_execution' WHERE status = 'pending' AND placed_at >= '2025-11-23';
UPDATE orders SET status = 'retry_pending' WHERE status = 'failed' AND first_failed_at IS NOT NULL;
UPDATE orders SET status = 'rejected' WHERE status = 'failed' AND reason LIKE 'Broker rejected:%';

-- Restore old reason fields (if data was preserved)
UPDATE orders SET failure_reason = reason WHERE status IN ('failed', 'retry_pending');
UPDATE orders SET rejection_reason = reason WHERE status = 'rejected';
UPDATE orders SET cancelled_reason = reason WHERE status = 'cancelled';
```

#### Code Rollback
- Revert enum changes
- Revert repository method changes
- Revert AutoTradeEngine changes
- Deploy previous version

---

## Part 7: Key Points to Remember

1. **No keyword-based filtering**: All FAILED orders are retriable until expiry
2. **Expiry is the only filter**: Orders expire at next trading day market close
3. **Expired orders are CANCELLED**: Not kept as FAILED
4. **Unified reason field**: All states use `reason` field
5. **Use side column for order type**: No separate SELL status - use `side='sell'` + standard statuses
6. **Unified status flow**: Both buy and sell orders use same statuses (PENDING, ONGOING, CLOSED, etc.)
7. **Backward compatibility**: Keep old fields temporarily during migration
8. **Testing is critical**: Test all scenarios before deployment

---

## Part 8: Configuration

### Configurable Parameters

```python
# Market close time
MARKET_CLOSE_TIME = time(15, 30)  # 3:30 PM IST

# Retry schedule
PREMARKET_RETRY_TIME = time(8, 0)  # 8:00 AM IST
```

### Future Enhancements

1. **Holiday Calendar**: Add holiday checking logic to `get_next_trading_day_close()`
2. **Custom Expiry**: Allow configurable expiry time per order type
3. **Retry Limits**: Add optional retry count limits (if needed in future)
4. **Reason Templates**: Standardize reason messages for better filtering

---

*Last Updated: November 23, 2025*
