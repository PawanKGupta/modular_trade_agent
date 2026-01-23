# Testing Guide: Missing Position Creation Fix

## Overview

This fix ensures that executed buy orders with `execution_price` but missing positions will have their positions created when the unified service runs.

## What the Fix Does

1. **Includes orders WITH execution_price** in reconciliation check (previously only orders WITHOUT execution_price were checked)
2. **Creates missing positions** for executed orders that already have execution details
3. **Prevents duplicate processing** with smart duplicate detection
4. **Validates input data** before position creation

## When Position Creation Happens

The fix triggers position creation in these scenarios:

### 1. **Service Restart** ✅
When the unified service restarts, it will:
- Start `sell_monitor` task (runs continuously during market hours)
- Call `monitor_all_orders()` → `check_buy_order_status()`
- Check ALL ONGOING orders (including those with execution_price)
- Create missing positions for executed orders

### 2. **During Normal Operation** ✅
During market hours (9:15 AM - 3:30 PM), the service:
- Runs `monitor_all_orders()` every minute
- Continuously checks buy order status
- Creates positions for newly executed orders

### 3. **Manual Trigger** ✅
You can manually trigger reconciliation by:
- Restarting the unified service
- Or waiting for the next `sell_monitor` execution cycle

## Testing Steps

### Test Case 1: Verify Missing Position Creation on Service Restart

**Prerequisites:**
- Order exists with `execution_price` but no position (e.g., order ID 300 for INDIAGLYCO-EQ, user 2)

**Steps:**

1. **Check current state (before fix):**
```sql
-- Check order status
SELECT id, user_id, symbol, side, status, execution_price, execution_qty, execution_time
FROM orders
WHERE id = 300;

-- Check if position exists
SELECT id, user_id, symbol, quantity, avg_price, opened_at
FROM positions
WHERE user_id = 2 AND symbol LIKE '%INDIAGLYCO%';
```

2. **Restart the unified service:**
```bash
# Stop the service
# (method depends on your setup - Windows service, Docker, etc.)

# Start the service
# (method depends on your setup)
```

3. **Wait for sell_monitor to start:**
- Service starts `sell_monitor` at 9:15 AM (or immediately if already past 9:15 AM)
- `monitor_all_orders()` is called
- `check_buy_order_status()` runs and processes ONGOING orders

4. **Verify position was created:**
```sql
-- Check if position was created
SELECT id, user_id, symbol, quantity, avg_price, opened_at
FROM positions
WHERE user_id = 2 AND symbol LIKE '%INDIAGLYCO%';

-- Check order status (should still be ONGOING - that's correct)
SELECT id, symbol, status, execution_price, execution_qty
FROM orders
WHERE id = 300;
```

**Expected Result:**
- ✅ Position should be created with:
  - `symbol` = `INDIAGLYCO-EQ` (or matching format)
  - `quantity` = `10` (from order execution_qty)
  - `avg_price` = `939.7` (from order execution_price)
  - `opened_at` = order's execution_time

### Test Case 2: Verify No Duplicate Position Creation

**Steps:**

1. **Create a test scenario:**
   - Ensure position already exists for a symbol
   - Order has execution_price and status = ONGOING

2. **Restart service and verify:**
   - Position should NOT be duplicated
   - Position quantity should remain the same (not doubled)

3. **Check logs for duplicate detection:**
```bash
# Look for log messages like:
# "Order {order_id} for {symbol} already processed (found in reentries). Skipping duplicate position update."
# OR
# "Order {order_id} for {symbol} appears to have already been processed (first order, no reentries). Skipping duplicate position update."
```

### Test Case 3: Verify Reentry Orders Still Work

**Steps:**

1. **Create a reentry scenario:**
   - Position exists for a symbol
   - New reentry order executes with execution_price

2. **Restart service and verify:**
   - Reentry order should be processed
   - Position quantity should increase
   - Reentry should be added to reentries array

3. **Check position:**
```sql
SELECT id, symbol, quantity, reentry_count, reentries
FROM positions
WHERE user_id = 2 AND symbol = 'YOUR_SYMBOL';
```

**Expected Result:**
- ✅ Position quantity increases
- ✅ Reentry count increments
- ✅ Reentry data added to reentries array

## Monitoring and Verification

### Check Service Logs

Look for these log messages:

**Position Creation:**
```
INFO - Created position for {symbol}: qty={qty}, price=Rs {price:.2f}, entry_rsi={rsi:.2f}
```

**Duplicate Detection:**
```
INFO - Order {order_id} for {symbol} already processed (found in reentries). Skipping duplicate position update.
```

**Reconciliation:**
```
INFO - Reconciled order {order_id} (source: {source}): executed at Rs {price:.2f}, qty {qty}
```

### Database Queries

**Check orders being processed:**
```sql
SELECT
    o.id,
    o.symbol,
    o.status,
    o.execution_price,
    o.execution_qty,
    o.execution_time,
    CASE WHEN p.id IS NULL THEN 'MISSING POSITION' ELSE 'POSITION EXISTS' END as position_status
FROM orders o
LEFT JOIN positions p ON (
    p.user_id = o.user_id
    AND p.symbol = o.symbol
    AND p.closed_at IS NULL
)
WHERE o.user_id = 2
AND o.side = 'buy'
AND o.status = 'ongoing'
AND o.execution_price IS NOT NULL
ORDER BY o.execution_time DESC;
```

**Check positions created:**
```sql
SELECT
    p.id,
    p.symbol,
    p.quantity,
    p.avg_price,
    p.opened_at,
    o.id as order_id,
    o.execution_time
FROM positions p
JOIN orders o ON (
    o.user_id = p.user_id
    AND o.symbol = p.symbol
    AND ABS(EXTRACT(EPOCH FROM (p.opened_at - o.execution_time))) < 3600
)
WHERE p.user_id = 2
AND p.closed_at IS NULL
ORDER BY p.opened_at DESC;
```

## Troubleshooting

### Position Not Created?

1. **Check if order is being processed:**
   - Verify order status is `ONGOING`
   - Verify `execution_price` is set
   - Check service logs for errors

2. **Check duplicate detection:**
   - Look for "Skipping duplicate position update" messages
   - Verify if position already exists (might be correct behavior)

3. **Check validation errors:**
   - Look for "Invalid execution_price" or "Invalid execution_qty" errors
   - Verify execution_price > 0 and execution_qty > 0

### Position Created But Wrong Data?

1. **Check execution details:**
   - Verify order's `execution_price` and `execution_qty` are correct
   - Check if order has `execution_time` set

2. **Check symbol matching:**
   - Verify order symbol matches position symbol format
   - Check for symbol suffix differences (-EQ, -BE, etc.)

## Expected Timeline

After service restart:
- **Immediate**: Service starts, login occurs
- **9:15 AM** (or immediately if past): `sell_monitor` starts
- **Within 1 minute**: `monitor_all_orders()` called
- **Within 1 minute**: `check_buy_order_status()` processes orders
- **Within 1 minute**: Missing positions created

**Total time**: ~1-2 minutes after service start

## Success Criteria

✅ Position created for order 300 (INDIAGLYCO-EQ, user 2)
✅ Position has correct quantity (10) and price (939.7)
✅ No duplicate positions created
✅ Reentry orders still work correctly
✅ Service logs show position creation messages
