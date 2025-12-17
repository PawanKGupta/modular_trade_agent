# Unified DB-Only Implementation Plan

**Date**: 2025-12-18
**Version**: 1.0
**Status**: Planning Phase
**Goal**: Migrate from hybrid storage (paper=file, real=DB) to unified DB-only approach

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Implementation Phases](#implementation-phases)
4. [Mode Switching Edge Cases](#mode-switching-edge-cases)
5. [Testing Strategy](#testing-strategy)
6. [Risk Mitigation](#risk-mitigation)
7. [Timeline](#timeline)
8. [Success Criteria](#success-criteria)

---

## Executive Summary

### Goal
Migrate from the current hybrid storage approach (paper trading uses files, real trading uses DB) to a unified DB-only approach where both paper and real trading data are stored in the database with `trade_mode` distinction.

### Benefits
- **Single Codebase**: One storage implementation (easier maintenance)
- **Consistency**: Paper trading mirrors real trading exactly
- **Unified Reporting**: Single dashboard, easy comparison
- **Data Integrity**: ACID transactions, foreign key constraints
- **Scalability**: Handles multiple users efficiently
- **Future-Proof**: Easy to add features, schema migrations

### Estimated Timeline
**6-8 weeks** (with buffer)

### Risk Level
**Medium** (requires careful migration and testing)

---

## Current State Analysis

### Paper Trading File-Based Storage

**Files Currently Used**:
1. `paper_trading/user_{user_id}/active_sell_orders.json`
   - Active sell orders tracking
   - Format: `{symbol: {order_id, target_price, qty, ticker, entry_date}}`

2. `paper_trading/user_{user_id}/account.json` (via PaperTradeStore)
   - Account balance, capital

3. `paper_trading/user_{user_id}/orders.json` (via PaperTradeStore)
   - All order history

4. `paper_trading/user_{user_id}/holdings.json` (via PaperTradeStore)
   - Current portfolio holdings

5. `paper_trading/user_{user_id}/transactions.json` (via PaperTradeStore)
   - Trade history

### Current DB Storage (Real Trading)

**Tables Used**:
1. `orders` table - All buy/sell orders (no `trade_mode` column)
2. `positions` table - Open/closed positions (no `trade_mode` column)
3. `user_settings` table - `trade_mode` field (current mode only)

### Current Code Locations

**Paper Trading (File-Based)**:
- `src/application/services/paper_trading_service_adapter.py`
  - `_load_sell_orders_from_file()` (line 1363)
  - `_save_sell_orders_to_file()` (line 1592)
  - `_place_sell_orders()` (line 886)

**Real Trading (DB-Based)**:
- `modules/kotak_neo_auto_trader/sell_engine.py`
  - `place_sell_order()` - persists to DB (line 2199)
  - `get_open_positions()` - reads from DB (line 436)

**Paper Trading (DB-Based - Partial)**:
- `src/application/services/paper_trading_service_adapter.py`
  - `place_reentry_orders()` - persists buy orders to DB (line 2737)

### Problem Statement

**Current Issues**:
- Inconsistent storage (paper: file, real: DB)
- Code duplication (two storage implementations)
- No unified reporting
- Data loss risk (files can be corrupted)
- Migration complexity when switching modes

---

## Implementation Phases

### Phase 1: Database Schema Updates (Week 1)

#### 1.1 Add `trade_mode` Column to `orders` Table

**Alembic Migration**:
```python
# alembic/versions/YYYYMMDD_add_trade_mode_to_orders.py

def upgrade():
    # Add trade_mode column
    op.add_column('orders',
        sa.Column('trade_mode', sa.String(16), nullable=True))

    # Backfill: Set trade_mode based on user's current setting
    op.execute("""
        UPDATE orders o
        SET trade_mode = (
            SELECT us.trade_mode::text
            FROM user_settings us
            WHERE us.user_id = o.user_id
        )
    """)

    # Make NOT NULL after backfill
    op.alter_column('orders', 'trade_mode', nullable=False)

    # Add index for filtering
    op.create_index('ix_orders_trade_mode', 'orders', ['trade_mode'])

def downgrade():
    op.drop_index('ix_orders_trade_mode', 'orders')
    op.drop_column('orders', 'trade_mode')
```

**SQLAlchemy Model Update**:
```python
# src/infrastructure/db/models.py

class Orders(Base):
    # ... existing fields ...
    trade_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # 'paper'|'broker'
```

#### 1.2 Add `trade_mode` Column to `positions` Table

**Alembic Migration**:
```python
# alembic/versions/YYYYMMDD_add_trade_mode_to_positions.py

def upgrade():
    op.add_column('positions',
        sa.Column('trade_mode', sa.String(16), nullable=True))

    # Backfill
    op.execute("""
        UPDATE positions p
        SET trade_mode = (
            SELECT us.trade_mode::text
            FROM user_settings us
            WHERE us.user_id = p.user_id
        )
    """)

    op.alter_column('positions', 'trade_mode', nullable=False)
    op.create_index('ix_positions_trade_mode', 'positions', ['trade_mode'])

def downgrade():
    op.drop_index('ix_positions_trade_mode', 'positions')
    op.drop_column('positions', 'trade_mode')
```

**SQLAlchemy Model Update**:
```python
# src/infrastructure/db/models.py

class Positions(Base):
    # ... existing fields ...
    trade_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # 'paper'|'broker'
```

#### 1.3 Update Repository Methods

**Files to Update**:
- `src/infrastructure/persistence/orders_repository.py`
  - `create_amo()` - add `trade_mode` parameter
  - `list()` - add `trade_mode` filter option
  - All query methods - add `trade_mode` filtering

- `src/infrastructure/persistence/positions_repository.py`
  - `upsert()` - add `trade_mode` parameter
  - `list()` - add `trade_mode` filter option
  - All query methods - add `trade_mode` filtering

**Testing**:
- Unit tests for repository methods with `trade_mode`
- Integration tests for filtering

---

### Phase 2: Data Migration Script (Week 1-2)

#### 2.1 Create Migration Script

**File**: `scripts/migrate_paper_trading_to_db.py`

**Functionality**:
1. Read all paper trading files for each user
2. Migrate `active_sell_orders.json` → `orders` table
3. Migrate `holdings.json` → `positions` table
4. Migrate `transactions.json` → `orders` table (executed orders)
5. Migrate `orders.json` → `orders` table
6. Validate data integrity
7. Create backup of original files

**Key Features**:
- Dry-run mode (preview changes)
- Per-user migration (can run for specific users)
- Rollback capability (restore from backup)
- Progress tracking
- Validation checks

**Data Mapping**:
```python
# active_sell_orders.json → orders table
{
    "RELIANCE-EQ": {
        "order_id": "12345",
        "target_price": 2500.0,
        "qty": 10,
        "ticker": "RELIANCE.NS",
        "entry_date": "2025-12-18"
    }
}
→
Orders(
    user_id=user_id,
    symbol="RELIANCE-EQ",
    side="sell",
    order_type="limit",
    quantity=10,
    price=2500.0,
    broker_order_id="12345",
    status="pending",  # or "ongoing" if active
    trade_mode="paper",
    order_metadata={
        "ticker": "RELIANCE.NS",
        "entry_date": "2025-12-18",
        "source": "paper_trading_migration"
    }
)
```

#### 2.2 Validation & Testing

**Validation Checks**:
- All file data migrated
- No data loss
- Referential integrity
- Duplicate detection
- Data format validation

**Testing**:
- Test with sample data
- Test with real user data (backup first)
- Test rollback mechanism
- Performance testing (large datasets)

---

### Phase 3: Code Updates - Paper Trading Service (Week 2-3)

#### 3.1 Update `PaperTradingServiceAdapter`

**File**: `src/application/services/paper_trading_service_adapter.py`

**Changes**:

1. **Remove File-Based Sell Order Loading**
   - Remove `_load_sell_orders_from_file()` method
   - Remove `_save_sell_orders_to_file()` method
   - Remove `self._sell_orders_file` initialization

2. **Add DB-Based Sell Order Loading**
   ```python
   def _load_sell_orders_from_db(self):
       """Load active sell orders from database"""
       from src.infrastructure.persistence.orders_repository import OrdersRepository

       orders_repo = OrdersRepository(self.db)
       active_sell_orders = orders_repo.list(
           user_id=self.user_id,
           side="sell",
           status=["pending", "ongoing"],
           trade_mode="paper"
       )

       # Convert to format expected by existing code
       for order in active_sell_orders:
           symbol = order.symbol
           self.active_sell_orders[symbol] = {
               "order_id": order.broker_order_id,
               "target_price": order.price,
               "qty": order.quantity,
               "ticker": order.order_metadata.get("ticker") if order.order_metadata else None,
               "entry_date": order.placed_at.strftime("%Y-%m-%d"),
           }
   ```

3. **Update `_place_sell_orders()`**
   - Persist sell orders to DB via `orders_repo.create_amo()`
   - Set `trade_mode="paper"`
   - Remove file saving

4. **Update `_monitor_sell_orders()`**
   - Update orders in DB instead of file
   - Use `orders_repo.update()` for status changes

5. **Update `_update_sell_order_quantity()`**
   - Update DB instead of file
   - Remove file saving

6. **Update `initialize()`**
   - Call `_load_sell_orders_from_db()` instead of `_load_sell_orders_from_file()`

#### 3.2 Update `PaperTradingBrokerAdapter` Integration

**File**: `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/paper_trading_adapter.py`

**Changes**:
- Keep `PaperTradeStore` for account balance (or migrate to DB)
- Update order placement to persist to DB
- Update holdings sync to use `positions` table

**Decision Point**:
- Option A: Keep `PaperTradeStore` for account/balance only
- Option B: Create `paper_trading_accounts` table

**Recommendation**: Option B (full DB migration)

---

### Phase 4: Code Updates - Repository Layer (Week 3)

#### 4.1 Update `OrdersRepository`

**File**: `src/infrastructure/persistence/orders_repository.py`

**Changes**:

1. **Update `create_amo()`**
   ```python
   def create_amo(
       self,
       *,
       user_id: int,
       symbol: str,
       side: str,
       order_type: str,
       quantity: float,
       price: float | None,
       trade_mode: str | None = None,  # NEW
       # ... other params
   ) -> Orders:
       # Get trade_mode from user_settings if not provided
       if trade_mode is None:
           from src.infrastructure.persistence.settings_repository import SettingsRepository
           settings_repo = SettingsRepository(self.db)
           settings = settings_repo.get_by_user_id(user_id)
           trade_mode = settings.trade_mode.value

       order = Orders(
           # ... existing fields ...
           trade_mode=trade_mode,  # NEW
       )
       # ... rest of method
   ```

2. **Update `list()`**
   ```python
   def list(
       self,
       user_id: int,
       status: OrderStatus | None = None,
       trade_mode: str | None = None,  # NEW
   ) -> list[Orders]:
       # Add trade_mode filter to query
       if trade_mode:
           stmt = stmt.where(Orders.trade_mode == trade_mode)
   ```

3. **Update All Query Methods**
   - `get_by_broker_order_id()` - add `trade_mode` filter
   - `get_by_order_id()` - add `trade_mode` filter
   - `has_successful_buy_order()` - add `trade_mode` filter
   - All other methods - add `trade_mode` parameter

#### 4.2 Update `PositionsRepository`

**File**: `src/infrastructure/persistence/positions_repository.py`

**Changes**:

1. **Update `upsert()`**
   ```python
   def upsert(
       self,
       user_id: int,
       symbol: str,
       trade_mode: str | None = None,  # NEW
       # ... other params
   ) -> Positions:
       # Get trade_mode from user_settings if not provided
       if trade_mode is None:
           from src.infrastructure.persistence.settings_repository import SettingsRepository
           settings_repo = SettingsRepository(self.db)
           settings = settings_repo.get_by_user_id(user_id)
           trade_mode = settings.trade_mode.value

       # ... rest of method
   ```

2. **Update `list()`**
   ```python
   def list(
       self,
       user_id: int,
       trade_mode: str | None = None,  # NEW
   ) -> list[Positions]:
       # Add trade_mode filter
   ```

3. **Update All Query Methods**
   - Add `trade_mode` parameter to all methods
   - Add filtering in queries

---

### Phase 5: Code Updates - Real Trading (Week 3-4)

#### 5.1 Update `SellOrderManager`

**File**: `modules/kotak_neo_auto_trader/sell_engine.py`

**Changes**:

1. **Update `place_sell_order()`**
   - Already persists to DB, but ensure `trade_mode` is set
   - Get `trade_mode` from user settings or context

2. **Update `get_open_positions()`**
   - Already reads from DB, but add `trade_mode` filter
   - Ensure filtering by current user's trade mode

3. **Remove File-Based Loading**
   - Remove any file-based order loading
   - Ensure all orders loaded from DB

#### 5.2 Update `AutoTradeEngine`

**File**: `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Changes**:

1. **Update All `create_amo()` Calls**
   - Ensure `trade_mode` is passed or auto-detected
   - Default to "broker" for real trading

2. **Update Order Queries**
   - Add `trade_mode` filtering everywhere
   - Ensure no mixing of paper and real trading data

---

### Phase 6: Update All Query Points (Week 4)

#### 6.1 Add Filtering Everywhere

**Files to Update**:
- All API endpoints that query orders/positions
- All service methods that query orders/positions
- All repository methods
- All dashboard/reporting queries

**Pattern**:
```python
# Always filter by trade_mode
orders = orders_repo.list(
    user_id=user_id,
    trade_mode=current_trade_mode  # Get from user_settings
)
```

#### 6.2 Update API Endpoints

**Files**:
- `server/app/routers/orders.py`
- `server/app/routers/paper_trading.py`
- `server/app/routers/broker.py`

**Changes**:
- Get `trade_mode` from user settings
- Filter all queries by `trade_mode`
- Ensure no cross-mode data leakage

---

### Phase 7: Mode Switching Edge Cases (Week 4-5)

#### 7.1 Create Mode Switch Handler

**File**: `src/application/services/mode_switch_handler.py`

**Functionality**:
- Handle graceful transitions between modes
- Manage active orders/positions during switch
- Service lifecycle management
- Data preservation

**Key Methods**:
```python
class ModeSwitchHandler:
    def switch_mode(
        self,
        user_id: int,
        new_mode: str,
        cancel_paper_orders: bool = False,
        close_paper_positions: bool = False
    ) -> bool:
        """Switch user's trade mode with configurable options"""

    def _handle_paper_to_broker(
        self,
        user_id: int,
        cancel_orders: bool = False,
        close_positions: bool = False
    ):
        """Handle switching from paper to broker"""

    def _handle_broker_to_paper(self, user_id: int):
        """Handle switching from broker to paper"""
```

#### 7.2 Edge Cases Handling

**Case 1: Paper → Broker Switch**
- Keep paper orders/positions active (default)
- Optional: Cancel paper orders or close positions
- Start broker service
- Both modes coexist in DB

**Case 2: Broker → Paper Switch**
- Always preserve broker data (REAL money)
- Continue monitoring broker positions
- Start paper service
- Both modes coexist in DB

**Case 3: Active Orders During Switch**
- Paper orders: Keep active (or cancel if configured)
- Broker orders: Always keep active (cannot cancel)
- Both can execute independently

**Case 4: Service State Management**
- Graceful shutdown of current service
- Complete current tasks
- Save state to database
- Start new service

**Case 5: Query Filtering**
- Always filter by `trade_mode` in queries
- Prevent data mixing
- Support both modes or current mode only

**Case 6: Duplicate Prevention**
- Filter duplicate checks by `trade_mode`
- Paper and broker orders for same symbol are NOT duplicates
- Holdings checked separately per mode

**Case 7: Position Monitoring**
- Monitor based on current mode (default)
- Or monitor both modes (configurable)
- Filter positions by `trade_mode`

**Case 8: Historical Data**
- Separate reports for paper vs broker
- Comparison view (side-by-side)
- Historical timeline showing mode switches

#### 7.3 Configuration Options

```python
class ModeSwitchConfig:
    """Configuration for mode switching behavior"""

    # When switching from paper to broker
    CANCEL_PAPER_ORDERS_ON_SWITCH: bool = False  # Default: Keep orders
    CLOSE_PAPER_POSITIONS_ON_SWITCH: bool = False  # Default: Keep positions

    # Monitoring
    MONITOR_BOTH_MODES: bool = False  # Default: Monitor current mode only

    # Execution
    EXECUTE_BY_SERVICE: bool = True  # Default: Service that created order executes
```

---

### Phase 8: Testing & Validation (Week 5-6)

#### 8.1 Unit Tests

**Test Files to Update/Create**:
- `tests/unit/persistence/test_orders_repository_trade_mode.py`
- `tests/unit/persistence/test_positions_repository_trade_mode.py`
- `tests/unit/services/test_paper_trading_db_only.py`
- `tests/unit/services/test_real_trading_db_only.py`
- `tests/unit/services/test_mode_switch_handler.py`

**Test Cases**:
- Create orders with `trade_mode`
- Filter orders by `trade_mode`
- Prevent cross-mode data access
- Migration script validation
- Mode switching scenarios

#### 8.2 Integration Tests

**Test Files**:
- `tests/integration/migration/test_paper_trading_migration.py`
- `tests/integration/services/test_unified_db_storage.py`
- `tests/integration/services/test_mode_switching.py`

**Test Scenarios**:
- Full migration flow
- Paper trading order placement → DB
- Real trading order placement → DB
- Switching between modes
- Data isolation between modes
- Active orders during switch
- Position monitoring

#### 8.3 End-to-End Tests

**Test Scenarios**:
- Paper trading workflow (buy → sell → monitor)
- Real trading workflow (buy → sell → monitor)
- Mode switching (paper → broker → paper)
- Data persistence across restarts
- Concurrent users (different modes)
- Historical data querying

---

### Phase 9: Cleanup & Documentation (Week 6-7)

#### 9.1 Remove File-Based Code

**Files to Clean Up**:
- Remove `_load_sell_orders_from_file()`
- Remove `_save_sell_orders_to_file()`
- Remove `PaperTradeStore` (if fully migrated)
- Remove file-based order tracking

**Keep** (if needed):
- `PaperTradeStore` for account balance only (or migrate to DB)
- File-based logging (separate concern)

#### 9.2 Update Documentation

**Documents to Update**:
- Architecture documentation
- API documentation
- Developer guide
- Migration guide

**New Documents**:
- `UNIFIED_DB_STORAGE.md` - Architecture decision
- `MODE_SWITCHING_GUIDE.md` - How to handle mode switches

#### 9.3 Deprecation Warnings

**Add Warnings**:
- Log warnings if file-based code is still called
- Add deprecation notices in code comments
- Update README with migration status

---

## Testing Strategy

### Unit Tests

**Coverage**:
- Repository methods with `trade_mode`
- Service methods with mode filtering
- Mode switch handler
- Data validation

### Integration Tests

**Coverage**:
- Migration script
- Order placement (both modes)
- Position tracking (both modes)
- Mode switching scenarios
- Data isolation

### End-to-End Tests

**Coverage**:
- Complete workflows (both modes)
- Mode switching
- Data persistence
- Concurrent users
- Historical queries

---

## Risk Mitigation

### Risk 1: Data Loss During Migration

**Mitigation**:
- Full database backup before migration
- File backups before migration
- Dry-run mode in migration script
- Rollback script ready
- Test on staging first

### Risk 2: Performance Degradation

**Mitigation**:
- Add indexes on `trade_mode` columns
- Query optimization
- Load testing
- Monitor query performance

### Risk 3: Breaking Changes

**Mitigation**:
- Feature flag for new code
- Gradual rollout (per user)
- Comprehensive testing
- Rollback plan ready

### Risk 4: Incomplete Migration

**Mitigation**:
- Validation checks in migration script
- Post-migration verification
- Monitoring and alerts
- Support for partial migration

### Risk 5: Mode Switching Issues

**Mitigation**:
- Comprehensive edge case handling
- Graceful service transitions
- Data preservation
- User notifications

---

## Rollback Plan

### If Migration Fails

1. **Stop Migration Process**
   - Halt all migration scripts
   - Prevent new data writes

2. **Restore from Backup**
   - Restore database from backup
   - Restore files from backup
   - Verify data integrity

3. **Revert Code Changes**
   - Revert to previous code version
   - Restore file-based code paths
   - Verify system functionality

4. **Investigate Issues**
   - Analyze failure cause
   - Fix issues
   - Plan retry

### If Issues Found Post-Migration

1. **Identify Affected Users**
   - Check logs for errors
   - Identify data inconsistencies

2. **Fix Data Issues**
   - Run data correction scripts
   - Manual fixes if needed

3. **Monitor System**
   - Watch for errors
   - Check data integrity
   - User feedback

---

## Timeline

| Phase | Duration | Dependencies | Key Deliverables |
|-------|----------|--------------|------------------|
| Phase 1: Schema Updates | 1 week | None | `trade_mode` columns, indexes |
| Phase 2: Data Migration | 1 week | Phase 1 | Migration script, data validation |
| Phase 3: Paper Trading Code | 1 week | Phase 1, Phase 2 | DB-based paper trading |
| Phase 4: Repository Updates | 1 week | Phase 1 | Updated repositories |
| Phase 5: Real Trading Code | 1 week | Phase 1, Phase 4 | DB-based real trading |
| Phase 6: Query Updates | 1 week | Phase 4, Phase 5 | Filtered queries |
| Phase 7: Mode Switching | 1 week | All phases | Mode switch handler |
| Phase 8: Testing | 1 week | All phases | Test suite |
| Phase 9: Cleanup | 1 week | Phase 8 | Documentation, cleanup |

**Total**: 8-9 weeks (with buffer)

---

## Success Criteria

### Phase 1 Success
- ✅ `trade_mode` columns added to tables
- ✅ All existing data backfilled
- ✅ Indexes created
- ✅ Tests passing

### Phase 2 Success
- ✅ Migration script completes successfully
- ✅ All file data migrated to DB
- ✅ Data validation passes
- ✅ No data loss

### Phase 3-6 Success
- ✅ All code updated to use DB
- ✅ File-based code removed
- ✅ All queries filter by `trade_mode`
- ✅ Tests passing

### Phase 7 Success
- ✅ Mode switching works correctly
- ✅ Edge cases handled
- ✅ Data preserved
- ✅ Services transition gracefully

### Phase 8 Success
- ✅ All tests passing
- ✅ No performance degradation
- ✅ Data isolation verified
- ✅ Mode switching tested

### Phase 9 Success
- ✅ Documentation updated
- ✅ Code cleanup complete
- ✅ System stable
- ✅ User acceptance

---

## Dependencies

### External Dependencies
- Database access (PostgreSQL/SQLite)
- Alembic for migrations
- Backup system

### Internal Dependencies
- User settings repository
- Orders repository
- Positions repository
- Paper trading service
- Real trading service
- Mode switch handler

---

## Post-Migration Benefits

1. **Single Codebase**
   - One storage implementation
   - Easier maintenance
   - Faster feature development

2. **Unified Reporting**
   - Single dashboard
   - Compare paper vs real performance
   - Historical analysis

3. **Data Integrity**
   - ACID transactions
   - Foreign key constraints
   - Data validation

4. **Scalability**
   - Handles multiple users
   - Concurrent access
   - Indexed queries

5. **Future-Proof**
   - Easy to add features
   - Schema migrations
   - Complex relationships

6. **Mode Switching**
   - Seamless transitions
   - Data preservation
   - Flexible configuration

---

## Next Steps

1. **Review & Approve Plan**
   - Team review
   - Stakeholder approval
   - Resource allocation

2. **Set Up Environment**
   - Staging database
   - Test data
   - Backup system

3. **Start Phase 1**
   - Create Alembic migrations
   - Update models
   - Test schema changes

4. **Execute Plan**
   - Follow phases sequentially
   - Test at each phase
   - Monitor progress

---

## Appendix

### A. File Structure Changes

**Before**:
```
paper_trading/
  user_1/
    active_sell_orders.json
    account.json
    orders.json
    holdings.json
    transactions.json
```

**After**:
```
paper_trading/
  user_1/
    (empty or removed)
```

### B. Database Schema Changes

**Before**:
```sql
orders (
    id, user_id, symbol, side, order_type, quantity, price, status, ...
    -- NO trade_mode
)

positions (
    id, user_id, symbol, quantity, avg_price, ...
    -- NO trade_mode
)
```

**After**:
```sql
orders (
    id, user_id, symbol, side, order_type, quantity, price, status, ...
    trade_mode VARCHAR(16) NOT NULL,  -- NEW
    INDEX ix_orders_trade_mode (trade_mode)  -- NEW
)

positions (
    id, user_id, symbol, quantity, avg_price, ...
    trade_mode VARCHAR(16) NOT NULL,  -- NEW
    INDEX ix_positions_trade_mode (trade_mode)  -- NEW
)
```

### C. Code Pattern Changes

**Before**:
```python
# Paper trading
self._load_sell_orders_from_file()
self._save_sell_orders_to_file()

# Real trading
orders_repo.create_amo(...)
```

**After**:
```python
# Both modes
orders_repo.create_amo(..., trade_mode="paper")  # or "broker"
orders = orders_repo.list(user_id, trade_mode="paper")
```

### D. Critical Rules

1. ✅ Always filter queries by `trade_mode`
2. ✅ Never cancel broker orders automatically (real money)
3. ✅ Never close broker positions automatically (real money)
4. ✅ Preserve all historical data
5. ✅ Graceful service transitions
6. ✅ Data isolation between modes

---

## Questions & Decisions Needed

1. **Paper Trading Account Balance**
   - Keep in file or migrate to DB?
   - **Recommendation**: Create `paper_trading_accounts` table

2. **Migration Strategy**
   - Big bang or gradual?
   - **Recommendation**: Gradual (per user)

3. **Feature Flag**
   - Use feature flag for rollout?
   - **Recommendation**: Yes, for safety

4. **File Cleanup**
   - When to delete old files?
   - **Recommendation**: After 30 days of stable operation

5. **Mode Switch Defaults**
   - Cancel paper orders on switch?
   - **Recommendation**: No (keep for comparison)

6. **Monitoring Strategy**
   - Monitor both modes or current only?
   - **Recommendation**: Current mode only (configurable)

---

**Document Status**: Ready for Review
**Last Updated**: 2025-12-18
