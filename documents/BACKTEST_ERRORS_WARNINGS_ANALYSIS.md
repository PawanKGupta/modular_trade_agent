# Backtest Errors and Warnings Analysis

## Test Execution

**Command**: `python trade_agent.py --backtest`  
**Date**: 2025-11-09  
**Status**: ⚠️ Completed with errors and warnings

## Errors Found

### 1. ❌ ERROR: No Data Available After Indicator Calculation

**Error Message**:
```
Error loading data: No data available for HGM.NS after indicator calculation (all data dropped as NaN)
Error loading data: No data available for STALLION.NS after indicator calculation (all data dropped as NaN)
```

**Status**: ❌ **CRITICAL ERROR**  
**Frequency**: 2 stocks (HGM.NS, STALLION.NS)  
**Impact**: High - Backtest fails for these stocks

**Root Cause**:
- EMA200 requires 200 days of data to calculate
- After calculating indicators and dropping NaN values, all data is removed
- Stocks with very limited trading history (< 200 days) cannot have EMA200 calculated
- When all rows are dropped as NaN, no data remains for backtest

**Affected Stocks**:
- **HGM.NS**: Very limited trading history
- **STALLION.NS**: Very limited trading history (197 points fetched, but all dropped after EMA200 calculation)

**Current Behavior**:
- Backtest engine fails to load data
- Falls back to simple backtest
- Simple backtest may also fail if data is insufficient

**Recommendations**:

#### Option 1: Skip EMA200 for Stocks with Limited Data (Recommended)
```python
# In backtest_engine.py _calculate_indicators():
# Check if we have enough data for EMA200
if len(self.data) < 200:
    # Skip EMA200 calculation for stocks with limited data
    logger.warning(f"{self.symbol}: Insufficient data for EMA200 (need 200 days, have {len(self.data)} days) - skipping EMA200")
    # Calculate RSI only (needs only 10 days)
    # Continue without EMA200 - entry condition will be RSI < 30 only
else:
    # Calculate EMA200 normally
    self.data['EMA200'] = ta.ema(self.data['Close'], length=200)
```

#### Option 2: Use Shorter EMA for Limited Data
```python
# Use shorter EMA (e.g., EMA50) for stocks with limited data
if len(self.data) < 200:
    ema_period = min(200, len(self.data) - 10)  # Use available data minus buffer
    logger.info(f"{self.symbol}: Using EMA{ema_period} instead of EMA200 (limited data)")
    self.data['EMA200'] = ta.ema(self.data['Close'], length=ema_period)
```

#### Option 3: Filter Out Stocks with Insufficient Data
```python
# Skip backtest for stocks with insufficient data
if len(self.data) < 200:
    logger.warning(f"{self.symbol}: Insufficient data for backtest (need 200 days for EMA200, have {len(self.data)} days) - skipping")
    return None  # Skip this stock
```

**Recommended Solution**: **Option 1** - Skip EMA200 for stocks with limited data and continue with RSI-only analysis. This allows backtesting newer stocks while maintaining data quality for established stocks.

---

### 2. ❌ ERROR: Insufficient Backtest Period Data

**Error Message**:
```
Error loading data: Insufficient backtest period data: 17 days (need at least 20 days)
```

**Status**: ❌ **ERROR**  
**Frequency**: 1 stock (TRANSRAILL.NS)  
**Impact**: Medium - Backtest fails for this stock

**Root Cause**:
- After calculating indicators and filtering to backtest period, only 17 days remain
- Minimum requirement is 20 days for backtest period
- This happens when:
  - Stock has limited trading history
  - Backtest period starts very early (before stock was listed)
  - Data is filtered out after indicator calculation

**Affected Stocks**:
- **TRANSRAILL.NS**: Only 17 days of data in backtest period after indicator calculation

**Current Behavior**:
- Backtest engine fails to load data
- Falls back to simple backtest

**Recommendations**:

#### Option 1: Adjust Backtest Period Automatically
```python
# In backtest_engine.py _load_data():
# If backtest period has insufficient data, adjust the period
if len(backtest_period_data) < 20:
    # Find the actual date range with sufficient data
    # Adjust start_date to ensure at least 20 days
    actual_start = self.data.index[-20]  # Last 20 days
    backtest_period_data = self.data.loc[actual_start:self.end_date]
    logger.warning(f"{self.symbol}: Adjusted backtest period to ensure minimum 20 days")
```

#### Option 2: Reduce Minimum Requirement for Limited Data
```python
# Reduce minimum requirement for stocks with limited history
min_days = 20 if len(self.data) >= 100 else 10  # Lower threshold for newer stocks
if len(backtest_period_data) < min_days:
    # Handle accordingly
```

#### Option 3: Skip Backtest for Stocks with Insufficient Data
```python
# Skip backtest for stocks with insufficient data in backtest period
if len(backtest_period_data) < 20:
    logger.warning(f"{self.symbol}: Insufficient data in backtest period ({len(backtest_period_data)} days < 20 days) - skipping")
    return None  # Skip this stock
```

**Recommended Solution**: **Option 1** - Automatically adjust the backtest period to ensure minimum data requirements while maintaining data quality.

---

### 3. ❌ ERROR: NoneType Comparison in Priority Score

**Error Message**:
```
WARNING — scoring_service — Error computing priority score: '<=' not supported between instances of 'NoneType' and 'int'
```

**Status**: ❌ **ERROR** (Still occurring)  
**Frequency**: 1 stock (STALLION.NS)  
**Impact**: Medium - Priority score calculation fails

**Root Cause**:
- We fixed NoneType comparisons in `scoring_service.py`, but there's still a comparison happening
- Likely in a section we haven't covered yet
- STALLION.NS has chart quality failed, which may result in None values for some fields

**Current Behavior**:
- Priority score calculation fails
- Falls back to combined/strength score
- Analysis continues but without priority score

**Investigation Needed**:
- Check all comparison operations in `compute_trading_priority_score`
- Ensure all numeric fields are checked for None before comparison
- Check if chart quality failure results in None values that aren't handled

**Fix Required**: Add None checks for all numeric comparisons in priority score calculation.

---

## Warnings Found

### 1. ⚠️ WARNING: Feature Columns File Not Found

**Warning Message**:
```
WARNING — ml_verdict_service — Feature columns file not found. Will extract features dynamically.
```

**Status**: ✅ **Expected** (Informational)  
**Frequency**: Once per run  
**Impact**: None - Features are extracted dynamically  
**Action**: None required - This is normal behavior

---

### 2. ⚠️ WARNING: Could Not Fetch Fundamental Data

**Warning Message**:
```
WARNING — verdict_service — Could not fetch fundamental data for [TICKER]: API returned None (data may be unavailable for this ticker)
```

**Status**: ⚠️ **Expected** (Handled gracefully)  
**Frequency**: Multiple stocks  
**Impact**: Low - Analysis continues without fundamental data  
**Action**: None required - Already handled gracefully with improved error messages

**Affected Stocks**:
- KHAICHEM.NS
- MANORAMA.NS
- SWARAJENG.NS
- JSL.NS
- AIIL.NS
- TRANSRAILL.NS
- KAYNES.NS
- MAHSCOOTER.NS
- PGHL.NS
- SHREERAMA.NS

---

### 3. ⚠️ WARNING: Limited Data for Chart Quality

**Warning Message**:
```
WARNING — analysis_service — HGM.NS: Limited data for chart quality (51 days < 60 days) - assessing with available data
```

**Status**: ⚠️ **Expected** (Handled gracefully)  
**Frequency**: 1 stock (HGM.NS)  
**Impact**: Low - Chart quality assessed with available data  
**Action**: None required - Already handled gracefully

---

### 4. ⚠️ INFO: Weekly Data Below Ideal

**Info Message**:
```
INFO — data_fetcher — Weekly data for HGM.NS: 11 rows (minimum recommended: 20, but continuing with available data for dip-buying strategy)
INFO — data_fetcher — Weekly data for HGM.NS: 11 rows (below ideal 20, but usable for dip-buying strategy)
```

**Status**: ✅ **Expected** (Informational)  
**Frequency**: Stocks with limited weekly data  
**Impact**: None - System continues with available data  
**Action**: None required - This is the new flexible weekly data solution working correctly

---

### 5. ⚠️ INFO: Chart Quality Failed

**Info Message**:
```
INFO — analysis_service — STALLION.NS: Chart quality FAILED on data up to latest (197 days) - Too many gaps (31.7%) | Extreme candles (36.7%)
INFO — analysis_service — STALLION.NS: Chart quality FAILED (hard filter) - Too many gaps (31.7%) | Extreme candles (36.7%)
INFO — analysis_service — STALLION.NS: Returning 'avoid' verdict immediately (chart quality filter)
```

**Status**: ✅ **Expected** (Working correctly)  
**Frequency**: 1 stock (STALLION.NS)  
**Impact**: None - Chart quality filter working as expected  
**Action**: None required - This is correct behavior

---

### 6. ⚠️ HTTP Error 401: Unauthorized

**Error Message**:
```
HTTP Error 401: {"finance":{"result":null,"error":{"code":"Unauthorized","description":"User is unable to access this feature - https://bit.ly/yahoo-finance-api-feedback"}}}
HTTP Error 401: {"finance":{"result":null,"error":{"code":"Unauthorized","description":"Invalid Crumb"}}}
```

**Status**: ⚠️ **Expected** (API rate limiting)  
**Frequency**: Multiple occurrences  
**Impact**: Low - Circuit breaker handles this gracefully  
**Action**: None required - This is expected behavior for API rate limiting

---

## Summary

### Critical Errors (Need Fixing)

1. ❌ **No Data Available After Indicator Calculation** (HGM.NS, STALLION.NS)
   - **Priority**: HIGH
   - **Fix**: Skip EMA200 for stocks with limited data (< 200 days)
   - **Impact**: Allows backtesting newer stocks

2. ❌ **Insufficient Backtest Period Data** (TRANSRAILL.NS)
   - **Priority**: MEDIUM
   - **Fix**: Automatically adjust backtest period or reduce minimum requirement
   - **Impact**: Allows backtesting stocks with limited history

3. ❌ **NoneType Comparison in Priority Score** (STALLION.NS)
   - **Priority**: MEDIUM
   - **Fix**: Add None checks for all numeric comparisons
   - **Impact**: Prevents priority score calculation errors

### Expected Warnings (No Action Required)

1. ✅ Feature columns file not found (Informational)
2. ✅ Could not fetch fundamental data (Handled gracefully)
3. ✅ Limited data for chart quality (Handled gracefully)
4. ✅ Weekly data below ideal (New flexible solution working)
5. ✅ Chart quality failed (Working correctly)
6. ✅ HTTP Error 401 (API rate limiting - expected)

---

## Action Items

### Immediate Actions (High Priority)

1. **Fix EMA200 Calculation for Limited Data**:
   - Skip EMA200 for stocks with < 200 days of data
   - Continue with RSI-only analysis
   - Allow backtesting newer stocks

2. **Fix NoneType Comparison Error**:
   - Add None checks for all numeric comparisons in priority score
   - Ensure all fields are validated before comparison

### Short-term Actions (Medium Priority)

1. **Fix Insufficient Backtest Period Data**:
   - Automatically adjust backtest period for stocks with limited data
   - Or reduce minimum requirement for newer stocks

2. **Improve Error Handling**:
   - Add better error messages for data availability issues
   - Provide fallback options for stocks with limited data

### Long-term Actions (Low Priority)

1. **Data Quality Indicators**:
   - Add data quality indicators to analysis results
   - Help identify stocks with limited data

2. **Alternative Data Sources**:
   - Consider alternative data sources for stocks with limited YFinance data
   - Implement caching to reduce API calls

---

## Recommendations

### For Immediate Fix

**Priority 1**: Fix EMA200 calculation for limited data stocks
- This will allow backtesting newer stocks
- Maintains data quality for established stocks
- Minimal impact on existing functionality

**Priority 2**: Fix NoneType comparison error
- Prevents priority score calculation errors
- Improves system robustness
- Already partially fixed, need to complete

**Priority 3**: Fix insufficient backtest period data
- Allows backtesting stocks with limited history
- Improves system coverage
- Can be handled with automatic period adjustment

---

## Conclusion

**Overall Status**: ⚠️ **NEEDS FIXING**

**Key Issues**:
- 3 critical errors need fixing
- All errors are related to stocks with limited data
- System handles most cases gracefully but fails for very limited data stocks

**Next Steps**:
1. Fix EMA200 calculation for limited data stocks
2. Fix NoneType comparison error
3. Fix insufficient backtest period data
4. Test with various stocks to ensure fixes work

---

**Last Updated**: 2025-11-09  
**Status**: ⚠️ Analysis Complete - Fixes Required

