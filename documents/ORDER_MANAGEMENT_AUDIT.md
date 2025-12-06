# Order Management Flow Audit

**Date**: 2025-12-06  
**Purpose**: Validate that all order lifecycle events are tracked in the database with proper timestamps

---

## Order Lifecycle Events

### 1. Order Creation/Placement

**Event**: Order is created and placed with broker

**Current Tracking**:
- ✅ `placed_at` - Set when order is created via `create_amo()` (line 210 in orders_repository.py)
- ✅ `status` - Set to `PENDING` (default)
- ✅ `reason` - Set to "Order placed - waiting for market open"

**Code Location**:
- `src/infrastructure/persistence/orders_repository.py::create_amo()` (line 200-220)
- `modules/kotak_neo_auto_trader/auto_trade_engine.py::place_new_entries()` (line 3698)
- `modules/kotak_neo_auto_trader/auto_trade_engine.py::place_reentry_orders()` (line 4819)

**Status**: ✅ **TRACKED**

---

### 2. Order Status Check

**Event**: System checks order status with broker

**Current Tracking**:
- ✅ `last_status_check` - Updated via `update_status_check()` (line 385-388 in orders_repository.py)

**Code Location**:
- `src/infrastructure/persistence/orders_repository.py::update_status_check()` (line 385-388)
- `modules/kotak_neo_auto_trader/unified_order_monitor.py::_update_buy_order_status()` (line 584)
- `modules/kotak_neo_auto_trader/auto_trade_engine.py::_sync_order_status_snapshot()` (line 2369)

**Status**: ✅ **TRACKED**

---

### 3. Order Execution

**Event**: Order is executed/filled by broker

**Current Tracking**:
- ✅ `execution_time` - Set to current time (line 379)
- ✅ `filled_at` - Set to current time (line 380)
- ✅ `execution_price` - Price at which order executed (line 377)
- ✅ `execution_qty` - Quantity executed (line 378)
- ✅ `status` - Changed to `ONGOING` (line 376)
- ✅ `last_status_check` - Updated (line 381)
- ✅ `reason` - Set to "Order executed at Rs {price:.2f}" (line 382)

**Code Location**:
- `src/infrastructure/persistence/orders_repository.py::mark_executed()` (line 369-383)
- `modules/kotak_neo_auto_trader/unified_order_monitor.py::_update_buy_order_status()` (line 595)
- `modules/kotak_neo_auto_trader/unified_order_monitor.py::_handle_buy_order_execution()` (line 495)

**Status**: ✅ **TRACKED**

---

### 4. Order Rejection

**Event**: Order is rejected by broker

**Current Tracking**:
- ✅ `status` - Changed to `FAILED` (line 356)
- ✅ `reason` - Set to "Broker rejected: {rejection_reason}" (line 357)
- ✅ `last_status_check` - Updated (line 358)
- ⚠️ `first_failed_at` - **NOT SET** (should be set for rejected orders)

**Code Location**:
- `src/infrastructure/persistence/orders_repository.py::mark_rejected()` (line 351-359)
- `modules/kotak_neo_auto_trader/unified_order_monitor.py::_update_buy_order_status()` (line 602)
- `modules/kotak_neo_auto_trader/auto_trade_engine.py::_sync_order_status_snapshot()` (line 2375)

**Status**: ✅ **TRACKED** (Fixed: `first_failed_at` now set in `mark_rejected()`)

---

### 5. Order Cancellation

**Event**: Order is cancelled (by user or system)

**Current Tracking**:
- ✅ `status` - Changed to `CANCELLED` (line 363)
- ✅ `closed_at` - Set to current time (line 365)
- ✅ `reason` - Set to cancellation reason (line 364)
- ✅ `last_status_check` - Updated (line 366)

**Code Location**:
- `src/infrastructure/persistence/orders_repository.py::mark_cancelled()` (line 361-367)
- `modules/kotak_neo_auto_trader/unified_order_monitor.py::_update_buy_order_status()` (line 605)
- `modules/kotak_neo_auto_trader/auto_trade_engine.py::_sync_order_status_snapshot()` (line 2378)
- `modules/kotak_neo_auto_trader/sell_engine.py::_cancel_pending_reentry_orders()` (line 1284, 1296)

**Status**: ✅ **TRACKED**

---

### 6. Order Failure

**Event**: Order fails (API error, validation failure, etc.)

**Current Tracking**:
- ✅ `status` - Changed to `FAILED` (line 341)
- ✅ `reason` - Set to failure reason (line 342)
- ✅ `first_failed_at` - Set to current time (only if not already set) (line 343-344)
- ✅ `last_retry_attempt` - Set to current time (line 345)
- ✅ `retry_count` - Incremented (line 347)

**Code Location**:
- `src/infrastructure/persistence/orders_repository.py::mark_failed()` (line 330-349)
- `modules/kotak_neo_auto_trader/auto_trade_engine.py::place_new_entries()` (line 611)
- `modules/kotak_neo_auto_trader/auto_trade_engine.py::retry_failed_orders()` (line 663)

**Status**: ✅ **TRACKED**

---

### 7. Order Modification/Update

**Event**: Order details are updated (quantity, price, broker_order_id, etc.)

**Current Tracking**:
- ✅ `update()` method updates fields but **does NOT track modification timestamp**
- ⚠️ **MISSING**: No `updated_at` or `last_modified_at` field

**Code Location**:
- `src/infrastructure/persistence/orders_repository.py::update()` (line 293-322)
- Multiple locations where `orders_repo.update()` is called

**Status**: ⚠️ **NOT FULLY TRACKED** - Missing modification timestamp

---

### 8. Order Quantity Adjustment (Pre-market AMO)

**Event**: AMO order quantity is adjusted before market open

**Current Tracking**:
- ✅ `quantity` - Updated with new quantity
- ✅ `status` - May remain `PENDING` or change
- ⚠️ **MISSING**: No timestamp tracking when quantity is adjusted

**Code Location**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py::adjust_amo_quantities_premarket()` (line 3216)

**Status**: ⚠️ **PARTIALLY TRACKED** - Missing adjustment timestamp

---

### 9. Order Closure (Sell Order Execution)

**Event**: Buy order is closed when corresponding sell order executes

**Current Tracking**:
- ✅ `status` - Changed to `CLOSED` (when sell executes)
- ✅ `closed_at` - Set when position is closed
- ⚠️ **MISSING**: No explicit tracking of when buy order transitions from `ONGOING` to `CLOSED`

**Code Location**:
- `modules/kotak_neo_auto_trader/sell_engine.py::monitor_and_update()` (line 2188)
- `src/infrastructure/persistence/positions_repository.py::mark_closed()` (sets position closed_at)

**Status**: ✅ **TRACKED** (Fixed: `_close_buy_orders_for_symbol()` now closes buy orders when sell executes)

---

### 10. Manual Order Detection

**Event**: System detects manual order placed by user

**Current Tracking**:
- ✅ `broker_order_id` - Updated with manual order ID
- ✅ `quantity` - Updated with manual order quantity
- ✅ `price` - Updated with manual order price
- ✅ `status` - Set to `PENDING`
- ⚠️ **MISSING**: No timestamp tracking when manual order is detected

**Code Location**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py::_detect_and_handle_manual_buys()` (line 3686, 3698)

**Status**: ⚠️ **PARTIALLY TRACKED** - Missing detection timestamp

---

## Summary of Issues

### ✅ Fixed Issues

1. **Order Rejection Missing `first_failed_at`** ✅ **FIXED**
   - **Fix**: `mark_rejected()` now sets `first_failed_at` if not already set
   - **File**: `src/infrastructure/persistence/orders_repository.py::mark_rejected()` (line 359-360)

2. **Buy Order Closure Timestamp Missing** ✅ **FIXED**
   - **Fix**: Added `_close_buy_orders_for_symbol()` method that closes ONGOING buy orders when sell executes
   - **File**: `modules/kotak_neo_auto_trader/sell_engine.py::_close_buy_orders_for_symbol()` (line 1323-1385)
   - **Integration**: Called in `monitor_and_update()` after position is marked as closed

### Remaining Issues

1. **Order Modification Timestamp Missing**
   - **Issue**: No `updated_at` or `last_modified_at` field to track when order details change
   - **Impact**: Cannot audit when order was modified
   - **Recommendation**: Add `updated_at` field to Orders model and update it in `update()` method
   - **Note**: This requires a database migration

### Medium Issues (Missing Context Timestamps)

4. **AMO Quantity Adjustment Timestamp Missing**
   - **Issue**: No timestamp tracking when AMO order quantity is adjusted
   - **Impact**: Cannot audit pre-market adjustments
   - **Recommendation**: Add `quantity_adjusted_at` field or log in `order_metadata`

5. **Manual Order Detection Timestamp Missing**
   - **Issue**: No timestamp tracking when manual order is detected
   - **Impact**: Cannot audit manual order detection
   - **Recommendation**: Add `manual_detected_at` field or log in `order_metadata`

---

## Recommendations

### Priority 1: Add `updated_at` Field

**Action**: Add `updated_at` field to Orders model and update it in all `update()` calls

**Benefits**:
- Complete audit trail of all order modifications
- Can track when order details change
- Useful for debugging and compliance

### Priority 2: Fix Missing Timestamps in Existing Methods

**Actions**:
1. Set `first_failed_at` in `mark_rejected()` if not already set
2. Set buy order's `closed_at` when sell order executes
3. Track quantity adjustment timestamps

### Priority 3: Add Context Timestamps (Optional)

**Actions**:
1. Add `quantity_adjusted_at` for AMO adjustments
2. Add `manual_detected_at` for manual order detection
3. Or use `order_metadata` JSON field to store these timestamps

---

## Database Schema Changes Required

### Add `updated_at` Field to Orders Table

```sql
ALTER TABLE orders ADD COLUMN updated_at DATETIME;
CREATE INDEX ix_orders_updated_at ON orders(updated_at);
```

### Update Model

```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime, default=ist_now, onupdate=ist_now, nullable=False
)
```

---

## Implementation Checklist

- [x] Fix `mark_rejected()` to set `first_failed_at` ✅ **DONE**
- [x] Set buy order's `closed_at` when sell executes ✅ **DONE**
- [x] Add `updated_at` field to Orders model ✅ **DONE**
- [x] Update `update()` method to set `updated_at` ✅ **DONE**
- [x] Update `create_amo()` method to set `updated_at` ✅ **DONE**
- [x] Update `list()` method to include `updated_at` in queries ✅ **DONE**
- [x] Create Alembic migration for `updated_at` field ✅ **DONE**
- [x] Run migration: `alembic upgrade head` ✅ **DONE**
- [ ] Add quantity adjustment timestamp tracking (optional - can use `order_metadata`)
- [ ] Add manual order detection timestamp tracking (optional - can use `order_metadata`)
- [ ] Add tests for timestamp tracking
- [ ] Update documentation

