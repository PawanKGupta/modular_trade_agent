# Unified Order Monitoring Implementation Plan

## Implementation Progress

- ✅ **Phase 1: Database Schema & Models** - COMPLETE
  - Added new OrderStatus enum values (FAILED, RETRY_PENDING, REJECTED, PENDING_EXECUTION)
  - Added order monitoring fields to Orders model
  - Created Alembic migration
  - Updated OrdersRepository with helper methods
  - Updated API schema and router
  - Added comprehensive tests (>80% coverage)

- ✅ **Phase 2: Unified Order Monitor Core** - COMPLETE
  - Created UnifiedOrderMonitor class
  - Added buy order loading from DB
  - Implemented buy order status checking
  - Integrated into TradingService
  - Added 25 unit tests with 88% coverage
- ✅ **Phase 3: Order State Manager Extensions** - COMPLETE
  - Added active_buy_orders tracking structure
  - Added register_buy_order() method
  - Extended sync_with_broker() for buy orders
  - Added mark_buy_order_executed() with trade history integration
  - Added buy order rejection/cancellation handling
  - Added 13 new tests with 83% coverage

- ✅ **Phase 4: Trading Service Integration** - COMPLETE
  - Added buy order loading at market open (9:15 AM)
  - Added buy order registration with OrderStateManager
  - Integrated buy order monitoring into continuous loop
  - Added market close handling (orders tracked next day)
  - Added 7 new tests with 85% coverage
- ⏳ **Phase 5: Immediate Polling After Placement** - PENDING
- ⏳ **Phase 6: Failure Status Promotion** - PENDING
- ⏳ **Phase 7: Pending Orders DB Migration** - PENDING
- ⏳ **Phase 8: Retry Queue API & UI** - PENDING
- ⏳ **Phase 9: Notifications** - PENDING
- ⏳ **Phase 10: Manual Activity Detection** - PENDING
- ⏳ **Phase 11: Cleanup & Optimization** - PENDING

## Overview

This document outlines the implementation plan for extending the existing sell order monitoring system to include AMO buy order tracking, reconciliation, and state management. The goal is to create a unified order monitoring system that handles both buy and sell orders during market hours with proper status tracking, failure handling, and user visibility.

## Current State Analysis

### Existing Infrastructure
- **Sell Order Monitoring**: `SellOrderManager.monitor_and_update()` runs every minute during market hours (9:15 AM - 3:30 PM)
- **Order State Manager**: `OrderStateManager.sync_with_broker()` syncs sell orders with broker status
- **Trading Service**: `TradingService.run_sell_monitor()` orchestrates continuous monitoring
- **Broker API**: `orders.get_orders()` and `orders.get_executed_orders()` already fetch all orders

### Current Gaps
1. AMO buy orders never verified after placement (rejection tracking gap)
2. Failed orders hidden in metadata/JSON, not exposed via API
3. Manual cancellations/modifications not detected for buy orders
4. Retry queue not visible or controllable via UI
5. `pending_orders.json` grows indefinitely without cleanup
6. No notifications for buy order state changes

## Implementation Goals

1. **Unified Monitoring**: Single system monitors both buy and sell orders during market hours
2. **Status Reconciliation**: Poll broker to verify order status (immediate + market hours)
3. **First-Class Statuses**: Explicit order statuses (failed, retry_pending, rejected, cancelled)
4. **Manual Activity Detection**: Track manual cancellations/modifications for buy orders
5. **Retry Queue Visibility**: API/UI to view and manage failed orders
6. **Database Migration**: Move pending orders from JSON to DB with dual-write transition
7. **Comprehensive Notifications**: Alert users on all order state changes

## Architecture Changes

### 1. Database Schema Updates

#### Orders Table Enhancements
```sql
-- Add new status values
ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'failed';
ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'retry_pending';
ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'rejected';
ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'pending_execution';

-- Add new columns
ALTER TABLE orders ADD COLUMN IF NOT EXISTS failure_reason TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS first_failed_at TIMESTAMP;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS last_retry_attempt TIMESTAMP;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cancelled_reason TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS last_status_check TIMESTAMP;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS execution_price NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS execution_qty NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS execution_time TIMESTAMP;
```

### 2. Unified Order Monitor

**New Component**: `OrderMonitor` (extends/refactors `SellOrderManager`)
- Monitors both buy and sell orders in single loop
- Queries broker once per cycle for all orders
- Updates status for both order types
- Handles execution, rejection, cancellation for both

**Key Methods**:
- `monitor_all_orders()` - Main monitoring loop (replaces `monitor_and_update()`)
- `check_buy_order_status()` - Check AMO buy order status
- `check_sell_order_status()` - Check sell order status (existing)
- `update_order_status_in_db()` - Update order status in database
- `handle_order_execution()` - Process executed orders (buy and sell)
- `handle_order_rejection()` - Process rejected orders
- `handle_order_cancellation()` - Process cancelled orders

### 3. Order State Manager Extensions

**Extend `OrderStateManager`**:
- Add `active_buy_orders` tracking (similar to `active_sell_orders`)
- Extend `sync_with_broker()` to handle buy orders
- Add buy order status update methods
- Track buy order execution and update trade history

### 4. Trading Service Integration

**Modify `TradingService.run_sell_monitor()`**:
- Rename to `run_order_monitor()` (or keep name, extend functionality)
- Load pending AMO buy orders from DB at start
- Add buy orders to monitoring alongside sell orders
- Use same polling interval (every minute during market hours)

## Implementation Phases

### Phase 1: Database Schema & Models (Week 1) ✅ COMPLETE

**Tasks**:
1. ✅ Create Alembic migration for new columns and status values
2. ✅ Update `OrderStatus` enum in `src/infrastructure/db/models.py`
3. ✅ Update `OrdersRepository` to handle new fields
4. ✅ Add validation for status transitions
5. ✅ Create database indexes for new query patterns

**Deliverables**:
- ✅ Migration script: `alembic/versions/b8f2a1c3d4e5_add_order_monitoring_fields.py`
- ✅ Updated models: Added 10 new fields to Orders model
- ✅ Repository methods: Added 8 new helper methods for status management
- ✅ API updates: Extended schema and router to support new statuses and fields

**Testing**:
- ✅ Unit tests for enum values: `tests/unit/infrastructure/test_order_status_enum.py` (8 test cases, 100% coverage)
- ✅ Repository tests: `tests/unit/infrastructure/test_order_monitoring_repository.py` (18 test cases, >80% coverage)
- ✅ API endpoint tests: Extended `tests/server/test_orders_endpoint.py` (6 test cases)
- ✅ Schema tests: `server/app/schemas/orders.py` (100% coverage)
- ✅ Model tests: `src/infrastructure/db/models.py` (100% coverage for new fields)
- ✅ Test coverage: >80% for all new functionality (schemas: 100%, models: 100%, repository: >80%)

**New Features Added**:
- **OrderStatus Enum**: Added FAILED, RETRY_PENDING, REJECTED, PENDING_EXECUTION
- **Failure Tracking**: failure_reason, first_failed_at, last_retry_attempt, retry_count
- **Rejection Tracking**: rejection_reason, cancelled_reason
- **Execution Tracking**: execution_price, execution_qty, execution_time
- **Status Monitoring**: last_status_check timestamp
- **Repository Methods**: mark_failed(), mark_rejected(), mark_cancelled(), mark_executed(), update_status_check(), get_pending_amo_orders(), get_failed_orders()

---

### Phase 2: Unified Order Monitor Core (Week 2) ✅ COMPLETE

**Tasks**:
1. ✅ Create `UnifiedOrderMonitor` class that wraps `SellOrderManager`
2. ✅ Add buy order loading from DB (status='amo')
3. ✅ Implement buy order status checking
4. ✅ Extend broker order query to process both buy and sell
5. ✅ Add status update logic for buy orders
6. ✅ Implement execution tracking for buy orders
7. ✅ Integrate into TradingService

**Key Changes**:
- ✅ Created `modules/kotak_neo_auto_trader/unified_order_monitor.py`
- ✅ Added `load_pending_buy_orders()` method
- ✅ Added `check_buy_order_status()` method
- ✅ Added `_update_buy_order_status()` method
- ✅ Added `monitor_all_orders()` unified method
- ✅ Updated `TradingService.run_sell_monitor()` to use unified monitor

**Deliverables**:
- ✅ Unified monitoring method: `monitor_all_orders()`
- ✅ Buy order status checking: `check_buy_order_status()`
- ✅ Status update logic: `_update_buy_order_status()`
- ✅ Database integration for buy order tracking

**Testing**:
- ✅ Unit tests for buy order status checking: `tests/unit/kotak/test_unified_order_monitor.py` (25 test cases)
- ✅ Test coverage: 88% for unified_order_monitor.py (exceeds 80% requirement)
- ✅ Tests cover: initialization, buy order loading, status checking, status updates, error handling, unified monitoring

---

### Phase 3: Order State Manager Extensions (Week 2-3) ✅ COMPLETE

**Tasks**:
1. ✅ Extend `OrderStateManager.sync_with_broker()` for buy orders
2. ✅ Add `active_buy_orders` tracking structure
3. ✅ Implement buy order execution detection
4. ✅ Add buy order rejection/cancellation handling
5. ✅ Update trade history on buy order execution

**Key Changes**:
- ✅ `modules/kotak_neo_auto_trader/order_state_manager.py`
- ✅ Added `active_buy_orders` tracking structure
- ✅ Added `register_buy_order()` method
- ✅ Extended `sync_with_broker()` to check buy orders
- ✅ Added `mark_buy_order_executed()` method
- ✅ Added `remove_buy_order_from_tracking()` method
- ✅ Added `get_active_buy_orders()` and `get_active_buy_order()` helper methods

**Deliverables**:
- ✅ Extended state manager with buy order support
- ✅ Buy order tracking in-memory cache
- ✅ Trade history integration (adds new positions on buy execution)

**Testing**:
- ✅ Unit tests for buy order tracking: Extended `tests/integration/kotak/test_order_state_manager.py` (13 new test cases)
- ✅ Test coverage: 83% for order_state_manager.py (exceeds 80% requirement)
- ✅ Tests cover: registration, execution, rejection, cancellation, sync with broker, trade history updates

---

### Phase 4: Trading Service Integration (Week 3) ✅ COMPLETE

**Tasks**:
1. ✅ Modify `TradingService.run_sell_monitor()` to load buy orders
2. ✅ Add buy order initialization at market open
3. ✅ Integrate buy order monitoring into continuous loop
4. ✅ Add buy order cleanup at market close
5. ✅ Handle orders placed after market hours (start tracking next day)

**Key Changes**:
- ✅ `modules/kotak_neo_auto_trader/run_trading_service.py`
  - Added buy order loading at market open (9:15 AM)
  - Added buy order registration with OrderStateManager
  - Added market close handling (orders tracked next day)
- ✅ `modules/kotak_neo_auto_trader/unified_order_monitor.py`
  - Added `register_buy_orders_with_state_manager()` method
  - Updated buy order handlers to use OrderStateManager
  - Integrated execution, rejection, cancellation with state manager

**Deliverables**:
- ✅ Integrated monitoring service with buy order support
- ✅ Market hours handling (9:15 AM - 3:30 PM)
- ✅ Order lifecycle management (load at market open, track during hours, cleanup at close)

**Testing**:
- ✅ Extended `tests/unit/kotak/test_unified_order_monitor.py` (7 new test cases)
- ✅ Test coverage: 85% for unified_order_monitor.py (exceeds 80% requirement)
- ✅ Tests cover: registration with state manager, execution/rejection/cancellation handlers, error handling

---

### Phase 5: Immediate Polling After Placement (Week 3)

**Tasks**:
1. Add immediate status check after AMO placement
2. Poll broker once after order placement (within 10-30 seconds)
3. Update order status immediately if rejected
4. Send notification if immediate rejection detected
5. Add to `_attempt_place_order()` method

**Key Changes**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- Add `_verify_order_placement()` method
- Call after successful order placement
- Handle immediate rejections

**Deliverables**:
- Immediate verification
- Rejection detection
- Notification on immediate failure

**Testing**:
- Unit tests for immediate polling
- Rejection scenario tests
- Notification tests

---

### Phase 6: Failure Status Promotion (Week 4)

**Tasks**:
1. Update `_add_failed_order()` to set status='failed' or 'retry_pending'
2. Store failure metadata in new columns (not just metadata JSON)
3. Update failed order creation to use new status values
4. Migrate existing failed orders from metadata to explicit status
5. Update API to return new status values

**Key Changes**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- `src/infrastructure/persistence/orders_repository.py`
- `server/app/routers/orders.py`

**Deliverables**:
- First-class failure statuses
- Migration script for existing data
- Updated API responses

**Testing**:
- Status transition tests
- Migration tests
- API response tests

---

### Phase 7: Pending Orders DB Migration (Week 4-5)

**Tasks**:
1. Create `pending_orders` table or use existing `orders` table with status
2. Implement dual-write: write to both JSON and DB
3. Implement dual-read: read from DB first, fallback to JSON
4. Create migration script to move existing JSON entries to DB
5. Add feature flag for dual-write/DB-only modes
6. Deprecate JSON writes after migration complete

**Migration Strategy**:
- Phase 7a: Dual-write mode (1 week)
- Phase 7b: Dual-read mode (1 week)
- Phase 7c: Migrate existing data (1 day)
- Phase 7d: DB-only mode (remove JSON dependency)

**Key Changes**:
- `modules/kotak_neo_auto_trader/order_tracker.py`
- Add DB write methods
- Add migration script
- Update all consumers to use DB

**Deliverables**:
- Dual-write implementation
- Migration script
- DB-only mode

**Testing**:
- Dual-write tests
- Migration tests
- Backward compatibility tests

---

### Phase 8: Retry Queue API & UI (Week 5)

**Tasks**:
1. Create API endpoint `/api/v1/user/orders/failed` or extend existing endpoint
2. Add query parameters for filtering (status, reason, date range)
3. Add endpoints for manual retry and drop operations
4. Update UI to show failed orders tab/section
5. Display retry count, expiry time, shortfall amount
6. Add manual retry/drop buttons

**API Endpoints**:
- `GET /api/v1/user/orders?status=failed` - List failed orders
- `POST /api/v1/user/orders/{id}/retry` - Force retry
- `DELETE /api/v1/user/orders/{id}` - Drop from retry queue

**Key Changes**:
- `server/app/routers/orders.py`
- `web/src/routes/dashboard/OrdersPage.tsx`
- `web/src/api/orders.ts`

**Deliverables**:
- Failed orders API
- UI components
- Manual retry/drop functionality

**Testing**:
- API endpoint tests
- UI component tests
- Manual retry tests

---

### Phase 9: Notifications (Week 5-6)

**Tasks**:
1. Add notification triggers for all order state changes
2. Send Telegram/email on rejection, cancellation, execution
3. Include broker rejection reason in notifications
4. Add notification preferences (which events to notify)
5. Rate limit notifications to avoid spam

**Notification Events**:
- Order placed successfully
- Order rejected (immediate or delayed)
- Order cancelled (manual or system)
- Order executed
- Order modified manually
- Retry queue updated

**Key Changes**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- `modules/kotak_neo_auto_trader/order_monitor.py`
- `core/telegram.py` (extend)

**Deliverables**:
- Notification system
- Event triggers
- User preferences

**Testing**:
- Notification trigger tests
- Rate limiting tests
- Message format tests

---

### Phase 10: Manual Activity Detection (Week 6)

**Tasks**:
1. Extend `OrderStateManager.sync_with_broker()` for buy orders
2. Detect manual cancellations by comparing broker status
3. Detect manual modifications (price/qty changes)
4. Update DB and tracking when manual changes detected
5. Send notification on manual activity

**Key Changes**:
- `modules/kotak_neo_auto_trader/order_state_manager.py`
- Add buy order comparison logic
- Add modification detection

**Deliverables**:
- Manual activity detection
- Status updates
- Notifications

**Testing**:
- Manual cancellation tests
- Manual modification tests
- State sync tests

---

### Phase 11: Cleanup & Optimization (Week 6-7)

**Tasks**:
1. Remove JSON dependency after migration complete
2. Clean up old `pending_orders.json` file
3. Optimize database queries (add indexes)
4. Add monitoring metrics (order status distribution)
5. Performance testing and optimization
6. Documentation updates

**Key Changes**:
- Remove JSON file operations
- Add database indexes
- Add monitoring/logging
- Update documentation

**Deliverables**:
- Cleaned up codebase
- Performance optimizations
- Updated documentation

**Testing**:
- Performance tests
- Load tests
- Documentation review

---

## Testing Strategy

### Unit Tests
- Order status transitions
- Broker API mocking
- State manager operations
- Notification triggers

### Integration Tests
- End-to-end order placement → monitoring → execution
- Dual-write/read operations
- Migration scripts
- API endpoints

### E2E Tests
- Full order lifecycle (place → monitor → execute/reject)
- Manual cancellation detection
- Retry queue operations
- UI interactions

### Performance Tests
- Database query performance
- Broker API rate limiting
- Concurrent order monitoring
- Large order volume handling

## Migration Plan

### Data Migration
1. **Existing Failed Orders**: Migrate from `order_metadata["failed_order"]` to explicit status
2. **Pending Orders JSON**: Migrate `pending_orders.json` entries to DB
3. **Status Updates**: Update existing AMO orders with new status values

### Code Migration
1. **Dual-Write Period**: 2 weeks (write to both JSON and DB)
2. **Dual-Read Period**: 1 week (read from DB, fallback to JSON)
3. **DB-Only Period**: Remove JSON dependency

### Rollback Plan
- Feature flags for each phase
- Database migration rollback scripts
- JSON backup before migration

## Success Criteria

1. ✅ All AMO buy orders verified after placement (immediate + market hours)
2. ✅ Failed orders visible in UI with clear status and reason
3. ✅ Manual cancellations/modifications detected and updated
4. ✅ Retry queue accessible via API/UI with manual controls
5. ✅ Pending orders stored in DB (no JSON dependency)
6. ✅ Notifications sent for all order state changes
7. ✅ Unified monitoring system handles both buy and sell orders
8. ✅ Zero data loss during migration
9. ✅ Performance acceptable (< 1 second per monitoring cycle)
10. ✅ All tests passing

## Timeline

- **Week 1**: Database schema & models
- **Week 2**: Unified order monitor core
- **Week 3**: State manager extensions & trading service integration
- **Week 4**: Immediate polling & failure status promotion
- **Week 5**: Pending orders migration & retry queue API/UI
- **Week 6**: Notifications & manual activity detection
- **Week 7**: Cleanup, optimization, documentation

**Total Duration**: 7 weeks

## Risk Mitigation

1. **Broker API Rate Limits**: Batch queries, add delays, cache responses
2. **Data Loss During Migration**: Backup JSON, dual-write period, rollback scripts
3. **Performance Degradation**: Database indexes, query optimization, monitoring
4. **Breaking Changes**: Feature flags, gradual rollout, backward compatibility
5. **Notification Spam**: Rate limiting, user preferences, batching

## Dependencies

- Database migration tools (Alembic)
- Broker API access (Kotak Neo)
- Notification services (Telegram)
- UI framework (React)
- Testing framework (pytest)

## Open Questions

1. Should we create separate `pending_orders` table or use `orders` table with status?
2. What notification channels besides Telegram? (Email, SMS, Push)
3. How long to keep historical order data? (Retention policy)
4. Should manual retry respect portfolio limits?
5. What's the acceptable polling interval? (Currently 1 minute)

## Next Steps

1. Review and approve this plan
2. Create detailed technical specifications for each phase
3. Set up development environment and branch strategy
4. Begin Phase 1 implementation
5. Schedule weekly progress reviews

---

**Document Version**: 1.0
**Last Updated**: 2025-01-XX
**Author**: Development Team
**Status**: Draft - Pending Review
