# Holdings API Retry and Database Fallback Feature

## Overview
This feature implements robust error handling for the holdings API used during buy order placement. When the broker API is temporarily unavailable (e.g., during maintenance windows), the system uses retry logic and a database fallback to prevent duplicate orders while still allowing legitimate new orders to be placed.

## Problem Statement

### Broker API Restrictions
- **Time-based restrictions**: Broker API may restrict balance/holdings checks between 12 AM - 6 AM IST
- **Transient failures**: Network issues, API rate limits, or temporary service outages can cause holdings API to fail
- **Impact**: Without proper handling, the system would either:
  - Block all orders when holdings API fails (too restrictive)
  - Place duplicate orders if holdings check is skipped (unsafe)

### Previous Behavior
- Holdings API failure would immediately abort order placement
- No retry mechanism for transient errors
- No fallback when API is unavailable
- Users couldn't place orders during broker maintenance windows

## Solution

### 1. Retry Logic
- **Automatic retries**: Up to 3 attempts with 2-second delays between retries
- **Transient error handling**: Catches temporary API failures and retries automatically
- **Logging**: Clear logs indicate retry attempts and final status

### 2. Database Fallback
When holdings API fails after all retries:
- **Check database**: Query existing orders table for pending/ongoing buy orders for the same symbols
- **Prevent duplicates**: If existing orders found, abort to prevent duplicates
- **Allow new orders**: If no existing orders found, proceed with order placement (with warning)
- **Broker-side validation**: Final safeguard - broker API validates balance and prevents duplicates

### 3. Graceful Degradation
- **No database available**: System aborts safely (prevents duplicates)
- **Database available**: Uses database check as fallback
- **Balance validation**: Still occurs during order placement via `get_affordable_qty()` and broker API

## Implementation Details

### Code Flow

```
1. Attempt holdings API (with retries)
   ├─ Success → Proceed with order placement
   └─ Failure → Check database fallback
       ├─ Database available → Check for existing orders
       │   ├─ Existing orders found → Abort (prevent duplicates)
       │   └─ No existing orders → Proceed with warning
       └─ No database → Abort safely
```

### Key Components

#### `place_new_entries()` Method
- **Pre-flight check**: Fetches holdings to verify API health
- **Retry loop**: Up to 3 attempts with 2-second delays
- **Database fallback**: Checks `orders` table for existing buy orders
- **Validation**: Ensures balance checks still occur during order placement

#### Database Query
```sql
SELECT COUNT(*) as count
FROM orders
WHERE user_id = :user_id
AND symbol = :symbol
AND side = 'buy'
AND status IN ('amo', 'ongoing')
```

### Error Handling

#### Holdings API Failures
- **Transient errors**: Retried automatically (up to 3 times)
- **Persistent errors**: Falls back to database check
- **No database**: Aborts safely with clear error message

#### Balance Validation
- **Still enforced**: Balance checks occur during order placement
- **Multiple layers**:
  1. Holdings API (if available)
  2. `get_affordable_qty()` during processing
  3. Broker API validation when submitting order

## Usage

### Normal Operation
1. System attempts to fetch holdings via API
2. If successful, proceeds with order placement
3. Balance validated during order processing

### During API Restrictions (12 AM - 6 AM)
1. Holdings API fails (expected during restricted hours)
2. System retries up to 3 times
3. After retries fail, checks database for existing orders
4. If no duplicates found, proceeds with order placement
5. Balance still validated during order placement

### Error Scenarios

#### Scenario 1: Transient API Failure
```
Holdings API fails → Retry 1 → Retry 2 → Success → Proceed
```

#### Scenario 2: Persistent API Failure (No Database)
```
Holdings API fails → Retries exhausted → No database → Abort safely
```

#### Scenario 3: Persistent API Failure (With Database, No Duplicates)
```
Holdings API fails → Retries exhausted → Database check → No duplicates → Proceed with warning
```

#### Scenario 4: Persistent API Failure (With Database, Duplicates Found)
```
Holdings API fails → Retries exhausted → Database check → Duplicates found → Abort
```

## Benefits

1. **Resilience**: System continues operating during broker API maintenance windows
2. **Safety**: Prevents duplicate orders through multiple validation layers
3. **User Experience**: Users can place orders even when holdings API is temporarily unavailable
4. **Transparency**: Clear logging indicates when fallback mechanisms are used

## Limitations

1. **Database dependency**: Fallback requires database access (aborts if unavailable)
2. **Potential duplicates**: If holdings exist but not in database, duplicates possible (mitigated by broker-side validation)
3. **Time restrictions**: Broker API restrictions during 12 AM - 6 AM are expected behavior

## Testing

See `tests/unit/modules/test_auto_trade_engine_holdings_fallback.py` for comprehensive test coverage including:
- Holdings API success scenarios
- Retry logic validation
- Database fallback scenarios
- Error handling edge cases

## Related Features

- **AMO Order Retry**: Retries failed orders due to insufficient balance
- **Order Tracking**: Tracks order status in database
- **Balance Validation**: Multiple layers of balance checking

## Future Improvements

1. **Cached holdings**: Cache holdings snapshot for use during API outages
2. **Predictive scheduling**: Skip holdings checks during known restriction windows
3. **Enhanced logging**: More detailed telemetry on fallback usage
