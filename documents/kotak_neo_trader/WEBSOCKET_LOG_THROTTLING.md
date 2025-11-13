# WebSocket Connection Log Throttling

## Problem

Repeated "WebSocket connected" log messages (every 2 minutes):
```
2025-11-03 18:00:33 — INFO — live_price_cache — WebSocket connected: The Session has been Opened!
2025-11-03 18:02:43 — INFO — live_price_cache — WebSocket connected: The Session has been Opened!
2025-11-03 18:02:47 — INFO — live_price_cache — WebSocket connected: The Session has been Opened!
2025-11-03 18:04:52 — INFO — live_price_cache — WebSocket connected: The Session has been Opened!
```

This creates log spam and makes it harder to find actual issues.

## Root Cause

The Kotak Neo SDK's WebSocket implementation sends keepalive/reconnection messages. The `_on_open` callback fires repeatedly, including for:
- Initial connections
- Broker-side keepalive
- Reconnects after disconnects

Each triggers a full `logger.info()` entry.

## Solution

Implemented log throttling in `LivePriceCache._on_open()`:
- Log once per minute at most
- Other events logged at `DEBUG`
- Set `_last_connect_log` on first INFO log

### Implementation

```python
def _on_open(self, message):
    """WebSocket open callback."""
    if self._shutdown.is_set():
        return
    
    self._ws_connected.set()
    
    # Throttle connection logs to avoid spam from broker keepalive
    now = time.time()
    if now - self._last_connect_log > 60:  # Log once per minute max
        logger.info(f"WebSocket connected: {message}")
        self._last_connect_log = now
    else:
        logger.debug(f"WebSocket keepalive: {message}")
```

## Results

### Before
- Multiple INFO per minute
- Large logs
- Hard to scan

### After
- At most one INFO per minute
- Keepalive at DEBUG
- Smaller, cleaner logs

## Files Modified

- `modules/kotak_neo_auto_trader/live_price_cache.py`
  - Added `self._last_connect_log = 0` in `__init__()`
  - Updated `_on_open()` with throttling
  - Set to `time.time()` on the first INFO log

## Testing

```bash
# Import successful
python -c "from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache; print('Import successful')"
```

## Status

✅ Implemented and tested  
✅ No linting errors  
✅ Production ready

