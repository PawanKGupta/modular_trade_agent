# Bug Fixes - January 2025

## Analysis Service and Signal Persistence Improvements

### Date: 2025-01-19

### Summary
Fixed critical bugs in the analysis service signal persistence logic, including boolean conversion, verdict filtering, time-based update blocking, and field normalization from nested structures.

---

## Bug Fixes

### 1. Boolean Conversion from Strings
**Issue**: Analysis results contained string representations of booleans (`"True"`, `"False"`) which caused `TypeError: Not a boolean value` during signal persistence.

**Fix**:
- Added `_convert_boolean()` method in `AnalysisDeduplicationService` to handle string boolean conversion
- Applied conversion to all boolean fields: `clean_chart`, `fundamental_ok`, `vol_ok`, `vol_strong`, `is_above_ema200`, `decline_rate_slowing`
- Handles both capitalized (`"True"`, `"False"`) and lowercase (`"true"`, `"false"`) strings

**Files Modified**:
- `src/application/services/analysis_deduplication_service.py`
- `src/application/services/individual_service_manager.py`

---

### 2. Verdict Filtering Priority
**Issue**: Signal persistence was not correctly prioritizing `final_verdict` (post-backtest) over `verdict` (pre-backtest), and was persisting all stocks regardless of verdict.

**Fix**:
- Updated `_persist_analysis_results()` to filter stocks by verdict: only `"buy"` and `"strong_buy"` are persisted
- Verdict priority: `final_verdict` > `verdict` > `ml_verdict`
- Stocks with verdicts `"watch"`, `"avoid"`, or other values are skipped

**Files Modified**:
- `src/application/services/individual_service_manager.py`

---

### 3. Time-Based Update Blocking
**Issue**: Analysis results were being blocked from persistence at incorrect times, preventing updates when they should be allowed.

**Fix**:
- Updated `should_update_signals()` logic in `AnalysisDeduplicationService`:
  - **Weekdays**: Block updates between 9AM-4PM (during trading hours), allow before 9AM or after 4PM
  - **Weekends/Holidays**: Allow before 9AM (part of previous trading day), block after 9AM
- Analysis can now run anytime, but persistence is blocked during trading hours (9AM-4PM) on weekdays

**Files Modified**:
- `src/application/services/analysis_deduplication_service.py`
- `src/application/services/individual_service_manager.py`

---

### 4. Field Normalization from Nested Structures
**Issue**: Many fields (e.g., `ema9`, `ema200`, `distance_to_ema9`, `confidence`, `volume_ratio`, `clean_chart`, `monthly_support_dist`, `backtest_score`) were null in the Signals table because they were stored in nested structures within analysis results.

**Fix**:
- Enhanced `_normalize_analysis_row()` to extract fields from nested structures:
  - `volume_ratio` from `volume_analysis.ratio`
  - `clean_chart` from `chart_quality.status` or `chart_quality.passed`
  - `monthly_support_dist` from `timeframe_analysis.daily_analysis.support_analysis.distance_pct`
  - `backtest_score` from `backtest.score` or top-level `backtest_score`
- Added direct field mappings for `ema9`, `ema200`, `distance_to_ema9`, `confidence` which are now included in analysis results

**Files Modified**:
- `src/application/services/individual_service_manager.py`
- `services/analysis_service.py`

---

### 5. Fundamental Assessment Conversion
**Issue**: `fundamental_assessment` field was stored as a dictionary but the database column expects a string (max 64 chars).

**Fix**:
- Added `_convert_fundamental_assessment()` method to extract `fundamental_reason` from dict or convert to JSON string
- Truncates to 64 characters if needed

**Files Modified**:
- `src/application/services/analysis_deduplication_service.py`

---

## Code Cleanup

### Removed Unused Code
- Removed verbose debug logging from `_persist_analysis_results()`
- Removed unused `verdict_stats` variable
- Cleaned up redundant comments
- Consolidated logging imports
- Removed ML model status logging (temporarily disabled code)

**Files Modified**:
- `src/application/services/individual_service_manager.py`
- `src/application/services/analysis_deduplication_service.py`
- `services/analysis_service.py`

---

## Testing

### New Test Coverage
Added comprehensive unit tests for all bug fixes:

1. **Analysis Deduplication Service Tests** (`tests/unit/application/test_analysis_deduplication_service.py`):
   - Time-based update logic (weekday/weekend, before/after 9AM, during trading hours)
   - Boolean conversion (None, bool, string variants)
   - Fundamental assessment conversion
   - Signal creation and update
   - Deduplication logic

2. **Individual Service Manager Analysis Tests** (`tests/unit/application/test_individual_service_manager_analysis.py`):
   - Verdict filtering and priority
   - Field normalization from nested structures
   - Boolean conversion in normalization
   - Time-based persistence blocking
   - Missing field handling

**Total Test Coverage**: 41 new tests covering all bug fixes

---

## Database Schema Changes

### New Fields Added to Signals Table
The following fields were added to store comprehensive analysis results:
- `final_verdict`, `rule_verdict`, `verdict_source`, `backtest_confidence`
- `vol_strong`, `is_above_ema200`
- `dip_depth_from_20d_high_pct`, `consecutive_red_days`, `dip_speed_pct_per_day`
- `decline_rate_slowing`, `volume_green_vs_red_ratio`, `support_hold_count`
- `liquidity_recommendation`, `trading_params`
- `ema9`, `ema200`, `distance_to_ema9`, `confidence`

**Migration**: `alembic/versions/2a037cee1fc2_add_missing_fields_to_signals.py`

---

## Impact

### Before Fixes
- Many signal fields were null in database
- Boolean conversion errors during persistence
- All stocks persisted regardless of verdict
- Updates blocked at incorrect times
- Missing data from nested analysis structures

### After Fixes
- All analysis fields properly extracted and stored
- Boolean values correctly converted
- Only buy/strong_buy stocks persisted
- Time-based blocking works correctly
- Complete data available in Signals table for Buying Zone page

---

---

## Execution Tracking Separation Fix

### Date: 2025-01-20

### Summary
Fixed duplicate execution tracking issue where individual services were writing to both `service_task_execution` (unified service) and `individual_service_task_execution` tables, causing conflicts and confusion.

### Issue
When individual services executed tasks, they created records in both:
1. `individual_service_task_execution` (intended)
2. `service_task_execution` (unintended - for unified service only)

This happened because individual services call `TradingService` methods which use the `execute_task` wrapper that always writes to `service_task_execution`.

### Fix
1. **Added `track_execution` parameter** to `execute_task()` wrapper (defaults to `True` for backward compatibility)
   - When `False`, skips writing to `service_task_execution` table
   - Logging still occurs, only database tracking is skipped

2. **Added `skip_execution_tracking` parameter** to `TradingService.__init__()`
   - When `True`, all `execute_task` calls skip unified service tracking
   - Individual services pass this flag when creating `TradingService` instances

3. **Updated all `execute_task` calls** in `TradingService` to respect the flag
   - Passes `track_execution=not self.skip_execution_tracking`

4. **Updated `IndividualServiceManager`** to pass `skip_execution_tracking=True`
   - Individual services now only write to `individual_service_task_execution`

### Files Modified
- `src/application/services/task_execution_wrapper.py`
- `src/application/services/individual_service_manager.py`
- `modules/kotak_neo_auto_trader/run_trading_service.py`
- `scripts/run_individual_service.py` (added execution tracking for scheduled runs)

### Testing
- Added tests for `track_execution=False` parameter
- Verified no duplicate records created
- Verified unified service still tracks correctly
- Added tests for `formatDuration()` utility function

---

## Duration Formatting Improvement

### Date: 2025-01-20

### Summary
Improved duration display in UI to show minutes and hours instead of always showing seconds.

### Fix
- Added `formatDuration()` function in `web/src/utils/time.ts`
  - < 60 seconds: "X.Xs" (e.g., "32.5s")
  - < 3600 seconds: "X.Xm" (e.g., "1.2m", "59.5m")
  - >= 3600 seconds: "X.Xh" (e.g., "1.0h", "2.5h")
- Updated `IndividualServiceControls` to use `formatDuration()` for execution duration display

### Files Modified
- `web/src/utils/time.ts`
- `web/src/routes/dashboard/IndividualServiceControls.tsx`
- `web/src/utils/__tests__/time.test.ts` (added tests)

---

## Schedule Type Validation

### Date: 2025-01-20

### Summary
Added validation to prevent invalid combinations of schedule type and execution type.

### Fix
- Added validation in `ScheduleManager.validate_schedule()`:
  - If `schedule_type == "once"`, then `is_hourly` and `is_continuous` must be `False`
  - If `schedule_type == "once"`, then `end_time` must be `None`
- Updated UI to disable execution dropdown when schedule type is "once"
- Added tests for validation rules

### Files Modified
- `src/application/services/schedule_manager.py`
- `server/app/routers/admin.py`
- `web/src/routes/dashboard/ServiceSchedulePage.tsx`
- `tests/unit/application/test_schedule_manager.py`

---

## Related Documentation
- [Individual Service Management User Guide](../features/INDIVIDUAL_SERVICE_MANAGEMENT_USER_GUIDE.md)
- [Individual Service Management Implementation Plan](../features/INDIVIDUAL_SERVICE_MANAGEMENT_IMPLEMENTATION_PLAN.md)
