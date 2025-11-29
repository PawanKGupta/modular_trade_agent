# Retry Edge Cases Analysis

## Overview

This document analyzes three critical edge cases for the retry mechanism:
1. Capital modified before retry
2. Manual AMO order placed before retry
3. Manual AMO order with different quantity before retry

## Current Behavior Analysis

### Case 1: Capital Modified Before Retry

**Current Implementation**:
- Retry recalculates execution capital using `_calculate_execution_capital(ticker, close, avg_vol)`
- Calculates quantity: `qty = max(config.MIN_QTY, floor(execution_capital / close))`
- Checks balance: `affordable = self.get_affordable_qty(close)` (queries broker API)
- If `qty > affordable`, marks as failed and keeps as `RETRY_PENDING`

**Behavior**:
1. ✅ **Handled**: If capital reduced, retry correctly fails and stays as `RETRY_PENDING`
2. ✅ **By Design**: If capital increased, retry adapts to new capital (this is intentional - system adapts to current conditions)
3. ✅ **By Design**: Execution capital is recalculated based on current liquidity (adapts to market conditions)

**Rationale**:
- System is designed to adapt to current market conditions and available capital
- Recalculating execution capital ensures orders are sized appropriately for current liquidity
- If user wants to preserve original order size, they can manually place the order

**Status**: ✅ **Working as designed** - No changes needed

### Case 2: Manual AMO Order Placed Before Retry

**Current Implementation (After Improvements)**:
- ✅ **Manual Order Detection**: `_check_for_manual_orders()` checks if order exists in database
  - If order not in DB → Manual order
  - If order in DB → System order
- ✅ **Quantity Comparison**: `_should_skip_retry_due_to_manual_order()` compares quantities
  - If manual qty >= retry qty → Skip retry
  - If manual qty >> retry qty (50% more) → Skip retry
  - If manual qty ≈ retry qty (within 2 shares) → Skip retry
  - Otherwise → Cancel and replace
- ✅ **Notifications**: Sends Telegram notification when manual order detected
- ✅ **System Orders**: Still cancels and replaces system orders (consistent behavior)

**Remaining Considerations**:
1. ⚠️ **Timing Issue**: Manual order might not be immediately visible in broker API
   - Broker API might have delay (few seconds to minutes)
   - Retry might proceed before manual order appears
   - **Mitigation**: System checks broker API at retry time (scheduled retries have delay)
   - **Future Enhancement**: Add retry mechanism to check multiple times

**Status**: ✅ **Implemented** - Manual order detection and quantity comparison added

### Case 3: Manual AMO Order with Different Quantity

**Current Implementation (After Improvements)**:
- ✅ **Quantity Comparison**: Compares manual order quantity with retry quantity
  - If manual qty >= retry qty → Skip retry (user already has enough)
  - If manual qty >> retry qty (50% more) → Skip retry (user wants more)
  - If manual qty ≈ retry qty (within 2 shares) → Skip retry (similar quantity)
  - If manual qty < retry qty → Cancel and replace (user needs more)
- ✅ **User Intent Preserved**: System respects manual orders when quantity is acceptable
- ✅ **Notifications**: Sends Telegram notification when manual order detected
  - Notification includes: manual order ID, manual qty, retry qty, action taken

**Status**: ✅ **Implemented** - Quantity-aware retry logic added

## Proposed Solutions

### Solution 1: Enhanced Manual Order Detection

```python
def _check_for_manual_orders(self, symbol: str) -> dict[str, Any]:
    """
    Check for manual orders (orders not in our database).
    
    Returns:
        {
            'has_manual_order': bool,
            'order_id': str | None,
            'quantity': int | None,
            'price': float | None,
            'is_system_order': bool
        }
    """
    # 1. Get active orders from broker
    active_orders = self.orders.get_pending_orders() or []
    
    # 2. Check each order for this symbol
    for order in active_orders:
        if order matches symbol:
            order_id = extract_order_id(order)
            
            # 3. Check if order exists in our database
            db_order = self.orders_repo.get_by_broker_order_id(self.user_id, order_id)
            
            if not db_order:
                # This is a manual order (not in our DB)
                return {
                    'has_manual_order': True,
                    'order_id': order_id,
                    'quantity': extract_quantity(order),
                    'price': extract_price(order),
                    'is_system_order': False
                }
            else:
                # This is a system order
                return {
                    'has_manual_order': True,
                    'order_id': order_id,
                    'quantity': extract_quantity(order),
                    'price': extract_price(order),
                    'is_system_order': True
                }
    
    return {'has_manual_order': False}
```

### Solution 2: Quantity-Aware Retry Logic

```python
def _should_skip_retry_due_to_manual_order(
    self, symbol: str, retry_qty: int, manual_order_info: dict[str, Any]
) -> tuple[bool, str]:
    """
    Determine if retry should be skipped due to existing manual order.
    
    Returns:
        (should_skip: bool, reason: str)
    """
    manual_qty = manual_order_info.get('quantity', 0)
    
    # If manual order quantity is >= retry quantity, skip retry
    if manual_qty >= retry_qty:
        return (True, f"Manual order exists with {manual_qty} shares (>= retry qty {retry_qty})")
    
    # If manual order quantity is significantly larger, skip retry
    if manual_qty > retry_qty * 1.5:  # 50% more
        return (True, f"Manual order exists with {manual_qty} shares (much larger than retry qty {retry_qty})")
    
    # If manual order quantity is close to retry quantity, skip retry
    if abs(manual_qty - retry_qty) <= 2:  # Within 2 shares
        return (True, f"Manual order exists with {manual_qty} shares (similar to retry qty {retry_qty})")
    
    # Otherwise, proceed with retry (will cancel and replace)
    return (False, f"Manual order has {manual_qty} shares, retry wants {retry_qty} shares")
```

### Solution 3: Store Original Execution Capital

```python
# In retry_pending_orders_from_db():
# Option 1: Use stored original execution capital
if db_order.execution_capital:
    execution_capital = db_order.execution_capital
    qty = max(config.MIN_QTY, floor(execution_capital / close))
else:
    # Fallback: Recalculate
    execution_capital = self._calculate_execution_capital(ticker, close, avg_vol)
    qty = max(config.MIN_QTY, floor(execution_capital / close))
    # Store for future retries
    db_order.execution_capital = execution_capital
    self.orders_repo.update(db_order)
```

## Implementation Priority

1. **High Priority**: Manual order detection (Case 2 & 3)
   - Prevents duplicate orders
   - Respects user's manual actions
   - Critical for user trust

2. **Medium Priority**: Quantity comparison (Case 3)
   - Prevents unnecessary cancellations
   - Better user experience

3. **Low Priority**: Original capital preservation (Case 1)
   - Less critical (current behavior is acceptable)
   - Can be handled via configuration

## Testing Scenarios

### Test 1: Capital Reduced
- Place order with insufficient balance → RETRY_PENDING
- Reduce capital further
- Run retry → Should fail again, stay RETRY_PENDING

### Test 2: Capital Increased
- Place order with insufficient balance → RETRY_PENDING
- Increase capital significantly
- Run retry → Should succeed, but order size might be larger than original

### Test 3: Manual Order Before Retry
- Place order → RETRY_PENDING
- Manually place AMO order for same symbol
- Run retry → Should detect manual order and skip (or notify)

### Test 4: Manual Order with Same Quantity
- Place order for 10 shares → RETRY_PENDING
- Manually place AMO order for 10 shares
- Run retry → Should skip (quantity matches)

### Test 5: Manual Order with Different Quantity
- Place order for 10 shares → RETRY_PENDING
- Manually place AMO order for 5 shares
- Run retry → Should notify user, ask if should cancel and replace

### Test 6: Manual Order Not Yet Visible
- Place order → RETRY_PENDING
- Manually place AMO order (just now)
- Run retry immediately → Should have retry mechanism to wait for order to appear

