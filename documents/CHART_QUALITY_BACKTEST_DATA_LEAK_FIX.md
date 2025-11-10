# Chart Quality Backtest Data Leak Fix

## Critical Bug: Future Data Leak in Backtesting

### Issue

**Question**: Are we using latest 60 days candle to decide chart quality in backtest or before the date when signal was generated?

**Answer**: ❌ **BUG FOUND** - We were using **future data** (latest 60 days from backtest end date) instead of last 60 days **before the signal date**.

### Root Cause

**The Problem**:
1. Chart quality service uses `df.tail(60)` which gets the **LAST 60 rows** from the dataframe
2. In backtesting, when analyzing a signal from 2021-11-22:
   - Full data might span 2020-2025 (5 years)
   - Chart quality was assessed on **full data** (2020-2025)
   - Then `.tail(60)` gets last 60 days from **2025** (FUTURE DATA!)
   - But we should use last 60 days **before 2021-11-22** (signal date)

**Why This is a Critical Bug**:
- **Data Leak**: Using future data (2025) to decide chart quality for a signal in 2021
- **Invalid Backtest**: Backtest results are biased/incorrect
- **Unrealistic**: In real trading, you can't see future data

### The Fix

**Solution**: Clip data to signal date **FIRST**, then assess chart quality.

**Before (BUG)**:
```python
# Step 2: Assess chart quality on FULL data (2020-2025)
chart_quality_data = assess_chart_quality(df)  # Uses .tail(60) = last 60 days from 2025 ❌

# Step 3: Clip to signal date (2021-11-22)
df = clip_to_date(df, "2021-11-22")
```

**After (FIXED)**:
```python
# Step 2: Clip to signal date FIRST (2021-11-22)
df_clipped = clip_to_date(df, "2021-11-22")  # Data up to 2021-11-22 only

# Step 3: Assess chart quality on CLIPPED data
chart_quality_data = assess_chart_quality(df_clipped)  # Uses .tail(60) = last 60 days BEFORE 2021-11-22 ✅
```

### Code Changes

**File**: `services/analysis_service.py`

**Key Changes**:
1. **Clip data FIRST** (before chart quality assessment) when `as_of_date` is provided
2. **Assess chart quality** on clipped data (last 60 days BEFORE signal date)
3. **Use same clipped data** for analysis (consistent)

**Implementation**:
```python
# Step 2: Clip to as_of_date FIRST (CRITICAL for backtesting - prevents future data leak)
if as_of_date:
    df_for_chart_quality = self.data_service.clip_to_date(df.copy(), as_of_date)
    logger.debug(f"Clipped data to {as_of_date} BEFORE chart quality assessment (prevents future data leak)")

# Step 3: Check chart quality on data up to as_of_date (last 60 days BEFORE signal date)
chart_quality_data = self.verdict_service.assess_chart_quality(df_for_chart_quality)
```

### Example

**Scenario**: Backtesting signal from 2021-11-22

**Data Available**:
- Full data: 2020-01-01 to 2025-11-09 (5 years)
- Signal date: 2021-11-22
- Chart quality needs: Last 60 days

**Before Fix (BUG)**:
1. Assess chart quality on full data (2020-2025)
2. `.tail(60)` gets: **2025-09-11 to 2025-11-09** (FUTURE DATA!) ❌
3. Uses future data to decide chart quality for 2021 signal

**After Fix (CORRECT)**:
1. Clip data to 2021-11-22 first
2. Clipped data: 2020-01-01 to 2021-11-22
3. Assess chart quality on clipped data
4. `.tail(60)` gets: **2021-09-23 to 2021-11-22** (LAST 60 DAYS BEFORE SIGNAL) ✅
5. Uses only historical data (correct for backtesting)

### Impact

**Before Fix**:
- ❌ Future data leak (using data from 2025 to decide chart quality for 2021 signal)
- ❌ Invalid backtest results
- ❌ Unrealistic trading simulation

**After Fix**:
- ✅ No future data leak (using only data before signal date)
- ✅ Valid backtest results
- ✅ Realistic trading simulation

### Verification

**To verify the fix**:
1. Run backtest validation test:
   ```bash
   python tests/integration/test_backtest_verdict_validation.py --symbol RELIANCE.NS --years 2
   ```

2. Check logs for:
   - "Clipped data to {date} BEFORE chart quality assessment"
   - "Chart quality FAILED on data up to {date}"

3. Verify chart quality uses last 60 days **before** signal date, not after

### Related Issues

- **Issue**: Future data leak in chart quality assessment during backtesting
- **Fix**: Clip data to signal date BEFORE chart quality assessment
- **Impact**: Critical - affects backtest validity
- **Status**: ✅ FIXED

### Notes

1. **Live Trading**: When `as_of_date` is None (live trading), we use full data (correct - no clipping needed)

2. **Chart Quality Service**: The service uses `.tail(60)` which gets last 60 rows. By clipping data first, we ensure `.tail(60)` gets last 60 days **before** signal date.

3. **Consistency**: Chart quality and analysis now use the same clipped data, ensuring consistency.

4. **Performance**: No performance impact - clipping is fast and happens once.

### Summary

**Question**: Are we using latest 60 days candle to decide chart quality in backtest or before the date when signal was generated?

**Answer**: ✅ **FIXED** - We now use last 60 days **BEFORE the signal date** (correct for backtesting).

**Fix**: Clip data to signal date **FIRST**, then assess chart quality on clipped data.

**Status**: ✅ **FIXED** - No more future data leak in backtesting.




