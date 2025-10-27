# Automated Sell Order Management System

Automated profit-taking system that places and manages sell orders for open positions using daily EMA9 as target.

## Features

1. **Market Open Execution** - Places limit sell orders at 9:15 AM for all open positions
2. **Dynamic Target Tracking** - Monitors daily EMA9 every minute and updates orders with lowest value
3. **Automatic Execution Tracking** - Marks positions as closed in trade history when orders execute
4. **Safe Order Management** - Prevents duplicate orders and validates entries

## How It Works

### Phase 1: Order Placement (9:15 AM)
- Reads all open positions from `trade_history.json`
- Fetches current daily EMA9 for each position
- Places limit sell orders at EMA9 price
- Validates that EMA9 is reasonable (not more than 5% below entry price)

### Phase 2: Continuous Monitoring (Until 3:30 PM)
- Checks EMA9 value every minute for all active positions
- If lower EMA9 is found:
  - Cancels existing sell order
  - Places new order at lower price
  - Tracks the lowest EMA9 seen
- Checks for order execution
- Updates trade history when orders execute

## Usage

### Basic Run (Waits for Market Open)
```bash
python -m modules.kotak_neo_auto_trader.run_sell_orders --env modules\kotak_neo_auto_trader\kotak_neo.env
```

### Testing (Skip Wait, Run Once)
```bash
# Place orders immediately without monitoring
python -m modules.kotak_neo_auto_trader.run_sell_orders --skip-wait --run-once --env modules\kotak_neo_auto_trader\kotak_neo.env
```

### Custom Monitor Interval
```bash
# Check every 2 minutes instead of default 1 minute
python -m modules.kotak_neo_auto_trader.run_sell_orders --monitor-interval 120 --env modules\kotak_neo_auto_trader\kotak_neo.env
```

## Command Line Options

- `--env`: Path to Kotak Neo credentials file (default: `kotak_neo.env`)
- `--monitor-interval`: Monitoring interval in seconds (default: 60)
- `--skip-wait`: Skip waiting for market open, start immediately
- `--run-once`: Place orders once and exit (no monitoring)

## Requirements

### Environment Setup
Same `kotak_neo.env` file used for buy orders:
```env
KOTAK_CONSUMER_KEY=your_key
KOTAK_CONSUMER_SECRET=your_secret
KOTAK_MOBILE_NUMBER=your_mobile
KOTAK_PASSWORD=your_password
KOTAK_MPIN=your_mpin
KOTAK_ENVIRONMENT=prod
```

### Trade History
System reads open positions from `data/trades_history.json`. Each trade entry must have:
- `symbol`: Base symbol (e.g., "GLENMARK")
- `ticker`: Full ticker with suffix (e.g., "GLENMARK.NS")
- `qty`: Quantity to sell
- `status`: "open" (only open positions are processed)
- `entry_price`: Entry price for validation

## Workflow Example

**9:00 AM** - Start script (waits for market open)
```bash
python -m modules.kotak_neo_auto_trader.run_sell_orders --env modules\kotak_neo_auto_trader\kotak_neo.env
```

**9:15 AM** - Market opens
- ✅ Auth with Kotak Neo
- ✅ Read 3 open positions from trade_history
- ✅ Fetch EMA9 for each: GLENMARK (₹1850), RELIANCE (₹2920), TCS (₹3540)
- ✅ Place 3 limit sell orders

**9:16 AM - 3:30 PM** - Continuous monitoring
- Every minute: Check if EMA9 is lower
- If yes: Cancel old order → Place new order at lower price
- Track executions → Update trade_history

**Order Executed at 2:45 PM**
- ✅ GLENMARK sold at ₹1848
- ✅ Position marked as closed in trade_history
- ✅ P&L calculated and logged
- ✅ 2 positions remaining in monitoring

**3:30 PM** - Market closes
- Stop monitoring
- Show session summary

## Safety Features

1. **Entry Validation** - Skips orders if EMA9 < 95% of entry price
2. **Duplicate Prevention** - Tracks active orders, prevents re-ordering
3. **Execution Tracking** - Removes executed orders from monitoring
4. **Error Handling** - Continues monitoring even if individual API calls fail
5. **Trading Day Check** - Only runs on weekdays
6. **Market Hours** - Automatically stops after 3:30 PM

## Output Example

```
============================================================
SELL ORDER MANAGEMENT SYSTEM
============================================================
Authenticating with Kotak Neo...
✅ Authentication successful
✅ Sell Order Manager initialized

============================================================
PHASE 1: PLACING SELL ORDERS AT MARKET OPEN
============================================================
Found 3 open positions in trade history
Placing LIMIT SELL order: GLENMARK-EQ x100 @ ₹1850.25
✅ Sell order placed: GLENMARK-EQ @ ₹1850.25, Order ID: 12345
Placing LIMIT SELL order: RELIANCE-EQ x50 @ ₹2920.50
✅ Sell order placed: RELIANCE-EQ @ ₹2920.50, Order ID: 12346
✅ Phase 1 complete: 2 sell orders placed

============================================================
PHASE 2: CONTINUOUS MONITORING
============================================================
Monitoring every 60 seconds until market close (3:30 PM)

--- Monitor Cycle #1 (09:16:30) ---
Monitoring 2 active sell orders...
Monitor cycle: 2 checked, 0 updated, 0 executed

--- Monitor Cycle #2 (09:17:30) ---
GLENMARK: New lower EMA9 found - ₹1848.75 (was ₹1850.25)
Cancelling order 12345 to update price
✅ Order updated: GLENMARK-EQ @ ₹1848.75, New Order ID: 12347
Monitor cycle: 2 checked, 1 updated, 0 executed

... [monitoring continues] ...

--- Monitor Cycle #45 (10:01:30) ---
✅ Sell order executed: Order ID 12347
Position closed: GLENMARK - P&L: ₹245.00 (+2.45%)
Monitor cycle: 2 checked, 0 updated, 1 executed

============================================================
SESSION SUMMARY
============================================================
Total monitor cycles: 320
Positions checked: 640
Orders updated: 15
Orders executed: 2
============================================================
```

## Integration with Auto Trader

### Complete Trading Workflow

**Morning (Pre-Market)**
1. Run analysis: `python -m src.presentation.cli.application analyze --backtest`
2. Generate buy recommendations with combined scores

**Market Open (9:15 AM)**
1. **Buy Side**: `run_auto_trade.py` - Place AMO buy orders (already filled)
2. **Sell Side**: `run_sell_orders.py` - Place sell orders for existing positions

**Throughout Day**
- Sell orders automatically updated if lower EMA9 found
- Executed orders update trade_history
- P&L calculated and logged

**Result**: Fully automated entry and exit management

## Troubleshooting

**"No open positions to place sell orders"**
- Check `data/trades_history.json` has entries with `status: "open"`
- Verify trade entries have required fields (symbol, ticker, qty)

**"Failed to fetch EMA9"**
- Check ticker format (e.g., "RELIANCE.NS" not "RELIANCE")
- Ensure yfinance can access the ticker
- Check internet connection

**"Order placement failed"**
- Verify Kotak Neo credentials
- Check if market is open (9:15 AM - 3:30 PM)
- Ensure sufficient holdings to sell

**"Skipping: EMA9 is too low"**
- System prevents selling at loss > 5%
- EMA9 is below 95% of entry price
- Either wait for price recovery or manually adjust

## Notes

- Orders are **LIMIT orders** (not market orders) at EMA9 price
- Orders are **DAY orders** (auto-cancel at end of day if not executed)
- EMA9 is calculated on **daily timeframe** (not intraday)
- System uses **REGULAR variety** (not AMO, since placed during market hours)
- Monitoring interval can be adjusted (default 60 seconds to avoid rate limits)

## Architecture

```
run_sell_orders.py (Runner/Scheduler)
    ↓
SellOrderManager (sell_engine.py)
    ├─→ get_open_positions() - Read trade_history.json
    ├─→ get_current_ema9() - Fetch daily EMA9 from yfinance
    ├─→ place_sell_order() - Place limit sell via KotakNeoOrders
    ├─→ update_sell_order() - Cancel & replace with new price
    ├─→ check_order_execution() - Monitor order status
    └─→ mark_position_closed() - Update trade_history.json
```

## Future Enhancements

- [ ] Telegram alerts for order execution
- [ ] Trailing stop-loss option (update on price increase)
- [ ] Multi-level profit taking (partial exits)
- [ ] Integration with re-entry logic (buy back on dips)
- [ ] Performance analytics dashboard
