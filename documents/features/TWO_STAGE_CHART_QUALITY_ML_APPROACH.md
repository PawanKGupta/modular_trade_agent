# Two-Stage Approach: Chart Quality + ML Model

## Overview

This document describes the two-stage approach implemented in production to ensure ML models only see stocks that pass chart quality filtering, matching the training data distribution.

---

## Problem Statement

**Training-Serving Mismatch**:
- Training data: Collected with `--disable-chart-quality` (includes bad charts)
- Production: Chart quality filtering is **ENABLED** (filters out bad charts)
- Impact: Model trained on distribution that doesn't match production

**Solution**: Two-stage approach ensures ML model only sees stocks that pass chart quality filtering.

---

## Two-Stage Approach

### Stage 1: Chart Quality Filter (Hard Filter)

**Purpose**: Filter out stocks with poor chart quality before ML prediction.

**Implementation**:
```python
# Check chart quality (hard filter)
chart_quality_data = chart_quality_service.assess_chart_quality(df)
chart_quality_passed = chart_quality_data.get('passed', True)

if not chart_quality_passed:
    return "avoid"  # Skip ML prediction
```

**When Applied**:
- Early in analysis pipeline (Step 4 in `AnalysisService`)
- Before ML model prediction
- Before rule-based verdict determination

**Criteria**:
- Gap frequency < 20%
- Daily range > 1.5%
- Extreme candle frequency < 15%
- Chart cleanliness score >= 60

### Stage 2: ML Model Prediction

**Purpose**: Predict verdict using ML model (only if chart quality passed).

**Implementation**:
```python
# Only run ML prediction if chart quality passed
if chart_quality_passed and ml_model_loaded:
    ml_verdict = ml_model.predict(features)
    return ml_verdict
```

**When Applied**:
- Only after chart quality check passes
- If ML model is available
- Falls back to rule-based logic if ML unavailable

---

## Implementation Details

### 1. AnalysisService (Primary Pipeline)

**File**: `services/analysis_service.py`

**Flow**:
1. Step 4: Check chart quality (hard filter)
2. If chart quality fails → Return early with "avoid"
3. Step 11: Determine verdict (includes ML if MLVerdictService is used)
4. ML prediction only runs if chart quality passed

**Code**:
```python
# Step 4: Check chart quality (hard filter)
chart_quality_data = self.verdict_service.assess_chart_quality(df)
chart_quality_passed = chart_quality_data.get('passed', True)

if not chart_quality_passed:
    return {
        "verdict": "avoid",
        "chart_quality": chart_quality_data,
        ...
    }

# Step 11: Determine verdict (ML included if MLVerdictService)
verdict, justification = self.verdict_service.determine_verdict(
    ...,
    chart_quality_passed=chart_quality_passed  # Passed to ML service
)
```

### 2. MLVerdictService (ML Prediction)

**File**: `services/ml_verdict_service.py`

**Flow**:
1. Check chart quality (Stage 1)
2. If chart quality fails → Return "avoid" immediately
3. If chart quality passed → Run ML prediction (Stage 2)
4. Fall back to rule-based if ML unavailable

**Code**:
```python
def determine_verdict(..., chart_quality_passed: bool = True):
    # Stage 1: Chart quality filter (hard filter)
    if not chart_quality_passed:
        return "avoid", ["Chart quality failed"]
    
    # Stage 2: ML model prediction (only if chart quality passed)
    if self.model_loaded:
        ml_verdict = self._predict_with_ml(...)
        if ml_verdict:
            return ml_verdict, justification
    
    # Fall back to rule-based logic
    return super().determine_verdict(..., chart_quality_passed=chart_quality_passed)
```

### 3. trade_agent.py (Legacy Support)

**File**: `trade_agent.py`

**Flow**:
1. AnalysisService already checks chart quality
2. Check chart quality status from result
3. Only run ML prediction if chart quality passed
4. Skip ML prediction if chart quality failed

**Code**:
```python
# Check chart quality status
chart_quality = result.get('chart_quality', {})
chart_quality_passed = chart_quality.get('passed', True)

# Only run ML prediction if chart quality passed (Stage 2)
if ml_service and ml_service.model_loaded and chart_quality_passed:
    ml_verdict, ml_confidence = ml_service.predict_verdict_with_confidence(
        ...,
        chart_quality_passed=chart_quality_passed  # Two-stage approach
    )
```

---

## Configuration

### Enable ML Model

**Option 1: Automatic (Recommended)**
- `AnalysisService` automatically uses `MLVerdictService` if ML model exists
- Model path: `models/verdict_model_random_forest.pkl` (default)
- Or: `config.ml_verdict_model_path` (if configured)

**Option 2: Manual**
```python
from services.ml_verdict_service import MLVerdictService
from services.analysis_service import AnalysisService

ml_verdict_service = MLVerdictService(model_path="models/verdict_model.pkl")
analysis_service = AnalysisService(verdict_service=ml_verdict_service)
```

### Chart Quality Settings

**Default** (Production):
```python
chart_quality_enabled: bool = True  # REQUIRED in production
chart_quality_min_score: float = 60.0
chart_quality_max_gap_frequency: float = 20.0
chart_quality_min_daily_range_pct: float = 1.5
chart_quality_max_extreme_candle_frequency: float = 15.0
```

**Environment Variables**:
```bash
CHART_QUALITY_ENABLED=true  # REQUIRED - DO NOT disable in production
CHART_QUALITY_MIN_SCORE=60.0
CHART_QUALITY_MAX_GAP_FREQUENCY=20.0
CHART_QUALITY_MIN_DAILY_RANGE_PCT=1.5
CHART_QUALITY_MAX_EXTREME_CANDLE_FREQUENCY=15.0
```

---

## Benefits

### 1. Distribution Match

**Before**:
- Training: Includes bad charts (3-5%)
- Production: Only good charts
- Mismatch: Model sees different distribution

**After**:
- Training: Filtered to only good charts
- Production: Only good charts
- Match: 100% distribution alignment ✅

### 2. Model Accuracy

**Expected Improvement**:
- Accuracy: +2-5% improvement
- Consistency: Better prediction consistency
- Overfitting: Reduced risk of overfitting

### 3. Production Safety

**Benefits**:
- Chart quality always enforced (hard filter)
- ML model only sees valid stocks
- No risk of ML model predicting on bad charts
- Consistent with training data distribution

---

## Verification

### Check Two-Stage Implementation

```python
from services.analysis_service import AnalysisService
from services.ml_verdict_service import MLVerdictService

# Check if MLVerdictService is being used
analysis_service = AnalysisService()
if isinstance(analysis_service.verdict_service, MLVerdictService):
    print("✅ Using MLVerdictService (two-stage approach)")
    print(f"   ML model loaded: {analysis_service.verdict_service.model_loaded}")
else:
    print("⚠️  Using VerdictService (rule-based only)")

# Check chart quality is enabled
config = analysis_service.config
print(f"✅ Chart quality enabled: {config.chart_quality_enabled}")
```

### Test Two-Stage Filtering

```python
# Test with bad chart (should fail Stage 1)
bad_chart_result = analysis_service.analyze_ticker("BADCHART.NS")
assert bad_chart_result['verdict'] == 'avoid'
assert bad_chart_result['chart_quality']['passed'] == False
assert 'ml_verdict' not in bad_chart_result  # ML not called

# Test with good chart (should pass both stages)
good_chart_result = analysis_service.analyze_ticker("RELIANCE.NS")
assert good_chart_result['chart_quality']['passed'] == True
# ML verdict may or may not be present (depends on ML model availability)
```

---

## Usage

### Standard Usage (Automatic)

```python
from services.analysis_service import AnalysisService

# AnalysisService automatically uses MLVerdictService if model exists
service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")

# Two-stage approach is automatically enforced:
# 1. Chart quality check (Stage 1)
# 2. ML prediction (Stage 2, only if Stage 1 passed)
```

### Manual Configuration

```python
from services.ml_verdict_service import MLVerdictService
from services.analysis_service import AnalysisService
from config.strategy_config import StrategyConfig

# Create ML verdict service
config = StrategyConfig.default()
ml_verdict_service = MLVerdictService(
    model_path="models/verdict_model.pkl",
    config=config
)

# Create analysis service with ML verdict service
analysis_service = AnalysisService(
    verdict_service=ml_verdict_service,
    config=config
)

# Analyze stock (two-stage approach automatically enforced)
result = analysis_service.analyze_ticker("RELIANCE.NS")
```

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Stock Analysis Pipeline                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   Step 1-3: Data & Indicators     │
        └───────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────┐
        │   Stage 1: Chart Quality Filter   │
        │   (Hard Filter)                   │
        └───────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
         ❌ Failed              ✅ Passed
                │                       │
                ▼                       ▼
        ┌───────────────┐   ┌──────────────────────┐
        │ Return "avoid"│   │  Stage 2: ML Model   │
        │ (Skip ML)     │   │  Prediction          │
        └───────────────┘   └──────────────────────┘
                                    │
                            ┌───────┴───────┐
                            │               │
                      ML Available    ML Unavailable
                            │               │
                            ▼               ▼
                    ┌──────────────┐  ┌──────────────┐
                    │ ML Verdict   │  │ Rule-based   │
                    │              │  │ Verdict      │
                    └──────────────┘  └──────────────┘
```

---

## Testing

### Unit Tests

```python
def test_two_stage_approach_chart_quality_failed():
    """Test that ML prediction is skipped if chart quality fails"""
    service = MLVerdictService(model_path="models/verdict_model.pkl")
    
    # Test with chart quality failed
    verdict, justification = service.determine_verdict(
        signals=[],
        rsi_value=25,
        is_above_ema200=True,
        vol_ok=True,
        vol_strong=False,
        fundamental_ok=True,
        timeframe_confirmation=None,
        news_sentiment=None,
        chart_quality_passed=False  # Chart quality failed
    )
    
    assert verdict == "avoid"
    assert "Chart quality failed" in justification[0]
    # ML prediction should not be called

def test_two_stage_approach_chart_quality_passed():
    """Test that ML prediction runs if chart quality passes"""
    service = MLVerdictService(model_path="models/verdict_model.pkl")
    
    # Test with chart quality passed
    verdict, justification = service.determine_verdict(
        signals=[],
        rsi_value=25,
        is_above_ema200=True,
        vol_ok=True,
        vol_strong=False,
        fundamental_ok=True,
        timeframe_confirmation=None,
        news_sentiment=None,
        chart_quality_passed=True  # Chart quality passed
    )
    
    # ML prediction should be called (if model loaded)
    if service.model_loaded:
        assert verdict in ["strong_buy", "buy", "watch", "avoid"]
        assert "ML prediction" in justification[0]
```

---

## Troubleshooting

### ML Model Not Being Used

**Symptoms**: AnalysisService uses VerdictService instead of MLVerdictService

**Solution**:
1. Check if ML model file exists: `models/verdict_model_random_forest.pkl`
2. Check model path in config: `config.ml_verdict_model_path`
3. Verify model file is readable
4. Check logs for ML model loading errors

### Chart Quality Not Filtering

**Symptoms**: Stocks with bad charts are not being filtered

**Solution**:
1. Check `config.chart_quality_enabled = True`
2. Check environment variable: `CHART_QUALITY_ENABLED=true`
3. Verify chart quality service is being called
4. Check chart quality thresholds in config

### ML Prediction Always Returns None

**Symptoms**: ML verdict is always None even when chart quality passes

**Solution**:
1. Check if ML model is loaded: `ml_service.model_loaded`
2. Check if chart quality passed: `chart_quality_passed = True`
3. Verify feature extraction is working
4. Check ML model confidence threshold

---

## Best Practices

### 1. Always Enable Chart Quality in Production

```python
# ✅ CORRECT: Chart quality enabled
config.chart_quality_enabled = True

# ❌ WRONG: Chart quality disabled (only for testing)
config.chart_quality_enabled = False
```

### 2. Filter Training Data by Chart Quality

```bash
# Filter training data to match production distribution
python scripts/filter_training_data_by_chart_quality.py \
    --input-file data/ml_training_data.csv \
    --output-file data/ml_training_data_filtered.csv
```

### 3. Use Two-Stage Approach

```python
# ✅ CORRECT: Two-stage approach (automatic in AnalysisService)
service = AnalysisService()  # Automatically uses MLVerdictService if available

# ❌ WRONG: Bypassing chart quality filter
ml_verdict = ml_service.predict(features)  # Without chart quality check
```

### 4. Monitor Chart Quality Filtering

```python
# Log chart quality filtering results
chart_quality = result.get('chart_quality', {})
if not chart_quality.get('passed', True):
    logger.info(f"Stock filtered by chart quality: {chart_quality.get('reason')}")
```

---

## Summary

### Key Points

1. ✅ **Two-stage approach is implemented**: Chart quality → ML model
2. ✅ **Chart quality is always enforced**: Hard filter in production
3. ✅ **ML model only sees good charts**: Matches training distribution
4. ✅ **Automatic in AnalysisService**: No manual configuration needed
5. ✅ **Falls back gracefully**: Rule-based if ML unavailable

### Benefits

- ✅ Distribution match between training and production
- ✅ Improved model accuracy (+2-5%)
- ✅ Better prediction consistency
- ✅ Reduced overfitting risk
- ✅ Production safety (chart quality always enforced)

---

## Related Documentation

- [Chart Quality Usage Guide](CHART_QUALITY_USAGE_GUIDE.md)
- [Chart Quality ML Impact Analysis](../CHART_QUALITY_ML_IMPACT_ANALYSIS.md)
- [ML Integration Guide](../architecture/ML_INTEGRATION_GUIDE.md)




