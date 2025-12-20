# Duplicate Order Prevention Mechanisms

## Overview

The system uses multiple layers of duplicate prevention to ensure orders are not placed multiple times for the same symbol. This document explains how duplicate prevention works during manual retry, pre-market retry, and regular order placement.

## Duplicate Prevention Layers

### Layer 1: Holdings Check (Broker API)

**Method**: `has_holding(symbol)`

**How it works**:
- Queries broker API for current holdings
- Checks if symbol (with all variants: `-EQ`, `-BE`, `-BL`, `-BZ`) already exists in holdings
- Returns `True` if symbol is already owned

**Used in**:
- `retry_pending_orders_from_db()` - Line 2132
- `place_new_entries()` - Line 2535
- `evaluate_reentries_and_exits()` - Line 3001

**Behavior**:
- If already in holdings → **Skip order placement**
- In retry: Marks order as CANCELLED with reason "Already in holdings"
- In new placement: Skips with reason "already_in_holdings"

### Layer 2: Active Buy Order Check (Broker API)

**Method**: `has_active_buy_order(symbol)`

**How it works**:
- Queries broker API for pending orders
- Checks if there's an active BUY order for the symbol (with all variants)
- Returns `True` if pending buy order exists

**Used in**:
- `retry_pending_orders_from_db()` - Line 2140
- `place_new_entries()` - Line 2543
- `evaluate_reentries_and_exits()` - Line 3001

**Behavior**:
- **In `place_new_entries()`**: Cancels existing pending buy order and replaces it
  ```python
  if self.has_active_buy_order(broker_symbol):
      cancelled = self.orders.cancel_pending_buys_for_symbol(variants)
      # Then places new order
  ```

- **In `retry_pending_orders_from_db()`**: Just skips (does NOT cancel)
  ```python
  if self.has_active_buy_order(symbol):
      logger.info(f"Skipping retry for {symbol}: already has pending buy order")
      summary["skipped"] += 1
      continue
  ```

### Layer 3: Database Check (Fallback)

**Used in**: `place_new_entries()` only (when holdings API fails)

**How it works**:
- When holdings API fails after retries, checks database for existing orders
- Queries `orders` table for pending/ongoing buy orders for the same symbol
- SQL query:
  ```sql
  SELECT COUNT(*) as count
  FROM orders
  WHERE user_id = :user_id
  AND symbol = :symbol
  AND side = 'buy'
  AND status IN ('amo', 'ongoing')
  ```

**Behavior**:
- If existing orders found → **Abort to prevent duplicates**
- If no existing orders → Proceed with warning (rely on broker-side validation)

**Not used in**: `retry_pending_orders_from_db()` - relies only on broker API checks

### Layer 4: Order ID Duplicate Check (Database)

**Method**: `add_pending_order()` in `OrderTracker`

**How it works**:
- Before adding order to database, checks if order with same `order_id` already exists
- Queries database: `get_by_broker_order_id()` or `get_by_order_id()`

**Behavior**:
- If order_id exists → Skip duplicate add
- If order_id doesn't exist → Create new order

**Used in**: All order placement paths (via `add_pending_order()`)

## Current Implementation by Scenario

### Scenario 1: Pre-Market Retry (`retry_pending_orders_from_db()`)

**Duplicate Prevention**:
1. ✅ Checks holdings via `has_holding()` - **Skips if already owned**
2. ✅ Checks active buy orders via `has_active_buy_order()` - **Skips if pending order exists**
3. ❌ **Does NOT cancel existing pending orders** (just skips)
4. ❌ **Does NOT use database fallback** (only broker API)

**Potential Gap**:
- If there's a stale pending buy order that should be replaced, retry will skip it
- If broker API is down, retry cannot check for duplicates

### Scenario 2: Regular Order Placement (`place_new_entries()`)

**Duplicate Prevention**:
1. ✅ Checks holdings (cached + live) - **Skips if already owned**
2. ✅ Checks active buy orders - **Cancels and replaces** if pending order exists
3. ✅ Database fallback when holdings API fails - **Aborts if duplicates found**
4. ✅ Order ID check in `add_pending_order()` - **Prevents duplicate order_id**

**Robust**: Multiple layers with fallback

### Scenario 3: Manual Retry (via API)

**Current Implementation**: Uses same logic as pre-market retry (`retry_pending_orders_from_db()`)

**Duplicate Prevention**: Same as Scenario 1

## Identified Gaps

### Gap 1: Inconsistent Behavior for Active Buy Orders

**Issue**:
- `place_new_entries()` cancels and replaces existing pending buy orders
- `retry_pending_orders_from_db()` just skips if pending order exists

**Impact**:
- If user manually placed an order that's still pending, retry will skip
- User might want to retry with updated price/quantity, but system skips

**Recommendation**:
- Consider canceling and replacing in retry (same as `place_new_entries()`)
- OR: Add configuration to allow cancel-and-replace vs skip

### Gap 2: No Database Fallback in Retry

**Issue**:
- `retry_pending_orders_from_db()` only uses broker API checks
- If broker API is down, retry cannot check for duplicates

**Impact**:
- During broker API maintenance (12 AM - 6 AM IST), retry might place duplicates
- No fallback mechanism like `place_new_entries()` has

**Recommendation**:
- Add database fallback check similar to `place_new_entries()`
- Check database for existing orders before retrying

### Gap 3: No Database Check for Holdings in Retry

**Issue**:
- `retry_pending_orders_from_db()` only checks broker API for holdings
- If holdings API fails, retry cannot verify if symbol is already owned

**Impact**:
- During API restrictions, might retry order for symbol already in portfolio
- Could result in duplicate holdings

**Recommendation**:
- Add database check for existing positions/orders before retry
- Query `orders` table for executed/ongoing orders for the symbol

## Recommendations

### Short-term Fixes

1. **Add database fallback to retry method**:
   ```python
   # In retry_pending_orders_from_db()
   # If has_holding() fails, check database for executed orders
   if not self.has_holding(symbol):
       # Check database for executed/ongoing orders
       existing_orders = self.orders_repo.list(self.user_id)
       for order in existing_orders:
           if order.symbol == symbol and order.status in [ONGOING, EXECUTED]:
               # Skip retry - already have position
   ```

2. **Consider cancel-and-replace for active buy orders in retry**:
   ```python
   # In retry_pending_orders_from_db()
   if self.has_active_buy_order(symbol):
       # Cancel existing order before retry (like place_new_entries does)
       variants = self._symbol_variants(symbol)
       cancelled = self.orders.cancel_pending_buys_for_symbol(variants)
       logger.info(f"Cancelled {cancelled} pending BUY order(s) for {symbol} before retry")
   ```

### Long-term Improvements

1. **Unified duplicate prevention logic**:
   - Extract duplicate checking into a shared method
   - Use same logic in both `place_new_entries()` and `retry_pending_orders_from_db()`

2. **Database-first approach**:
   - Check database first (faster, more reliable)
   - Fallback to broker API if needed
   - Reduces dependency on broker API availability

3. **Configuration option**:
   - Allow users to choose: "skip" vs "cancel-and-replace" for active buy orders
   - Default to cancel-and-replace for consistency

## Current Status Summary (After Improvements)

| Scenario | Holdings Check | Active Order Check | Database Fallback | Order ID Check |
|----------|---------------|-------------------|------------------|----------------|
| Pre-market Retry | ✅ Broker API + DB | ✅ Broker API + DB (cancel) | ✅ Yes | ✅ Yes |
| Manual Retry | ✅ Broker API + DB | ✅ Broker API + DB (cancel) | ✅ Yes | ✅ Yes |
| Regular Placement | ✅ Broker API + DB | ✅ Broker API (cancel) | ✅ Yes | ✅ Yes |

**Overall**: All scenarios now have robust duplicate prevention with database fallback and consistent cancel-and-replace behavior.

## Improvements Implemented (December 2024)

### 1. Database Fallback for Holdings Check
- **Before**: Only checked broker API, failed if API was down
- **After**: Falls back to database check for `ONGOING` orders when API fails
- **Benefit**: Prevents duplicates during broker API maintenance windows

### 2. Cancel-and-Replace for Active Buy Orders
- **Before**: Just skipped if active buy order existed
- **After**: Cancels existing pending order and replaces it (consistent with `place_new_entries()`)
- **Benefit**: Allows retry to update stale pending orders with fresh price/quantity

### 3. Database Fallback for Active Order Check
- **Before**: Only checked broker API for pending orders
- **After**: Falls back to database check for `AMO`, `PENDING_EXECUTION`, `ONGOING` orders when API fails
- **Benefit**: Prevents duplicates when broker API is unavailable

### 4. Error Handling
- **Before**: API failures would cause retry to fail or skip incorrectly
- **After**: Graceful fallback to database checks with proper error handling
- **Benefit**: More resilient during API outages
