# Example: Target and Lowest EMA9 Fix

## Scenario: DALBHARAT Order Monitoring

### Before Fix (The Problem)

**Initial State:**
- Order placed at 09:15:08 with price ₹2095.53
- Order registered in OrderStateManager with `target_price: 2095.53`
- Service restarts or `monitor_and_update()` runs

**What Happens:**
1. `monitor_and_update()` calls `_get_active_orders()`
2. Orders synced from OrderStateManager: `{'DALBHARAT': {'order_id': '251106000008974', 'target_price': 0.0, ...}}`
   - Note: `target_price` is 0.0 due to duplicate registration bug
3. `lowest_ema9` is NOT initialized (empty dict: `{}`)
4. `_check_and_update_single_stock()` runs:
   - `lowest_so_far = self.lowest_ema9.get('DALBHARAT', float('inf'))` → `float('inf')`
   - `current_target = order_info.get('target_price', lowest_so_far)` → `0.0` (from order_info)
   - Log shows: `Target=₹0.00, Lowest=₹0.00` ❌

**Code Flow:**
```python
# In _check_and_update_single_stock()
lowest_so_far = self.lowest_ema9.get(symbol, float('inf'))  # Returns inf
current_target = order_info.get('target_price', lowest_so_far)  # Returns 0.0 (from order_info)
logger.info(f"Target=₹{current_target:.2f}, Lowest=₹{lowest_so_far:.2f}")
# Output: Target=₹0.00, Lowest=₹inf (but formatted as 0.00)
```

---

### After Fix (The Solution)

**Same Initial State:**
- Order placed at 09:15:08 with price ₹2095.53
- Order registered in OrderStateManager with `target_price: 2095.53`
- Service restarts or `monitor_and_update()` runs

**What Happens Now:**

**Step 1: Sync Orders**
```python
# In _get_active_orders()
state_orders = {'DALBHARAT': {'order_id': '251106000008974', 'target_price': 0.0, ...}}
self.active_sell_orders.update(state_orders)

# NEW: Initialize lowest_ema9 from target_price
for symbol, order_info in state_orders.items():
    if symbol not in self.lowest_ema9:
        target_price = order_info.get('target_price', 0)
        if target_price > 0:
            self.lowest_ema9[symbol] = target_price
        # If target_price is 0, we'll initialize it later in monitoring
```

**Step 2: Monitor Order**
```python
# In _check_and_update_single_stock()
# Current EMA9 calculated: ₹2095.27
rounded_ema9 = 2095.27

# NEW: Initialize lowest_ema9 if not set
if 'DALBHARAT' not in self.lowest_ema9:
    target_price = order_info.get('target_price', 0)  # 0.0
    if target_price > 0:
        self.lowest_ema9['DALBHARAT'] = target_price
    else:
        # Use current EMA9 as initial value
        self.lowest_ema9['DALBHARAT'] = rounded_ema9  # 2095.27

lowest_so_far = self.lowest_ema9.get('DALBHARAT', float('inf'))  # 2095.27
current_target = order_info.get('target_price', 0)  # 0.0

# NEW: Handle zero target_price
if current_target <= 0:
    current_target = lowest_so_far if lowest_so_far != float('inf') else rounded_ema9
    # current_target = 2095.27

logger.info(f"Target=₹{current_target:.2f}, Lowest=₹{lowest_so_far:.2f}")
# Output: Target=₹2095.27, Lowest=₹2095.27 ✅
```

---

## Example Log Output

### Before Fix:
```
2025-11-06 15:23:25 — INFO — sell_engine — DALBHARAT LTP from WebSocket: ₹2048.80
2025-11-06 15:23:25 — INFO — sell_engine — DALBHARAT: LTP=₹2048.80, Yesterday EMA9=₹2106.89 → Current EMA9=₹2095.27
2025-11-06 15:23:25 — INFO — sell_engine — DALBHARAT: Current EMA9=₹2095.30, Target=₹0.00, Lowest=₹0.00  ❌
```

### After Fix:
```
2025-11-06 15:23:25 — INFO — sell_engine — DALBHARAT LTP from WebSocket: ₹2048.80
2025-11-06 15:23:25 — INFO — sell_engine — DALBHARAT: LTP=₹2048.80, Yesterday EMA9=₹2106.89 → Current EMA9=₹2095.27
2025-11-06 15:23:25 — INFO — sell_engine — DALBHARAT: Current EMA9=₹2095.30, Target=₹2095.30, Lowest=₹2095.30  ✅
```

---

## Edge Cases Handled

### Case 1: Order with Valid target_price
```python
order_info = {'target_price': 2095.53, ...}
# lowest_ema9 initialized to 2095.53
# Target shows 2095.53, Lowest shows 2095.53
```

### Case 2: Order with Zero target_price (Duplicate Bug)
```python
order_info = {'target_price': 0.0, ...}
# lowest_ema9 initialized to current EMA9 (2095.27)
# Target shows 2095.27 (from lowest_ema9), Lowest shows 2095.27
```

### Case 3: Order with Missing target_price
```python
order_info = {}  # No target_price key
# lowest_ema9 initialized to current EMA9 (2095.27)
# Target shows 2095.27 (from lowest_ema9), Lowest shows 2095.27
```

### Case 4: Order Already Has lowest_ema9 Set
```python
self.lowest_ema9['DALBHARAT'] = 2090.00  # Already set from previous monitoring
order_info = {'target_price': 0.0, ...}
# lowest_ema9 not re-initialized (already exists)
# Target shows 2090.00 (from lowest_ema9), Lowest shows 2090.00
```

---

## Key Improvements

1. **Initialization**: `lowest_ema9` is now initialized when syncing from OrderStateManager
2. **Fallback**: If `target_price` is 0, uses current EMA9 as initial value
3. **Display**: Target always shows a meaningful value (never ₹0.00)
4. **Tracking**: Lowest EMA9 is properly tracked even after service restart

This ensures that monitoring always has valid values to work with, even when `target_price` is corrupted due to the duplicate registration bug.





