# Trading Services Flow - Real Trading Day

## Overview

The unified trading service (`run_trading_service.py`) runs continuously 24/7 and executes different tasks automatically on trading days (Monday-Friday) at specific times. This document explains the flow of each service during a real trading day.

---

## Service Architecture

### Unified Trading Service
- **Single Persistent Service**: Runs all tasks with one persistent session
- **Continuous Operation**: Runs 24/7, checks every 30 seconds
- **Trading Days Only**: Tasks execute only on Mon-Fri
- **Database-Driven Schedules**: Task times are configurable via database
- **Heartbeat Updates**: Updates service status every minute

---

## Daily Trading Flow Timeline

### 🌅 **Pre-Market (8:00 AM - 9:15 AM)**

#### 1. **Pre-Market Retry** (8:00 AM / Configurable)
**Task**: `run_premarket_retry()`

**Purpose**: Retry failed AMO orders from previous day

**Flow**:
1. Query database for orders with `RETRY_PENDING` status
2. For each pending order:
   - Check if order still valid (price, quantity, market conditions)
   - Retry placing the order
   - Update order status in database
3. Log summary: retried, placed, failed, skipped counts

**Key Operations**:
- Calls `engine.retry_pending_orders_from_db()`
- Updates order status in `orders` table
- Tracks execution in `task_executions` table

**Output**:
- Summary of retried orders
- New orders placed (if successful)
- Failed orders (if still failing)

---

#### 2. **Pre-Market AMO Adjustment** (9:05 AM)
**Task**: `run_premarket_amo_adjustment()`

**Purpose**: Adjust AMO order quantities based on pre-market prices

**Flow**:
1. Get all pending AMO orders from database
2. For each order:
   - Fetch current pre-market price
   - Calculate adjusted quantity based on price change
   - Modify order if quantity needs adjustment
3. Log summary: total orders, adjusted, no adjustment needed, etc.

**Key Operations**:
- Calls `engine.adjust_amo_quantities_premarket()`
- Modifies existing AMO orders via broker API
- Updates order quantities in database

**Output**:
- Number of orders adjusted
- Orders that didn't need adjustment
- Orders with price unavailable
- Modification failures

---

### 📈 **Market Hours (9:15 AM - 3:30 PM)**

#### 3. **Sell Monitor** (9:15 AM - 3:30 PM, Continuous)
**Task**: `run_sell_monitor()`

**Purpose**: Place sell orders at market open, then monitor continuously

**Flow - Initial Setup (9:15 AM, First Run)**:
1. **Place Sell Orders**:
   - Load open positions from database (via `SellOrderManager.get_open_positions()`)
   - For each open position:
     - Calculate EMA9 target price
     - Check if sell order already exists
     - Place limit sell order at EMA9 price
   - Log summary of orders placed

2. **Subscribe to Price Updates**:
   - Get symbols from open positions and existing sell orders
   - Subscribe to WebSocket price updates via `PriceService`
   - Enable real-time LTP (Last Traded Price) monitoring

3. **Cache Warming** (Pre-market warm-up):
   - Warm price cache for all open positions
   - Warm indicator cache (EMA9) for all open positions
   - Log cache warming statistics

**Flow - Continuous Monitoring (Every Minute)**:
1. **Monitor All Orders** (if `UnifiedOrderMonitor` available):
   - Check buy orders (AMO) status
   - Check sell orders status
   - Update order statuses in database
   - Place sell orders for newly executed buy orders
   - Track new holdings from executed orders

2. **Update Sell Orders** (if only `SellOrderManager`):
   - Check current EMA9 for each position
   - Update sell order price if EMA9 is lower (frozen EMA9 strategy)
   - Track executed sell orders
   - Mark positions as closed when sold

3. **Log Status** (once per minute):
   - Log unified monitor stats (checked, updated, executed, rejected, cancelled)
   - Or log sell monitor stats (checked, updated, executed)

**Key Operations**:
- `SellOrderManager.run_at_market_open()` - Places initial sell orders
- `UnifiedOrderMonitor.monitor_all_orders()` - Monitors both buy and sell orders
- `SellOrderManager.monitor_and_update()` - Updates sell order prices
- Database updates for order statuses and positions

**Output**:
- Initial: Number of sell orders placed
- Continuous: Order status updates, price adjustments, executions

---

#### 4. **Position Monitor** (9:30 AM, then Hourly until 3:30 PM)
**Task**: `run_position_monitor()`

**Purpose**: Monitor positions for reentry/exit signals

**Flow**:
1. Load open positions from database
2. For each position:
   - Check current price vs entry price
   - Check technical indicators (RSI, EMA, etc.)
   - Determine if reentry signal (buy more) or exit signal (sell)
   - Generate recommendations
3. Log position analysis results

**Key Operations**:
- Calls `engine.monitor_positions()`
- Analyzes technical indicators
- Updates position recommendations in database

**Output**:
- Position analysis results
- Reentry/exit signals
- Recommendations for each position

**Schedule**: Runs at 9:30 AM, then every hour (10:30, 11:30, 12:30, 1:30, 2:30, 3:30)

---

### 📊 **Post-Market (4:00 PM - 6:00 PM)**

#### 5. **Market Analysis** (4:00 PM)
**Task**: `run_analysis()`

**Purpose**: Analyze stocks and generate buy recommendations

**Flow**:
1. **Run Backtest Analysis**:
   - Execute `trade_agent.py --backtest` as subprocess
   - Analyze stocks using technical indicators
   - Score stocks based on strategy criteria
   - Generate buy signals (BUY, STRONG_BUY)

2. **Store Results**:
   - Save analysis results to database (`signals` table)
   - Store backtest scores and recommendations
   - Update stock rankings

3. **Error Handling**:
   - Retry on network errors (up to 3 attempts)
   - Log analysis failures
   - Continue even if analysis fails

**Key Operations**:
- Subprocess execution of `trade_agent.py --backtest`
- Database writes to `signals` table
- Stock scoring and ranking

**Output**:
- Analysis results in database
- Buy recommendations (signals)
- Backtest scores for stocks

**Note**: This task is typically admin-only and may be disabled for regular users

---

#### 6. **Buy Orders** (4:05 PM)
**Task**: `run_buy_orders()`

**Purpose**: Place AMO (After Market Order) buy orders for next day

**Flow**:
1. **Load Buy Recommendations**:
   - Query `signals` table for BUY/STRONG_BUY signals
   - Filter by strategy criteria (RSI, price, chart quality, etc.)
   - Rank by score/priority

2. **Check Portfolio Limits**:
   - Check current portfolio size
   - Check available capital
   - Skip if portfolio limit reached

3. **Place AMO Orders**:
   - For each recommendation:
     - Calculate order quantity based on capital allocation
     - Place AMO order via broker API
     - Track order in database (`orders` table)
   - Log summary of orders placed

4. **Order Tracking**:
   - Orders stored in database with `PENDING` status
   - Will be executed next day at market open (9:15 AM)
   - Status tracked until execution or rejection

**Key Operations**:
- Calls `engine.place_new_entries()` or `engine.place_amo_orders()`
- Broker API calls to place orders
- Database writes to `orders` and `positions` tables

**Output**:
- Summary: placed, skipped (duplicates, portfolio limit, missing data, invalid qty)
- Order IDs for tracking
- Orders ready for next day execution

---

#### 7. **End-of-Day Cleanup** (6:00 PM)
**Task**: `run_eod_cleanup()`

**Purpose**: End-of-day reconciliation and cleanup

**Flow**:
1. **Order Reconciliation**:
   - Compare broker orders with database orders
   - Detect any mismatches or missing orders
   - Update order statuses

2. **Manual Trade Detection**:
   - Check for manual trades (trades not placed by bot)
   - Update positions accordingly
   - Log manual trade activity

3. **Statistics Generation**:
   - Calculate daily P&L
   - Update position statistics
   - Generate trading statistics

4. **Cleanup**:
   - Reset daily flags
   - Prepare for next trading day
   - Clean up temporary data

5. **Notifications** (if enabled):
   - Send Telegram summary of day's trading
   - Include P&L, orders placed, positions closed

**Key Operations**:
- Calls `engine.eod_cleanup()` or `engine.reconcile_orders()`
- Database updates for positions and orders
- Statistics calculation and storage

**Output**:
- Daily P&L report
- Trading statistics
- Reconciliation results
- Telegram notification (if enabled)

---

## Service Execution Flow

### Scheduler Loop (Continuous)

```
1. Service starts → initialize() → login → authenticate
2. Enter scheduler loop (runs every 30 seconds)
3. Check if trading day (Mon-Fri)
4. For each minute:
   - Check scheduled tasks
   - Execute tasks at their designated times
   - Update heartbeat in database
5. Continue until shutdown (Ctrl+C)
```

### Task Execution Pattern

```
For each task:
1. Check if task is enabled (database schedule)
2. Check if task should run (time window)
3. Check if task already completed today
4. Execute task with error handling
5. Mark task as completed
6. Log execution to database
```

---

## Database Integration

### Tables Used

1. **`orders`**: All buy and sell orders
   - Status: PENDING, ONGOING, EXECUTED, REJECTED, CANCELLED, RETRY_PENDING
   - Tracks order lifecycle from placement to execution

2. **`positions`**: Open and closed positions
   - Tracks holdings (symbol, quantity, avg_price)
   - `closed_at` = NULL for open positions

3. **`signals`**: Buy recommendations from analysis
   - Stores BUY/STRONG_BUY signals
   - Used by buy_orders task

4. **`task_executions`**: Task execution tracking
   - Logs when each task ran
   - Stores execution results and summaries

5. **`service_status`**: Service health monitoring
   - Heartbeat updates every minute
   - Tracks service running status

6. **`task_schedules`**: Task scheduling configuration
   - Configurable task times
   - Enable/disable tasks
   - Continuous vs one-time tasks

---

## Key Features

### 1. **Database-Only Position Tracking**
- All positions loaded from `positions` table
- No file dependencies
- Single source of truth

### 2. **Unified Order Monitoring**
- Monitors both buy (AMO) and sell orders
- Places sell orders for newly executed buy orders
- Real-time status updates

### 3. **Frozen EMA9 Strategy**
- Sell orders placed at EMA9 price
- Price updated if EMA9 goes lower (frozen at lowest)
- Target: Mean reversion to EMA9

### 4. **AMO Order Management**
- Orders placed at 4:05 PM for next day
- Executed automatically at market open (9:15 AM)
- Pre-market retry for failed orders

### 5. **Continuous Monitoring**
- Sell monitor runs continuously during market hours
- Updates order prices every minute
- Tracks executions in real-time

---

## Error Handling

### Task-Level Error Handling
- Each task wrapped in `execute_task()` context
- Errors logged to database
- Task execution tracked even on failure
- Service continues running if task fails

### Service-Level Error Handling
- Scheduler loop continues on errors
- Heartbeat updates even if tasks fail
- Graceful shutdown on Ctrl+C
- Database session cleanup on exit

---

## Monitoring & Logging

### Logs
- All tasks log to database (`user_logs` table)
- Console logs for debugging
- User-scoped logging (per user_id)

### Heartbeat
- Updates every minute
- Tracks service running status
- Used for health monitoring

### Task Execution Tracking
- Each task execution logged to `task_executions`
- Stores execution time, duration, results
- Tracks success/failure status

---

## Configuration

### Task Schedules (Database)
- Configurable via `task_schedules` table
- Default times:
  - Pre-market retry: 8:00 AM (configurable)
  - Pre-market AMO adjustment: 9:05 AM
  - Sell monitor: 9:15 AM - 3:30 PM (continuous)
  - Position monitor: 9:30 AM (hourly)
  - Analysis: 4:00 PM (configurable)
  - Buy orders: 4:05 PM (configurable)
  - EOD cleanup: 6:00 PM (configurable)

### User Configuration
- Strategy parameters via `user_trading_config`
- Broker credentials via `user_settings`
- Per-user customization

---

## Example Daily Flow

### Monday (Trading Day)

```
8:00 AM  → Pre-market retry (retry failed orders from Friday)
9:05 AM  → Pre-market AMO adjustment (adjust quantities)
9:15 AM  → Sell monitor starts:
           - Place sell orders for all open positions
           - Subscribe to price updates
           - Start continuous monitoring
9:30 AM  → Position monitor (first run)
10:30 AM → Position monitor (hourly)
11:30 AM → Position monitor (hourly)
... (continues hourly)
3:30 PM  → Position monitor (last run)
          → Sell monitor continues until 3:30 PM
4:00 PM  → Market analysis (generate buy signals)
4:05 PM  → Buy orders (place AMO orders for Tuesday)
6:00 PM  → EOD cleanup (reconciliation, statistics, notifications)
```

### Tuesday (Trading Day)

```
8:00 AM  → Pre-market retry (retry any failed orders from Monday)
9:05 AM  → Pre-market AMO adjustment
9:15 AM  → AMO orders from Monday execute automatically
          → Sell monitor starts (places sell orders, monitors)
... (same flow as Monday)
```

---

## Summary

The unified trading service provides a complete automated trading system that:
- ✅ Retries failed orders before market opens
- ✅ Adjusts order quantities based on pre-market prices
- ✅ Places and monitors sell orders continuously
- ✅ Monitors positions for reentry/exit signals
- ✅ Analyzes stocks and generates recommendations
- ✅ Places buy orders for next day
- ✅ Performs end-of-day cleanup and reconciliation

All tasks are database-driven, configurable, and tracked for monitoring and debugging.
