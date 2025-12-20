# Edge Cases for Manual Sell Detection via get_orders()

## Overview
This document identifies edge cases in the `_detect_manual_sells_from_orders()` implementation and proposes fixes.

## Identified Edge Cases

### 1. **"ongoing" Status Includes Non-Executed Orders** ⚠️ HIGH PRIORITY
**Issue**: Status check includes `"ongoing"` which might include orders that are still pending execution, not fully executed.

**Current Code**:
```python
status = OrderFieldExtractor.get_status(order)
if status not in ["executed", "filled", "complete", "ongoing"]:
    continue
```

**Problem**: An "ongoing" order might be pending execution (filled_qty = 0), not actually executed.

**Fix**: Check `filled_qty > 0` to ensure order has actually been executed:
```python
status = OrderFieldExtractor.get_status(order)
executed_qty = OrderFieldExtractor.get_filled_quantity(order)

# Only process orders that are actually executed (have filled quantity)
if status not in ["executed", "filled", "complete"]:
    # For "ongoing" status, only process if order has been partially/fully filled
    if status == "ongoing" and executed_qty <= 0:
        continue
    elif status != "ongoing":
        continue
```

### 2. **Multiple Manual Sell Orders for Same Symbol** ⚠️ MEDIUM PRIORITY
**Issue**: If user places multiple manual sell orders for the same symbol, we process them sequentially. If the first one closes the position, subsequent ones might try to update a closed position.

**Current Behavior**: Processes orders in sequence, might fail on second order if position already closed.

**Fix**: Check if position is still open before processing:
```python
# Get position from database (fresh read to check if still open)
position_obj = self.positions_repo.get_by_symbol(self.user_id, base_symbol)
if not position_obj or position_obj.closed_at is not None:
    continue  # Position already closed, skip this order
```

### 3. **Position Already Closed by Our System** ⚠️ MEDIUM PRIORITY
**Issue**: If our system's sell order executes and closes the position, we might still try to process a manual sell order that executed around the same time.

**Current Behavior**: Uses `get_open_positions()` which should filter closed positions, but there's a race condition window.

**Fix**: Add explicit check in the loop:
```python
# Re-check position status before processing (handles race conditions)
position_obj = self.positions_repo.get_by_symbol(self.user_id, base_symbol)
if not position_obj or position_obj.closed_at is not None:
    logger.debug(f"Position {base_symbol} already closed, skipping manual sell order {order_id}")
    continue
```

### 4. **Order Timestamp Check** ⚠️ LOW PRIORITY
**Issue**: We might process old orders from previous days if broker API returns historical orders.

**Current Behavior**: No timestamp check, processes all orders in response.

**Fix**: Check if order was executed today (or recently):
```python
from datetime import datetime, timedelta
from src.infrastructure.db.timezone_utils import ist_now

# Get order execution time
order_time_str = OrderFieldExtractor.get_order_time(order)
if order_time_str:
    try:
        # Parse order time (format varies by broker)
        order_time = datetime.fromisoformat(order_time_str.replace('Z', '+00:00'))
        # Only process orders executed today (or within last 24 hours)
        now = ist_now()
        if (now - order_time).days > 1:
            continue  # Skip old orders
    except Exception:
        pass  # If parsing fails, proceed (better to process than skip)
```

### 5. **Duplicate Processing** ⚠️ MEDIUM PRIORITY
**Issue**: If an order is partially filled and still executing, we might process it multiple times in consecutive monitoring cycles.

**Current Behavior**: No tracking of processed orders, might process same order multiple times.

**Fix**: Track processed order IDs (optional, since position update should be idempotent, but good for logging):
```python
# Track processed order IDs to avoid duplicate processing
processed_order_ids = set()

# In the loop:
if order_id in processed_order_ids:
    continue  # Already processed this order
processed_order_ids.add(order_id)
```

**Note**: This might not be necessary if `reduce_quantity()` and `mark_closed()` are idempotent, but it's good for avoiding duplicate logs.

### 6. **Position Quantity Validation** ⚠️ LOW PRIORITY
**Issue**: What if `position.get("qty", 0)` returns None or invalid value?

**Current Code**:
```python
position_qty = int(position.get("qty", 0))
```

**Fix**: Add validation:
```python
position_qty = int(position.get("qty", 0) or 0)
if position_qty <= 0:
    logger.warning(f"Invalid position quantity for {base_symbol}: {position_qty}, skipping")
    continue
```

### 7. **Executed Quantity > Position Quantity** ⚠️ MEDIUM PRIORITY
**Issue**: What if `executed_qty > position_qty`? This shouldn't happen for manual sells, but could indicate:
- Position was already partially sold
- Data inconsistency
- Multiple positions for same symbol (different users)

**Current Behavior**: Treats as full sell if `executed_qty >= position_qty`.

**Fix**: Add validation and logging:
```python
if executed_qty > position_qty:
    logger.warning(
        f"Manual sell executed quantity ({executed_qty}) exceeds position quantity ({position_qty}) "
        f"for {base_symbol}. This might indicate position was already partially sold or data inconsistency. "
        f"Marking position as closed."
    )
    # Still mark as closed, but log the anomaly
```

### 8. **Database Transaction Conflicts** ⚠️ LOW PRIORITY
**Issue**: If position update fails due to concurrent modification (e.g., our system's sell order executing simultaneously), we should handle gracefully.

**Current Behavior**: Exception is caught and logged, but might not be specific enough.

**Fix**: Already handled with try-except, but could add more specific error handling:
```python
except Exception as e:
    # Check if it's a database constraint violation or concurrent modification
    error_str = str(e).lower()
    if "closed" in error_str or "does not exist" in error_str:
        logger.debug(f"Position {base_symbol} was already closed/updated by another process: {e}")
    else:
        logger.error(f"Error updating position {base_symbol} quantity: {e}")
```

### 9. **Order ID Format Mismatch** ⚠️ LOW PRIORITY
**Issue**: Broker might return order IDs in different formats (string vs int, with/without prefixes).

**Current Code**:
```python
tracked_sell_order_ids.add(str(order_id))
# ...
if order_id in tracked_sell_order_ids:
```

**Fix**: Normalize order IDs consistently:
```python
# Normalize order IDs to strings for consistent comparison
def normalize_order_id(order_id: str | int | None) -> str:
    if order_id is None:
        return ""
    return str(order_id).strip()

# Usage:
tracked_sell_order_ids.add(normalize_order_id(order_info.get("order_id")))
# ...
if normalize_order_id(order_id) in tracked_sell_order_ids:
```

### 10. **Symbol Matching Edge Cases** ⚠️ LOW PRIORITY
**Issue**: What if broker returns symbol in different format (e.g., "ASTERDM" vs "ASTERDM-EQ")?

**Current Code**: Uses `extract_base_symbol()` which should handle it.

**Status**: ✅ Already handled correctly with `extract_base_symbol()`.

## Recommended Fixes (Priority Order)

### High Priority
1. **Fix #1**: Check `filled_qty > 0` for "ongoing" status orders
2. **Fix #3**: Add explicit position open check before processing

### Medium Priority
3. **Fix #2**: Handle multiple manual sell orders gracefully
4. **Fix #7**: Validate executed_qty vs position_qty
5. **Fix #5**: Track processed order IDs (optional but recommended)

### Low Priority
6. **Fix #4**: Add order timestamp check (optional, broker API might filter)
7. **Fix #6**: Add position quantity validation
8. **Fix #8**: Improve error handling for database conflicts
9. **Fix #9**: Normalize order IDs consistently

## Implementation Notes

- Most fixes are defensive programming (better safe than sorry)
- Some fixes (like timestamp check) might not be necessary if broker API already filters
- Database transaction conflicts are already handled, but could be more specific
- Position quantity validation is good practice but might not be critical

## Testing Recommendations

1. **Test with "ongoing" status orders**: Verify that orders with status="ongoing" but filled_qty=0 are skipped
2. **Test multiple manual sells**: Place 2 manual sell orders for same symbol, verify both are handled correctly
3. **Test race condition**: Simulate our system's sell order executing simultaneously with manual sell
4. **Test old orders**: Verify that orders from previous days are not processed (if timestamp check is added)
5. **Test partial execution**: Verify that partially filled orders are handled correctly
