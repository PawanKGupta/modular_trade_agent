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

---

## Paper Trading Support for Individual Services

### Date: 2025-01-20

### Summary
Implemented full paper trading support for individual services, allowing users to run all trading tasks (buy_orders, sell_monitor, position_monitor, etc.) in paper trading mode without requiring broker credentials.

### Implementation
1. **Created `PaperTradingServiceAdapter`** (`src/application/services/paper_trading_service_adapter.py`):
   - Provides TradingService-compatible interface for paper trading
   - Uses `PaperTradingBrokerAdapter` instead of real broker authentication
   - Implements all task methods: `run_buy_orders()`, `run_premarket_retry()`, `run_sell_monitor()`, `run_position_monitor()`, `run_eod_cleanup()`
   - User-specific storage paths: `paper_trading/user_{user_id}/`
   - Sets `max_position_size` from `strategy_config.user_capital` during initialization

2. **Created `PaperTradingEngineAdapter`**:
   - Provides AutoTradeEngine-compatible interface using paper trading broker
   - **Loads recommendations from database (Signals table)** instead of CSV files
   - Filters for buy/strong_buy verdicts (prioritizes `final_verdict` > `verdict` > `ml_verdict`)
   - Extracts `execution_capital` from `liquidity_recommendation` or `trading_params`
   - Places orders using paper trading broker
   - Handles portfolio limits, duplicate detection, and balance checks
   - Respects `max_position_size` limit from trading configuration

3. **Updated `IndividualServiceManager`**:
   - Detects paper trading mode (`trade_mode.value == "paper"`)
   - Uses `PaperTradingServiceAdapter` instead of `TradingService` for paper mode
   - No broker credentials required for paper trading mode

4. **Updated `TradingService`**:
   - Made `broker_creds` parameter optional (`dict | None = None`)
   - Supports paper trading mode initialization

### Features
- ✅ All trading tasks work in paper trading mode
- ✅ No broker credentials required
- ✅ User-specific paper trading storage
- ✅ Portfolio limits and duplicate detection
- ✅ Balance validation and order placement
- ✅ EOD reports and cleanup
- ✅ **Loads recommendations from database (Signals table)**
- ✅ **Uses `strategy_config.user_capital` for max position size**
- ✅ **Respects trading configuration for position sizing**

### Improvements (2025-01-21)
1. **Database-based Recommendations**:
   - Changed from loading CSV files to querying `Signals` table
   - Filters for today's signals (or recent if none today)
   - Only includes buy/strong_buy verdicts
   - Extracts execution_capital from signal metadata

2. **Trading Configuration Integration**:
   - `max_position_size` in `PaperTradingConfig` is set from `strategy_config.user_capital`
   - Orders respect user's configured capital per trade
   - Quantity calculation uses `user_capital` instead of hardcoded defaults

3. **Better Error Handling**:
   - Improved logging for recommendation loading
   - Better error messages for order rejections
   - Summary returned from `run_buy_orders()` for execution details

### Files Modified
- `src/application/services/paper_trading_service_adapter.py`
- `src/application/services/individual_service_manager.py`
- `modules/kotak_neo_auto_trader/run_trading_service.py`
- `tests/unit/application/test_paper_trading_service_adapter.py`

### Testing
- Added comprehensive tests for paper trading adapter
- Tests cover initialization, buy orders, duplicate detection, portfolio limits
- Tests verify recommendation loading from database
- Tests verify max_position_size from strategy_config
- Tests verify quantity adjustment when exceeding limits

---

## Buy Order Service Optimizations

### Date: 2025-01-21

### Summary
Implemented several performance and reliability optimizations for the buy order service, including unified recommendation source, per-ticker telemetry, batching of API calls, and fail-fast error handling.

---

### 1. Recommendation Source Unification

**Issue**: Unified service was reading recommendations from CSV files, while individual/paper services were reading from the `Signals` table, causing inconsistency and file I/O overhead.

**Fix**:
- Modified `AutoTradeEngine.load_latest_recommendations()` to prioritize database (`Signals` table) when a database session and user_id are available
- Falls back to CSV files for backward compatibility (standalone execution, legacy workflows)
- Unified service now uses the same authoritative source as individual services
- Eliminates file I/O and keeps all services in sync

**Priority Order**:
1. Custom CSV path (if set via `_custom_csv_path` - for backward compatibility)
2. **Database (`Signals` table)** - when `db` and `user_id` available
3. CSV files (fallback)

**Files Modified**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Benefits**:
- Single source of truth for recommendations
- No file I/O overhead for unified service
- Late updates/filters possible without regenerating CSVs
- Consistent behavior across all service types

---

### 2. Per-Ticker Telemetry

**Issue**: Only summary statistics were logged, making it difficult to debug individual order attempts or track per-ticker performance.

**Fix**:
- Added `ticker_attempts` list to `place_new_entries()` summary
- Each attempt records:
  - `ticker`: Original ticker symbol
  - `symbol`: Broker-specific symbol
  - `verdict`: Recommendation verdict (buy/strong_buy)
  - `status`: Attempt status (placed, skipped, failed)
  - `reason`: Skip/fail reason (e.g., "already_in_holdings", "insufficient_balance", "missing_indicators")
  - `qty`: Calculated quantity
  - `execution_capital`: Capital allocated
  - `price`: Order price
  - `order_id`: Broker order ID (if placed)

**Files Modified**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Benefits**:
- Detailed audit trail for each ticker
- Easier debugging of order placement issues
- KPI tracking per ticker
- UI can display detailed results

---

### 3. Batching Indicators and Portfolio Snapshots

**Issue**: Each recommendation was fetching portfolio and indicators individually, causing O(n) API calls and high latency.

**Fix**:
- **Portfolio Caching**: Fetch portfolio snapshot once at start of `place_new_entries()`
  - Cache holdings count and symbols set
  - Reuse for all recommendations in the run
- **Indicator Pre-fetching**: Pre-fetch daily indicators for all recommendation tickers
  - Batch fetch at start of run
  - Cache results for reuse
  - Reduces API calls from O(n) to O(1)

**Files Modified**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Benefits**:
- Dramatically reduced API calls (from O(n) to O(1))
- Lower latency per recommendation
- Reduced broker API rate limit risk
- Faster overall execution

---

### 4. Paper Trading Price Batching

**Issue**: Paper trading was fetching prices ticker-by-ticker through YFinance, causing high latency.

**Fix**:
- Pre-fetch prices for all recommendation tickers at start of `place_new_entries()`
- Use `self.broker.price_provider.get_prices()` for batch operation
- Cache results to warm price provider cache
- Fallback to individual fetches if batch method unavailable

**Files Modified**:
- `src/application/services/paper_trading_service_adapter.py`

**Benefits**:
- Reduced latency for paper trading orders
- Warms price cache for faster subsequent lookups
- Better performance for large recommendation sets

---

### 5. Fail-Fast on Broker/API Errors

**Issue**: Broker/API errors (e.g., rate limiting, authentication failures) were being retried, potentially causing account locks or duplicate orders.

**Fix**:
- Introduced `OrderPlacementError` exception for broker/API errors
- Modified `AutoTradeEngine.place_new_entries()` to catch `OrderPlacementError` and re-raise immediately
- Modified `TradingService.run_buy_orders()` to catch and re-raise `OrderPlacementError` after logging
- Task execution marked as "failed" immediately, stopping further order attempts

**Files Modified**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- `modules/kotak_neo_auto_trader/run_trading_service.py`
- `tests/unit/kotak/test_production_scenarios.py` (added test)

**Benefits**:
- Prevents account locks from repeated API calls
- Prevents duplicate orders from retries
- Faster failure detection
- Clear error reporting

---

### Performance Impact

**Before Optimizations**:
- Unified service: CSV file I/O for recommendations
- O(n) API calls for portfolio/indicators per recommendation
- O(n) price fetches for paper trading
- No per-ticker audit trail
- Retries on broker errors (risky)

**After Optimizations**:
- Unified service: Database queries (faster, consistent)
- O(1) API calls for portfolio/indicators (batched)
- O(1) price fetches for paper trading (batched)
- Complete per-ticker telemetry
- Fail-fast on broker errors (safe)

**Estimated Improvements**:
- **Latency**: 50-70% reduction for typical recommendation sets (10-50 tickers)
- **API Calls**: 80-90% reduction (from O(n) to O(1))
- **Reliability**: Improved (fail-fast prevents account issues)

---

### Testing

**New Test Coverage**:
- Added `test_order_placement_error_stops_run` to verify fail-fast behavior
- Verifies that `OrderPlacementError` stops processing immediately
- Ensures no further recommendations are processed after broker error

**Files Modified**:
- `tests/unit/kotak/test_production_scenarios.py`

---

### Files Modified

**Core Changes**:
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
  - Recommendation source unification (DB-first)
  - Per-ticker telemetry
  - Portfolio/indicator batching
  - Fail-fast error handling

- `src/application/services/paper_trading_service_adapter.py`
  - Price batching for paper trading

- `modules/kotak_neo_auto_trader/run_trading_service.py`
  - Fail-fast error handling in `run_buy_orders()`

**Tests**:
- `tests/unit/kotak/test_production_scenarios.py`
  - Added test for fail-fast behavior

---

### Backward Compatibility

All optimizations maintain backward compatibility:
- CSV fallback still works if database unavailable
- Individual price fetches still work if batch unavailable
- Existing summary statistics still available
- No breaking changes to API or data structures

---

## Individual Services Not Available in UI Fix

### Date: 2025-01-21

### Summary
Fixed issue where individual services were not appearing in the UI when the database was empty or schedules were missing.

### Issue
When the database was dropped or schedules were missing, the `get_status()` method in `IndividualServiceManager` returned an empty dictionary because it only returned services for existing schedules. This caused the UI to display "No individual services available".

### Fix
1. **Auto-creation of Default Schedules**:
   - Added `_ensure_default_schedules()` method to `IndividualServiceManager`
   - Automatically creates default schedules when none exist in the database
   - Called automatically from `get_status()` before returning service status
   - Creates all 6 default schedules: `premarket_retry`, `sell_monitor`, `position_monitor`, `analysis`, `buy_orders`, `eod_cleanup`

2. **Optimization**:
   - Added `_schedules_checked` flag to cache the check result
   - Avoids repeated database queries on subsequent `get_status()` calls
   - Only checks once per `IndividualServiceManager` instance

3. **Default Schedule Configuration**:
   - `premarket_retry`: 09:00, daily, enabled
   - `sell_monitor`: 09:15, daily, continuous (ends 15:30), enabled
   - `position_monitor`: 09:30, daily, hourly, enabled
   - `analysis`: 16:00, daily, enabled (admin-only)
   - `buy_orders`: 16:05, daily, enabled
   - `eod_cleanup`: 18:00, daily, enabled

### Files Modified
- `src/application/services/individual_service_manager.py`
  - Added `_ensure_default_schedules()` method
  - Added `_schedules_checked` flag for optimization
  - Updated `get_status()` to call `_ensure_default_schedules()`

### Testing
- Added comprehensive tests in `tests/unit/application/test_individual_service_manager_schedules.py`:
  - Test auto-creation of default schedules when missing
  - Test that schedules are not duplicated if they already exist
  - Test that `get_status()` returns services when schedules exist
  - Test handling of empty database

### Benefits
- Individual services now appear in UI even after database reset
- No manual intervention required to create schedules
- Automatic recovery from missing schedules
- Optimized to avoid unnecessary database queries

---

## Related Documentation
- [Individual Service Management User Guide](../features/INDIVIDUAL_SERVICE_MANAGEMENT_USER_GUIDE.md)
- [Individual Service Management Implementation Plan](../features/INDIVIDUAL_SERVICE_MANAGEMENT_IMPLEMENTATION_PLAN.md)
- [Paper Trading Documentation](../../paper_trading/README.md)
