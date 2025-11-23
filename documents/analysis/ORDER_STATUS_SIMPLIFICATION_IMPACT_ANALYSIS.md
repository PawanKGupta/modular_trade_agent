# Order Status Simplification - Impact Analysis

## Overview

This document provides a comprehensive analysis of all areas that will be impacted by the order status simplification implementation (9 → 5 statuses).

**Changes Summary**:
- `AMO` + `PENDING_EXECUTION` → `PENDING`
- `FAILED` + `RETRY_PENDING` + `REJECTED` → `FAILED` (with unified `reason` field)
- `SELL` → **Removed** (use `side='sell'` column instead)

---

## Impact Areas

### 1. Database Layer

#### 1.1 Schema Changes
**Files**:
- `src/infrastructure/db/models.py`

**Changes Required**:
- Update `OrderStatus` enum (remove `AMO`, `PENDING_EXECUTION`, `RETRY_PENDING`, `REJECTED`, `SELL`)
- Add `PENDING` status
- Add unified `reason` field (String(512))
- Keep old reason fields temporarily for migration (`failure_reason`, `rejection_reason`, `cancelled_reason`)

**Impact**: **HIGH** - Core schema change affecting all order operations

#### 1.2 Database Migration
**Files**:
- `alembic/versions/XXXXX_order_status_simplification.py` (new migration file)

**Changes Required**:
- Migrate existing status values:
  - `AMO` → `PENDING`
  - `PENDING_EXECUTION` → `PENDING`
  - `RETRY_PENDING` → `FAILED`
  - `REJECTED` → `FAILED`
  - `SELL` → `PENDING` (for orders with `side='sell'`)
- Migrate reason fields to unified `reason` field
- Update database indexes if needed

**Impact**: **HIGH** - Data migration required, must be tested thoroughly

**Risk**: Medium - Requires careful migration to avoid data loss

---

### 2. Repository Layer

#### 2.1 Orders Repository
**Files**:
- `src/infrastructure/persistence/orders_repository.py`

**Methods to Update**:
1. **`create_amo()`**:
   - Change default status from `OrderStatus.AMO` to `OrderStatus.PENDING`
   - Add `reason` parameter
   - Set default reason: "Order placed - waiting for market open"

2. **`mark_failed()`**:
   - Remove `retry_pending` parameter (or keep for backward compatibility but ignore)
   - Always set status to `OrderStatus.FAILED` (not `RETRY_PENDING`)
   - Use unified `reason` field instead of `failure_reason`

3. **`mark_rejected()`**:
   - Change status from `OrderStatus.REJECTED` to `OrderStatus.FAILED`
   - Use unified `reason` field instead of `rejection_reason`
   - Format reason: `f"Broker rejected: {rejection_reason}"`

4. **`mark_cancelled()`**:
   - Use unified `reason` field instead of `cancelled_reason`

5. **`mark_executed()`**:
   - Add reason: `f"Order executed at Rs {execution_price:.2f}"`

6. **`get_pending_amo_orders()`**:
   - Change from `AMO` + `PENDING_EXECUTION` to just `PENDING`
   - Consider renaming to `get_pending_orders()`

7. **`get_failed_orders()`**:
   - Change from `RETRY_PENDING` + `FAILED` to just `FAILED`

8. **`get_retriable_failed_orders()`** (new method):
   - Get `FAILED` orders that haven't expired
   - Apply expiry filter (next trading day market close)
   - Mark expired orders as `CANCELLED`

9. **`list()`**:
   - Update to handle new status values
   - Ensure `reason` field is retrieved

10. **`update()`**:
    - Ensure `reason` field can be updated

**Impact**: **HIGH** - Core data access layer, affects all order operations

**Risk**: Medium - Must ensure backward compatibility during migration

---

### 3. Business Logic Layer

#### 3.1 AutoTradeEngine
**Files**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Methods to Update**:

1. **`place_new_entries()`**:
   - Update status checks:
     - `AMO`/`PENDING_EXECUTION` → `PENDING`
     - `RETRY_PENDING`/`REJECTED` → `FAILED`
   - Ensure `CLOSED` and `CANCELLED` are NOT in blocking status set
   - Filter by `side == "buy"` to exclude sell orders from blocking logic
   - Update reason field when creating/updating orders

2. **`retry_pending_orders_from_db()`**:
   - Use `get_retriable_failed_orders()` instead of `get_failed_orders()`
   - Remove status filtering (all returned orders are retriable)
   - Update reason when retrying: "Order retried successfully"

3. **`_sync_order_status_snapshot()`**:
   - Update status mapping:
     - `PENDING_EXECUTION` → `PENDING`
     - `REJECTED` → `FAILED`
   - Update reason field when status changes

4. **`_add_failed_order()`**:
   - Remove `retry_pending` parameter usage
   - Always use `FAILED` status
   - Use unified `reason` field

5. **`evaluate_reentries_and_exits()`**:
   - Update sell order creation to use `PENDING` status with `side='sell'`
   - Set reason: "Sell order placed at EMA9 target"

6. **`has_active_buy_order()`**:
   - Update status checks to use new statuses
   - Filter by `side == "buy"`

**Impact**: **CRITICAL** - Core trading logic, affects all order placement and retry operations

**Risk**: High - Must test thoroughly to avoid breaking order placement logic

---

#### 3.2 OrderTracker
**Files**:
- `modules/kotak_neo_auto_trader/order_tracker.py`

**Methods to Update**:

1. **`add_pending_order()`**:
   - Remove status update from `AMO` to `PENDING_EXECUTION`
   - `create_amo()` already sets `PENDING`
   - Add reason: "Order placed - waiting for market open"

2. **`update_order_status()`**:
   - Update status mapping:
     - `PENDING` → `PENDING` (not `PENDING_EXECUTION`)
     - `REJECTED` → `FAILED` (not `REJECTED`)
     - `CANCELLED` → `CANCELLED` (not `CLOSED`)
   - Update reason field when status changes

**Impact**: **HIGH** - Order tracking and status synchronization

**Risk**: Medium - Must ensure status transitions are correct

---

#### 3.3 OrderStateManager
**Files**:
- `modules/kotak_neo_auto_trader/order_state_manager.py`

**Methods to Update**:

1. **`sync_with_broker()`**:
   - Update status handling:
     - `REJECTED` → `FAILED` (via `mark_rejected()`)
   - Update reason field when status changes

**Impact**: **HIGH** - Broker synchronization logic

**Risk**: Medium - Must ensure broker status mapping is correct

---

#### 3.4 Sell Engine
**Files**:
- `modules/kotak_neo_auto_trader/sell_engine.py`
- `modules/kotak_neo_auto_trader/run_sell_orders.py`

**Methods to Update**:

1. **Sell order placement**:
   - Change from `OrderStatus.SELL` to `OrderStatus.PENDING` with `side='sell'`
   - Set reason: "Sell order placed at EMA9 target"

2. **Sell order monitoring**:
   - Change from `status == OrderStatus.SELL` to `side == "sell" and status == OrderStatus.PENDING`
   - Update all queries to filter by `side` instead of status

**Impact**: **HIGH** - Sell order logic completely changes

**Risk**: High - Sell orders are critical for trade completion

---

#### 3.5 Unified Order Monitor
**Files**:
- `modules/kotak_neo_auto_trader/unified_order_monitor.py`

**Methods to Update**:

1. **`check_buy_order_status()`**:
   - Update status checks to use new statuses
   - Filter by `side == "buy"`

2. **`check_sell_order_status()`**:
   - Change from `status == OrderStatus.SELL` to `side == "sell" and status == OrderStatus.PENDING`
   - Update all status checks

**Impact**: **HIGH** - Order monitoring logic

**Risk**: Medium - Must ensure monitoring works for both buy and sell orders

---

#### 3.6 Order Status Parser
**Files**:
- `modules/kotak_neo_auto_trader/utils/order_status_parser.py`
- `modules/kotak_neo_auto_trader/utils/order_field_extractor.py`

**Methods to Update**:

1. **Broker status mapping**:
   - Update mapping to use new statuses
   - Ensure `REJECTED` maps to `FAILED`

**Impact**: **MEDIUM** - Status parsing from broker responses

**Risk**: Low - Mostly internal utility functions

---

### 4. API Layer

#### 4.1 Orders API
**Files**:
- `server/app/routers/orders.py`

**Endpoints to Update**:

1. **`GET /api/v1/user/orders/`**:
   - Update status filter to accept new statuses
   - Remove `amo`, `pending_execution`, `retry_pending`, `rejected`, `sell` from valid statuses
   - Add `pending`, `failed` to valid statuses
   - Update response schema to include `reason` field
   - Update response schema to include `side` field (if not already present)

2. **`POST /api/v1/user/orders/{order_id}/retry`**:
   - Update to work with `FAILED` status (instead of `RETRY_PENDING`)
   - Update validation logic

3. **Status mapping**:
   - Update status mapping dictionary:
     ```python
     # Before
     "amo": DbOrderStatus.AMO,
     "pending_execution": DbOrderStatus.PENDING_EXECUTION,
     "retry_pending": DbOrderStatus.RETRY_PENDING,
     "rejected": DbOrderStatus.REJECTED,
     "sell": DbOrderStatus.SELL,

     # After
     "pending": DbOrderStatus.PENDING,
     "failed": DbOrderStatus.FAILED,
     # Note: "sell" removed - use side='sell' to identify sell orders
     ```

**Impact**: **HIGH** - API contract changes, affects frontend and external integrations

**Risk**: High - Breaking change for API consumers

---

#### 4.2 API Schemas
**Files**:
- `server/app/schemas/trading_config.py` (if order statuses are referenced)

**Changes Required**:
- Update order status enum in schemas
- Add `reason` field to order response schemas
- Ensure `side` field is included in order schemas

**Impact**: **MEDIUM** - Schema validation and documentation

**Risk**: Medium - Must ensure schemas match database models

---

### 5. Frontend Layer

#### 5.1 TypeScript Types
**Files**:
- `web/src/api/orders.ts` (or similar type definitions)

**Changes Required**:
```typescript
// Before
export type OrderStatus =
  | 'amo'
  | 'pending_execution'
  | 'ongoing'
  | 'sell'
  | 'closed'
  | 'failed'
  | 'retry_pending'
  | 'rejected'
  | 'cancelled';

// After
export type OrderStatus =
  | 'pending'
  | 'ongoing'
  | 'closed'
  | 'failed'
  | 'cancelled';
  // Note: 'sell' removed - use side='sell' to identify sell orders
```

**Impact**: **HIGH** - Type safety and frontend logic

**Risk**: Medium - TypeScript will catch most issues at compile time

---

#### 5.2 UI Components
**Files**:
- `web/src/routes/dashboard/OrdersPage.tsx`
- `web/src/routes/dashboard/PaperTradingPage.tsx`
- `web/src/routes/dashboard/OrderConfigSection.tsx`
- `web/src/routes/dashboard/IndividualServiceControls.tsx`

**Changes Required**:

1. **Order filtering**:
   ```typescript
   // Before
   const sellOrders = orders.filter(o => o.status === 'sell');
   const buyOrders = orders.filter(o => o.status !== 'sell');

   // After
   const sellOrders = orders.filter(o => o.side === 'sell');
   const buyOrders = orders.filter(o => o.side === 'buy');
   ```

2. **Status display**:
   - Update status badges/colors to use new statuses
   - Remove `SELL` status display
   - Add `reason` field display (if needed)

3. **Status filters**:
   - Update dropdown/select options to use new statuses
   - Remove old status options

4. **Order details**:
   - Display `reason` field (if available)
   - Ensure `side` field is displayed

**Impact**: **HIGH** - User-facing changes, affects all order displays

**Risk**: Medium - Must ensure UI correctly displays new statuses and filters

---

#### 5.3 Mock Data
**Files**:
- `web/src/mocks/test-handlers.ts`

**Changes Required**:
- Update mock order data to use new statuses
- Remove `SELL` status from mocks
- Add `reason` field to mock orders
- Ensure `side` field is present in mocks

**Impact**: **LOW** - Testing and development only

**Risk**: Low - Only affects local development

---

### 6. Test Layer

#### 6.1 Unit Tests
**Files** (41 test files identified):
- `tests/unit/infrastructure/test_order_status_enum.py`
- `tests/unit/infrastructure/test_order_monitoring_repository.py`
- `tests/unit/kotak/test_sync_order_status_snapshot.py`
- `tests/unit/kotak/test_sync_order_status_snapshot_coverage.py`
- `tests/unit/kotak/test_cancelled_status_on_order_update.py`
- `tests/unit/kotak/test_auto_trade_engine_retry_from_db.py`
- `tests/unit/kotak/test_duplicate_prevention_multiple_runs.py`
- `tests/unit/kotak/test_unified_order_monitor.py`
- `tests/unit/kotak/test_order_tracker_duplicate_prevention.py`
- `tests/unit/kotak/test_manual_order_detection.py`
- `tests/unit/kotak/test_manual_order_detection_edge_cases.py`
- `tests/unit/kotak/test_capital_recalculation_on_retry.py`
- `tests/unit/kotak/test_reentry_logic_fix.py`
- `tests/unit/kotak/test_auto_trade_engine_failure_status.py`
- `tests/unit/kotak/test_order_tracker_db_only_mode_phase11.py`
- `tests/unit/kotak/test_auto_trade_engine_notifications_phase9.py`
- `tests/unit/kotak/test_order_status_parser.py`
- `tests/unit/kotak/test_order_field_extractor.py`
- `tests/unit/kotak/test_api_response_normalizer.py`
- `tests/unit/kotak/test_order_entity.py`
- `tests/unit/kotak/test_order_enums.py`
- `tests/unit/modules/test_auto_trade_engine_storage.py`
- `tests/unit/modules/test_auto_trade_engine_holdings_fallback.py`
- `tests/unit/modules/test_auto_trade_engine_user_config.py`
- `tests/unit/infrastructure/test_phase1_repositories.py`
- `tests/unit/infrastructure/test_reentry_tracking_orders.py`
- `tests/unit/infrastructure/test_config_factory.py`
- `tests/unit/use_cases/test_execute_trades_partial_sell.py`
- `tests/integration/use_cases/test_execute_trades_use_case.py`
- `tests/integration/kotak/test_order_state_manager.py`
- `tests/regression/test_trading_service_fixes.py`
- ... and more

**Changes Required**:

1. **Test Fixtures**:
   - Replace `OrderStatus.AMO` with `OrderStatus.PENDING`
   - Replace `OrderStatus.PENDING_EXECUTION` with `OrderStatus.PENDING`
   - Replace `OrderStatus.RETRY_PENDING` with `OrderStatus.FAILED`
   - Replace `OrderStatus.REJECTED` with `OrderStatus.FAILED`
   - Replace `OrderStatus.SELL` with `OrderStatus.PENDING` (for sell orders, use `side='sell'`)

2. **Test Assertions**:
   - Update all status assertions to use new statuses
   - Update reason field assertions (use `reason` instead of `failure_reason`/`rejection_reason`/`cancelled_reason`)
   - Update sell order assertions to check `side == "sell"` instead of `status == OrderStatus.SELL`

3. **Test Data**:
   - Update test order creation to use new statuses
   - Add `reason` field to test orders
   - Ensure `side` field is set correctly

**Impact**: **CRITICAL** - All tests must be updated to pass

**Risk**: High - Large number of test files to update, must ensure all tests pass

---

#### 6.2 Integration Tests
**Files**:
- `tests/integration/kotak/test_order_state_manager.py`
- `tests/integration/use_cases/test_execute_trades_use_case.py`
- `tests/paper_trading/test_integration.py`
- `tests/paper_trading/test_paper_trading_basic.py`

**Changes Required**:
- Update end-to-end test scenarios
- Test status transitions with new statuses
- Test sell order flow with `side='sell'`
- Test retry logic with unified `FAILED` status
- Test expiry logic for failed orders

**Impact**: **HIGH** - Integration test coverage

**Risk**: Medium - Must ensure integration tests cover all scenarios

---

#### 6.3 API Tests
**Files**:
- `tests/server/test_orders_endpoint.py`
- `tests/server/test_data_isolation.py`

**Changes Required**:
- Update API endpoint tests to use new statuses
- Test status filtering with new statuses
- Test `reason` field in API responses
- Test `side` field filtering

**Impact**: **HIGH** - API contract testing

**Risk**: Medium - Must ensure API tests validate new contract

---

### 7. Documentation

#### 7.1 Architecture Documentation
**Files**:
- `documents/architecture/ORDER_STATUS_REFERENCE.md`
- `documents/architecture/AMO_VS_PENDING_EXECUTION.md`
- `documents/architecture/RETRY_FILTRATION_LOGIC.md`
- `documents/features/BUG_FIXES.md`

**Changes Required**:
- Update status reference guide (9 → 5 statuses)
- Remove `AMO_VS_PENDING_EXECUTION.md` (no longer relevant) or update to explain why they were merged
- Update retry filtration logic documentation
- Update bug fixes documentation with new status behavior

**Impact**: **MEDIUM** - Documentation accuracy

**Risk**: Low - Documentation only, but important for future reference

---

#### 7.2 API Documentation
**Files**:
- API documentation (OpenAPI/Swagger specs, if any)
- README files

**Changes Required**:
- Update API documentation with new statuses
- Document `reason` field
- Document `side` field usage for sell orders
- Update examples

**Impact**: **MEDIUM** - API documentation accuracy

**Risk**: Low - Documentation only

---

### 8. External Integrations

#### 8.1 Broker Adapters
**Files**:
- `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/kotak_neo_adapter.py`
- `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/paper_trading_adapter.py`

**Changes Required**:
- Update broker status mapping to use new statuses
- Ensure broker-specific statuses map correctly to new unified statuses

**Impact**: **MEDIUM** - Broker integration logic

**Risk**: Medium - Must ensure broker status mapping is correct

---

#### 8.2 Notification Services
**Files**:
- `modules/kotak_neo_auto_trader/telegram_notifier.py`

**Changes Required**:
- Update notification messages to use new statuses
- Include `reason` field in failure notifications
- Update sell order notifications to reference `side='sell'`

**Impact**: **LOW** - Notification formatting only

**Risk**: Low - Cosmetic changes only

---

### 9. Monitoring & Logging

#### 9.1 Logging
**Files**:
- All files that log order statuses

**Changes Required**:
- Update log messages to use new statuses
- Include `reason` field in failure logs
- Update log analysis queries (if any) to use new statuses

**Impact**: **MEDIUM** - Log analysis and debugging

**Risk**: Low - Logging changes only, but important for debugging

---

#### 9.2 Metrics/Dashboards
**Files**:
- Any monitoring dashboards or metrics collection

**Changes Required**:
- Update status-based metrics to use new statuses
- Update dashboard queries to filter by `side` instead of `SELL` status
- Update alert rules (if any) based on order statuses

**Impact**: **MEDIUM** - Monitoring and alerting

**Risk**: Medium - Must ensure monitoring continues to work correctly

---

## Summary

### Impact by Layer

| Layer | Impact Level | Risk Level | Files Affected |
|-------|-------------|------------|----------------|
| **Database** | HIGH | Medium | 1 (models.py) + 1 migration |
| **Repository** | HIGH | Medium | 1 (orders_repository.py) |
| **Business Logic** | CRITICAL | High | 6+ core files |
| **API** | HIGH | High | 2+ files |
| **Frontend** | HIGH | Medium | 5+ files |
| **Tests** | CRITICAL | High | 41+ test files |
| **Documentation** | MEDIUM | Low | 4+ files |
| **External** | MEDIUM | Medium | 2+ files |
| **Monitoring** | MEDIUM | Low | Multiple files |

### Total Impact

- **Files to Modify**: ~60+ files
- **Test Files to Update**: 41+ files
- **Breaking Changes**: API contract, database schema
- **Migration Required**: Yes (database status values and reason fields)

### Risk Assessment

**Overall Risk**: **HIGH**

**Key Risks**:
1. **Data Migration**: Must carefully migrate existing orders without data loss
2. **Test Coverage**: Large number of tests to update, must ensure all pass
3. **API Breaking Changes**: Frontend and external integrations must be updated
4. **Sell Order Logic**: Complete change in how sell orders are tracked
5. **Retry Logic**: Unified `FAILED` status changes retry behavior

### Mitigation Strategies

1. **Phased Rollout**: Deploy in phases (database → code → API → frontend)
2. **Backward Compatibility**: Keep old fields temporarily during migration
3. **Comprehensive Testing**: Run full test suite before deployment
4. **Feature Flags**: Consider feature flags for gradual rollout
5. **Rollback Plan**: Have rollback plan ready
6. **Monitoring**: Monitor closely after deployment for issues

---

*Last Updated: November 23, 2025*
