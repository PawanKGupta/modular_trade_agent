# ML Integration - Complete Guide

**Last Updated:** 2025-12-14
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Training Data Collection](#training-data-collection)
4. [Model Training](#model-training)
5. [Integration](#integration)
6. [Advanced Features](#advanced-features)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

Integrate AI/ML capabilities into the trading agent system to enhance verdict prediction and improve trading decisions.

### Key ML Opportunities

1. **Verdict Prediction** - Enhance rule-based buy/sell logic
2. **Price Target Prediction** - Smarter target calculation
3. **Stop Loss Optimization** - Better risk management
4. **Entry/Exit Timing** - Optimize when to enter/exit
5. **Pattern Recognition** - Enhance existing rule-based patterns
6. **Risk/Reward Prediction** - Predict optimal risk/reward ratios

### Current System Foundation

- ✅ Rich feature data (indicators, patterns, volume, fundamentals)
- ✅ Historical analysis results (training data)
- ✅ Backtest results with actual outcomes (labeled data)
- ✅ Pipeline architecture (easy ML step insertion)
- ✅ Event-driven system (ML training triggers)

---

## Quick Start

### One-Command Training Data Collection

```bash
# RECOMMENDED: Large dataset for good model accuracy
python scripts/collect_ml_training_data_full.py --large
```

This will:
1. Fetch all NSE stocks
2. Run backtests on 200 stocks over 10 years
3. Extract features and create training dataset
4. Generate ~10,000+ training examples

**Estimated Time:** ~7-10 minutes

### Train Model

```bash
python scripts/train_ml_model.py \
  --training-file data/ml_training_data_TIMESTAMP.csv \
  --model-type random_forest
```

### Use in Production

ML verdicts automatically appear in:
- Telegram notifications
- Analysis results
- Console output

---

## Training Data Collection

### Preset Modes (Recommended)

| Mode | Command | Stocks | Years | Examples | Time | Best For |
|------|---------|--------|-------|----------|------|----------|
| **Quick Test** | `--quick-test` | 10 | 2 | ~50 | 30s | Testing pipeline |
| **Small** | `--small` | 50 | 3 | ~500 | 2min | Quick iteration |
| **Medium** | `--medium` | 100 | 5 | ~2,000 | 4min | Initial training |
| **Large** ⭐ | `--large` | 200 | 10 | ~10,000 | 8min | **Production (Recommended)** |
| **Maximum** | Custom | 500 | 25 | ~50,000+ | 30min+ | Best accuracy |

### Examples

```bash
# Quick test (30 seconds)
python scripts/collect_ml_training_data_full.py --quick-test

# Small dataset (2 minutes)
python scripts/collect_ml_training_data_full.py --small

# Medium dataset (4 minutes)
python scripts/collect_ml_training_data_full.py --medium

# Large dataset - RECOMMENDED (8 minutes)
python scripts/collect_ml_training_data_full.py --large

# Custom: 150 stocks, 7 years
python scripts/collect_ml_training_data_full.py --max-stocks 150 --years-back 7
```

### Manual Step-by-Step (Alternative)

If you prefer manual control:

#### Step 1: Get NSE Stocks

```bash
python scripts/get_all_nse_stocks.py --output data/all_nse_stocks.txt
```

#### Step 2: Run Bulk Backtest

```bash
# Large dataset (RECOMMENDED)
python scripts/bulk_backtest_all_stocks.py \
  --stocks-file data/all_nse_stocks.txt \
  --output data/backtest_training_data.csv \
  --max-stocks 200 \
  --years-back 10
```

#### Step 3: Extract Training Features

```bash
python scripts/collect_training_data.py \
  --backtest-file data/backtest_training_data.csv \
  --output data/ml_training_data.csv
```

### Training Data Format

**24 Features per Example:**
- Technical: `rsi_10`, `ema200`, `price`, `price_above_ema200`
- Volume: `volume`, `avg_volume_20`, `volume_ratio`, `vol_strong`
- Price Action: `recent_high_20`, `recent_low_20`, `support_distance_pct`
- Patterns: `has_hammer`, `has_bullish_engulfing`, `has_divergence`
- Fundamentals: `pe`, `pb`, `fundamental_ok`
- Meta: `ticker`, `entry_date`, `exit_date`

**Labels:**
- `strong_buy` - Gain >= 10%
- `buy` - Gain 5-10%
- `watch` - Gain 0-5%
- `avoid` - Loss < 0%

### Expected Results

**Small Dataset (50 stocks, 3 years)**
- Examples: ~500
- Training time: ~10 seconds
- Model accuracy: 60-75% (may overfit)

**Medium Dataset (100 stocks, 5 years)**
- Examples: ~2,000
- Training time: ~30 seconds
- Model accuracy: 70-80%

**Large Dataset (200 stocks, 10 years)** ⭐ RECOMMENDED
- Examples: ~10,000
- Training time: ~1-2 minutes
- Model accuracy: 75-85% (good generalization)

**Maximum Dataset (500 stocks, 25 years)**
- Examples: ~50,000+
- Training time: ~5-10 minutes
- Model accuracy: 80-90% (best performance)

---

## Model Training

### Using Training Script

```bash
python scripts/train_ml_model.py \
  --training-file data/ml_training_data_TIMESTAMP.csv \
  --model-type random_forest
```

### Using Python API

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

### Output Files

- `models/verdict_model_random_forest.pkl` - Trained model
- `models/verdict_model_features_random_forest.txt` - Feature columns list

### Model Types

**Random Forest (Current)**
- Good for structured data
- Handles non-linear relationships
- Feature importance available

**XGBoost (Optional)**
```bash
pip install xgboost
python scripts/train_ml_model.py --model-type xgboost
```

---

## Integration

### Automatic Integration

The system automatically:
1. **Loads ML model** at startup (if available)
2. **Predicts ML verdicts** for each stock during analysis
3. **Includes ML predictions** in Telegram notifications for comparison

### Usage

```bash
# Just run trade_agent.py normally
python trade_agent.py --backtest

# ML verdicts will appear in Telegram if model is available
```

### Telegram Output Example

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

### Key Points

- ✅ ML verdicts are **additive only** (don't replace rule-based)
- ✅ Rule-based verdict remains **primary** for actual trading decisions
- ✅ ML verdicts shown in Telegram for **testing/comparison**
- ✅ System works **even if ML model is unavailable** (fallback to rules only)

---

## Advanced Features

### Feature Engineering

Add new features in `scripts/collect_training_data.py`:
- More technical indicators (MACD, Bollinger Bands)
- Sector information
- Market cap data
- Volatility metrics

### Model Tuning

Try different models:
```bash
# Random Forest (current)
python scripts/train_ml_model.py --model-type random_forest

# XGBoost (if installed)
pip install xgboost
python scripts/train_ml_model.py --model-type xgboost
```

### Continuous Improvement

#### Automatic Retraining (MLRetrainingService)

The `MLRetrainingService` automatically retrains models when new data is available:

```python
from services.ml_retraining_service import MLRetrainingService

# Initialize retraining service
retraining_service = MLRetrainingService(
    training_data_path="data/ml_training_data.csv",
    min_retraining_interval_hours=24,
    min_new_samples=100,
    auto_backup=True
)

# Service automatically listens to backtest completion events
# and triggers retraining when conditions are met
```

#### Feedback Collection (MLFeedbackService)

Collect actual trade outcomes to improve model accuracy:

```python
from services.ml_feedback_service import MLFeedbackService

feedback_service = MLFeedbackService("data/ml_feedback.csv")

# Record actual outcome
feedback_service.record_outcome(
    ticker="RELIANCE.NS",
    prediction_date="2025-12-14",
    ml_verdict="buy",
    rule_verdict="buy",
    final_verdict="buy",
    actual_outcome="profit",
    pnl_pct=5.2,
    holding_days=3
)
```

#### ML Monitoring (MLLoggingService)

Monitor ML predictions and track performance:

```python
from services.ml_logging_service import MLLoggingService, MLPredictionLog

logging_service = MLLoggingService("data/ml_predictions.csv")

# Log prediction
log_entry = MLPredictionLog(
    timestamp="2025-12-14 10:00:00",
    ticker="RELIANCE.NS",
    ml_verdict="buy",
    ml_confidence=0.75,
    rule_verdict="buy",
    final_verdict="buy",
    verdict_source="ml",
    features={...},
    indicators={...},
    agreement=True
)

logging_service.log_prediction(log_entry)
```

#### Monthly Retraining (Manual)

```bash
# Collect fresh data with recent market conditions
python scripts/collect_ml_training_data_full.py --large

# Retrain with new data
python scripts/train_ml_model.py \
  --training-file data/ml_training_data_LATEST.csv \
  --model-type random_forest

# Old model is automatically replaced
```

### Feature Data Available

#### Technical Indicators
- RSI (10-period) - oversold/overbought signals
- EMA 20, 50, 200 - trend direction
- Volume ratios - volume quality assessment
- Support/Resistance levels
- Price action patterns

#### Multi-Timeframe Data
- Daily analysis
- Weekly analysis
- Alignment scores (0-10)

#### Pattern Signals
- Hammer pattern
- Bullish engulfing
- Bullish divergence
- Uptrend dip confirmations

#### Fundamental Data
- PE ratio
- PB ratio
- Earnings quality

#### Volume Analysis
- Volume quality (illiquid/liquid/strong)
- Volume patterns
- Volume exhaustion scores

---

## Troubleshooting

### Issue: "Not enough training examples"

**Solution:** Increase `--max-stocks` or `--years-back`

```bash
# Instead of default
python scripts/collect_ml_training_data_full.py --small

# Try larger dataset
python scripts/collect_ml_training_data_full.py --large
```

### Issue: "Stratification failed - only 1 member"

**Cause:** Insufficient examples in one class (e.g., only 1 "avoid" example)

**Solution:** Already fixed in `ml_training_service.py` - stratification is auto-disabled when needed

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

### Issue: Model accuracy is low

**Solution:**
- Add more training data (more stocks)
- Check feature extraction (some features may be missing)
- Try different model types (XGBoost, Neural Networks)

---

## Best Practices

### For Model Training

1. **Minimum Dataset Size:** 500+ examples
2. **Recommended Dataset Size:** 2,000-10,000 examples
3. **Class Balance:** Try to get similar numbers of each label
4. **Time Range:** 5-10 years captures various market conditions

### Iterative Improvement

```bash
# Start with quick test
python scripts/collect_ml_training_data_full.py --quick-test

# If looks good, scale up
python scripts/collect_ml_training_data_full.py --medium

# For production
python scripts/collect_ml_training_data_full.py --large
```

### Production Workflow

```bash
# 1. Collect large dataset (once)
python scripts/collect_ml_training_data_full.py --large

# 2. Train model
python scripts/train_ml_model.py \
  --training-file data/ml_training_data_TIMESTAMP.csv \
  --model-type random_forest

# 3. Model is automatically saved to models/
# 4. Use in production - ML verdicts will appear in Telegram notifications
```

---

## Summary

**Quickest Path to Production ML:**

```bash
# One command - 8 minutes - 10,000+ examples
python scripts/collect_ml_training_data_full.py --large

# Train model - 1 minute
python scripts/train_ml_model.py \
  --training-file data/ml_training_data_*.csv \
  --model-type random_forest

# Done! ML verdicts now available in production
```

**Total Time:** ~10 minutes from zero to ML-powered trading signals! 🚀

---

## Related Documentation

- [ML Training Data Guide](../ML_TRAINING_DATA_GUIDE.md) - Detailed data collection
- [ML Training Workflow](../ML_TRAINING_WORKFLOW.md) - Step-by-step workflow
- [ML Integration Guide](./ML_INTEGRATION_GUIDE.md) - Integration details
