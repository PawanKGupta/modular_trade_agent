# HTTP 401 Error Analysis - API Rate Limiting

## Problem Statement

**Issue**: Getting 31+ HTTP 401 errors during backtest run
**Error Type**: `HTTP Error 401: Unauthorized` / `Invalid Crumb`
**Impact**: ⚠️ Medium - API rate limiting, but system handles gracefully

## Root Cause Analysis

### API Call Pattern

#### Phase 1: Initial Analysis (20 stocks)
```
For each stock:
  1. fetch_ohlcv_yf() [daily]     ← API Call #1
  2. fetch_ohlcv_yf() [weekly]    ← API Call #2
  3. yf.Ticker().info [fundamental] ← API Call #3 (not protected by circuit breaker)

Total: 20 stocks × 3 calls = 60 API calls
```

#### Phase 2: Backtest Scoring (20 stocks)
```
For each stock:
  1. BacktestEngine._load_data()
     └─ fetch_ohlcv_yf() [daily] ← API Call #1 (with retries)

  2. For each signal (average 8-15 signals per stock):
     └─ trade_agent()
        └─ analyze_ticker()
           └─ fetch_multi_timeframe_data()
              ├─ fetch_ohlcv_yf() [daily] ← API Call #2a (if pre_fetched_daily not used)
              └─ fetch_ohlcv_yf() [weekly] ← API Call #2b (pre_fetched_weekly is None!)
           └─ yf.Ticker().info [fundamental] ← API Call #3 (not protected)

Total: 20 stocks × (1 + N signals × 2-3 calls) = 20 + (20 × 10 × 2.5) = ~520 API calls
```

### Issues Identified

#### Issue 1: Direct yf.download() Call Bypasses Circuit Breaker

**Location**: `integrated_backtest.py` line 358

**Problem**:
```python
# Fallback to fetching if BacktestEngine data not available
import yfinance as yf
market_data = yf.download(stock_name, start=start_date, end=end_date, progress=False)
```

**Impact**:
- ❌ Bypasses circuit breaker protection
- ❌ Bypasses retry handler
- ❌ No error handling
- ❌ Direct API call without protection

**Fix Required**: Use `fetch_ohlcv_yf()` instead of direct `yf.download()`

---

#### Issue 2: Fundamental Data Calls Not Protected

**Location**: `services/verdict_service.py` line 54

**Problem**:
```python
ticker_obj = yf.Ticker(ticker)
info = ticker_obj.info  # This makes an API call
```

**Impact**:
- ❌ Not protected by circuit breaker
- ❌ Not protected by retry handler
- ❌ Makes separate API call for each stock
- ❌ Can trigger rate limiting

**Fix Required**: Add circuit breaker and retry protection to fundamental data fetching

---

#### Issue 3: Weekly Data Fetched Again for Each Signal

**Location**: `integrated_backtest.py` line 190

**Problem**:
```python
pre_fetched_weekly = None  # Always None!
```

**Impact**:
- ❌ Weekly data is fetched again for each signal
- ❌ Even though BacktestEngine has the data
- ❌ Increases API calls significantly
- ❌ For 10 signals: 10 × 2 (daily + weekly) = 20 additional calls per stock

**Fix Required**: Pass weekly data from BacktestEngine if available

---

#### Issue 4: No Data Caching

**Problem**:
- Same data is fetched multiple times for the same stock
- No caching mechanism to reuse fetched data
- Each signal triggers new API calls

**Impact**:
- ❌ Excessive API calls
- ❌ Higher chance of rate limiting
- ❌ Slower execution

**Fix Required**: Implement data caching or better data reuse

---

## Impact Analysis

### Current Impact

1. **API Rate Limiting**: ⚠️ **HIGH**
   - 31+ HTTP 401 errors in single run
   - Circuit breaker opens after 3 failures
   - Subsequent requests fail fast

2. **Performance**: ⚠️ **MEDIUM**
   - Slower execution due to retries
   - Circuit breaker delays
   - Fallback to simple backtest

3. **Data Quality**: ✅ **LOW**
   - System handles failures gracefully
   - Falls back to simple backtest
   - Analysis continues with available data

4. **User Experience**: ⚠️ **MEDIUM**
   - Many error messages in logs
   - Slower execution
   - Some stocks may fail backtest

### Expected API Calls

**Current (Without Optimization)**:
- Initial analysis: 60 calls (20 stocks × 3)
- Backtest scoring: ~520 calls (20 stocks × 26 calls average)
- **Total: ~580 API calls**

**After Fixes**:
- Initial analysis: 60 calls (20 stocks × 3)
- Backtest scoring: ~40 calls (20 stocks × 2, reuse data)
- **Total: ~100 API calls** (82% reduction)

---

## Recommended Fixes

### Fix 1: Replace Direct yf.download() with fetch_ohlcv_yf()

**File**: `integrated_backtest.py` line 358

**Change**:
```python
# Before:
import yfinance as yf
market_data = yf.download(stock_name, start=start_date, end=end_date, progress=False)

# After:
from core.data_fetcher import fetch_ohlcv_yf
market_data = fetch_ohlcv_yf(
    ticker=stock_name,
    days=365,  # Adjust as needed
    interval='1d',
    end_date=end_date,
    add_current_day=False
)
# Convert to proper format (uppercase columns for BacktestEngine compatibility)
if market_data is not None:
    market_data = market_data.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })
    market_data = market_data.set_index('date')
```

**Impact**: ✅ Protects API call with circuit breaker and retry handler

---

### Fix 2: Add Circuit Breaker to Fundamental Data Fetching

**File**: `services/verdict_service.py` line 54

**Change**:
```python
# Add circuit breaker and retry protection
@yfinance_circuit_breaker
@api_retry_configured
def _fetch_fundamental_data_protected(ticker: str) -> Dict:
    """Fetch fundamental data with circuit breaker protection"""
    try:
        logger.debug(f"Fetching fundamental data for {ticker}")
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        # ... rest of the logic
    except Exception as e:
        # ... error handling
```

**Impact**: ✅ Protects fundamental data calls from rate limiting

---

### Fix 3: Pass Weekly Data from BacktestEngine

**File**: `integrated_backtest.py` line 190

**Change**:
```python
# Get weekly data from BacktestEngine if available
pre_fetched_weekly = None
if backtest_engine and hasattr(backtest_engine, '_full_data'):
    # Check if we have weekly data cached or can derive it
    # For now, weekly data might need to be fetched separately
    # But we can at least avoid fetching it for each signal
    pass  # TODO: Implement weekly data reuse
```

**Impact**: ✅ Reduces API calls for weekly data

---

### Fix 4: Implement Data Caching

**Option**: Add caching layer to `fetch_ohlcv_yf()`

**Implementation**:
```python
# Simple in-memory cache
_data_cache = {}
_cache_lock = threading.Lock()

def fetch_ohlcv_yf(ticker, days=365, interval='1d', end_date=None, add_current_day=True):
    # Create cache key
    cache_key = (ticker, days, interval, end_date, add_current_day)

    # Check cache
    with _cache_lock:
        if cache_key in _data_cache:
            logger.debug(f"Using cached data for {ticker}")
            return _data_cache[cache_key].copy()

    # Fetch data
    df = _fetch_ohlcv_yf_impl(ticker, days, interval, end_date, add_current_day)

    # Store in cache
    with _cache_lock:
        _data_cache[cache_key] = df.copy()

    return df
```

**Impact**: ✅ Reduces duplicate API calls significantly

---

## Impact Summary

### Before Fixes
- **API Calls**: ~580 calls per backtest run
- **401 Errors**: 31+ errors
- **Circuit Breaker**: Opens frequently
- **Performance**: Slow due to retries and delays

### After Fixes
- **API Calls**: ~100 calls per backtest run (82% reduction)
- **401 Errors**: Expected to reduce significantly
- **Circuit Breaker**: Less likely to open
- **Performance**: Faster execution

---

## Priority

### High Priority (Immediate)
1. ✅ **Fix 1**: Replace direct `yf.download()` with `fetch_ohlcv_yf()`
2. ✅ **Fix 2**: Add circuit breaker to fundamental data fetching

### Medium Priority (Short-term)
3. 💡 **Fix 3**: Pass weekly data from BacktestEngine
4. 💡 **Fix 4**: Implement data caching

---

## Testing

### Test Cases
1. **Single Stock Backtest**: Verify API calls are reduced
2. **Multiple Stocks Backtest**: Verify circuit breaker doesn't open
3. **Error Handling**: Verify graceful degradation when API fails
4. **Data Consistency**: Verify cached data is correct

---

## Conclusion

**Root Cause**: Excessive API calls due to:
1. Direct `yf.download()` calls bypassing protection
2. Unprotected fundamental data calls
3. Weekly data fetched multiple times
4. No data caching

**Impact**: ⚠️ **MEDIUM** - System handles gracefully but performance is affected

**Fix Priority**: **HIGH** - Should fix immediately to reduce API calls and improve performance

---

**Last Updated**: 2025-11-09
**Status**: ⚠️ Analysis Complete - Fixes Recommended
