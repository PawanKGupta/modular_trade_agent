# Phase 3 Implementation: Unified Order State Manager

## Overview

Phase 3 introduces a unified `OrderStateManager` that consolidates order state management across multiple storage systems, providing a single source of truth for order tracking.

## Problem Solved

**Before Phase 3:**
- Order state tracked in 4 separate places:
  1. `active_sell_orders` dict in `SellOrderManager` (in-memory)
  2. `pending_orders.json` via `OrderTracker` (file-based)
  3. `trades` in `trades_history.json` (file-based)
  4. `failed_orders` in `trades_history.json` (file-based)
- State synchronization required manual updates in multiple places
- Risk of state inconsistency
- Complex queries across multiple sources

**After Phase 3:**
- Single `OrderStateManager` interface
- Atomic updates across all state sources
- Thread-safe operations
- Consistent state management

## Implementation

### OrderStateManager Class

**Location:** `modules/kotak_neo_auto_trader/order_state_manager.py`

**Key Features:**
1. **Unified Interface**: Single API for all order state operations
2. **Atomic Updates**: Updates all state sources in one operation
3. **Thread Safety**: Uses locks for concurrent access
4. **Backward Compatible**: Works alongside existing code

### Core Methods

#### `register_sell_order()`
- Registers new sell order
- Updates: `active_sell_orders`, `pending_orders`, trade history (if needed)
- Returns: Success status

#### `mark_order_executed()`
- Marks order as executed
- Updates: Removes from `active_sell_orders`, updates `pending_orders`, updates trade history
- Returns: Success status

#### `sync_with_broker()`
- Syncs state with broker API
- Detects: Executed orders, rejected orders, cancelled orders, manual sells
- Returns: Stats dict with sync results

#### `get_active_sell_orders()`
- Returns all active sell orders
- Thread-safe read operation

#### `update_sell_order_price()`
- Updates target price for active order
- Thread-safe update

#### `remove_from_tracking()`
- Removes order from tracking (rejected/cancelled)
- Updates all state sources

## Usage Example

```python
from modules.kotak_neo_auto_trader.order_state_manager import OrderStateManager

# Initialize
state_manager = OrderStateManager(
    history_path="data/trades_history.json",
    data_dir="data"
)

# Register sell order
state_manager.register_sell_order(
    symbol="RELIANCE-EQ",
    order_id="12345",
    target_price=2500.0,
    qty=10,
    ticker="RELIANCE.NS"
)

# Sync with broker
stats = state_manager.sync_with_broker(orders_api)
# Returns: {'checked': 1, 'executed': 1, 'rejected': 0, ...}

# Get active orders
active_orders = state_manager.get_active_sell_orders()
```

## Migration Strategy

### Option 1: Incremental Migration (Recommended)
- Keep existing code working
- Gradually migrate modules to use `OrderStateManager`
- Both systems coexist during transition
- Lower risk, easier rollback

### Option 2: Full Migration
- Replace all direct state management with `OrderStateManager`
- Requires comprehensive testing
- Higher risk, cleaner end state

## Testing

**Test File:** `tests/integration/kotak/test_order_state_manager.py`

**Test Coverage:**
- ✅ Order registration
- ✅ Order execution marking
- ✅ Price updates
- ✅ Order removal
- ✅ Broker synchronization
- ✅ Thread safety
- ✅ Trade history integration

## Benefits

1. **Single Source of Truth**: One place to query order state
2. **Atomic Updates**: No risk of partial updates
3. **Consistency**: State always synchronized
4. **Thread Safety**: Safe for concurrent operations
5. **Maintainability**: Easier to understand and modify
6. **Testability**: Easier to test unified interface

## Risk Assessment

**Risk Level:** Medium-High (Architectural Change)

**Mitigation:**
- Backward compatible design
- Incremental migration option
- Comprehensive test suite
- Thread-safe operations
- Error handling and logging

## Future Enhancements

1. **State Persistence**: Save `active_sell_orders` to disk for recovery
2. **State Validation**: Validate state consistency on startup
3. **State Reconciliation**: Detect and fix inconsistencies
4. **Metrics**: Track state operations for monitoring
5. **Full Migration**: Complete migration of all modules

## Status

✅ **Phase 3 Core Implementation Complete**
- OrderStateManager class created
- All core methods implemented
- Comprehensive test suite
- Documentation complete

⏳ **Optional Next Steps:**
- Migrate `SellOrderManager` to use `OrderStateManager`
- Add state persistence for `active_sell_orders`
- Implement state validation and reconciliation

