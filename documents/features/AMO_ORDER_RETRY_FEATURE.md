# AMO Order Retry Feature

## Overview
This feature resolves the critical issue where AMO orders rejected due to insufficient balance had no way to be retried, even after the user added funds to their account.

## Problem Statement
Previously, when an AMO order failed due to insufficient balance:
1. The system would send a notification about the insufficient balance
2. The order would be skipped
3. **No retry mechanism existed** - even if the user added balance later, the order would never be placed

## Solution
A comprehensive **same-day retry mechanism** has been implemented that:
1. **Tracks failed orders** in the trades history file
2. **Automatically retries** failed orders on subsequent runs **SAME DAY ONLY** when balance is available
3. **Auto-expires** orders at end of day (technical signals are time-sensitive)
4. **Removes from retry queue** once successfully placed or if symbol is already in holdings

## Implementation Details

### Storage Structure
The trades history JSON file (`trades_history.json`) now includes a `failed_orders` array:

```json
{
  "trades": [...],
  "failed_orders": [
    {
      "symbol": "RELIANCE",
      "ticker": "RELIANCE.NS",
      "close": 2450.50,
      "qty": 10,
      "required_cash": 24505.00,
      "shortfall": 5000.00,
      "reason": "insufficient_balance",
      "verdict": "strong_buy",
      "rsi10": 28.5,
      "ema9": 2400.00,
      "ema200": 2300.00,
      "first_failed_at": "2025-10-27T10:30:00",
      "retry_count": 2,
      "last_retry_attempt": "2025-10-27T11:00:00"
    }
  ],
  "last_run": "2025-10-27T11:00:00"
}
```

### New Functions in `storage.py`

#### `add_failed_order(path, failed_order)`
- Adds a failed order to the retry queue
- Updates existing entry if symbol already exists in queue
- Tracks first failure time and retry count

#### `get_failed_orders(path)`
- Returns list of all orders waiting to be retried
- Used by `place_new_entries` to attempt retries

#### `remove_failed_order(path, symbol)`
- Removes order from retry queue after successful placement
- Also called if symbol is already in holdings

### Modified Workflow in `place_new_entries`

The order placement now follows this two-step process:

**STEP 1: Retry Previously Failed Orders**
1. Load all failed orders from history
2. For each failed order:
   - Check portfolio limit
   - Skip if already in holdings (remove from queue)
   - Skip if active buy order exists
   - Get fresh market indicators
   - Check if balance is now sufficient
   - If yes: attempt to place order and remove from queue on success
   - If no: update retry count and timestamp

**STEP 2: Process New Recommendations**
1. Process recommendations from CSV as before
2. If insufficient balance detected:
   - Send notification (as before)
   - **NEW:** Save to failed_orders queue for retry
   - Skip for now
3. If sufficient balance: place order normally

### Key Features

#### Same-Day Retry Window
- Failed orders are only retried **on the same day** they were created
- Orders automatically expire at midnight (technical signals lose validity)
- Every time `run_place_amo.py` or the main engine runs, same-day failed orders are retried first
- No manual intervention required

#### Intelligent Deduplication
- Removes from retry queue if symbol already exists in holdings
- Skips retry if pending buy order already exists
- Prevents duplicate orders

#### Portfolio Limit Respect
- Retries respect the `MAX_PORTFOLIO_SIZE` limit
- Failed order retries happen before new recommendations

#### Fresh Data
- Each retry attempt fetches fresh market indicators (RSI, EMA, price)
- Ensures order is still valid and relevant

#### Retry Tracking
- Tracks number of retry attempts
- Records timestamp of each retry attempt
- Useful for debugging and monitoring

## User Notifications

When an order fails due to insufficient balance, the notification now includes:

```
⚠️ Insufficient balance for RELIANCE AMO BUY.
Needed: ₹24,505 for 10 @ ₹2,450.50.
Available: ₹19,505. Shortfall: ₹5,000.

🔁 Order saved for automatic retry TODAY if you add balance.
Note: Order expires end-of-day (signals are time-sensitive).
```

This informs users:
- The order will automatically retry if they add balance
- Only retries happen **same day** (order expires at midnight)
- Technical signals are time-sensitive and shouldn't carry over to next day

## Usage

No changes are required to existing workflows. The retry mechanism is automatically active:

```bash
# Normal AMO placement (will retry any previously failed orders first)
python -m modules.kotak_neo_auto_trader.run_place_amo --env modules/kotak_neo_auto_trader/kotak_neo.env --csv analysis_results/bulk_analysis_*.csv
```

## Logging

The run summary now includes retry statistics:

```
Run Summary: NewEntries placed=3/attempted=5, retried=2, failed_balance=1, 
skipped_dup=0, skipped_limit=0; Re/Exits: reentries=0, exits=0, symbols=3
```

Where:
- `retried`: Number of previously failed orders attempted in this run
- `failed_balance`: Number of new orders that failed due to insufficient balance (added to retry queue)
- `placed`: Total successfully placed (includes both new orders and successful retries)

## Testing

To test the feature:

1. **Create an insufficient balance scenario**:
   - Ensure your account has less balance than required for an order
   - Run `run_place_amo.py` with recommendations at 4:05 PM
   - Verify order is saved to `failed_orders` in `trades_history.json`

2. **Add balance and retry (same day)**:
   - Add sufficient balance to your account
   - Run `run_place_amo.py` again manually (or wait for next scheduled task if within same day)
   - Verify the failed order is retried and removed from queue on success

3. **Test expiry (next day)**:
   - If a failed order remains at end of day
   - Run the script next day
   - Verify expired orders are automatically cleaned up and NOT retried
   - Fresh recommendations from new analysis will be used instead

## Benefits

1. **Same-day retry only**: Respects time-sensitivity of technical signals
2. **No stale orders**: Auto-expires at end of day, preventing outdated trades
3. **No manual tracking needed**: System automatically remembers failed orders within the day
4. **Automatic recovery**: Orders placed as soon as balance is available (same day)
5. **User-friendly**: Clear notifications about retry window and expiry
6. **Portfolio-aware**: Respects limits and prevents duplicates

## Edge Cases Handled

1. **Symbol already in holdings**: Removed from retry queue
2. **Active pending order exists**: Skips retry to prevent duplicate
3. **Portfolio limit reached**: Stops retries until space available
4. **Price moved significantly**: Fresh indicators fetched on each retry
5. **Multiple failed orders**: All are tracked and retried in order
6. **Orders from previous day**: Automatically cleaned up and NOT retried (expired signals)
7. **End of day expiry**: All failed orders expire at midnight to prevent stale trades

## Files Modified

1. `modules/kotak_neo_auto_trader/storage.py`
   - Added `failed_orders` to storage structure
   - Added helper functions for failed order management

2. `modules/kotak_neo_auto_trader/auto_trade_engine.py`
   - Modified `place_new_entries` to retry failed orders first
   - Added `_attempt_place_order` helper to avoid code duplication
   - Enhanced logging to include retry statistics

## Why Same-Day Only?

**Technical Analysis is Time-Sensitive**:
- RSI, EMA, and other indicators change daily
- A "strong buy" signal today may not be valid tomorrow
- Price action can reverse overnight
- Better to use fresh analysis each day than retry stale orders

**Example**:
```
Monday 4:05 PM  → RELIANCE RSI=28 (oversold), EMA shows support → Strong Buy
                → Order fails (insufficient balance)

Tuesday Morning → RELIANCE RSI=45 (neutral), price moved up 3%
                → OLD signal no longer valid!
                → System runs fresh analysis, may generate different signal
```

## Future Enhancements

Potential improvements (not yet implemented):

1. **Priority ordering**: Retry based on RSI/signal strength within same day
2. **Multiple retry attempts**: Retry every X minutes if script runs multiple times per day
3. **Notification on success**: Alert user when a previously failed order succeeds
4. **Dashboard integration**: Show pending retry queue in monitoring dashboard
5. **Configurable expiry**: Allow user to set custom expiry window (e.g., 2 hours vs end-of-day)
