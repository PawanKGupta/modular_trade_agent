# Re-entry Implementation - Complete Documentation

**Date**: 2025-01-22
**Status**: ✅ Complete - All edge cases covered, all tests passing

---

## Table of Contents

1. [Re-entry Flow Overview](#re-entry-flow-overview)
2. [Implementation Details](#implementation-details)
3. [Edge Cases Validation](#edge-cases-validation)
4. [Fixes Applied](#fixes-applied)
5. [Compatibility Check](#compatibility-check)
6. [Test Coverage](#test-coverage)

---

## Re-entry Flow Overview

### Purpose
Handle additional buys (re-entries) on existing positions when an oversold dip extends further, while keeping the overall position aimed at a mean reversion bounce to EMA9.

### Entry Gate (when a re-entry is allowed)
- Existing open position already tracked for the user
- Oversold continuation detected (e.g., RSI10 still depressed and price extends below prior entry)
- Position sizing rules allow adding (available capital / risk guardrails)
- Symbol not blocked by risk controls (e.g., too many recent re-entries, hard position cap, or broker constraints)
- Duplicate protection: no active pending/ongoing re-entry for the same symbol and user

### Re-Entry Signal Detection

#### When It Runs
- **Timing**: Executes at **4:05 PM** daily (same time as buy order placement)
- **Trigger**: `AutoTradeEngine.place_reentry_orders()` method
- **Frequency**: Once per trading day

#### Detection Process

**Step 1: Load Open Positions**
- **Database Table**: `positions` table
- **Repository Method**: `PositionsRepository.list(user_id)`
- **Status Filter**: `closed_at IS NULL` (position is open)
- Each position contains `entry_rsi` (RSI10 value when position was first opened)

**Step 2: Fetch Current Market Data (End-of-Day Data at 4:05 PM)**
- Construct ticker symbol (e.g., "RELIANCE.NS")
- Call `get_daily_indicators(ticker)` to fetch end-of-day indicators:
  - Current RSI10 (`rsi10`)
  - Current Price (`close`)
  - EMA200 (for uptrend filter)
  - Average Volume (for position sizing)

**Step 3: Determine Re-Entry Level**
Call `_determine_reentry_level(entry_rsi, current_rsi, position)`:

**Logic Based on Entry RSI**:
- **Entry at RSI < 30**: Next re-entry at RSI < 20 → Then at RSI < 10 → Then only reset
- **Entry at RSI < 20**: Next re-entry at RSI < 10 → Then only reset
- **Entry at RSI < 10**: Only reset (no more re-entries until reset)

**Reset Mechanism**:
- When `current_rsi > 30`: Store `last_rsi_above_30` timestamp
- When `current_rsi < 30` AND `last_rsi_above_30` exists: Reset all levels, increment cycle

**Step 4: Additional Validations (Before Placing AMO Order)**
- **Daily Cap Check**: Max 1 re-entry per symbol per day (checks `placed_at` date)
- **Uptrend Filter**: `current_price > EMA200`
- **Duplicate Check**: No active pending/ongoing buy orders
- **Balance Check**: Sufficient funds available
- **Order Type**: Always placed as **AMO (After Market Order)**

### High-Level Re-Entry Flow

1. **Detect re-entry signal (4:05 PM)**
   - System evaluates each open position at 4:05 PM
   - Uses end-of-day RSI10 and price data
   - Compares current RSI10 vs entry RSI to determine next re-entry level

2. **Validate gates (4:05 PM)**
   - Position exists and is open; risk checks pass; no duplicate pending re-entry

3. **Place re-entry order (4:05 PM)**
   - AMO order is placed via broker API
   - Order status: `PENDING` (waiting for next day market open)
   - Order tagged with `entry_type="reentry"` in database

4. **Order execution (Next day, 9:15 AM)**
   - AMO order executes automatically at market open
   - Order status changes: `PENDING` → `ONGOING` (executed)
   - Position updated in database (quantity, avg_price, reentries array)

5. **Update position on execution (9:15 AM)**
   - On fill, position quantity and weighted average price are updated
   - Re-entry audit (count, details) is appended to the position record
   - `reentry_count` incremented, `reentries` JSON array updated

### Database Tracking

**Orders table**:
- `entry_type="reentry"` to flag the order as an add-on entry
- Lifecycle fields updated on execution

**Positions table**:
- Quantity and avg_price recalculated on each executed re-entry
- `reentry_count` incremented; `reentries` JSON appended with each event:
  - `qty`: Execution quantity
  - `price`: Execution price
  - `time`: Execution timestamp
  - `placed_at`: Order placement date (for daily cap check)
  - `level`: Re-entry level (20, 10, 30)
  - `rsi`: RSI value at re-entry
  - `order_id`: Broker order ID
  - `cycle`: Cycle number (for tracking)

### Daily Re-Entry Cap: Max 1 Per Symbol Per Day

**Fix: Placement Date vs Execution Date**

**Previous Issue**: Daily cap check used execution date (`time` field), which caused incorrect blocking:
- Day 1, 4:05 PM: Place AMO order → `placed_at = Day 1`
- Day 2, 9:15 AM: Order executes → `time = Day 2` (execution date)
- Day 2, 4:05 PM: Check daily cap → Found re-entry with `time = Day 2` → Count = 1 → **Incorrectly blocked** ❌

**Fix**: Daily cap check now uses placement date (`placed_at` field):
- Day 1, 4:05 PM: Place AMO order → `placed_at = Day 1`
- Day 2, 9:15 AM: Order executes → `placed_at = Day 1`, `time = Day 2`
- Day 2, 4:05 PM: Check daily cap → Found re-entry with `placed_at = Day 1` → Count = 0 for Day 2 → **Correctly allows new order** ✅

**Implementation**:
- When re-entry executes, `placed_at` date is extracted from order's `placed_at` field and stored in `reentries` array
- `reentries_today()` checks `placed_at` date first, falls back to `time` date for backward compatibility

---

## Implementation Details

### Key Features Implemented

1. ✅ **Cycle tracking** with `current_cycle`, `last_rsi_above_30`, `last_rsi_value`
2. ✅ **Reset detection on startup** via `last_rsi_above_30` timestamp
3. ✅ **Level-based blocking** by cycle number (not just level)
4. ✅ **`levels_taken` updated** from executed re-entries in current cycle
5. ✅ **Reset triggers appropriate level** based on current RSI (10 > 20 > 30)
6. ✅ **Level skipping allowed** (priority order: 10 > 20 > 30)
7. ✅ **Backtrack prevention** (intermediate levels marked as taken)
8. ✅ **`allow_reset` applies to all levels** (30, 20, 10)
9. ✅ **Partial execution** handled correctly
10. ✅ **AMO placement date** used for daily cap (not execution date)

### Data Format Evolution

**Old Format** (still supported):
```json
[
  {"qty": 10, "level": 20, "rsi": 18.5, "price": 9.50, "time": "...", "order_id": "..."},
  {"qty": 5, "level": 10, "rsi": 8.2, "price": 9.20, "time": "...", "order_id": "..."}
]
```

**New Format** (with cycle metadata):
```json
{
  "_cycle_metadata": {
    "current_cycle": 1,
    "last_rsi_above_30": "2025-01-15T10:30:00+05:30",
    "last_rsi_value": 32.5
  },
  "reentries": [
    {"qty": 10, "level": 20, "rsi": 18.5, "price": 9.50, "time": "...", "order_id": "...", "cycle": 0, "placed_at": "..."},
    {"qty": 5, "level": 10, "rsi": 8.2, "price": 9.20, "time": "...", "order_id": "...", "cycle": 1, "placed_at": "..."}
  ]
}
```

**Status**: ✅ **Both formats handled correctly**

---

## Edge Cases Validation

### Coverage Summary

| Category | Total Cases | Covered | Coverage |
|----------|-------------|---------|----------|
| Reset Detection & Cycles | 4 | 4 | 100% |
| Level Progression & Skipping | 5 | 5 | 100% |
| Initial Entry Blocking | 4 | 4 | 100% |
| Reset Behavior | 5 | 5 | 100% |
| Cycle-Based Blocking | 4 | 4 | 100% |
| levels_taken Updates | 4 | 4 | 100% |
| Order Placement & Execution | 4 | 4 | 100% |
| Service Restart Scenarios | 4 | 4 | 100% |
| Complex Scenarios | 8 | 8 | 100% |
| **TOTAL** | **42** | **42** | **100%** |

### Key Edge Cases

#### Category 1: Reset Detection & Cycles
- ✅ Service restart between RSI > 30 and < 30
- ✅ Multiple reset cycles
- ✅ Reset in same day
- ✅ Multiple resets, same cycle

#### Category 2: Level Progression & Skipping
- ✅ Normal sequential progression (30 → 20 → 10)
- ✅ Skip level 20 → level 10
- ✅ Backtrack prevention
- ✅ Skip level 30 → level 20
- ✅ Skip level 30 → level 10

#### Category 3: Initial Entry Blocking
- ✅ Initial entry at RSI < 30 blocks level 30
- ✅ Initial entry at RSI < 20 blocks level 20
- ✅ Initial entry at RSI < 10 blocks level 10
- ✅ Reset allows re-entry at initial level

#### Category 4: Reset Behavior
- ✅ Reset triggers level 30
- ✅ Reset triggers level 20
- ✅ Reset triggers level 10
- ✅ Reset at RSI between 20-30
- ✅ Reset at RSI between 10-20

#### Category 5: Cycle-Based Blocking
- ✅ Same level in same cycle
- ✅ Same level in different cycle
- ✅ Old re-entries without cycle
- ✅ Multiple cycles, same level

#### Category 6: levels_taken Updates
- ✅ levels_taken from executed re-entries
- ✅ Intermediate levels marked when skip
- ✅ levels_taken persists across days
- ✅ levels_taken reset on new cycle

#### Category 7: Order Placement & Execution
- ✅ Partial execution
- ✅ AMO placement vs execution date
- ✅ Order cancelled/failed
- ✅ Retry failed order

#### Category 8: Service Restart Scenarios
- ✅ Service restart after RSI > 30
- ✅ Service restart multiple times
- ✅ Fresh start, duplicate check
- ✅ Service starts at 9:15 AM, places and executes

#### Category 9: Complex Scenarios
- ✅ Complex multi-cycle pattern
- ✅ RSI oscillating at 30
- ✅ Skip then reset
- ✅ Entry < 20, then reset
- ✅ Entry < 10
- ✅ RSI = 30 (no reset)
- ✅ RSI > 30 (with reset)
- ✅ Skip level, backtrack attempt

---

## Fixes Applied

| Fix | Description | Location | Status |
|-----|-------------|----------|--------|
| **Fix 1** | Update `levels_taken` from executed re-entries | Line 5095-5137 | ✅ Implemented |
| **Fix 2** | Reset triggers appropriate level (10 > 20 > 30) | Line 5191-5208 | ✅ Implemented |
| **Fix 3** | Allow skipping levels (priority order) | Line 5214-5233 | ✅ Implemented |
| **Fix 4** | Backtrack prevention (mark intermediate levels) | Line 5139-5158 | ✅ Implemented |
| **Fix 5** | `allow_reset` applies to all levels | Line 2208 | ✅ Implemented |
| **Fix 6** | Cycle tracking with metadata | Line 2078-2165 | ✅ Implemented |
| **Fix 7** | Reset detection on startup | Line 5160-5208 | ✅ Implemented |
| **Fix 8** | Partial execution handling | unified_order_monitor.py | ✅ Implemented |
| **Fix 9** | AMO placement date for daily cap | unified_order_monitor.py line 885-911 | ✅ Implemented |
| **Fix 10** | `reentries_today()` handles both formats | Line 2017-2026 | ✅ Implemented |

---

## Compatibility Check

### Summary

✅ **All services are compatible** - The implementation maintains backward compatibility and doesn't break any existing functionality.

### Service-by-Service Compatibility

| Component | Compatibility | Notes |
|-----------|---------------|-------|
| **Database Schema** | ✅ Compatible | No schema changes, JSON field accepts both formats |
| **AutoTradeEngine** | ✅ Compatible | Handles both formats, backward compatible |
| **UnifiedOrderMonitor** | ✅ Compatible | Preserves metadata, handles both formats |
| **PaperTradingAdapter** | ✅ Compatible | Separate implementation, no impact |
| **SellOrderManager** | ✅ Compatible | Doesn't access reentries field |
| **PositionsRepository** | ✅ Compatible | Stores as-is, no validation |
| **API Endpoints** | ✅ Compatible | Don't expose reentries structure |
| **Existing Tests** | ✅ Compatible | Use old format, still work |
| **New Tests** | ✅ Compatible | Test new functionality |
| **Migration** | ✅ Not Required | Automatic, no data loss |

### Backward Compatibility Mechanisms

**Reading reentries Field**:
```python
if isinstance(position.reentries, dict):
    # New format: extract reentries array
    reentries = position.reentries.get("reentries", [])
elif isinstance(position.reentries, list):
    # Old format: directly a list
    reentries = position.reentries
else:
    # None or invalid
    reentries = []
```

**Writing reentries Field**:
```python
if isinstance(existing_pos.reentries, dict) and "_cycle_metadata" in existing_pos.reentries:
    # Preserve existing cycle metadata
    reentries_to_store = {
        "_cycle_metadata": existing_pos.reentries["_cycle_metadata"],
        "reentries": reentries_array
    }
else:
    # Old format or no metadata - store as list (backward compatible)
    reentries_to_store = reentries_array
```

**Status**: ✅ **Both formats handled correctly**

---

## Test Coverage

### Test Suite

**File**: `tests/unit/kotak/test_reentry_all_edge_cases.py`

**Total Tests**: 44 tests (42 edge cases + 2 backward compatibility)

### Test Results

✅ **All 44 tests passing**

### Test Categories

1. **Reset Detection & Cycles** - 4 tests
2. **Level Progression & Skipping** - 5 tests
3. **Initial Entry Blocking** - 4 tests
4. **Reset Behavior** - 5 tests
5. **Cycle-Based Blocking** - 4 tests
6. **levels_taken Updates** - 4 tests
7. **Order Placement & Execution** - 4 tests
8. **Service Restart Scenarios** - 4 tests
9. **Complex Scenarios** - 8 tests
10. **Backward Compatibility** - 2 tests

### Running Tests

```bash
# Run all edge case tests
pytest tests/unit/kotak/test_reentry_all_edge_cases.py -v

# Run specific category
pytest tests/unit/kotak/test_reentry_all_edge_cases.py::TestResetDetectionAndCycles -v
```

---

## Conclusion

✅ **ALL EDGE CASES COVERED**

**Summary**:
- ✅ **42 edge cases** identified and validated
- ✅ **100% coverage** - All edge cases are handled correctly
- ✅ **10 fixes implemented** - All critical issues resolved
- ✅ **No gaps identified** - Implementation is complete
- ✅ **All services compatible** - No breaking changes
- ✅ **All tests passing** - 44/44 tests pass

**Status**: ✅ **Implementation is robust and handles all edge cases correctly**

---

## Key Implementation Files

- `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Main re-entry logic
- `modules/kotak_neo_auto_trader/unified_order_monitor.py` - Order execution tracking
- `tests/unit/kotak/test_reentry_all_edge_cases.py` - Comprehensive test suite

---

**Last Updated**: 2025-01-22
