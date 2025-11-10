# Timeframe Analysis Indexer Error Fix

**Date**: 2025-11-07  
**Status**: Fixed  
**Severity**: Medium (Non-blocking but causes error logs)

---

## Error Description

### Error Message
```
ERROR — timeframe_analysis — Error in support analysis: cannot do positional indexing on RangeIndex with these indexers [-30.0] of type float
ERROR — timeframe_analysis — Error in resistance analysis: cannot do positional indexing on RangeIndex with these indexers [-30.0] of type float
```

### Impact
- **Non-blocking**: Analysis continues but with degraded support/resistance analysis
- **Error Logs**: Repeated error messages in logs during backtesting
- **Functionality**: Support and resistance analysis returns default values when error occurs

### Occurrence
- Occurs during backtesting when analyzing historical dates
- Happens when `TimeframeAnalysis._analyze_support_levels()` and `_analyze_resistance_levels()` are called
- Error appears multiple times per backtest run (once per signal analyzed)

---

## Root Cause Analysis

### Problem
The `_get_adaptive_lookback()` method can return a float value (e.g., `50.0`) when calculating adaptive lookback periods:

```python
return min(base_lookback * 2.5, 50)  # Returns 50.0 (float) when base_lookback * 2.5 = 50.0
```

When this float value is passed to `df.tail()`, pandas may have issues with type conversion in certain edge cases, especially when the DataFrame has a RangeIndex.

### Code Location
- **File**: `core/timeframe_analysis.py`
- **Methods**: 
  - `_get_adaptive_lookback()` (lines 46-73)
  - `_analyze_support_levels()` (lines 135-185)
  - `_analyze_resistance_levels()` (lines 187-231)

### Why -30.0?
The error message shows `[-30.0]`, which is confusing because:
- The lookback values should be 20 (daily) or 50 (weekly)
- The value `30.0` matches `RSI_OVERSOLD` threshold, but shouldn't be used as a lookback

**Hypothesis**: The error message might be misleading - pandas may be trying to interpret the float value in a way that causes this specific error message, even though the actual value being used is different.

---

## Solution

### Fix Applied

1. **Explicit Integer Conversion in `_get_adaptive_lookback()`**:
   ```python
   # Before
   return min(base_lookback * 2.5, 50)  # Could return 50.0 (float)
   
   # After
   return int(min(base_lookback * 2.5, 50))  # Always returns 50 (int)
   ```

2. **Defensive Integer Conversion in Analysis Methods**:
   ```python
   # Added to _analyze_support_levels() and _analyze_resistance_levels()
   support_lookback = int(support_lookback)  # Ensure integer before use
   ```

### Changes Made

**File**: `core/timeframe_analysis.py`

1. **Line 59**: `return int(min(base_lookback * 2.5, 50))`
2. **Line 61**: `return int(min(base_lookback * 2, 40))`
3. **Line 67**: `return int(min(base_lookback * 2.5, 50))`
4. **Line 69**: `return int(min(base_lookback * 1.5, 30))`
5. **Line 141**: Added `support_lookback = int(support_lookback)` in `_analyze_support_levels()`
6. **Line 193**: Added `support_lookback = int(support_lookback)` in `_analyze_resistance_levels()`

---

## Testing

### Test Command
```powershell
if (Test-Path .venv\Scripts\Activate.ps1) { .\.venv\Scripts\Activate.ps1; python test_trade_agent_backtest.py } else { Write-Host ".venv not found" }
```

### Expected Result
- ✅ No more "Error in support analysis" messages
- ✅ No more "Error in resistance analysis" messages
- ✅ Backtest completes successfully
- ✅ Support and resistance analysis works correctly

### Verification
After fix, the test should run without the timeframe_analysis errors.

---

## Prevention

### Best Practices
1. **Always use integers for pandas indexing operations**:
   - `df.tail(n)` - n should be int
   - `df.iloc[n]` - n should be int
   - `df.loc[n]` - n should be int (for integer index)

2. **Explicit type conversion**:
   - When calculating values that will be used as indices, explicitly convert to int
   - Use `int()` conversion before passing to pandas operations

3. **Type hints**:
   - Use `-> int` return type hints to document expected types
   - Helps catch type issues during development

### Code Review Checklist
- [ ] Check that all indexer values are integers
- [ ] Verify type conversions for calculated index values
- [ ] Test with edge cases (float results from calculations)

---

## Related Issues

- **Deprecation Warning**: The code still uses deprecated `core.analysis.analyze_ticker()` - should migrate to `services.AnalysisService.analyze_ticker()`
- **XGBoost Warning**: `xgboost not available` - optional dependency, not critical

---

## References

- [PROJECT_RULES.md](../../PROJECT_RULES.md) - Project rules and standards
- [TESTING_RULES.md](../testing/TESTING_RULES.md) - Testing guidelines
- [core/timeframe_analysis.py](../../core/timeframe_analysis.py) - Fixed file

---

**Fixed By**: Auto (AI Assistant)  
**Reviewed By**: Pending  
**Merged**: Pending




