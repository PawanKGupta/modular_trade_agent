# HTTP 401 Error - Root Cause and Impact Analysis

## Executive Summary

**Issue**: 31+ HTTP 401 errors during backtest run  
**Root Cause**: Excessive API calls due to unprotected API calls and duplicate data fetching  
**Impact**: ⚠️ **MEDIUM** - API rate limiting, but system handles gracefully with circuit breaker

---

## API Call Analysis

### Current API Call Pattern

#### Phase 1: Initial Analysis (20 stocks)
```
For each stock:
  1. fetch_ohlcv_yf() [daily]        ← Protected (circuit breaker + retry)
  2. fetch_ohlcv_yf() [weekly]       ← Protected (circuit breaker + retry)
  3. yf.Ticker().info [fundamental]  ← ❌ NOT PROTECTED (no circuit breaker, no retry)

Total: 20 stocks × 3 calls = 60 API calls
```

#### Phase 2: Backtest Scoring (20 stocks)
```
For each stock:
  
  Step 1: BacktestEngine._load_data()
    └─ fetch_multi_timeframe_data()
       ├─ fetch_ohlcv_yf() [daily]  ← API Call #1 (protected)
       └─ fetch_ohlcv_yf() [weekly] ← API Call #2 (protected, but data discarded!)
  
  Step 2: For each signal (average 8-15 signals per stock):
    └─ trade_agent()
       └─ analyze_ticker()
          └─ fetch_multi_timeframe_data() [if pre_fetched_daily not used properly]
             ├─ fetch_ohlcv_yf() [daily]  ← API Call #3a (should be avoided)
             └─ fetch_ohlcv_yf() [weekly] ← API Call #3b (ALWAYS fetched - pre_fetched_weekly is None!)
          └─ yf.Ticker().info [fundamental] ← API Call #4 (❌ NOT PROTECTED, called for each signal!)

Total per stock: 1 + 1 + (N signals × 3) = 2 + (N × 3) calls
Total for 20 stocks: 20 × (2 + 10 × 3) = 20 × 32 = 640 API calls
```

### Issues Identified

#### Issue 1: ❌ Direct yf.download() Bypasses Protection

**Location**: `integrated_backtest.py` line 358

**Code**:
```python
# Fallback to fetching if BacktestEngine data not available
import yfinance as yf
market_data = yf.download(stock_name, start=start_date, end=end_date, progress=False)
```

**Problems**:
- ❌ Bypasses circuit breaker (`@yfinance_circuit_breaker`)
- ❌ Bypasses retry handler (`@api_retry_configured`)
- ❌ No error handling
- ❌ Direct API call without protection
- ❌ Can trigger rate limiting

**Impact**: ⚠️ **HIGH** - Unprotected API calls can cause rate limiting

---

#### Issue 2: ❌ Fundamental Data Calls Not Protected

**Location**: `services/verdict_service.py` line 54

**Code**:
```python
ticker_obj = yf.Ticker(ticker)
info = ticker_obj.info  # This makes an API call
```

**Problems**:
- ❌ Not protected by circuit breaker
- ❌ Not protected by retry handler
- ❌ Makes separate API call for each stock
- ❌ Called again for each signal in backtest (not cached)
- ❌ Can trigger rate limiting

**Impact**: ⚠️ **HIGH** - Unprotected API calls, called multiple times per stock

**Frequency**:
- Initial analysis: 20 calls (1 per stock)
- Backtest scoring: 20 stocks × 10 signals = 200 calls (1 per signal)
- **Total: 220 fundamental data API calls**

---

#### Issue 3: ❌ Weekly Data Fetched Multiple Times

**Location**: `integrated_backtest.py` line 190

**Code**:
```python
pre_fetched_weekly = None  # Always None!
```

**Problems**:
- ❌ Weekly data is fetched in BacktestEngine but discarded
- ❌ Weekly data is fetched again for each signal
- ❌ `pre_fetched_weekly` is always None, so weekly data is always fetched
- ❌ No reuse of weekly data from BacktestEngine

**Impact**: ⚠️ **HIGH** - Excessive API calls for weekly data

**Frequency**:
- BacktestEngine: 20 calls (1 per stock, but data discarded)
- Per signal: 20 stocks × 10 signals = 200 calls
- **Total: 220 weekly data API calls (200 unnecessary)**

---

#### Issue 4: ❌ No Data Caching

**Problems**:
- ❌ Same data fetched multiple times for the same stock
- ❌ No caching mechanism to reuse fetched data
- ❌ Each signal triggers new API calls
- ❌ Fundamental data fetched for each signal (not cached)

**Impact**: ⚠️ **MEDIUM** - Excessive API calls, slower execution

---

## Impact Analysis

### Current Impact

#### 1. API Rate Limiting ⚠️ **HIGH**

**Symptoms**:
- 31+ HTTP 401 errors in single run
- Circuit breaker opens after 3 failures
- Subsequent requests fail fast
- System falls back to simple backtest

**Root Cause**:
- Excessive API calls (~640 calls for 20 stocks)
- Unprotected API calls (fundamental data)
- Duplicate data fetching (weekly data)

**Impact**:
- ⚠️ API rate limiting triggers
- ⚠️ Circuit breaker opens frequently
- ⚠️ Some stocks fail backtest
- ⚠️ Performance degradation

---

#### 2. Performance ⚠️ **MEDIUM**

**Symptoms**:
- Slower execution due to retries
- Circuit breaker delays (60 seconds)
- Fallback to simple backtest
- Multiple API calls per stock

**Impact**:
- ⚠️ Backtest takes longer to complete
- ⚠️ Retries add delays
- ⚠️ Circuit breaker adds 60-second delays

---

#### 3. Data Quality ✅ **LOW**

**Symptoms**:
- System handles failures gracefully
- Falls back to simple backtest
- Analysis continues with available data

**Impact**:
- ✅ No critical data loss
- ✅ System continues to work
- ✅ Graceful degradation

---

#### 4. User Experience ⚠️ **MEDIUM**

**Symptoms**:
- Many error messages in logs
- Slower execution
- Some stocks may fail backtest

**Impact**:
- ⚠️ Logs are noisy
- ⚠️ Slower execution
- ⚠️ Some stocks may not be analyzed

---

## API Call Count Breakdown

### Current (Without Optimization)

**Initial Analysis**:
- Daily data: 20 stocks × 1 = 20 calls
- Weekly data: 20 stocks × 1 = 20 calls
- Fundamental data: 20 stocks × 1 = 20 calls (unprotected)
- **Subtotal: 60 calls**

**Backtest Scoring**:
- BacktestEngine daily: 20 stocks × 1 = 20 calls
- BacktestEngine weekly: 20 stocks × 1 = 20 calls (discarded)
- Per signal daily: 20 stocks × 10 signals × 1 = 200 calls (should be 0 with pre_fetched)
- Per signal weekly: 20 stocks × 10 signals × 1 = 200 calls (unnecessary)
- Per signal fundamental: 20 stocks × 10 signals × 1 = 200 calls (unprotected, unnecessary)
- **Subtotal: 640 calls**

**Total: 700 API calls** (for 20 stocks with ~10 signals each)

---

### Expected After Fixes

**Initial Analysis**:
- Daily data: 20 stocks × 1 = 20 calls
- Weekly data: 20 stocks × 1 = 20 calls
- Fundamental data: 20 stocks × 1 = 20 calls (protected)
- **Subtotal: 60 calls**

**Backtest Scoring**:
- BacktestEngine daily: 20 stocks × 1 = 20 calls
- BacktestEngine weekly: 20 stocks × 1 = 20 calls (reused)
- Per signal daily: 0 calls (reused from BacktestEngine)
- Per signal weekly: 0 calls (reused from BacktestEngine)
- Per signal fundamental: 0 calls (cached from initial analysis)
- **Subtotal: 40 calls**

**Total: 100 API calls** (86% reduction)

---

## Recommended Fixes

### Fix 1: Replace Direct yf.download() with fetch_ohlcv_yf() ⚠️ **HIGH PRIORITY**

**File**: `integrated_backtest.py` line 358

**Change**:
```python
# Before:
import yfinance as yf
market_data = yf.download(stock_name, start=start_date, end=end_date, progress=False)

# After:
from core.data_fetcher import fetch_ohlcv_yf
try:
    # Calculate days needed
    days_needed = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 365
    market_data_df = fetch_ohlcv_yf(
        ticker=stock_name,
        days=days_needed,
        interval='1d',
        end_date=end_date,
        add_current_day=False
    )
    if market_data_df is not None:
        # Convert to BacktestEngine format (uppercase columns, date index)
        market_data = market_data_df.set_index('date')
        market_data = market_data.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
    else:
        raise ValueError(f"Failed to fetch market data for {stock_name}")
except Exception as e:
    logger.error(f"Failed to fetch market data for {stock_name}: {e}")
    raise
```

**Impact**: ✅ Protects API call with circuit breaker and retry handler

---

### Fix 2: Add Circuit Breaker to Fundamental Data Fetching ⚠️ **HIGH PRIORITY**

**File**: `services/verdict_service.py` line 52

**Change**:
```python
# Import circuit breaker and retry handler
from utils.circuit_breaker import CircuitBreaker
from utils.retry_handler import api_retry_configured

# Create circuit breaker for fundamental data (same as OHLCV data)
yfinance_fundamental_circuit_breaker = CircuitBreaker(
    name="YFinance_Fundamental_API",
    failure_threshold=3,  # Same as OHLCV
    recovery_timeout=60.0  # Same as OHLCV
)

@yfinance_fundamental_circuit_breaker
@api_retry_configured
def _fetch_fundamental_data_protected(ticker: str) -> Dict:
    """Fetch fundamental data with circuit breaker and retry protection"""
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

### Fix 3: Cache Fundamental Data ⚠️ **MEDIUM PRIORITY**

**File**: `services/verdict_service.py`

**Change**:
```python
# Add in-memory cache for fundamental data
_fundamental_cache = {}
_cache_lock = threading.Lock()

def _fetch_fundamental_data_protected(ticker: str) -> Dict:
    # Check cache first
    with _cache_lock:
        if ticker in _fundamental_cache:
            logger.debug(f"Using cached fundamental data for {ticker}")
            return _fundamental_cache[ticker].copy()
    
    # Fetch data
    data = _fetch_fundamental_data_impl(ticker)
    
    # Store in cache
    with _cache_lock:
        _fundamental_cache[ticker] = data.copy()
    
    return data
```

**Impact**: ✅ Reduces duplicate fundamental data calls

---

### Fix 4: Reuse Weekly Data from BacktestEngine ⚠️ **MEDIUM PRIORITY**

**File**: `integrated_backtest.py` line 190

**Change**:
```python
# Get weekly data from BacktestEngine if available
pre_fetched_weekly = None
if backtest_engine:
    # Check if BacktestEngine has weekly data (it fetches it but discards it)
    # We need to store weekly data in BacktestEngine for reuse
    if hasattr(backtest_engine, '_weekly_data') and backtest_engine._weekly_data is not None:
        pre_fetched_weekly = backtest_engine._weekly_data.copy()
        # Convert to lowercase for compatibility
        if 'Close' in pre_fetched_weekly.columns:
            pre_fetched_weekly = pre_fetched_weekly.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
```

**Also need to modify BacktestEngine**:
```python
# In backtest_engine.py _load_data():
# Store weekly data for reuse
if multi_data.get('weekly') is not None:
    self._weekly_data = multi_data['weekly'].copy()
```

**Impact**: ✅ Reduces weekly data API calls significantly

---

## Impact Summary

### Before Fixes
- **API Calls**: ~700 calls per backtest run
- **401 Errors**: 31+ errors
- **Circuit Breaker**: Opens frequently
- **Performance**: Slow due to retries and delays
- **Unprotected Calls**: 220 calls (fundamental data)

### After Fixes
- **API Calls**: ~100 calls per backtest run (86% reduction)
- **401 Errors**: Expected to reduce to < 5 errors
- **Circuit Breaker**: Less likely to open
- **Performance**: Faster execution
- **Unprotected Calls**: 0 calls (all protected)

---

## Priority

### High Priority (Immediate)
1. ✅ **Fix 1**: Replace direct `yf.download()` with `fetch_ohlcv_yf()`
2. ✅ **Fix 2**: Add circuit breaker to fundamental data fetching

### Medium Priority (Short-term)
3. 💡 **Fix 3**: Cache fundamental data
4. 💡 **Fix 4**: Reuse weekly data from BacktestEngine

---

## Testing

### Test Cases
1. **Single Stock Backtest**: Verify API calls are reduced
2. **Multiple Stocks Backtest**: Verify circuit breaker doesn't open
3. **Error Handling**: Verify graceful degradation when API fails
4. **Data Consistency**: Verify cached/reused data is correct

---

## Conclusion

**Root Cause**: Excessive API calls due to:
1. Direct `yf.download()` calls bypassing protection
2. Unprotected fundamental data calls
3. Weekly data fetched multiple times
4. No data caching

**Impact**: ⚠️ **MEDIUM** - System handles gracefully but performance is affected

**Fix Priority**: **HIGH** - Should fix immediately to reduce API calls and improve performance

**Expected Improvement**: 86% reduction in API calls (700 → 100 calls)

---

**Last Updated**: 2025-11-09  
**Status**: ⚠️ Analysis Complete - Fixes Recommended
