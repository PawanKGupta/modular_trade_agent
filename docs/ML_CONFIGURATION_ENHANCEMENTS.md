# ML Configuration Enhancements Documentation

**Version:** 1.0
**Date:** 2025-12-05
**Branch:** `feature/ml-configuration-tests`
**Status:** ✅ Complete - Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Features Implemented](#features-implemented)
3. [Configuration](#configuration)
4. [Confidence-Aware Verdict Combination](#confidence-aware-verdict-combination)
5. [Model Version Resolution](#model-version-resolution)
6. [Integration Points](#integration-points)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)
9. [Migration Guide](#migration-guide)

---

## Overview

This document describes the ML configuration enhancements that integrate ML settings from the user interface into the backend trading engine. These enhancements ensure that:

- ML configuration from the UI is properly respected
- Model versions can be selected and resolved dynamically
- Confidence-aware verdict combination provides safety-first trading decisions
- All changes are thoroughly tested with >80% coverage

### Key Benefits

✅ **UI Integration**: ML settings from the UI are now fully integrated into the backend
✅ **Model Versioning**: Support for multiple ML model versions with database-backed resolution
✅ **Safety-First**: Confidence-aware combination logic ensures conservative trading decisions
✅ **Backward Compatible**: Existing functionality remains unchanged
✅ **Well Tested**: Comprehensive test suite with 49 tests covering all scenarios

---

## Features Implemented

### 1. ML Configuration Integration

**Problem**: ML settings from the UI were not being used by the backend. The `ml_enabled` flag was hardcoded to `False`.

**Solution**:
- Fixed `config_converter.py` to use `user_config.ml_enabled` instead of hardcoding
- Updated `AnalysisService` to respect `ml_enabled` setting
- Added model version resolution via `ml_model_resolver.py`

**Files Modified**:
- `src/application/services/config_converter.py`
- `services/analysis_service.py`
- `utils/ml_model_resolver.py` (new)
- `modules/kotak_neo_auto_trader/run_trading_service.py`
- `src/application/services/multi_user_trading_service.py`
- `src/application/services/individual_service_manager.py`

### 2. Confidence-Aware Verdict Combination

**Problem**: When `ml_combine_with_rules=true`, the system only showed both justifications but didn't actually combine the verdicts intelligently based on ML confidence.

**Solution**: Implemented a three-tier confidence-aware combination logic:

- **High Confidence (≥70%)**: Trust ML more, but still prefer more conservative verdict
- **Medium Confidence (60-70%)**: Equal weight, use more conservative verdict
- **Low Confidence (50-60%)**: Trust rules more, but still consider ML if it's much more conservative

**Files Modified**:
- `services/ml_verdict_service.py`

### 3. Feature Extraction Fix

**Problem**: Feature extraction was creating both `avg_volume_{volume_lookback}` and `avg_volume_20`, resulting in 44 features instead of the model's expected 43.

**Solution**: Only create `avg_volume_20` to match the model's training data exactly.

**Files Modified**:
- `services/ml_verdict_service.py`

---

## Configuration

### UI Configuration Options

The following ML configuration options are available in the UI and are now fully integrated:

#### 1. ML Enabled (`ml_enabled`)

- **Type**: Boolean
- **Default**: `false`
- **Description**: Enable/disable ML-enhanced verdicts
- **Impact**: When `true`, the system uses `MLVerdictService`; when `false`, uses `VerdictService`

#### 2. ML Model Version (`ml_model_version`)

- **Type**: String (e.g., "v1.0", "v2.0")
- **Default**: `None`
- **Description**: Select specific ML model version
- **Impact**: Resolves to model path from database via `MLModel` table
- **Fallback**: Uses default `models/verdict_model_random_forest.pkl` if version not found

#### 3. ML Confidence Threshold (`ml_confidence_threshold`)

- **Type**: Float (0.0 to 1.0)
- **Default**: `0.5` (50%)
- **Description**: Minimum ML confidence required to use ML prediction
- **Impact**: ML predictions below this threshold fall back to rule-based logic

#### 4. ML Combine with Rules (`ml_combine_with_rules`)

- **Type**: Boolean
- **Default**: `true`
- **Description**: Whether to combine ML and rule-based verdicts
- **Impact**:
  - `true`: Uses confidence-aware combination (more conservative verdict)
  - `false`: Uses ML verdict directly if confidence meets threshold

### Configuration Flow

```
UserTradingConfig (Database)
    ↓
config_converter.py (user_config_to_strategy_config)
    ↓
StrategyConfig (Dataclass)
    ↓
AnalysisService / MLVerdictService
```

### Example Configuration

```python
# UserTradingConfig in database
user_config = UserTradingConfig(
    ml_enabled=True,
    ml_model_version="v1.0",
    ml_confidence_threshold=0.7,
    ml_combine_with_rules=True,
)

# Converted to StrategyConfig
strategy_config = user_config_to_strategy_config(
    user_config,
    db_session=db_session  # Required for model version resolution
)

# Result:
# strategy_config.ml_enabled = True
# strategy_config.ml_verdict_model_path = "models/verdict_model_v1.0.pkl" (resolved from DB)
# strategy_config.ml_confidence_threshold = 0.7
# strategy_config.ml_combine_with_rules = True
```

---

## Confidence-Aware Verdict Combination

### Verdict Hierarchy

Verdicts are ordered from most aggressive to most conservative:

```
strong_buy (0) < buy (1) < watch (2) < avoid (3)
```

Higher number = more conservative.

### Combination Logic

When `ml_combine_with_rules=true`, the system uses confidence-aware combination:

#### High Confidence (≥70%)

**Behavior**: Trust ML more, but still prefer more conservative verdict

**Scenarios**:
- ML more conservative → Use ML verdict (high confidence in caution is valuable)
- Rules more conservative → Use rules (safety-first, even with high ML confidence)
- Both agree → Use ML verdict (high confidence confirmation)

**Example**:
```
ML: watch (80% confidence)
Rules: buy
Result: watch (ML is more conservative with high confidence)
```

#### Medium Confidence (60-70%)

**Behavior**: Equal weight, use more conservative verdict

**Scenarios**:
- Always uses the more conservative of the two verdicts

**Example**:
```
ML: buy (65% confidence)
Rules: watch
Result: watch (more conservative)
```

#### Low Confidence (50-60%)

**Behavior**: Trust rules more, but still consider ML if it's much more conservative

**Scenarios**:
- ML much more conservative (rank difference > 1) → Use ML (safety signal)
- ML slightly more conservative → Use rules (low ML confidence)
- Rules more conservative or equal → Use rules (low ML confidence)

**Example**:
```
ML: avoid (52% confidence)
Rules: buy
Result: avoid (ML is much more conservative - strong safety signal)

ML: watch (52% confidence)
Rules: buy
Result: buy (rules - ML confidence too low for slight difference)
```

### Direct ML Mode

When `ml_combine_with_rules=false`:

- Uses ML verdict directly if confidence ≥ threshold
- Falls back to rule-based if confidence < threshold
- No combination logic applied

---

## Model Version Resolution

### How It Works

1. User selects model version in UI (e.g., "v1.0")
2. `config_converter.py` calls `_resolve_ml_model_path()`
3. `_resolve_ml_model_path()` uses `ml_model_resolver.get_model_path_from_version()`
4. Resolver queries `MLModel` table in database
5. Returns model path if found, otherwise falls back to default

### Database Schema

```sql
CREATE TABLE ml_models (
    id INTEGER PRIMARY KEY,
    model_type VARCHAR(64) NOT NULL,  -- 'verdict_classifier' or 'price_regressor'
    version VARCHAR(16) NOT NULL,      -- 'v1.0', 'v2.0', etc.
    model_path VARCHAR(512) NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    training_job_id INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    created_by INTEGER NOT NULL,
    UNIQUE(model_type, version)
);
```

### Resolution Flow

```
ml_model_version="v1.0"
    ↓
get_model_path_from_version(db, "verdict_classifier", "v1.0")
    ↓
Query: SELECT * FROM ml_models
       WHERE model_type='verdict_classifier' AND version='v1.0'
    ↓
If found and file exists:
    Return: "models/verdict_model_v1.0.pkl"
Else:
    Return: None → Fallback to default
```

### Fallback Behavior

- If `ml_model_version` is `None` → Use default path
- If version not found in database → Use default path (with warning log)
- If model file doesn't exist → Use default path (with warning log)
- If database error → Use default path (with warning log)

### Active Model Resolution

You can also get the active model for a type:

```python
from utils.ml_model_resolver import get_active_model_path

active_model_path = get_active_model_path(db_session, "verdict_classifier")
# Returns path to model where is_active=True
```

---

## Integration Points

### 1. Config Converter

**File**: `src/application/services/config_converter.py`

**Function**: `user_config_to_strategy_config()`

**Changes**:
- Uses `user_config.ml_enabled` (not hardcoded)
- Resolves `ml_model_version` via `_resolve_ml_model_path()`
- Passes all ML settings to `StrategyConfig`

**Usage**:
```python
strategy_config = user_config_to_strategy_config(
    user_config,
    db_session=db_session  # Required for model version resolution
)
```

### 2. Analysis Service

**File**: `services/analysis_service.py`

**Changes**:
- Checks `config.ml_enabled` before initializing `MLVerdictService`
- Falls back to `VerdictService` if ML disabled or model not found

**Logic**:
```python
if config.ml_enabled and model_file_exists:
    use MLVerdictService
else:
    use VerdictService
```

### 3. ML Verdict Service

**File**: `services/ml_verdict_service.py`

**Changes**:
- Implements confidence-aware verdict combination
- Uses `_get_confidence_aware_combined_verdict()` for combination logic
- Fixed feature extraction to match model's 43 features exactly

**Key Methods**:
- `determine_verdict()`: Main entry point with combination logic
- `_get_confidence_aware_combined_verdict()`: Confidence-aware combination
- `_get_more_conservative_verdict()`: Helper to get more conservative verdict
- `_extract_features()`: Feature extraction (fixed to 43 features)

### 4. Service Initialization

**Files Modified**:
- `modules/kotak_neo_auto_trader/run_trading_service.py`
- `src/application/services/multi_user_trading_service.py`
- `src/application/services/individual_service_manager.py`

**Changes**:
- All now pass `db_session` to `user_config_to_strategy_config()`
- Enables model version resolution

---

## Testing

### Test Coverage

**Total Tests**: 49 tests
**Coverage**: >80% for all modified files

### Test Files

1. **`tests/unit/application/test_config_converter_ml_enhancements.py`** (16 tests)
   - ML configuration passed through
   - Model version resolution
   - Error handling

2. **`tests/unit/utils/test_ml_model_resolver.py`** (12 tests)
   - Model path resolution from version
   - Active model resolution
   - Error handling and edge cases

3. **`tests/unit/services/test_analysis_service_ml_config.py`** (5 tests)
   - AnalysisService respects ml_enabled
   - Fallback behavior

4. **`tests/unit/services/test_ml_verdict_service_confidence_aware.py`** (16 tests)
   - Confidence-aware combination logic
   - All confidence bands
   - Verdict combinations

### Running Tests

```bash
# Run all ML configuration tests
pytest tests/unit/application/test_config_converter_ml_enhancements.py \
       tests/unit/utils/test_ml_model_resolver.py \
       tests/unit/services/test_analysis_service_ml_config.py \
       tests/unit/services/test_ml_verdict_service_confidence_aware.py -v

# Run with coverage
pytest tests/unit/application/test_config_converter_ml_enhancements.py \
       tests/unit/utils/test_ml_model_resolver.py \
       tests/unit/services/test_analysis_service_ml_config.py \
       tests/unit/services/test_ml_verdict_service_confidence_aware.py \
       --cov=src/application/services/config_converter \
       --cov=utils/ml_model_resolver \
       --cov=services/analysis_service \
       --cov=services/ml_verdict_service \
       --cov-report=term-missing
```

### Test Scenarios Covered

✅ ML enabled/disabled from UI
✅ Model version resolution with/without db_session
✅ Model version not found in database
✅ Model file doesn't exist
✅ Confidence-aware combination (high/medium/low)
✅ Verdict agreement/disagreement scenarios
✅ Edge cases (unknown verdicts, threshold boundaries)
✅ Feature extraction (43 features exactly)

---

## Troubleshooting

### Issue: ML Not Being Used Despite `ml_enabled=true`

**Possible Causes**:
1. Model file doesn't exist at resolved path
2. Model failed to load
3. `db_session` not passed to `user_config_to_strategy_config()`

**Solution**:
```python
# Check if model path is resolved correctly
strategy_config = user_config_to_strategy_config(user_config, db_session=db_session)
print(f"ML enabled: {strategy_config.ml_enabled}")
print(f"Model path: {strategy_config.ml_verdict_model_path}")

# Check if model file exists
from pathlib import Path
model_path = Path(strategy_config.ml_verdict_model_path)
print(f"Model exists: {model_path.exists()}")
```

### Issue: Model Version Not Resolving

**Possible Causes**:
1. Version not in database
2. `db_session` not provided
3. Model file doesn't exist

**Solution**:
```python
# Check database
from src.infrastructure.db.models import MLModel
from sqlalchemy import select

stmt = select(MLModel).where(
    MLModel.model_type == "verdict_classifier",
    MLModel.version == "v1.0"
)
model = db_session.execute(stmt).scalar_one_or_none()
if model:
    print(f"Found: {model.model_path}")
    print(f"File exists: {Path(model.model_path).exists()}")
else:
    print("Model not found in database")
```

### Issue: Wrong Verdict Combination

**Possible Causes**:
1. Confidence threshold too high/low
2. `ml_combine_with_rules` setting
3. Confidence band logic misunderstanding

**Solution**:
```python
# Check confidence bands
# High: >= 70%
# Medium: 60-70%
# Low: 50-60%

# Check combination mode
if config.ml_combine_with_rules:
    # Uses confidence-aware combination
else:
    # Uses ML directly
```

### Issue: Feature Count Mismatch (44 instead of 43)

**Cause**: Code was creating both `avg_volume_{volume_lookback}` and `avg_volume_20`

**Solution**: Fixed in commit `bd777ad0`. Only `avg_volume_20` is created now.

**Verification**:
```python
features = ml_service._extract_features(...)
assert len(features) == 43, f"Expected 43 features, got {len(features)}"
```

---

## Migration Guide

### For Existing Users

No migration required. The changes are backward compatible:

- Existing configurations continue to work
- Default behavior unchanged (ML disabled by default)
- Model path defaults to standard location if version not specified

### For New ML Model Versions

1. **Train new model** and save to `models/verdict_model_v2.0.pkl`

2. **Add to database**:
```python
from src.infrastructure.db.models import MLModel, MLTrainingJob, Users
from src.infrastructure.db.timezone_utils import ist_now

# Create training job
training_job = MLTrainingJob(
    model_type="verdict_classifier",
    status="completed",
    started_by=admin_user_id,
    algorithm="random_forest",
    training_data_path="data/training_v2.csv",
    started_at=ist_now(),
)
db_session.add(training_job)
db_session.commit()

# Create model entry
model = MLModel(
    model_type="verdict_classifier",
    version="v2.0",
    model_path="models/verdict_model_v2.0.pkl",
    training_job_id=training_job.id,
    is_active=False,  # Set to True to make it active
    created_by=admin_user_id,
    created_at=ist_now(),
)
db_session.add(model)
db_session.commit()
```

3. **Users can select v2.0 in UI** and it will be automatically resolved

### Updating Feature Set

If you need to update the feature set:

1. **Update feature extraction** in `ml_verdict_service.py`
2. **Update feature columns file**: `models/verdict_model_features_enhanced.txt`
3. **Retrain model** with new features
4. **Update model in database** with new version

**Important**: The model expects exactly 43 features. Any change requires retraining.

---

## API Reference

### `user_config_to_strategy_config()`

```python
def user_config_to_strategy_config(
    user_config: UserTradingConfig,
    db_session: Optional[object] = None
) -> StrategyConfig:
    """
    Convert UserTradingConfig to StrategyConfig.

    Args:
        user_config: UserTradingConfig from database
        db_session: Optional database session for model version resolution

    Returns:
        StrategyConfig with ML settings from user_config
    """
```

### `get_model_path_from_version()`

```python
def get_model_path_from_version(
    db: Session,
    model_type: str,
    version: str | None
) -> Optional[str]:
    """
    Get model path from version string.

    Args:
        db: Database session
        model_type: "verdict_classifier" or "price_regressor"
        version: Version string like "v1.0" or None

    Returns:
        Model path if found, None otherwise
    """
```

### `get_active_model_path()`

```python
def get_active_model_path(
    db: Session,
    model_type: str
) -> Optional[str]:
    """
    Get path to active model for given type.

    Args:
        db: Database session
        model_type: "verdict_classifier" or "price_regressor"

    Returns:
        Model path if found, None otherwise
    """
```

### `_get_confidence_aware_combined_verdict()`

```python
def _get_confidence_aware_combined_verdict(
    self,
    ml_verdict: str,
    ml_confidence: float,
    rule_verdict: str,
    confidence_threshold: float,
) -> str:
    """
    Get combined verdict considering ML confidence level.

    Logic:
    - High ML confidence (>= 70%): Trust ML more, but still use more conservative
    - Medium ML confidence (60-70%): Equal weight, use more conservative
    - Low ML confidence (50-60%): Trust rules more, but still consider ML if much more conservative

    Returns:
        Combined verdict considering confidence
    """
```

---

## Best Practices

### 1. Always Pass `db_session`

When calling `user_config_to_strategy_config()`, always pass `db_session` to enable model version resolution:

```python
# ✅ Good
strategy_config = user_config_to_strategy_config(user_config, db_session=db_session)

# ❌ Bad (model version won't resolve)
strategy_config = user_config_to_strategy_config(user_config)
```

### 2. Use Confidence Thresholds Wisely

- **Conservative**: 0.7 (70%) - Only use high-confidence ML predictions
- **Moderate**: 0.6 (60%) - Use medium-to-high confidence predictions
- **Aggressive**: 0.5 (50%) - Use all predictions above minimum threshold

### 3. Enable Combine Mode for Safety

For production trading, keep `ml_combine_with_rules=true` to ensure safety-first decisions.

### 4. Monitor Model Performance

Track ML predictions and their outcomes to identify when model retraining is needed.

### 5. Test Model Versions Before Activating

Before setting `is_active=True` for a new model version:
- Test on historical data
- Compare performance with current model
- Monitor initial predictions closely

---

## Changelog

### Version 1.0 (2025-12-05)

**Added**:
- ML configuration integration from UI
- Model version resolution via database
- Confidence-aware verdict combination logic
- Comprehensive test suite (49 tests)

**Fixed**:
- `ml_enabled` was hardcoded to `False` - now uses UI setting
- Feature extraction creating 44 features instead of 43
- Model version not resolving without `db_session`

**Changed**:
- `ml_combine_with_rules` now actually combines verdicts (not just shows both)
- Combination logic considers ML confidence level

---

## Related Documentation

- [Trading Configuration Guide](TRADING_CONFIG.md) - UI configuration options
- [ML Implementation Guide](../archive/documents/ML_IMPLEMENTATION_GUIDE.md) - ML system overview
- [Two-Stage Chart Quality + ML Approach](../documents/features/TWO_STAGE_CHART_QUALITY_ML_APPROACH.md) - Chart quality filtering

---

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review test files for usage examples
3. Check logs for detailed error messages
4. Verify database entries for model versions

---

**Last Updated**: 2025-12-05
**Maintainer**: Trading Agent Team
