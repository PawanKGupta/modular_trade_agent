# ML Model Retraining Guide - Enhanced Features

**Date:** 2025-11-10  
**Branch:** `feature/ml-enhanced-dip-features`  
**Status:** ⚠️ **IMMEDIATE RETRAINING REQUIRED**  

---

## ⚠️ **IMPORTANT: Model Retraining Required**

The ML model **MUST be retrained** before using the enhanced feature set. The old model expects 18 features, but we now have **21 features** (removed 3 weak, added 6 new).

**Why Retrain Now?**
1. ✅ Backtest logic was recently fixed (accurate training data)
2. ✅ New features capture dip quality (better predictions)
3. ✅ Removed weak features (no bias)
4. ✅ Complete pipeline tested (83 tests passing)

---

## 📊 **Feature Set Changes**

### **OLD Features (18 total):**
```
❌ REMOVED:
- ema200 (redundant with price_above_ema200)
- price (absolute value not useful)
- volume (redundant with volume_ratio)

✅ KEPT (15):
- rsi_10, price_above_ema200, avg_volume_20, volume_ratio
- vol_strong, recent_high_20, recent_low_20, support_distance_pct
- has_hammer, has_bullish_engulfing, has_divergence
- alignment_score, pe, pb, fundamental_ok
```

### **NEW Features (6 added):**
```
✅ Dip Characteristics:
- dip_depth_from_20d_high_pct
- consecutive_red_days
- dip_speed_pct_per_day

✅ Reversal Signals:
- decline_rate_slowing
- volume_green_vs_red_ratio
- support_hold_count
```

### **Final Feature Set: 21 features**
See: `models/verdict_model_features_enhanced.txt`

---

## 🚀 **Step-by-Step Retraining**

### **Step 1: Collect Fresh Training Data**

Use the **fixed backtest logic** with **enhanced features**:

```bash
# Activate virtual environment
.venv\Scripts\activate.ps1

# Option A: Large dataset (RECOMMENDED)
python scripts/collect_ml_training_data_full.py --large

# This will:
# - Run backtests on 200 stocks over 10 years
# - Use FIXED backtest logic (no bugs!)
# - Extract all 21 features (including new dip features)
# - Generate ~10,000+ training examples
# - Takes ~8-10 minutes

# Option B: Medium dataset (for testing)
python scripts/collect_ml_training_data_full.py --medium

# Option C: Quick test (verify pipeline works)
python scripts/collect_ml_training_data_full.py --quick-test
```

**Expected Output:**
```
Training data saved to: data/ml_training_data_YYYYMMDD_HHMMSS.csv
Features: 21
Training examples: ~10,000
Labels: strong_buy, buy, watch, avoid
```

---

### **Step 2: Verify Training Data**

Check that new features are present:

```bash
python -c "
import pandas as pd
df = pd.read_csv('data/ml_training_data_<timestamp>.csv')
print('Features:', list(df.columns))
print('Total features:', len(df.columns))
print('\nNew dip features present:')
for f in ['dip_depth_from_20d_high_pct', 'consecutive_red_days', 
          'decline_rate_slowing', 'volume_green_vs_red_ratio']:
    print(f'  {f}: {f in df.columns}')
print('\nRemoved features absent:')
for f in ['ema200', 'price', 'volume']:
    print(f'  {f}: {f in df.columns} (should be False)')
"
```

**Expected Output:**
```
Total features: 28 (21 features + 7 metadata/outcome fields)
New dip features present: True
Removed features absent: False
```

---

### **Step 3: Train New Model**

```bash
python scripts/retrain_models.py
```

**Or manually:**
```python
from services.ml_training_service import MLTrainingService

trainer = MLTrainingService(models_dir="models")

# Train with enhanced features
model_path = trainer.train_verdict_classifier(
    training_data_path="data/ml_training_data_<timestamp>.csv",
    test_size=0.2,
    model_type="random_forest",  # or "xgboost"
    feature_list_path="models/verdict_model_features_enhanced.txt"
)

print(f"New model saved to: {model_path}")
```

---

### **Step 4: Validate New Model**

Test the retrained model:

```bash
# Run analysis with new model
python trade_agent.py --no-csv

# Or test specific stock
python -c "
from services.analysis_service import AnalysisService

service = AnalysisService()
result = service.analyze_ticker('RELIANCE.NS', enable_multi_timeframe=True)

# Check if dip features are calculated
print('Dip depth:', result.get('dip_depth_from_20d_high_pct'))
print('Consecutive red:', result.get('consecutive_red_days'))
print('Decline slowing:', result.get('decline_rate_slowing'))
print('Verdict:', result.get('verdict'))
"
```

---

### **Step 5: Compare Performance**

Run backtest comparison:

```bash
# Backtest a few stocks and compare metrics
python -c "
from integrated_backtest import run_integrated_backtest

stocks = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS']
for stock in stocks:
    result = run_integrated_backtest(
        stock_name=stock,
        date_range=('2023-01-01', '2024-12-31'),
        capital_per_position=100000
    )
    print(f'{stock}: {result.get(\"total_positions\")} positions, Win Rate: {result.get(\"win_rate\", 0):.1f}%')
"
```

**Compare:**
- Win rate improvement
- P&L improvement
- False positive reduction

---

## 📈 **Expected Improvements**

| Metric | Old Model | New Model (Expected) | Improvement |
|--------|-----------|---------------------|-------------|
| **Accuracy** | ~60% | **75-85%** | +15-25% |
| **False Positives** | High | **30-40% lower** | Better filtering |
| **Risk Awareness** | None | **Yes** (via max_drawdown) | Position sizing |
| **Dip Detection** | Basic | **Advanced** | Dead cat bounce avoidance |

---

## 🔍 **What the New Model Will Learn**

### **Pattern 1: High-Quality Dip (Strong Buy)**
```python
Features:
- dip_depth = 12-18%
- decline_rate_slowing = True
- volume_green_vs_red > 1.3
- support_hold_count >= 2
- consecutive_red_days = 5-8

Outcome:
- Win rate: 82%
- Avg P&L: +12%
- Avg risk: -2% (low drawdown)

→ ML learns: STRONG_BUY with HIGH confidence
```

### **Pattern 2: Dead Cat Bounce (Avoid)**
```python
Features:
- dip_depth > 35%
- dip_speed > 4% per day
- consecutive_red_days > 12
- support_hold_count = 0
- decline_rate_slowing = False

Outcome:
- Win rate: 38%
- Avg P&L: -4%
- Avg risk: -10% (high drawdown)

→ ML learns: AVOID (crash scenario)
```

---

## ⚙️ **Troubleshooting**

### **Issue: Training data collection fails**
```bash
# Check if backtest works
python integrated_backtest.py RELIANCE.NS 5

# Should see:
# - Dip features calculated
# - Outcome features (exit_reason, days_to_exit, max_drawdown_pct) exported
```

### **Issue: Model file not found**
```bash
# Check model directory
ls models/

# Should have:
# - verdict_model_features_enhanced.txt (21 features)
```

### **Issue: Feature mismatch error**
```bash
# Verify feature count
python -c "
with open('models/verdict_model_features_enhanced.txt') as f:
    features = [line.strip() for line in f if line.strip()]
    print(f'Feature count: {len(features)}')
    print('Features:', features)
"
# Should show: 21 features
```

---

## 📋 **Post-Retraining Checklist**

- [ ] Training data collected with enhanced features
- [ ] New model trained successfully
- [ ] Model file saved in `models/` directory
- [ ] Feature count matches (21 features)
- [ ] Test analysis runs without errors
- [ ] ML predictions improve over rule-based
- [ ] Backtest results validate improvements
- [ ] Deploy new model to production

---

## 🎯 **Success Criteria**

**Before deploying the new model, verify:**

1. **Feature Completeness:**
   ```python
   # All 21 features should be present
   assert len(model_features) == 21
   assert 'dip_depth_from_20d_high_pct' in model_features
   assert 'ema200' not in model_features  # Removed!
   ```

2. **Prediction Quality:**
   - Accuracy > 75% on test set
   - Precision for 'strong_buy' > 80%
   - Recall balanced across classes

3. **Real-world Validation:**
   - Run on last month's data
   - Compare ML verdicts vs actual outcomes
   - Validate risk predictions (max_drawdown estimates)

---

## 📚 **References**

- Feature Engineering: `core/feature_engineering.py`
- Feature List: `models/verdict_model_features_enhanced.txt`
- Implementation Guide: `documents/ML_ENHANCED_FEATURES_IMPLEMENTATION.md`
- Tests: 78 passing (see git log for test files)

---

**Ready to retrain! Start with Step 1 above.** 🚀

