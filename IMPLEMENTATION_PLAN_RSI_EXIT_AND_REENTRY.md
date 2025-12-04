# Implementation Plan: RSI Exit & Re-entry Integration

## Overview
Integrate RSI exit condition into sell monitor and re-entry logic into buy order service, removing the need for hourly position monitor.

---

## 1. RSI Exit in Sell Monitor

### Changes Required

#### 1.1 Cache Management
- **Add RSI10 cache** to `SellOrderManager`
  - Cache previous day's RSI10 at market open (9:15 AM)
  - Store: `{symbol: rsi10_value}`
  - Track converted orders: `{symbol}` set

#### 1.2 Real-time RSI Calculation
- **Calculate RSI10 every minute** during monitoring
  - **First**: Check previous day's RSI10 (cached at market open)
  - **Then**: Try to get real-time RSI10
  - If real-time available: Update cache and use real-time value (don't want to miss exit)
  - If real-time unavailable: Use cached previous day's RSI10
  - **Priority**: Previous day's RSI10 for initial check, then real-time for continuous monitoring

#### 1.3 RSI Exit Check
- **Check RSI10 > 50** for each active sell order
  - Skip if already converted to market
  - If RSI10 > 50:
    - **Primary**: Try to modify existing limit sell order to market order
    - **Fallback**: If modify fails, cancel existing limit sell order and place new market sell order
    - Track as converted (prevent duplicate conversion)
    - Remove from limit order monitoring

#### 1.4 Integration Points
- **Initialize cache** in `run_at_market_open()` (9:15 AM)
- **Check RSI exit** in `monitor_and_update()` (every minute)
- **Handle conversion** before EMA9 check (priority)

---

## 2. Re-entry in Buy Order Service

### Changes Required

#### 2.1 Entry RSI Tracking
- **Track entry RSI level** when position is opened
  - Store `entry_rsi` in position metadata
  - Used to determine re-entry progression

#### 2.2 Re-entry Level Logic
- **Respect entry RSI level** for re-entry progression:
  - Entry at RSI < 30 → Re-entry at RSI < 20 → RSI < 10 → Reset
  - Entry at RSI < 20 → Re-entry at RSI < 10 → Reset
  - Entry at RSI < 10 → Only Reset

#### 2.3 Reset Mechanism
- **Track reset state**:
  - When RSI > 30: Set `reset_ready = True`
  - When RSI drops < 30 after reset_ready: Reset all levels
  - After reset: New cycle starts (can re-enter at RSI < 30)

#### 2.4 Re-entry Order Placement
- **Check re-entry conditions** at 4:05 PM (with buy orders)
  - Load all open positions
  - For each position: Check re-entry conditions based on entry RSI
  - Validate capital available
  - Place open orders (AMO-like) for re-entries
  - Use same retry mechanism if insufficient balance

#### 2.5 Pre-market Re-entry Adjustment
- **Recalculate quantity and price** at 9:05 AM (pre-market adjustment)
  - Load all pending re-entry orders (filter by `Orders.entry_type = "reentry"`)
  - **Check if position closed**: Cancel re-entry order if position is closed
  - Recalculate quantity based on current price and available capital
  - Update order quantity and price (same as AMO adjustment)
  - **No RSI validation**: Don't check RSI conditions again
  - Execute at 9:15 AM (market open)

#### 2.6 Integration Points
- **Add re-entry check** in `run_buy_orders()` (4:05 PM)
- **Create new method**: `place_reentry_orders()`
- **Use existing retry mechanism**: `RETRY_PENDING` status
- **Retry at 8:00 AM**: Same as fresh entry retry
- **Add re-entry adjustment** in `adjust_amo_quantities_premarket()` (9:05 AM)

---

## 3. Remove Hourly Position Monitor

### Changes Required

#### 3.1 Remove Position Monitor Task (Real Trading)
- **Remove** `run_position_monitor()` from scheduler
- **Remove** hourly execution (9:30 AM, 10:30 AM, etc.)
- **Remove** task from `run_trading_service.py`

#### 3.2 Remove Position Monitor Task (Paper Trading)
- **Remove** `run_position_monitor()` from `PaperTradingServiceAdapter`
- **Remove** hourly execution (9:30 AM, 10:30 AM, etc.)
- **Remove** position monitor from paper trading scheduler

#### 3.3 Keep/Refactor Methods
- **Keep** `evaluate_reentries_and_exits()` method (refactor for re-entry only)
- **Remove** exit condition checks (moved to sell monitor)
- **Move** re-entry logic to buy order service
- **Paper Trading**: Keep `monitor_positions()` method but mark as deprecated

#### 3.4 Cleanup
- **Remove** position monitor health checks (no longer needed)
- **Remove** position monitor alerts (no longer needed)
- **Update** documentation to reflect changes

---

## 4. Files to Modify

### 4.1 Sell Monitor (`sell_engine.py`)
- Add RSI10 cache initialization
- Add real-time RSI10 calculation with fallback
- Add RSI exit condition check
- Add limit-to-market order conversion:
  - **Primary**: Modify existing order (change order_type from LIMIT to MARKET)
  - **Fallback**: Cancel and place new market order if modify fails
- Add converted order tracking

### 4.1.1 Paper Trading Sell Monitor (`paper_trading_service_adapter.py`)
- Add RSI10 cache initialization (paper trading)
- Add real-time RSI10 calculation with fallback (paper trading)
- Add RSI exit condition check (paper trading)
- **Note**: Paper trading may use different sell order mechanism
- **Note**: Adapt RSI exit logic for paper trading's order execution model

### 4.2 Buy Order Service (`auto_trade_engine.py`)
- Add entry RSI tracking when position opened
- Add re-entry condition check method
- Add re-entry order placement (open orders, AMO-like)
- Integrate re-entry check into `run_buy_orders()` (4:05 PM)
- Update retry mechanism to handle re-entry orders
- Add re-entry order adjustment in pre-market (9:05 AM)

### 4.2.1 Paper Trading Buy Order Service (`paper_trading_service_adapter.py`)
- Add entry RSI tracking when position opened (paper trading)
- Add re-entry condition check method (for paper trading)
- Integrate re-entry check into `run_buy_orders()` (paper trading)
- **Same as Real Trading**: Place open orders (AMO-like) that execute next day
- **Same as Real Trading**: Validate capital, use retry mechanism if insufficient
- **Same as Real Trading**: Recalculate quantity/price in pre-market (9:05 AM)

### 4.2.2 Pre-market AMO Adjustment (`auto_trade_engine.py`)
- **Extend** `adjust_amo_quantities_premarket()` to handle re-entry orders
- **Filter re-entry orders** by `Orders.entry_type = "reentry"` column
- **Check position status**: Cancel re-entry order if position is closed
- **Include** re-entry orders in pre-market quantity/price recalculation
- **Same logic** for both fresh entry and re-entry orders
- **No RSI validation**: Don't check RSI conditions again
- **Both brokers**: Real trading and paper trading use same adjustment logic

### 4.3 Trading Service (`run_trading_service.py`)
- Remove `run_position_monitor()` task
- Remove position monitor from scheduler
- Update initialization if needed

### 4.3.1 Paper Trading Service (`paper_trading_service_adapter.py`)
- Remove `run_position_monitor()` task (hourly execution)
- Remove position monitor from scheduler
- Update `PaperTradingEngineAdapter.monitor_positions()`:
  - Remove exit condition checks (moved to sell monitor)
  - Move re-entry logic to buy order service
  - Keep method for backward compatibility (deprecated)

### 4.4 Position Tracking
- **Add `entry_rsi` column** to `Positions` table (dedicated column, not just JSON)
- Update position loading to include entry RSI
- **Backfill strategy**: Use `Orders.order_metadata.rsi_entry_level` if available, or calculate from historical data
- Update `PositionsRepository` to handle `entry_rsi`

### 4.4.1 Database Schema Changes
- **Add column**: `Positions.entry_rsi` (Float, nullable)
- **Add column**: `Orders.entry_type` (String, nullable) - dedicated column for entry type tracking
- **Migration script**: Backfill `entry_rsi` from `Orders.order_metadata.rsi_entry_level` if available
- **Fallback**: Calculate from historical data if metadata not available

### 4.5 UI Cleanup (Frontend)
- **File**: `web/src/routes/dashboard/ServiceSchedulePage.tsx`
  - Remove `position_monitor` from service name mapping
- **File**: `web/src/routes/dashboard/IndividualServiceControls.tsx`
  - Remove `position_monitor` from service name and description mappings

### 4.6 UI Cleanup (Backend)
- **File**: `server/app/schemas/service.py`
  - Remove `position_monitor` from `StartIndividualServiceRequest` description
- **File**: `server/app/routers/service.py` (if exists)
  - Remove position monitor route handlers

### 4.7 Test Files
- **Remove**: `tests/unit/kotak/test_position_monitor.py`
- **Remove**: `tests/unit/kotak/test_position_monitor_position_loader.py`
- **Remove**: `modules/kotak_neo_auto_trader/dev_tests/test_realtime_position_monitor.py`
- **Modify**: `tests/unit/kotak/test_trading_service_*.py` (remove position monitor references)
- **Modify**: `tests/unit/kotak/test_reentry_logic_fix.py` (update for new implementation)
- **Add**: `tests/unit/kotak/test_sell_engine_rsi_exit.py` (new)
- **Add**: `tests/unit/kotak/test_buy_orders_reentry.py` (new)
- **Add**: `tests/integration/test_rsi_exit_reentry_integration.py` (new)
- **Add**: `tests/unit/paper_trading/test_paper_trading_rsi_exit.py` (new - paper trading)
- **Add**: `tests/unit/paper_trading/test_paper_trading_reentry.py` (new - paper trading)

---

## 5. Paper Trading Considerations

### 5.1 Shared Logic (Same for Both)

#### 5.1.1 RSI Exit Logic
- **Same Logic**: 
  - Cache previous day's RSI10 at market open
  - Calculate real-time RSI10 every minute (with fallback)
  - Check if RSI10 > 50
  - Modify existing order (LIMIT → MARKET), fallback to cancel+place
- **Only Difference**: Broker API calls (real broker vs paper broker)
- **Implementation**: Share RSI exit check logic, abstract broker calls

#### 5.1.2 Re-entry Logic
- **Same Logic**:
  - Track entry RSI level when position opened
  - Check re-entry conditions based on entry RSI
  - Respect level progression (30 → 20 → 10 → reset)
  - Check reset mechanism (RSI > 30 then drops < 30)
  - Validate capital available before placing order
  - Place open order (AMO-like) that executes next day
  - Recalculate quantity and price in pre-market (9:05 AM)
- **Same Behavior**: Both real trading and paper trading use same order model
  - Place open order at 4:05 PM (execute next day at 9:15 AM)
  - Recalculate quantity/price at 9:05 AM (pre-market adjustment)
  - Execute at 9:15 AM (market open)
- **Implementation**: Share re-entry condition check logic, same order placement model

#### 5.1.3 Entry RSI Tracking
- **Same Logic**: Track entry RSI when position is opened
- **Same Storage**: Store in position metadata
- **Same Usage**: Used to determine re-entry progression
- **Implementation**: Shared across both trading modes

### 5.2 Differences (Execution Model Only)

#### 5.2.1 Order Execution Model
- **Real Trading**: Uses AMO orders (placed at 4:05 PM, execute next day at 9:15 AM)
- **Paper Trading**: Uses immediate market orders (execute immediately)
- **Impact**: Order placement method differs, but condition check logic is shared

#### 5.2.2 Re-entry Execution
- **Both Trading Modes**: Re-entry orders placed as open orders (AMO-like)
  - Place at 4:05 PM (with buy orders)
  - Validate capital available
  - If insufficient balance: Save to retry queue (RETRY_PENDING)
  - Recalculate quantity and price at 9:05 AM (pre-market adjustment)
  - Execute at 9:15 AM (market open)
- **Impact**: Same re-entry condition check, same order placement model, same retry handling

#### 5.2.3 RSI Exit Execution
- **Both Trading Modes**: Modify existing order (LIMIT → MARKET)
  - **Primary**: Use `modify_order()` API to change order_type from LIMIT to MARKET
  - **Fallback**: If modify fails, cancel existing order and place new market order
- **Real Trading**: Uses real broker API (modify_order or cancel+place)
- **Paper Trading**: Uses paper broker API (modify_order or cancel+place)
- **Impact**: Same logic, different broker implementation (abstracted)

### 5.3 Implementation Strategy (Shared Logic)

#### 5.3.1 Shared RSI Exit Logic
- **Create**: Shared RSI exit check method (in `sell_engine.py` or shared utility)
- **Parameters**: Symbol, ticker, broker (abstracted)
- **Returns**: Should convert to market (boolean)
- **Usage**: Both real trading and paper trading use same method
- **Broker Abstraction**: Pass broker instance (real or paper) for order operations

#### 5.3.2 Shared Re-entry Logic
- **Create**: Shared re-entry condition check method (in `auto_trade_engine.py` or shared utility)
- **Parameters**: Position, current RSI, entry RSI, levels_taken
- **Returns**: Re-entry action (reentry_20, reentry_10, reset, or None)
- **Usage**: Both real trading and paper trading use same method
- **Order Placement**: Abstract order placement (AMO vs immediate market)

#### 5.3.3 Paper Trading Implementation
- **RSI Exit**: Use shared RSI exit check, pass paper broker for order operations
- **Re-entry**: Use shared re-entry condition check, place immediate market orders
- **Entry RSI Tracking**: Use shared tracking logic

### 5.4 Paper Trading Specific Changes

#### 5.4.1 RSI Exit in Paper Trading Sell Monitor
- **File**: `src/application/services/paper_trading_service_adapter.py`
- **Method**: `_monitor_sell_orders()` (already exists)
- **Changes**:
  - Call shared RSI exit check method
  - Pass paper broker for order conversion
  - Same logic as real trading, different broker instance

#### 5.4.2 Re-entry in Paper Trading Buy Order Service
- **File**: `src/application/services/paper_trading_service_adapter.py`
- **Method**: `run_buy_orders()` (already exists)
- **Changes**:
  - Call shared re-entry condition check method
  - Validate capital available (same as real trading)
  - Place open orders (AMO-like) that execute next day (same as real trading)
  - Use retry mechanism if insufficient balance (same as real trading)
  - Track entry RSI when position opened (shared logic)

#### 5.4.3 Pre-market Re-entry Adjustment (Both Brokers)
- **File**: `auto_trade_engine.py` and `paper_trading_service_adapter.py`
- **Method**: `adjust_amo_quantities_premarket()` (extend existing)
- **Changes**:
  - Include re-entry orders in pre-market adjustment
  - Recalculate quantity based on current price
  - Update order quantity and price (same as AMO adjustment)
  - Both brokers use same adjustment logic

#### 5.4.3 Remove Paper Trading Position Monitor
- **File**: `src/application/services/paper_trading_service_adapter.py`
- **Method**: `run_position_monitor()` (remove)
- **Method**: `monitor_positions()` (keep but mark as deprecated)
- **Changes**:
  - Remove hourly position monitor task
  - Move re-entry logic to buy order service (using shared logic)
  - Move exit logic to sell monitor (using shared logic)

### 5.3 Paper Trading Test Requirements
- **RSI Exit Tests**: Same as real trading (different broker mock)
- **Re-entry Tests**: Same logic, immediate execution (no retry tests)
- **Integration Tests**: Include paper trading scenarios

---

## 6. Key Implementation Details

### 5.1 RSI Exit Flow
```
Market Open (9:15 AM):
  → Cache previous day's RSI10 for all positions

Every Minute:
  → First: Check previous day's RSI10 (cached)
  → Then: Calculate real-time RSI10 (update cache if available)
  → Use real-time if available (don't want to miss exit)
  → Fallback to cached previous day's value if real-time unavailable
  → Check if RSI10 > 50
  → If yes: Modify existing limit order to market order
  → If modify fails: Cancel limit order → Place market order (fallback)
  → Track converted orders (prevent duplicates)
```

### 5.2 Re-entry Flow
```
4:05 PM (Buy Order Service):
  → Load all open positions
  → For each position:
     → Check entry RSI level
     → Determine next re-entry level
     → Check reset condition
     → Validate capital available
     → Place open order (AMO-like) if condition met
     → Tag order with entry_type = "reentry" (dedicated column)
  → If insufficient balance: Save to RETRY_PENDING
  → Retry at 8:00 AM (same as fresh entries)

9:05 AM (Pre-market Adjustment):
  → Load all pending orders (fresh entry + re-entry)
  → Filter re-entry orders by entry_type column
  → Check if position closed: Cancel re-entry order if position is closed
  → Recalculate quantity based on current price
  → Update order quantity and price
  → No RSI validation (orders placed at 4:05 PM are valid)
  → Execute at 9:15 AM (market open)
```

### 5.3 Re-entry Level Progression
```
Entry RSI < 30:
  → Re-entry at RSI < 20
  → Then at RSI < 10
  → Then only reset

Entry RSI < 20:
  → Re-entry at RSI < 10
  → Then only reset

Entry RSI < 10:
  → Only reset (RSI > 30 then drops < 30)
```

---

## 7. Edge Cases to Handle

### 6.1 RSI Exit
- Real-time RSI unavailable → Use cached previous day's value
- Order already converted → Skip (prevent duplicate)
- **Primary path**: Modify existing order (LIMIT → MARKET)
  - If modify succeeds → Order converted, track as converted
- **Fallback path**: If modify fails
  - Cancel existing limit order
  - Place new market sell order
  - If cancel fails → Log error, send user notification, keep limit order (no retry)
  - If place fails → Log error, send user notification, keep limit order (no retry)
  - Order executes between cancel and place → Log warning, send user notification
- **Error Handling**: No retry mechanism, use user notifications and logging only

### 6.2 Re-entry
- Entry RSI not tracked → Use default 29.5 (assume entry at RSI < 30)
- Reset state not tracked → Initialize on first check
- Multiple re-entry opportunities → Only one per day per symbol
- Insufficient balance → Save to retry queue (same as fresh entries)
- **Both Brokers**: Re-entry orders placed as open orders (execute next day)
- **Both Brokers**: Re-entry orders adjusted in pre-market (9:05 AM)
- **Position check at 9:05 AM**: Cancel re-entry order if position is closed
- **No RSI validation at 9:05 AM**: Don't check RSI conditions again
- **Entry type tracking**: Use dedicated `Orders.entry_type` column (not just JSON metadata)

---

## 8. Testing Considerations

### 7.1 RSI Exit Testing
- Test cache initialization at market open
- Test previous day's RSI10 check (first priority)
- Test real-time RSI calculation (second priority)
- Test fallback to cached value
- Test limit-to-market conversion:
  - Test modify order (primary path)
  - Test cancel+place fallback (if modify fails)
  - Test modify failure scenarios
- Test duplicate prevention
- Test error handling (modify fails, cancel fails, placement fails) - verify notifications sent, no retry

### 7.2 Re-entry Testing
- Test entry RSI tracking (stored in `Positions.entry_rsi` column)
- Test re-entry level progression
- Test reset mechanism
- Test AMO order placement with `entry_type` column
- Test retry mechanism for insufficient balance
- Test multiple positions with different entry RSI levels
- Test pre-market adjustment (cancel if position closed, no RSI validation)
- Test entry RSI backfill from `Orders.order_metadata.rsi_entry_level`

### 7.3 Integration Testing
- Test RSI exit during sell monitoring (previous day first, then real-time)
- Test re-entry during buy order placement (with `entry_type` column)
- Test retry mechanism for both fresh and re-entry orders
- Test pre-market adjustment with re-entry orders (cancel if position closed, no RSI validation)
- Test entry RSI backfill migration
- Test removal of position monitor
- Test error handling (notifications sent, no retry/fallback)

---

## 9. Migration Notes

### 8.1 Data Migration
- **Add columns**: `Positions.entry_rsi` and `Orders.entry_type`
- **Backfill strategy**: 
  - Use `Orders.order_metadata.rsi_entry_level` if available
  - Or calculate from historical data (fetch RSI at entry date)
  - Default to 29.5 if not available (assume entry at RSI < 30)
- **Migration script**: 
  - Backfill `entry_rsi` for existing positions
  - Backfill `entry_type` for existing orders (identify re-entry orders)
  - Log warnings for positions/orders without entry RSI data

### 8.2 Configuration
- No new configuration needed
- Existing retry mechanism works for re-entry orders
- RSI exit uses existing sell monitor infrastructure

### 8.3 Rollout
- Can be implemented incrementally
- RSI exit can be added first
- Re-entry can be added second
- Position monitor can be removed last

---

## 10. Benefits

### 9.1 Architecture
- **Simpler**: Fewer services (remove position monitor)
- **More efficient**: Real-time RSI exit detection
- **Better integration**: Re-entry uses existing buy order flow

### 9.2 User Experience
- **Faster exit**: RSI exit detected every minute
- **Consistent retry**: Re-entry uses same retry mechanism
- **Overnight window**: Time to add funds for re-entry orders

### 9.3 Code Quality
- **Less duplication**: Re-entry uses existing AMO infrastructure
- **Better separation**: Exit logic with sell orders, re-entry with buy orders
- **Easier maintenance**: Fewer moving parts

---

## 11. Open Questions / Clarifications

1. **RSI Exit**: Should we check previous day's RSI10 or current day's RSI10?
   - **Decision**: Check previous day's RSI10 first, then continue using real-time (don't want to miss exit)
   - **Logic**: Previous day's RSI10 for initial check, real-time for continuous monitoring

2. **Re-entry Timing**: Should we check re-entry during pre-market retry (8:00 AM)?
   - **Decision**: No, only at 4:05 PM (when buy orders run)

3. **Position Monitor**: Should we keep any health checks or alerts?
   - **Decision**: No, remove completely

4. **Entry RSI Tracking**: How to handle existing positions without entry RSI?
   - **Decision**: Default to 29.5 for existing positions (assume entry at RSI < 30)

5. **Paper Trading Re-entry**: Should paper trading re-entry execute immediately or schedule for next day?
   - **Decision**: Schedule for next day (open orders, AMO-like) - same as real trading
   - **Reason**: Consistent behavior, capital validation, pre-market adjustment

6. **Pre-market Re-entry Adjustment**: Should re-entry orders be adjusted in pre-market?
   - **Decision**: Yes, both fresh entry and re-entry orders adjusted at 9:05 AM
   - **Reason**: Recalculate quantity/price based on current market conditions
   - **Position check**: Cancel re-entry order if position is closed
   - **No RSI validation**: Don't check RSI conditions again

7. **Entry RSI Storage**: Where to store entry RSI?
   - **Decision**: Add dedicated `entry_rsi` column to `Positions` table
   - **Backfill**: Use `Orders.order_metadata.rsi_entry_level` if available, or calculate from historical data
   - **Default**: 29.5 if not available (assume entry at RSI < 30)

8. **Re-entry Order Tracking**: How to identify re-entry orders?
   - **Decision**: Add dedicated `entry_type` column to `Orders` table (not just JSON metadata)

9. **Error Handling**: Should we use retry/fallback mechanisms?
   - **Decision**: No retry/fallback, use user notifications and logging only

---

## 12. Implementation Order

1. **Phase 1**: RSI Exit in Sell Monitor
   - Add cache management (real trading)
   - Add RSI exit check (real trading)
   - Add limit-to-market conversion (real trading)
   - Add RSI exit for paper trading (adapt for paper trading model)
   - Add tests (`test_sell_engine_rsi_exit.py`)
   - Add paper trading tests (`test_paper_trading_rsi_exit.py`)
   - Test thoroughly

2. **Phase 2**: Re-entry in Buy Order Service
   - Add entry RSI tracking (both brokers)
   - Add re-entry condition check (shared logic)
   - Add re-entry order placement (open orders, AMO-like, both brokers)
   - Integrate with buy order service (4:05 PM, both brokers)
   - Add pre-market re-entry adjustment (9:05 AM, both brokers)
   - Extend `adjust_amo_quantities_premarket()` to include re-entry orders
   - Add tests (`test_buy_orders_reentry.py`)
   - Add paper trading tests (`test_paper_trading_reentry.py`)
   - Add pre-market adjustment tests (`test_premarket_reentry_adjustment.py`)
   - Test thoroughly

3. **Phase 3**: Remove Position Monitor
   - Remove position monitor task from scheduler (real trading)
   - Remove position monitor task from scheduler (paper trading)
   - Remove position monitor from UI (frontend + backend)
   - Remove position monitor tests
   - Clean up unused code
   - Update documentation

4. **Phase 4**: Test Updates & Integration
   - Update existing tests (remove position monitor references)
   - Add integration tests (real trading + paper trading)
   - Verify test coverage >80%
   - Update test documentation

---

## 13. UI Cleanup - Position Monitor Removal

### 12.1 Frontend Changes

#### 12.1.1 Service Schedule Page
- **File**: `web/src/routes/dashboard/ServiceSchedulePage.tsx`
- **Remove**: `position_monitor` from service name mapping
- **Action**: Remove entry `position_monitor: 'Position Monitor'`

#### 12.1.2 Individual Service Controls
- **File**: `web/src/routes/dashboard/IndividualServiceControls.tsx`
- **Remove**: `position_monitor` from:
  - Service name mapping: `position_monitor: 'Position Monitor'`
  - Service description mapping: `position_monitor: 'Monitors positions hourly for reentry/exit signals'`
- **Action**: Remove both entries from mappings

### 12.2 Backend API Changes

#### 12.2.1 Service Schema
- **File**: `server/app/schemas/service.py`
- **Remove**: `position_monitor` from `StartIndividualServiceRequest` description
- **Action**: Update description to: `"Task name: premarket_retry, sell_monitor, buy_orders, eod_cleanup"`

#### 12.2.2 Service Router (if exists)
- **File**: `server/app/routers/service.py` (or similar)
- **Remove**: Any position monitor endpoints or references
- **Action**: Remove position monitor route handlers if they exist

### 12.3 Documentation Cleanup
- **File**: `documents/features/LIVE_POSITION_MONITORING.md`
- **Action**: Mark as deprecated or remove entirely
- **File**: `WHY_POSITION_MONITORING_REQUIRED.md`
- **Action**: Update to reflect new architecture or remove

---

## 14. Test Modifications & Cleanup

### 13.1 Tests to Remove/Deprecate

#### 13.1.1 Position Monitor Tests
- **File**: `tests/unit/kotak/test_position_monitor.py`
- **Action**: **Remove** - Position monitor no longer exists
- **Reason**: Tests for removed functionality

#### 13.1.2 Position Monitor with Position Loader Tests
- **File**: `tests/unit/kotak/test_position_monitor_position_loader.py`
- **Action**: **Remove** - Position monitor no longer exists
- **Reason**: Tests for removed functionality

#### 13.1.3 Dev Tests for Position Monitor
- **File**: `modules/kotak_neo_auto_trader/dev_tests/test_realtime_position_monitor.py`
- **Action**: **Remove** - Dev test for removed functionality
- **Reason**: No longer needed

### 13.2 Tests to Modify

#### 13.2.1 Trading Service Tests
- **File**: `tests/unit/kotak/test_trading_service_thread_safety.py`
- **Modify**: Remove position monitor task from scheduler tests
- **Action**: Update tests to exclude position monitor from task list

#### 13.2.2 Auto Trade Engine Tests
- **File**: `tests/unit/kotak/test_auto_trade_engine_*.py` (various files)
- **Modify**: Update tests that reference `evaluate_reentries_and_exits()`
- **Action**: 
  - Remove exit condition tests (moved to sell monitor)
  - Keep re-entry logic tests but update to reflect new flow
  - Update tests to check re-entry in buy order service context

#### 13.2.3 Re-entry Logic Tests
- **File**: `tests/unit/kotak/test_reentry_logic_fix.py`
- **Modify**: Update to reflect new re-entry implementation
- **Action**: 
  - Update to test re-entry in buy order service
  - Test entry RSI level progression
  - Test reset mechanism
  - Test AMO order placement for re-entries

#### 13.2.4 Paper Trading Tests
- **File**: `tests/unit/paper_trading/test_paper_trading_service_adapter.py` (if exists)
- **Modify**: Remove position monitor task from scheduler tests
- **Action**: Update tests to exclude position monitor from task list

### 13.3 New Tests to Add

#### 13.3.1 RSI Exit in Sell Monitor Tests
- **New File**: `tests/unit/kotak/test_sell_engine_rsi_exit.py`
- **Test Cases**:
  - Test RSI10 cache initialization at market open
  - Test real-time RSI10 calculation and cache update
  - Test fallback to cached previous day's RSI10
  - Test RSI exit condition check (RSI10 > 50)
  - Test limit-to-market order conversion:
    - Test modify order (primary path) - change order_type from LIMIT to MARKET
    - Test modify success scenario
    - Test modify failure scenario (fallback to cancel+place)
    - Test cancel+place fallback path
  - Test duplicate conversion prevention
  - Test error handling (modify fails, cancel fails, placement fails)
  - Test order execution between cancel and place (fallback scenario)

#### 13.3.2 Re-entry in Buy Order Service Tests
- **New File**: `tests/unit/kotak/test_buy_orders_reentry.py`
- **Test Cases**:
  - Test entry RSI tracking when position opened
  - Test re-entry condition check based on entry RSI level
  - Test re-entry level progression (30 → 20 → 10 → reset)
  - Test reset mechanism (RSI > 30 then drops < 30)
  - Test AMO order placement for re-entries
  - Test retry mechanism for insufficient balance
  - Test multiple positions with different entry RSI levels
  - Test re-entry with fresh entry same day (should not happen)

#### 13.3.3 Integration Tests
- **New File**: `tests/integration/test_rsi_exit_reentry_integration.py`
- **Test Cases**:
  - Test RSI exit during sell monitoring (end-to-end) - real trading
  - Test re-entry during buy order placement (end-to-end) - real trading
  - Test retry mechanism for both fresh and re-entry orders - real trading
  - Test position monitor removal (verify no errors) - real trading
  - Test UI cleanup (verify no position monitor references)
  - Test RSI exit in paper trading (end-to-end)
  - Test re-entry in paper trading (end-to-end)
  - Test position monitor removal in paper trading

#### 13.3.4 Trading Service Tests Updates
- **File**: `tests/unit/kotak/test_trading_service_database_only.py`
- **Add Tests**:
  - Test position monitor removal from scheduler
  - Test RSI exit integration in sell monitor
  - Test re-entry integration in buy order service

#### 13.3.5 Paper Trading RSI Exit Tests
- **New File**: `tests/unit/paper_trading/test_paper_trading_rsi_exit.py`
- **Test Cases**:
  - Test RSI10 cache initialization (paper trading)
  - Test real-time RSI10 calculation (paper trading)
  - Test RSI exit condition check (paper trading)
  - Test sell order conversion (paper trading model)
  - Test error handling (paper trading)

#### 13.3.6 Paper Trading Re-entry Tests
- **New File**: `tests/unit/paper_trading/test_paper_trading_reentry.py`
- **Test Cases**:
  - Test entry RSI tracking (paper trading)
  - Test re-entry condition check (paper trading)
  - Test re-entry level progression (paper trading)
  - Test reset mechanism (paper trading)
  - Test open order placement (AMO-like, not immediate)
  - Test capital validation (paper trading)
  - Test retry mechanism for insufficient balance (paper trading)
  - Test pre-market quantity/price recalculation (paper trading)

#### 13.3.7 Pre-market Re-entry Adjustment Tests
- **New File**: `tests/unit/kotak/test_premarket_reentry_adjustment.py`
- **Test Cases**:
  - Test re-entry orders filtered by `entry_type` column
  - Test quantity recalculation for re-entry orders
  - Test price update for re-entry orders
  - Test both fresh entry and re-entry orders adjusted together
  - Test cancellation if position closed at 9:05 AM
  - Test no RSI validation at 9:05 AM
  - Test real trading pre-market adjustment
  - Test paper trading pre-market adjustment

---

## 15. Test Coverage Requirements

### 14.1 RSI Exit Tests
- **Target Coverage**: >80%
- **Critical Paths**:
  - Cache initialization ✅
  - Real-time RSI calculation ✅
  - Fallback to cache ✅
  - RSI exit condition check ✅
  - Order conversion ✅
  - Error handling ✅

### 14.2 Re-entry Tests
- **Target Coverage**: >80%
- **Critical Paths**:
  - Entry RSI tracking ✅
  - Re-entry condition check ✅
  - Level progression ✅
  - Reset mechanism ✅
  - AMO placement ✅
  - Retry mechanism ✅

### 14.3 Integration Tests
- **Target Coverage**: >70%
- **Critical Paths**:
  - End-to-end RSI exit flow ✅
  - End-to-end re-entry flow ✅
  - Retry mechanism ✅
  - Position monitor removal ✅

---

## 16. Success Criteria

- ✅ RSI exit detected every minute during market hours
- ✅ Limit orders converted to market when RSI10 > 50
- ✅ Re-entry orders placed at 4:05 PM based on entry RSI level (both brokers)
- ✅ Re-entry orders retried at 8:00 AM if insufficient balance (both brokers)
- ✅ Re-entry orders adjusted in pre-market (9:05 AM, both brokers)
- ✅ Re-entry orders execute at 9:15 AM (market open, both brokers)
- ✅ Position monitor removed from scheduler
- ✅ Position monitor removed from UI (frontend + backend)
- ✅ Position monitor tests removed/deprecated
- ✅ New tests added for RSI exit and re-entry
- ✅ Test coverage >80% for new functionality
- ✅ No duplicate orders (fresh entry + re-entry same day)
- ✅ Re-entry respects level progression (30 → 20 → 10 → reset)

