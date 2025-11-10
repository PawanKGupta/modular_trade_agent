# Phase 2 Tests Documentation

This document describes the unit and integration tests created for Phase 2 implementation of configurable indicators.

## Test Structure

### Unit Tests

#### 1. `tests/unit/services/test_phase2_scoring_service.py`
Tests for ScoringService with configurable RSI thresholds:
- Default config usage
- Custom config acceptance
- Configurable RSI thresholds in scoring logic
- Timeframe analysis thresholds
- Extreme severity handling
- Non-buy verdict handling

**Key Tests:**
- `test_scoring_service_default_config`: Verifies default config is used
- `test_scoring_service_custom_config`: Verifies custom config is accepted
- `test_scoring_with_configurable_rsi_thresholds`: Tests configurable thresholds work
- `test_scoring_timeframe_analysis_thresholds`: Tests timeframe analysis uses config

#### 2. `tests/unit/core/test_phase2_patterns.py`
Tests for configurable pattern detection:
- `bullish_divergence` with configurable RSI period
- Configurable lookback period
- Backward compatibility with `rsi10` column
- Error handling for missing columns
- Insufficient data handling

**Key Tests:**
- `test_bullish_divergence_default_parameters`: Tests default parameters
- `test_bullish_divergence_custom_rsi_period`: Tests custom RSI period
- `test_bullish_divergence_backward_compatibility`: Tests backward compatibility

#### 3. `tests/unit/config/test_phase2_legacy_config.py`
Tests for legacy config constants deprecation:
- Legacy constants still exist for backward compatibility
- Legacy constants synced with StrategyConfig
- Default values verification
- Importability verification

**Key Tests:**
- `test_legacy_constants_synced_with_strategy_config`: Verifies sync
- `test_strategy_config_preferred`: Verifies StrategyConfig is preferred

#### 4. `tests/unit/services/test_phase2_analysis_service.py`
Tests for AnalysisService with pre-fetched data:
- Pre-fetched daily data acceptance
- Pre-calculated indicators optimization
- Config usage verification

**Key Tests:**
- `test_analysis_service_accepts_pre_fetched_daily`: Tests pre-fetched data
- `test_analysis_service_accepts_pre_calculated_indicators`: Tests pre-calculated indicators
- `test_analysis_service_uses_config`: Tests config propagation

#### 5. `tests/unit/modules/test_phase2_auto_trader_config.py`
Tests for auto-trader config sync:
- RSI period sync with StrategyConfig
- EMA settings separation
- Config importability

**Key Tests:**
- `test_auto_trader_rsi_period_synced`: Verifies RSI period sync
- `test_auto_trader_ema_settings_separate`: Verifies EMA settings are separate

### Integration Tests

#### 6. `tests/integration/test_phase2_complete.py`
Comprehensive integration tests for Phase 2:
- End-to-end analysis with configurable parameters
- All services using config correctly
- Legacy analysis.py with StrategyConfig
- Pattern detection in real scenarios
- Data optimization verification

**Key Test Classes:**
- `TestPhase2CompleteIntegration`: Main integration tests
- `TestPhase2DataOptimization`: Data fetching optimization tests

**Key Tests:**
- `test_analysis_service_with_custom_config`: Tests custom config end-to-end
- `test_scoring_service_with_custom_thresholds`: Tests custom thresholds
- `test_all_services_use_config`: Verifies all services use config
- `test_auto_trader_config_sync`: Verifies auto-trader config sync
- `test_analysis_service_pre_fetched_data_parameter`: Tests pre-fetched data parameters

## Running Tests

### Run All Phase 2 Tests
```bash
pytest tests/unit/services/test_phase2_scoring_service.py \
       tests/unit/core/test_phase2_patterns.py \
       tests/unit/config/test_phase2_legacy_config.py \
       tests/unit/services/test_phase2_analysis_service.py \
       tests/unit/modules/test_phase2_auto_trader_config.py \
       tests/integration/test_phase2_complete.py -v
```

### Run Unit Tests Only
```bash
pytest tests/unit/ -k "phase2" -v
```

### Run Integration Tests Only
```bash
pytest tests/integration/test_phase2_complete.py -v -m integration
```

### Run Specific Test File
```bash
pytest tests/unit/services/test_phase2_scoring_service.py -v
```

### Run with Coverage
```bash
pytest tests/unit/ tests/integration/ -k "phase2" --cov=. --cov-report=html
```

## Test Coverage

### Phase 2 Tasks Covered

1. ✅ **Scoring Service with Configurable RSI Thresholds**
   - Unit tests: `test_phase2_scoring_service.py`
   - Integration tests: `test_phase2_complete.py`

2. ✅ **Pattern Detection with Configurable Parameters**
   - Unit tests: `test_phase2_patterns.py`
   - Integration tests: `test_phase2_complete.py`

3. ✅ **Legacy Config Constants Deprecation**
   - Unit tests: `test_phase2_legacy_config.py`
   - Integration tests: `test_phase2_complete.py`

4. ✅ **AnalysisService with Pre-fetched Data**
   - Unit tests: `test_phase2_analysis_service.py`
   - Integration tests: `test_phase2_complete.py`

5. ✅ **Auto-Trader Config Sync**
   - Unit tests: `test_phase2_auto_trader_config.py`
   - Integration tests: `test_phase2_complete.py`

6. ✅ **Service Layer Config Usage**
   - Integration tests: `test_phase2_complete.py`

7. ✅ **Data Fetching Optimization**
   - Unit tests: `test_phase2_analysis_service.py`
   - Integration tests: `test_phase2_complete.py`

## Test Markers

Tests use pytest markers:
- `@pytest.mark.unit`: Unit tests (auto-marked based on path)
- `@pytest.mark.integration`: Integration tests (auto-marked based on path)
- `@pytest.mark.slow`: Slow-running tests (may require network/data)

## Notes

1. **Network Tests**: Some integration tests may require network access for data fetching. These are marked with `@pytest.mark.slow` and `@pytest.mark.integration`.

2. **Mocking**: Unit tests use mocking to avoid external dependencies. Integration tests may use real data fetching.

3. **Backward Compatibility**: Tests verify backward compatibility is maintained where needed.

4. **Config Propagation**: Tests verify that StrategyConfig is properly propagated through all service layers.

## Future Enhancements

1. Add performance benchmarks for data optimization
2. Add regression tests comparing old vs new behavior
3. Add E2E tests for complete workflows
4. Add stress tests for configurable parameters





