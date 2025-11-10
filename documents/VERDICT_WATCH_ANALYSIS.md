# Verdict "Watch" Analysis - Root Cause Investigation

**Date**: 2025-11-09  
**CSV File**: `bulk_analysis_final_20251109_133452.csv`  
**Total Stocks**: 20 (19 watch, 1 avoid)

## Executive Summary

All stocks in the bulk analysis are getting "watch" verdicts instead of "buy" despite having:
- ✅ Good chart quality (85-100 score, all passed)
- ✅ Oversold RSI (many below 30, some below 20)
- ✅ Good alignment scores (7-10)
- ✅ Excellent/good uptrend dip confirmations
- ✅ Clean charts with minimal gaps

## Root Causes Identified

### 1. **ML Model Predicting "watch" (Primary Issue)**

**Evidence:**
- All tested stocks show justification: `['ML prediction: watch']`
- Stocks like NAVA.NS have ALL conditions met but still get "watch":
  - RSI: 18.16 (extremely oversold)
  - PE: 17.76 (profitable)
  - PB: 2.13 (reasonable)
  - Alignment Score: 9 (excellent)
  - Signals: `rsi_oversold`, `excellent_uptrend_dip`
  - Chart Quality: 100.0 (passed)
  - Volume Quality: excellent

**Root Cause:**
- ML model (`MLVerdictService`) is being used and predicting "watch"
- ML model may have:
  - Low confidence threshold (fails back to rule-based)
  - Conservative training data (more "watch" than "buy" in training set)
  - Missing features or feature extraction issues
  - Model not calibrated for current market conditions

**Impact:** ~95% of stocks (19/20) getting "watch" due to ML predictions

### 2. **Volume/Liquidity Filters (Secondary Issue)**

**Evidence:**
- MAHSCOOTER.NS: `avg_volume=11525 < 20000` (low liquidity)
- AIIL.NS: Volume quality = "poor"
- Volume data not exported to CSV (can't see `vol_ok`/`vol_strong`)

**Root Cause:**
- Liquidity filter: `MIN_ABSOLUTE_AVG_VOLUME = 20000`
- Volume quality assessment failing even with relaxed thresholds (0.7x, 0.5x for RSI < 30)
- Some stocks may have:
  - Volume < 0.7x average (even after RSI adjustment to 0.5x)
  - Low absolute volume (< 20,000)
  - Poor volume quality (declining volume, low volume decline)

**Impact:** ~10-20% of stocks failing volume requirements

### 3. **Missing Trading Parameters**

**Evidence:**
- All stocks have `buy_range=None`, `target=None`, `stop=None`
- Trading parameters are ONLY calculated when verdict is "buy" or "strong_buy"

**Root Cause:**
- Trading parameters calculation is gated by verdict type
- Since verdict is "watch", parameters are never calculated
- This is expected behavior but confirms stocks never reached "buy" verdict

**Impact:** Confirms stocks never met "buy" criteria

## Detailed Analysis

### Stock Examples

#### NAVA.NS (Should be "buy")
- **Verdict**: watch
- **Justification**: `['ML prediction: watch']`
- **RSI**: 18.16 (extremely oversold)
- **PE**: 17.76 (profitable)
- **PB**: 2.13 (reasonable)
- **Signals**: `rsi_oversold`, `excellent_uptrend_dip`
- **Alignment Score**: 9 (excellent)
- **Chart Quality**: 100.0 (passed)
- **Volume Quality**: excellent
- **Issue**: ML model predicting "watch" despite all conditions met

#### MAHSCOOTER.NS (Volume issue)
- **Verdict**: watch
- **Justification**: `['ML prediction: watch']`
- **RSI**: 13.45 (extremely oversold)
- **PE**: 46.30 (high but positive)
- **PB**: 0.50 (very low, excellent)
- **Signals**: `rsi_oversold`, `excellent_uptrend_dip`
- **Alignment Score**: 10 (excellent)
- **Chart Quality**: 100.0 (passed)
- **Volume Quality**: illiquid (`avg_volume=11525 < 20000`)
- **Issue**: Low liquidity filter blocking entry

#### AIIL.NS (Volume + ML issue)
- **Verdict**: watch
- **Justification**: `['ML prediction: watch']`
- **RSI**: 24.55 (oversold)
- **PE**: 11.63 (good)
- **PB**: 3.23 (reasonable)
- **Signals**: `rsi_oversold`, `good_uptrend_dip`
- **Alignment Score**: 7 (good)
- **Chart Quality**: 85.0 (passed)
- **Volume Quality**: poor
- **Issue**: Poor volume quality AND ML model predicting "watch"

## Recommendations

### 1. **Fix ML Model Predictions (High Priority)**

**Options:**
- **A. Lower ML Confidence Threshold**
  - Current: 50% minimum confidence
  - Suggested: 40% minimum confidence
  - Allow ML predictions with lower confidence to be used
  - Implementation: `services/ml_verdict_service.py`

- **B. Improve ML Model Training**
  - Re-train model with more "buy" examples
  - Balance training data (currently may have more "watch" than "buy")
  - Add more features (volume quality, fundamental assessment)
  - Calibrate model for current market conditions

- **C. Use Rule-Based Fallback More Aggressively**
  - If ML confidence < 60%, use rule-based logic
  - Rule-based logic seems more accurate for current conditions
  - Implementation: `services/ml_verdict_service.py::determine_verdict()`

- **D. Disable ML Model Temporarily**
  - Use `VerdictService` instead of `MLVerdictService`
  - Verify rule-based logic produces "buy" verdicts
  - Re-enable ML after fixing/training

### 2. **Relax Volume Requirements (Medium Priority)**

**Options:**
- **A. Lower Liquidity Threshold**
  - Current: `MIN_ABSOLUTE_AVG_VOLUME = 20000`
  - Suggested: `10000` or `15000` (allow smaller stocks)
  - Implementation: `config/settings.py`

- **B. Further Relax Volume Multiplier for Oversold**
  - Current: 0.5x for RSI < 30
  - Suggested: 0.3x for RSI < 20 (extremely oversold)
  - Implementation: `core/volume_analysis.py`

- **C. Improve Volume Quality Assessment**
  - Don't fail on "poor" volume quality if RSI is extremely oversold
  - Allow "fair" volume quality for oversold conditions
  - Implementation: `core/volume_analysis.py`

### 3. **Improve CSV Export (Low Priority)**

**Options:**
- **A. Add Missing Fields to CSV**
  - Added: `justification`, `pe`, `pb`, `rsi`, `avg_vol`, `today_vol`
  - Still missing: `vol_ok`, `vol_strong`, `fundamental_ok`, `fundamental_assessment`
  - Implementation: `trade_agent.py::_process_results()`

- **B. Add Volume Data to CSV**
  - Export `vol_ok`, `vol_strong`, `volume_ratio`, `volume_quality`
  - Export `fundamental_ok`, `fundamental_growth_stock`, `fundamental_avoid`
  - Implementation: `trade_agent.py::_process_results()`

### 4. **Debug ML Model Predictions (High Priority)**

**Options:**
- **A. Add ML Prediction Logging**
  - Log ML confidence scores
  - Log feature values used for prediction
  - Log why ML predicted "watch" vs "buy"
  - Implementation: `services/ml_verdict_service.py`

- **B. Compare ML vs Rule-Based Predictions**
  - Run both ML and rule-based for same stocks
  - Compare predictions and identify discrepancies
  - Use rule-based when ML is too conservative

## Implementation Plan

### Phase 1: Immediate Fixes (1-2 hours)
1. ✅ Add missing fields to CSV export (`justification`, `pe`, `pb`, `rsi`)
2. Add ML confidence logging
3. Add volume data to CSV export

### Phase 2: ML Model Fixes (2-4 hours)
1. Lower ML confidence threshold to 40%
2. Add rule-based fallback when ML confidence < 60%
3. Test with sample stocks to verify "buy" verdicts

### Phase 3: Volume Relaxation (1-2 hours)
1. Lower liquidity threshold to 15000
2. Further relax volume multiplier for RSI < 20 (0.3x)
3. Improve volume quality assessment for oversold conditions

### Phase 4: Long-Term Improvements (1-2 days)
1. Re-train ML model with balanced data
2. Add more features to ML model
3. Calibrate model for current market conditions

## Expected Impact

### After Phase 1 + 2:
- **Expected "buy" verdicts**: 30-40% (currently 0%)
- **ML model**: More accurate predictions or better fallback
- **Debugging**: Better visibility into verdict reasons

### After Phase 3:
- **Expected "buy" verdicts**: 40-50% (with volume relaxation)
- **Volume filters**: Less restrictive for oversold conditions
- **Liquidity**: More stocks pass liquidity filter

### After Phase 4:
- **Expected "buy" verdicts**: 50-60% (with improved ML model)
- **ML model**: Better calibrated for current conditions
- **Accuracy**: Higher confidence in predictions

## Testing Plan

1. **Test with Sample Stocks**
   - Run analysis on NAVA.NS, MAHSCOOTER.NS, AIIL.NS
   - Verify "buy" verdicts after fixes
   - Check justification and trading parameters

2. **Test with Bulk Analysis**
   - Run bulk analysis on 20-50 stocks
   - Verify "buy" verdict rate increases
   - Check CSV export includes all fields

3. **Test ML Model Predictions**
   - Compare ML vs rule-based predictions
   - Verify ML confidence scores
   - Check fallback to rule-based when needed

## Conclusion

The primary issue is the **ML model predicting "watch"** for stocks that should be "buy" based on rule-based logic. The secondary issue is **volume/liquidity filters** blocking some stocks.

**Recommended immediate actions:**
1. Lower ML confidence threshold to 40%
2. Add rule-based fallback when ML confidence < 60%
3. Lower liquidity threshold to 15000
4. Add missing fields to CSV export for debugging

**Expected outcome:** 30-50% of stocks should get "buy" verdicts after these fixes.




