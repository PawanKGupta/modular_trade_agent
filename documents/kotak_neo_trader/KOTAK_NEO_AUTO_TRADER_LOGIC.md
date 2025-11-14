# Kotak Neo Auto Trader - Buying, Selling, and Re-entry Logic

## Overview

The Kotak Neo Auto Trader (`modules/kotak_neo_auto_trader/`) implements an automated trading system that:
1. **Buys new stocks** from recommendations (CSV files)
2. **Manages re-entries** for existing positions based on RSI levels
3. **Sells positions** when target (EMA9) is hit or exit conditions are met

## Key Components

### 1. Buying New Stocks (`place_new_entries`)

**Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` (lines 1054-1324)

**Process**:
1. **Portfolio Limit Check**: Maximum 6 stocks (`MAX_PORTFOLIO_SIZE = 6`)
2. **Duplicate Prevention**: 
   - Skips if already in holdings
   - Cancels existing pending buy orders before placing new ones
3. **Capital Calculation**: 
   - Uses `execution_capital` from recommendation CSV (if available)
   - Otherwise calculates based on liquidity: `calculate_execution_capital(ticker, price, avg_volume)`
   - Default: ₹100,000 per trade (`CAPITAL_PER_TRADE`)
4. **Position Size Validation**: 
   - Checks position-to-volume ratio (liquidity filter)
   - Ensures position size is not too large relative to average volume
5. **Balance Check**: 
   - Verifies sufficient cash available
   - If insufficient, saves order for retry (until 9:15 AM next day)
   - Sends Telegram notification on insufficient balance
6. **Order Placement**: 
   - Places AMO (After Market Order) buy orders
   - Records trade in `data/trades_history.json`

**Key Logic**:
```python
# Check portfolio limit
if current_count >= MAX_PORTFOLIO_SIZE:
    skip

# Check if already in holdings
if has_holding(symbol):
    skip

# Calculate quantity
execution_capital = recommendation.execution_capital or calculate_execution_capital(...)
qty = floor(execution_capital / price)

# Check balance
if qty > affordable_qty:
    save_for_retry()
    send_telegram_notification()
    continue

# Place order
place_market_buy(symbol, qty, variety="AMO")
```

### 2. Re-entry Logic (`evaluate_reentries_and_exits`)

**Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` (lines 1327-1685)

**Re-entry Levels**:
- **Level 1 (RSI < 30)**: Initial entry level (marked as taken after first entry)
- **Level 2 (RSI < 20)**: Second re-entry level
- **Level 3 (RSI < 10)**: Third re-entry level (extreme oversold)

**Reset Logic**:
- If RSI > 30: Mark position as `reset_ready = True`
- If RSI < 30 again (after being > 30): Reset all levels, treat as NEW CYCLE
- This allows re-entries after position recovers

**Re-entry Conditions**:
```python
# Check current RSI level
levels = entries[0].get('levels_taken', {"30": True, "20": False, "10": False})

# Reset handling
if rsi > 30:
    entries[0]['reset_ready'] = True

# New cycle detection
if rsi < 30 and reset_ready:
    # Reset all levels, trigger re-entry at RSI<30
    levels = {"30": False, "20": False, "10": False}
    next_level = 30

# Normal progression
if levels.get('30') and not levels.get('20') and rsi < 20:
    next_level = 20  # Re-entry at RSI < 20
if levels.get('20') and not levels.get('10') and rsi < 10:
    next_level = 10  # Re-entry at RSI < 10
```

**Re-entry Protection**:
- **Daily Cap**: Max 1 re-entry per symbol per day
- **Duplicate Prevention**: 
  - Skips if already in holdings
  - Skips if active buy order exists
- **Balance Check**: Reduces quantity if insufficient funds

**Re-entry Execution**:
```python
if next_level is not None:
    # Daily cap check
    if reentries_today(symbol) >= 1:
        skip
    
    # Calculate quantity
    execution_capital = calculate_execution_capital(ticker, price, avg_volume)
    qty = floor(execution_capital / price)
    
    # Balance check
    if qty > affordable_qty:
        qty = affordable_qty
    
    # Place re-entry order
    if not has_holding(symbol) and not has_active_buy_order(symbol):
        place_market_buy(symbol, qty)
        entries[0]['levels_taken'][str(next_level)] = True
```

### 3. Exit/Selling Logic (`evaluate_reentries_and_exits` + `sell_engine.py`)

**Location**: 
- Exit conditions: `auto_trade_engine.py` (lines 1371-1517)
- Sell order management: `modules/kotak_neo_auto_trader/sell_engine.py`

**Exit Conditions**:
- **EMA9 Target**: Price >= EMA9 (target reached)
- **RSI50 Exit**: RSI > 50 (overbought exit)
- Configurable via `EXIT_ON_EMA9_OR_RSI50 = True`

**Exit Process**:
```python
# Check exit conditions
if EXIT_ON_EMA9_OR_RSI50 and (price >= ema9 or rsi > 50):
    # Place market sell order
    total_qty = sum(entry['qty'] for entry in entries)
    place_market_sell(symbol, total_qty)
    
    # Mark all entries as closed
    for entry in entries:
        entry['status'] = 'closed'
        entry['exit_price'] = price
        entry['exit_reason'] = 'EMA9 or RSI50'
```

**Sell Order Management** (`SellOrderManager`):

1. **Place Sell Orders at Market Open** (`run_at_market_open`):
   - Places limit sell orders at EMA9 target for all open positions
   - Checks for existing orders to avoid duplicates
   - Updates order if EMA9 changes during the day

2. **Monitor and Update** (`monitor_and_update`):
   - Monitors EMA9 in real-time (every minute)
   - Updates sell order price if EMA9 drops (only lowers, never raises)
   - Tracks lowest EMA9 value seen during the day
   - Uses parallel processing for multiple positions

3. **Order Execution Tracking**:
   - Checks for executed orders
   - Updates trade history when order executes
   - Marks position as closed
   - Calculates P&L

**Sell Order Logic**:
```python
# At market open (9:15 AM)
for open_position in get_open_positions():
    # Get current EMA9 (real-time with LTP)
    ema9 = get_current_ema9(ticker, broker_symbol)
    
    # Place limit sell order at EMA9
    order_id = place_limit_sell(symbol, qty, price=ema9)
    
    # Track order
    track_sell_order(symbol, order_id, target_price=ema9)

# During market hours (every minute)
for active_sell_order in active_sell_orders:
    # Get current EMA9
    current_ema9 = get_current_ema9(ticker)
    
    # Update if EMA9 is lower (only lower, never raise)
    if current_ema9 < lowest_ema9_seen:
        update_sell_order(order_id, new_price=current_ema9)
        lowest_ema9_seen = current_ema9
```

## Key Differences from Integrated Backtest

### 1. Position Tracking
- **Auto Trader**: Uses `data/trades_history.json` to track positions
- **Integrated Backtest**: Uses in-memory `IntegratedPosition` objects

### 2. Re-entry Logic
- **Auto Trader**: 
  - Tracks RSI levels (`levels_taken: {"30": True, "20": False, "10": False}`)
  - Resets levels when RSI > 30, then < 30 again
  - Daily cap: Max 1 re-entry per symbol per day
- **Integrated Backtest**: 
  - Tracks positions in memory
  - Adds re-entries to existing position (averaging)
  - No daily cap (processes all signals)

### 3. Exit Logic
- **Auto Trader**: 
  - Exits when `price >= ema9` OR `rsi > 50`
  - Places limit sell orders at EMA9 target
  - Updates sell orders if EMA9 drops during the day
- **Integrated Backtest**: 
  - Exits when `high >= target_price` (EMA9)
  - No RSI50 exit condition
  - Simulates exit at target price

### 4. Capital Management
- **Auto Trader**: 
  - Uses `execution_capital` based on liquidity
  - Adjusts quantity based on available balance
  - Saves failed orders for retry
- **Integrated Backtest**: 
  - Uses fixed `capital_per_position` (default: ₹100,000)
  - No balance checks (simulation)

### 5. Order Execution
- **Auto Trader**: 
  - Places real broker orders (AMO/MARKET)
  - Tracks order status
  - Handles order failures and retries
- **Integrated Backtest**: 
  - Simulates order execution
  - No order tracking
  - Assumes all orders execute successfully

## Important Notes

### Re-entry Reset Logic
The auto trader uses a **reset mechanism** for re-entries:
1. When RSI > 30: Position is marked as `reset_ready = True`
2. When RSI < 30 again: All levels are reset, treating it as a new cycle
3. This allows re-entries after the position recovers above RSI 30

### Daily Cap
- **Re-entries**: Max 1 re-entry per symbol per day
- **New entries**: No daily cap (limited by portfolio size)

### Position Tracking
- Positions are tracked in `data/trades_history.json`
- Each entry has:
  - `status`: 'open' or 'closed'
  - `levels_taken`: Which RSI levels have been used
  - `reset_ready`: Whether position can reset levels
  - `entry_price`, `exit_price`, `qty`, `pnl`, etc.

### Sell Order Management
- Sell orders are placed as **limit orders** at EMA9 target
- Orders are updated if EMA9 drops during the day (only lower, never raise)
- Tracks lowest EMA9 value seen to ensure best exit price

## Configuration

**Key Config Values** (`modules/kotak_neo_auto_trader/config.py`):
- `MAX_PORTFOLIO_SIZE = 6`: Maximum number of stocks in portfolio
- `CAPITAL_PER_TRADE = 100000`: Default capital per trade (₹1 lakh)
- `RSI_PERIOD = 10`: RSI period (synced with StrategyConfig)
- `EMA_SHORT = 9`: EMA9 for target calculation
- `EMA_LONG = 200`: EMA200 for trend filter
- `EXIT_ON_EMA9_OR_RSI50 = True`: Exit when target hit or RSI > 50
- `MIN_COMBINED_SCORE = 25`: Minimum score for recommendations

## Comparison with Integrated Backtest Fix

The **integrated backtest fix** we just implemented ensures that:
1. Positions are tracked **before** processing new signals
2. If a position closes, new signals execute as **new entries** (not pyramiding)
3. If a position is still open, new signals execute as **pyramiding** (re-entries)

This aligns with the auto trader's logic:
- Auto trader checks `has_holding(symbol)` before placing new orders
- If holding exists, it's treated as re-entry (pyramiding)
- If no holding exists, it's treated as new entry

The key difference is that the integrated backtest processes signals sequentially and tracks positions in memory, while the auto trader checks holdings from the broker and tracks positions in JSON files.
