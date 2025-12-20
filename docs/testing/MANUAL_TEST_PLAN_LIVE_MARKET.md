# Manual Test Plan - Order Management Flow (Live Market)

**Date**: 2025-12-07
**Version**: 1.0
**Purpose**: Comprehensive manual testing guide for order management flow in live market conditions

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Test Environment Setup](#test-environment-setup)
3. [Test Scenarios](#test-scenarios)
   - [Basic Order Placement & Execution](#1-basic-order-placement--execution)
   - [Reentry Order Scenarios](#2-reentry-order-scenarios)
   - [Sell Order Scenarios](#3-sell-order-scenarios)
   - [Session & Authentication](#4-session--authentication-scenarios)
   - [Error Handling & Recovery](#5-error-handling--recovery)
   - [Position Tracking & Reconciliation](#6-position-tracking--reconciliation)
   - [Concurrent Operations](#7-concurrent-operations)
   - [Edge Cases](#8-edge-cases)

---

## Prerequisites

### System Requirements
- ✅ Live market access (NSE/BSE trading hours: 9:15 AM - 3:30 PM IST)
- ✅ Broker account with sufficient balance for testing
- ✅ System running with all services active
- ✅ Database access for verification
- ✅ Log access for debugging

### Pre-Test Checklist
- [ ] Verify broker authentication is working
- [ ] Check system logs for any errors
- [ ] Verify database connectivity
- [ ] Ensure order monitoring service is running
- [ ] Check available balance in broker account
- [ ] Select test symbols (preferably low-value stocks for safety)

### Test Symbols Recommendation
- Use low-value stocks (₹10-50 range) to minimize risk
- Use liquid stocks to ensure order execution
- Avoid stocks with high volatility during testing
- Recommended: Small-cap stocks with good volume

---

## Test Environment Setup

### 1. Enable Test Mode (if available)
```bash
# Set environment variable for test mode
export TEST_MODE=true
```

### 2. Monitor Logs
```bash
# Tail logs for real-time monitoring
docker-compose logs -f tradeagent-api
```

### 3. Database Access
```bash
# Connect to database for verification
psql -h localhost -U postgres -d tradeagent
```

### 4. Key Queries for Verification

```sql
-- Check orders
SELECT * FROM orders WHERE user_id = '<user_id>' ORDER BY created_at DESC LIMIT 10;

-- Check positions
SELECT * FROM positions WHERE user_id = '<user_id>' AND closed_at IS NULL;

-- Check reentry tracking
SELECT symbol, reentries FROM positions WHERE user_id = '<user_id>' AND reentries IS NOT NULL;

-- Check order status
SELECT order_id, status, reason, executed_at FROM orders WHERE user_id = '<user_id>' ORDER BY created_at DESC;
```

---

## Test Scenarios

---

## 1. Basic Order Placement & Execution

### Test 1.1: New Entry Order Placement (AMO)

**Objective**: Verify new buy order placement and execution flow

**Prerequisites**:
- System time: 4:05 PM (or trigger manually)
- Available balance in broker account
- Valid buy signal for test symbol

**Test Steps**:
1. Trigger `place_new_entries()` (or wait for scheduled execution at 4:05 PM)
2. Monitor logs for order placement
3. Check database for new order entry
4. Wait for market open (9:15 AM next day)
5. Monitor order execution during market hours
6. Verify position creation after execution

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Order placed successfully | ✅ Log shows: "Order placed: <order_id>" |
| 2 | Order status = `PENDING` | ✅ Database: `orders.status = 'PENDING'` |
| 3 | Order reason = "Order placed - waiting for market open" | ✅ Database: `orders.reason` contains "waiting for market open" |
| 4 | Order appears in broker account | ✅ Broker portal: AMO order visible |
| 5 | Order executes at market open | ✅ Log shows: "Order executed: <order_id>" |
| 6 | Order status = `EXECUTED` | ✅ Database: `orders.status = 'EXECUTED'` |
| 7 | Position created in database | ✅ Database: New entry in `positions` table |
| 8 | Position quantity = execution quantity | ✅ Database: `positions.quantity = orders.executed_qty` |
| 9 | Position avg_price = execution price | ✅ Database: `positions.avg_price = orders.executed_price` |
| 10 | Position entry_rsi stored | ✅ Database: `positions.entry_rsi` is not null |

**How to Verify**:
```sql
-- Check order
SELECT order_id, symbol, status, reason, executed_at, executed_qty, executed_price
FROM orders
WHERE symbol = '<TEST_SYMBOL>'
ORDER BY created_at DESC
LIMIT 1;

-- Check position
SELECT symbol, quantity, avg_price, entry_rsi, created_at
FROM positions
WHERE symbol = '<TEST_SYMBOL>'
AND closed_at IS NULL;
```

**Notes**:
- Order should be placed as AMO (After Market Order)
- Execution should happen automatically at market open
- Transaction should be atomic (order + position creation)

---

### Test 1.2: Order Execution Monitoring

**Objective**: Verify order monitoring detects execution correctly

**Prerequisites**:
- Order placed and pending execution
- Market hours (9:15 AM - 3:30 PM)

**Test Steps**:
1. Place a buy order (or use existing pending order)
2. Monitor logs during market hours
3. Verify order execution detection
4. Check position creation timing

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Order monitoring active | ✅ Log shows periodic checks: "Checking buy order status" |
| 2 | Execution detected within 1-2 minutes | ✅ Log shows: "Order executed: <order_id>" |
| 3 | Position created immediately after execution | ✅ Database: `positions.created_at` ≈ `orders.executed_at` |
| 4 | Transaction atomicity maintained | ✅ Both order and position updated together |

**How to Verify**:
```sql
-- Check execution timing
SELECT
    o.order_id,
    o.executed_at,
    p.created_at,
    EXTRACT(EPOCH FROM (p.created_at - o.executed_at)) as time_diff_seconds
FROM orders o
JOIN positions p ON o.symbol = p.symbol
WHERE o.order_id = '<ORDER_ID>'
AND p.closed_at IS NULL;
-- time_diff_seconds should be < 5 seconds
```

---

## 2. Reentry Order Scenarios

### Test 2.1: Reentry Order Placement & Execution

**Objective**: Verify reentry order placement and execution with position update

**Prerequisites**:
- Existing open position for test symbol
- Position quantity > 0
- Price below entry price (for reentry trigger)

**Test Steps**:
1. Ensure open position exists for test symbol
2. Trigger reentry placement (or wait for scheduled execution)
3. Monitor reentry order placement
4. Wait for reentry order execution
5. Verify position update (quantity increase, avg price recalculation)
6. Verify reentry tracking in database

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Position exists and is open | ✅ Database: `positions.closed_at IS NULL` |
| 2 | Reconciliation runs before reentry | ✅ Log shows: "Reconciling holdings before reentry" |
| 3 | Reentry order placed | ✅ Database: New order with `is_reentry = true` |
| 4 | Reentry order executes | ✅ Log shows: "Reentry order executed: <order_id>" |
| 5 | Position quantity increased | ✅ Database: `positions.quantity` = old_qty + reentry_qty |
| 6 | Position avg_price recalculated | ✅ Database: `positions.avg_price` = weighted average |
| 7 | Reentry added to reentries array | ✅ Database: `positions.reentries` contains new reentry |
| 8 | Reentry count incremented | ✅ Database: `reentry_count` increased by 1 |
| 9 | Sell order quantity synced (if exists) | ✅ Broker: Sell order quantity = position quantity |

**How to Verify**:
```sql
-- Check position before and after
SELECT symbol, quantity, avg_price, reentry_count, reentries
FROM positions
WHERE symbol = '<TEST_SYMBOL>'
AND closed_at IS NULL;

-- Check reentry order
SELECT order_id, symbol, is_reentry, executed_at, executed_qty, executed_price
FROM orders
WHERE symbol = '<TEST_SYMBOL>'
AND is_reentry = true
ORDER BY executed_at DESC
LIMIT 1;

-- Verify reentry in array
SELECT
    symbol,
    jsonb_array_length(reentries) as reentry_count,
    reentries
FROM positions
WHERE symbol = '<TEST_SYMBOL>'
AND reentries IS NOT NULL;
```

**Notes**:
- Reentry should only be placed if price is below entry price
- Position quantity should be sum of all entries
- Avg price should be weighted average of all entries

---

### Test 2.2: Duplicate Reentry Prevention

**Objective**: Verify duplicate reentry detection prevents multiple reentries

**Prerequisites**:
- Reentry order already executed for the day
- Same order detected as executed again (simulate duplicate detection)

**Test Steps**:
1. Execute a reentry order
2. Verify reentry recorded in database
3. Simulate duplicate execution detection (or wait for concurrent processing)
4. Verify duplicate is rejected

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | First reentry executes successfully | ✅ Position updated, reentry added |
| 2 | Duplicate detection triggered | ✅ Log shows: "Duplicate reentry detected" |
| 3 | Duplicate reentry rejected | ✅ Log shows: "Skipping duplicate reentry" |
| 4 | Position not updated again | ✅ Database: `positions.quantity` unchanged |
| 5 | Reentry count not incremented | ✅ Database: `reentry_count` unchanged |

**How to Verify**:
```sql
-- Check reentry count before and after
SELECT symbol, reentry_count, jsonb_array_length(reentries) as array_length
FROM positions
WHERE symbol = '<TEST_SYMBOL>';

-- Should remain the same if duplicate was rejected
```

**Notes**:
- Duplicate detection uses locked read to prevent race conditions
- Re-check happens just before position update (Flaw #8 fix)

---

### Test 2.3: Reentry During Sell Order Update

**Objective**: Verify reentry execution during concurrent sell order update

**Prerequisites**:
- Open position with sell order
- Reentry order pending execution
- Sell order update triggered simultaneously

**Test Steps**:
1. Have open position with sell order
2. Trigger reentry order execution
3. Simultaneously trigger sell order update
4. Verify both operations complete correctly
5. Verify sell order quantity matches position quantity

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Both operations start | ✅ Logs show both operations |
| 2 | Position re-read with lock | ✅ Log shows: "Re-reading position with lock" |
| 3 | Reentry updates position | ✅ Position quantity increased |
| 4 | Sell order uses latest quantity | ✅ Sell order quantity = updated position quantity |
| 5 | No data inconsistency | ✅ Database: Position quantity = Sell order quantity |

**How to Verify**:
```sql
-- Check position and sell order consistency
SELECT
    p.symbol,
    p.quantity as position_qty,
    o.executed_qty as sell_order_qty
FROM positions p
LEFT JOIN orders o ON p.symbol = o.symbol
    AND o.transaction_type = 'SELL'
    AND o.status = 'ONGOING'
WHERE p.symbol = '<TEST_SYMBOL>'
AND p.closed_at IS NULL;
-- position_qty should equal sell_order_qty
```

**Notes**:
- Sell order update should re-read position with lock (Flaw #3 fix)
- Ensures latest quantity is used even if reentry executes concurrently

---

## 3. Sell Order Scenarios

### Test 3.1: Sell Order Placement at Market Open

**Objective**: Verify sell order placement at market open (9:15 AM)

**Prerequisites**:
- Open position exists
- Market open time (9:15 AM)
- Position quantity > 0

**Test Steps**:
1. Ensure open position exists
2. Wait for market open (9:15 AM) or trigger manually
3. Monitor sell order placement
4. Verify sell order in broker account
5. Verify sell order in database

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Position exists and is open | ✅ Database: `positions.closed_at IS NULL` |
| 2 | Reconciliation runs first | ✅ Log shows: "Reconciling holdings before sell order" |
| 3 | Position re-read with lock | ✅ Log shows: "Re-reading position with lock" |
| 4 | Sell order placed at 9:15 AM | ✅ Log shows: "Sell order placed: <order_id>" |
| 5 | Sell order status = `ONGOING` | ✅ Database: `orders.status = 'ONGOING'` |
| 6 | Sell order quantity = position quantity | ✅ Database: `orders.quantity = positions.quantity` |
| 7 | Sell order in broker account | ✅ Broker portal: Sell order visible |

**How to Verify**:
```sql
-- Check sell order
SELECT order_id, symbol, transaction_type, status, quantity, created_at
FROM orders
WHERE symbol = '<TEST_SYMBOL>'
AND transaction_type = 'SELL'
AND status = 'ONGOING'
ORDER BY created_at DESC
LIMIT 1;

-- Verify quantity match
SELECT
    p.quantity as position_qty,
    o.quantity as sell_order_qty
FROM positions p
JOIN orders o ON p.symbol = o.symbol
WHERE p.symbol = '<TEST_SYMBOL>'
AND p.closed_at IS NULL
AND o.transaction_type = 'SELL'
AND o.status = 'ONGOING';
```

---

### Test 3.2: Sell Order Execution & Position Closure

**Objective**: Verify sell order execution closes position correctly

**Prerequisites**:
- Open position with sell order
- Sell order executes (full execution)

**Test Steps**:
1. Have open position with sell order
2. Wait for sell order execution (or simulate)
3. Monitor position closure
4. Verify position closed in database
5. Verify pending reentry orders cancelled

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Sell order executes | ✅ Log shows: "Sell order executed: <order_id>" |
| 2 | Position marked as closed | ✅ Database: `positions.closed_at IS NOT NULL` |
| 3 | Position quantity = 0 | ✅ Database: `positions.quantity = 0` |
| 4 | Exit price stored | ✅ Database: `positions.exit_price = sell_execution_price` |
| 5 | Buy orders closed | ✅ Database: Related buy orders `status = 'CLOSED'` |
| 6 | Pending reentry orders cancelled | ✅ Database: Pending reentry orders `status = 'CANCELLED'` |
| 7 | Transaction atomicity | ✅ All updates happen together or not at all |

**How to Verify**:
```sql
-- Check closed position
SELECT symbol, quantity, closed_at, exit_price
FROM positions
WHERE symbol = '<TEST_SYMBOL>'
AND closed_at IS NOT NULL
ORDER BY closed_at DESC
LIMIT 1;

-- Check closed buy orders
SELECT order_id, symbol, status
FROM orders
WHERE symbol = '<TEST_SYMBOL>'
AND transaction_type = 'BUY'
AND status = 'CLOSED';

-- Check cancelled reentry orders
SELECT order_id, symbol, status, reason
FROM orders
WHERE symbol = '<TEST_SYMBOL>'
AND is_reentry = true
AND status = 'CANCELLED';
```

**Notes**:
- Position closure should be atomic (transaction wrapped)
- All related orders should be closed/cancelled together

---

### Test 3.3: Partial Sell Execution

**Objective**: Verify partial sell execution handling

**Prerequisites**:
- Open position with sell order
- Sell order partially executes (e.g., 50 of 100 shares)

**Test Steps**:
1. Have open position with sell order (quantity = 100)
2. Sell order partially executes (50 shares)
3. Monitor position update
4. Verify position quantity reduced
5. Verify sell order remains active
6. Verify reentry after partial sell syncs sell order

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Partial execution detected | ✅ Log shows: "Partial sell execution: 50/100" |
| 2 | Position quantity reduced | ✅ Database: `positions.quantity = 50` (was 100) |
| 3 | Position remains open | ✅ Database: `positions.closed_at IS NULL` |
| 4 | Sell order remains active | ✅ Database: Sell order `status = 'ONGOING'` |
| 5 | Sell order quantity updated | ✅ Database: Sell order `quantity = 50` |
| 6 | Reentry after partial sell | ✅ If reentry executes, sell order syncs to new quantity |

**How to Verify**:
```sql
-- Check position after partial sell
SELECT symbol, quantity, closed_at
FROM positions
WHERE symbol = '<TEST_SYMBOL>'
AND closed_at IS NULL;

-- Check sell order
SELECT order_id, symbol, quantity, status
FROM orders
WHERE symbol = '<TEST_SYMBOL>'
AND transaction_type = 'SELL'
AND status = 'ONGOING';
```

**Notes**:
- Partial sell should reduce position quantity
- Sell order should remain active for remaining quantity
- Reentry after partial sell should sync sell order quantity (Flaw #6 fix)

---

### Test 3.4: Sell Order Update Failure Recovery

**Objective**: Verify sell order update failure is recovered automatically

**Prerequisites**:
- Open position with sell order
- Reentry executes (should update sell order)
- Simulate broker API failure during sell order update

**Test Steps**:
1. Have open position with sell order
2. Execute reentry order
3. Simulate broker API failure during sell order update
4. Verify position still updated
5. Wait for periodic mismatch check (15 minutes)
6. Verify mismatch detected and fixed

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Reentry executes | ✅ Position quantity increased |
| 2 | Sell order update fails | ✅ Log shows: "Failed to update sell order" |
| 3 | Position still updated | ✅ Database: Position quantity = new quantity |
| 4 | Warning logged | ✅ Log shows: "Sell order update failed, will retry" |
| 5 | Mismatch detected (15 min) | ✅ Log shows: "Mismatch detected: position=110, sell_order=100" |
| 6 | Mismatch fixed | ✅ Log shows: "Sell order updated: 100 -> 110" |
| 7 | Consistency restored | ✅ Database: Position quantity = Sell order quantity |

**How to Verify**:
```sql
-- Check for mismatches
SELECT
    p.symbol,
    p.quantity as position_qty,
    o.quantity as sell_order_qty,
    (p.quantity - o.quantity) as mismatch
FROM positions p
JOIN orders o ON p.symbol = o.symbol
WHERE p.symbol = '<TEST_SYMBOL>'
AND p.closed_at IS NULL
AND o.transaction_type = 'SELL'
AND o.status = 'ONGOING'
AND p.quantity != o.quantity;
-- Should be empty after mismatch fix
```

**Notes**:
- Broker API called before DB update (Flaw #9 fix)
- Position updated even if broker API fails
- Periodic mismatch check fixes failures automatically (Flaw #7 fix)

---

## 4. Session & Authentication Scenarios

### Test 4.1: Session Expiry & Re-authentication

**Objective**: Verify automatic re-authentication on session expiry

**Prerequisites**:
- System running with active session
- Session expires during operation

**Test Steps**:
1. Start order placement operation
2. Simulate session expiry (or wait for natural expiry)
3. Monitor re-authentication
4. Verify operation retries after re-auth
5. Verify operation succeeds

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Operation starts | ✅ Log shows: "Placing order: <symbol>" |
| 2 | Auth error detected | ✅ Log shows: "Authentication error: JWT token expired" |
| 3 | Re-auth triggered | ✅ Log shows: "Re-authenticating..." |
| 4 | Re-auth succeeds | ✅ Log shows: "Re-authentication successful" |
| 5 | Operation retries | ✅ Log shows: "Retrying order placement..." |
| 6 | Operation succeeds | ✅ Order placed successfully |

**How to Verify**:
- Check logs for re-authentication messages
- Verify order placed successfully
- Check database for order entry

**Notes**:
- Re-authentication should be thread-safe
- Failure rate limiting prevents infinite loops
- Client refreshed after re-auth

---

### Test 4.2: Connection Error & Client Refresh

**Objective**: Verify client refresh on connection errors

**Prerequisites**:
- System running
- Connection error occurs (e.g., network issue)

**Test Steps**:
1. Trigger API call (e.g., get_holdings)
2. Simulate connection error (or wait for network issue)
3. Monitor client refresh
4. Verify operation retries with fresh client
5. Verify operation succeeds

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | API call starts | ✅ Log shows: "Getting holdings..." |
| 2 | Connection error detected | ✅ Log shows: "Connection refused" or "Connection error" |
| 3 | Client refreshed | ✅ Log shows: "Refreshed client from auth handler" |
| 4 | Operation retries | ✅ Log shows: "Retrying with fresh client..." |
| 5 | Operation succeeds | ✅ Holdings retrieved successfully |

**How to Verify**:
- Check logs for connection error and client refresh messages
- Verify API call succeeds after retry
- Check database for updated data

**Notes**:
- Connection errors trigger client refresh
- Fresh client ensures session (sId) is used
- Retry happens automatically

---

### Test 4.3: Timeout Error & Client Refresh

**Objective**: Verify client refresh on timeout errors

**Prerequisites**:
- System running
- Broker API slow or unresponsive

**Test Steps**:
1. Trigger API call (e.g., place_order)
2. Wait for timeout (30 seconds)
3. Monitor client refresh
4. Verify operation retries with fresh client
5. Verify operation succeeds

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | API call starts | ✅ Log shows: "Placing order: <symbol>" |
| 2 | Timeout occurs | ✅ Log shows: "SDK call timed out after 30 seconds" |
| 3 | Client refreshed | ✅ Log shows: "Refreshed client after timeout" |
| 4 | Operation retries | ✅ Log shows: "Retrying order placement..." |
| 5 | Operation succeeds | ✅ Order placed successfully |

**How to Verify**:
- Check logs for timeout and client refresh messages
- Verify order placed successfully after retry
- Check database for order entry

**Notes**:
- Timeout errors trigger client refresh
- Fresh client ensures session is used
- Retry happens automatically

---

## 5. Error Handling & Recovery

### Test 5.1: Broker API Failure During Order Placement

**Objective**: Verify graceful handling of broker API failures

**Prerequisites**:
- System running
- Broker API unavailable or returns error

**Test Steps**:
1. Trigger order placement
2. Simulate broker API failure
3. Monitor error handling
4. Verify appropriate error message
5. Verify no partial state in database

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Order placement starts | ✅ Log shows: "Placing order: <symbol>" |
| 2 | Broker API fails | ✅ Log shows: "Broker API error: <error>" |
| 3 | Error handled gracefully | ✅ Log shows: "Failed to place order: <reason>" |
| 4 | No partial state | ✅ Database: No order entry created |
| 5 | Error logged | ✅ Log contains error details |

**How to Verify**:
- Check logs for error messages
- Verify database has no partial order entry
- Check error notification (if configured)

---

### Test 5.2: Database Transaction Rollback

**Objective**: Verify transaction rollback on errors

**Prerequisites**:
- System running
- Error occurs during multi-step operation

**Test Steps**:
1. Trigger operation that involves multiple steps (e.g., order execution + position creation)
2. Simulate error during operation
3. Monitor transaction rollback
4. Verify no partial state

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Operation starts | ✅ Log shows: "Processing order execution..." |
| 2 | Error occurs | ✅ Log shows: "Error during operation: <error>" |
| 3 | Transaction rolls back | ✅ Log shows: "Transaction rolled back" |
| 4 | No partial state | ✅ Database: No partial updates |
| 5 | State consistent | ✅ Database: All related records consistent |

**How to Verify**:
```sql
-- Check for partial states
SELECT * FROM orders WHERE status = 'PENDING' AND executed_at IS NOT NULL;
-- Should be empty (no partial executions)

SELECT * FROM positions WHERE quantity = 0 AND closed_at IS NULL;
-- Should be empty (no invalid positions)
```

**Notes**:
- All multi-step operations wrapped in transactions
- Errors trigger automatic rollback
- Database state remains consistent

---

## 6. Position Tracking & Reconciliation

### Test 6.1: Manual Trade Detection

**Objective**: Verify manual trade detection and reconciliation

**Prerequisites**:
- Open position in database
- Manual trade executed outside system (buy or sell)

**Test Steps**:
1. Have open position in database
2. Execute manual trade in broker account (buy or sell)
3. Wait for reconciliation (30 minutes) or trigger manually
4. Monitor reconciliation process
5. Verify database updated

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Position exists | ✅ Database: Open position for symbol |
| 2 | Manual trade executed | ✅ Broker portal: Trade visible |
| 3 | Reconciliation triggered | ✅ Log shows: "Reconciling holdings..." |
| 4 | Mismatch detected | ✅ Log shows: "Mismatch detected: db_qty=X, broker_qty=Y" |
| 5 | Database updated | ✅ Database: Position quantity = broker holdings |
| 6 | Position closed if holdings = 0 | ✅ Database: `positions.closed_at IS NOT NULL` if holdings = 0 |

**How to Verify**:
```sql
-- Check position before and after reconciliation
SELECT symbol, quantity, closed_at
FROM positions
WHERE symbol = '<TEST_SYMBOL>';

-- Compare with broker holdings (manual check)
```

**Notes**:
- Reconciliation runs every 30 minutes during market hours
- Reconciliation also runs before reentry placement
- Manual trades are detected and database updated

---

### Test 6.2: Periodic Reconciliation

**Objective**: Verify periodic reconciliation during market hours

**Prerequisites**:
- System running during market hours
- Open positions exist

**Test Steps**:
1. Have open positions
2. Wait for reconciliation time (every 30 minutes: :00 and :30)
3. Monitor reconciliation execution
4. Verify reconciliation runs on schedule

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Reconciliation scheduled | ✅ System configured for 30-minute intervals |
| 2 | Reconciliation runs at :00 | ✅ Log shows: "Reconciling holdings..." at :00 |
| 3 | Reconciliation runs at :30 | ✅ Log shows: "Reconciling holdings..." at :30 |
| 4 | Holdings compared | ✅ Log shows: "Comparing positions with broker holdings" |
| 5 | Mismatches fixed | ✅ Database: Positions match broker holdings |

**How to Verify**:
- Check logs for reconciliation messages at :00 and :30
- Verify database positions match broker holdings

**Notes**:
- Reconciliation runs every 30 minutes during market hours
- Lightweight reconciliation runs before sell order updates

---

## 7. Concurrent Operations

### Test 7.1: Concurrent Reentry Executions

**Objective**: Verify database locking prevents race conditions

**Prerequisites**:
- Open position exists
- Multiple reentry orders execute simultaneously (simulate)

**Test Steps**:
1. Have open position
2. Simulate concurrent reentry executions (or rapid polling)
3. Monitor database locking
4. Verify only one reentry processed
5. Verify position updated correctly

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Multiple executions detected | ✅ Log shows: "Processing reentry execution..." |
| 2 | Database lock acquired | ✅ Log shows: "Acquiring lock for position..." |
| 3 | Only one processes | ✅ Log shows: "Reentry processed" (only once) |
| 4 | Position updated once | ✅ Database: `reentry_count` increased by 1 |
| 5 | No duplicate reentries | ✅ Database: `reentries` array has no duplicates |

**How to Verify**:
```sql
-- Check reentry count
SELECT symbol, reentry_count, jsonb_array_length(reentries) as array_length
FROM positions
WHERE symbol = '<TEST_SYMBOL>';

-- Should match (no duplicates)
```

**Notes**:
- Database-level locking (`SELECT ... FOR UPDATE`) prevents race conditions
- Second process sees updated state from first process
- No lost updates

---

### Test 7.2: Reentry During Sell Execution

**Objective**: Verify reentry doesn't reopen closed positions

**Prerequisites**:
- Open position with sell order
- Sell order executes
- Reentry order executes simultaneously

**Test Steps**:
1. Have open position with sell order
2. Sell order executes (closes position)
3. Reentry order executes simultaneously
4. Monitor position state
5. Verify position remains closed

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Sell order executes | ✅ Position closed: `positions.closed_at IS NOT NULL` |
| 2 | Reentry execution detected | ✅ Log shows: "Processing reentry execution..." |
| 3 | Closed position check | ✅ Log shows: "Position already closed, skipping reentry" |
| 4 | Reentry skipped | ✅ Log shows: "Skipping reentry for closed position" |
| 5 | Position remains closed | ✅ Database: `positions.closed_at IS NOT NULL` |
| 6 | Position quantity = 0 | ✅ Database: `positions.quantity = 0` |

**How to Verify**:
```sql
-- Check position state
SELECT symbol, quantity, closed_at
FROM positions
WHERE symbol = '<TEST_SYMBOL>';

-- Should be closed (closed_at IS NOT NULL, quantity = 0)
```

**Notes**:
- Re-check `closed_at` with locked read before position update (Flaw #4 fix)
- Prevents closed positions from being reopened

---

## 8. Edge Cases

### Test 8.1: Multiple Reentries in Same Day

**Objective**: Verify daily reentry cap enforcement

**Prerequisites**:
- Open position exists
- Reentry already executed today

**Test Steps**:
1. Execute first reentry for the day
2. Attempt second reentry (should be blocked)
3. Verify daily cap enforcement
4. Verify only one reentry per day

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | First reentry executes | ✅ Database: `reentry_count = 1` |
| 2 | Second reentry blocked | ✅ Log shows: "Daily reentry cap reached" |
| 3 | No second reentry order | ✅ Database: Only one reentry order for the day |
| 4 | Reentry count = 1 | ✅ Database: `reentry_count = 1` |

**How to Verify**:
```sql
-- Check reentry orders for the day
SELECT order_id, symbol, is_reentry, executed_at
FROM orders
WHERE symbol = '<TEST_SYMBOL>'
AND is_reentry = true
AND DATE(executed_at) = CURRENT_DATE;

-- Should be only one
```

---

### Test 8.2: Order Cancellation

**Objective**: Verify order cancellation works correctly

**Prerequisites**:
- Pending order exists
- Order can be cancelled

**Test Steps**:
1. Have pending order
2. Cancel order (manually or via system)
3. Monitor cancellation
4. Verify order status updated
5. Verify no position created

**Expected Results**:

| Step | Expected Result | Verification Method |
|------|----------------|---------------------|
| 1 | Order exists | ✅ Database: Order with `status = 'PENDING'` |
| 2 | Cancellation triggered | ✅ Log shows: "Cancelling order: <order_id>" |
| 3 | Order cancelled in broker | ✅ Broker portal: Order cancelled |
| 4 | Order status = `CANCELLED` | ✅ Database: `orders.status = 'CANCELLED'` |
| 5 | No position created | ✅ Database: No position for cancelled order |

**How to Verify**:
```sql
-- Check cancelled order
SELECT order_id, symbol, status, reason
FROM orders
WHERE order_id = '<ORDER_ID>';

-- Should be CANCELLED
```

---

## Test Execution Checklist

### Pre-Test
- [ ] Test environment set up
- [ ] Logs monitoring active
- [ ] Database access configured
- [ ] Test symbols selected
- [ ] Broker account verified

### During Test
- [ ] Monitor logs continuously
- [ ] Verify database after each operation
- [ ] Check broker portal for order status
- [ ] Document any unexpected behavior
- [ ] Take screenshots of key steps

### Post-Test
- [ ] Review all logs
- [ ] Verify database consistency
- [ ] Compare with expected results
- [ ] Document findings
- [ ] Report any issues

---

## Expected Test Results Summary

| Test Category | Total Tests | Expected Pass | Critical Tests |
|--------------|-------------|---------------|----------------|
| Basic Order Placement | 2 | 2 | ✅ All |
| Reentry Scenarios | 3 | 3 | ✅ All |
| Sell Order Scenarios | 4 | 4 | ✅ All |
| Session & Authentication | 3 | 3 | ✅ All |
| Error Handling | 2 | 2 | ✅ All |
| Position Tracking | 2 | 2 | ✅ All |
| Concurrent Operations | 2 | 2 | ✅ All |
| Edge Cases | 2 | 2 | ✅ All |
| **Total** | **20** | **20** | **✅ All** |

---

## Notes & Observations

### Important Notes
1. **Transaction Safety**: All multi-step operations are atomic (all succeed or all fail)
2. **Database Locking**: Position updates use `SELECT ... FOR UPDATE` to prevent race conditions
3. **Automatic Recovery**: Periodic checks fix inconsistencies automatically
4. **Session Management**: Automatic re-authentication on session expiry
5. **Client Refresh**: Client refreshed on timeout/connection errors

### Known Limitations
1. Reconciliation runs every 30 minutes (not real-time)
2. Mismatch check runs every 15 minutes (not real-time)
3. Manual trades detected during reconciliation cycles only

### Risk Mitigation
1. Use low-value stocks for testing
2. Monitor logs continuously
3. Have rollback plan ready
4. Test in small quantities first
5. Verify each step before proceeding

---

## Troubleshooting

### Common Issues

#### Issue: Order not executing
**Check**:
- Broker account balance
- Market hours (9:15 AM - 3:30 PM)
- Order status in broker portal
- Logs for errors

#### Issue: Position not created
**Check**:
- Order execution status
- Transaction logs
- Database for partial states
- Logs for errors

#### Issue: Reentry not placing
**Check**:
- Position exists and is open
- Price below entry price
- Daily reentry cap not reached
- Logs for validation errors

#### Issue: Sell order not syncing
**Check**:
- Position quantity
- Sell order quantity
- Periodic mismatch check logs
- Broker API connectivity

---

## Conclusion

This test plan provides comprehensive coverage of the order management flow. All critical scenarios are covered, including:

- ✅ Basic order placement and execution
- ✅ Reentry order scenarios
- ✅ Sell order scenarios
- ✅ Session and authentication
- ✅ Error handling and recovery
- ✅ Position tracking and reconciliation
- ✅ Concurrent operations
- ✅ Edge cases

**Expected Outcome**: All 20 tests should pass, confirming the system is production-ready and handles all scenarios correctly.

---

**Document Version**: 1.0
**Last Updated**: 2025-12-07
**Next Review**: After first live market test execution
