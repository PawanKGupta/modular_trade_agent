# CRITICAL ISSUE: Order Rejection Tracking Gap

## Problem Statement

**Current System Flaw:**
The system assumes orders are successfully executed based on the initial placement response, but **does not verify actual order status** with the broker. This creates a critical mismatch:

- System thinks: "Order placed successfully"
- Broker reality: "Order REJECTED"
- User sees: Confusion and potential trading errors

## Why This is Critical

### Scenario 1: AMO Order Rejection
```
4:05 PM  → System places AMO order for RELIANCE
         → Broker API returns "success" (order accepted for placement)
         → System logs: "Order placed successfully"
         
9:15 AM  → Market opens
         → Broker rejects order (symbol not tradable, circuit limit, etc.)
         → System still thinks order is active
         
9:30 AM  → Reconciliation runs
         → Order not in holdings (because it was rejected)
         → But system never checks rejection status
         → Order remains in "pending" limbo forever
```

### Scenario 2: Immediate Rejection
```
→ System places MARKET order for INVALID-SYMBOL-EQ
→ Broker returns success with order ID
→ Broker immediately rejects (symbol not found)
→ System thinks order is placed
→ User never gets notified of rejection
```

## Root Causes

1. **No Order ID Tracking**
   - `_attempt_place_order()` returns True/False
   - Does not capture or return order ID from broker response
   - Cannot track order status later

2. **No Status Verification**
   - System never calls `get_orders()` to check status
   - Assumes order moved to holdings automatically
   - No handling for REJECTED/CANCELLED states

3. **Reconciliation Assumes Success**
   - `reconcile_holdings_to_history()` only checks holdings
   - If order not in holdings → ignored (could be rejected)
   - Never verifies if "missing" order was rejected

4. **No Rejection Handling**
   - No notifications when orders are rejected
   - No logging of rejection reasons
   - No retry mechanism for legitimately retryable rejections

## Order Lifecycle States

### Broker Order States
```
PENDING → OPEN → EXECUTED → in Holdings
           ↓        ↓
       REJECTED  CANCELLED
```

### Current System Assumptions
```
place_order() → "success" → Assume in Holdings eventually
```

### Required System Flow
```
place_order() → Capture Order ID → Track as PENDING
                      ↓
           Verify Status (every 15 min)
                      ↓
         ┌────────────┴────────────┐
         ↓                         ↓
    EXECUTED/COMPLETE         REJECTED/CANCELLED
         ↓                         ↓
   Add to Holdings         Notify + Handle Rejection
```

## Solution Architecture

### 1. Storage Layer (storage.py)

Add `pending_orders` tracking to history:

```python
{
  "trades": [...],
  "failed_orders": [...],
  "pending_orders": [  # NEW
    {
      "order_id": "20250127-ORDER-123",
      "symbol": "RELIANCE-EQ",
      "ticker": "RELIANCE.NS",
      "qty": 10,
      "order_type": "MARKET",
      "variety": "AMO",
      "placed_at": "2025-01-27T16:05:00",
      "last_status_check": "2025-01-27T16:05:00",
      "status": "PENDING",  # PENDING/OPEN/EXECUTED/REJECTED/CANCELLED
      "rejection_reason": null,
      "check_count": 0
    }
  ]
}
```

### 2. Order Placement (auto_trade_engine.py)

Modify `_attempt_place_order()` to:
- Extract order ID from broker response
- Store in `pending_orders` with status PENDING
- Return (success: bool, order_id: str)

### 3. Order Status Verification

New function `verify_pending_orders()`:
```python
def verify_pending_orders():
    """
    Check status of all pending orders and handle rejections.
    Should run:
    - Immediately after placement (same session)
    - Every 15 minutes after 9:15 AM market open
    """
    pending = get_pending_orders_from_storage()
    
    for order in pending:
        status = check_order_status(order['order_id'])
        
        if status == 'REJECTED':
            handle_rejection(order)
        elif status == 'CANCELLED':
            handle_cancellation(order)
        elif status in ['EXECUTED', 'COMPLETE']:
            mark_order_complete(order)
        elif status in ['PENDING', 'OPEN']:
            # Still waiting - update check timestamp
            update_last_check(order)
```

### 4. Rejection Handling

```python
def handle_rejection(order, reason):
    """
    Handle rejected order:
    1. Notify user via Telegram
    2. Log rejection with reason
    3. Remove from pending_orders
    4. Optionally: Add to failed_orders for manual review
    """
    symbol = order['symbol']
    reason_text = extract_rejection_reason(reason)
    
    # Telegram notification
    send_telegram(
        f"❌ Order REJECTED by broker\\n"
        f"Symbol: {symbol}\\n"
        f"Qty: {order['qty']}\\n"
        f"Reason: {reason_text}\\n"
        f"Order ID: {order['order_id']}"
    )
    
    # Log
    logger.error(f"Order rejected: {symbol} - {reason_text}")
    
    # Remove from pending
    remove_pending_order(order['order_id'])
    
    # Track in history for audit
    add_rejected_order_to_history(order, reason_text)
```

### 5. Reconciliation Enhancement

Update `reconcile_holdings_to_history()`:
```python
def reconcile_holdings_to_history():
    # BEFORE: Only check holdings
    # AFTER: Also verify pending orders
    
    # 1. Check holdings (existing logic)
    reconcile_from_holdings()
    
    # 2. Check pending orders status
    verify_pending_orders()
    
    # 3. Cleanup old pending orders (>24 hours without status)
    cleanup_stale_pending_orders()
```

## Implementation Priority

### Phase 1: Critical (Implement ASAP)
1. ✅ Add `pending_orders` to storage structure
2. ✅ Extract order ID from place_order response
3. ✅ Add order status verification function
4. ✅ Add rejection handling and notifications
5. ✅ Update reconciliation to check pending orders

### Phase 2: Enhancement
1. Add scheduled task to verify orders every 15 min (9:15 AM - 3:30 PM)
2. Add retry logic for certain rejection types (e.g., "Try again")
3. Add rejection analytics dashboard
4. Add unit tests for rejection scenarios

### Phase 3: Advanced
1. Predictive rejection prevention (validate before placing)
2. Smart order modification on rejection
3. Broker API error correlation and auto-recovery

## Broker API Integration

### Extract Order ID from Response

```python
def extract_order_id(response: Dict) -> Optional[str]:
    """
    Extract order ID from broker response.
    Kotak Neo API returns different formats:
    - {'data': {'neoOrdNo': 'ORDER-123'}}
    - {'neoOrdNo': 'ORDER-123'}
    - {'orderId': 'ORDER-123'}
    """
    if not isinstance(response, dict):
        return None
    
    # Try common field names
    data = response.get('data', response)
    return (
        data.get('neoOrdNo') or
        data.get('orderId') or
        data.get('order_id') or
        data.get('OrdId')
    )
```

### Check Order Status

```python
def check_order_status(order_id: str) -> OrderStatus:
    """
    Query broker API for order status.
    Uses orders.get_orders() and filter by order ID.
    """
    orders = self.orders.get_orders()
    if not orders or 'data' not in orders:
        return OrderStatus.UNKNOWN
    
    for order in orders['data']:
        if order.get('neoOrdNo') == order_id:
            status_str = order.get('orderStatus', 'PENDING')
            return OrderStatus.from_string(status_str)
    
    return OrderStatus.NOT_FOUND
```

## Testing Strategy

### Test Cases

1. **Normal Success Flow**
   - Place order → Get order ID → Status = EXECUTED → Add to holdings

2. **Rejection at Placement**
   - Place order → Rejected immediately → Notify user → Remove from pending

3. **Rejection After Placement**
   - Place AMO → Status = PENDING → Market opens → Status = REJECTED → Notify

4. **Cancelled Order**
   - Place order → User cancels manually → Status = CANCELLED → Clean up

5. **Missing Order ID**
   - Place order → No order ID in response → Log warning → Track differently

6. **API Failure During Verification**
   - Pending order → Status check fails → Retry later → Don't assume rejection

## Risk Mitigation

### False Rejection Detection
- Don't mark as rejected if API call fails
- Require explicit REJECTED status from broker
- Keep pending for reasonable duration before giving up

### Notification Fatigue
- Batch rejections if multiple
- Don't spam on transient API errors
- Clear, actionable messages

### Performance
- Batch status checks (one API call for all orders)
- Cache recent checks
- Only verify during market hours

## Monitoring & Alerts

### Metrics to Track
1. Orders placed vs orders executed (acceptance rate)
2. Rejection rate by symbol
3. Rejection rate by time of day
4. Common rejection reasons
5. Time from placement to status update

### Alerts
- Rejection rate > 20% (symbol validation issue?)
- Pending orders > 1 hour old (API issue?)
- Same symbol rejected repeatedly (blocklist?)

## Migration Path

### Existing Orders
For orders already placed before this fix:
1. No order ID available → Cannot verify
2. Trust reconciliation via holdings check
3. After fix deployed → All new orders tracked properly

### Backward Compatibility
- Old history files without `pending_orders` → Initialize empty array
- Graceful handling if order ID extraction fails

## Documentation Updates

1. Update AMO_ORDER_RETRY_FEATURE.md with rejection handling
2. Add ORDER_STATUS_VERIFICATION.md with technical details
3. Update monitoring guide with new metrics
4. Add troubleshooting guide for rejections

## Summary

**Critical Gap**: System assumes order success without verification
**Impact**: Users confused, potential trading errors, poor UX
**Solution**: Order status tracking + verification + rejection handling
**Priority**: CRITICAL - Implement Phase 1 immediately

This is a foundational fix that should be deployed before any further order placement features.
