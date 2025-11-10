# Indicator Calculation Flow Analysis

## Overview

This document explains how EMA/RSI indicators are calculated in the integrated backtest flow, specifically after BacktestEngine data is available.

---

## Current Flow

### Step 1: BacktestEngine Calculates Indicators

**File:** `backtest/backtest_engine.py`

**Method:** `_calculate_indicators()` (line 128)

```python
def _calculate_indicators(self):
    """Calculate technical indicators"""
    # Calculate RSI using pandas_ta default method (matches TradingView)
    self.data['RSI10'] = ta.rsi(self.data['Close'], length=self.config.RSI_PERIOD)
    
    # Calculate EMA200
    self.data['EMA200'] = ta.ema(self.data['Close'], length=self.config.EMA_PERIOD)
    
    # Drop NaN values
    self.data = self.data.dropna()
```

**Key Points:**
- Uses `pandas_ta` library (`ta.rsi()` and `ta.ema()`)
- Calculated **once** during `_load_data()` (line 105)
- Stored in `self.data['RSI10']` and `self.data['EMA200']`
- Data is filtered to backtest period **after** indicator calculation

**Calculation Method:**
- RSI: `pandas_ta.rsi()` - Uses pandas_ta's default RSI implementation
- EMA: `pandas_ta.ema()` - Uses pandas_ta's EMA implementation

---

### Step 2: Integrated Backtest Uses Pre-Calculated Indicators

**File:** `integrated_backtest.py`

**Method:** `run_backtest()` (line 48)

```python
engine = BacktestEngine(...)  # Indicators already calculated here

# Iterate through the data to identify buy signals
for current_date, row in engine.data.iterrows():
    # Uses pre-calculated indicators from BacktestEngine
    signal = {
        'signal_date': current_date,
        'execution_date': next_day, 
        'execution_price': execution_price,
        'reason': entry_reason,
        'rsi': row['RSI10'],        # ← Pre-calculated from BacktestEngine
        'close_price': row['Close'],
        'ema200': row['EMA200']     # ← Pre-calculated from BacktestEngine
    }
```

**Key Points:**
- Uses indicators **already calculated** by BacktestEngine
- No recalculation needed at this stage
- Values extracted directly from `engine.data` DataFrame

---

### Step 3: Trade Agent Recalculates Indicators (DUPLICATE)

**File:** `integrated_backtest.py`

**Method:** `trade_agent()` (line 117)

```python
def trade_agent(stock_name: str, buy_date: str) -> SignalResult:
    # Calls analyze_ticker which fetches data AGAIN
    analysis_result = analyze_ticker(
        stock_name,
        enable_multi_timeframe=True,
        export_to_csv=False,
        as_of_date=buy_date  # ← Fetches data again for this date
    )
```

**File:** `core/analysis.py` or `services/analysis_service.py`

**Method:** `analyze_ticker()` → `compute_indicators()` (line 433)

```python
# Fetch data AGAIN (duplicate fetch)
df = fetch_multi_timeframe_data(ticker, end_date=as_of_date, ...)

# Compute technical indicators AGAIN (different method!)
df = compute_indicators(df)
```

**File:** `core/indicators.py`

**Method:** `compute_indicators()` (line 23)

```python
def compute_indicators(df):
    # Use Wilder's RSI method (matches TradingView)
    df['rsi10'] = wilder_rsi(df[close_col], period=10)  # ← DIFFERENT METHOD!
    
    df['ema200'] = df[close_col].ewm(span=200).mean()  # ← DIFFERENT METHOD!
```

**Key Points:**
- **Fetches data again** (duplicate API call)
- **Recalculates indicators** using **different methods**:
  - RSI: `wilder_rsi()` (custom function) vs `pandas_ta.rsi()` 
  - EMA: `df.ewm().mean()` (pandas) vs `pandas_ta.ema()`
- This is part of the data duplication issue identified earlier

---

## Critical Issue: Inconsistent Calculation Methods

### Problem

**BacktestEngine** and **Trade Agent** use **different calculation methods**:

| Component | RSI Method | EMA Method | Library |
|-----------|------------|------------|---------|
| **BacktestEngine** | `pandas_ta.rsi()` | `pandas_ta.ema()` | pandas_ta |
| **Trade Agent** | `wilder_rsi()` (custom) | `df.ewm().mean()` | pandas |

### Impact

1. **Different RSI Values:**
   - `pandas_ta.rsi()` may use different smoothing/calculation than `wilder_rsi()`
   - Could lead to different signals between BacktestEngine and Trade Agent

2. **Different EMA Values:**
   - `pandas_ta.ema()` vs `df.ewm().mean()` may have slight differences
   - Could affect EMA200 comparison logic

3. **Data Duplication:**
   - Data fetched twice (BacktestEngine + Trade Agent)
   - Indicators calculated twice with different methods

---

## Proposed Solution

### Option 1: Reuse BacktestEngine Data (Recommended)

**Modify `trade_agent()` to accept pre-calculated data:**

```python
def trade_agent(
    stock_name: str, 
    buy_date: str,
    pre_fetched_data: Optional[pd.DataFrame] = None,
    pre_calculated_indicators: Optional[Dict] = None
) -> SignalResult:
    """
    Trade agent with optional pre-fetched data
    
    Args:
        pre_fetched_data: DataFrame with OHLCV data (from BacktestEngine)
        pre_calculated_indicators: Dict with rsi, ema200 values (from BacktestEngine)
    """
    if pre_fetched_data is not None and pre_calculated_indicators is not None:
        # Use pre-calculated indicators
        # Skip data fetching and indicator calculation
        # Use pre_fetched_data for analysis
    else:
        # Fallback to current behavior (fetch and calculate)
        analysis_result = analyze_ticker(...)
```

**Benefits:**
- Eliminates duplicate data fetching
- Uses same calculation method (BacktestEngine's pandas_ta)
- Consistent indicator values
- Better performance

---

### Option 2: Standardize Calculation Methods

**Make both use same method:**

**Option 2A:** Both use `pandas_ta`
```python
# Update core/indicators.py
def compute_indicators(df):
    import pandas_ta as ta
    df['rsi10'] = ta.rsi(df[close_col], length=10)
    df['ema200'] = ta.ema(df[close_col], length=200)
```

**Option 2B:** Both use `wilder_rsi()` + pandas EMA
```python
# Update BacktestEngine
def _calculate_indicators(self):
    from core.indicators import wilder_rsi
    self.data['RSI10'] = wilder_rsi(self.data['Close'], period=self.config.RSI_PERIOD)
    self.data['EMA200'] = self.data['Close'].ewm(span=self.config.EMA_PERIOD).mean()
```

**Benefits:**
- Consistent calculation methods
- Same indicator values regardless of path

---

## Impact on Configurable Indicators

### Current State

**BacktestEngine:**
- Uses `self.config.RSI_PERIOD` ✅ (configurable)
- Uses `self.config.EMA_PERIOD` ✅ (configurable)

**Trade Agent (`compute_indicators()`):**
- Uses hardcoded `period=10` ❌ (not configurable)
- Uses hardcoded `span=200` ❌ (not configurable)

### After Proposed Changes

**Both should use configurable parameters:**
- RSI period from `StrategyConfig.rsi_period`
- EMA period from `StrategyConfig.ema_period` (if exists) or default 200

---

## Recommendations

1. **Immediate:** Document the inconsistency in requirements document
2. **Short-term:** Implement Option 1 (reuse BacktestEngine data)
3. **Medium-term:** Standardize calculation methods (Option 2)
4. **Long-term:** Make all indicator calculations use configurable parameters

---

## Related Issues

- **Data Fetching Duplication:** See Section 12.6 in requirements document
- **Configurable Indicators:** See main requirements document
- **Backtest Impact:** See Section 12 in requirements document

---

**Last Updated:** 2025-01-XX
**Status:** Analysis Complete - Awaiting Implementation Decision
