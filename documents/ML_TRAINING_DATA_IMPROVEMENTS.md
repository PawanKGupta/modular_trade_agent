# ML Training Data - Assessment & Improvements

**Date:** 2025-11-12  
**Your Current Accuracy:** 72.5%  
**Training Examples:** 8,490 (5,540 unique positions)

---

## ✅ **What You're Doing RIGHT** (Excellent!)

### **1. Re-entry Handling with Quantity Weighting** ⭐⭐⭐
```python
fill_quantity = float(fill.get('quantity', 0))
if total_quantity > 0:
    features['sample_weight'] = fill_quantity / total_quantity
```
**Why this is great:** Most beginners ignore re-entries entirely! You're properly weighting by share contribution to P&L. This is advanced.

### **2. GroupKFold Cross-Validation** ⭐⭐⭐
Using `position_id` to prevent data leakage is **critical** and you got it right:
```python
position_id = f"{ticker}_{initial_date_str.replace('-', '')}"
```
**Why this matters:** Prevents the model from seeing multiple fills from same position in both train and test sets.

### **3. Removed Absolute Values** ⭐⭐
```python
# REMOVED: price (absolute price not useful for ML)
# REMOVED: volume (absolute volume redundant with volume_ratio)
```
**Why this is smart:** Absolute prices create false patterns. A ₹100 stock isn't inherently different from ₹1000 stock.

### **4. Long Time Span (10 Years)** ⭐⭐
Captures multiple market cycles: bull markets, bear markets, corrections, recoveries.

### **5. Rich Feature Set** ⭐
Dip features, support/resistance, volume analysis, fundamentals - comprehensive!

---

## ⚠️ **CRITICAL ISSUES** (Must Fix!)

### **🔴 1. Look-Ahead Bias - CRITICAL!**

**Current Code:**
```python
df = data_service.fetch_single_timeframe(
    ticker=ticker,
    end_date=entry_date,  # ← This INCLUDES entry_date!
    add_current_day=False
)

# Get latest row (entry date)
last = df.iloc[-1]  # ← Using data FROM entry_date
```

**Problem:** You're extracting features using data from the **fill date itself**. In real trading, you decide to buy BEFORE the day ends. You don't know:
- Today's close price
- Today's volume
- Today's high/low

**Impact on Accuracy:**  
- Your 72.5% accuracy is **overstated**
- Real-world accuracy will be **lower** (maybe 65-68%)
- Model has seen "future" information during training

**Fix:**
```python
# Option 1: Use previous day's close
entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d')
lookback_date = (entry_datetime - timedelta(days=1)).strftime('%Y-%m-%d')

df = data_service.fetch_single_timeframe(
    ticker=ticker,
    end_date=lookback_date,  # ← Day BEFORE fill
    add_current_day=False
)

# Option 2: Use entry_date but only pre-market data (if available)
# For Indian market, this means using previous day's data
```

**Testing the fix:**
```bash
# Re-collect training data with 1-day offset
python scripts/collect_training_data.py \
    --backtest-file backtest_results.csv \
    --output-file data/ml_training_data_no_lookahead.csv \
    --lookback-days 1  # New parameter
```

**Expected outcome:** Accuracy may drop to 68-70%, but it will be **REAL** accuracy you'll see in live trading.

---

### **🟡 2. Market Regime Features - HIGH IMPACT**

**Current:** You only look at the stock in isolation.

**Problem:** A stock with RSI=25 behaves differently in:
- Bull market (bounces quickly) vs
- Bear market (keeps falling)

**Add these features:**
```python
def add_market_regime_features(df, entry_date):
    """Add features about overall market condition"""
    
    # Fetch Nifty 50 data up to entry_date
    nifty_df = fetch_index_data('NIFTY50', end_date=entry_date)
    
    features = {}
    
    # 1. Nifty trend (most important!)
    nifty_sma_20 = nifty_df['close'].tail(20).mean()
    nifty_sma_50 = nifty_df['close'].tail(50).mean()
    nifty_last = nifty_df['close'].iloc[-1]
    
    features['nifty_above_sma20'] = bool(nifty_last > nifty_sma_20)
    features['nifty_above_sma50'] = bool(nifty_last > nifty_sma_50)
    features['nifty_trend'] = 'bullish' if (nifty_last > nifty_sma_20 > nifty_sma_50) else \
                             'bearish' if (nifty_last < nifty_sma_20 < nifty_sma_50) else 'neutral'
    
    # 2. India VIX (fear gauge)
    # High VIX = high volatility/fear
    vix_df = fetch_index_data('INDIAVIX', end_date=entry_date)
    current_vix = vix_df['close'].iloc[-1]
    avg_vix_20 = vix_df['close'].tail(20).mean()
    
    features['vix_level'] = float(current_vix)
    features['vix_above_average'] = bool(current_vix > avg_vix_20)
    features['vix_elevated'] = bool(current_vix > 20)  # High fear
    
    # 3. Sector relative strength
    # (If stock is TECHM.NS, compare to NIFTY IT)
    sector_index = get_sector_index(ticker)  # Map stock to sector
    sector_df = fetch_index_data(sector_index, end_date=entry_date)
    
    # Sector vs Nifty relative strength
    sector_return_5d = (sector_df['close'].iloc[-1] / sector_df['close'].iloc[-5] - 1) * 100
    nifty_return_5d = (nifty_df['close'].iloc[-1] / nifty_df['close'].iloc[-5] - 1) * 100
    
    features['sector_outperforming'] = bool(sector_return_5d > nifty_return_5d)
    features['sector_relative_strength'] = float(sector_return_5d - nifty_return_5d)
    
    return features
```

**Expected Impact:** Could improve accuracy by 3-5% (to 75-77%).

---

### **🟡 3. Time-Based Features - MEDIUM IMPACT**

**Pattern:** Some days/months are better for reversals than others.

**Add:**
```python
def add_time_features(entry_date_str):
    """Add temporal features"""
    entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d')
    
    return {
        'day_of_week': entry_date.weekday(),  # 0=Monday, 4=Friday
        'is_monday': entry_date.weekday() == 0,  # Monday effect
        'is_friday': entry_date.weekday() == 4,  # Friday effect
        'month': entry_date.month,
        'quarter': (entry_date.month - 1) // 3 + 1,
        'is_q4': (entry_date.month >= 10),  # Oct-Dec (earnings season)
        'is_month_end': (entry_date.day >= 25),  # Window dressing
        'is_quarter_end': (entry_date.month in [3, 6, 9, 12] and entry_date.day >= 25)
    }
```

**Why:** 
- Mondays often see follow-through from weekend sentiment
- Quarter-end sees institutional rebalancing
- Earnings season creates more volatility

**Expected Impact:** 1-2% accuracy improvement.

---

## 🟢 **NICE-TO-HAVE Improvements**

### **4. Feature Interactions**

**Current:** Features are independent.  
**Better:** Some combinations are powerful:

```python
# Add interaction features
features['rsi_volume_interaction'] = features['rsi_10'] * features['volume_ratio']
features['dip_depth_with_support'] = features['dip_depth_from_20d_high_pct'] * features['support_distance_pct']
features['extreme_dip_high_volume'] = bool(
    features['dip_depth_from_20d_high_pct'] > 10 and features['volume_ratio'] > 1.5
)
```

---

### **5. Rolling Features (Momentum)**

**Add change over time:**
```python
# RSI momentum
rsi_current = df['rsi10'].iloc[-1]
rsi_5d_ago = df['rsi10'].iloc[-5]
features['rsi_momentum'] = rsi_current - rsi_5d_ago  # Rising or falling?

# Volume trend
vol_last_5d = df['volume'].tail(5).mean()
vol_prev_5d = df['volume'].iloc[-10:-5].mean()
features['volume_expanding'] = bool(vol_last_5d > vol_prev_5d * 1.2)
```

---

### **6. Feature Normalization**

**Check if you're normalizing:**
```python
from sklearn.preprocessing import StandardScaler

# In your training script
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
```

**Why:** Features like `dip_depth_from_20d_high_pct` (-20%) and `rsi_10` (25) are on different scales. Tree-based models (Random Forest) don't need it, but it can help.

---

### **7. Class Imbalance Handling**

**Check your label distribution:**
```python
import pandas as pd
df = pd.read_csv('data/ml_training_data.csv')
print(df['label'].value_counts())
```

**If imbalanced:**
```python
from imblearn.over_sampling import SMOTE

# Over-sample minority classes
smote = SMOTE(random_state=42)
X_resampled, y_resampled = smote.fit_resample(X_train, y_train)
```

---

### **8. Outcome Window Clarity**

**Current labeling:**
```python
if pnl_pct_value >= 10:
    label = 'strong_buy'
elif pnl_pct_value >= 5:
    label = 'buy'
```

**Question:** What about positions that exited after 1 day vs 30 days?
- +10% in 3 days = excellent
- +10% in 60 days = mediocre

**Enhancement:**
```python
# Consider return RATE (annualized or per-day)
daily_return = pnl_pct_value / holding_days if holding_days > 0 else 0

if daily_return > 0.5:  # >0.5%/day = 150%+ annualized!
    label = 'strong_buy'
elif daily_return > 0.3:  # >0.3%/day = 90%+ annualized
    label = 'buy'
elif daily_return > 0:
    label = 'watch'
else:
    label = 'avoid'
```

---

### **9. Survivorship Bias Check**

**Question:** Are you including **delisted stocks**?

If not, your model learns patterns from "survivors" only, which creates optimistic bias.

**Fix:** Include historical data from stocks that were delisted/merged.

---

### **10. Time-Series Cross-Validation**

**Current:** GroupKFold prevents position leakage ✓

**Enhancement:** Also ensure no temporal leakage:
```python
from sklearn.model_selection import TimeSeriesSplit

# Sort by entry_date first
df_sorted = df.sort_values('entry_date')

# Then use TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)

for train_index, test_index in tscv.split(df_sorted):
    X_train, X_test = X[train_index], X[test_index]
    # Train and validate
```

This ensures training always happens on older data, testing on newer data.

---

## 📊 **Priority Ranking**

| Priority | Issue | Expected Impact | Effort |
|----------|-------|----------------|--------|
| 🔴 **1** | Fix look-ahead bias | -2 to -4% accuracy (but REAL) | Medium |
| 🟡 **2** | Add market regime features | +3 to +5% accuracy | High |
| 🟡 **3** | Add time features | +1 to +2% accuracy | Low |
| 🟢 **4** | Feature interactions | +1% accuracy | Low |
| 🟢 **5** | Outcome rate vs absolute | +1 to +2% accuracy | Medium |
| 🟢 **6** | Time-series CV | Better generalization | Medium |

---

## 🎯 **Recommended Action Plan**

### **Phase 1: Critical Fixes (Week 1)**
1. ✅ Fix look-ahead bias (use day-before data)
2. ✅ Re-collect training data
3. ✅ Re-train model
4. ✅ Compare old vs new accuracy (expect drop to 68-70%)

### **Phase 2: Market Context (Week 2-3)**
1. ✅ Add Nifty 50 trend features
2. ✅ Add VIX features
3. ✅ Re-train and test (expect improvement to 73-75%)

### **Phase 3: Refinements (Week 4)**
1. ✅ Add time-based features
2. ✅ Add feature interactions
3. ✅ Implement time-series CV
4. ✅ Final model (target 75-78% accuracy)

---

## 💡 **Bottom Line**

### **You're doing better than 80% of ML beginners!**

**Strengths:**
- ✅ Re-entry handling (advanced!)
- ✅ GroupKFold (prevents leakage)
- ✅ Removed bad features
- ✅ Long time span

**Critical fixes needed:**
- 🔴 Look-ahead bias (your 72.5% is optimistic)
- 🟡 Market regime (huge missing context)

**After fixes:**
- Expect 68-70% accuracy initially (but REAL accuracy)
- Then improve to 75-78% with market features
- This will match your live trading performance

---

## 📚 **Learning Resources**

1. **Look-ahead bias:** https://www.kaggle.com/code/alexisbcook/data-leakage
2. **Time-series CV:** https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split
3. **Feature engineering:** "Feature Engineering for Machine Learning" by Alice Zheng

---

**Your current approach is solid! Fix the look-ahead bias first, then add market context. You're on the right track!** 🚀

