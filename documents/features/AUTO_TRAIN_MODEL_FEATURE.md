# Auto-Train Model Feature

## Overview

The system includes an **automatic model retraining feature** (`MLRetrainingService`) that can automatically retrain ML models based on events. However, **it is NOT enabled by default** and must be explicitly activated.

---

## Current Status

### ✅ Feature Exists
- **Service**: `services/ml_retraining_service.py`
- **Status**: Implemented but **NOT enabled by default**
- **Type**: Event-driven automatic retraining

### ❌ Not Enabled by Default
- **Default State**: Disabled
- **Initialization**: Must be explicitly called during application startup
- **Configuration**: No environment variables or config options (yet)

---

## How It Works

### Event-Driven Retraining

The `MLRetrainingService` listens to events and automatically triggers model retraining when conditions are met:

1. **Backtest Completion Event**
   - When a backtest completes, the service checks if retraining should be triggered
   - Condition: Minimum interval has passed (default: 24 hours)

2. **Analysis Batch Completion Event**
   - When a large analysis batch completes (≥50 stocks)
   - Condition: Minimum interval has passed + batch size ≥ 50

### Retraining Conditions

The service checks the following before retraining:

1. **Time Interval**: At least 24 hours since last retraining (configurable)
2. **Training Data**: Training data file exists (`data/ml_training_data.csv`)
3. **Minimum Samples**: (Future feature) Minimum new samples required

### Retraining Process

1. **Check Conditions**: Verify retraining should happen
2. **Backup Models**: Backup existing models to `models/backups/`
3. **Retrain Models**: Train new models using `MLTrainingService`
4. **Update Metadata**: Track retraining history and statistics
5. **Log Results**: Log to `logs/ml_retraining_history.txt`

---

## Configuration

### Default Settings

```python
MLRetrainingService(
    training_data_path="data/ml_training_data.csv",
    min_retraining_interval_hours=24,  # 24 hours minimum between retraining
    min_new_samples=100,  # Not currently enforced
    auto_backup=True  # Backup old models before retraining
)
```

### No Environment Variables (Yet)

Currently, there are **no environment variables** or configuration options in `StrategyConfig` for auto-retraining. This is a potential enhancement.

---

## How to Enable

### Option 1: Enable in trade_agent.py

Add to `trade_agent.py` at application startup:

```python
from services.ml_retraining_service import setup_ml_retraining

# Enable automatic ML retraining
setup_ml_retraining()
```

### Option 2: Enable in Auto Trader

Add to `modules/kotak_neo_auto_trader/run_trading_service.py`:

```python
from services.ml_retraining_service import setup_ml_retraining

class TradingService:
    def __init__(self):
        # ... existing initialization ...
        
        # Enable automatic ML retraining
        setup_ml_retraining()
```

### Option 3: Manual Trigger

Manually trigger retraining:

```python
from services.ml_retraining_service import get_ml_retraining_service

# Get service instance
service = get_ml_retraining_service()

# Manually trigger retraining
results = service.retrain_models(
    reason="Manual trigger",
    model_types=["random_forest", "xgboost"]
)
```

---

## Retraining Triggers

### Automatic Triggers (When Enabled)

1. **Backtest Completion**
   ```python
   # When backtest completes
   event_bus.publish(Event(
       event_type=EventType.BACKTEST_COMPLETED,
       data={'ticker': 'RELIANCE.NS', 'results': backtest_data}
   ))
   # → MLRetrainingService checks conditions → Retrains if needed
   ```

2. **Large Analysis Batch**
   ```python
   # When analysis batch completes (≥50 stocks)
   event_bus.publish(Event(
       event_type=EventType.ANALYSIS_COMPLETED,
       data={'batch_size': 100}
   ))
   # → MLRetrainingService checks conditions → Retrains if needed
   ```

### Manual Triggers

```python
# Direct call
service = get_ml_retraining_service()
service.retrain_models(reason="Manual trigger")
```

---

## Requirements

### Prerequisites

1. **Training Data**: `data/ml_training_data.csv` must exist
2. **ML Training Service**: `MLTrainingService` must be available
3. **Event Bus**: `EventBus` must be set up and events published
4. **Models Directory**: `models/` directory must exist

### Training Data Format

The training data CSV should contain:
- Feature columns (RSI, volume, price, etc.)
- Label column (`label`: 'buy', 'avoid', 'watch')
- Metadata columns (ticker, entry_date, exit_date, etc.)

---

## Safety Features

### 1. Minimum Interval

- **Default**: 24 hours between retraining
- **Purpose**: Prevent excessive retraining
- **Configurable**: Pass `min_retraining_interval_hours` to constructor

### 2. Model Backup

- **Default**: Enabled (`auto_backup=True`)
- **Location**: `models/backups/`
- **Format**: `{model_name}_{timestamp}.pkl`
- **Purpose**: Preserve old models before retraining

### 3. Retraining History

- **Location**: `logs/ml_retraining_history.txt`
- **Content**: Retraining timestamp, reason, models trained, errors
- **Purpose**: Track retraining frequency and results

### 4. Error Handling

- **Graceful Failure**: Errors are logged but don't crash the service
- **Partial Success**: Some models may train successfully even if others fail
- **Error Reporting**: Errors are included in retraining results

---

## Monitoring

### Check Retraining Status

```python
from services.ml_retraining_service import get_ml_retraining_service

service = get_ml_retraining_service()
stats = service.get_retraining_stats()

print(f"Total retrainings: {stats['total_retrainings']}")
print(f"Last retraining: {stats['last_retraining']}")
print(f"Min interval (hours): {stats['min_interval_hours']}")
print(f"Can retrain now: {stats['can_retrain_now']}")
```

### View Retraining History

```bash
# View retraining history
cat logs/ml_retraining_history.txt
```

---

## Limitations

### Current Limitations

1. **Not Enabled by Default**: Must be explicitly enabled
2. **No Configuration**: No environment variables or config options
3. **Event Dependency**: Requires events to be published (backtest, analysis)
4. **Training Data Dependency**: Requires training data file to exist
5. **No Drift Detection**: Doesn't check model drift automatically
6. **No Performance Validation**: Doesn't validate new model performance before replacing

### Future Enhancements

1. **Configuration Options**: Add to `StrategyConfig` and environment variables
2. **Drift Detection**: Automatically detect model drift and trigger retraining
3. **Performance Validation**: Compare new model with old model before replacing
4. **Scheduled Retraining**: Retrain on a schedule (daily, weekly)
5. **Minimum Samples Check**: Enforce minimum new samples requirement
6. **A/B Testing**: Test new models before full deployment

---

## Example Usage

### Enable Auto-Training

```python
# In trade_agent.py or main application file
from services.ml_retraining_service import setup_ml_retraining

def main():
    # ... existing initialization ...
    
    # Enable automatic ML retraining
    setup_ml_retraining()
    
    # ... rest of application ...
```

### Custom Configuration

```python
from services.ml_retraining_service import MLRetrainingService

# Create service with custom settings
service = MLRetrainingService(
    training_data_path="data/ml_training_data_filtered.csv",
    min_retraining_interval_hours=48,  # 48 hours instead of 24
    min_new_samples=200,  # Require 200 new samples
    auto_backup=True
)

# Setup listeners
service.setup_listeners()
```

### Manual Retraining

```python
from services.ml_retraining_service import get_ml_retraining_service

# Get service
service = get_ml_retraining_service()

# Manually trigger retraining
results = service.retrain_models(
    reason="Manual trigger after data collection",
    model_types=["random_forest", "xgboost"]
)

# Check results
print(f"Models trained: {len(results['models_trained'])}")
print(f"Errors: {len(results['errors'])}")
```

---

## Integration with Two-Stage Approach

### Chart Quality + ML Model

The auto-train feature works seamlessly with the two-stage approach:

1. **Training Data**: Should be filtered by chart quality (if using two-stage approach)
2. **Model Training**: Trains on filtered data (good charts only)
3. **Production**: Model used in two-stage approach (chart quality + ML)

### Recommended Workflow

1. **Collect Training Data**: With `--disable-chart-quality` (for data collection)
2. **Filter Training Data**: Filter by chart quality using `filter_training_data_by_chart_quality.py`
3. **Train Model**: Train on filtered data
4. **Enable Auto-Training**: Enable automatic retraining for future updates
5. **Production**: Use two-stage approach (chart quality + ML)

---

## Troubleshooting

### Auto-Training Not Triggering

**Symptoms**: Models not retraining automatically

**Solutions**:
1. **Check if enabled**: Verify `setup_ml_retraining()` is called
2. **Check events**: Verify events are being published
3. **Check interval**: Verify 24 hours have passed since last retraining
4. **Check training data**: Verify training data file exists

### Retraining Too Frequent

**Symptoms**: Models retraining too often

**Solutions**:
1. **Increase interval**: Set `min_retraining_interval_hours=48` or higher
2. **Check events**: Reduce frequency of triggering events
3. **Add conditions**: Add additional checks in `_should_retrain()`

### Retraining Failing

**Symptoms**: Retraining errors or failures

**Solutions**:
1. **Check training data**: Verify training data format and quality
2. **Check disk space**: Ensure enough disk space for model files
3. **Check logs**: Review `logs/ml_retraining_history.txt` for errors
4. **Manual retraining**: Try manual retraining to debug

---

## Best Practices

### 1. Start with Manual Retraining

**Recommendation**: Start with manual retraining until stable

```python
# Manual retraining first
service = get_ml_retraining_service()
service.retrain_models(reason="Initial training")

# Enable auto-training after validation
setup_ml_retraining()
```

### 2. Monitor Retraining Frequency

**Recommendation**: Monitor retraining history

```python
# Check retraining stats regularly
stats = service.get_retraining_stats()
if stats['total_retrainings'] > 10:
    # Review retraining frequency
    pass
```

### 3. Validate New Models

**Recommendation**: Validate new models before production use

```python
# After retraining, validate new model
# (Feature to be implemented)
```

### 4. Backup Strategy

**Recommendation**: Keep model backups

```python
# Enable auto-backup (default: True)
service = MLRetrainingService(auto_backup=True)
```

### 5. Filter Training Data

**Recommendation**: Filter training data by chart quality for two-stage approach

```bash
# Filter training data
python scripts/filter_training_data_by_chart_quality.py \
    --input-file data/ml_training_data.csv \
    --output-file data/ml_training_data_filtered.csv
```

---

## Summary

### Key Points

1. ✅ **Feature Exists**: `MLRetrainingService` provides automatic retraining
2. ❌ **Not Enabled by Default**: Must be explicitly enabled
3. 🔄 **Event-Driven**: Triggers on backtest/analysis completion events
4. ⏱️ **Minimum Interval**: 24 hours between retraining (configurable)
5. 💾 **Auto-Backup**: Backs up old models before retraining
6. 📊 **History Tracking**: Tracks retraining history and statistics

### Current Status

- **Implementation**: ✅ Complete
- **Enabled by Default**: ❌ No
- **Configuration**: ❌ No environment variables
- **Documentation**: ✅ Complete
- **Testing**: ⚠️ Limited

### Recommendations

1. **Enable Auto-Training**: Add `setup_ml_retraining()` to application startup
2. **Add Configuration**: Add environment variables for auto-training settings
3. **Monitor Usage**: Track retraining frequency and results
4. **Validate Models**: Implement model validation before deployment
5. **Filter Training Data**: Use chart quality filtering for two-stage approach

---

## Related Documentation

- [ML Implementation Guide](../ML_IMPLEMENTATION_GUIDE.md)
- [ML Model Retraining Guide](../ML_MODEL_RETRAINING_GUIDE.md)
- [Two-Stage Approach Guide](TWO_STAGE_CHART_QUALITY_ML_APPROACH.md)
- [Chart Quality Usage Guide](CHART_QUALITY_USAGE_GUIDE.md)




