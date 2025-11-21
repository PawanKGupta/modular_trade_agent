# Retry Behavior Change - December 2024

## Summary

Changed retry behavior from immediate retry queue processing during buy order placement to scheduled retry-only approach.

## Changes

### Before
- Failed orders (insufficient balance) were saved to retry queue
- Retry queue was processed immediately during the same `place_new_entries()` run
- Orders were retried in the same execution cycle

### After
- Failed orders are saved to database with `RETRY_PENDING` status
- No retry queue processing during buy order placement
- Retries only happen at scheduled time (8:00 AM) via `run_premarket_retry()`
- Manual retry via API/UI still available

## Implementation Details

### 1. Removed Retry Queue Processing from `place_new_entries()`
- Removed STEP 1 that processed failed orders from retry queue
- `place_new_entries()` now only processes new recommendations
- Summary no longer includes `retried` field

### 2. Added `retry_pending_orders_from_db()` Method
- New method in `AutoTradeEngine` to retry orders from database
- Reads orders with `RETRY_PENDING` status
- Validates portfolio limits, balance, holdings before retry
- Updates order status on success/failure

### 3. Updated `run_premarket_retry()` Task
- Changed from calling `place_new_entries()` to calling `retry_pending_orders_from_db()`
- Runs at scheduled time (8:00 AM) instead of during buy order placement
- Processes all `RETRY_PENDING` orders from database

### 4. Updated Insufficient Balance Handling
- When balance is insufficient, order is created in DB with `RETRY_PENDING` status
- Telegram notification updated to indicate retry at scheduled time
- No immediate retry attempt

## Benefits

1. **Cleaner Separation**: Buy order placement and retry logic are now separate
2. **Predictable Timing**: Retries happen at scheduled time, not during placement
3. **Better Resource Management**: No immediate retry attempts that might fail again
4. **Simpler Logic**: One attempt per order placement, retry handled separately

## Migration Notes

- Existing `RETRY_PENDING` orders in database will be retried at next scheduled time
- No database schema changes required
- API endpoints for manual retry remain unchanged

## Testing

- Added `test_auto_trade_engine_retry_from_db.py` - Tests for new retry method
- Added `test_auto_trade_engine_no_retry_during_placement.py` - Verifies no retry during placement
- Added `test_run_premarket_retry.py` - Tests for updated premarket retry task

## Files Changed

- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
  - Removed retry queue processing from `place_new_entries()`
  - Added `retry_pending_orders_from_db()` method
  - Updated insufficient balance handling

- `modules/kotak_neo_auto_trader/run_trading_service.py`
  - Updated `run_premarket_retry()` to call new retry method

- `documents/features/TRADING_WORKFLOW_ASCII.md`
  - Updated workflow diagram to reflect new retry behavior

