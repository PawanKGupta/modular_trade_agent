#
ML Model Retraining Guide

**Version:** 1.0  
**Date:** 2025-11-07  
**Status:** Complete

---

## Overview

This guide explains how to retrain ML models with non-default configurations for the Configurable Indicators Implementation.

---

## Prerequisites

1. **Training Data:** Historical analysis data with labels (buy/sell outcomes)
2. **ML Training Service:** `services/ml_training_service.py`
3. **Model Storage:** `models/` directory
4. **Configuration:** `config/strategy_config.py`

---

## Model Versioning System

### Version Naming Convention

Models are versioned based on configuration:

```
verdict_model_rsi{period}_vol{lookback}_support{lookback}_v{version}.pkl
price_model_rsi{period}_vol{lookback}_support{lookback}_v{version}.pkl
```

**Example:**
- `verdict_model_rsi10_vol20_support20_v1.pkl` - Default config (RSI10, volume lookback 20, support lookback 20)
- `verdict_model_rsi14_vol30_support50_v1.pkl` - Custom config (RSI14, volume lookback 30, support lookback 50)

### Version Management

```python
# models/model_versions.json
{
    "verdict_models": {
        "rsi10_vol20_support20": {
            "version": 1,
            "path": "models/verdict_model_rsi10_vol20_support20_v1.pkl",
            "config": {
                "rsi_period": 10,
                "volume_exhaustion_lookback_daily": 20,
                "support_resistance_lookback_daily": 20
            },
            "trained_date": "2025-11-07",
            "performance": {
                "accuracy": 0.85,
                "precision": 0.82,
                "recall": 0.88
            }
        }
    },
    "price_models": {
        "rsi10_vol20_support20": {
            "version": 1,
            "path": "models/price_model_rsi10_vol20_support20_v1.pkl",
            "config": {
                "rsi_period": 10,
                "volume_exhaustion_lookback_daily": 20,
                "support_resistance_lookback_daily": 20
            },
            "trained_date": "2025-11-07",
            "performance": {
                "rmse": 0.05,
                "mae": 0.03
            }
        }
    }
}
```

---

## Retraining Process

### Step 1: Prepare Training Data

Collect historical analysis data with outcomes:

```python
# Example: Collect training data
from services.analysis_service import AnalysisService
from config.strategy_config import StrategyConfig
import pandas as pd
from datetime import datetime, timedelta

config = StrategyConfig(
    rsi_period=14,  # Custom config
    volume_exhaustion_lookback_daily=30,
    support_resistance_lookback_daily=50
)

service = AnalysisService(config=config)

# Collect data for multiple stocks over time period
training_data = []
start_date = datetime(2023, 1, 1)
end_date = datetime(2024, 12, 31)

for date in pd.date_range(start_date, end_date, freq='D'):
    # Analyze stocks and collect features + outcomes
    # ... (implementation depends on your data collection method)
    pass
```

### Step 2: Train Models

```python
# train_models.py
from services.ml_training_service import MLTrainingService
from config.strategy_config import StrategyConfig
import json

# Define configuration
config = StrategyConfig(
    rsi_period=14,
    volume_exhaustion_lookback_daily=30,
    support_resistance_lookback_daily=50
)

# Initialize training service
trainer = MLTrainingService(config=config)

# Load training data
training_data = load_training_data()  # Your data loading function

# Train verdict model
verdict_model = trainer.train_verdict_model(training_data)

# Train price model
price_model = trainer.train_price_model(training_data)

# Save models with versioning
version = get_next_version(config)  # Your versioning logic
verdict_path = f"models/verdict_model_rsi{config.rsi_period}_vol{config.volume_exhaustion_lookback_daily}_support{config.support_resistance_lookback_daily}_v{version}.pkl"
price_path = f"models/price_model_rsi{config.rsi_period}_vol{config.volume_exhaustion_lookback_daily}_support{config.support_resistance_lookback_daily}_v{version}.pkl"

trainer.save_model(verdict_model, verdict_path)
trainer.save_model(price_model, price_path)

# Update model versions
update_model_versions(config, verdict_path, price_path, version)
```

### Step 3: Validate Models

```python
# validate_models.py
from services.ml_training_service import MLTrainingService
from config.strategy_config import StrategyConfig

config = StrategyConfig(
    rsi_period=14,
    volume_exhaustion_lookback_daily=30,
    support_resistance_lookback_daily=50
)

trainer = MLTrainingService(config=config)

# Load validation data
validation_data = load_validation_data()

# Evaluate models
verdict_performance = trainer.evaluate_verdict_model(validation_data)
price_performance = trainer.evaluate_price_model(validation_data)

print(f"Verdict Model Performance: {verdict_performance}")
print(f"Price Model Performance: {price_performance}")
```

### Step 4: Update Model Configuration

Update `MLVerdictService` to use new models:

```python
# services/ml_verdict_service.py
from config.strategy_config import StrategyConfig
import os

class MLVerdictService:
    def __init__(self, config: StrategyConfig = None):
        self.config = config or StrategyConfig.default()
        
        # Load model based on configuration
        model_path = self._get_model_path()
        if os.path.exists(model_path):
            self.model = self._load_model(model_path)
        else:
            # Fallback to default model
            self.model = self._load_model("models/verdict_model_random_forest.pkl")
    
    def _get_model_path(self) -> str:
        """Get model path based on configuration."""
        rsi_period = self.config.rsi_period
        vol_lookback = self.config.volume_exhaustion_lookback_daily
        support_lookback = self.config.support_resistance_lookback_daily
        
        # Try to find matching model
        model_pattern = f"models/verdict_model_rsi{rsi_period}_vol{vol_lookback}_support{support_lookback}_v*.pkl"
        matching_models = glob.glob(model_pattern)
        
        if matching_models:
            # Use latest version
            return sorted(matching_models)[-1]
        
        # Fallback to default
        return "models/verdict_model_random_forest.pkl"
```

---

## Retraining Script

### Complete Retraining Script

```python
#!/usr/bin/env python3
"""
ML Model Retraining Script

Retrains ML models with custom configuration.
"""

import sys
import os
from pathlib import Path
import argparse
import json
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from services.ml_training_service import MLTrainingService


def get_next_version(config: StrategyConfig, model_type: str) -> int:
    """Get next version number for model."""
    versions_file = project_root / "models" / "model_versions.json"
    
    if not versions_file.exists():
        return 1
    
    with open(versions_file, 'r') as f:
        versions = json.load(f)
    
    model_key = f"rsi{config.rsi_period}_vol{config.volume_exhaustion_lookback_daily}_support{config.support_resistance_lookback_daily}"
    
    if model_type in versions and model_key in versions[model_type]:
        return versions[model_type][model_key]["version"] + 1
    
    return 1


def update_model_versions(config: StrategyConfig, verdict_path: str, price_path: str, version: int, performance: dict):
    """Update model versions file."""
    versions_file = project_root / "models" / "model_versions.json"
    
    model_key = f"rsi{config.rsi_period}_vol{config.volume_exhaustion_lookback_daily}_support{config.support_resistance_lookback_daily}"
    
    if versions_file.exists():
        with open(versions_file, 'r') as f:
            versions = json.load(f)
    else:
        versions = {"verdict_models": {}, "price_models": {}}
    
    # Update verdict model
    versions["verdict_models"][model_key] = {
        "version": version,
        "path": verdict_path,
        "config": {
            "rsi_period": config.rsi_period,
            "volume_exhaustion_lookback_daily": config.volume_exhaustion_lookback_daily,
            "support_resistance_lookback_daily": config.support_resistance_lookback_daily
        },
        "trained_date": datetime.now().isoformat(),
        "performance": performance.get("verdict", {})
    }
    
    # Update price model
    versions["price_models"][model_key] = {
        "version": version,
        "path": price_path,
        "config": {
            "rsi_period": config.rsi_period,
            "volume_exhaustion_lookback_daily": config.volume_exhaustion_lookback_daily,
            "support_resistance_lookback_daily": config.support_resistance_lookback_daily
        },
        "trained_date": datetime.now().isoformat(),
        "performance": performance.get("price", {})
    }
    
    with open(versions_file, 'w') as f:
        json.dump(versions, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Retrain ML models with custom configuration")
    parser.add_argument("--rsi-period", type=int, default=10, help="RSI period")
    parser.add_argument("--vol-lookback", type=int, default=20, help="Volume exhaustion lookback (daily)")
    parser.add_argument("--support-lookback", type=int, default=20, help="Support/resistance lookback (daily)")
    parser.add_argument("--training-data", type=str, required=True, help="Path to training data CSV")
    parser.add_argument("--validation-data", type=str, help="Path to validation data CSV")
    
    args = parser.parse_args()
    
    # Create configuration
    config = StrategyConfig(
        rsi_period=args.rsi_period,
        volume_exhaustion_lookback_daily=args.vol_lookback,
        support_resistance_lookback_daily=args.support_lookback
    )
    
    print(f"Training models with configuration:")
    print(f"  RSI Period: {config.rsi_period}")
    print(f"  Volume Lookback: {config.volume_exhaustion_lookback_daily}")
    print(f"  Support Lookback: {config.support_resistance_lookback_daily}")
    
    # Initialize training service
    trainer = MLTrainingService(config=config)
    
    # Load training data
    print(f"Loading training data from {args.training_data}...")
    training_data = pd.read_csv(args.training_data)
    
    # Train models
    print("Training verdict model...")
    verdict_model = trainer.train_verdict_model(training_data)
    
    print("Training price model...")
    price_model = trainer.train_price_model(training_data)
    
    # Get next version
    version = get_next_version(config, "verdict_models")
    
    # Save models
    verdict_path = f"models/verdict_model_rsi{config.rsi_period}_vol{config.volume_exhaustion_lookback_daily}_support{config.support_resistance_lookback_daily}_v{version}.pkl"
    price_path = f"models/price_model_rsi{config.rsi_period}_vol{config.volume_exhaustion_lookback_daily}_support{config.support_resistance_lookback_daily}_v{version}.pkl"
    
    trainer.save_model(verdict_model, verdict_path)
    trainer.save_model(price_model, price_path)
    
    print(f"Models saved:")
    print(f"  Verdict: {verdict_path}")
    print(f"  Price: {price_path}")
    
    # Evaluate models if validation data provided
    performance = {}
    if args.validation_data:
        print(f"Evaluating models with validation data from {args.validation_data}...")
        validation_data = pd.read_csv(args.validation_data)
        
        verdict_perf = trainer.evaluate_verdict_model(validation_data)
        price_perf = trainer.evaluate_price_model(validation_data)
        
        performance = {
            "verdict": verdict_perf,
            "price": price_perf
        }
        
        print(f"Verdict Model Performance: {verdict_perf}")
        print(f"Price Model Performance: {price_perf}")
    
    # Update model versions
    update_model_versions(config, verdict_path, price_path, version, performance)
    
    print("Model retraining complete!")


if __name__ == "__main__":
    main()
```

---

## Usage Examples

### Retrain with Default Configuration

```bash
python scripts/retrain_models.py \
    --training-data data/training_data.csv \
    --validation-data data/validation_data.csv
```

### Retrain with Custom Configuration

```bash
python scripts/retrain_models.py \
    --rsi-period 14 \
    --vol-lookback 30 \
    --support-lookback 50 \
    --training-data data/training_data.csv \
    --validation-data data/validation_data.csv
```

---

## Best Practices

### 1. Data Quality

- Ensure training data has sufficient samples (minimum 1000+)
- Balance positive/negative samples
- Include diverse market conditions

### 2. Model Validation

- Always validate models before deployment
- Use separate validation dataset
- Monitor performance metrics

### 3. Version Management

- Keep track of model versions
- Document configuration for each version
- Maintain performance history

### 4. Backward Compatibility

- Maintain default models for backward compatibility
- Support fallback to default models if custom model not found
- Test with existing code

### 5. Performance Monitoring

- Monitor model performance in production
- Track prediction accuracy
- Retrain if performance degrades

---

## Troubleshooting

### Issue: Model Not Found

**Solution:**
- Check model path matches configuration
- Verify model file exists
- Use default model as fallback

### Issue: Poor Model Performance

**Solution:**
- Collect more training data
- Tune hyperparameters
- Try different algorithms

### Issue: Feature Mismatch

**Solution:**
- Ensure feature extraction matches training configuration
- Verify feature names match model expectations
- Check configuration consistency

---

## Summary

This guide provides a complete framework for retraining ML models with custom configurations. Key points:

1. ✅ Use versioning system for model management
2. ✅ Train models with matching configuration
3. ✅ Validate models before deployment
4. ✅ Maintain backward compatibility
5. ✅ Monitor performance in production

For more information, see:
- `documents/ML_IMPLEMENTATION_GUIDE.md` - ML implementation details
- `services/ml_training_service.py` - Training service
- `services/ml_verdict_service.py` - Verdict service

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-07

