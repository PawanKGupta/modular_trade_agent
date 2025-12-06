# ML Configuration and Quality Filtering Enhancements

## Overview

This document describes the comprehensive enhancements made to the trading system to improve ML configuration handling, quality filtering, and recommendation prioritization. These enhancements ensure that ML predictions are properly integrated throughout the analysis pipeline and that only high-quality stocks are recommended for trading.

## Table of Contents

1. [ML Configuration Enhancements](#ml-configuration-enhancements)
2. [Quality-Focused Filtering](#quality-focused-filtering)
3. [Priority-Based Order Placement](#priority-based-order-placement)
4. [Configuration Flow](#configuration-flow)
5. [Testing](#testing)
6. [Migration Guide](#migration-guide)

---

## ML Configuration Enhancements

### Problem Statement

Previously, ML configuration settings from the UI (such as `ml_enabled`, `ml_confidence_threshold`, `ml_combine_with_rules`) were not consistently respected throughout the analysis pipeline, particularly in backtesting scenarios. This led to situations where ML was disabled in logs even when enabled in the UI.

### Solution

#### 1. Config Passing Through Analysis Pipeline

**Files Modified:**
- `services/analysis_service.py`
- `integrated_backtest.py`
- `core/backtest_scoring.py`
- `services/backtest_service.py`
- `trade_agent.py`

**Changes:**

1. **AnalysisService** now stores the `StrategyConfig` in analysis results:
   ```python
   result['_config'] = self.config
   ```

2. **BacktestService** extracts and passes config through the backtest chain:
   ```python
   def add_backtest_scores_to_results(self, results, config=None):
       # Extract config from first result if not provided
       if config is None and results:
           config = results[0].get('_config')
       # Pass config to run_stock_backtest
       backtest_result = self.run_stock_backtest(ticker, config=config)
   ```

3. **integrated_backtest.py** respects config when validating entries:
   ```python
   def validate_initial_entry_with_trade_agent(..., config=None):
       if config is None:
           # Try to load from environment variable
           user_id_str = os.environ.get("TRADE_AGENT_USER_ID")
           if user_id_str:
               config = load_user_config_from_db(user_id)
           else:
               config = StrategyConfig.default()
       service = AnalysisService(config=config)
   ```

#### 2. Environment Variable Support

When `trade_agent.py` is run as a subprocess, it now:
- Reads `TRADE_AGENT_USER_ID` from environment
- Loads user-specific `StrategyConfig` from database
- Passes config to `AsyncAnalysisService`

**Implementation:**
```python
# In trade_agent.py
user_id_str = os.environ.get("TRADE_AGENT_USER_ID")
if user_id_str:
    user_id = int(user_id_str)
    db_session = next(get_session())
    config_repo = UserTradingConfigRepository(db_session)
    user_config = config_repo.get_or_create_default(user_id)
    config = user_config_to_strategy_config(user_config, db_session=db_session)
```

#### 3. Config Converter Fixes

**File:** `src/application/services/config_converter.py`

- Fixed `ml_enabled` to use `user_config.ml_enabled` instead of hardcoded `False`
- Added `_resolve_ml_model_path` to resolve model paths from `ml_model_version`
- Ensures ML model path is correctly resolved from version

---

## Quality-Focused Filtering

### Problem Statement

The previous filtering logic had several issues:
1. ML-only recommendations bypassed quality filters
2. No minimum quality thresholds for ML-only signals
3. Backtest results were not used to filter low-quality stocks
4. Inconsistent score thresholds between rule-based and ML-only paths

### Solution

#### 1. Backtest Quality Filters

**New Function:** `_passes_backtest_quality_filters()`

**Location:** `trade_agent.py`

**Filters Applied:**
- **Win Rate:** Minimum 65% (configurable)
- **Average Profit:** Minimum 1.5% per trade (configurable)
- **Backtest Score:** Minimum 45/100 (configurable)
- **Positive Return:** Total return must be positive (configurable)
- **No Minimum Trades:** Removed requirement for 5+ trades (1 trade with 100% win rate is valuable)

**Implementation:**
```python
def _passes_backtest_quality_filters(
    result,
    min_win_rate=65.0,
    min_avg_profit=1.5,
    min_backtest_score=45.0,
    require_positive_return=True
):
    backtest = result.get("backtest", {})
    if not backtest:
        return True  # No backtest data = pass (backward compatibility)

    win_rate = backtest.get("win_rate", 0)
    avg_return = backtest.get("avg_return", 0)
    total_return = backtest.get("total_return_pct", 0)
    backtest_score = backtest.get("score", 0)

    # Check all quality criteria
    if win_rate < min_win_rate:
        return False
    if avg_return < min_avg_profit:
        return False
    if require_positive_return and total_return <= 0:
        return False
    if backtest_score < min_backtest_score:
        return False

    return True
```

#### 2. ML Confidence Normalization

**New Function:** `_normalize_ml_confidence()`

**Purpose:** Handles both 0-1 and 0-100 ML confidence formats

**Implementation:**
```python
def _normalize_ml_confidence(confidence):
    """Normalize ML confidence to 0-1 range"""
    if confidence is None:
        return 0.0
    if confidence > 1.0:
        # Assume percentage format (0-100), convert to decimal
        logger.debug(f"Converting ML confidence from percentage to decimal: {confidence}% -> {confidence/100}")
        return confidence / 100.0
    return confidence
```

#### 3. Enhanced Filtering Logic

**Location:** `trade_agent.py::_process_results()`

**Key Improvements:**

1. **Config Extraction First:**
   ```python
   # Extract config from first result
   config = None
   if results:
       config = results[0].get("_config")
   ```

2. **ML-Only Minimum Score Threshold:**
   - Changed from `combined_score >= 0` to `combined_score >= 20`
   - Applied to all ML-only filtering paths

3. **ML Verdict Check Even When Combine=True:**
   - If `final_verdict` is "watch" or "avoid" but ML says "buy"/"strong_buy"
   - Check ML confidence and score thresholds
   - Include if quality filters pass

4. **Respect `ml_enabled` Flag:**
   - ML verdicts are only considered if `config.ml_enabled is True`
   - Prevents ML-only signals when ML is disabled

5. **Backtest Quality Filters Applied:**
   - Applied to all buy/strong_buy filtering paths
   - Ensures only high-quality stocks pass

**Filtering Flow:**
```
For each result:
  ├─ Extract config (if not provided)
  ├─ Normalize ML confidence
  ├─ Apply backtest quality filters
  │   ├─ min_backtest_score >= 45.0
  │   ├─ min_win_rate >= 65.0% (if trades > 0)
  │   ├─ min_avg_profit >= 1.5% (if trades > 0)
  │   └─ require_positive_return = True
  ├─ Check if rule-based buy/strong_buy
  │   └─ combined_score >= 25
  ├─ Check if ML-only buy/strong_buy (when combine=false)
  │   ├─ Verify ml_enabled=True
  │   ├─ Check ML confidence >= threshold (default 100%)
  │   └─ Check combined_score >= 20
  └─ Check if weak final_verdict but ML says buy (when combine=true)
      ├─ Verify ml_enabled=True
      ├─ Check ML confidence >= threshold (default 100%)
      └─ Check combined_score >= 20
```

**Note:** All ML predictions (initial and backtest) use the same `ml_confidence_threshold` without any adjustments.

---

## Priority-Based Order Placement

### Problem Statement

Buy and strong_buy recommendations were not being prioritized for order placement. The system needed a way to rank recommendations based on multiple factors, including ML confidence.

### Solution

#### 1. Priority Score Calculation

**Location:** `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Factors Considered:**
- Risk-reward ratio
- RSI value
- Volume strength
- Multi-timeframe alignment
- PE ratio
- Backtest score
- Chart quality

**ML Confidence Boost:**
- **High Confidence (>=70%):** +20 points
- **Medium Confidence (60-70%):** +10 points
- **Low Confidence (50-60%):** +5 points
- **Below Threshold (<50%):** No boost

**Note:** With default `ml_confidence_threshold = 1.0` (100%), only very high confidence ML predictions will pass the threshold. Users can lower this threshold via configuration if needed.

**Implementation:**
```python
def load_latest_recommendations(self, ...):
    # Extract priority_score from signal/CSV
    priority_score = signal.priority_score or signal.combined_score

    # Apply ML confidence boost
    ml_confidence = signal.ml_confidence
    if ml_confidence is not None:
        ml_conf_normalized = ml_confidence if ml_confidence <= 1.0 else ml_confidence / 100.0

        if ml_conf_normalized >= 0.70:
            priority_score += 20  # High confidence boost
        elif ml_conf_normalized >= 0.60:
            priority_score += 10  # Medium confidence boost
        elif ml_conf_normalized >= 0.50:
            priority_score += 5   # Low confidence boost

    # Sort by priority_score (descending)
    recommendations.sort(key=lambda r: r.priority_score or 0, reverse=True)
```

#### 2. Database Support

**Model:** `src/infrastructure/db/models.py::Signals`

**Fields Added:**
- `priority_score`: Float field for priority ranking
- `combined_score`: Fallback if priority_score is missing

**CSV Support:**
- `priority_score` column extracted from CSV
- Falls back to `combined_score` if missing

---

## Configuration Flow

### End-to-End Config Flow

```
UI (UserTradingConfig)
    ↓
config_converter.py (user_config_to_strategy_config)
    ↓
StrategyConfig (dataclass)
    ↓
AnalysisService.__init__(config=config)
    ↓
AnalysisService.analyze_ticker()
    ├─ Stores config in result: result['_config'] = self.config
    └─ Returns result with _config
        ↓
trade_agent.py::_process_results()
    ├─ Extracts config from results[0].get('_config')
    └─ Passes to BacktestService.add_backtest_scores_to_results(config=config)
        ↓
BacktestService.add_backtest_scores_to_results()
    ├─ Uses provided config or extracts from result['_config']
    └─ Passes to run_stock_backtest(config=config)
        ↓
core/backtest_scoring.py::run_stock_backtest()
    └─ Passes to run_integrated_backtest(config=config)
        ↓
integrated_backtest.py::run_integrated_backtest()
    └─ Passes to validate_initial_entry_with_trade_agent(config=config)
        ↓
integrated_backtest.py::validate_initial_entry_with_trade_agent()
    ├─ Uses provided config OR
    ├─ Loads from TRADE_AGENT_USER_ID env var OR
    └─ Falls back to StrategyConfig.default()
        ↓
AnalysisService(config=config) [new instance]
    └─ Uses config.ml_enabled to decide MLVerdictService vs VerdictService
```

### Subprocess Execution Flow

```
IndividualServiceManager
    ↓
Sets TRADE_AGENT_USER_ID environment variable
    ↓
Calls trade_agent.py as subprocess
    ↓
trade_agent.py::main_async() or main_sequential()
    ├─ Reads TRADE_AGENT_USER_ID from environment
    ├─ Loads user config from database
    └─ Initializes AsyncAnalysisService(config=config)
        ↓
AsyncAnalysisService
    └─ Passes config to AnalysisService
        ↓
AnalysisService
    └─ Stores config in results: result['_config'] = self.config
```

---

## Testing

### Test Coverage

#### 1. ML Configuration Tests

**File:** `tests/unit/integrated_backtest/test_integrated_backtest_ml_config.py`

**Tests:**
- `test_validate_initial_entry_uses_provided_config`
- `test_validate_initial_entry_loads_config_from_env_when_none`
- `test_validate_initial_entry_defaults_when_no_env_var`
- `test_validate_initial_entry_logs_config_usage`

#### 2. BacktestService Config Tests

**File:** `tests/unit/services/test_backtest_service_ml_config_respect.py`

**Tests:**
- `test_backtest_service_passes_config_to_run_stock_backtest`
- `test_backtest_service_uses_config_from_result_if_available`
- `test_backtest_service_logs_config_usage`
- `test_backtest_service_warns_when_no_config`

#### 3. Quality Filtering Tests

**File:** `tests/unit/trade_agent/test_trade_agent_quality_filters.py`

**Tests:**
- `test_backtest_quality_filters_pass_high_quality_stocks`
- `test_ml_verdict_checked_when_final_verdict_weak`
- `test_ml_only_minimum_score_threshold`
- `test_no_minimum_trades_requirement`
- `test_config_extracted_first`
- `test_ml_enabled_respected_in_filtering`
- `test_ml_confidence_normalization_logging`

#### 4. Priority Ordering Tests

**File:** `tests/unit/modules/test_auto_trade_engine_priority_ordering.py`

**Tests:**
- CSV loading with priority scores
- Database loading with priority scores
- ML confidence boost (high, medium, low)
- Fallback to combined_score

### Running Tests

```bash
# Run all ML config tests
pytest tests/unit/integrated_backtest/test_integrated_backtest_ml_config.py -v
pytest tests/unit/services/test_backtest_service_ml_config_respect.py -v

# Run quality filtering tests
pytest tests/unit/trade_agent/test_trade_agent_quality_filters.py -v

# Run priority ordering tests
pytest tests/unit/modules/test_auto_trade_engine_priority_ordering.py -v

# Run all related tests
pytest tests/unit/integrated_backtest/ tests/unit/services/test_backtest_service_ml_config*.py tests/unit/trade_agent/test_trade_agent_quality_filters.py -v
```

---

## Migration Guide

### For Developers

#### 1. Using StrategyConfig in New Code

**Before:**
```python
service = AnalysisService()  # Uses default config
```

**After:**
```python
# Load user config
config = load_user_config(user_id)
service = AnalysisService(config=config)
```

#### 2. Passing Config Through Functions

**Before:**
```python
def run_backtest(stock_symbol):
    # No config passed
    result = analyze_stock(stock_symbol)
```

**After:**
```python
def run_backtest(stock_symbol, config=None):
    # Extract config from result if not provided
    if config is None:
        result = analyze_stock(stock_symbol)
        config = result.get('_config')
    # Pass config to subsequent calls
    backtest_result = run_integrated_backtest(stock_symbol, config=config)
```

#### 3. Handling ML Configuration

**Before:**
```python
if ml_enabled:  # Hardcoded or missing
    use_ml_service()
```

**After:**
```python
if config and config.ml_enabled:
    use_ml_service()
```

### For Users

#### 1. Enabling ML Predictions

1. Go to Trading Configuration in UI
2. Enable "ML Predictions"
3. Set "ML Confidence Threshold" (recommended: 50-70%)
4. Choose "Combine ML with Rule-Based Logic" (recommended: enabled for safety)

#### 2. Understanding Quality Filters

The system now applies quality filters to all recommendations:
- **Win Rate:** Must be >= 65%
- **Average Profit:** Must be >= 1.5% per trade
- **Backtest Score:** Must be >= 45/100
- **Positive Return:** Total return must be positive

These filters ensure only high-quality stocks are recommended.

#### 3. Priority-Based Ordering

Recommendations are now automatically sorted by priority score:
- Higher priority = better risk-reward
- ML confidence boosts priority (high confidence = +20 points)
- Orders are placed in priority order

---

## Configuration Parameters

### ML Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ml_enabled` | bool | `False` | Enable/disable ML predictions |
| `ml_model_version` | str | `None` | ML model version to use |
| `ml_confidence_threshold` | float | `1.0` | Minimum ML confidence (0-1), default 100% |
| `ml_combine_with_rules` | bool | `True` | Combine ML with rule-based logic |

### Quality Filter Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_win_rate` | float | `65.0` | Minimum win rate (%) |
| `min_avg_profit` | float | `1.5` | Minimum average profit per trade (%) |
| `min_backtest_score` | float | `45.0` | Minimum backtest score (0-100) |
| `require_positive_return` | bool | `True` | Require positive total return |
| `ml_score_min` | float | `20.0` | Minimum combined_score for ML-only signals |

### Priority Boost Parameters

| ML Confidence | Boost | Description |
|---------------|-------|-------------|
| >= 70% | +20 | High confidence |
| 60-70% | +10 | Medium confidence |
| 50-60% | +5 | Low confidence |
| < 50% | +0 | Below threshold |

---

## Troubleshooting

### Issue: ML Still Disabled in Logs

**Symptoms:**
- Log shows "ML is disabled in config, using VerdictService"
- But ML is enabled in UI

**Solutions:**
1. Check that `TRADE_AGENT_USER_ID` environment variable is set when running as subprocess
2. Verify user config is loaded correctly in `trade_agent.py`
3. Check that `config.ml_enabled` is `True` after loading

### Issue: No ML-Only Recommendations

**Symptoms:**
- ML is enabled but no ML-only signals appear

**Possible Causes:**
1. `ml_combine_with_rules=True` - ML-only path is disabled when combine is enabled
2. ML confidence below threshold
3. `combined_score < 20` (minimum threshold)
4. Backtest quality filters failing

**Solutions:**
1. Set `ml_combine_with_rules=False` to enable ML-only path
2. Lower `ml_confidence_threshold` if needed (default is 100%, which is very strict)
3. Check backtest results for quality issues
4. Verify ML predictions are being generated and stored in CSV

### Issue: Config Not Passed to Backtest

**Symptoms:**
- Backtest uses default config instead of user config

**Solutions:**
1. Ensure `result['_config']` is set in `AnalysisService.analyze_ticker()`
2. Verify `BacktestService.add_backtest_scores_to_results()` extracts config from results
3. Check that `run_integrated_backtest()` receives config parameter

---

## Performance Considerations

### Config Loading

- Config is loaded once per analysis run
- Cached in `result['_config']` for reuse
- Database queries only when `TRADE_AGENT_USER_ID` is set

### Quality Filtering

- Quality filters are applied during result processing
- Minimal performance impact (simple comparisons)
- Backtest data must be present for filters to work

### Priority Calculation

- Priority score calculated once per recommendation
- Sorting is O(n log n) but n is typically small (< 100)
- ML confidence boost is O(1) operation

---

## Future Enhancements

### Potential Improvements

1. **Configurable Quality Thresholds:**
   - Allow users to customize quality filter thresholds via UI
   - Store in `UserTradingConfig`

2. **Dynamic Priority Weights:**
   - Allow users to adjust priority score weights
   - Fine-tune ML confidence boost amounts

3. **Quality Filter Presets:**
   - Conservative: Higher thresholds
   - Moderate: Default thresholds
   - Aggressive: Lower thresholds

4. **ML Model Versioning:**
   - Support multiple ML models per user
   - A/B testing capabilities

5. **Config Validation:**
   - Validate config parameters before use
   - Warn about invalid combinations

---

## References

### Related Documentation

- [ML Configuration Enhancements](./ML_CONFIGURATION_ENHANCEMENTS.md) - Original ML config documentation
- [Strategy Config](./STRATEGY_CONFIG.md) - Strategy configuration details
- [Backtest Scoring](./BACKTEST_SCORING.md) - Backtest scoring implementation

### Code References

- `config/strategy_config.py` - StrategyConfig dataclass
- `src/application/services/config_converter.py` - Config conversion
- `services/analysis_service.py` - Analysis service with config support
- `integrated_backtest.py` - Integrated backtest with config
- `trade_agent.py` - Trade agent with quality filtering
- `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Priority ordering

---

## Changelog

### Version 1.0.0 (Current)

**Added:**
- ML configuration respect throughout analysis pipeline
- Quality-focused filtering with backtest quality filters
- ML confidence normalization
- Priority-based order placement with ML confidence boost
- Environment variable support for subprocess execution
- Comprehensive test coverage

**Fixed:**
- ML disabled in logs when enabled in UI
- Config not passed to backtest
- ML-only recommendations bypassing quality filters
- Inconsistent score thresholds

**Changed:**
- Removed minimum trades requirement (5+ trades)
- Changed ML-only minimum score from 0 to 20
- Enhanced filtering logic to respect `ml_combine_with_rules`

---

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Review test files for usage examples
3. Check logs for detailed debug information
4. Contact the development team

---

---

## Recent Updates (2025-12-05)

### CSV Export Enhancements

1. **ML Verdicts in CSV:**
   - ML predictions (`ml_verdict`, `ml_confidence`, `ml_probabilities`) are now properly stored in CSV files
   - All columns are included even if values are None/empty
   - `ml_confidence` and `combined_score` are rounded to 2 decimal places for cleaner output

2. **Default ML Confidence Threshold:**
   - Changed default `ml_confidence_threshold` from `0.5` (50%) to `1.0` (100%)
   - This ensures only high-confidence ML predictions are used by default
   - User can still override via configuration

3. **Backtest ML Predictions:**
   - Backtest ML predictions are now properly stored and used
   - No special threshold adjustments - uses full `ml_confidence_threshold`
   - Backtest ML predictions are validated from profitable trades

4. **Quality Filter Thresholds:**
   - Restored original quality filter thresholds:
     - `min_backtest_score = 45.0`
     - `min_win_rate = 65.0%`
     - `min_avg_profit = 1.5%`
   - No special adjustments for backtest ML predictions

5. **Code Cleanup:**
   - Removed all debug logging statements
   - Removed temporary debugging modifications
   - Code is now production-ready

---

**Last Updated:** 2025-12-05
**Version:** 1.1.0
