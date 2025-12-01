# Investigation: Duplicate Order Registration Issue

## Problem Statement

Three duplicate pending orders were created for DALBHARAT with the same order_id `251106000008974`:
- **09:15:08** - Price: ₹2095.53 (correct initial placement)
- **09:52:14** - Price: ₹0.0 (duplicate)
- **09:56:41** - Price: ₹0.0 (duplicate)

## Root Cause Analysis

### Primary Issue: Missing Duplicate Prevention

1. **`add_pending_order()` in `order_tracker.py`**
   - **Problem**: Always appended orders without checking for duplicates
   - **Impact**: Same order_id could be added multiple times to `pending_orders.json`

2. **`register_sell_order()` in `order_state_manager.py`**
   - **Problem**: Always called `add_pending_order()` without checking if order already exists
   - **Impact**: When `run_at_market_open()` found existing orders from broker, it re-registered them

### Trigger Flow

```
1. Order placed at 09:15:08 → registered correctly
   ↓
2. Service restarts OR run_at_market_open() called again (09:52:14)
   ↓
3. run_at_market_open() finds existing order from broker
   ↓
4. Calls _register_order() → register_sell_order() → add_pending_order()
   ↓
5. add_pending_order() adds duplicate (no check)
   ↓
6. Same happens again at 09:56:41
```

### Why Price Was 0.0

The duplicate entries had price ₹0.0 because:
- When `run_at_market_open()` finds existing orders, it extracts price from broker order
- If price extraction failed or returned 0, it passed 0.0 to `register_sell_order()`
- This overwrote the correct price in memory cache (though original entry still had correct price)

## Fixes Applied

### Fix 1: Duplicate Prevention in `add_pending_order()`

**File**: `modules/kotak_neo_auto_trader/order_tracker.py`

**Change**: Added duplicate check before adding order
```python
# Check if order already exists (prevent duplicates)
existing_order = None
for order in data["orders"]:
    if order["order_id"] == order_id:
        existing_order = order
        break

if existing_order:
    logger.warning(
        f"Order {order_id} already exists in pending orders. "
        f"Existing: symbol={existing_order.get('symbol')}, "
        f"status={existing_order.get('status')}, "
        f"price={existing_order.get('price')}. "
        f"Skipping duplicate add for {symbol}."
    )
    return
```

**Benefit**: Prevents duplicate entries in `pending_orders.json`

### Fix 2: Duplicate Prevention in `register_sell_order()`

**File**: `modules/kotak_neo_auto_trader/order_state_manager.py`

**Change**: Added check for existing order before registration
```python
# Check if order already exists in active_sell_orders
existing_order = self.active_sell_orders.get(base_symbol)
if existing_order and existing_order.get('order_id') == order_id:
    # Order already registered - check if price needs updating
    existing_price = existing_order.get('target_price', 0)
    if existing_price != target_price and target_price > 0:
        # Price changed - update it
        logger.debug(f"Updating price from ₹{existing_price:.2f} to ₹{target_price:.2f}")
        self.active_sell_orders[base_symbol]['target_price'] = target_price
    else:
        # Order already registered - skip duplicate registration
        logger.debug(f"Skipping duplicate registration.")
        return True  # Return True since order is already tracked
```

**Benefit**:
- Prevents duplicate registration in memory
- Allows price updates if needed
- Avoids unnecessary calls to `add_pending_order()`

## Prevention Strategy

### Multi-Layer Protection

1. **Layer 1**: `register_sell_order()` checks `active_sell_orders` before registering
2. **Layer 2**: `add_pending_order()` checks `pending_orders.json` before adding
3. **Result**: Even if one layer fails, the other prevents duplicates

### When Duplicates Can Still Occur

Duplicates can still occur if:
- Different order_ids for same symbol (legitimate - multiple orders)
- Order_id changes (e.g., cancel+replace creates new order_id)
- Manual intervention (orders added manually to JSON)

## Testing Recommendations

1. **Test duplicate prevention**:
   - Call `register_sell_order()` twice with same order_id
   - Verify only one entry in `pending_orders.json`
   - Verify warning logged for duplicate attempt

2. **Test price updates**:
   - Register order with price ₹100
   - Register same order with price ₹200
   - Verify price updated, not duplicated

3. **Test service restart**:
   - Place order
   - Restart service
   - Run `run_at_market_open()`
   - Verify no duplicate created

## Related Files Modified

- `modules/kotak_neo_auto_trader/order_tracker.py` - Added duplicate check
- `modules/kotak_neo_auto_trader/order_state_manager.py` - Added duplicate check

## Next Steps

1. ✅ Fix duplicate prevention in `add_pending_order()`
2. ✅ Fix duplicate prevention in `register_sell_order()`
3. ⏳ Clean up existing duplicate entries in `pending_orders.json`
4. ⏳ Monitor logs for duplicate prevention warnings
5. ⏳ Test with real orders to verify fix works

## Impact

- **Before**: Duplicate orders created on every service restart or `run_at_market_open()` call
- **After**: Duplicates prevented at both registration layers
- **Risk**: Low - fixes are defensive and don't change existing behavior for legitimate cases
