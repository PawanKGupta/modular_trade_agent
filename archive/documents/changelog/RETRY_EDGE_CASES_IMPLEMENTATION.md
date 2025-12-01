# Retry Edge Cases - User Expected Behavior Implementation

## Overview

Implemented the user's expected behavior for three critical edge cases in the retry and new order placement mechanisms.

## User Requirements vs Implementation

### 1. Capital Per Trade Modified Before Retry

**User Expected**:
- Recalculate qty based on new capital per trade config
- Update DB with new qty
- Retry with new qty (increased/decreased)

**Implementation**:
✅ **Implemented**
- Retry recalculates execution capital using `_calculate_execution_capital()` which uses current `strategy_config.user_capital`
- Calculates new quantity: `qty = max(config.MIN_QTY, floor(execution_capital / close))`
- Updates DB order with new quantity when retry succeeds:
  ```python
  self.orders_repo.update(
      db_order,
      broker_order_id=order_id,
      quantity=qty,  # Update with recalculated quantity
      status=DbOrderStatus.PENDING_EXECUTION,
  )
  ```

**Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` - `retry_pending_orders_from_db()`

### 2. Manual AMO Order Placed Before Retry/New Order

**User Expected**:
- **For new order**: Skip placing new AMO order, update DB with existing order details
- **For retry order**: Update status to PENDING_EXECUTION from RETRY_PENDING with existing qty, skip retry

**Implementation**:
✅ **Implemented**

#### For New Orders (`place_new_entries`):
- Detects manual orders using `_check_for_manual_orders()`
- If manual order found:
  - Skips placing new order
  - Creates/updates DB record with manual order details:
    - `broker_order_id`: Manual order ID
    - `quantity`: Manual order quantity
    - `price`: Manual order price
    - `status`: PENDING_EXECUTION
  - Logs action and continues to next recommendation

#### For Retry Orders (`retry_pending_orders_from_db`):
- Detects manual orders using `_check_for_manual_orders()`
- If manual order found:
  - Links manual order to existing DB record
  - Updates DB order:
    - `broker_order_id`: Manual order ID
    - `quantity`: Manual order quantity (uses actual manual order qty)
    - `price`: Manual order price
    - `status`: PENDING_EXECUTION (from RETRY_PENDING)
  - Skips retry placement
  - Sends notification

**Location**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py` - `place_new_entries()`
- `modules/kotak_neo_auto_trader/auto_trade_engine.py` - `retry_pending_orders_from_db()`

### 3. Manual AMO Order with Different Quantity

**User Expected**: Same as Case 2 (regardless of quantity difference)

**Implementation**:
✅ **Implemented** - Same logic as Case 2
- No quantity comparison - always links manual order to DB
- Uses actual manual order quantity (not calculated qty)
- Updates DB with manual order details regardless of quantity difference

## Key Implementation Details

### Manual Order Detection

**Method**: `_check_for_manual_orders(symbol)`

**Logic**:
1. Queries broker API for pending buy orders
2. For each order, checks if it exists in our database
3. If order not in DB → Manual order
4. If order in DB → System order

**Returns**:
```python
{
    'has_manual_order': bool,
    'has_system_order': bool,
    'manual_orders': list[dict],  # List of manual orders with order_id, quantity, price
    'system_orders': list[dict],  # List of system orders
}
```

### Database Updates

**For New Orders**:
- Creates new DB record if manual order not in DB
- Updates existing DB record if manual order already in DB
- Sets status to `PENDING_EXECUTION`

**For Retry Orders**:
- Updates existing `RETRY_PENDING` order record
- Changes status from `RETRY_PENDING` to `PENDING_EXECUTION`
- Updates with manual order details (order_id, qty, price)

### Notifications

**Telegram Notifications**:
- **For Retry**: Sends notification when manual order linked
  - Action: `linked_manual_order`
  - Includes: manual_order_id, manual_qty, manual_price, retry_qty, message

## Benefits

1. **Order Tracking**: Manual orders are now tracked in the system
2. **No Duplicates**: Prevents placing duplicate orders when manual order exists
3. **DB Consistency**: DB always reflects actual broker state
4. **Config Adaptation**: Retry adapts to config changes automatically
5. **User Intent**: Respects user's manual actions by linking them to system

## Testing Scenarios

### Test 1: Capital Per Trade Increased
- Place order with 1L capital → RETRY_PENDING
- Increase capital to 2L in config
- Run retry → Should place order with new qty (based on 2L), update DB

### Test 2: Capital Per Trade Decreased
- Place order with 2L capital → RETRY_PENDING
- Decrease capital to 1L in config
- Run retry → Should place order with new qty (based on 1L), update DB

### Test 3: Manual Order Before New Order
- System wants to place order for RELIANCE
- User manually places AMO order for RELIANCE
- System runs `place_new_entries()` → Should skip placing, create DB record with manual order details

### Test 4: Manual Order Before Retry
- Order in RETRY_PENDING status
- User manually places AMO order for same symbol
- System runs retry → Should update DB order status to PENDING_EXECUTION, link manual order, skip retry

### Test 5: Manual Order with Different Quantity
- Order wants 10 shares
- User manually places order for 5 shares
- System detects manual order → Should link to DB with 5 shares (actual qty), skip placement

## Files Modified

1. `modules/kotak_neo_auto_trader/auto_trade_engine.py`:
   - Updated `retry_pending_orders_from_db()`:
     - Recalculates qty based on current config
     - Updates DB with new qty on successful retry
     - Links manual orders to DB records
     - Updates status from RETRY_PENDING to PENDING_EXECUTION
   - Updated `place_new_entries()`:
     - Detects manual orders before placing
     - Creates/updates DB records with manual order details
     - Skips placing new order if manual order exists

2. `documents/changelog/RETRY_EDGE_CASES_IMPLEMENTATION.md`:
   - This file - implementation summary

## Status

✅ **All three edge cases implemented as per user requirements**:
- Case 1: Capital per trade modification - ✅ Implemented
- Case 2: Manual AMO order detection - ✅ Implemented (for both new and retry)
- Case 3: Manual order with different qty - ✅ Implemented (same as Case 2)
