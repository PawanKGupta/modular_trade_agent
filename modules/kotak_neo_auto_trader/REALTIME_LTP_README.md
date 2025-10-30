# Real-Time LTP Integration

WebSocket-based real-time price streaming for accurate EMA9 trailing stops.

## Overview

The position monitor now uses **real-time LTP** from Kotak Neo WebSocket instead of 15-minute delayed yfinance data. This ensures:

- ✅ **Accurate EMA9 calculation** with current market prices
- ✅ **Real-time exit detection** without delay
- ✅ **Automatic fallback to yfinance** if WebSocket unavailable
- ✅ **Zero additional cost** (included with Kotak Neo account)

---

## Architecture

```
┌──────────────────────────┐
│  Position Monitor        │
│  (Hourly Check)          │
└────────────┬─────────────┘
             │
             v
┌──────────────────────────┐
│  Live Price Manager      │
│  (Get LTP)               │
└────────────┬─────────────┘
             │
      ┌──────┴──────┐
      v             v
┌───────────┐  ┌──────────┐
│ WebSocket │  │ yfinance │
│ (Primary) │  │ (Fallback)│
└───────────┘  └──────────┘
```

### Components

1. **`live_price_cache.py`** - WebSocket service that:
   - Connects to Kotak Neo WebSocket
   - Subscribes to open positions
   - Caches latest LTP in memory (thread-safe)
   - Auto-reconnects on disconnect

2. **`live_price_manager.py`** - High-level interface:
   - Manages WebSocket lifecycle
   - Provides `get_ltp(symbol)` API
   - Automatic fallback to yfinance
   - Usage statistics

3. **`position_monitor.py`** (Updated) - Now uses real-time LTP for:
   - Current price (instead of close price)
   - EMA9 calculation (with live price appended)
   - Exit condition detection

---

## Usage

### Basic (Automatic - Default)

Position monitor **automatically** uses real-time prices:

```bash
.\.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_position_monitor
```

### Disable Real-Time Prices (Use yfinance only)

If you want to use yfinance only (15-min delay):

```python
from modules.kotak_neo_auto_trader.position_monitor import get_position_monitor

monitor = get_position_monitor(
    history_path="data/trades_history.json",
    enable_alerts=True,
    enable_realtime_prices=False  # Disable WebSocket
)

results = monitor.monitor_all_positions()
```

### Standalone Price Manager

Use the price manager independently:

```python
from modules.kotak_neo_auto_trader.live_price_manager import LivePriceManager

# Initialize
manager = LivePriceManager(
    env_file="modules/kotak_neo_auto_trader/kotak_neo.env",
    enable_websocket=True,
    enable_yfinance_fallback=True
)

# Subscribe to positions
manager.subscribe_to_positions(["RELIANCE", "TCS", "HCLTECH"])

# Wait for connection
if manager.price_manager.wait_for_connection(timeout=10):
    print("Connected!")

# Get LTP
ltp = manager.get_ltp("RELIANCE", "RELIANCE.NS")
print(f"RELIANCE LTP: ₹{ltp}")

# Get all cached prices
all_prices = manager.get_all_ltps()
print(all_prices)  # {'RELIANCE': 2450.50, 'TCS': 3035.30, ...}

# Stats
manager.print_stats()

# Cleanup
manager.stop()
```

---

## Testing

Run the test script to verify integration:

```bash
.\.venv\Scripts\python.exe test_realtime_position_monitor.py
```

This will:
1. Load open positions from `data/trades_history.json`
2. Initialize position monitor with real-time prices
3. Subscribe to WebSocket for all positions
4. Run position monitoring
5. Show EMA9 calculated with live LTP
6. Display WebSocket vs yfinance usage stats

---

## How It Works

### Real-Time EMA9 Calculation

```python
# 1. Fetch historical data (yfinance)
df = fetch_ohlcv_yf(ticker, days=200)

# 2. Get real-time LTP (WebSocket)
current_price = price_manager.get_ltp(symbol)

# 3. Append current price to series
close_series = df['close'].copy()
close_series = pd.concat([close_series, pd.Series([current_price])])

# 4. Calculate EMA9 with latest price
ema9 = close_series.ewm(span=9).mean().iloc[-1]

# 5. Check exit conditions
if current_price >= ema9:
    # EXIT SIGNAL!
```

### Fallback Logic

```
Try: WebSocket LTP
 ├─ Success → Use WebSocket price
 └─ Failed/Unavailable
     └─ Try: yfinance
         ├─ Success → Use yfinance price
         └─ Failed → Log error, skip position
```

---

## Configuration

### WebSocket Settings

In `live_price_cache.py`:

```python
stale_threshold_seconds = 60  # Mark data stale after 60s
reconnect_delay_seconds = 5   # Wait 5s before reconnect
```

### Position Monitor Settings

In `position_monitor.py`:

```python
enable_realtime_prices = True  # Enable/disable WebSocket
```

---

## Limitations

1. **Market Hours Only**: WebSocket only works during market hours (9:15 AM - 3:30 PM)
   - Outside market hours: Falls back to yfinance

2. **Token Limit**: Max 3000 instruments subscribed simultaneously
   - Your use case: ~10-20 positions (well within limit)

3. **Connection Stability**: WebSocket can disconnect
   - Auto-reconnection handles this
   - Falls back to yfinance if reconnection fails

4. **Session Expiry**: Kotak Neo session expires after ~1 hour
   - Cached sessions help (valid until end-of-day)
   - May need re-authentication

---

## Monitoring

### Check WebSocket Status

```python
# Is WebSocket connected?
connected = monitor.price_manager.is_websocket_connected()

# Get statistics
stats = monitor.price_manager.get_stats()
print(stats)
```

### Sample Stats Output

```
======================================================================
LIVE PRICE MANAGER STATS
======================================================================
WebSocket Enabled: True
WebSocket Initialized: True
WebSocket Connected: True
yfinance Fallback Enabled: True

WebSocket Hits: 24
yfinance Fallbacks: 2
Errors: 0
Last WebSocket Fetch: 2025-10-30 15:22:45
Last yfinance Fallback: 2025-10-30 14:10:12

WebSocket Cache:
  Subscriptions: 8
  Cache Size: 8
  Messages Received: 156
  Updates Processed: 312
  Reconnections: 0
  Last Update: 2025-10-30 15:22:45
======================================================================
```

---

## Troubleshooting

### WebSocket Not Connecting

**Symptom**: Warnings like "WebSocket connection timeout"

**Solutions**:
1. Check if market is open (Mon-Fri 9:15 AM - 3:30 PM)
2. Verify Kotak Neo login credentials in `kotak_neo.env`
3. Check internet connection
4. Position monitor will fall back to yfinance automatically

### High yfinance Fallback Count

**Symptom**: `yfinance_fallbacks` > `websocket_hits` in stats

**Possible Causes**:
1. Market closed → Expected behavior
2. WebSocket disconnected → Check reconnection logs
3. Symbols not found in scrip master → Verify symbol names

### Stale Data Warnings

**Symptom**: "Stale data for SYMBOL (age: 65s)"

**Solutions**:
1. Check if market is open
2. Check WebSocket connection status
3. Increase `stale_threshold_seconds` if needed (default: 60s)

---

## Benefits

### Before (yfinance only)
- ❌ 15-minute data delay
- ❌ EMA9 calculated with outdated prices
- ❌ Exit signals delayed by 15+ minutes
- ❌ Potential slippage on exits

### After (Real-time WebSocket)
- ✅ Real-time price updates (tick-by-tick)
- ✅ EMA9 reflects current market conditions
- ✅ Exit signals trigger immediately
- ✅ Reduced slippage, better execution prices
- ✅ Automatic fallback if WebSocket unavailable

---

## Example Scenario

**Without Real-Time LTP:**
```
Market Time: 3:15 PM
Actual LTP: ₹2455 (crossed EMA9 at 3:12 PM)
yfinance Price: ₹2440 (delayed 15 min from 3:00 PM)
EMA9: ₹2450

Result: Exit signal NOT triggered (2440 < 2450)
Outcome: Missed exit, potential loss if price drops
```

**With Real-Time LTP:**
```
Market Time: 3:15 PM
WebSocket LTP: ₹2455 (live)
EMA9 (with live price): ₹2452

Result: Exit signal TRIGGERED (2455 > 2452)
Outcome: Immediate exit, preserved gains
```

---

## Summary

Real-time LTP integration provides:

1. **Accurate EMA9 calculation** with current market prices
2. **No 15-minute delay** on exit signals
3. **Automatic fallback** to yfinance when WebSocket unavailable
4. **Zero cost** - included with Kotak Neo account
5. **Production-ready** with auto-reconnection and error handling

**Recommended**: Keep `enable_realtime_prices=True` (default) for best results.

---

## Files Created/Modified

**New Files:**
- `modules/kotak_neo_auto_trader/live_price_cache.py` - WebSocket cache service
- `modules/kotak_neo_auto_trader/live_price_manager.py` - High-level price manager
- `test_realtime_position_monitor.py` - Integration test script
- `test_websocket_subscribe.py` - WebSocket demo script

**Modified Files:**
- `modules/kotak_neo_auto_trader/position_monitor.py` - Uses real-time LTP
- `modules/kotak_neo_auto_trader/run_position_monitor.py` - (No changes needed, uses factory function)

---

## Future Enhancements

Potential improvements:

1. **Redis cache** - Share LTP across multiple processes
2. **Historical tick storage** - Store tick data for backtesting
3. **Order book depth** - Use `isDepth=True` for better entry/exit timing
4. **Multiple exchanges** - Support BSE, NFO, MCX
5. **Price alerts** - Send alerts on specific price levels

---

**Questions?** Check logs in `logs/` directory for detailed WebSocket activity.
