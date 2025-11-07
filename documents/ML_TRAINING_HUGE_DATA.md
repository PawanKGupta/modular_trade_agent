# ML Training with Huge Data - Quick Guide

**Last Updated:** 2025-11-08  
**Status:** Ready for Production

---

## 🚀 Quick Start - Train with Huge Data

### **Complete Workflow (Two Commands)**

```bash
# Step 1: Collect huge training data (500 stocks, 25 years)
python scripts/collect_ml_training_data_full.py --max-stocks 500 --years-back 25

# Step 2: Train ML model with optimized settings
python scripts/train_ml_model_huge.py \
    --training-file data/ml_training_data_*.csv \
    --model-type xgboost \
    --n-estimators 500
```

**Estimated Time:**
- Data Collection: 30-60 minutes (depends on API rate limits)
- Training: 5-15 minutes (depends on dataset size)

**Expected Results:**
- ~50,000+ training examples
- High accuracy model (>85%)
- Optimized for production use

---

## 📊 Dataset Size Recommendations

| Dataset Size | Stocks | Years | Examples | Time | Command |
|--------------|--------|-------|----------|------|---------|
| **Quick Test** | 10 | 2 | ~50 | 30s | `--quick-test` |
| **Small** | 50 | 3 | ~500 | 2min | `--small` |
| **Medium** | 100 | 5 | ~2,000 | 4min | `--medium` |
| **Large** ⭐ | 200 | 10 | ~10,000 | 8min | `--large` |
| **Huge** 🚀 | 500 | 25 | ~50,000+ | 30-60min | `--max-stocks 500 --years-back 25` |

---

## 🎯 Training Commands

### **1. Collect Huge Training Data**

```bash
# Maximum dataset (RECOMMENDED for production)
python scripts/collect_ml_training_data_full.py \
    --max-stocks 500 \
    --years-back 25

# Or use preset large dataset (faster)
python scripts/collect_ml_training_data_full.py --large
```

**Output Files:**
- `data/all_nse_stocks.txt` - List of stocks
- `data/backtest_training_data_*.csv` - Backtest results
- `data/ml_training_data_*.csv` - Training dataset

### **2. Train Model with Huge Data**

#### **Option A: XGBoost (Recommended for Huge Data)**

```bash
# XGBoost with optimized parameters for huge data
python scripts/train_ml_model_huge.py \
    --training-file data/ml_training_data_*.csv \
    --model-type xgboost \
    --n-estimators 500 \
    --max-depth 8 \
    --learning-rate 0.05
```

**Advantages:**
- ✅ Faster training on large datasets
- ✅ Better accuracy with more data
- ✅ Memory efficient
- ✅ Supports early stopping

#### **Option B: Random Forest (Alternative)**

```bash
# Random Forest (slower but good for medium datasets)
python scripts/train_ml_model_huge.py \
    --training-file data/ml_training_data_*.csv \
    --model-type random_forest \
    --n-estimators 300
```

### **3. Standard Training (Smaller Datasets)**

```bash
# For smaller datasets (<10,000 examples)
python scripts/train_ml_model.py \
    --training-file data/ml_training_data.csv \
    --model-type xgboost
```

---

## ⚙️ Optimization Parameters

### **XGBoost Parameters (Huge Data)**

```bash
python scripts/train_ml_model_huge.py \
    --training-file data/ml_training_data.csv \
    --model-type xgboost \
    --n-estimators 500 \      # More trees = better accuracy (slower)
    --max-depth 8 \            # Tree depth (6-10 recommended)
    --learning-rate 0.05 \     # Lower = more accurate (slower)
    --test-size 0.2            # 20% for testing
```

**Parameter Guidelines:**
- **n_estimators**: 200-1000 (more = better, but slower)
- **max_depth**: 6-10 (8 is optimal for most cases)
- **learning_rate**: 0.01-0.1 (lower = better, but slower)
- **test_size**: 0.1-0.3 (0.2 recommended)

### **Random Forest Parameters**

```bash
python scripts/train_ml_model_huge.py \
    --training-file data/ml_training_data.csv \
    --model-type random_forest \
    --n-estimators 300 \       # More trees = better accuracy
    --max-depth 10             # Tree depth
```

---

## 📈 Performance Expectations

### **Dataset Size vs Accuracy**

| Examples | Expected Accuracy | Training Time |
|----------|------------------|---------------|
| 1,000 | 70-75% | 1-2 min |
| 5,000 | 75-80% | 2-5 min |
| 10,000 | 80-85% | 5-10 min |
| 50,000+ | 85-90%+ | 10-20 min |

### **Model Comparison**

| Model | Speed | Accuracy | Memory | Best For |
|-------|-------|----------|--------|----------|
| **XGBoost** | Fast | High | Low | Huge datasets |
| **Random Forest** | Medium | High | Medium | Medium datasets |

---

## 🔍 Monitoring Training

### **Check Training Progress**

The training script provides:
- ✅ Data loading progress
- ✅ Training progress (for XGBoost)
- ✅ Evaluation metrics
- ✅ Feature importance
- ✅ Model save location

### **Example Output**

```
🚀 Training ML Model with Huge Dataset
======================================================================
Training File: data/ml_training_data_20251108_120000.csv
Model Type: xgboost
Estimators: 500
Max Depth: 8
Test Size: 0.2
======================================================================

📊 Loading training data...
   Loaded 52,347 training examples
   Features: 45 (excluding metadata columns)

⏳ Training model...
[0]	validation_0-mlogloss:1.23456
[50]	validation_0-mlogloss:0.98765
...

📈 Model Performance
======================================================================
   Accuracy: 87.34%

              precision    recall  f1-score   support

       avoid       0.89      0.91      0.90      5234
         buy       0.85      0.83      0.84      3145
   strong_buy       0.91      0.88      0.90      4187
        watch       0.82      0.81      0.82      2091

    accuracy                           0.87     14657
   macro avg       0.87      0.86      0.86     14657
weighted avg       0.87      0.87      0.87     14657

🔝 Top 15 Features:
   rsi: 0.1234
   volume_ratio: 0.0987
   ...
```

---

## 🛠️ Troubleshooting

### **Issue: Out of Memory**

**Solution:**
```bash
# Reduce dataset size or use chunking
python scripts/train_ml_model_huge.py \
    --training-file data/ml_training_data.csv \
    --model-type xgboost \
    --n-estimators 300 \    # Reduce estimators
    --max-depth 6           # Reduce depth
```

### **Issue: Training Too Slow**

**Solution:**
```bash
# Use XGBoost instead of Random Forest
python scripts/train_ml_model_huge.py \
    --training-file data/ml_training_data.csv \
    --model-type xgboost \
    --n-estimators 200      # Reduce estimators
```

### **Issue: Poor Accuracy**

**Solution:**
1. Collect more training data
2. Increase n_estimators
3. Tune learning_rate and max_depth
4. Check feature quality

### **Issue: XGBoost Not Installed**

**Solution:**
```bash
pip install xgboost
```

---

## 📝 Best Practices

### **1. Data Quality**
- ✅ Collect data from diverse market conditions
- ✅ Balance positive/negative samples
- ✅ Include recent data (last 2-5 years)
- ✅ Filter out low-quality trades

### **2. Model Training**
- ✅ Use 80/20 train/test split
- ✅ Use early stopping (XGBoost)
- ✅ Tune hyperparameters
- ✅ Monitor overfitting

### **3. Model Validation**
- ✅ Test on separate validation set
- ✅ Check feature importance
- ✅ Monitor accuracy per class
- ✅ Validate on recent data

### **4. Production Deployment**
- ✅ Save model with version
- ✅ Document model parameters
- ✅ Monitor performance in production
- ✅ Retrain periodically (monthly/quarterly)

---

## 📚 Related Documentation

- `documents/ML_TRAINING_DATA_GUIDE.md` - Data collection guide
- `documents/ML_MODEL_RETRAINING_GUIDE.md` - Retraining guide
- `documents/architecture/ML_TRAINING_WORKFLOW.md` - Complete workflow
- `services/ml_training_service.py` - Training service code

---

## 🎯 Quick Reference

### **Complete Command (Copy-Paste Ready)**

```bash
# Step 1: Collect huge data
python scripts/collect_ml_training_data_full.py --max-stocks 500 --years-back 25

# Step 2: Find the latest training file
ls -lt data/ml_training_data_*.csv | head -1

# Step 3: Train model
python scripts/train_ml_model_huge.py \
    --training-file data/ml_training_data_YYYYMMDD_HHMMSS.csv \
    --model-type xgboost \
    --n-estimators 500 \
    --max-depth 8 \
    --learning-rate 0.05
```

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-08

