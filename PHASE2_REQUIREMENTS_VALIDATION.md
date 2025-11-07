# Phase 2: Requirements Validation Report

**Date:** 2025-11-07  
**Status:** ⚠️ **PARTIALLY COMPLETE** (8/15 required tasks complete, 7 pending)

---

## Executive Summary

**Completion Status:**
- ✅ **Required Tasks:** 8/11 complete (73%)
- ❌ **Required Tasks Missing:** 3/11 incomplete (27%)
- ⏸️ **Optional Tasks:** 0/4 complete (0%)

**Critical Missing Items:**
1. ❌ ML Feature Extraction Update (REQUIRED)
2. ❌ ScoringService Update (REQUIRED)
3. ❌ analyze_ticker() pre-fetched data support (REQUIRED)

---

## Detailed Requirements Validation

### ✅ COMPLETED TASKS (8/11 Required)

#### 1. ✅ Update core/indicators.py for RSI period
- **Status:** ✅ **COMPLETE**
- **Evidence:** `compute_indicators()` accepts `config` and `rsi_period` parameters
- **File:** `core/indicators.py`

#### 2. ✅ Update core/timeframe_analysis.py for lookbacks
- **Status:** ✅ **COMPLETE**
- **Evidence:** `TimeframeAnalysis` initialized with `StrategyConfig`, configurable lookbacks implemented
- **File:** `core/timeframe_analysis.py`

#### 3. ✅ Update core/data_fetcher.py for configurable data fetching
- **Status:** ✅ **COMPLETE**
- **Evidence:** `fetch_multi_timeframe_data()` accepts `config` parameter, uses configurable max years
- **File:** `core/data_fetcher.py`

#### 4. ✅ Update core/backtest_scoring.py for configurable RSI period
- **Status:** ✅ **COMPLETE**
- **Evidence:** `run_simple_backtest()` and `calculate_wilder_rsi()` accept `config` parameter
- **File:** `core/backtest_scoring.py`

#### 5. ✅ Sync BacktestConfig with StrategyConfig (REQUIRED per Q7)
- **Status:** ✅ **COMPLETE**
- **Evidence:** `BacktestConfig.from_strategy_config()` and `BacktestConfig.default_synced()` methods added
- **File:** `backtest/backtest_config.py`

#### 6. ✅ Update BacktestEngine to use fetch_multi_timeframe_data() (REQUIRED per Q10)
- **Status:** ✅ **COMPLETE**
- **Evidence:** `BacktestEngine._load_data()` uses `fetch_multi_timeframe_data()`
- **File:** `backtest/backtest_engine.py`

#### 7. ✅ Optimize integrated_backtest.py data fetching (CRITICAL per Q9)
- **Status:** ✅ **MOSTLY COMPLETE** (4/5 sub-tasks done)
- **Sub-tasks:**
  - ✅ Modify `run_backtest()` to return BacktestEngine instance
  - ✅ Reuse BacktestEngine data for position tracking (eliminate duplicate fetch)
  - ✅ Modify `trade_agent()` to accept pre-fetched data (optional parameter)
  - ❌ **MISSING:** Modify `analyze_ticker()` to accept pre-fetched data (optional parameter)
  - ✅ Update `run_integrated_backtest()` to pass data between components
- **File:** `integrated_backtest.py`

#### 8. ✅ Standardize indicator calculation methods (CRITICAL - Section 15)
- **Status:** ✅ **MOSTLY COMPLETE** (2/3 sub-tasks done)
- **Sub-tasks:**
  - ✅ Update `core/indicators.py` to use pandas_ta (consistent with BacktestEngine)
  - ✅ Make `compute_indicators()` accept configurable RSI/EMA periods
  - ⚠️ **PARTIAL:** Update `trade_agent()` to reuse BacktestEngine indicators (accepts but may not fully use)
- **Files:** `backtest/backtest_engine.py`, `core/indicators.py`

---

### ❌ MISSING REQUIRED TASKS (3/11 Required)

#### 9. ❌ Update ML feature extraction (REQUIRED - ML compatibility)
- **Status:** ❌ **NOT COMPLETE**
- **Current State:**
  - `MLVerdictService.__init__()` accepts `config` parameter ✅
  - `_extract_features()` still uses hardcoded values ❌
    - Line 207: `features['rsi_10']` (hardcoded)
    - Line 216: `features['avg_volume_20']` (hardcoded 20-period lookback)
    - Lines 232-233: `features['recent_high_20']` and `features['recent_low_20']` (hardcoded 20-period lookback)
- **Required Changes:**
  - Update feature extraction to use configurable RSI period: `f'rsi_{config.rsi_period}'`
  - Update feature extraction to use configurable lookbacks: `f'avg_volume_{config.volume_exhaustion_lookback_daily}'`
  - Update feature extraction to use configurable support/resistance lookbacks: `f'recent_high_{config.support_resistance_lookback_daily}'`
  - Maintain backward compatibility with existing models (keep old feature names if period == 10)
- **File:** `services/ml_verdict_service.py`
- **Priority:** ⚠️ **REQUIRED**

#### 10. ❌ Update scoring/verdict system (REQUIRED - Scoring compatibility)
- **Status:** ⚠️ **PARTIALLY COMPLETE** (1/2 sub-tasks done)
- **Sub-tasks:**
  - ❌ **MISSING:** Update `services/scoring_service.py` to use configurable RSI thresholds
    - **Current State:** Still uses hardcoded thresholds (30, 20) at lines 72-74
    - **Required:** Use `config.rsi_oversold` and `config.rsi_extreme_oversold`
  - ✅ **COMPLETE:** Update `core/backtest_scoring.py` RSI thresholds for entry conditions
    - **Evidence:** Uses `config.rsi_oversold` and `config.rsi_extreme_oversold` at lines 464-465
- **Files:** `services/scoring_service.py`, `core/backtest_scoring.py`
- **Priority:** ⚠️ **REQUIRED**

#### 11. ❌ Modify analyze_ticker() to accept pre-fetched data (REQUIRED per Q9)
- **Status:** ❌ **NOT COMPLETE**
- **Current State:** `analyze_ticker()` does not accept `pre_fetched_data` parameter
- **Required:** Add `pre_fetched_data` and `pre_calculated_indicators` parameters to `analyze_ticker()`
- **File:** `core/analysis.py`
- **Priority:** ⚠️ **REQUIRED** (for data fetching optimization)

---

### ⏸️ OPTIONAL TASKS (Not Required for Phase 2)

#### 12. ⏸️ Update legacy core/analysis.py (OPTIONAL - Medium priority)
- **Status:** ⏸️ **NOT DONE** (Optional)
- **Current State:** Still uses `config.settings` constants (`RSI_OVERSOLD`, `RSI_NEAR_OVERSOLD`)
- **Required Changes:**
  - Migrate from `config.settings` constants to `StrategyConfig`
  - Update RSI threshold usage to use configurable values
  - Replace `RSI_OVERSOLD` imports with `StrategyConfig.rsi_oversold`
  - Update hardcoded `rsi_threshold = 20` to use `config.rsi_extreme_oversold`
  - Update `rsi10` column references to use configurable `rsi{config.rsi_period}`
- **File:** `core/analysis.py`
- **Priority:** ⏸️ **OPTIONAL**

#### 13. ⏸️ Sync auto-trader config (OPTIONAL - Medium priority)
- **Status:** ⏸️ **NOT DONE** (Optional)
- **Current State:** `modules/kotak_neo_auto_trader/config.py` has `RSI_PERIOD = 10` (matches default)
- **Required Changes:**
  - Sync `kotak_neo_auto_trader/config.py` RSI_PERIOD with StrategyConfig
  - Keep EMA_SHORT/EMA_LONG separate (auto-trader specific)
  - Update `auto_trade_engine.py` to use synced RSI period
- **Files:** `modules/kotak_neo_auto_trader/config.py`, `auto_trade_engine.py`
- **Priority:** ⏸️ **OPTIONAL**

#### 14. ⏸️ Make pattern detection configurable (OPTIONAL - Low priority)
- **Status:** ⏸️ **NOT DONE** (Optional)
- **Current State:** `bullish_divergence()` uses hardcoded `'rsi10'` column at lines 36, 38
- **Required Changes:**
  - Update `core/patterns.py` `bullish_divergence()` to accept `rsi_period` parameter
  - Make lookback period configurable (default: 10)
  - Use configurable RSI column name `f'rsi{rsi_period}'`
- **File:** `core/patterns.py`
- **Priority:** ⏸️ **OPTIONAL**

#### 15. ⏸️ Deprecate legacy config constants (OPTIONAL - Medium priority)
- **Status:** ⏸️ **NOT DONE** (Optional)
- **Current State:** `config/settings.py` still has `RSI_OVERSOLD = 30` and `RSI_NEAR_OVERSOLD = 40` without deprecation warnings
- **Required Changes:**
  - Add deprecation warnings to `config/settings.py` for `RSI_OVERSOLD` and `RSI_NEAR_OVERSOLD`
  - Update all remaining usages to use `StrategyConfig`
  - Document migration path in deprecation messages
- **File:** `config/settings.py`
- **Priority:** ⏸️ **OPTIONAL**

#### 16. ⏸️ Update service layer to pass config
- **Status:** ⏸️ **NOT VERIFIED** (Optional)
- **Note:** Need to verify if service layer components pass config correctly
- **Priority:** ⏸️ **OPTIONAL**

---

## Summary

### Required Tasks Status
- ✅ **Complete:** 8/11 (73%)
- ❌ **Missing:** 3/11 (27%)

### Missing Required Tasks Breakdown
1. ❌ **ML Feature Extraction Update** - `services/ml_verdict_service.py` (REQUIRED)
2. ❌ **ScoringService Update** - `services/scoring_service.py` (REQUIRED)
3. ❌ **analyze_ticker() pre-fetched data** - `core/analysis.py` (REQUIRED)

### Optional Tasks Status
- ⏸️ **Complete:** 0/4 (0%)
- ⏸️ **Pending:** 4/4 (100%)

---

## Recommendations

### Immediate Actions (Required)
1. **Update ML Feature Extraction** (`services/ml_verdict_service.py`)
   - Make feature names dynamic based on config
   - Maintain backward compatibility
   - Estimated time: 2-3 hours

2. **Update ScoringService** (`services/scoring_service.py`)
   - Replace hardcoded RSI thresholds (30, 20) with configurable values
   - Use `config.rsi_oversold` and `config.rsi_extreme_oversold`
   - Estimated time: 1-2 hours

3. **Add pre-fetched data support to analyze_ticker()** (`core/analysis.py`)
   - Add `pre_fetched_data` and `pre_calculated_indicators` parameters
   - Use pre-fetched data if available
   - Estimated time: 1-2 hours

### Future Actions (Optional)
- Legacy code migration (when time permits)
- Auto-trader config sync (when needed)
- Pattern detection configurable (low priority)
- Config deprecation (when ready to remove legacy code)

---

## Conclusion

**Phase 2 Status:** ⚠️ **73% COMPLETE** (8/11 required tasks)

The Phase 2 completion document correctly identifies that **8 core tasks are complete**, but it **incorrectly marks optional tasks as "not required"** when some are actually **REQUIRED** per the user's requirements list.

**Critical Gap:** 3 required tasks are missing:
1. ML feature extraction update
2. ScoringService update
3. analyze_ticker() pre-fetched data support

These should be completed before considering Phase 2 fully complete.

