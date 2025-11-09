# Alignment Score Calculation

## Overview

The **Alignment Score** is a multi-timeframe analysis metric that evaluates how well daily and weekly chart conditions align for a dip-buying opportunity. It ranges from **0 to 10**, where higher scores indicate better setup quality.

**Location**: `core/timeframe_analysis.py` - `get_dip_buying_alignment_score()`

---

## Score Components

The alignment score is calculated by combining 6 components:

### 1. Daily Oversold Condition (3 points max) - PRIMARY SIGNAL

**Weight**: 3 points (highest weight)

**Scoring**:
- **Extreme Oversold** (RSI < 20): **+3 points**
- **High Oversold** (RSI < 30): **+2 points**
- **Moderate Oversold** (RSI approaching oversold): **+1 point**
- **Not Oversold**: **+0 points**

**Rationale**: The daily RSI oversold condition is the primary entry signal for the dip-buying strategy. Extreme oversold (RSI < 20) gets the highest score as it indicates strong mean reversion potential.

**Configuration**:
- RSI threshold: `config.rsi_oversold` (default: 30)
- Extreme oversold: `config.rsi_extreme_oversold` (default: 20)

---

### 2. Weekly Uptrend Context (2 points max)

**Weight**: 2 points

**Scoring**:
- **Weekly in Uptrend** (`above_ema_uptrend` in weekly reversion reasons): **+2 points**
  - Best case: Weekly timeframe also in uptrend - perfect setup
- **Weekly Pullback** (moderate/high oversold in weekly): **+1 point**
  - Temporary weekly pullback in an uptrend
- **Weekly Support Holding** (strong/moderate support): **+1 point**
  - Support holding in uptrend context

**Rationale**: Weekly timeframe provides the broader trend context. If the weekly timeframe is in an uptrend, a daily dip becomes a much better buying opportunity (buy the dip in an uptrend).

**Conditions Checked**:
- Weekly oversold analysis severity
- Weekly support analysis quality
- Weekly reversion setup reasons

---

### 3. Support Level Confluence (2 points max)

**Weight**: 2 points

**Scoring**:
- **Very Close to Strong Support** (quality = 'strong' AND distance <= 3%): **+2 points**
- **Close to Good Support** (quality = 'strong'/'moderate' AND distance <= 5%): **+1 point**
- **Far from Support**: **+0 points**

**Rationale**: Support levels act as price floors. When price is close to a strong support level, the risk of further downside is reduced, making it a safer entry point.

**Support Analysis**:
- Looks at recent lows (default: 20 days for daily, 50 weeks for weekly)
- Calculates distance from current price to nearest support
- Assesses support strength based on:
  - Number of times support was tested
  - How recent the support level is
  - Whether price is holding above support

**Configuration**:
- Daily support lookback: `config.support_resistance_lookback_daily` (default: 20)
- Weekly support lookback: `config.support_resistance_lookback_weekly` (default: 50)

---

### 4. Volume Exhaustion Signals (2 points max)

**Weight**: 2 points

**Scoring**:
- **Strong Volume Exhaustion** (combined daily + weekly exhaustion_score >= 3): **+2 points**
- **Some Volume Exhaustion** (combined exhaustion_score >= 1): **+1 point**
- **No Volume Exhaustion**: **+0 points**

**Rationale**: Volume exhaustion indicates that selling pressure is drying up, which is a positive sign for reversal. The score combines daily and weekly volume exhaustion signals.

**Volume Exhaustion Analysis**:
- **Low volume on down days**: Selling drying up
- **Declining volume trend**: Volume decreasing over time
- **Very low current volume**: Volume ratio < 0.6x average

**Volume Exhaustion Score** (per timeframe):
- Each exhaustion signal adds +1 to exhaustion_score
- Maximum exhaustion_score per timeframe: 3 (if all signals present)

**Configuration**:
- Daily volume lookback: `config.volume_exhaustion_lookback_daily` (default: 10)
- Weekly volume lookback: `config.volume_exhaustion_lookback_weekly` (default: 20)

---

### 5. Selling Pressure Exhaustion (1 point max)

**Weight**: 1 point

**Scoring**:
- **Selling Pressure Exhausted** (daily selling exhaustion_score >= 1): **+1 point**
- **No Exhaustion**: **+0 points**

**Rationale**: Selling pressure exhaustion indicates that bearish momentum is weakening, which is favorable for reversal.

**Selling Pressure Analysis**:
- **Consecutive down days**: Counts consecutive red candles
- **Decline magnitude**: Percentage decline over recent period
- **Weakening decline**: Higher lows pattern (bearish momentum weakening)
- **Shallow final day**: Last down day not very deep (exhaustion sign)

**Exhaustion Signs**:
- **Higher low**: Price making higher low (momentum weakening)
- **Shallow final day**: Last down day not deep (selling exhausted)

**Exhaustion Score**:
- Each exhaustion sign adds +1 to exhaustion_score
- Maximum exhaustion_score: 2 (if all signs present)

---

### 6. Reversion Setup Quality Bonus (1 point max)

**Weight**: 1 point

**Scoring**:
- **Excellent/Good Reversion Setup** (daily reversion quality in ['excellent', 'good']): **+1 point**
- **Fair/Poor Setup**: **+0 points**

**Rationale**: Overall mean reversion setup quality provides additional confirmation. Excellent or good setups get a bonus point.

**Reversion Setup Analysis**:
- Assesses overall mean reversion setup quality
- Considers:
  - RSI oversold condition
  - Support level proximity
  - Volume exhaustion
  - Price action patterns

**Quality Levels**:
- **Excellent**: Strong oversold + support + volume exhaustion
- **Good**: Good oversold + support/volume signals
- **Fair**: Moderate setup
- **Poor**: Weak setup

---

## Complete Calculation Flow

```
Alignment Score = 0 (initial)

1. Daily Oversold Condition (0-3 points)
   ├─ Extreme (RSI < 20): +3
   ├─ High (RSI < 30): +2
   └─ Moderate: +1

2. Weekly Uptrend Context (0-2 points)
   ├─ Weekly in Uptrend: +2
   ├─ Weekly Pullback: +1
   └─ Weekly Support: +1

3. Support Level Confluence (0-2 points)
   ├─ Very Close to Strong Support: +2
   └─ Close to Good Support: +1

4. Volume Exhaustion (0-2 points)
   ├─ Strong (score >= 3): +2
   └─ Some (score >= 1): +1

5. Selling Pressure Exhaustion (0-1 point)
   └─ Exhausted (score >= 1): +1

6. Reversion Setup Quality (0-1 point)
   └─ Excellent/Good: +1

Total Score = min(sum of all components, 10)
```

---

## Alignment Score to Confirmation Mapping

The alignment score is mapped to confirmation levels:

### With Weekly Analysis (Full MTF)

| Alignment Score | Confirmation Level | Description |
|----------------|-------------------|-------------|
| **>= 8** | `excellent_uptrend_dip` | RSI < 30 + strong uptrend + support |
| **>= 6** | `good_uptrend_dip` | RSI < 30 + uptrend context |
| **>= 4** | `fair_uptrend_dip` | RSI < 30 + some uptrend signs |
| **>= 2** | `weak_uptrend_dip` | Marginal uptrend dip |
| **< 2** | `poor_uptrend_dip` | Avoid - not in uptrend |

### Without Weekly Analysis (Daily Only)

| Alignment Score | Confirmation Level | Description |
|----------------|-------------------|-------------|
| **>= 5** | `good_uptrend_dip` | Daily-only good setup |
| **>= 3** | `fair_uptrend_dip` | Daily-only fair setup |
| **>= 1** | `weak_uptrend_dip` | Daily-only weak setup |
| **< 1** | `poor_uptrend_dip` | Poor daily setup |

**Note**: Thresholds are lower when weekly analysis is unavailable, as daily-only analysis is less comprehensive.

---

## Usage in Verdict Determination

The alignment score is used in verdict determination:

### Rule-Based Logic

**Location**: `services/verdict_service.py` - `determine_verdict()`

**Above EMA200** (Uptrend Dip Buying):
- **`strong_buy`**: `alignment_score >= mtf_alignment_excellent` (default: 8) OR `"excellent_uptrend_dip"` signal
- **`buy`**: `alignment_score >= mtf_alignment_fair` (default: 4) OR pattern signals OR `vol_strong`

**Below EMA200** (Extreme Oversold Reversal):
- **`buy`**: `alignment_score >= mtf_alignment_good` (default: 6) OR pattern signals OR `vol_strong`
- **`watch`**: Default (requires stronger signals)

**Configuration**:
```python
mtf_alignment_excellent = 8.0  # Excellent alignment (strong_buy threshold)
mtf_alignment_good = 6.0       # Good alignment (buy threshold for below EMA200)
mtf_alignment_fair = 4.0       # Fair alignment (buy threshold for above EMA200)
```

---

## Example Calculations

### Example 1: Excellent Setup (Score: 9)

**Inputs**:
- Daily RSI: 18 (extreme oversold)
- Weekly: In uptrend (`above_ema_uptrend`)
- Support: Strong support at 3% distance
- Volume Exhaustion: Daily score = 2, Weekly score = 2 (combined = 4)
- Selling Pressure: Exhaustion score = 1
- Reversion Setup: Excellent

**Calculation**:
```
1. Daily Oversold: 18 < 20 → Extreme → +3 points
2. Weekly Uptrend: above_ema_uptrend → +2 points
3. Support Confluence: Strong support at 3% → +2 points
4. Volume Exhaustion: Combined score 4 >= 3 → +2 points
5. Selling Pressure: Exhaustion score 1 >= 1 → +1 point
6. Reversion Setup: Excellent → +1 point

Total: 3 + 2 + 2 + 2 + 1 + 1 = 11
Capped: min(11, 10) = 10
```

**Result**: Alignment Score = **10** → `excellent_uptrend_dip`

---

### Example 2: Good Setup (Score: 6)

**Inputs**:
- Daily RSI: 28 (high oversold)
- Weekly: Pullback in uptrend (moderate oversold)
- Support: Moderate support at 4% distance
- Volume Exhaustion: Daily score = 1, Weekly score = 1 (combined = 2)
- Selling Pressure: Exhaustion score = 0
- Reversion Setup: Good

**Calculation**:
```
1. Daily Oversold: 28 < 30 → High → +2 points
2. Weekly Uptrend: Moderate oversold → +1 point
3. Support Confluence: Moderate support at 4% → +1 point
4. Volume Exhaustion: Combined score 2 >= 1 → +1 point
5. Selling Pressure: Exhaustion score 0 → +0 points
6. Reversion Setup: Good → +1 point

Total: 2 + 1 + 1 + 1 + 0 + 1 = 6
```

**Result**: Alignment Score = **6** → `good_uptrend_dip`

---

### Example 3: Fair Setup (Score: 4)

**Inputs**:
- Daily RSI: 32 (moderate oversold)
- Weekly: Support holding (moderate support)
- Support: Moderate support at 6% distance
- Volume Exhaustion: Daily score = 1, Weekly score = 0 (combined = 1)
- Selling Pressure: Exhaustion score = 0
- Reversion Setup: Fair

**Calculation**:
```
1. Daily Oversold: 32 → Moderate → +1 point
2. Weekly Uptrend: Support holding → +1 point
3. Support Confluence: Moderate support at 6% → +0 points (too far)
4. Volume Exhaustion: Combined score 1 >= 1 → +1 point
5. Selling Pressure: Exhaustion score 0 → +0 points
6. Reversion Setup: Fair → +0 points

Total: 1 + 1 + 0 + 1 + 0 + 0 = 3
```

**Result**: Alignment Score = **3** → `fair_uptrend_dip` (with weekly) or `weak_uptrend_dip` (daily-only)

---

### Example 4: Poor Setup (Score: 1)

**Inputs**:
- Daily RSI: 45 (not oversold)
- Weekly: Not in uptrend
- Support: Weak support at 10% distance
- Volume Exhaustion: Daily score = 0, Weekly score = 0 (combined = 0)
- Selling Pressure: Exhaustion score = 0
- Reversion Setup: Poor

**Calculation**:
```
1. Daily Oversold: 45 → Not oversold → +0 points
2. Weekly Uptrend: Not in uptrend → +0 points
3. Support Confluence: Weak support at 10% → +0 points
4. Volume Exhaustion: Combined score 0 → +0 points
5. Selling Pressure: Exhaustion score 0 → +0 points
6. Reversion Setup: Poor → +0 points

Total: 0 + 0 + 0 + 0 + 0 + 0 = 0
```

**Result**: Alignment Score = **0** → `poor_uptrend_dip`

---

## Key Files

1. **`core/timeframe_analysis.py`**: 
   - `get_dip_buying_alignment_score()`: Main calculation method
   - `get_dip_buying_confirmation()`: Maps score to confirmation level
   - `analyze_dip_conditions()`: Analyzes daily/weekly conditions
   - `_analyze_oversold_conditions()`: Analyzes RSI oversold
   - `_analyze_support_levels()`: Analyzes support levels
   - `_analyze_volume_exhaustion()`: Analyzes volume exhaustion
   - `_analyze_selling_pressure()`: Analyzes selling pressure
   - `_analyze_reversion_setup()`: Analyzes reversion setup quality

2. **`services/verdict_service.py`**: 
   - Uses alignment score in verdict determination
   - Applies thresholds: `mtf_alignment_excellent`, `mtf_alignment_good`, `mtf_alignment_fair`

3. **`config/strategy_config.py`**: 
   - Configuration parameters for alignment score thresholds
   - Support/resistance lookback periods
   - Volume exhaustion lookback periods
   - RSI thresholds

---

## Configuration Parameters

```python
# RSI Thresholds
rsi_oversold = 30.0           # Daily RSI threshold for oversold
rsi_extreme_oversold = 20.0   # Daily RSI threshold for extreme oversold
weekly_oversold_threshold = 40.0  # Weekly RSI threshold (hardcoded)

# Support/Resistance Lookback
support_resistance_lookback_daily = 20   # Daily support lookback (days)
support_resistance_lookback_weekly = 50  # Weekly support lookback (weeks)

# Volume Exhaustion Lookback
volume_exhaustion_lookback_daily = 10    # Daily volume lookback (days)
volume_exhaustion_lookback_weekly = 20   # Weekly volume lookback (weeks)

# Alignment Score Thresholds
mtf_alignment_excellent = 8.0  # Excellent alignment (strong_buy)
mtf_alignment_good = 6.0       # Good alignment (buy for below EMA200)
mtf_alignment_fair = 4.0       # Fair alignment (buy for above EMA200)
```

---

## Summary

The **Alignment Score** is a comprehensive multi-timeframe metric that evaluates:

1. **Daily Oversold Condition** (3 points) - Primary signal
2. **Weekly Uptrend Context** (2 points) - Trend confirmation
3. **Support Level Confluence** (2 points) - Risk management
4. **Volume Exhaustion Signals** (2 points) - Momentum exhaustion
5. **Selling Pressure Exhaustion** (1 point) - Bearish momentum weakening
6. **Reversion Setup Quality** (1 point) - Overall setup quality

**Total**: 0-10 points (capped at 10)

**Higher scores** indicate better dip-buying opportunities with:
- Strong oversold conditions
- Uptrend context (weekly)
- Support level confluence
- Volume exhaustion
- Selling pressure exhaustion
- Good reversion setup quality

The alignment score is used to determine verdicts (`strong_buy`, `buy`, `watch`, `avoid`) and confirmation levels (`excellent_uptrend_dip`, `good_uptrend_dip`, `fair_uptrend_dip`, `weak_uptrend_dip`, `poor_uptrend_dip`).

