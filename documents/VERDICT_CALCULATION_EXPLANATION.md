# How Trade Agent Calculates Verdict

## Overview

The trade agent uses a **two-stage approach** to determine trading verdicts:

1. **Stage 1: Chart Quality Filter** (Hard Filter) - MUST pass before proceeding
2. **Stage 2: Verdict Determination** - ML Model (if available) OR Rule-Based Logic

## Verdict Types

- **`strong_buy`**: Excellent trading opportunity
- **`buy`**: Good trading opportunity
- **`watch`**: Monitor for better entry
- **`avoid`**: Not a good opportunity

---

## Stage 1: Chart Quality Filter (Hard Filter)

**Location**: `services/chart_quality_service.py`

### Purpose
Filters out stocks with "unclean" daily charts before any other analysis.

### Checks Performed
1. **Gap Analysis**: Detects excessive gaps (up/down) in daily candles
2. **Movement Analysis**: Detects lack of movement (flat charts)
3. **Extreme Candle Analysis**: Detects excessive big red/green candles

### Criteria
- **Chart Cleanliness Score**: Must be >= `chart_quality_min_score` (default: 60)
- **Max Gap Frequency**: Must be < `chart_quality_max_gap_frequency` (default: 0.15 = 15%)
- **Min Daily Range**: Must be >= `chart_quality_min_daily_range_pct` (default: 0.5%)
- **Max Extreme Candle Frequency**: Must be < `chart_quality_max_extreme_candle_frequency` (default: 0.20 = 20%)

### Result
- **If FAILED**: Immediately return `"avoid"` verdict with reason
- **If PASSED**: Proceed to Stage 2

### Configuration
```python
# config/strategy_config.py
chart_quality_enabled = True  # Enable chart quality filtering
chart_quality_min_score = 60  # Minimum cleanliness score (0-100)
chart_quality_max_gap_frequency = 0.15  # Max 15% gaps
chart_quality_min_daily_range_pct = 0.5  # Min 0.5% daily range
chart_quality_max_extreme_candle_frequency = 0.20  # Max 20% extreme candles
```

---

## Stage 2: Verdict Determination

### Option A: ML Model Prediction (If Available)

**Location**: `services/ml_verdict_service.py`

#### Process
1. **Feature Extraction**: Extracts features matching training data format
2. **ML Prediction**: Uses trained model (Random Forest or XGBoost) to predict verdict
3. **Confidence Check**: Only uses ML prediction if confidence > 50%
4. **Fallback**: Falls back to rule-based logic if confidence too low

#### Features Used
- `rsi_10`: RSI(10) value
- `ema200`: EMA(200) value
- `price`: Current price
- `price_above_ema200`: Boolean (1.0 or 0.0)
- `volume`: Current volume
- `avg_volume_20`: 20-day average volume
- `volume_ratio`: Current volume / Average volume
- `vol_strong`: Boolean (1.0 or 0.0)
- `recent_high_20`: 20-day high
- `recent_low_20`: 20-day low
- `support_distance_pct`: Distance to support level
- `has_hammer`: Boolean (1.0 or 0.0)
- `has_bullish_engulfing`: Boolean (1.0 or 0.0)
- `has_divergence`: Boolean (1.0 or 0.0)
- `alignment_score`: Multi-timeframe alignment score
- `pe`: Price-to-Earnings ratio
- `pb`: Price-to-Book ratio
- `fundamental_ok`: Boolean (1.0 or 0.0)

#### ML Model Initialization
- Automatically initialized if ML model file exists at `ml_verdict_model_path`
- Falls back to rule-based logic if model not found or fails to load

### Option B: Rule-Based Logic (Primary or Fallback)

**Location**: `services/verdict_service.py`

#### Core Entry Conditions

1. **RSI Oversold** (Adaptive Threshold):
   - **Above EMA200**: RSI < `rsi_oversold` (default: 30)
   - **Below EMA200**: RSI < `rsi_extreme_oversold` (default: 20)
   - **Reason**: Stocks above EMA200 need less oversold condition (30), while stocks below EMA200 need extreme oversold (20)

2. **Volume Check**:
   - **`vol_ok`**: Volume must be adequate (based on average volume)
   - **`vol_strong`**: Strong volume gets bonus points

3. **Fundamentals Check**:
   - **`fundamental_ok`**: PE ratio must not be negative (negative PE = loss-making company)

#### Verdict Classification Logic

##### Above EMA200 (Uptrend Dip Buying)

**Conditions**: `RSI < 30` AND `vol_ok` AND `fundamental_ok`

- **`strong_buy`**: 
  - `alignment_score >= mtf_alignment_excellent` (default: 80) OR
  - Signal: `"excellent_uptrend_dip"`
  
- **`buy`**:
  - `alignment_score >= mtf_alignment_fair` (default: 60) OR
  - Signals: `"good_uptrend_dip"`, `"fair_uptrend_dip"`, `"hammer"`, `"bullish_engulfing"` OR
  - `vol_strong` OR
  - Default for valid uptrend reversal conditions

##### Below EMA200 (Extreme Oversold Reversal)

**Conditions**: `RSI < 20` AND `vol_ok` AND `fundamental_ok`

- **`buy`**:
  - `alignment_score >= mtf_alignment_good` (default: 70) OR
  - Signals: `"hammer"`, `"bullish_engulfing"`, `"bullish_divergence"` OR
  - `vol_strong`
  
- **`watch`**: Default for below-trend stocks (requires stronger signals)

##### Partial Signals

- **`watch`**: Has some signals and volume but doesn't meet core reversal conditions

##### No Signals

- **`avoid`**: No significant signals or doesn't meet entry conditions

#### Additional Adjustments

1. **News Sentiment Downgrade**:
   - If `news_sentiment.score <= news_sentiment_neg_threshold` (default: -0.3)
   - AND `news_sentiment.used >= 1`
   - Then: Downgrade `buy`/`strong_buy` to `watch`
   - Justification: `"news_negative"`

2. **Candle Quality Downgrade**:
   - Analyzes recent 3 candles
   - May downgrade `buy`/`strong_buy` to `watch` if candle quality is poor
   - Reasons: Poor candle patterns, excessive volatility, etc.

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    START ANALYSIS                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              STAGE 1: Chart Quality Check                    │
│  • Gap Analysis                                              │
│  • Movement Analysis                                         │
│  • Extreme Candle Analysis                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            │                             │
            ▼                             ▼
    ┌───────────────┐           ┌──────────────────┐
    │   FAILED      │           │     PASSED       │
    │               │           │                  │
    │ Return "avoid"│           │  Proceed to      │
    │ with reason   │           │  Stage 2         │
    └───────────────┘           └────────┬─────────┘
                                         │
                                         ▼
                        ┌────────────────────────────────┐
                        │  STAGE 2: Verdict Determination│
                        └────────┬───────────────────────┘
                                 │
                  ┌──────────────┴──────────────┐
                  │                             │
                  ▼                             ▼
        ┌──────────────────┐         ┌─────────────────────┐
        │  ML Model Available?       │  Rule-Based Logic   │
        └────────┬─────────┘         └──────────┬──────────┘
                 │                               │
        ┌────────┴────────┐                      │
        │                 │                      │
        ▼                 ▼                      ▼
   ┌─────────┐      ┌──────────┐         ┌──────────────────┐
   │ Extract │      │ Confidence│         │ Check Entry      │
   │ Features│      │ > 50%?    │         │ Conditions:      │
   └────┬────┘      └─────┬────┘         │ • RSI < 30/20    │
        │                 │               │ • Volume OK       │
        │                 │               │ • Fundamentals OK │
        ▼                 │               └────────┬──────────┘
   ┌─────────┐            │                        │
   │ Predict │            │                        │
   │ Verdict │            │                        │
   └────┬────┘            │                        │
        │                 │                        │
        └────────┬────────┴────────┬───────────────┘
                 │                 │
                 ▼                 ▼
        ┌────────────────────────────────┐
        │   Apply Adjustments:           │
        │   • News Sentiment             │
        │   • Candle Quality             │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   FINAL VERDICT            │
        │   (strong_buy/buy/watch/   │
        │    avoid)                  │
        └────────────────────────────┘
```

---

## Configuration Parameters

### RSI Thresholds
```python
rsi_period = 10  # RSI calculation period
rsi_oversold = 30  # RSI threshold for stocks above EMA200
rsi_extreme_oversold = 20  # RSI threshold for stocks below EMA200
```

### Multi-Timeframe Alignment
```python
mtf_alignment_excellent = 8.0  # Excellent alignment score (0-10 scale)
mtf_alignment_good = 6.0       # Good alignment score (0-10 scale)
mtf_alignment_fair = 4.0       # Fair alignment score (0-10 scale)
```

**Note**: Alignment score is calculated on a 0-10 scale. See [Alignment Score Calculation](ALIGNMENT_SCORE_CALCULATION.md) for detailed explanation.

### News Sentiment
```python
news_sentiment_neg_threshold = -0.3  # Negative sentiment threshold
```

### ML Configuration
```python
ml_enabled = True  # Enable ML prediction
ml_verdict_model_path = "models/verdict_model_random_forest.pkl"  # Model path
ml_confidence_threshold = 0.5  # Minimum confidence for ML prediction
ml_combine_with_rules = False  # Combine ML with rules (future feature)
```

---

## Example Verdict Calculation

### Example 1: Strong Buy (Above EMA200)

**Inputs**:
- RSI = 25 (oversold)
- Price above EMA200 = True
- Volume OK = True
- Volume Strong = True
- Alignment Score = 85
- Fundamental OK = True
- Chart Quality = Passed

**Process**:
1. ✅ Chart Quality: Passed
2. ✅ RSI Check: 25 < 30 (oversold threshold for above EMA200)
3. ✅ Volume Check: OK
4. ✅ Fundamental Check: OK
5. ✅ Alignment Score: 85 >= 80 (excellent)

**Result**: `"strong_buy"`

**Justification**:
- `rsi:25.0(above_ema200)`
- `excellent_uptrend_dip_confirmation`
- `volume_strong`

---

### Example 2: Buy (Below EMA200)

**Inputs**:
- RSI = 18 (extreme oversold)
- Price above EMA200 = False
- Volume OK = True
- Volume Strong = False
- Alignment Score = 75
- Fundamental OK = True
- Chart Quality = Passed
- Signal: `"hammer"`

**Process**:
1. ✅ Chart Quality: Passed
2. ✅ RSI Check: 18 < 20 (extreme oversold threshold for below EMA200)
3. ✅ Volume Check: OK
4. ✅ Fundamental Check: OK
5. ✅ Alignment Score: 75 >= 70 (good) OR Signal: `"hammer"`

**Result**: `"buy"`

**Justification**:
- `rsi:18.0(below_ema200)`
- `pattern:hammer`
- `volume_adequate`

---

### Example 3: Avoid (Chart Quality Failed)

**Inputs**:
- Chart Quality Score = 45 (below threshold of 60)
- Gap Frequency = 0.25 (above threshold of 0.15)

**Process**:
1. ❌ Chart Quality: Failed (Score: 45 < 60, Gaps: 25% > 15%)

**Result**: `"avoid"`

**Justification**:
- `Chart quality failed: Too many gaps (25.0% > 15.0%) or poor cleanliness score (45.0 < 60.0)`

---

### Example 4: Watch (Partial Signals)

**Inputs**:
- RSI = 35 (not oversold)
- Volume OK = True
- Signals: `["hammer"]`
- Fundamental OK = True
- Chart Quality = Passed

**Process**:
1. ✅ Chart Quality: Passed
2. ❌ RSI Check: 35 >= 30 (not oversold)
3. ✅ Volume Check: OK
4. ✅ Has Signals: `["hammer"]`

**Result**: `"watch"`

**Justification**:
- `signals:hammer`
- `partial_reversal_setup`

---

## Key Files

1. **`services/analysis_service.py`**: Main orchestrator
2. **`services/verdict_service.py`**: Rule-based verdict logic
3. **`services/ml_verdict_service.py`**: ML-enhanced verdict logic
4. **`services/chart_quality_service.py`**: Chart quality filtering
5. **`config/strategy_config.py`**: Configuration parameters

---

## Summary

The verdict calculation is a **two-stage process**:

1. **Stage 1**: Chart quality filter (hard filter) - eliminates stocks with poor charts
2. **Stage 2**: Verdict determination - uses ML model (if available) or rule-based logic

**Rule-Based Logic** uses:
- Adaptive RSI thresholds (30 for above EMA200, 20 for below EMA200)
- Volume quality checks
- Fundamental checks
- Multi-timeframe alignment scores
- Pattern signals (hammer, bullish engulfing, etc.)
- News sentiment adjustments
- Candle quality adjustments

**ML Model** (if available):
- Extracts features from current market state
- Predicts verdict with confidence score
- Falls back to rule-based logic if confidence too low

This ensures robust verdict determination with multiple layers of filtering and analysis.

