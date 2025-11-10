# Flexible Weekly Data Solution for Dip-Buying Strategy

## Problem

**Issue**: Most stocks get "insufficient data for 1wk" warnings because the system requires 50 rows of weekly data, which many newer stocks don't have.

**Impact**: 
- Analysis fails or degrades for stocks with limited trading history
- Many valid dip-buying opportunities are missed
- Unnecessary errors and warnings in logs

## Solution: Flexible Weekly Data Requirements

### Strategy Rationale

For a **dip-buying strategy**:
- **Daily timeframe is PRIMARY**: Used for entry signals (RSI < 30, EMA200 position)
- **Weekly timeframe is SECONDARY**: Used for trend confirmation and support/resistance
- Weekly data enhances analysis but is not critical for dip-buying entry decisions

### Changes Implemented

#### 1. Reduced Minimum Weekly Data Requirement

**Before**: 50 rows (1 year) - strict requirement  
**After**: 20 rows (5 months) - recommended, but flexible

**File**: `core/data_fetcher.py`

**Changes**:
```python
# Before:
min_required = 50 if interval == '1wk' else 30

# After:
min_required_daily = 30  # Daily needs minimum for EMA200
min_required_weekly = 20  # Weekly: Reduced from 50 to 20 for newer stocks
```

#### 2. Graceful Degradation for Weekly Data

**Behavior**:
- If weekly data has 10-19 rows: Log as INFO, continue with available data
- If weekly data has < 10 rows: Log as WARNING, use daily-only analysis
- If weekly data fetch fails: Continue with daily-only analysis (no failure)

**File**: `core/data_fetcher.py`

**Changes**:
```python
if interval == '1wk':
    if len(df) >= 10:  # At least 10 weeks (2.5 months)
        logger.info(f"Weekly data: {len(df)} rows (below recommended but continuing)")
        return df  # Return data even if below minimum
    else:
        # Very limited weekly data - not useful
        raise ValueError(f"Insufficient weekly data: only {len(df)} rows")
```

#### 3. Adaptive Lookback for Limited Weekly Data

**File**: `core/timeframe_analysis.py`

**Changes**:
- When weekly data has limited rows (< recommended lookback):
  - Use reduced lookback (50% of requested, minimum 10)
  - Continue analysis with available data
  - Log debug message for transparency

```python
if len(df) < support_lookback:
    if timeframe == 'weekly' and len(df) >= 10:
        # Use reduced lookback (50% of requested)
        support_lookback = max(int(support_lookback * 0.5), 10)
        logger.debug(f"Weekly data limited, using reduced lookback: {support_lookback}")
    else:
        return None  # Not enough data
```

#### 4. Improved Error Handling in Multi-Timeframe Fetch

**File**: `core/data_fetcher.py`

**Changes**:
- Catch ValueError for insufficient data separately
- Continue with daily-only analysis when weekly data is insufficient
- Log as INFO instead of WARNING for expected cases (newer stocks)

```python
except ValueError as e:
    # Insufficient data - continue with daily-only
    logger.info(f"Weekly data unavailable: {e} - continuing with daily-only analysis")
    return {'daily': daily_data, 'weekly': None}
```

### How It Works

#### Scenario 1: Sufficient Weekly Data (≥ 20 rows)
- ✅ Full MTF analysis with weekly confirmation
- ✅ Standard lookback periods
- ✅ Best analysis quality

#### Scenario 2: Limited Weekly Data (10-19 rows)
- ✅ MTF analysis with reduced lookback
- ✅ Weekly data used for basic trend confirmation
- ✅ Analysis continues with available data
- ℹ️ Logged as INFO (not warning)

#### Scenario 3: Very Limited Weekly Data (< 10 rows)
- ✅ Daily-only analysis
- ✅ MTF analysis uses daily data only
- ✅ Adjusted thresholds for daily-only (already implemented)
- ℹ️ Logged as INFO

#### Scenario 4: Weekly Data Fetch Fails
- ✅ Daily-only analysis
- ✅ No failure - analysis continues
- ℹ️ Logged as INFO (not error)

### Benefits

1. **More Stocks Analyzed**: Newer stocks with limited history can still be analyzed
2. **Better Dip-Buying Coverage**: Focus on daily signals (primary) while using weekly when available
3. **Reduced Noise**: Fewer warnings for expected cases (newer stocks)
4. **Graceful Degradation**: System continues to work even with limited weekly data
5. **Better Logging**: INFO level for expected cases, WARNING only for real issues

### Impact on Analysis Quality

#### Daily-Only Analysis (When Weekly Unavailable)
- ✅ **Entry Signals**: RSI < 30, EMA200 position (daily) - **PRIMARY**
- ✅ **Support/Resistance**: Daily timeframe analysis
- ✅ **Volume Analysis**: Daily volume patterns
- ⚠️ **Trend Confirmation**: Limited (no weekly trend)
- ✅ **MTF Alignment Score**: Adjusted thresholds (already implemented)

#### With Limited Weekly Data (10-19 rows)
- ✅ **Entry Signals**: RSI < 30, EMA200 position (daily) - **PRIMARY**
- ✅ **Support/Resistance**: Daily + limited weekly
- ✅ **Volume Analysis**: Daily + limited weekly
- ✅ **Trend Confirmation**: Basic weekly trend (reduced lookback)
- ✅ **MTF Alignment Score**: Standard calculation with limited data

### Configuration

**Current Settings**:
- Daily minimum: 30 rows (for EMA200 calculation)
- Weekly minimum: 20 rows (recommended, but flexible)
- Weekly absolute minimum: 10 rows (for basic analysis)
- Weekly reduced lookback: 50% of standard (minimum 10)

**Future Enhancement**: Make these configurable via `StrategyConfig`:
```python
# In StrategyConfig:
weekly_data_min_recommended = 20  # Recommended minimum
weekly_data_min_absolute = 10     # Absolute minimum for basic analysis
weekly_data_reduced_lookback_ratio = 0.5  # Reduced lookback when limited
```

### Testing

#### Test Cases

1. **New Stock (5 weeks of data)**:
   - ✅ Should continue with daily-only analysis
   - ✅ No errors, INFO level log

2. **Recent IPO (15 weeks of data)**:
   - ✅ Should use weekly data with reduced lookback
   - ✅ INFO level log about limited data

3. **Established Stock (100+ weeks of data)**:
   - ✅ Should use full weekly analysis
   - ✅ No warnings or info messages

4. **Weekly Data Fetch Failure**:
   - ✅ Should continue with daily-only analysis
   - ✅ No failure, INFO level log

### Migration Notes

**Backward Compatibility**: ✅ **FULLY COMPATIBLE**
- Existing analysis continues to work
- Stocks with sufficient weekly data get full analysis
- Stocks with limited weekly data get improved analysis (instead of failure)

**No Breaking Changes**: ✅
- All existing functionality preserved
- Only adds flexibility for limited data cases
- No changes to analysis results for stocks with sufficient data

### Recommendations

1. **Short Term** (Implemented):
   - ✅ Reduced minimum weekly data requirement
   - ✅ Graceful degradation for limited weekly data
   - ✅ Improved error handling

2. **Medium Term** (Consider):
   - 💡 Make weekly data requirements configurable
   - 💡 Add data quality indicators to analysis results
   - 💡 Monitor analysis quality with limited weekly data

3. **Long Term** (Consider):
   - 💡 Alternative data sources for weekly data
   - 💡 Caching weekly data to reduce API calls
   - 💡 Adaptive analysis based on data availability

## Conclusion

✅ **Solution Implemented**: Flexible weekly data requirements for dip-buying strategy

**Key Benefits**:
- More stocks can be analyzed (newer stocks with limited history)
- Better focus on daily signals (primary for dip-buying)
- Reduced noise in logs (INFO instead of WARNING for expected cases)
- Graceful degradation (analysis continues with available data)

**Status**: ✅ **READY FOR USE**

---

**Last Updated**: 2025-11-09  
**Status**: ✅ Solution Implemented




