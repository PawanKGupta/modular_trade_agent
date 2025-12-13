# Signal Expiry Logic Fix - Planning Document

**Date**: 2025-12-13  
**Status**: Completed  
**Priority**: High

---

## Problem Statement

### Current Issues

1. **Incorrect Time Window**: Signals expire too late
   - Current: Signal from Monday expires on Wednesday at 3:30 PM
   - Expected: Signal from Monday expires on Tuesday at 3:30 PM (next trading day)

2. **Database Inconsistency**: Time-based expiry only in UI
   - Current: Database status doesn't reflect time-based expiry
   - Expected: Database status should be updated when time-based expiry occurs

3. **Missing Weekend/Holiday Handling**: Current logic doesn't properly handle weekends and holidays

---

## Requirements

### Rule
**A signal is valid until the end of the next trading day's market hours (3:30 PM IST), then expires.**

### Trading Day Definition
- **Trading days**: Monday-Friday (excluding weekends)
- **Non-trading days**: Saturday, Sunday, and market holidays
- **Market hours**: 9:15 AM - 3:30 PM IST
- **Market close**: 3:30 PM IST

### Expiry Logic
1. Signal created on day X
2. Find next trading day (day X+1, skipping weekends/holidays)
3. Signal expires at: next trading day at 3:30 PM IST
4. Database status should be updated to EXPIRED

---

## Implementation Plan

### Phase 1: Core Logic Implementation

#### 1.1 Create/Update Trading Day Utility Function
**File**: `src/infrastructure/persistence/signals_repository.py` or new utility

**Function**: `get_signal_expiry_time(signal_timestamp: datetime) -> datetime`
- Calculate next trading day from signal creation date
- Skip weekends (Saturday, Sunday)
- Skip holidays (TODO: implement holiday checking)
- Return: next trading day at 3:30 PM IST

**Dependencies**:
- Use existing `get_next_trading_day_close()` from `trading_day_utils.py` as reference
- May need to create new function or extend existing one

#### 1.2 Update Time-Based Expiry Check
**File**: `src/infrastructure/persistence/signals_repository.py`

**Function**: `_is_signal_expired_by_market_close()` → Update logic
- Current: Checks if signal is from yesterday and past today's 3:30 PM
- New: Check if current time >= signal's expiry time (next trading day 3:30 PM)

#### 1.3 Add Database Status Update Function
**File**: `src/infrastructure/persistence/signals_repository.py`

**Function**: `mark_time_expired_signals() -> int`
- Find all ACTIVE signals where current time >= expiry time
- Update status to EXPIRED
- Return count of expired signals
- Should be called periodically or on-demand

---

### Phase 2: Integration Points

#### 2.1 Scheduled Task (Recommended)
**File**: `src/application/services/individual_service_manager.py` or new service

**Task**: Periodic expiry check
- Run every hour or every 30 minutes
- Call `mark_time_expired_signals()`
- Log results

**Alternative**: Check on-demand when signals are queried

#### 2.2 Update Signal Queries
**File**: `src/infrastructure/persistence/signals_repository.py`

**Functions**: `get_active_signals()`, `get_user_signal_status()`
- Before returning signals, check and update time-expired signals
- Ensure database is consistent before returning results

#### 2.3 Update UI Logic
**File**: `web/src/routes/dashboard/BuyingZonePage.tsx`

**Update**: Time-based expiry check
- Use same logic as backend (next trading day 3:30 PM)
- Should match database status (database is source of truth)

---

### Phase 3: Holiday Handling

#### 3.1 Holiday Calendar Implementation
**Options**:
1. **Static list**: Store NSE/BSE holidays in database or config file
2. **API integration**: Use NSE/BSE holiday API (if available)
3. **Library**: Use Python holiday library (e.g., `holidays` package)

**Recommendation**: Start with static list, add API later if needed

**File**: `src/infrastructure/db/models.py` or `src/application/services/holiday_service.py`

**Structure**:
```python
class MarketHoliday(Base):
    date: date
    name: str
    exchange: str  # "NSE" or "BSE"
```

#### 3.2 Update Trading Day Functions
**Files**: 
- `modules/kotak_neo_auto_trader/utils/trading_day_utils.py`
- `src/infrastructure/persistence/signals_repository.py`

**Update**: `get_next_trading_day_close()` and signal expiry functions
- Check holiday list when finding next trading day
- Skip holidays in addition to weekends

---

## Test Coverage Plan

### Unit Tests

#### Test File: `tests/unit/infrastructure/test_signal_expiry_logic.py`

**Test Cases**:

1. **Basic Expiry - Next Day**
   - Signal Monday 4:00 PM → Expires Tuesday 3:30 PM
   - Signal Tuesday 4:00 PM → Expires Wednesday 3:30 PM

2. **Weekend Handling**
   - Signal Friday 4:00 PM → Expires Monday 3:30 PM (skip weekend)
   - Signal Thursday 4:00 PM → Expires Friday 3:30 PM (normal)

3. **Holiday Handling**
   - Signal Wednesday (before holiday) → Expires Friday 3:30 PM (skip holiday)
   - Signal Friday (before long weekend) → Expires Tuesday 3:30 PM (skip weekend + holiday)

4. **Edge Cases**
   - Signal created on Saturday → Expires Monday 3:30 PM
   - Signal created on Sunday → Expires Monday 3:30 PM
   - Signal created on holiday → Expires next trading day 3:30 PM
   - Multiple consecutive holidays → Skip all holidays

5. **Time Boundary Tests**
   - Signal expires exactly at 3:30 PM → Should be expired
   - Signal expires at 3:29 PM → Should be active
   - Signal expires at 3:31 PM → Should be expired

6. **Database Status Update**
   - ACTIVE signal past expiry time → Status updated to EXPIRED
   - Already EXPIRED signal → No change
   - TRADED signal → Not affected by time expiry
   - REJECTED signal → Not affected by time expiry

7. **Bulk Expiry**
   - Multiple signals with different expiry times → Only expired ones updated
   - Signals from different days → All expired ones updated correctly

### Integration Tests

#### Test File: `tests/integration/test_signal_expiry_integration.py`

**Test Cases**:

1. **End-to-End Expiry Flow**
   - Create signal → Wait for expiry time → Check database status → Verify UI display

2. **Scheduled Task Integration**
   - Run scheduled expiry check → Verify signals updated in database

3. **Signal Query Integration**
   - Query active signals → Verify expired signals not returned
   - Query all signals → Verify expired signals have correct status

---

## Edge Cases to Handle

### 1. Weekend Signals
- **Scenario**: Signal created on Saturday/Sunday
- **Expected**: Expires on next trading day (Monday) at 3:30 PM
- **Test**: Verify weekend skip logic

### 2. Holiday Signals
- **Scenario**: Signal created on market holiday
- **Expected**: Expires on next trading day at 3:30 PM
- **Test**: Verify holiday skip logic

### 3. Multiple Consecutive Holidays
- **Scenario**: Signal before multiple consecutive holidays
- **Expected**: Skip all holidays, expire on first trading day after holidays
- **Test**: Verify multiple holiday skip

### 4. Year-End/Year-Beginning
- **Scenario**: Signal created on Dec 31, next trading day is Jan 2
- **Expected**: Expires on Jan 2 at 3:30 PM
- **Test**: Verify year boundary handling

### 5. Timezone Edge Cases
- **Scenario**: Signal created in different timezone
- **Expected**: All times converted to IST before comparison
- **Test**: Verify timezone conversion

### 6. Database Consistency
- **Scenario**: Signal expires while being queried
- **Expected**: Database status updated atomically
- **Test**: Verify no race conditions

### 7. Concurrent Expiry Checks
- **Scenario**: Multiple processes checking expiry simultaneously
- **Expected**: Only one process updates status, no duplicates
- **Test**: Verify thread-safety

### 8. Signal Created During Market Hours
- **Scenario**: Signal created at 2:00 PM on Monday
- **Expected**: Expires Tuesday 3:30 PM (not Monday 3:30 PM)
- **Test**: Verify expiry is always next trading day, not same day

### 9. Signal Created After Market Close
- **Scenario**: Signal created at 4:00 PM on Monday
- **Expected**: Expires Tuesday 3:30 PM
- **Test**: Verify after-hours signals handled correctly

### 10. Leap Year / Month End
- **Scenario**: Signal created on Feb 28, next trading day is Mar 1
- **Expected**: Expires on Mar 1 at 3:30 PM
- **Test**: Verify date arithmetic handles month boundaries

---

## Implementation Steps

### Step 1: Create Utility Function
- [ ] Create `get_signal_expiry_time()` function
- [ ] Handle weekends
- [ ] Add TODO for holidays (implement later)
- [ ] Add unit tests

### Step 2: Update Expiry Check Logic
- [ ] Update `_is_signal_expired_by_market_close()` function
- [ ] Use new expiry time calculation
- [ ] Update unit tests

### Step 3: Add Database Update Function
- [ ] Create `mark_time_expired_signals()` function
- [ ] Update ACTIVE signals to EXPIRED based on time
- [ ] Add unit tests

### Step 4: Integration
- [ ] Add scheduled task or on-demand check
- [ ] Update signal query functions
- [ ] Add integration tests

### Step 5: Update UI
- [ ] Update frontend expiry logic to match backend
- [ ] Ensure UI reflects database status
- [ ] Add frontend tests if needed

### Step 6: Holiday Handling ✅
- [x] Create holiday calendar structure (`src/infrastructure/utils/holiday_calendar.py`)
- [x] Implement holiday checking (NSE holidays for 2025)
- [x] Update trading day functions
- [x] Add holiday tests (14 test cases)

---

## Files to Modify

### Backend
1. `src/infrastructure/persistence/signals_repository.py`
   - Update `_is_signal_expired_by_market_close()`
   - Add `get_signal_expiry_time()`
   - Add `mark_time_expired_signals()`

2. `modules/kotak_neo_auto_trader/utils/trading_day_utils.py`
   - May need to extend or create new function

3. `src/application/services/individual_service_manager.py` (optional)
   - Add scheduled expiry check

### Frontend
4. `web/src/routes/dashboard/BuyingZonePage.tsx`
   - Update time-based expiry logic

### Tests
5. `tests/unit/infrastructure/test_signal_expiry_logic.py` (new)
   - All unit tests

6. `tests/integration/test_signal_expiry_integration.py` (new)
   - Integration tests

---

## Success Criteria

1. ✅ Signals expire at next trading day's 3:30 PM IST
2. ✅ Weekends are properly skipped
3. ✅ Database status reflects time-based expiry
4. ✅ UI and database are consistent
5. ✅ All edge cases handled
6. ✅ Comprehensive test coverage (90%+)
7. ✅ No performance degradation
8. ✅ Holiday handling ready (even if not fully implemented)

---

## Risk Assessment

### Low Risk
- Logic changes are straightforward
- Existing trading day utilities can be reused
- Tests will catch regressions

### Medium Risk
- Holiday calendar implementation (can start with TODO)
- Performance impact of periodic checks (can optimize later)

### Mitigation
- Implement in phases
- Start with weekends, add holidays later
- Use existing utilities where possible
- Comprehensive testing before deployment

---

## Timeline Estimate

- **Phase 1**: Core logic (2-3 hours)
- **Phase 2**: Integration (1-2 hours)
- **Phase 3**: Testing (2-3 hours)
- **Phase 4**: Holiday handling (1-2 hours, future)
- **Total**: ~6-10 hours

---

## Notes

- Holiday checking is marked as TODO in existing code - can implement later
- Start with weekend handling, add holidays incrementally
- Ensure backward compatibility with existing signals
- Consider performance: batch updates vs individual checks

