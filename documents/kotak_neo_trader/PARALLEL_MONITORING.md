# Parallel Monitoring Implementation

## Overview

The sell order management system now uses **parallel processing** with ThreadPoolExecutor to monitor multiple stocks simultaneously, significantly reducing slippage risk during live trading.

## Key Features

### 1. Parallel Stock Monitoring
- **10 concurrent worker threads** (configurable via `max_workers`)
- All stocks monitored simultaneously instead of sequentially
- Dramatic performance improvement: **~5x faster** for 5 stocks

### 2. Scrip Master Integration
- Automatic download and caching of Kotak Neo instrument master
- Proper symbol/token resolution for accurate order placement
- Daily cache with auto-refresh capability
- Falls back to API or URL download

### 3. Lowest EMA9 Tracking
- Tracks the **lowest EMA9 value** seen for each position
- Only updates sell orders when EMA9 goes **lower** than previous minimum
- Prevents unnecessary order modifications
- Maximizes profit-taking potential

## Performance Comparison

### Before (Sequential)
```
5 stocks × 0.5s each = 2.5 seconds per monitoring cycle
```

### After (Parallel)
```
5 stocks processed simultaneously = 0.5 seconds per monitoring cycle
Speedup: 5x faster
Time saved: 2.0s per cycle
```

**Real-world impact:** With 60-second monitoring intervals and 390 minutes of trading:
- **Sequential:** 390 cycles × 2.5s = 975s wasted
- **Parallel:** 390 cycles × 0.5s = 195s wasted
- **Net savings:** ~13 minutes per trading day

## Architecture

### Thread-Safe Design

```python
# Each stock processed independently
for symbol in stocks:
    ThreadPoolExecutor.submit(
        check_and_update_single_stock,
        symbol, order_info
    )

# Results collected after all threads complete
for future in as_completed(futures):
    result = future.result()
    # Safe updates to shared state
```

### Data Flow

```
┌─────────────────────────────────────────────┐
│  Open Positions (Trade History)            │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Place Initial Sell Orders @ EMA9           │
│  (Sequential - happens once at market open) │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Continuous Monitoring Loop (Every 60s)     │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  Parallel Processing (10 workers)    │  │
│  │  ┌────────────────────────────────┐  │  │
│  │  │  Stock 1: Fetch LTP & EMA9     │  │  │
│  │  │  Stock 2: Fetch LTP & EMA9     │  │  │
│  │  │  Stock 3: Fetch LTP & EMA9     │  │  │
│  │  │  ...                            │  │  │
│  │  └────────────────────────────────┘  │  │
│  │                                       │  │
│  │  ┌────────────────────────────────┐  │  │
│  │  │  Compare with Lowest EMA9      │  │  │
│  │  │  Update if Lower               │  │  │
│  │  └────────────────────────────────┘  │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## Components

### 1. SellOrderManager
**Location:** `modules/kotak_neo_auto_trader/sell_engine.py`

**Enhancements:**
- `max_workers` parameter (default: 10)
- `scrip_master` integration for symbol resolution
- `_check_and_update_single_stock()` - thread-safe per-stock processing
- `monitor_and_update()` - parallel execution with ThreadPoolExecutor

### 2. KotakNeoScripMaster
**Location:** `modules/kotak_neo_auto_trader/scrip_master.py`

**Features:**
- Downloads daily instrument master from Kotak Neo
- Caches to `data/scrip_master/` (daily refresh)
- Symbol lookup and resolution
- Token mapping for API calls

### 3. Test Suite
**Location:** `modules/kotak_neo_auto_trader/test_parallel_monitoring.py`

**Tests:**
- Sequential vs parallel performance comparison
- Lowest EMA9 tracking verification
- Mock API with realistic delays

## Usage

### Basic Usage

```python
from sell_engine import SellOrderManager
from auth import KotakNeoAuth

# Initialize with authentication
auth = KotakNeoAuth('kotak_neo.env')
auth.login()

# Create sell order manager (10 workers by default)
sell_manager = SellOrderManager(auth)

# Place orders at market open
sell_manager.run_at_market_open()

# Monitor and update (runs in parallel)
while market_is_open():
    stats = sell_manager.monitor_and_update()
    print(f"Checked: {stats['checked']}, Updated: {stats['updated']}")
    time.sleep(60)
```

### Custom Worker Count

```python
# For more stocks or faster updates
sell_manager = SellOrderManager(auth, max_workers=20)

# For fewer resources
sell_manager = SellOrderManager(auth, max_workers=5)
```

### Running the Sell Order System

```bash
# Normal operation (wait for market open, monitor until close)
python modules/kotak_neo_auto_trader/run_sell_orders.py

# Test mode (skip wait, place orders and exit)
python modules/kotak_neo_auto_trader/run_sell_orders.py --skip-wait --run-once

# With custom monitoring interval
python modules/kotak_neo_auto_trader/run_sell_orders.py --monitor-interval 30
```

## Testing

### Performance Test
```bash
python modules/kotak_neo_auto_trader/test_parallel_monitoring.py
```

**Expected output:**
```
Sequential:  2.52s
Parallel:    0.51s
Speedup:     4.95x faster
✅ PASS
```

### Dry-Run Test (Real Data)
```bash
python modules/kotak_neo_auto_trader/test_real_env_dry_run.py
```

**Tests:**
- Real EMA9 calculation with live market data
- Parallel monitoring with actual positions
- No actual orders placed (dry-run mode)

## Configuration

### Environment Variables
```bash
# kotak_neo.env
KOTAK_CONSUMER_KEY=your_key
KOTAK_CONSUMER_SECRET=your_secret
KOTAK_MOBILE_NUMBER=your_mobile
KOTAK_PASSWORD=your_password
KOTAK_MPIN=your_mpin
```

### Settings
```python
# modules/kotak_neo_auto_trader/config.py
DEFAULT_EXCHANGE = "NSE"
DEFAULT_PRODUCT = "CNC"
TRADES_HISTORY_PATH = "data/trades_history.json"
```

## Monitoring Behavior

### Lowest EMA9 Logic

1. **Initial Order Placement**
   - Calculate current EMA9 from yesterday's EMA + today's LTP
   - Place limit sell order at EMA9 price
   - Store as `lowest_ema9[symbol]`

2. **Continuous Monitoring**
   - Every 60 seconds, recalculate EMA9 for all positions
   - Compare with `lowest_ema9[symbol]`
   - If `current_ema9 < lowest_ema9[symbol]`:
     - Cancel existing order
     - Place new order at lower price
     - Update `lowest_ema9[symbol]`

3. **Execution Tracking**
   - Check order status in parallel
   - When order executes:
     - Mark position closed in trade history
     - Calculate P&L
     - Remove from active tracking

### Safety Features

- **Pre-flight check:** Verifies portfolio holdings before placing orders
- **Duplicate prevention:** Checks existing positions to avoid duplicate orders
- **Price validation:** Skips orders if EMA9 is >5% below entry price
- **Error handling:** Graceful degradation on API failures
- **Thread safety:** Proper synchronization of shared state

## Troubleshooting

### Issue: Scrip master download blocked
**Solution:** System automatically falls back to using symbols as-is. During market hours with active authentication, the API method will work.

### Issue: "No compatible quote method found"
**Cause:** Market is closed or symbol resolution failed
**Solution:** This is normal outside market hours. During trading, the Kotak Neo API will provide live quotes.

### Issue: Orders not updating
**Check:**
1. Verify market is open (9:15 AM - 3:30 PM)
2. Check if EMA9 is actually going lower
3. Review logs for API errors
4. Ensure holdings can be fetched

### Issue: Slow performance
**Solutions:**
- Increase `max_workers` (default: 10)
- Check network latency
- Verify API rate limits not exceeded

## Future Enhancements

- [ ] Dynamic worker pool sizing based on position count
- [ ] WebSocket integration for real-time price updates
- [ ] Advanced order types (bracket, cover orders)
- [ ] Risk management rules (max drawdown, trailing stop)
- [ ] Performance metrics dashboard
- [ ] Alert system for critical events

## References

- Main Documentation: `SELL_ORDERS_README.md`
- Auto Trader Documentation: `README.md`
- Kotak Neo API: https://napi.kotaksecurities.com/
