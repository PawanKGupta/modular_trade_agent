# YFinance Stale Data Fix - Real-Time WebSocket Prices

**Date**: October 31, 2025
**Issue**: Sell order monitoring using 15-20 minute delayed yfinance prices instead of real-time data
**Status**: ✅ **FIXED**

## Problem

The sell order monitoring system was using yfinance to fetch LTP (Last Traded Price) data, which has a significant delay:

- **yfinance LTP for DALBHARAT**: ₹2096.90 (delayed ~15-20 minutes)
- **Actual current price**: ₹2103.50
- **Difference**: ₹6.60 delay

This caused inaccurate EMA9 calculations and prevented optimal exit pricing.

### Root Cause

```python
# Old implementation in sell_engine.py (line 217-240)
def get_current_ltp(self, ticker: str, broker_symbol: str = None):
    # Used yfinance directly - 15-20 minute delay
    df = fetch_ohlcv_yf(ticker, days=1, interval='1m', add_current_day=True)
    ltp = float(df['close'].iloc[-1])  # Last 1m candle close - DELAYED!
    return ltp
```

## Solution

Integrated **LivePriceCache** (WebSocket-based real-time prices) into the sell order monitoring system:

### 1. Updated `sell_engine.py`

Added optional `price_manager` parameter and WebSocket-first LTP fetching:

```python
class SellOrderManager:
    def __init__(self, auth, history_path=None, max_workers=10, price_manager=None):
        self.price_manager = price_manager  # NEW: Optional LivePriceManager
        # ... rest of init
```

```python
def get_current_ltp(self, ticker: str, broker_symbol: str = None):
    base_symbol = ticker.replace('.NS', '').upper()

    # Try LivePriceManager first (real-time WebSocket prices)
    if self.price_manager:
        try:
            ltp = self.price_manager.get_ltp(base_symbol, ticker)
            if ltp is not None:
                logger.info(f"➡️ {base_symbol} LTP from WebSocket: ₹{ltp:.2f}")
                return ltp
        except Exception as e:
            logger.debug(f"WebSocket LTP failed for {base_symbol}: {e}")

    # Fallback to yfinance (delayed ~15-20 min)
    df = fetch_ohlcv_yf(ticker, days=1, interval='1m', add_current_day=True)
    ltp = float(df['close'].iloc[-1])
    logger.info(f"➡️ {base_symbol} LTP from yfinance (delayed ~15min): ₹{ltp:.2f}")
    return ltp
```

### 2. Updated `run_sell_orders.py`

Initialize `LivePriceManager` and pass it to `SellOrderManager`:

```python
# Initialize LivePriceManager for real-time WebSocket prices
price_manager = None
try:
    logger.info("Initializing LivePriceManager for real-time prices...")

    # Get open orders to extract symbols
    from .orders import KotakNeoOrders
    orders_api = KotakNeoOrders(auth)
    orders_response = orders_api.get_orders()

    # Extract symbols from open sell orders
    symbols = []
    if orders_response and 'data' in orders_response:
        for order in orders_response['data']:
            status = (order.get('orderStatus') or order.get('ordSt') or '').lower()
            txn_type = (order.get('transactionType') or order.get('trnsTp') or '').upper()
            broker_symbol = (order.get('tradingSymbol') or order.get('trdSym') or '').replace('-EQ', '')

            if status == 'open' and txn_type == 'S' and broker_symbol:
                if broker_symbol not in symbols:
                    symbols.append(broker_symbol)

    if symbols:
        # Initialize scrip_master and load data
        scrip_master = KotakNeoScripMaster(exchanges=['NSE'], auth_client=auth.get_client())
        scrip_master.load_scrip_master()

        # Initialize LivePriceCache
        price_cache = LivePriceCache(auth_client=auth, scrip_master=scrip_master)

        # Initialize and start LivePriceManager
        price_manager = LivePriceManager(price_cache, symbols)
        price_manager.start()

        logger.info(f"✅ LivePriceManager started for {len(symbols)} symbols: {', '.join(symbols)}")
        time.sleep(2)  # Give it time to connect

except Exception as e:
    logger.warning(f"Failed to initialize LivePriceManager: {e}")
    logger.info("Will fallback to yfinance for price data")

# Initialize sell order manager WITH price_manager
sell_manager = SellOrderManager(auth, price_manager=price_manager)
```

## Results

### Before Fix (yfinance)
```
➡️ DALBHARAT LTP from yfinance (delayed ~15min): ₹2096.90
📈 DALBHARAT: LTP=₹2096.90, Yesterday EMA9=₹2139.59 → Current EMA9=₹2131.05
📊 DALBHARAT: Current EMA9=₹2131.10, Target=₹2131.10, Lowest=₹2131.10
```

### After Fix (WebSocket)
```
➡️ DALBHARAT LTP from WebSocket: ₹2102.00  ✅ REAL-TIME!
📈 DALBHARAT: LTP=₹2102.00, Yesterday EMA9=₹2139.59 → Current EMA9=₹2131.55
📊 DALBHARAT: Current EMA9=₹2131.55, Target=₹2131.10, Lowest=₹2131.10
```

**Price Difference**:
- Old (yfinance): ₹2096.90
- New (WebSocket): ₹2102.00
- **Improvement**: ₹5.10 more accurate (closer to actual ₹2103.50)

## Technical Details

### Architecture

```
run_sell_orders.py
  ├─ Initialize LivePriceManager (WebSocket)
  │   ├─ KotakNeoScripMaster (symbol resolution)
  │   ├─ LivePriceCache (WebSocket connection)
  │   └─ Symbols from active sell orders
  │
  └─ SellOrderManager(price_manager=LivePriceManager)
       └─ get_current_ltp()
            ├─ Try: price_manager.get_ltp() → WebSocket (real-time) ✅
            └─ Fallback: yfinance (15-20 min delay)
```

### Dependencies

- `live_price_cache.py`: WebSocket connection to broker
- `live_price_manager.py`: High-level price manager
- `scrip_master.py`: Symbol resolution for broker
- `orders.py`: Fetch active sell orders for symbol list

### Fallback Strategy

The system gracefully falls back to yfinance if:
1. LivePriceManager initialization fails
2. WebSocket connection drops
3. Symbol not found in LivePriceCache

This ensures monitoring continues even if real-time prices are unavailable.

## Files Modified

1. **`sell_engine.py`**
   - Added `price_manager` parameter to `__init__`
   - Updated `get_current_ltp()` to try WebSocket first
   - Added logging to show LTP data source

2. **`run_sell_orders.py`**
   - Added LivePriceManager initialization
   - Extract symbols from active sell orders
   - Pass price_manager to SellOrderManager

## Testing

```bash
# Start sell monitoring with real-time prices
.\.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_sell_orders \
  --env modules\kotak_neo_auto_trader\kotak_neo.env \
  --monitor-interval 60 \
  --skip-wait
```

**Expected Output**:
```
Initializing LivePriceManager for real-time prices...
✅ LivePriceManager started for 2 symbols: DALBHARAT, GALLANTT
➡️ DALBHARAT LTP from WebSocket: ₹2102.00  # ← REAL-TIME!
➡️ GALLANTT LTP from WebSocket: ₹524.60    # ← REAL-TIME!
```

## Benefits

1. **Real-Time Prices**: WebSocket provides prices within 1-2 seconds of market updates
2. **Accurate EMA9**: Using current prices instead of 15-20 minute old data
3. **Better Exit Timing**: Orders modified based on real-time market movements
4. **Reliable Fallback**: Still works if WebSocket fails (uses yfinance)
5. **Explicit Logging**: Shows data source (WebSocket vs yfinance) for debugging

## Next Steps

- ✅ Monitor for 1-2 trading days to verify stability
- ✅ Verify EMA9 target updates happen more frequently
- ✅ Check if sell orders execute at better prices
- ⏹️ Consider adding reconnection logic if WebSocket drops

## Related Documentation

- `LIVE_PRICE_CACHE_MIGRATION.md`: Migration guide for all LTP usage
- `SELL_ORDER_MONITORING_FIX.md`: Overall monitoring system fixes
- `BUG_FIXES.md`: Bug #3 - Sell order update logic
