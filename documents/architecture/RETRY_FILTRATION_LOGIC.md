# Retry Filtration Logic - Detailed Explanation

## Overview

With the simplified approach (all `FAILED` orders are retriable), the pre-market retry job needs to **filter** which `FAILED` orders should be retried. This document explains how filtration works.

---

## Current Retry Logic (Before Simplification)

### Current Approach
```python
# Step 1: Query only RETRY_PENDING orders
retry_pending_orders = self.orders_repo.get_failed_orders(self.user_id)
retry_pending_orders = [
    o for o in retry_pending_orders
    if o.status == DbOrderStatus.RETRY_PENDING  # ← Status-based filter
]

# Step 2: For each order, perform runtime checks
for db_order in retry_pending_orders:
    # Runtime filters (applied during retry):
    # 1. Portfolio limit check
    # 2. Already in holdings check
    # 3. Missing indicators check
    # 4. Invalid price check
    # 5. Manual order check
    # 6. Active order check
    # 7. Position-to-volume ratio check
    # 8. Balance check
```

**Current Filter**: Status-based (only `RETRY_PENDING` orders are queried)

---

## Proposed Retry Logic (After Simplification)

### Two-Level Filtration Strategy

With all `FAILED` orders being retriable, we need **two levels of filtration**:

1. **Query-Level Filtration** (Early filtering - before processing)
   - Filter at database query level
   - Exclude orders that should never be retried
   - Reduces processing overhead

2. **Runtime Filtration** (During retry - per order)
   - Filter based on current conditions
   - Applied during retry attempt
   - Same as current runtime checks

---

## Level 1: Query-Level Filtration

### Purpose
Filter out orders that have expired before processing begins.

### Filter Criteria

#### 1. **Expiry Check** (Next Trading Day Market Close)
```python
# Orders expire at next trading day market close (3:30 PM IST)
# Excludes weekends and holidays
MARKET_CLOSE_TIME = time(15, 30)  # 3:30 PM IST
```

**Logic**:
- Calculate next trading day from `first_failed_at` (skip weekends and holidays)
- Order expires at 3:30 PM IST on that next trading day
- **Expired orders are marked as CANCELLED** (not kept as FAILED)
- After expiry, order is no longer retriable

**Example**:
- Order failed: `Monday 4:05 PM`
  - Next trading day: `Tuesday`
  - Expiry: `Tuesday 3:30 PM`
  - Status: **FAILED** (retriable before Tuesday 3:30 PM)
  - Status: **CANCELLED** (after Tuesday 3:30 PM - expired)

- Order failed: `Friday 4:05 PM`
  - Next trading day: `Monday` (skip weekend)
  - Expiry: `Monday 3:30 PM`
  - Status: **FAILED** (retriable before Monday 3:30 PM)
  - Status: **CANCELLED** (after Monday 3:30 PM - expired)

- Order failed: `Thursday 4:05 PM` (if Friday is holiday)
  - Next trading day: `Monday` (skip Friday holiday + weekend)
  - Expiry: `Monday 3:30 PM`
  - Status: **FAILED** (retriable before Monday 3:30 PM)
  - Status: **CANCELLED** (after Monday 3:30 PM - expired)

### Query-Level Filter Implementation

```python
def get_retriable_failed_orders(self, user_id: int) -> list[Orders]:
    """
    Get FAILED orders that are eligible for retry.
    Applies query-level filters to exclude orders that should never be retried.
    """
    from datetime import datetime, timedelta
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus

    # Get all FAILED orders
    all_failed = self.orders_repo.list(user_id, status=DbOrderStatus.FAILED)

    # Apply query-level filters
    retriable_orders = []

    for order in all_failed:
        # Filter 1: Mark expired orders as CANCELLED and skip
        if order.first_failed_at:
            next_trading_day_close = get_next_trading_day_close(order.first_failed_at)
            if datetime.now() > next_trading_day_close:
                # Order expired - mark as CANCELLED
                self.orders_repo.mark_cancelled(
                    order,
                    f"Order expired - past next trading day market close ({next_trading_day_close.strftime('%Y-%m-%d %H:%M')})"
                )
                continue  # Skip expired orders

        # Order passed filter - eligible for retry (status remains FAILED)
        retriable_orders.append(order)

    return retriable_orders
```

### Benefits of Query-Level Filtration

1. **Performance**: Reduces processing overhead (fewer orders to process)
2. **Efficiency**: Excludes expired orders early
3. **Clarity**: Clear expiry logic - orders expire at next trading day market close

---

## Level 2: Runtime Filtration

### Purpose
Filter orders based on **current conditions** during the retry attempt.

### Filter Criteria (Same as Current Logic)

#### 1. **Portfolio Limit Check**
```python
if current_count >= max_portfolio_size:
    # Skip - portfolio limit reached
    break  # Stop processing remaining orders
```

#### 2. **Already in Holdings Check**
```python
if already_in_holdings:
    # Skip - order no longer needed
    mark_as_cancelled(order, "Already in holdings")
    continue
```

#### 3. **Missing Indicators Check**
```python
if not ind or missing_required_indicators(ind):
    # Skip - cannot validate order
    continue
```

#### 4. **Invalid Price Check**
```python
if close <= 0:
    # Skip - invalid price
    continue
```

#### 5. **Manual Order Check**
```python
if has_manual_order:
    # Skip - link manual order to DB
    update_status_to_pending_execution(order)
    continue
```

#### 6. **Active Order Check**
```python
if has_active_buy_order:
    # Skip - duplicate prevention
    continue
```

#### 7. **Position-to-Volume Ratio Check**
```python
if not check_position_volume_ratio(qty, avg_vol, symbol, close):
    # Skip - position too large
    # Order remains FAILED, will be retried next time if conditions change
    continue
```

#### 8. **Balance Check**
```python
if affordable < MIN_QTY or qty > affordable:
    # Skip - still insufficient balance
    increment_retry_count(order)
    continue  # Will be retried next time
```

### Runtime Filter Implementation

```python
def retry_pending_orders_from_db(self) -> dict[str, int]:
    """
    Retry FAILED orders that passed query-level filters.
    Applies runtime filters during retry attempt.
    """
    # Step 1: Get retriable orders (query-level filter applied)
    retriable_orders = self.orders_repo.get_retriable_failed_orders(self.user_id)

    for db_order in retriable_orders:
        # Step 2: Apply runtime filters (same as current logic)
        # 1. Portfolio limit check
        # 2. Already in holdings check
        # 3. Missing indicators check
        # 4. Invalid price check
        # 5. Manual order check
        # 6. Active order check
        # 7. Position-to-volume ratio check
        # 8. Balance check

        # If all runtime checks pass, attempt retry
        success, order_id = self._attempt_place_order(...)
        if success:
            update_status_to_pending_execution(db_order)
        else:
            increment_retry_count(db_order)
```

---

## Complete Filtration Flow

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Query All FAILED Orders                             │
│ SELECT * FROM orders WHERE status = 'FAILED'                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Query-Level Filtration (Early Filter)              │
│                                                              │
│ Filter 1: Expiry Check                                       │
│   ✅ now < next_trading_day_close → Keep as FAILED           │
│   ❌ now >= next_trading_day_close → Mark as CANCELLED       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Retriable Orders (Passed Query-Level Filters)       │
│ [Order1, Order2, Order3, ...]                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Runtime Filtration (Per Order)                      │
│                                                              │
│ For each order:                                             │
│   ✅ Portfolio limit check                                   │
│   ✅ Already in holdings check                               │
│   ✅ Missing indicators check                                │
│   ✅ Invalid price check                                     │
│   ✅ Manual order check                                      │
│   ✅ Active order check                                      │
│   ✅ Position-to-volume ratio check                         │
│   ✅ Balance check                                           │
│                                                              │
│ If all checks pass → Attempt retry                          │
│ If any check fails → Skip (may retry next time)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Retry Attempt                                        │
│                                                              │
│ Success → Update to PENDING                                 │
│ Failure → Increment retry_count, keep as FAILED             │
└─────────────────────────────────────────────────────────────┘
```

---

## Example Scenarios

### Scenario 1: Insufficient Balance (Retriable)
```
Order:
  status: FAILED
  reason: "Insufficient balance - shortfall: Rs 5,000"
  retry_count: 2
  first_failed_at: Monday 4:05 PM

Query-Level Filter:
  ✅ Check expiry: now (Tuesday 8:00 AM) < Tuesday 3:30 PM → PASS

Runtime Filter:
  ✅ Portfolio limit: OK
  ✅ Already in holdings: No
  ✅ Indicators: Available
  ✅ Price: Valid
  ✅ Balance: Still insufficient → SKIP (increment retry_count)

Result: Order skipped this time, will retry next time (retry_count = 3)
```

### Scenario 2: Expired Order (Query-Level Filter)
```
Order:
  status: FAILED
  reason: "Insufficient balance - shortfall: Rs 5,000"
  retry_count: 5
  first_failed_at: Monday 4:05 PM
  Current time: Tuesday 4:00 PM (after market close)

Query-Level Filter:
  ❌ Check expiry: now (Tuesday 4:00 PM) >= Tuesday 3:30 PM → Mark as CANCELLED

Result: Order marked as CANCELLED (expired at next trading day market close)
```

### Scenario 3: Weekend Handling (Query-Level Filter)
```
Order:
  status: FAILED
  reason: "Insufficient balance - shortfall: Rs 5,000"
  retry_count: 1
  first_failed_at: Friday 4:05 PM
  Current time: Monday 8:00 AM (before market close)

Query-Level Filter:
  ✅ Check expiry: now (Monday 8:00 AM) < Monday 3:30 PM → PASS

Result: Order eligible for retry (next trading day is Monday, expires at 3:30 PM)
```

### Scenario 4: Successful Retry
```
Order:
  status: FAILED
  reason: "Insufficient balance - shortfall: Rs 5,000"
  retry_count: 1
  first_failed_at: Monday 4:05 PM
  Current time: Tuesday 8:00 AM

Query-Level Filter:
  ✅ Check expiry: now (Tuesday 8:00 AM) < Tuesday 3:30 PM → PASS

Runtime Filter:
  ✅ All checks pass → Attempt retry

Retry Attempt:
  ✅ Balance now sufficient → Order placed successfully

Result: Order updated to PENDING status
```

### Scenario 5: Holiday Handling
```
Order:
  status: FAILED
  reason: "Insufficient balance - shortfall: Rs 5,000"
  retry_count: 0
  first_failed_at: Thursday 4:05 PM
  Next day: Friday (holiday)
  Next trading day: Monday

Query-Level Filter:
  ✅ Check expiry: now (Monday 8:00 AM) < Monday 3:30 PM → PASS

Result: Order eligible for retry (skipped Friday holiday, expires Monday 3:30 PM)
```

---

## Configuration Parameters

### Query-Level Filter Parameters
```python
# Market close time
MARKET_CLOSE_TIME = time(15, 30)  # 3:30 PM IST

# Helper function to calculate next trading day market close
def get_next_trading_day_close(failed_at: datetime) -> datetime:
    """
    Calculate next trading day market close from failure time.
    Excludes weekends and holidays.

    Args:
        failed_at: When order failed

    Returns:
        datetime: Next trading day market close (3:30 PM IST)
    """
    from datetime import timedelta

    # Start from day after failure
    next_day = failed_at.date() + timedelta(days=1)

    # Skip weekends (Saturday=5, Sunday=6)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)

    # TODO: Skip holidays (add holiday checking logic)
    # For now, just skip weekends

    # Return market close time on next trading day
    return datetime.combine(next_day, MARKET_CLOSE_TIME)
```

### Runtime Filter Parameters
- Same as current logic (portfolio limit, balance, etc.)

---

## Benefits of Two-Level Filtration

1. **Performance**: Query-level filter reduces processing overhead
2. **Efficiency**: Excludes orders that will never succeed early
3. **Flexibility**: Runtime filters handle dynamic conditions
4. **Clarity**: Clear separation between permanent and temporary failures
5. **Maintainability**: Easy to adjust filter criteria

---

## Summary

**Query-Level Filtration** (Early):
- Filters orders that have expired
- Based on: expiry (next trading day market close)
- **No retry count limit** - all orders are retriable regardless of retry_count
- **No keyword-based filtering** - all FAILED orders are retriable until expiry
- **Expiry**: Orders expire at next trading day market close (3:30 PM IST), excluding weekends and holidays
- **Status Changes**: Expired orders are marked as **CANCELLED** (not kept as FAILED)
- Applied before processing begins

**Runtime Filtration** (During Retry):
- Filters orders based on **current conditions**
- Based on: portfolio limit, holdings, indicators, balance, etc.
- Applied during retry attempt

**Key Changes from Original Design**:
1. ✅ **Removed retry count limit** - orders can be retried unlimited times (until expiry)
2. ✅ **Expiry based on next trading day market close** - not calendar days
3. ✅ **Weekend and holiday handling** - automatically skips non-trading days
4. ✅ **No keyword-based filtering** - all FAILED orders are retriable until expiry (no "invalid_symbol", "not retryable" checks)
5. ✅ **Status management** - expired orders are marked as **CANCELLED**, not kept as FAILED
6. ✅ **No new statuses** - only existing statuses (FAILED, CANCELLED) are used

**Result**: Only orders that pass both levels are retried, ensuring efficient and accurate retry logic. Orders remain retriable (status = FAILED) until next trading day market close, regardless of retry count or failure reason. Expired orders are automatically marked as CANCELLED.

---

*Last Updated: November 23, 2025*
