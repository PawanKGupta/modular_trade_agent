# Order Tracking and Status Sync Implementation Plan

## Problem Statement

Orders placed through `ExecuteTradesUseCase` (used by the `buy_orders` service) are not being tracked in the database or synced with broker status. This causes:

1. **Order Visibility Issues**: Orders don't appear in order queries/UI
2. **No Status Updates**: Order status changes (execution, rejection) are not detected
3. **Missing Sell Orders**: Executed buy orders don't trigger sell order placement
4. **Data Inconsistency**: Broker has orders that system doesn't know about

### Current Behavior

- **AutoTradeEngine path**: ✅ Tracks orders + immediate sync
- **ExecuteTradesUseCase path**: ❌ No tracking + no sync

## Current Architecture

### Order Placement Flow

```
ExecuteTradesUseCase
  └─> PlaceOrderUseCase
       └─> KotakNeoBrokerAdapter.place_order()
            └─> Returns order_id
                 └─> ❌ No tracking
                 └─> ❌ No status sync
```

### Order Monitoring Flow

```
UnifiedOrderMonitor.monitor_all_orders() [runs every 1 min during market hours]
  ├─> Fetches broker orders once
  ├─> check_buy_order_status(broker_orders) - syncs buy orders
  └─> sell_manager.monitor_and_update() - syncs sell orders
```

### Service Status Checking

- **Unified Service**: `ConflictDetectionService.is_unified_service_running(user_id)`
- **Individual Service**: `IndividualServiceStatusRepository.get_by_user_and_task(user_id, "sell_monitor")`

## Solution Design

### Core Principle

**Only track system-placed orders** (not manual orders from broker):
- System orders: `orig_source = 'signal'` or `None`
- Manual orders: `orig_source = 'manual'` (excluded from tracking)

### Strategy

1. **Track all system-placed orders** in database via `add_pending_order()`
2. **Leverage existing monitoring** - if monitoring service is running, skip immediate sync
3. **Provide manual sync** - API endpoint for when monitoring is not active
4. **Service-aware sync** - check if unified/sell_monitor service is running instead of market hours

## Implementation Plan

### Phase 1: Add Order Tracking to ExecuteTradesUseCase

#### 1.1 Add Dependencies

**File**: `src/application/use_cases/execute_trades.py`

```python
# Add imports
from modules.kotak_neo_auto_trader.order_tracker import add_pending_order
from src.infrastructure.persistence.orders_repository import OrdersRepository
```

#### 1.2 Add Helper Function

```python
def _is_order_monitoring_active(self) -> bool:
    """
    Check if order monitoring is active (unified service or sell_monitor individual service).

    Returns:
        True if unified service OR sell_monitor service is running
    """
    if not self.user_id or not self.db_session:
        return False

    # Check unified service
    from src.application.services.conflict_detection_service import ConflictDetectionService
    conflict_service = ConflictDetectionService(self.db_session)
    if conflict_service.is_unified_service_running(self.user_id):
        return True

    # Check sell_monitor individual service
    from src.infrastructure.persistence.individual_service_status_repository import (
        IndividualServiceStatusRepository
    )
    status_repo = IndividualServiceStatusRepository(self.db_session)
    sell_monitor_status = status_repo.get_by_user_and_task(self.user_id, "sell_monitor")
    if sell_monitor_status and sell_monitor_status.is_running:
        return True

    return False
```

#### 1.3 Track Orders After Placement

**Location**: After line 151 in `execute()` method

```python
# After successful order placement:
order_id = resp.order_id or ""

# Always track the order (creates DB entry)
try:
    add_pending_order(
        order_id=order_id,
        symbol=stock.ticker,
        ticker=stock.ticker,
        qty=qty,
        order_type="MARKET",
        variety="REGULAR",
        price=0.0,
        entry_type="initial",  # or from recommendation if available
        order_metadata={
            "verdict": stock.final_verdict or stock.verdict,
            "combined_score": stock.combined_score,
            "execution_capital": capital_to_use,
        },
    )
    logger.debug(f"Order {order_id} tracked in database")
except Exception as e:
    logger.warning(f"Failed to track order {order_id}: {e}")
    # Don't fail order placement if tracking fails

# Check if order monitoring is active
if self._is_order_monitoring_active():
    # Monitoring is active - periodic sync will handle status updates
    logger.debug(
        f"Order {order_id} tracked. Status will sync via active monitoring service."
    )
else:
    # No monitoring active - suggest manual sync
    logger.info(
        f"Order {order_id} placed but monitoring service is not running. "
        f"Use POST /api/v1/user/orders/sync to update status."
    )
```

### Phase 2: Create Manual Sync API Endpoint

#### 2.1 Add Endpoint to Orders Router

**File**: `server/app/routers/orders.py`

```python
@router.post("/sync", response_model=dict)
def sync_order_status(
    order_id: int | None = Query(
        None, description="Optional: Sync specific order. If None, syncs all pending/ongoing orders"
    ),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> dict:
    """
    Manually sync order status from broker.

    Useful when:
    - Order monitoring service is not running
    - Force refresh order status
    - Troubleshooting order status issues

    Args:
        order_id: Optional order ID to sync specific order. If None, syncs all pending/ongoing orders.

    Returns:
        Dict with sync results: {
            "synced": int,
            "updated": int,
            "executed": int,
            "rejected": int,
            "cancelled": int,
            "errors": list[str]
        }
    """
    try:
        # Check if monitoring is active
        from src.application.services.conflict_detection_service import ConflictDetectionService
        from src.infrastructure.persistence.individual_service_status_repository import (
            IndividualServiceStatusRepository
        )

        conflict_service = ConflictDetectionService(db)
        status_repo = IndividualServiceStatusRepository(db)

        is_unified_running = conflict_service.is_unified_service_running(current.id)
        sell_monitor_status = status_repo.get_by_user_and_task(current.id, "sell_monitor")
        is_sell_monitor_running = sell_monitor_status.is_running if sell_monitor_status else False

        if is_unified_running or is_sell_monitor_running:
            return {
                "message": "Order monitoring service is active. Status syncs automatically every minute.",
                "sync_performed": False,
                "monitoring_active": True
            }

        # Perform manual sync
        from src.infrastructure.persistence.orders_repository import OrdersRepository
        from src.infrastructure.db.models import OrderStatus
        from modules.kotak_neo_auto_trader.shared_session_manager import (
            get_shared_session_manager
        )
        from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter import (
            KotakNeoBrokerAdapter
        )
        from modules.kotak_neo_auto_trader.infrastructure.broker_factory import BrokerFactory
        from server.app.routers.broker import (
            decrypt_broker_credentials,
            create_temp_env_file,
        )
        from src.infrastructure.persistence.settings_repository import SettingsRepository
        from src.infrastructure.db.models import TradeMode
        from pathlib import Path

        orders_repo = OrdersRepository(db)
        settings_repo = SettingsRepository(db)
        settings = settings_repo.get_by_user_id(current.id)

        if not settings or settings.trade_mode != TradeMode.BROKER:
            raise HTTPException(
                status_code=400,
                detail="Broker mode required for order sync"
            )

        if not settings.broker_creds_encrypted:
            raise HTTPException(
                status_code=400,
                detail="Broker credentials not configured"
            )

        # Get broker session
        broker_creds = decrypt_broker_credentials(settings.broker_creds_encrypted)
        env_file = create_temp_env_file(broker_creds)

        try:
            session_manager = get_shared_session_manager()
            auth = session_manager.get_or_create_session(
                current.id, env_file, db
            )

            broker = BrokerFactory.create_broker("kotak_neo", auth)
            if not broker.connect():
                raise HTTPException(
                    status_code=503,
                    detail="Failed to connect to broker"
                )

            # Fetch broker orders
            orders_api = broker.orders if hasattr(broker, 'orders') else None
            if not orders_api:
                raise HTTPException(
                    status_code=500,
                    detail="Broker orders API not available"
                )

            orders_response = orders_api.get_orders() or {}
            broker_orders = orders_response.get("data", []) if isinstance(orders_response, dict) else []

            # Get orders to sync
            if order_id:
                # Sync specific order
                order = orders_repo.get(order_id)
                if not order or order.user_id != current.id:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Order {order_id} not found"
                    )
                orders_to_sync = [order]
            else:
                # Sync all pending/ongoing orders
                orders_to_sync = orders_repo.list(
                    current.id,
                    status=None  # Get all, filter below
                )
                orders_to_sync = [
                    o for o in orders_to_sync
                    if o.status in [OrderStatus.PENDING, OrderStatus.ONGOING]
                ]

            # Sync each order
            stats = {
                "synced": 0,
                "updated": 0,
                "executed": 0,
                "rejected": 0,
                "cancelled": 0,
                "errors": []
            }

            from modules.kotak_neo_auto_trader.utils.order_field_extractor import (
                OrderFieldExtractor
            )

            for db_order in orders_to_sync:
                stats["synced"] += 1
                order_id_str = db_order.broker_order_id or db_order.order_id
                if not order_id_str:
                    stats["errors"].append(f"Order {db_order.id} has no broker_order_id")
                    continue

                # Find order in broker orders
                broker_order = None
                for bo in broker_orders:
                    broker_order_id = OrderFieldExtractor.get_order_id(bo)
                    if broker_order_id == str(order_id_str):
                        broker_order = bo
                        break

                if not broker_order:
                    # Order not found in broker - might be executed and removed
                    # Check holdings to see if it was executed
                    continue

                # Extract status
                status = OrderFieldExtractor.get_status(broker_order)
                status_lower = status.lower() if status else ""

                if not status_lower:
                    continue

                # Update order status
                try:
                    if status_lower in ["rejected", "reject"]:
                        rejection_reason = OrderFieldExtractor.get_rejection_reason(broker_order) or "Rejected by broker"
                        orders_repo.mark_rejected(db_order, rejection_reason)
                        stats["rejected"] += 1
                        stats["updated"] += 1
                    elif status_lower in ["cancelled", "cancel"]:
                        cancelled_reason = OrderFieldExtractor.get_rejection_reason(broker_order) or "Cancelled"
                        orders_repo.mark_cancelled(db_order, cancelled_reason)
                        stats["cancelled"] += 1
                        stats["updated"] += 1
                    elif status_lower in ["executed", "filled", "complete"]:
                        execution_price = OrderFieldExtractor.get_price(broker_order)
                        execution_qty = OrderFieldExtractor.get_filled_quantity(broker_order) or OrderFieldExtractor.get_quantity(broker_order) or db_order.quantity
                        orders_repo.mark_executed(
                            db_order,
                            execution_price=execution_price,
                            execution_qty=execution_qty,
                        )
                        stats["executed"] += 1
                        stats["updated"] += 1
                    elif status_lower in ["pending", "open", "trigger_pending"]:
                        # Update last_status_check
                        orders_repo.update_status_check(db_order)
                        stats["updated"] += 1
                except Exception as e:
                    stats["errors"].append(f"Error updating order {db_order.id}: {str(e)}")

            return {
                "message": f"Order sync completed",
                "sync_performed": True,
                "monitoring_active": False,
                **stats
            }

        finally:
            # Cleanup temp env file
            try:
                Path(env_file).unlink(missing_ok=True)
            except Exception:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error syncing order status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync order status: {str(e)}"
        ) from e
```

### Phase 3: Update Order Tracker Integration

#### 3.1 Ensure Order Tracker Has Required Context

**File**: `modules/kotak_neo_auto_trader/order_tracker.py`

The `add_pending_order()` function already:
- ✅ Checks for existing orders (prevents duplicates)
- ✅ Creates DB entry via `orders_repo.create_amo()`
- ✅ Sets `orig_source` appropriately (not 'manual')

**No changes needed** - existing implementation is correct.

### Phase 4: Testing

#### 4.1 Unit Tests

**File**: `tests/unit/use_cases/test_execute_trades_tracking.py`

```python
"""
Tests for order tracking in ExecuteTradesUseCase
"""

def test_order_tracking_when_monitoring_active():
    """Test that orders are tracked when monitoring service is active"""
    # Mock monitoring service as running
    # Place order
    # Verify add_pending_order was called
    # Verify no immediate sync attempted

def test_order_tracking_when_monitoring_inactive():
    """Test that orders are tracked when monitoring service is inactive"""
    # Mock monitoring service as not running
    # Place order
    # Verify add_pending_order was called
    # Verify log message suggests manual sync

def test_order_tracking_handles_failure_gracefully():
    """Test that order placement succeeds even if tracking fails"""
    # Mock add_pending_order to raise exception
    # Place order
    # Verify order placement still succeeds
    # Verify error is logged

def test_duplicate_order_prevention():
    """Test that duplicate orders are prevented"""
    # Place order twice for same symbol
    # Verify second order returns existing order
```

#### 4.2 Integration Tests

**File**: `tests/integration/test_order_sync_api.py`

```python
"""
Integration tests for manual order sync API
"""

def test_manual_sync_when_monitoring_active():
    """Test that sync endpoint returns message when monitoring is active"""
    # Start monitoring service
    # Call sync endpoint
    # Verify response indicates monitoring is active

def test_manual_sync_specific_order():
    """Test syncing a specific order"""
    # Create order in DB
    # Mock broker order response
    # Call sync endpoint with order_id
    # Verify order status updated

def test_manual_sync_all_orders():
    """Test syncing all pending/ongoing orders"""
    # Create multiple orders in DB
    # Mock broker orders response
    # Call sync endpoint without order_id
    # Verify all orders synced
```

### Phase 5: Documentation Updates

#### 5.1 Update API Documentation

- Add `/api/v1/user/orders/sync` endpoint to API docs
- Document when to use manual sync
- Document service status checking

#### 5.2 Update User Guide

- Explain order tracking behavior
- Explain when manual sync is needed
- Explain service status implications

## Implementation Checklist

### Phase 1: Core Tracking
- [ ] Add imports to `ExecuteTradesUseCase`
- [ ] Add `_is_order_monitoring_active()` helper method
- [ ] Add order tracking after placement
- [ ] Add logging for monitoring status
- [ ] Handle tracking failures gracefully

### Phase 2: Manual Sync API
- [ ] Create `/orders/sync` endpoint
- [ ] Implement service status checking
- [ ] Implement broker order fetching
- [ ] Implement status update logic
- [ ] Add error handling
- [ ] Add response formatting

### Phase 3: Testing
- [ ] Write unit tests for tracking
- [ ] Write integration tests for sync API
- [ ] Test with monitoring active
- [ ] Test with monitoring inactive
- [ ] Test error scenarios

### Phase 4: Documentation
- [ ] Update API documentation
- [ ] Update user guide
- [ ] Add code comments

## Potential Issues and Mitigations

### Issue 1: Order Tracker Not Initialized

**Problem**: `add_pending_order()` requires OrderTracker to be initialized with user_id and db_session.

**Mitigation**:
- Ensure OrderTracker is properly initialized via singleton pattern
- Check if tracking is available before calling
- Log warning if tracking unavailable

### Issue 2: Duplicate Order Creation

**Problem**: Multiple calls to `add_pending_order()` for same order.

**Mitigation**:
- `add_pending_order()` already checks for existing orders
- `create_amo()` also checks for duplicates
- Both prevent duplicate creation

### Issue 3: Service Status Check Performance

**Problem**: Checking service status on every order placement.

**Mitigation**:
- Cache service status check result (TTL: 30 seconds)
- Service status checks are lightweight DB queries
- Acceptable performance impact

### Issue 4: Manual Sync API Complexity

**Problem**: Manual sync endpoint requires broker connection setup.

**Mitigation**:
- Reuse existing broker connection logic from broker router
- Handle errors gracefully
- Return clear error messages

### Issue 5: Race Conditions

**Problem**: Order placed and tracked simultaneously with periodic monitoring.

**Mitigation**:
- Database transactions ensure consistency
- `last_status_check` timestamp prevents redundant updates
- Existing monitoring logic handles this

## Success Criteria

1. ✅ All system-placed orders are tracked in database
2. ✅ Order status syncs automatically when monitoring is active
3. ✅ Manual sync available when monitoring is inactive
4. ✅ No duplicate orders created
5. ✅ Order placement succeeds even if tracking fails
6. ✅ Clear logging and user guidance
7. ✅ Comprehensive test coverage

## Timeline

- **Phase 1**: 2-3 hours (Core tracking implementation)
- **Phase 2**: 3-4 hours (Manual sync API)
- **Phase 3**: 2-3 hours (Testing)
- **Phase 4**: 1 hour (Documentation)

**Total**: ~8-11 hours

## Dependencies

- `OrderTracker` module (already exists)
- `OrdersRepository` (already exists)
- `ConflictDetectionService` (already exists)
- `IndividualServiceStatusRepository` (already exists)
- Broker session management (already exists)

## Notes

- This implementation maintains backward compatibility
- No breaking changes to existing APIs
- Only adds new functionality
- Follows existing code patterns and architecture
