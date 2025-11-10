# ML Training Workflow - Complete Guide

**Date:** 2025-11-02  
**Status:** Implementation Guide  
**Purpose:** Generate large training dataset and integrate ML verdicts for testing

---

## Overview

This guide shows how to:
1. **Get all NSE stocks** (not just ChartInk suggested ones)
2. **Run backtest on all stocks** to generate large training dataset
3. **Collect training data** from backtest results
4. **Train ML model** for verdict prediction
5. **Integrate ML verdicts** in Telegram notifications (for testing only)

**Key Point:** ML verdicts are included in Telegram for **testing/comparison only**. Rule-based system remains primary.

---

## Step-by-Step Workflow

### Step 1: Get All NSE Stocks

**Script:** `scripts/get_all_nse_stocks.py`

```bash
# Fetch all NSE stocks and save to file
python scripts/get_all_nse_stocks.py --output data/all_nse_stocks.txt

# Or load from existing file if you have one
python scripts/get_all_nse_stocks.py --file data/your_stocks.txt --output data/all_nse_stocks.txt
```

**Output:** `data/all_nse_stocks.txt` - One stock symbol per line (with .NS suffix)

**Note:** Currently uses a predefined list of major NSE stocks. You can:
- Expand the list in the script
- Add NSE website scraping
- Use a complete NSE stock list file

---

### Step 2: Run Bulk Backtest on All Stocks

**Script:** `scripts/bulk_backtest_all_stocks.py`

```bash
# Run backtest on all stocks
python scripts/bulk_backtest_all_stocks.py \
    --stocks-file data/all_nse_stocks.txt \
    --output data/backtest_training_data.csv \
    --years-back 2 \
    --max-stocks 100  # Optional: limit for testing

# With dip mode
python scripts/bulk_backtest_all_stocks.py \
    --stocks-file data/all_nse_stocks.txt \
    --output data/backtest_training_data.csv \
    --years-back 2 \
    --dip-mode
```

**Output:** `data/backtest_training_data.csv` with columns:
- `ticker`: Stock symbol
- `backtest_score`: Backtest score (0-100)
- `total_return_pct`: Total return %
- `win_rate`: Win rate %
- `total_trades`: Number of trades
- `full_results`: Detailed position data (JSON)

**Time:** This can take a while (depends on number of stocks). Each stock takes ~10-30 seconds.

**Tip:** Use `--max-stocks 50` for initial testing.

---

### Step 3: Collect Training Data from Backtest Results

**Script:** `scripts/collect_training_data.py`

```bash
# Collect features and labels from backtest results
python scripts/collect_training_data.py \
    --backtest-file data/backtest_training_data.csv \
    --output data/ml_training_data.csv
```

**What it does:**
1. Loads backtest results
2. For each trade in backtest results:
   - Extracts features at entry date
   - Creates label based on actual P&L outcome
   - Saves training example

**Labels:**
- `strong_buy`: P&L >= 10%
- `buy`: P&L 5-10%
- `watch`: P&L 0-5%
- `avoid`: P&L < 0%

**Output:** `data/ml_training_data.csv` with:
- Features: RSI, EMA, volume ratios, patterns, etc.
- Labels: strong_buy/buy/watch/avoid
- Outcomes: actual P&L, holding days, etc.

---

### Step 4: Train ML Model

**Script:** Create training script or use Python directly

```python
from services.ml_training_service import MLTrainingService

# Initialize trainer
trainer = MLTrainingService(models_dir="models")

# Train verdict classifier
model_path = trainer.train_verdict_classifier(
    training_data_path="data/ml_training_data.csv",
    test_size=0.2,
    model_type="random_forest"
)

print(f"Model saved to: {model_path}")
```

**Or create a script:**

**File:** `scripts/train_ml_model.py`

```python
#!/usr/bin/env python3
"""Train ML model from collected training data"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.ml_training_service import MLTrainingService
from utils.logger import logger

if __name__ == "__main__":
    trainer = MLTrainingService()
    
    training_file = "data/ml_training_data.csv"
    
    if not Path(training_file).exists():
        logger.error(f"Training data not found: {training_file}")
        logger.info("Run collect_training_data.py first")
        sys.exit(1)
    
    logger.info(f"Training ML model from {training_file}...")
    
    model_path = trainer.train_verdict_classifier(
        training_data_path=training_file,
        test_size=0.2,
        model_type="random_forest"
    )
    
    logger.info(f"\n✅ Model trained and saved to: {model_path}")
```

**Run:**
```bash
python scripts/train_ml_model.py
```

**Output:** 
- `models/verdict_model_random_forest.pkl` - Trained model
- `models/verdict_model_random_forest_features.txt` - Feature columns list

---

### Step 5: Use ML Verdicts in Telegram (Testing Only)

**Already implemented!** The system automatically:

1. **Loads ML model** at startup (if available)
2. **Predicts ML verdicts** for each stock during analysis
3. **Includes ML predictions** in Telegram notifications for comparison

**Usage:**
```bash
# Just run trade_agent.py normally
python trade_agent.py --backtest

# ML verdicts will appear in Telegram if model is available
```

**Telegram Output Example:**
```
1. RELIANCE.NS:
   Buy (2450.00-2500.00)
   Target 2650.00 (+8.5%)
   Stop 2300.00 (-6.5%)
   RSI:25.5
   MTF:8/10
   RR:1.3x
   ...
   🤖 ML Prediction: 🤖📈 BUY (confidence: 72%)
```

**Key Points:**
- ✅ ML verdicts are **additive only** (don't replace rule-based)
- ✅ Rule-based verdict remains **primary** for actual trading decisions
- ✅ ML verdicts shown in Telegram for **testing/comparison**
- ✅ System works **even if ML model is unavailable** (fallback to rules only)

---

## Complete Workflow Example

### 1. Initial Setup (One-time)
```bash
# Get all NSE stocks
python scripts/get_all_nse_stocks.py --output data/all_nse_stocks.txt
```

### 2. Generate Training Data (Run periodically)
```bash
# Step 1: Run bulk backtest
python scripts/bulk_backtest_all_stocks.py \
    --stocks-file data/all_nse_stocks.txt \
    --output data/backtest_training_data.csv \
    --years-back 2 \
    --max-stocks 500  # Start with subset, expand later

# Step 2: Collect training data
python scripts/collect_training_data.py \
    --backtest-file data/backtest_training_data.csv \
    --output data/ml_training_data.csv

# Step 3: Train model
python scripts/train_ml_model.py
```

### 3. Use ML Verdicts (Testing)
```bash
# Run normal analysis - ML verdicts will be included in Telegram
python trade_agent.py --backtest
```

---

## Training Data Scale

### Expected Data Sizes

**For 100 stocks:**
- ~500-1000 training examples (depends on number of trades per stock)
- Good for initial model training

**For 500 stocks:**
- ~2500-5000 training examples
- Better model performance

**For 2000+ stocks:**
- ~10,000-20,000 training examples
- Excellent model performance

**Recommendation:** Start with 100-200 stocks for initial testing, then expand.

---

## Model Performance Expectations

### Initial Model (100 stocks)
- Accuracy: ~60-70%
- Good enough for testing/comparison
- Will improve with more data

### Good Model (500 stocks)
- Accuracy: ~70-80%
- Useful for comparison
- Can start considering ML suggestions

### Excellent Model (2000+ stocks)
- Accuracy: ~80-90%
- Strong predictive power
- Can consider making ML primary (with human oversight)

---

## Next Steps

### Immediate
1. ✅ Get all NSE stocks
2. ✅ Run bulk backtest (start with subset)
3. ✅ Collect training data
4. ✅ Train initial model
5. ✅ Test ML verdicts in Telegram

### Future Enhancements
1. **Retrain periodically** as new backtest data arrives
2. **Expand feature set** (add more indicators)
3. **Try different models** (XGBoost, Neural Networks)
4. **A/B testing** - Compare rule-based vs ML performance
5. **Gradually increase ML influence** based on performance

---

## Troubleshooting

### Issue: No ML verdicts in Telegram
**Solution:** Check if model file exists:
```bash
ls models/verdict_model_random_forest.pkl
```
If not, run training first.

### Issue: ML model not loading
**Solution:** Check if scikit-learn is installed:
```bash
pip install scikit-learn joblib
```

### Issue: Training data has too few examples
**Solution:** 
- Run backtest on more stocks
- Check backtest results have trades (some stocks may have no trades)

### Issue: Model accuracy is low
**Solution:**
- Add more training data (more stocks)
- Check feature extraction (some features may be missing)
- Try different model types (XGBoost, Neural Networks)

---

## Summary

✅ **Get all NSE stocks** → `scripts/get_all_nse_stocks.py`
✅ **Run bulk backtest** → `scripts/bulk_backtest_all_stocks.py`
✅ **Collect training data** → `scripts/collect_training_data.py`
✅ **Train ML model** → `scripts/train_ml_model.py` (or directly)
✅ **Use in Telegram** → Already integrated! Just run `trade_agent.py`

**ML verdicts appear in Telegram automatically for testing/comparison!**

---

**Ready to start?** Begin with Step 1: Get all NSE stocks!
