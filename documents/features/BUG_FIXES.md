## Bug Fix #79: Paper Trading Target Exit - Pending Orders Never Execute

**Date Fixed**: November 27, 2025
**Status**: ✅ Fixed
**Severity**: 🔴 Critical

### Problem
Even though sell orders were placed at target price (EMA9), positions weren't being squared off when the target was reached. The pending limit sell orders were never checked to see if they should execute.

**What Was Happening**:
1. ✅ Sell limit orders placed at target price (by `_place_sell_orders()`)
2. ✅ Orders stored as PENDING/OPEN
3. ❌ **Orders never checked for execution** when price reaches target
4. ❌ **No trade history** with P&L when position closes

This caused:
- Positions to remain open even after target hit
- Unrealized P&L to keep fluctuating
- No completed trade records in history
- Inaccurate paper trading performance tracking

### Root Cause

**Missing Mechanism**: The paper trading broker had no periodic check to execute pending limit orders when price conditions are met.

**Flow Issue**:
```
1. Place limit sell order at Rs 2600 → Order status: OPEN
2. Price reaches Rs 2650 (>= target) → Order STILL OPEN (no execution check!)
3. Monitor detects target hit → Only logs, doesn't trigger execution
4. Position remains open indefinitely
```

### Solution

Implemented a complete order execution and trade tracking system:

#### 1. Added `check_and_execute_pending_orders()` to Paper Trading Broker

**File**: `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/paper_trading_adapter.py`

```python
def check_and_execute_pending_orders(self) -> dict:
    """Check all pending limit orders and execute if price conditions are met"""
    summary = {"checked": 0, "executed": 0, "still_pending": 0}

    pending_orders = self.get_pending_orders()
    for order in pending_orders:
        if order.order_type == OrderType.LIMIT:
            self._execute_order(order)  # Checks price & executes if conditions met
            if order.is_executed():
                summary["executed"] += 1

    return summary
```

#### 2. Enhanced Transaction Recording with P&L

**File**: `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/paper_trading_adapter.py`

Modified `_record_transaction()` to include trade completion details:

```python
# For sell orders, capture entry price BEFORE reducing holding
trade_info = {
    "entry_price": holding.average_price.amount,
    "exit_price": execution_price.amount,
    "realized_pnl": realized_pnl.amount,
    "charges": charges,
}

# Store in transaction with P&L
transaction["entry_price"] = entry_price
transaction["exit_price"] = exit_price
transaction["realized_pnl"] = pnl
transaction["pnl_percentage"] = pnl_pct
transaction["exit_reason"] = "Target Hit" | "RSI > 50" | "Manual"
```

#### 3. Integrated Execution Check in Sell Monitor

**File**: `src/application/services/paper_trading_service_adapter.py`

Added execution check at start of `_monitor_sell_orders()`:

```python
def _monitor_sell_orders(self):
    # Check and execute any pending limit orders first
    execution_summary = self.broker.check_and_execute_pending_orders()
    if execution_summary["executed"] > 0:
        self.logger.info(f"Executed {execution_summary['executed']} pending sell orders")

    # Then check exit conditions and clean up tracking
    ...
```

### Files Modified

1. **`modules/kotak_neo_auto_trader/infrastructure/broker_adapters/paper_trading_adapter.py`**
   - Added `check_and_execute_pending_orders()` method
   - Enhanced `_record_transaction()` to capture P&L for sell orders
   - Modified `_update_portfolio_after_execution()` to return trade info

2. **`src/application/services/paper_trading_service_adapter.py`**
   - Added call to `check_and_execute_pending_orders()` in `_monitor_sell_orders()`
   - Updated exit condition logic to check holdings before removing from tracking

3. **`tests/unit/application/test_paper_trading_service_adapter.py`**
   - Updated `test_monitor_sell_orders_target_reached` to verify execution check
   - Mocked `check_and_execute_pending_orders()` and `get_holding()`

### Testing

**Unit Test**: `test_monitor_sell_orders_target_reached` ✅ Passed
- Verifies `check_and_execute_pending_orders()` is called
- Confirms order removed from tracking when position closes
- All 10 sell monitoring tests pass

### Complete Flow (After Fix)

```
1. _place_sell_orders() → Limit order at Rs 2600 (OPEN)
2. Price reaches Rs 2650
3. _monitor_sell_orders() calls check_and_execute_pending_orders()
4. OrderSimulator checks: Rs 2650 >= Rs 2600 ✓
5. Order executes → Holding reduced/removed
6. Transaction recorded with:
   - Entry: Rs 2500
   - Exit: Rs 2600
   - P&L: Rs +4000 (+4.0%)
   - Exit reason: "Target Hit"
7. Position closed, trade history updated
```

### Impact

- ✅ Pending limit orders now execute automatically when price conditions are met
- ✅ Positions correctly square off at target price
- ✅ Completed trades stored with full P&L details (entry, exit, realized P&L, %)
- ✅ Trade history shows accurate performance metrics
- ✅ Exit reason tracked ("Target Hit", "RSI > 50", "Manual")
- ✅ Paper trading results now match real trading behavior

---

## Feature #78: Signal Status & Soft Delete - Buying Zone Expiry Management

**Date Implemented**: November 27, 2025
**Status**: ✅ Implemented

### Description
Implemented a comprehensive signal lifecycle management system using soft deletion. Signals in the buying zone now have explicit statuses tracking their lifecycle: `ACTIVE`, `EXPIRED`, `TRADED`, and `REJECTED`.

**Problem**: Previously, buying zone signals never expired. Stale signals from previous analysis runs remained visible indefinitely, causing confusion about which signals were current.

**User Requirements**:
- Signals should expire "till next analysis run" (not a fixed time like end of day)
- Expired signals should be visible in UI with different styling
- Signals should be marked as `TRADED` when orders are placed
- Users should be able to manually reject signals
- Status filtering in the UI

### Implementation Details

#### 1. Database Schema Changes

**File**: `alembic/versions/d8bee4599cff_add_status_to_signals.py`

Added `status` column to `signals` table with enum type:

```python
SignalStatus = Enum('ACTIVE', 'EXPIRED', 'TRADED', 'REJECTED', name='signalstatus')
```

- Default status: `ACTIVE`
- Indexed for fast filtering
- Server-side default ensures all new signals are active

#### 2. Repository Methods

**File**: `src/infrastructure/persistence/signals_repository.py`

Added four key methods:

1. **`mark_old_signals_as_expired(before_timestamp=None)`**
   - Marks all ACTIVE signals before timestamp as EXPIRED
   - Called before each analysis run
   - Returns count of expired signals

2. **`mark_as_traded(symbol)`**
   - Marks a signal as TRADED when order is placed
   - Only affects ACTIVE signals
   - Called in both paper and real trading flows

3. **`mark_as_rejected(symbol)`**
   - Marks a signal as REJECTED (user decision)
   - Only affects ACTIVE signals
   - Called via API endpoint

4. **`get_active_signals(limit)`**
   - Returns only ACTIVE signals
   - Used for filtering buying zone

#### 3. Integration Points

**Analysis Flow** (`src/application/services/individual_service_manager.py`):
```python
# Before adding new signals, expire old ones
signals_repo = SignalsRepository(self.db)
expired_count = signals_repo.mark_old_signals_as_expired()
logger.info(f"Marked {expired_count} old signals as EXPIRED")
```

**Paper Trading** (`src/application/services/paper_trading_service_adapter.py`):
```python
# After successful order placement
signals_repo = SignalsRepository(self.db)
if signals_repo.mark_as_traded(symbol):
    logger.info(f"Marked signal for {symbol} as TRADED")
```

**Real Trading** (`modules/kotak_neo_auto_trader/auto_trade_engine.py`):
```python
# After successful order placement
signals_repo = SignalsRepository(self.db_session)
base_symbol = broker_symbol.split("-")[0]  # Remove -EQ suffix
if signals_repo.mark_as_traded(base_symbol):
    logger.info(f"Marked signal for {base_symbol} as TRADED")
```

#### 4. API Changes

**File**: `server/app/routers/signals.py`

**Buying Zone Endpoint** - Added status filtering:
```python
@router.get("/buying-zone")
def buying_zone(
    status_filter: str = Query("active", description="Filter by status: 'active', 'expired', 'traded', 'rejected', or 'all'")
):
    # Apply status filter
    if status_filter and status_filter != "all":
        status_enum = SignalStatus(status_filter.lower())
        items = [s for s in items if s.status == status_enum]
```

**New Reject Endpoint**:
```python
@router.patch("/signals/{symbol}/reject")
def reject_signal(symbol: str):
    """Mark a signal as REJECTED"""
    repo = SignalsRepository(db)
    success = repo.mark_as_rejected(symbol)
    if not success:
        raise HTTPException(status_code=404, detail=f"No active signal found")
```

Response now includes `status` field:
```json
{
  "symbol": "TATASTEEL",
  "status": "active",  // NEW
  "rsi10": 28.5,
  ...
}
```

#### 5. Frontend Changes

**File**: `web/src/routes/dashboard/BuyingZonePage.tsx`

**Status Filter Dropdown**:
```tsx
<select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
  <option value="active">✓ Active</option>
  <option value="all">All Statuses</option>
  <option value="expired">⏰ Expired</option>
  <option value="traded">✅ Traded</option>
  <option value="rejected">❌ Rejected</option>
</select>
```

**Status Badges** - Color-coded visual indicators:
- 🟢 **Active**: Green badge with ✓ icon + Reject button
- ⚪ **Expired**: Gray badge with ⏰ icon
- 🔵 **Traded**: Blue badge with ✅ icon
- 🔴 **Rejected**: Red badge with ❌ icon

**Reject Button** (only for active signals):
```tsx
{status === 'active' && (
  <button onClick={() => rejectMutation.mutate(row.symbol)}>
    Reject
  </button>
)}
```

#### 6. Status Transition Workflow

```
┌─────────┐
│ ACTIVE  │ ← New signal created by analysis
└────┬────┘
     │
     ├─[User clicks Reject]──────→ REJECTED
     │
     ├─[Order placed]────────────→ TRADED
     │
     └─[Next analysis runs]──────→ EXPIRED
```

**Key Points**:
- Signals start as `ACTIVE`
- Only ACTIVE signals can transition to TRADED or REJECTED
- EXPIRED signals remain expired (no further transitions)
- Expiry happens "till next analysis run", not at fixed time

### Testing

**Unit Tests** (`tests/unit/test_signals_repository_status.py`):
- 18 tests covering all repository methods
- Status transition lifecycle tests
- Edge cases (can't trade expired signals, etc.)

**API Tests** (`tests/server/test_signals_status_api.py`):
- 12 tests covering API endpoints
- Status filtering tests
- Complete workflow integration tests
- Authentication tests

**All tests passing ✅**

### User Impact

**Before**:
- ❌ Stale signals visible indefinitely
- ❌ No way to know if signal was already traded
- ❌ No way to manually dismiss unwanted signals
- ❌ Confusion about which signals are current

**After**:
- ✅ Signals automatically expire at next analysis run
- ✅ Clear visual status indicators with color-coded badges
- ✅ Filter by status (active/expired/traded/rejected)
- ✅ Manual reject option for unwanted signals
- ✅ Automatic TRADED marking when orders are placed
- ✅ Default view shows only ACTIVE signals

### Migration Notes

- Database migration adds `status` column with default `ACTIVE`
- All existing signals will be marked as `ACTIVE` after migration
- No data loss - soft delete preserves all signal records
- UI seamlessly filters by default to show only active signals

---

## Bug #77: New Users Missing Default Settings - Service Start Fails (HIGH)

**Date Fixed**: November 27, 2025
**Status**: ✅ Fixed

### Description
When an admin created a new user through the admin panel, the user could not start the unified trading service. The service failed with error:
```
ValueError: User settings not found for user_id=X
```

The user had to manually navigate to the Settings page and click "Save" (even with default values) before they could start the service. This created a poor user experience and confusion.

### Steps to Reproduce
1. Admin logs in
2. Admin creates a new user via Admin Panel
3. New user logs in
4. New user navigates to Service Status page
5. New user clicks "Start" on unified service
6. **ERROR**: "User settings not found for user_id=X"
7. User navigates to Settings page
8. User clicks "Save" (no changes needed)
9. Now service starts successfully

### Root Cause
The admin user creation endpoint (`POST /api/v1/admin/users`) was not creating the default `UserSettings` record. The `UserSettings` table is required by the trading service to determine:
- Trade mode (paper vs. broker)
- Broker configuration
- Encrypted credentials

Meanwhile, the signup flow (`POST /api/v1/auth/signup`) **was** correctly creating default settings via `SettingsRepository.ensure_default()`.

This inconsistency meant:
- ✅ Users who signed up themselves: Had default settings, service worked
- ❌ Users created by admin: No default settings, service failed

### Fix Applied

**File Modified**: `server/app/routers/admin.py`

Added `SettingsRepository.ensure_default()` call to admin user creation:

```python
@router.post("/users", response_model=AdminUserResponse)
def create_user(payload: AdminUserCreate, db: Session = Depends(get_db)):
    from src.infrastructure.persistence.settings_repository import SettingsRepository

    repo = UserRepository(db)
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    role = UserRole(payload.role)
    u = repo.create_user(
        email=payload.email, password=payload.password, name=payload.name, role=role
    )

    # Create default settings for new user (required for trading service)
    SettingsRepository(db).ensure_default(u.id)

    return AdminUserResponse(
        id=u.id, email=u.email, name=u.name, role=u.role.value, is_active=u.is_active
    )
```

### Test Coverage

**File Added**: `tests/server/test_admin_user_creation_with_settings.py`

Three comprehensive tests:
1. **`test_admin_create_user_creates_default_settings`**: Verifies admin-created users have UserSettings
2. **`test_signup_also_creates_default_settings`**: Regression test for signup flow
3. **`test_service_can_find_settings_for_new_user`**: Simulates the actual service startup scenario

All tests pass ✅

### Impact
- ✅ Admin-created users can immediately start trading service
- ✅ No manual "Save Settings" step required
- ✅ Consistent behavior between signup and admin creation
- ✅ Better user experience
- ✅ Reduced support requests

### Related Components
- `UserSettings` table (required for service)
- `UserTradingConfig` table (optional, for strategy config)
- `SettingsRepository.ensure_default()` - creates default UserSettings
- `MultiUserTradingService.start_service()` - requires UserSettings

### Before/After

**Before Fix:**
```
Admin creates user → User logs in → Start service → ERROR ❌
→ User must go to Settings → Click Save → Start service → Success ✅
```

**After Fix:**
```
Admin creates user → User logs in → Start service → Success ✅
```

---
