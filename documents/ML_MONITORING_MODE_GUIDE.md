# ML Monitoring Mode Guide

**Date:** 2025-11-11  
**Status:** ✅ ACTIVE  
**Purpose:** Validate ML model predictions before full production deployment

---

## 📋 **What is ML Monitoring Mode?**

ML Monitoring Mode allows you to see ML predictions **alongside** rule-based verdicts without actually using ML for trading decisions. This provides:

✅ **Safety:** Rule-based verdicts still used for trading (proven, reliable)  
✅ **Validation:** Compare ML vs Rules on real stocks  
✅ **Learning:** Track which approach is more accurate  
✅ **Confidence:** Make informed decision before full ML deployment

---

## 🎯 **How It Works**

### **Analysis Flow:**

```
Stock Analysis
    ↓
[Chart Quality Filter] ← Hard filter
    ↓
[Rule-Based Verdict] ← Used for TRADING ✓
    ↓
[ML Prediction] ← Shown for COMPARISON
    ↓
Telegram Alert:
  Verdict: BUY (rule-based)
  🤖 ML: WATCH 👀 (65% conf)  ← Monitoring only
```

### **Example Telegram Output:**

```
📈 BUY candidates:

1. STARCEMENT.NS:
   Buy (239.13-240.57)
   Target 267.54 (+10.5%)
   Stop 230.00 (-5.0%)
   RSI:29.02
   MTF:7/10
   RR:2.1x
   StrongSupp:0.9% HighRSI VolExh NearSupport
   Capital: ₹200,000
   Chart: 100/100 (clean)
   PE:32.3
   Vol:0.7x
   News:Neu +0.00 (0)
   Backtest: 42/100 (+1.4% return, 100% win, 1 trades)
   Combined Score: 33.1/100
   Confidence: 🟠 Low
   🤖 ML: WATCH 👀 (91% conf)  ← ML MONITORING
```

---

## 🚀 **How to Use**

### **Daily Analysis:**

```bash
# Activate environment
.venv\Scripts\activate.ps1

# Run trade agent with backtest scoring (includes ML monitoring)
python trade_agent.py --backtest
```

**What happens:**
1. Scrapes stocks from ChartInk
2. Analyzes each stock (rule-based)
3. Gets ML prediction for each stock
4. Runs 2-year backtest
5. Sends Telegram with BOTH rule verdict and ML prediction
6. Exports CSV with ML data

### **CSV Data:**

ML predictions are saved in analysis CSVs:

```csv
ticker,verdict,ml_verdict,ml_confidence,...
STARCEMENT.NS,buy,watch,91.2,...
RELIANCE.NS,watch,watch,85.3,...
```

**Fields:**
- `ml_verdict`: ML prediction (strong_buy, buy, watch, avoid)
- `ml_confidence`: ML confidence percentage (0-100)
- `ml_probabilities`: Full probability distribution

---

## 📊 **Monitoring Strategy**

### **Week 1-2: Data Collection**

**Track:**
- How often does ML agree with Rules?
- When they disagree, which is right?
- ML confidence levels for each verdict

**Tool:**
```bash
# Analyze ML agreement rate
Import-Csv analysis_results\bulk_analysis_final_*.csv | 
  Where-Object { $_.ml_verdict -ne '' } |
  Group-Object @{E={if ($_.verdict -eq $_.ml_verdict) {"Agree"} else {"Disagree"}}} |
  Select-Object Name, Count
```

### **Week 3-4: Performance Validation**

**Measure:**
- ML accuracy on actual trade outcomes
- Rule accuracy on actual trade outcomes
- Which approach has better win rate?

**Decision Criteria:**
- If ML accuracy > Rules: Enable ML for production
- If ML accuracy ≈ Rules: Continue monitoring
- If ML accuracy < Rules: Retrain with more data

---

## 🎛️ **How to Enable Full ML Mode**

**After validation period (2-4 weeks), if ML proves accurate:**

### **Step 1: Update ML Verdict Service**

Edit `services/ml_verdict_service.py` (around line 143-196):

**Change FROM (Monitoring Mode):**
```python
# Stage 2: ML model prediction (DISABLED FOR VERDICT - 2025-11-11)
# Currently logging ML predictions for monitoring/comparison only
# Using rule-based logic for actual verdict until fully validated

if self.model_loaded:
    # Get ML prediction for monitoring
    ml_result = self._predict_with_ml(...)
    
    if ml_result:
        # Store but don't use
        ml_prediction_info = {...}

# Use rule-based logic for verdict
verdict, justification = super().determine_verdict(...)
```

**Change TO (Full ML Mode):**
```python
# Stage 2: ML model prediction (ENABLED - Production)
# ML model is validated and ready for production use

if self.model_loaded:
    # Get ML prediction
    ml_result = self._predict_with_ml(...)
    
    if ml_result:
        ml_verdict, ml_confidence, ml_probs = ml_result
        # USE ML prediction for verdict
        return ml_verdict, self._build_ml_justification(ml_verdict)

# Fallback to rules only if ML fails
verdict, justification = super().determine_verdict(...)
```

### **Step 2: Update Documentation**

Update comment in `services/ml_verdict_service.py`:
```python
# ML model prediction (ENABLED FOR PRODUCTION - 2025-XX-XX)
# Model validated with XX% accuracy over X weeks
```

### **Step 3: Test Thoroughly**

```bash
# Test on sample stocks
python trade_agent.py --backtest

# Verify ML verdicts are being used
# Check logs for "ML predicts" messages
```

---

## 📈 **ML Model Stats (Current)**

### **Training Results:**
```
Model: Random Forest Classifier
Accuracy: 72.5%
Training examples: 8,490
Unique positions: 5,540
Re-entry examples: 2,950 (34.7%)
Data span: 10 years (2015-2025)
Cross-validation: GroupKFold (no data leakage)
```

### **Feature Importance (Top 10):**
```
1. dip_depth_from_20d_high_pct:   17.47% 
2. total_fills_in_position:       15.58%
3. support_distance_pct:          10.22%
4. rsi_10:                         5.47%
5. dip_speed_pct_per_day:          5.28%
6. fill_price_vs_initial_pct:     4.98%
7. consecutive_red_days:           4.93%
8. volume_ratio:                   3.88%
9. volume_green_vs_red_ratio:      3.77%
10. avg_volume_20:                 3.48%
```

### **Per-Class Performance:**
```
Label         Precision  Recall  F1     Support
────────────────────────────────────────────────
watch (0-5%)     0.76    0.86   0.80    985  ← Best
avoid (loss)     0.75    0.73   0.74    412  ← Good
buy (5-15%)      0.47    0.32   0.38    252  ← OK
strong_buy       0.58    0.14   0.23     49  ← Rare
```

---

## 🔍 **Troubleshooting**

### **ML prediction not showing in Telegram?**

Check logs for:
```
INFO — ml_verdict_service — ML verdict service: ML predicts 'watch' (XX% confidence)
INFO — analysis_service — TICKER: ✅ ML prediction retrieved
```

If missing, verify:
1. Model file exists: `models/verdict_model_random_forest.pkl`
2. Feature columns file: `models/verdict_model_features_random_forest.txt`
3. No errors in ML prediction extraction

### **ML confidence showing as 1% instead of 91%?**

This was a bug fixed in commit `0a87b1d`. Update to latest code:
```bash
git pull origin feature/ml-enhanced-dip-features
```

### **Re-train model if:**
- Accuracy drops below 65%
- Agreement rate with rules < 50%
- New market conditions emerge
- After 3-6 months (quarterly refresh recommended)

---

## 📝 **Change Log**

### **2025-11-11: Initial Deployment**
- Trained model with 8,490 examples (10 years)
- Implemented monitoring mode
- ML predictions in Telegram & CSV
- 72.5% accuracy achieved
- 893 tests passing

### **Next Update:**
- After 2-4 weeks monitoring
- Performance comparison report
- Decision on full ML enablement

---

**Status:** Model trained, monitoring active, ready for validation period! 🚀

