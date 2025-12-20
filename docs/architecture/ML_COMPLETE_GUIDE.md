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

### Training via Web UI (Recommended)

1. **Access ML Training Page**: Navigate to `/dashboard/admin/ml` (admin only)
2. **Start Training Job**:
   - Configure training parameters
   - Select model type (Random Forest, XGBoost)
   - Start training job
3. **Monitor Progress**: View training status and job history in the UI

### Training via API

```bash
# Start ML training job via API
curl -X POST http://localhost:8000/api/v1/admin/ml/train \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model_version": "v4",
    "force_retrain": false
  }'
```

### Manual Training Data Collection (Advanced)

If you need to collect training data manually:

```bash
# Get all NSE stocks
python scripts/get_all_nse_stocks.py --output data/all_nse_stocks.txt

# Run bulk backtest
python scripts/bulk_backtest_all_stocks.py \
  --stocks-file data/all_nse_stocks.txt \
  --output data/backtest_training_data.csv \
  --max-stocks 200 \
  --years-back 10

# Extract training features
python scripts/collect_training_data.py \
  --backtest-file data/backtest_training_data.csv \
  --output data/ml_training_data.csv
```

**Note**: The recommended approach is to use the web UI for ML training, which handles data collection, training, and model activation automatically.

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

For manual data collection:

```bash
# Small dataset (2 minutes)
python scripts/bulk_backtest_all_stocks.py \
  --stocks-file data/all_nse_stocks.txt \
  --output data/backtest_training_data.csv \
  --max-stocks 50 \
  --years-back 3

# Medium dataset (4 minutes)
python scripts/bulk_backtest_all_stocks.py \
  --stocks-file data/all_nse_stocks.txt \
  --output data/backtest_training_data.csv \
  --max-stocks 100 \
  --years-back 5

# Large dataset - RECOMMENDED (8 minutes)
python scripts/bulk_backtest_all_stocks.py \
  --stocks-file data/all_nse_stocks.txt \
  --output data/backtest_training_data.csv \
  --max-stocks 200 \
  --years-back 10
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

### Using Web UI (Recommended)

1. Navigate to **Admin → ML Training** (`/dashboard/admin/ml`)
2. Click **Start Training Job**
3. Configure parameters:
   - Model Type: Random Forest or XGBoost
   - Training Data: Path to training data CSV
   - Force Retrain: Whether to retrain existing models
4. Click **Start** and monitor progress

### Using API

```bash
POST /api/v1/admin/ml/train
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "model_version": "v4",
  "model_type": "random_forest",
  "force_retrain": false
}
```

### Using Python API (Advanced)

```python
from src.application.services.ml_training_service import MLTrainingService
from src.infrastructure.db.session import SessionLocal

# Initialize with database session
with SessionLocal() as db:
    trainer = MLTrainingService(db, artifact_dir="models")

    # Start training job
    job = trainer.start_training_job(
        started_by=user_id,
        config=TrainingJobConfig(
            model_type="random_forest",
            algorithm="RandomForestClassifier",
            training_data_path="data/ml_training_data.csv"
        )
    )

    # Run training (usually done in background)
    trainer.run_training_job(job.id, config)
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
# Then use web UI or API with model_type="xgboost"
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
# Use web UI or API with model_type="random_forest"

# XGBoost (if installed)
pip install xgboost
# Use web UI or API with model_type="xgboost"
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

**Via Web UI:**
1. Navigate to Admin → ML Training
2. Start new training job with updated data
3. System automatically handles model versioning

**Via Scripts:**
```bash
# Collect fresh data with recent market conditions
python scripts/get_all_nse_stocks.py --output data/all_nse_stocks.txt
python scripts/bulk_backtest_all_stocks.py \
  --stocks-file data/all_nse_stocks.txt \
  --output data/backtest_training_data.csv \
  --max-stocks 200 \
  --years-back 10
python scripts/collect_training_data.py \
  --backtest-file data/backtest_training_data.csv \
  --output data/ml_training_data_LATEST.csv

# Retrain via API or web UI
# Old model is automatically versioned, new model can be activated
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
python scripts/bulk_backtest_all_stocks.py && python scripts/collect_training_data.py --small

# Try larger dataset
python scripts/bulk_backtest_all_stocks.py && python scripts/collect_training_data.py --large
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
python scripts/bulk_backtest_all_stocks.py && python scripts/collect_training_data.py --quick-test

# If looks good, scale up
python scripts/bulk_backtest_all_stocks.py && python scripts/collect_training_data.py --medium

# For production
python scripts/bulk_backtest_all_stocks.py && python scripts/collect_training_data.py --large
```

### Production Workflow

**Recommended (Web UI):**
1. Navigate to Admin → ML Training
2. Start training job with desired parameters
3. Monitor job progress
4. Activate model when training completes
5. ML verdicts automatically appear in analysis results

**Manual Workflow:**
```bash
# 1. Collect large dataset (once)
python scripts/get_all_nse_stocks.py --output data/all_nse_stocks.txt
python scripts/bulk_backtest_all_stocks.py \
  --stocks-file data/all_nse_stocks.txt \
  --output data/backtest_training_data.csv \
  --max-stocks 200 \
  --years-back 10

# 2. Extract training features
python scripts/collect_training_data.py \
  --backtest-file data/backtest_training_data.csv \
  --output data/ml_training_data.csv

# 3. Train via API or web UI
# 4. Model is automatically saved and activated
# 5. ML verdicts appear in analysis results and notifications
```

---

## Summary

**Quickest Path to Production ML:**

**Via Web UI (Recommended):**
1. Navigate to Admin → ML Training
2. Start training job with default settings
3. Wait for completion (~10 minutes)
4. Activate model
5. Done! ML verdicts now appear in analysis

**Via Manual Scripts:**
```bash
# Collect training data - 8 minutes - 10,000+ examples
python scripts/get_all_nse_stocks.py --output data/all_nse_stocks.txt
python scripts/bulk_backtest_all_stocks.py \
  --stocks-file data/all_nse_stocks.txt \
  --output data/backtest_training_data.csv \
  --max-stocks 200 \
  --years-back 10
python scripts/collect_training_data.py \
  --backtest-file data/backtest_training_data.csv \
  --output data/ml_training_data.csv

# Train model via API or web UI - 1-2 minutes
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
