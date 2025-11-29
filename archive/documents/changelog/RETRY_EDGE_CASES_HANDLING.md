# Retry Edge Cases Handling - Implementation Summary

## Overview

Implemented comprehensive handling for three critical edge cases in the retry mechanism:
1. Capital modified before retry
2. Manual AMO order placed before retry
3. Manual AMO order with different quantity before retry

## Changes Implemented

### 1. Manual Order Detection

**New Method**: `_check_for_manual_orders(symbol)`

**Purpose**: Detects manual orders (orders not in our database) vs system orders (orders in our database).

**How it works**:
- Queries broker API for pending buy orders for the symbol
- For each order, checks if it exists in our database
- Returns:
  - `has_manual_order`: True if manual orders found
  - `has_system_order`: True if system orders found
  - `manual_orders`: List of manual orders with details (order_id, quantity, price)
  - `system_orders`: List of system orders with details

**Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

### 2. Quantity-Aware Retry Logic

**New Method**: `_should_skip_retry_due_to_manual_order(symbol, retry_qty, manual_order_info)`

**Purpose**: Determines if retry should be skipped based on existing manual order quantity.

**Logic**:
- If manual qty >= retry qty → Skip retry (user already has enough)
- If manual qty >> retry qty (50% more) → Skip retry (user wants more)
- If manual qty ≈ retry qty (within 2 shares) → Skip retry (similar quantity)
- Otherwise → Proceed with retry (will cancel and replace)

**Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

### 3. Enhanced Retry Flow

**Updated Method**: `retry_pending_orders_from_db()`

**Changes**:
1. **Manual Order Detection**: Checks for manual orders before calculating quantity
2. **Quantity Comparison**: Compares manual order quantity with retry quantity
3. **Smart Skipping**: Skips retry if manual order quantity is acceptable
4. **Notifications**: Sends Telegram notification when manual order detected
5. **System Order Handling**: Still cancels and replaces system orders (consistent behavior)

**Flow**:
```
1. Check if already in holdings → Skip if yes
2. Calculate retry quantity (based on current capital/liquidity)
3. Check for manual orders
   ├─ If manual order exists:
   │   ├─ Compare quantities
   │   ├─ If quantity acceptable → Skip retry, mark as cancelled
   │   └─ If quantity not acceptable → Cancel and replace
   └─ If no manual order:
       └─ Check for system orders → Cancel and replace if found
4. Proceed with retry placement
```

## Edge Cases Handled

### Case 1: Capital Modified Before Retry

**Status**: ✅ **Working as designed**

**Behavior**:
- Retry recalculates execution capital based on current market conditions
- Adapts to current available capital
- If capital reduced → Retry fails, stays as `RETRY_PENDING`
- If capital increased → Retry adapts to new capital (intentional behavior)

**Rationale**: System is designed to adapt to current market conditions and available capital.

### Case 2: Manual AMO Order Placed Before Retry

**Status**: ✅ **Implemented**

**Behavior**:
- Detects manual orders (orders not in database)
- Compares quantities with retry quantity
- Skips retry if manual order quantity is acceptable
- Sends notification when manual order detected
- Cancels and replaces if manual order quantity is insufficient

**Benefits**:
- Prevents duplicate orders
- Respects user's manual actions
- Provides visibility via notifications

### Case 3: Manual AMO Order with Different Quantity

**Status**: ✅ **Implemented**

**Behavior**:
- Compares manual order quantity with retry quantity
- Skips retry if:
  - Manual qty >= retry qty (user already has enough)
  - Manual qty >> retry qty (user wants more)
  - Manual qty ≈ retry qty (similar quantity)
- Cancels and replaces if manual qty < retry qty (user needs more)

**Benefits**:
- Preserves user intent
- Prevents unnecessary cancellations
- Provides clear notifications

## Notifications

**Telegram Notifications Added**:
1. **Manual Order Detected (Skipped)**:
   - Action: `skipped_manual_order`
   - Includes: reason, manual_order_id, manual_qty, retry_qty

2. **Manual Order Detected (Will Cancel)**:
   - Action: `will_cancel_manual_order`
   - Includes: reason, manual_order_id, manual_qty, retry_qty

## Testing Recommendations

### Test Scenarios

1. **Manual Order with Same Quantity**:
   - Place order → RETRY_PENDING
   - Manually place AMO order for same symbol with same quantity
   - Run retry → Should skip, mark as cancelled

2. **Manual Order with Larger Quantity**:
   - Place order for 10 shares → RETRY_PENDING
   - Manually place AMO order for 20 shares
   - Run retry → Should skip (user wants more)

3. **Manual Order with Smaller Quantity**:
   - Place order for 10 shares → RETRY_PENDING
   - Manually place AMO order for 5 shares
   - Run retry → Should cancel and replace (user needs more)

4. **System Order Before Retry**:
   - Place order → RETRY_PENDING
   - System places another order for same symbol
   - Run retry → Should cancel and replace (system order)

5. **No Orders Before Retry**:
   - Place order → RETRY_PENDING
   - No other orders exist
   - Run retry → Should proceed with retry placement

## Future Enhancements

1. **Timing Issue Mitigation**:
   - Add retry mechanism to check for orders multiple times
   - Add configurable delay before retry to allow manual orders to appear

2. **Configuration Options**:
   - Add setting: "Respect manual orders" vs "Always cancel and replace"
   - Add setting: "Use original capital" vs "Recalculate capital"

3. **Original Capital Preservation**:
   - Store original execution capital in DB order record
   - Option to use original capital for retry (if user prefers)

## Files Modified

1. `modules/kotak_neo_auto_trader/auto_trade_engine.py`:
   - Added `_check_for_manual_orders()` method
   - Added `_should_skip_retry_due_to_manual_order()` method
   - Updated `retry_pending_orders_from_db()` to use new methods

2. `documents/investigation/RETRY_EDGE_CASES.md`:
   - Updated with implementation status
   - Documented current behavior

3. `documents/changelog/RETRY_EDGE_CASES_HANDLING.md`:
   - This file - implementation summary

## Benefits

1. **Prevents Duplicate Orders**: Detects and handles manual orders intelligently
2. **Respects User Intent**: Preserves manual orders when quantity is acceptable
3. **Better User Experience**: Clear notifications about manual order detection
4. **Adaptive Behavior**: System adapts to current market conditions and capital
5. **Consistent Logic**: System orders still follow cancel-and-replace pattern

## Status

✅ **All three edge cases are now handled**:
- Case 1: Capital modification - Working as designed
- Case 2: Manual order detection - Implemented
- Case 3: Quantity comparison - Implemented
