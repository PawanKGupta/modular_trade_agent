# Scrip Master Integration for Buy Orders

## Overview

The buy order engine (`auto_trade_engine.py`) now integrates with the Kotak Neo Scrip Master for accurate symbol resolution during AMO (After Market Order) placement.

## Changes Made

### 1. Import Scrip Master Module

```python
# modules/kotak_neo_auto_trader/auto_trade_engine.py
from .scrip_master import KotakNeoScripMaster
```

### 2. Initialize Scrip Master on Login

```python
def login(self) -> bool:
    ok = self.auth.login()
    if ok:
        self.orders = KotakNeoOrders(self.auth)
        self.portfolio = KotakNeoPortfolio(self.auth)
        
        # Initialize scrip master for symbol resolution
        try:
            self.scrip_master = KotakNeoScripMaster(
                auth_client=self.auth.client if hasattr(self.auth, 'client') else None
            )
            self.scrip_master.load_scrip_master(force_download=False)
            logger.info("Scrip master loaded for buy order symbol resolution")
        except Exception as e:
            logger.warning(f"Failed to load scrip master: {e}. Will use symbol fallback.")
            self.scrip_master = None
    return ok
```

### 3. Use Scrip Master in Order Placement

```python
# In place_amo_orders() method
# Try to resolve symbol using scrip master first
resolved_symbol = None
if self.scrip_master and self.scrip_master.symbol_map:
    # Try base symbol first
    instrument = self.scrip_master.get_instrument(broker_symbol)
    if instrument:
        resolved_symbol = instrument['symbol']
        logger.debug(f"Resolved {broker_symbol} -> {resolved_symbol} via scrip master")

# If scrip master resolved the symbol, use it directly
if resolved_symbol:
    place_symbol = resolved_symbol
    trial = self.orders.place_market_buy(
        symbol=place_symbol,
        quantity=qty,
        variety=config.DEFAULT_VARIETY,
        exchange=config.DEFAULT_EXCHANGE,
        product=config.DEFAULT_PRODUCT,
    )
    resp = trial if isinstance(trial, dict) and ('data' in trial or 'order' in trial) else None
    placed_symbol = place_symbol if resp else None

# Fallback: Try common series suffixes if scrip master didn't work
if not resp:
    series_suffixes = ["-EQ", "-BE", "-BL", "-BZ"]
    for suf in series_suffixes:
        # Try each suffix...
```

## Benefits

### 1. **Accurate Symbol Resolution**
- Uses official Kotak Neo instrument master
- Correct series suffix automatically determined
- Reduces order rejection due to invalid symbols

### 2. **Token Mapping**
- Access to instrument tokens for API calls
- Better integration with quote/market data APIs
- Enables advanced order types in future

### 3. **Fallback Mechanism**
- If scrip master fails to load: uses existing suffix-based fallback
- If symbol not found in scrip master: tries common suffixes
- Robust error handling ensures orders still placed

## Usage

### Automatic Usage

When you run the auto trade system normally, scrip master is automatically initialized:

```bash
python modules/kotak_neo_auto_trader/run_auto_trade.py
```

**Output:**
```
INFO — Authenticating with Kotak Neo...
INFO — ✅ Authentication successful
INFO — Scrip master loaded for buy order symbol resolution
INFO — Loaded 2000+ instruments for NSE from cache
```

### Manual Initialization

If creating AutoTradeEngine programmatically:

```python
from auto_trade_engine import AutoTradeEngine
from auth import KotakNeoAuth

# Create and login
auth = KotakNeoAuth('kotak_neo.env')
engine = AutoTradeEngine(auth=auth)

# Login automatically initializes scrip master
if engine.login():
    print(f"Scrip master loaded: {engine.scrip_master is not None}")
    print(f"Symbols available: {len(engine.scrip_master.symbol_map)}")
```

## Symbol Resolution Examples

### Without Scrip Master (Old Way)
```
RELIANCE -> Try: RELIANCE-EQ, RELIANCE-BE, RELIANCE-BL, RELIANCE-BZ
           -> First successful attempt is used
           -> May waste API calls on invalid suffixes
```

### With Scrip Master (New Way)
```
RELIANCE -> Scrip Master Lookup
           -> Found: RELIANCE-EQ (token: 2885)
           -> Place order directly with correct symbol
           -> Single API call, no guessing
```

## Caching

- Scrip master downloaded **once per day**
- Cached to `data/scrip_master/scrip_master_NSE_YYYYMMDD.json`
- Automatic refresh next trading day
- Force refresh: `scrip_master.load_scrip_master(force_download=True)`

## Configuration

No configuration required. Works out of the box with defaults:

```python
# Default settings
exchanges = ['NSE']  # Can extend to BSE, NFO, CDS
cache_dir = "data/scrip_master"
max_cache_age = 1 day (refreshes daily)
```

## Error Handling

### Scenario 1: Scrip Master Download Fails
```
WARNING — Failed to load scrip master: Request timeout
INFO — Will use symbol fallback
```
**Result:** System continues with existing suffix-based fallback

### Scenario 2: Symbol Not Found in Scrip Master
```
WARNING — Instrument not found: NEWSYMBOL (NSE)
INFO — Trying fallback suffixes for NEWSYMBOL
```
**Result:** Falls back to trying common suffixes

### Scenario 3: Network Issues
```
ERROR — Cannot fetch scrip master: Connection timeout
WARNING — Using cached scrip master from yesterday
```
**Result:** Uses yesterday's cache (still valid for most symbols)

## Integration with Sell Orders

Both buy and sell engines now use scrip master:

| Engine | Module | Scrip Master Usage |
|--------|--------|-------------------|
| **Buy** | `auto_trade_engine.py` | Resolve symbols for AMO placement |
| **Sell** | `sell_engine.py` | Resolve symbols for limit sell orders + LTP quotes |

## Testing

### Verify Scrip Master Loaded

```python
# Check if scrip master is active
if engine.scrip_master and engine.scrip_master.symbol_map:
    print(f"✅ Scrip master active with {len(engine.scrip_master.symbol_map)} symbols")
    
    # Test symbol lookup
    instrument = engine.scrip_master.get_instrument('RELIANCE')
    if instrument:
        print(f"RELIANCE resolved to: {instrument['symbol']}")
        print(f"Token: {instrument['token']}")
```

### Verify During Order Placement

Check logs during order placement:

```
DEBUG — Resolved RELIANCE -> RELIANCE-EQ via scrip master
INFO — Order placed for RELIANCE-EQ
```

## Troubleshooting

### Issue: "Scrip master not loading"
**Check:**
1. Network connectivity
2. Kotak Neo authentication successful
3. Cache directory permissions (`data/scrip_master/`)

### Issue: "Symbol still using fallback"
**Possible causes:**
1. Symbol not in NSE scrip master
2. Symbol name mismatch (check exact spelling)
3. Scrip master failed to load (check logs)

### Issue: "Orders rejected after scrip master integration"
**Solution:**
1. Check if symbol exists: `engine.scrip_master.search_instruments('SYMBOL')`
2. Verify exchange segment (NSE vs BSE)
3. Check order logs for exact rejection reason

## Future Enhancements

- [ ] Support for BSE, NFO, CDS segments
- [ ] Real-time scrip master updates via API
- [ ] Symbol search and suggestion
- [ ] Integration with order modification
- [ ] Advanced order types (bracket, cover)

## Related Documentation

- **Scrip Master Module:** `scrip_master.py`
- **Sell Orders with Scrip Master:** `PARALLEL_MONITORING.md`
- **Main Auto Trade Docs:** `README.md`
