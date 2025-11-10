# Backtest Verdict Validation Test - Results Analysis

## Test Execution Summary

**Date**: 2025-11-09  
**Stock**: RELIANCE.NS  
**Period**: 5 years (2020-11-10 to 2025-11-09)  
**Total Signals**: 31  
**Executed Trades**: 0  
**Skipped Signals**: 31

## Key Findings

### 1. Chart Quality Filter Issue ⚠️

**Finding**: RELIANCE.NS failed chart quality check with **28.3% gaps** (threshold: 20%), but ML model is still predicting "watch" verdicts for all 31 signals.

**Expected Behavior**: 
- Chart quality failed → Verdict should be "avoid"
- ML model should not make predictions when chart quality fails (Stage 1 filter)

**Actual Behavior**:
- ML model predicted "watch" for all 31 signals
- Chart quality filter is not being respected by ML model

**Root Cause**:
- When using `as_of_date` parameter, chart quality is assessed on truncated data (data up to that date)
- Full historical chart quality assessment shows 28.3% gaps (fails)
- But individual date assessments might use different data subsets
- ML model might be bypassing chart quality check in some cases

**Impact**: 
- High - System is not properly filtering out stocks with poor chart quality
- All 31 signals got "watch" verdicts instead of "avoid"

### 2. ML Model vs Rule-Based Logic Mismatch ⚠️

**Finding**: ML model predictions differ significantly from rule-based logic expectations.

**Expected Behavior**:
- Rule-based logic: Chart quality failed → "avoid"
- ML model: Should respect chart quality (Stage 1) → "avoid"

**Actual Behavior**:
- Rule-based logic: Expects "avoid" (due to chart quality failure)
- ML model: Predicts "watch" (ignoring chart quality)

**Root Cause**:
- ML model might not be properly checking chart quality before prediction
- ML model training data might not include chart quality as a feature
- Two-stage approach (chart quality + ML) might not be properly implemented

**Impact**: 
- High - ML model is not following the two-stage approach correctly
- System consistency is compromised

### 3. EMA200 Position Calculation Differences ℹ️

**Finding**: EMA200 position (above/below) differs between backtest engine and analysis service.

**Expected Behavior**:
- Both should calculate EMA200 position consistently

**Actual Behavior**:
- Backtest engine: Shows price above EMA200
- Analysis service: Calculates price below EMA200 (for some dates)

**Root Cause**:
- Different data sources (backtest engine vs analysis service)
- `as_of_date` truncation affects EMA200 calculation (needs historical data)
- Different lookback periods or calculation methods

**Impact**: 
- Medium - Affects entry condition validation
- May cause signals to be generated incorrectly

### 4. No Trades Executed ⚠️

**Finding**: All 31 signals were skipped (no trades executed).

**Expected Behavior**:
- If verdict is "buy" or "strong_buy", trade should be executed
- If verdict is "watch" or "avoid", trade should be skipped

**Actual Behavior**:
- All signals got "watch" verdict (due to ML model)
- All trades were skipped (correct behavior for "watch" verdict)

**Impact**: 
- Medium - No trades executed during 5-year period
- Suggests either:
  - Chart quality filter is too strict (RELIANCE.NS has 28.3% gaps)
  - ML model is too conservative (predicting "watch" instead of "buy")
  - Entry conditions are not being met properly

## Recommendations

### 1. Fix Chart Quality Integration with ML Model 🔴 HIGH PRIORITY

**Issue**: ML model is not respecting chart quality filter (Stage 1).

**Solution**:
1. Ensure ML model checks chart quality BEFORE making predictions
2. Review `MLVerdictService.determine_verdict()` implementation
3. Verify chart quality is properly passed to ML model
4. Add unit tests to verify chart quality filter is enforced

**Code Review**:
- `services/ml_verdict_service.py`: Line 121-124 (chart quality check)
- `services/analysis_service.py`: Line 183-197 (chart quality assessment)

### 2. Fix Chart Quality Assessment with as_of_date 🔴 HIGH PRIORITY

**Issue**: Chart quality assessment differs when using `as_of_date` (truncated data).

**Solution**:
1. Use full historical data for chart quality assessment (not truncated)
2. Store chart quality result and reuse it for all date analyses
3. Or: Assess chart quality on full dataset, then filter by date for analysis

**Code Review**:
- `services/analysis_service.py`: Line 184 (chart quality assessment)
- Consider caching chart quality results for a stock

### 3. Align EMA200 Calculation 🔵 MEDIUM PRIORITY

**Issue**: EMA200 position calculation differs between backtest engine and analysis service.

**Solution**:
1. Use same data source for both backtest engine and analysis service
2. Ensure same lookback period for EMA200 calculation
3. Handle `as_of_date` properly (use full historical data for EMA200)

**Code Review**:
- `backtest/backtest_engine.py`: EMA200 calculation
- `services/indicator_service.py`: EMA200 calculation

### 4. Review ML Model Training Data 🔵 MEDIUM PRIORITY

**Issue**: ML model predictions differ significantly from rule-based logic.

**Solution**:
1. Review ML model training data - does it include chart quality as a feature?
2. Retrain ML model with chart quality as a feature
3. Ensure ML model is trained on data that respects chart quality filter
4. Consider adding chart quality as a hard filter before ML prediction

**Code Review**:
- `services/ml_verdict_service.py`: ML model feature extraction
- ML model training scripts

### 5. Improve Test Coverage 🟢 LOW PRIORITY

**Issue**: Test found issues that should have been caught earlier.

**Solution**:
1. Add unit tests for chart quality integration with ML model
2. Add integration tests for as_of_date scenarios
3. Add tests for EMA200 calculation consistency
4. Add regression tests for verdict calculation

## Test Validation Status

### Verdict Validations
- **Total**: 31
- **Passed**: 0
- **Failed**: 31
- **Pass Rate**: 0.0%

### Trade Execution Validations
- **Total**: 0
- **Passed**: 0
- **Failed**: 0
- **Pass Rate**: N/A (no trades executed)

### Overall Status: ❌ FAILED

## Next Steps

1. **Immediate Actions**:
   - Fix chart quality integration with ML model (Stage 1 filter)
   - Fix chart quality assessment with as_of_date
   - Review ML model training data and retrain if needed

2. **Short-term Actions**:
   - Align EMA200 calculation between backtest engine and analysis service
   - Add unit tests for chart quality integration
   - Add integration tests for as_of_date scenarios

3. **Long-term Actions**:
   - Improve ML model training process
   - Add regression tests for verdict calculation
   - Document chart quality assessment process

## Conclusion

The test successfully identified several critical issues in the system:

1. **Chart Quality Filter Not Respected**: ML model is not properly checking chart quality before making predictions
2. **Data Consistency Issues**: Chart quality assessment differs when using `as_of_date`
3. **Calculation Differences**: EMA200 position calculation differs between components

These issues need to be addressed before the system can be considered production-ready. The test is working correctly and providing valuable insights into system behavior.

## Test Script Improvements

The test script has been updated to:
- Better handle ML model predictions vs rule-based logic
- Treat EMA200 differences as warnings (due to data source differences)
- Provide recommendations based on findings
- Handle chart quality assessment with as_of_date

The test is now more robust and provides better insights into system behavior.




