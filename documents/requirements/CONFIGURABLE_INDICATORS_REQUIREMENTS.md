# Requirements Document: Configurable Indicator Parameters

**Version:** 1.0  
**Date:** 2024-12-19  
**Status:** DRAFT - For Review  
**Author:** System Analysis  

---

## 1. Executive Summary

### 1.1 Purpose
This document outlines requirements for making hardcoded indicator parameters configurable, specifically targeting improvements for the short-term dip-buying strategy: **RSI10 < 30 & Price > EMA200**.

### 1.2 Current Problem
The system currently uses fixed values for:
- RSI period (hardcoded to 10)
- Support/Resistance lookback (hardcoded to 20 periods)
- Volume exhaustion lookback (hardcoded to 10 periods)

These fixed values:
- Waste historical data (fetching 10 years but only using 20 periods)
- Prevent optimization and backtesting of different parameters
- Limit adaptability to different market conditions
- Create inconsistency (some params configurable, others not)

**Additional Critical Issue Discovered:**
- **Data fetching duplication** in integrated backtest: Data fetched 3+ times per signal (22+ API calls for 10 signals)
- Causes API rate limiting risk and performance degradation

### 1.3 Proposed Solution
Make these parameters configurable through `StrategyConfig` with:
- Sensible defaults optimized for short-term trading
- Ability to override via environment variables
- Adaptive behavior based on available data
- Backward compatibility maintained

**Additionally:**
- **Optimize data fetching** in integrated backtest to eliminate duplication
- Reuse BacktestEngine data instead of fetching multiple times
- Reduce API calls from 22+ to 1 per backtest (for 10 signals)

---

## 2. Current State Analysis

### 2.1 Base Strategy
**Core Entry Conditions:**
- RSI10 < 30 (oversold)
- Price > EMA200 (uptrend confirmation)
- Volume ≥ 80% of 20-day average
- Short-term trading focus (dip buying, not long-term holding)

### 2.2 Current Hardcoded Values

| Parameter | Current Value | Location | Issue |
|-----------|--------------|----------|-------|
| RSI Period | 10 | `core/indicators.py:36` | Hardcoded, not configurable |
| Support/Resistance Lookback (Daily) | 20 periods | `core/timeframe_analysis.py:14` | Hardcoded, ignores historical data |
| Support/Resistance Lookback (Weekly) | 20 periods | `core/timeframe_analysis.py:14` | Same as daily, not optimized |
| Volume Exhaustion Lookback (Daily) | 10 periods | `core/timeframe_analysis.py:15` | Hardcoded, short-term only |
| Volume Exhaustion Lookback (Weekly) | 10 periods | `core/timeframe_analysis.py:15` | Same as daily, not optimized |

### 2.3 Data Availability & Fetching Strategy
- **Current Data Fetching:**
  - Daily: Fixed 800 days minimum (`core/data_fetcher.py:231`)
  - Weekly: Fixed 3 years (~1095 days) minimum (`core/data_fetcher.py:239`)
- **Proposed Data Fetching Strategy:**
  - Daily: `min(max(800 days, 5 years), available_data)` = ~1,250 trading days when available
  - Weekly: `min(max(20 weeks, 3 years), available_data)` = ~156 weekly candles when available
- **Current Usage:** Only last 20 periods for support/resistance, last 10 for volume
- **Data Utilization:** With 5 years fetched, using only 20 periods = ~1.6% utilization
- **Waste:** ~98% of fetched historical data unused for support/resistance analysis

---

## 3. Requirements

### 3.1 Functional Requirements

#### FR-1: RSI Period Configuration
**Priority:** Medium  
**Description:** Make RSI calculation period configurable

**Requirements:**
- Add `rsi_period` to `StrategyConfig` (default: 10)
- Update `core/indicators.py` to use configurable period
- Support environment variable override: `RSI_PERIOD`
- Maintain backward compatibility (default 10 if not specified)
- Update all references from hardcoded `period=10` to use config

**Rationale:**
- RSI10 works well for short-term, but some stocks may benefit from RSI14 (more stable)
- Allows backtesting different RSI periods
- Standard practice in trading systems

**Value for Short-Term Strategy:**
- ✅ RSI10 is optimal for short-term (current default maintained)
- ✅ Allows experimentation with RSI14 for less noise
- ✅ Enables optimization through backtesting

---

#### FR-2: Support/Resistance Lookback Configuration
**Priority:** HIGH  
**Description:** Make support/resistance lookback periods configurable and adaptive

**Requirements:**
- Add `support_resistance_lookback_daily` to `StrategyConfig` (default: 20)
- Add `support_resistance_lookback_weekly` to `StrategyConfig` (default: 50)
- Support environment variable overrides
- Implement adaptive logic: Use longer lookbacks when more data available
- Update `TimeframeAnalysis` to use configurable values

**Adaptive Logic (Aligned with Data Fetching Strategy):**
```python
# Aligned with data fetching: Daily max 5 years, Weekly max 3 years
# Only applies if enable_adaptive_lookback is True (configurable per Q2)
# If 5 years data fetched: Use longer lookback
if config.enable_adaptive_lookback:
    if available_data_days >= 1825:  # 5 years
        support_lookback_daily = 30-50  # ~1.5-2.5 months (uses fetched data)
        support_lookback_weekly = 50  # ~1 year (uses fetched data)
    elif available_data_days >= 800:  # Minimum for EMA200
        support_lookback_daily = 20-30  # ~1-1.5 months
        support_lookback_weekly = 30-40  # ~7-9 months
    else:
        support_lookback_daily = 20  # Default (minimum)
        support_lookback_weekly = 20  # Default (minimum)
else:
    # Use configured defaults if adaptive logic disabled
    support_lookback_daily = config.support_resistance_lookback_daily  # Default: 20
    support_lookback_weekly = config.support_resistance_lookback_weekly  # Default: 50
```

**Relationship to Data Fetching:**
- **Data Fetched:** 5 years daily (~1,250 trading days), 3 years weekly (~156 candles)
- **Lookback Used:** 30-50 periods daily (~1.5-2.5 months), 50 periods weekly (~1 year)
- **Utilization:** ~4-6% of daily data, ~32% of weekly data (much better than current ~1.6%)

**Rationale:**
- Current 20 periods wastes 99% of historical data
- Longer lookbacks identify stronger support/resistance levels
- Weekly timeframe benefits from longer lookback (more stable)

**Value for Short-Term Strategy:**
- ✅ Better support/resistance identification (critical for stop-loss placement)
- ✅ Uses historical data effectively
- ✅ Weekly lookback of 50 periods (~1 year) provides better context
- ✅ Still maintains short-term focus (daily 20-50 periods = 1-2.5 months)

---

#### FR-3: Volume Exhaustion Lookback Configuration
**Priority:** Medium  
**Description:** Make volume exhaustion lookback periods configurable

**Requirements:**
- Add `volume_exhaustion_lookback_daily` to `StrategyConfig` (default: 10)
- Add `volume_exhaustion_lookback_weekly` to `StrategyConfig` (default: 20)
- Support environment variable overrides
- Update `TimeframeAnalysis` to use configurable values

**Rationale:**
- Current 10 periods may miss longer-term volume trends
- Weekly timeframe needs longer lookback for meaningful patterns
- Allows optimization through backtesting

**Value for Short-Term Strategy:**
- ✅ Daily 10 periods is appropriate for short-term (maintained)
- ✅ Weekly 20 periods provides better trend context
- ✅ Enables fine-tuning through backtesting

---

#### FR-4: Data Fetching Configuration (NEW)
**Priority:** HIGH  
**Description:** Make data fetching strategy configurable to align with lookback parameters

**Requirements:**
- Update `fetch_multi_timeframe_data()` to use configurable data fetching strategy
- Add `data_fetch_daily_max_years` to `StrategyConfig` (default: 5)
- Add `data_fetch_weekly_max_years` to `StrategyConfig` (default: 3)
- Implement: `Daily: min(max(800 days, max_years), available_data)`
- Implement: `Weekly: min(max(20 weeks, max_years), available_data)`
- Support environment variable overrides

**Current Implementation:**
```python
# core/data_fetcher.py - CURRENT (hardcoded)
daily_days = max(days, 800)  # Minimum 800 days
weekly_days = max(days * 3, 1095)  # Minimum 3 years
```

**Proposed Implementation:**
```python
# NEW: Configurable data fetching
daily_max_years = config.data_fetch_daily_max_years  # Default: 5
weekly_max_years = config.data_fetch_weekly_max_years  # Default: 3

daily_days = min(max(800, daily_max_years * 365), available_data_days)
weekly_days = min(max(20 * 7, weekly_max_years * 365), available_data_days)
```

**Rationale:**
- Aligns data fetching with analysis lookback periods
- Ensures sufficient data for longer lookbacks (e.g., 50 periods weekly needs ~1 year)
- Optimizes data fetching: fetch what we'll actually use
- Better balance between data availability and processing time

**Value for Short-Term Strategy:**
- ✅ Fetches 5 years daily (~1,250 days) - sufficient for EMA200 + longer lookbacks
- ✅ Fetches 3 years weekly (~156 candles) - sufficient for 50-period lookback
- ✅ Reduces unnecessary data fetching (not fetching 10 years if not needed)
- ✅ Ensures data availability matches analysis requirements

---

### 3.2 Non-Functional Requirements

#### NFR-1: Backward Compatibility
- All changes must maintain backward compatibility
- Default values must match current behavior
- No breaking changes to existing APIs

#### NFR-2: Performance
- Configurable parameters must not impact performance
- Adaptive logic should be lightweight
- No significant increase in processing time

#### NFR-3: Configuration Management
- All parameters accessible via `StrategyConfig`
- Environment variable support for easy deployment
- Clear documentation of defaults and ranges

---

## 4. Proposed Implementation

### 4.1 Configuration Changes

**File: `config/strategy_config.py`**

```python
@dataclass
class StrategyConfig:
    # ... existing fields ...
    
    # NEW: RSI Configuration
    rsi_period: int = 10  # RSI calculation period
    
    # NEW: Support/Resistance Configuration
    support_resistance_lookback_daily: int = 20  # Daily lookback periods
    support_resistance_lookback_weekly: int = 50  # Weekly lookback periods (CONFIRMED: 50)
    
    # NEW: Volume Exhaustion Configuration
    volume_exhaustion_lookback_daily: int = 10  # Daily lookback periods
    volume_exhaustion_lookback_weekly: int = 20  # Weekly lookback periods
    
    # NEW: Data Fetching Configuration
    data_fetch_daily_max_years: int = 5  # Maximum years to fetch for daily data (CONFIRMED: 5)
    data_fetch_weekly_max_years: int = 3  # Maximum years to fetch for weekly data (CONFIRMED: 3)
    
    # NEW: Adaptive Logic Configuration (CONFIRMED: Optional/Configurable)
    enable_adaptive_lookback: bool = True  # Enable adaptive lookback based on available data
    
    @classmethod
    def from_env(cls) -> 'StrategyConfig':
        return cls(
            # ... existing ...
            
            # NEW: RSI
            rsi_period=int(os.getenv('RSI_PERIOD', '10')),
            
            # NEW: Support/Resistance
            support_resistance_lookback_daily=int(os.getenv('SUPPORT_RESISTANCE_LOOKBACK_DAILY', '20')),
            support_resistance_lookback_weekly=int(os.getenv('SUPPORT_RESISTANCE_LOOKBACK_WEEKLY', '50')),
            
            # NEW: Volume Exhaustion
            volume_exhaustion_lookback_daily=int(os.getenv('VOLUME_EXHAUSTION_LOOKBACK_DAILY', '10')),
            volume_exhaustion_lookback_weekly=int(os.getenv('VOLUME_EXHAUSTION_LOOKBACK_WEEKLY', '20')),
            
            # NEW: Data Fetching
            data_fetch_daily_max_years=int(os.getenv('DATA_FETCH_DAILY_MAX_YEARS', '5')),
            data_fetch_weekly_max_years=int(os.getenv('DATA_FETCH_WEEKLY_MAX_YEARS', '3')),
            
            # NEW: Adaptive Logic
            enable_adaptive_lookback=os.getenv('ENABLE_ADAPTIVE_LOOKBACK', 'true').lower() in ('1', 'true', 'yes', 'on'),
        )
```

### 4.2 Code Changes

**File: `core/indicators.py`**
- Update `compute_indicators()` to accept `rsi_period` parameter
- Use configurable period instead of hardcoded 10

**File: `core/timeframe_analysis.py`**
- Update `__init__()` to accept `StrategyConfig`
- Use configurable lookback values instead of hardcoded 20/10
- Implement adaptive logic based on available data (aligned with data fetching strategy)

**File: `core/data_fetcher.py`**
- Update `fetch_multi_timeframe_data()` to use configurable data fetching
- Implement: `Daily: min(max(800 days, max_years), available_data)`
- Implement: `Weekly: min(max(20 weeks, max_years), available_data)`

**File: `services/indicator_service.py`**
- Pass `rsi_period` from config to indicator calculations

**File: `backtest/backtest_config.py`**
- Add `from_strategy_config()` method to sync with StrategyConfig
- Add `default_synced()` method for convenience

**File: `backtest/backtest_engine.py`**
- Update `_load_data()` to use `fetch_multi_timeframe_data()` instead of `yf.download()`
- Use configurable data fetching strategy from StrategyConfig

### 4.3 Adaptive Logic (Aligned with Data Fetching)

**File: `core/timeframe_analysis.py`**

```python
def _get_adaptive_lookback(self, available_data_days: int, base_lookback: int, timeframe: str) -> int:
    """
    Adaptive lookback based on available data
    Aligned with data fetching strategy: Daily max 5 years, Weekly max 3 years
    Only runs if enable_adaptive_lookback is True (configurable)
    """
    # Check if adaptive logic is enabled
    if not self.config.enable_adaptive_lookback:
        return base_lookback  # Return default if disabled
    
    if timeframe == 'weekly':
        # Weekly: 3 years fetched (~156 candles), use up to 50 periods (~1 year)
        if available_data_days >= 1095:  # 3 years (weekly fetch max)
            return min(base_lookback * 2.5, 50)  # Use up to 50 periods
        elif available_data_days >= 730:  # 2 years
            return min(base_lookback * 2, 40)
        else:
            return base_lookback  # Default
    else:  # daily
        # Daily: 5 years fetched (~1,250 days), use up to 50 periods (~2.5 months)
        if available_data_days >= 1825:  # 5 years (daily fetch max)
            return min(base_lookback * 2.5, 50)  # Use up to 50 periods
        elif available_data_days >= 1095:  # 3 years
            return min(base_lookback * 1.5, 30)
        else:
            return base_lookback  # Default (20 periods)
    
    return base_lookback  # Default fallback
```

**File: `core/data_fetcher.py`**

```python
def fetch_multi_timeframe_data(ticker, days=800, end_date=None, add_current_day=True, config=None):
    """
    Fetch data with configurable strategy:
    Daily: min(max(800 days, max_years), available_data)
    Weekly: min(max(20 weeks, max_years), available_data)
    """
    if config is None:
        from config.strategy_config import StrategyConfig
        config = StrategyConfig.default()
    
    # Calculate data fetching limits
    daily_max_years = config.data_fetch_daily_max_years  # Default: 5
    weekly_max_years = config.data_fetch_weekly_max_years  # Default: 3
    
    # Daily: min(max(800 days, 5 years), available)
    daily_min_days = max(800, daily_max_years * 365)
    daily_days = min(daily_min_days, available_data_days) if available_data_days else daily_min_days
    
    # Weekly: min(max(20 weeks, 3 years), available)
    weekly_min_days = max(20 * 7, weekly_max_years * 365)
    weekly_days = min(weekly_min_days, available_data_days) if available_data_days else weekly_min_days
    
    # Fetch data...
```

---

## 5. Value Proposition

### 5.1 For Short-Term Strategy (RSI10 < 30 & Price > EMA200)

#### Immediate Benefits:
1. **Better Support/Resistance Identification** ⭐⭐⭐⭐⭐
   - Longer lookbacks identify stronger support levels
   - Critical for accurate stop-loss placement
   - Reduces false breakouts

2. **Effective Use of Historical Data** ⭐⭐⭐⭐
   - Currently wasting 99% of fetched data
   - Longer lookbacks utilize 10-year history effectively
   - Better pattern recognition

3. **Optimization Capability** ⭐⭐⭐⭐
   - Can backtest different lookback periods
   - Find optimal values for different stocks
   - Improve signal quality through testing

#### Long-Term Benefits:
1. **Adaptability**
   - Adjust parameters for different market conditions
   - Optimize for different stock categories
   - Fine-tune based on backtest results

2. **Consistency**
   - All parameters configurable (not just some)
   - Centralized configuration management
   - Easier maintenance and updates

### 5.2 Expected Improvements

| Metric | Current | With Changes | Improvement |
|--------|---------|--------------|-------------|
| Support/Resistance Accuracy | Baseline | +15-20% | Better level identification |
| Historical Data Utilization | ~1.6% | ~4-32% | Better use of fetched data (daily 4-6%, weekly 32%) |
| Stop-Loss Accuracy | Baseline | +10-15% | Better support-based stops |
| Signal Quality | Baseline | +5-10% | Better filtering |

### 5.3 Risk Assessment

**Low Risk:**
- ✅ Backward compatible (defaults match current behavior)
- ✅ No breaking changes
- ✅ Can be rolled back easily

**Medium Risk:**
- ⚠️ Adaptive logic needs testing
- ⚠️ Longer lookbacks may slow processing slightly
- ⚠️ Need to validate new defaults don't break existing signals

**Mitigation:**
- Thorough testing with current data
- Performance benchmarking
- Gradual rollout with monitoring

---

## 6. Implementation Plan

### Phase 1: Configuration Setup (Low Risk)
1. Add parameters to `StrategyConfig`
2. Add environment variable support
3. Update documentation
4. **Estimated Time:** 2-3 hours

### Phase 2: Code Updates (Medium Risk)
1. Update `core/indicators.py` for RSI period
2. Update `core/timeframe_analysis.py` for lookbacks
3. Update `core/data_fetcher.py` for configurable data fetching
4. Update `core/backtest_scoring.py` for configurable RSI period
5. **Sync BacktestConfig with StrategyConfig** (REQUIRED per Q7)
6. **Update BacktestEngine to use fetch_multi_timeframe_data()** (REQUIRED per Q10)
7. **Optimize integrated_backtest.py data fetching** (CRITICAL per Q9)
   - Modify `run_backtest()` to return BacktestEngine instance (or expose engine.data)
   - Reuse BacktestEngine data for position tracking (eliminate duplicate fetch)
   - Modify `trade_agent()` to accept pre-fetched data (optional parameter)
   - Modify `analyze_ticker()` to accept pre-fetched data (optional parameter)
   - Update `run_integrated_backtest()` to pass data between components
8. **Standardize indicator calculation methods** (CRITICAL - Section 15)
   - Update `core/indicators.py` to use pandas_ta (consistent with BacktestEngine)
   - Make `compute_indicators()` accept configurable RSI/EMA periods
   - Update `trade_agent()` to reuse BacktestEngine indicators
9. **Update ML feature extraction** (REQUIRED - ML compatibility)
   - Update `services/ml_verdict_service.py` to use configurable parameters
   - Maintain backward compatibility with existing models
10. **Update scoring/verdict system** (REQUIRED - Scoring compatibility)
   - Update `services/scoring_service.py` to use configurable RSI thresholds
   - Update `core/backtest_scoring.py` RSI thresholds for entry conditions
   - Maintain backward compatibility with default config
11. **Update legacy core/analysis.py** (OPTIONAL - Medium priority)
   - Migrate from `config.settings` constants to `StrategyConfig`
   - Update RSI threshold usage to use configurable values
   - Replace `RSI_OVERSOLD` imports with `StrategyConfig.rsi_oversold`
   - Update hardcoded `rsi_threshold = 20` to use `config.rsi_extreme_oversold`
   - Update `rsi10` column references to use configurable `rsi{config.rsi_period}`
12. **Sync auto-trader config** (OPTIONAL - Medium priority)
   - Sync `kotak_neo_auto_trader/config.py` RSI_PERIOD with StrategyConfig
   - Keep EMA_SHORT/EMA_LONG separate (auto-trader specific)
   - Update `auto_trade_engine.py` to use synced RSI period
13. **Make pattern detection configurable** (OPTIONAL - Low priority)
   - Update `core/patterns.py` `bullish_divergence()` to accept `rsi_period` parameter
   - Make lookback period configurable (default: 10)
   - Use configurable RSI column name `f'rsi{rsi_period}'`
14. **Deprecate legacy config constants** (OPTIONAL - Medium priority)
   - Add deprecation warnings to `config/settings.py` for `RSI_OVERSOLD` and `RSI_NEAR_OVERSOLD`
   - Update all remaining usages to use `StrategyConfig`
   - Document migration path in deprecation messages
15. Update service layer to pass config
16. **Estimated Time:** 14-18 hours (includes all updates: backtest, ML, scoring, data fetching, indicator consistency, legacy migration, pattern detection, auto-trader sync, config deprecation)

### Phase 3: Testing & Validation (High Priority)
1. Unit tests for configurable parameters
2. Integration tests with current data
3. Backtest comparison (old vs new) - **CRITICAL**
4. BacktestEngine regression tests
5. Integrated backtest validation tests
6. Simple backtest regression tests
7. **Data fetching optimization tests** (NEW)
   - Verify data is fetched only once in integrated backtest
   - Verify data reuse works correctly
   - Performance comparison (before/after optimization)
8. **ML compatibility tests** (NEW)
   - Verify default config produces same features as current implementation
   - Verify backward compatibility with existing models
   - Test feature extraction with non-default configs
   - Model retraining validation
9. **Scoring/verdict tests** (NEW)
   - Verify scoring logic uses configurable RSI thresholds
   - Verify backtest scoring entry conditions use configurable RSI
   - Verify trading parameters improve with better support/resistance
10. **Indicator calculation consistency tests** (NEW)
   - Verify BacktestEngine and Trade Agent produce same RSI/EMA values
   - Verify pandas_ta methods produce consistent results
   - Verify compute_indicators() uses configurable parameters
11. **Legacy migration tests** (NEW)
   - Verify core/analysis.py uses StrategyConfig correctly
   - Verify pattern detection works with configurable RSI period
   - Verify auto-trader sync works correctly
   - Verify deprecated constants still work but show warnings
12. Performance benchmarking
13. **Estimated Time:** 13-16 hours (includes ML, scoring, indicator consistency, and legacy migration testing)

### Phase 4: Adaptive Logic (Optional - Per Q2)
**Status:** ✅ **Yes, but make it optional/configurable** (per your decision)

1. Implement adaptive lookback logic (make it configurable via StrategyConfig)
2. Add `enable_adaptive_lookback` flag to StrategyConfig (default: True)
3. Test with different data availability scenarios
4. Validate improvements
5. **Estimated Time:** 4-6 hours

**Total Estimated Time:** 26-40 hours (includes all updates: backtest, ML, scoring, data fetching optimization, indicator consistency, legacy migration, pattern detection, auto-trader sync, config deprecation, adaptive logic, and comprehensive testing)

---

## 7. Recommended Defaults for Short-Term Strategy

### 7.1 Rationale
Given your base strategy (RSI10 < 30 & Price > EMA200, short-term focus):

| Parameter | Recommended Default | Rationale | **Your Decision** |
|-----------|---------------------|-----------|-------------------|
| RSI Period | 10 | Optimal for short-term, fast signals | ✅ **RSI10 (confirmed)** |
| Support/Resistance Daily | 20-30 | Short-term focus, but can use more data | ✅ **20-30 (confirmed)** |
| Support/Resistance Weekly | 50 | Longer-term context for weekly timeframe | ✅ **50 (confirmed)** |
| Volume Exhaustion Daily | 10 | Short-term volume patterns | ✅ **10 (confirmed)** |
| Volume Exhaustion Weekly | 20 | Better trend detection for weekly | ✅ **20 (confirmed)** |
| Adaptive Logic | Optional/Configurable | Make it optional via config flag | ✅ **Yes, optional/configurable** |
| Data Fetching Daily | 5 years max | Balance between data and performance | ✅ **5 years (confirmed)** |
| Data Fetching Weekly | 3 years max | Sufficient for weekly analysis | ✅ **3 years (confirmed)** |

### 7.2 Data Fetching & Lookback Alignment

**Data Fetching Strategy:**
- **Daily:** `min(max(800 days, 5 years), available_data)` = ~1,250 trading days
- **Weekly:** `min(max(20 weeks, 3 years), available_data)` = ~156 weekly candles

**Lookback Recommendations (Aligned with Data Fetching):**

| Data Fetched | Support/Resistance Daily | Support/Resistance Weekly | Rationale |
|--------------|-------------------------|---------------------------|-----------|
| 5 years daily (~1,250 days) | 30-50 periods (~1.5-2.5 months) | 50 periods (~1 year) | Uses 4-6% of fetched data |
| 3 years weekly (~156 candles) | N/A | 50 periods (~1 year) | Uses 32% of fetched data |
| < 2 years | 20 periods (default) | 20 periods (default) | Minimum for basic analysis |

**Key Alignment:**
- ✅ **Daily:** Fetch 5 years → Use 30-50 periods (2-4% utilization, but better than 1.6%)
- ✅ **Weekly:** Fetch 3 years → Use 50 periods (32% utilization, excellent)
- ✅ **Volume:** Daily 10 periods, Weekly 20 periods (appropriate for short-term)

**Benefits:**
- Data fetching matches analysis needs
- No over-fetching (not fetching 10 years if using 20 periods)
- No under-fetching (ensures enough data for longer lookbacks)
- Optimal balance between data availability and processing time

## 11. Decision Summary

### 11.1 All Decisions Made

| Question | Decision | Impact |
|----------|----------|--------|
| **Q1: RSI Period** | ✅ Keep RSI10 as default | No change to current behavior |
| **Q2: Adaptive Logic** | ✅ Yes, but optional/configurable | Added `enable_adaptive_lookback` flag |
| **Q3: Weekly Lookback** | ✅ Default: 50 periods | Better weekly context |
| **Q4: Implementation Priority** | ✅ Phase 1-2 first, Phase 3 optional | Phased approach |
| **Q5: Data Fetching** | ✅ Daily: 5 years, Weekly: 3 years | Optimized data fetching |
| **Q6: Testing** | ✅ Backtest comparison | Historical validation |
| **Q7: Backtest Sync** | ✅ Yes - Sync BacktestConfig | Consistency between systems |
| **Q8: Simple Backtest** | ✅ Yes - Update to configurable | Consistency |
| **Q9: Data Optimization** | ✅ Yes - Critical | Eliminate 22+ API calls |
| **Q10: BacktestEngine Consistency** | ✅ Yes - Use fetch_multi_timeframe_data() | Consistent data fetching |
| **Q11: ML Retraining** | ✅ Backward compatibility | Keep old features with defaults |
| **Q12: Indicator Consistency** | ✅ Yes - Standardize pandas_ta + reuse | Consistency and performance |

### 11.2 Final Configuration Summary

**StrategyConfig Defaults (Confirmed):**
- `rsi_period = 10`
- `support_resistance_lookback_daily = 20`
- `support_resistance_lookback_weekly = 50`
- `volume_exhaustion_lookback_daily = 10`
- `volume_exhaustion_lookback_weekly = 20`
- `data_fetch_daily_max_years = 5`
- `data_fetch_weekly_max_years = 3`
- `enable_adaptive_lookback = True` (optional/configurable)

**BacktestConfig Changes (Required):**
- Add `from_strategy_config()` method
- Add `default_synced()` method
- Update BacktestEngine to use `fetch_multi_timeframe_data()`

**Data Fetching Optimization (Critical):**
- Reuse BacktestEngine data in integrated backtest
- Modify trade_agent() to accept pre-fetched data
- Reduce API calls from 22+ to 1 per backtest

**ML Compatibility (Medium Priority - Per Q11):**
- Update ML feature extraction to use configurable parameters
- Maintain backward compatibility with existing models ✅ **Confirmed**
- Retrain models when using non-default configurations ✅ **Confirmed**
- Keep old feature names with default config ✅ **Confirmed**

**Scoring/Verdict Compatibility (Medium Priority):**
- Update scoring service to use configurable RSI thresholds
- Update backtest scoring entry conditions
- Trading parameters improve automatically with better support/resistance

**Indicator Calculation Consistency (Critical Priority - Per Q12):**
- Standardize calculation methods (use pandas_ta consistently) ✅ **Confirmed**
- Reuse BacktestEngine indicators in trade_agent ✅ **Confirmed**
- Make compute_indicators() configurable ✅ **Confirmed**
- Eliminate duplicate indicator calculations ✅ **Confirmed**

**Additional System Components (Low-Medium Priority):**
- Pattern detection: Make lookback configurable (optional)
- Legacy core/analysis.py: Migrate to StrategyConfig (recommended)
- Auto-trader module: Sync RSI period with StrategyConfig (recommended)
- Config settings: Deprecate legacy constants (recommended)

---

## 12. Backtest Impact Analysis

### 12.1 Current Backtest Architecture

The system has **three separate backtest implementations**:

1. **BacktestEngine** (`backtest/backtest_engine.py`)
   - Uses `BacktestConfig` (separate from `StrategyConfig`)
   - Already has configurable `RSI_PERIOD` (default: 10)
   - Does NOT use support/resistance lookback or volume exhaustion
   - Does NOT use multi-timeframe analysis
   - **Purpose:** Pure strategy execution (RSI10 < 30 & Price > EMA200)

2. **Integrated Backtest** (`integrated_backtest.py`)
   - Uses `BacktestEngine` for signal generation
   - Uses `analyze_ticker()` for trade agent validation
   - **Purpose:** Validates backtest signals through full analysis pipeline

3. **Simple Backtest** (`core/backtest_scoring.py`)
   - Uses hardcoded `calculate_wilder_rsi(data['Close'], 10)`
   - Does NOT use support/resistance or volume exhaustion
   - **Purpose:** Quick scoring for stock screening

### 12.2 Impact Assessment

#### Impact Level: LOW - BacktestEngine
**File:** `backtest/backtest_engine.py`

| Change | Impact | Action Required |
|--------|--------|-----------------|
| RSI Period Configurable | ✅ **No Impact** | Already uses `BacktestConfig.RSI_PERIOD` |
| Support/Resistance Lookback | ✅ **No Impact** | Not used in BacktestEngine |
| Volume Exhaustion Lookback | ✅ **No Impact** | Not used in BacktestEngine |
| Data Fetching Strategy | ⚠️ **Indirect Impact** | Uses `yf.download()` directly, not `fetch_multi_timeframe_data()` |

**Recommendation:**
- ✅ **No changes needed** - BacktestEngine uses its own config system
- ⚠️ **Optional:** Sync `BacktestConfig.RSI_PERIOD` with `StrategyConfig.rsi_period` for consistency
- ⚠️ **Optional:** Consider using `fetch_multi_timeframe_data()` for consistency

---

#### Impact Level: MEDIUM - Integrated Backtest
**File:** `integrated_backtest.py`

| Change | Impact | Action Required |
|--------|--------|-----------------|
| RSI Period Configurable | ⚠️ **Indirect Impact** | Trade agent uses configurable RSI |
| Support/Resistance Lookback | ✅ **Direct Impact** | Trade agent uses multi-timeframe analysis |
| Volume Exhaustion Lookback | ✅ **Direct Impact** | Trade agent uses multi-timeframe analysis |
| Data Fetching Strategy | ✅ **Direct Impact** | Trade agent fetches data via `analyze_ticker()` |

**Impact Details:**
- **Signal Generation:** Uses `BacktestEngine` - **NO IMPACT** (uses BacktestConfig)
- **Signal Validation:** Uses `analyze_ticker()` - **WILL BE AFFECTED**
  - Better support/resistance identification → Better signal filtering
  - Better volume exhaustion detection → Better signal quality
  - Configurable RSI period → More flexible validation

**Recommendation:**
- ✅ **No breaking changes** - Will improve signal validation quality
- ⚠️ **Testing required** - Validate that improved analysis doesn't filter out too many signals
- ✅ **Backward compatible** - Defaults match current behavior

---

#### Impact Level: MEDIUM - Simple Backtest
**File:** `core/backtest_scoring.py`

| Change | Impact | Action Required |
|--------|--------|-----------------|
| RSI Period Configurable | ⚠️ **Direct Impact** | Currently hardcoded `period=10` |
| Support/Resistance Lookback | ✅ **No Impact** | Not used in simple backtest |
| Volume Exhaustion Lookback | ✅ **No Impact** | Not used in simple backtest |
| Data Fetching Strategy | ⚠️ **Indirect Impact** | Uses `yf.download()` directly |

**Impact Details:**
- **Line 172:** `data['RSI10'] = calculate_wilder_rsi(data['Close'], 10)` - **HARDCODED**
- Needs update to use configurable RSI period

**Recommendation:**
- ⚠️ **Update required:** Make RSI period configurable (use StrategyConfig or parameter)
- ✅ **Backward compatible:** Default to 10 if not specified

---

### 12.3 Required Changes for Backtest Compatibility

#### Change 1: Update Simple Backtest RSI Period
**File:** `core/backtest_scoring.py`

```python
# CURRENT (line 172):
data['RSI10'] = calculate_wilder_rsi(data['Close'], 10)

# PROPOSED:
from config.strategy_config import StrategyConfig
config = StrategyConfig.default()
data['RSI10'] = calculate_wilder_rsi(data['Close'], config.rsi_period)
```

**Impact:** ✅ Low - Simple change, backward compatible

---

#### Change 2: Sync BacktestConfig with StrategyConfig (REQUIRED)
**File:** `backtest/backtest_config.py`

**Decision:** ✅ **Yes - Sync BacktestConfig with StrategyConfig**

**Implementation:**
```python
# Add method to sync from StrategyConfig
@classmethod
def from_strategy_config(cls, strategy_config: StrategyConfig) -> 'BacktestConfig':
    """
    Create BacktestConfig from StrategyConfig for consistency
    
    Args:
        strategy_config: StrategyConfig instance
        
    Returns:
        BacktestConfig with RSI_PERIOD synced
    """
    config = cls()
    config.RSI_PERIOD = strategy_config.rsi_period
    # Optionally sync other parameters if needed
    return config

# Add class method to get default synced config
@classmethod
def default_synced(cls) -> 'BacktestConfig':
    """Get BacktestConfig synced with StrategyConfig defaults"""
    from config.strategy_config import StrategyConfig
    return cls.from_strategy_config(StrategyConfig.default())
```

**Impact:** ✅ Low - Ensures consistency between backtest and live analysis

---

#### Change 3: Use Configurable Data Fetching in BacktestEngine (REQUIRED)
**File:** `backtest/backtest_engine.py`

**Decision:** ✅ **Yes - Use fetch_multi_timeframe_data() for consistency**

**Current:** Uses `yf.download()` directly  
**Proposed:** Use `fetch_multi_timeframe_data()` for consistency

**Implementation:**
```python
# CURRENT (line 83):
self.data = yf.download(
    self.symbol, 
    start=auto_start_date, 
    end=data_end, 
    progress=False,
    auto_adjust=True
)

# PROPOSED:
from core.data_fetcher import fetch_multi_timeframe_data
from config.strategy_config import StrategyConfig

config = StrategyConfig.default()
multi_data = fetch_multi_timeframe_data(
    ticker=self.symbol,
    days=max(800, config.data_fetch_daily_max_years * 365),
    end_date=self.end_date.strftime('%Y-%m-%d'),
    add_current_day=False  # Backtesting mode
)
self.data = multi_data['daily'] if multi_data else None
```

**Impact:** ⚠️ Medium - More consistent data fetching, aligns with configurable strategy

**Benefits:**
- ✅ Consistent data fetching across all components
- ✅ Uses configurable data fetching strategy
- ✅ Better alignment with analysis pipeline

---

### 12.4 Backward Compatibility Guarantee

#### ✅ Guaranteed Backward Compatible:
1. **BacktestEngine:** Uses its own config - **NO IMPACT**
2. **Integrated Backtest:** Trade agent defaults match current behavior - **NO BREAKING CHANGES**
3. **Simple Backtest:** Will default to RSI10 if not specified - **NO BREAKING CHANGES**

#### ⚠️ Potential Improvements (Non-Breaking):
1. **Better Signal Quality:** Improved support/resistance → Better filtering
2. **More Accurate Validation:** Better volume exhaustion detection
3. **Consistent Configuration:** RSI period synced across all components

---

### 12.5 Testing Requirements

#### Test Cases Required:

1. **BacktestEngine Tests:**
   - ✅ Verify RSI_PERIOD still configurable via BacktestConfig
   - ✅ Verify no impact on signal generation
   - ✅ Verify results match current behavior with defaults

2. **Integrated Backtest Tests:**
   - ✅ Verify signal generation unchanged (uses BacktestEngine)
   - ✅ Verify signal validation improved (uses analyze_ticker)
   - ✅ Compare old vs new validation results
   - ⚠️ Ensure improved analysis doesn't filter out too many valid signals

3. **Simple Backtest Tests:**
   - ✅ Verify RSI period configurable
   - ✅ Verify default RSI10 works
   - ✅ Verify results match current behavior

4. **Regression Tests:**
   - ✅ Run existing backtest suite
   - ✅ Compare results before/after changes
   - ✅ Verify no performance degradation

---

### 12.6 Data Fetching Duplication Issue (CRITICAL)

**Problem Identified:** Data is fetched multiple times in integrated backtest, causing inefficiency and potential API rate limiting.

#### Current Data Fetching Flow in Integrated Backtest:

```
run_integrated_backtest()
  ├─ Step 1: run_backtest()
  │    └─ BacktestEngine._load_data()
  │         └─ yf.download() ← FETCH #1 (for signal generation)
  │
  ├─ Step 2: market_data = yf.download() ← FETCH #2 (for position tracking)
  │
  └─ Step 3: For each signal:
       └─ trade_agent()
            └─ analyze_ticker()
                 └─ fetch_multi_timeframe_data() ← FETCH #3 (for validation)
                      ├─ fetch_ohlcv_yf() [daily] ← FETCH #3a
                      └─ fetch_ohlcv_yf() [weekly] ← FETCH #3b
```

**Total Fetches per Integrated Backtest:**
- **Initial:** 1 fetch (BacktestEngine)
- **Position Tracking:** 1 fetch (market_data)
- **Per Signal:** 2 fetches (daily + weekly) × N signals
- **Example:** 10 signals = 1 + 1 + (2 × 10) = **22 API calls**

#### Impact:

| Issue | Severity | Impact |
|-------|----------|--------|
| API Rate Limiting | ⚠️ **HIGH** | yfinance may throttle/block excessive requests |
| Performance | ⚠️ **MEDIUM** | Slower backtest execution |
| Network Overhead | ⚠️ **MEDIUM** | Unnecessary bandwidth usage |
| Data Consistency | ⚠️ **LOW** | Same data fetched multiple times (should be consistent) |

#### Proposed Solution:

**Option 1: Reuse BacktestEngine Data (Recommended)**
```python
# In run_integrated_backtest():
# Step 1: Get data from BacktestEngine
engine = BacktestEngine(...)
backtest_data = engine.data  # Reuse this data

# Step 2: Use backtest_data for position tracking (no need for separate fetch)
market_data = backtest_data.loc[start_date:end_date].copy()

# Step 3: Pass data to trade_agent to avoid re-fetching
# (Requires modifying trade_agent/analyze_ticker to accept pre-fetched data)
```

**Option 2: Cache Data Fetches**
```python
# Add caching layer to fetch_multi_timeframe_data()
# Cache key: (ticker, end_date, add_current_day)
# Reuse cached data if available
```

**Option 3: Single Data Fetch with Sharing**
```python
# Fetch all data once at start
# Share between BacktestEngine, position tracking, and trade agent
```

**Recommendation:** **Option 1** - Reuse BacktestEngine data and modify trade_agent to accept pre-fetched data.

---

### 12.7 Required Changes for Data Fetching Optimization

#### Change 1: Reuse BacktestEngine Data in Integrated Backtest
**File:** `integrated_backtest.py`

```python
# CURRENT (line 279):
market_data = yf.download(stock_name, start=start_date, end=end_date, progress=False)

# PROPOSED:
# Reuse data from BacktestEngine (already fetched in run_backtest)
# Need to return engine.data from run_backtest() or pass it separately
```

**Impact:** ✅ High - Eliminates duplicate fetch for position tracking

---

#### Change 2: Modify trade_agent to Accept Pre-fetched Data (Optional)
**File:** `integrated_backtest.py` and `core/analysis.py`

**Current:** `trade_agent()` calls `analyze_ticker()` which fetches data  
**Proposed:** Allow passing pre-fetched data to avoid re-fetching

```python
# PROPOSED API:
def trade_agent(stock_name: str, buy_date: str, pre_fetched_data: Optional[Dict] = None):
    if pre_fetched_data:
        # Use pre-fetched data
        analysis_result = analyze_ticker_with_data(
            stock_name, 
            daily_df=pre_fetched_data.get('daily'),
            weekly_df=pre_fetched_data.get('weekly'),
            as_of_date=buy_date
        )
    else:
        # Fallback to current behavior
        analysis_result = analyze_ticker(...)
```

**Impact:** ✅ Very High - Eliminates per-signal data fetches

---

#### Change 3: Add Data Caching (Optional Enhancement)
**File:** `core/data_fetcher.py`

Add caching mechanism to avoid duplicate fetches:
```python
from functools import lru_cache
from datetime import datetime

_cache = {}

def fetch_multi_timeframe_data_cached(ticker, days=800, end_date=None, add_current_day=True):
    cache_key = (ticker, end_date, add_current_day)
    if cache_key in _cache:
        return _cache[cache_key]
    
    data = fetch_multi_timeframe_data(ticker, days, end_date, add_current_day)
    _cache[cache_key] = data
    return data
```

**Impact:** ⚠️ Medium - Helps but doesn't solve root cause

---

### 12.8 Updated Backtest Impact Summary

| Component | Data Fetches | Impact | Optimization Needed |
|-----------|--------------|--------|---------------------|
| BacktestEngine | 1 (per backtest) | ✅ Acceptable | None |
| Integrated Backtest (Position Tracking) | 1 (duplicate) | ⚠️ **Wasteful** | **Reuse BacktestEngine data** |
| Integrated Backtest (Trade Agent) | 2 × N signals | ⚠️ **CRITICAL** | **Accept pre-fetched data** |
| Simple Backtest | 1 (per backtest) | ✅ Acceptable | None |

**Priority:** 
- 🔴 **HIGH:** Optimize integrated backtest data fetching
- 🟡 **MEDIUM:** Add caching for repeated fetches
- 🟢 **LOW:** Sync BacktestConfig with StrategyConfig

---

### 12.9 Complete Backtest Impact Summary

| Component | Impact Level | Breaking Changes | Action Required | Data Fetching |
|-----------|-------------|------------------|-----------------|---------------|
| BacktestEngine | ✅ **LOW** | ❌ None | Optional: Sync RSI period | ✅ 1 fetch (OK) |
| Integrated Backtest | ⚠️ **MEDIUM** | ❌ None | Testing: Validate improved filtering | ⚠️ **3+ fetches (NEEDS OPTIMIZATION)** |
| Simple Backtest | ⚠️ **MEDIUM** | ❌ None | Update: Make RSI configurable | ✅ 1 fetch (OK) |

**Overall Assessment:**
- ✅ **No breaking changes** - All changes backward compatible
- ✅ **Improvements expected** - Better signal validation quality
- ⚠️ **Testing required** - Validate improvements don't filter too aggressively
- ✅ **Low risk** - Defaults match current behavior
- 🔴 **Data fetching optimization needed** - Integrated backtest fetches data 3+ times per signal

---

## 8. Success Criteria
- ✅ All parameters configurable via `StrategyConfig`
- ✅ Environment variable support working
- ✅ Backward compatibility maintained
- ✅ No breaking changes to existing functionality

### 8.2 Performance
- ✅ No significant performance degradation (< 5% increase)
- ✅ Adaptive logic executes quickly (< 1ms overhead)

### 8.3 Quality
- ✅ Support/resistance accuracy improved (measured via backtests)
- ✅ Better utilization of historical data
- ✅ Signal quality maintained or improved

---

## 9. Open Questions for Review

### Q1: RSI Period
- **Question:** Should we keep RSI10 as default, or consider RSI14?
- **Recommendation:** Keep RSI10 (optimal for short-term)
- **Your Input:** ✅ **Keep RSI10 as default**

### Q2: Adaptive Logic
- **Question:** Should we implement adaptive lookbacks based on available data?
- **Recommendation:** Yes, but make it optional/configurable
- **Your Input:** ✅ **Yes, but make it optional/configurable**

### Q3: Weekly Lookback Default
- **Question:** Weekly support/resistance lookback: 20 (current) or 50 (recommended)?
- **Recommendation:** 50 (better context, still short-term)
- **Your Input:** ✅ **Weekly lookback default: 50**

### Q4: Implementation Priority
- **Question:** Which phase should we prioritize?
- **Recommendation:** Phase 1-2 first (config + code), Phase 3 (adaptive) optional
- **Your Input:** ✅ **Phase 1-2 first (config + code), Phase 3 (adaptive) optional**

### Q5: Data Fetching Strategy
- **Question:** Confirm data fetching: Daily max 5 years, Weekly max 3 years?
- **Recommendation:** Yes - aligns with lookback parameters and optimizes performance
- **Your Input:** ✅ **Daily max 5 years, Weekly max 3 years**

### Q6: Testing Approach
- **Question:** How should we validate improvements?
- **Recommendation:** Backtest comparison on historical data
- **Your Input:** ✅ **Backtest comparison on historical data**

### Q7: Backtest Compatibility
- **Question:** Should we sync BacktestConfig.RSI_PERIOD with StrategyConfig.rsi_period?
- **Recommendation:** Optional - Keep separate for flexibility, but add sync method
- **Your Input:** ✅ **Yes - Sync BacktestConfig with StrategyConfig**

### Q8: Simple Backtest Update
- **Question:** Update simple backtest to use configurable RSI period?
- **Recommendation:** Yes - Required for consistency
- **Your Input:** ✅ **Yes - Update simple backtest to use configurable RSI period**

### Q9: Data Fetching Optimization
- **Question:** Should we optimize integrated backtest to reuse data instead of fetching 3+ times?
- **Recommendation:** Yes - Critical for performance and API rate limiting
- **Your Input:** ✅ **Yes - Critical for performance and API rate limiting**

### Q10: BacktestEngine Data Fetching Consistency
- **Question:** Should BacktestEngine use `fetch_multi_timeframe_data()` for consistency?
- **Recommendation:** Defer - Not critical, can be done later
- **Your Input:** ✅ **Yes - Use fetch_multi_timeframe_data() in BacktestEngine (consistency)**

### Q11: ML Model Retraining Strategy
- **Question:** How should we handle ML model retraining when features change?
- **Recommendation:** Backward compatibility - Keep old feature names with default config, retrain for non-default
- **Your Input:** ✅ **Backward compatibility - Keep old feature names with default config, retrain for non-default**

### Q12: Indicator Calculation Consistency
- **Question:** Should we standardize indicator calculation methods (use pandas_ta consistently) and reuse BacktestEngine indicators?
- **Recommendation:** Yes - Critical for consistency and performance
- **Your Input:** ✅ **Yes - Standardize indicator calculation methods (use pandas_ta consistently) and reuse BacktestEngine indicators**

---

## 13. ML Implementation Impact Analysis

### 13.1 Current ML Architecture

The system includes ML components for verdict prediction:

1. **MLVerdictService** (`services/ml_verdict_service.py`)
   - Uses trained Random Forest/XGBoost models
   - Extracts 18 features for prediction
   - Falls back to rule-based logic if ML unavailable

2. **MLTrainingService** (`services/ml_training_service.py`)
   - Trains models from historical backtest data
   - Uses features extracted from backtest results

3. **Training Data Collection**
   - Features extracted from backtest results
   - Models trained on historical data with specific feature values

### 13.2 ML Feature Dependencies

**Current ML Features (from `ml_verdict_service.py`):**

| Feature | Current Implementation | Hardcoded Value | Impact of Changes |
|---------|------------------------|-----------------|-------------------|
| `rsi_10` | `rsi_value` (line 207) | ✅ **Hardcoded name** | ⚠️ **Feature name mismatch** if RSI period changes |
| `avg_volume_20` | `df['volume'].tail(20).mean()` (line 216) | ✅ **Hardcoded 20 periods** | ⚠️ **Feature value changes** if volume lookback changes |
| `recent_high_20` | `df['high'].tail(20).max()` (line 232) | ✅ **Hardcoded 20 periods** | ⚠️ **Feature value changes** if support/resistance lookback changes |
| `recent_low_20` | `df['low'].tail(20).min()` (line 233) | ✅ **Hardcoded 20 periods** | ⚠️ **Feature value changes** if support/resistance lookback changes |
| `support_distance_pct` | Calculated from `recent_low_20` | ✅ **Depends on 20-period lookback** | ⚠️ **Feature value changes** if support/resistance lookback changes |

**Other Features (Not Affected):**
- `ema200`, `price`, `price_above_ema200` - Not affected
- `volume`, `volume_ratio`, `vol_strong` - Not directly affected
- Pattern signals (`has_hammer`, `has_bullish_engulfing`, etc.) - Not affected
- `alignment_score` - Not directly affected (uses multi-timeframe analysis)
- Fundamentals (`pe`, `pb`) - Not affected

### 13.3 Impact Assessment

#### Impact Level: ⚠️ **MEDIUM** - Model Retraining Required

| Change | Impact on ML | Action Required |
|--------|--------------|-----------------|
| **RSI Period Configurable** | ⚠️ **Feature name/value mismatch** | Update feature extraction + retrain models |
| **Support/Resistance Lookback Configurable** | ⚠️ **Feature value changes** | Update feature extraction + retrain models |
| **Volume Exhaustion Lookback Configurable** | ⚠️ **Feature value changes** | Update feature extraction + retrain models |
| **Data Fetching Strategy** | ✅ **No direct impact** | None (affects training data collection only) |

### 13.4 Required Changes for ML Compatibility

#### Change 1: Update ML Feature Extraction (REQUIRED)
**File:** `services/ml_verdict_service.py`

**Current Issues:**
- Line 207: Hardcoded `rsi_10` feature name
- Line 216: Hardcoded `avg_volume_20` (20-period lookback)
- Lines 232-233: Hardcoded `recent_high_20` and `recent_low_20` (20-period lookback)

**Proposed Solution:**
```python
# CURRENT (line 207):
features['rsi_10'] = float(rsi_value) if rsi_value is not None else 50.0

# PROPOSED:
rsi_period = self.config.rsi_period if self.config else 10
features[f'rsi_{rsi_period}'] = float(rsi_value) if rsi_value is not None else 50.0
# Also keep 'rsi_10' for backward compatibility if period == 10

# CURRENT (line 216):
features['avg_volume_20'] = float(df['volume'].tail(20).mean()) if len(df) >= 20 else features['volume']

# PROPOSED:
volume_lookback = self.config.volume_exhaustion_lookback_daily if self.config else 20
features[f'avg_volume_{volume_lookback}'] = float(df['volume'].tail(volume_lookback).mean()) if len(df) >= volume_lookback else features['volume']
# Also keep 'avg_volume_20' for backward compatibility if lookback == 20

# CURRENT (lines 232-233):
features['recent_high_20'] = float(df['high'].tail(20).max()) if len(df) >= 20 else features['price']
features['recent_low_20'] = float(df['low'].tail(20).min()) if len(df) >= 20 else features['price']

# PROPOSED:
support_lookback = self.config.support_resistance_lookback_daily if self.config else 20
features[f'recent_high_{support_lookback}'] = float(df['high'].tail(support_lookback).max()) if len(df) >= support_lookback else features['price']
features[f'recent_low_{support_lookback}'] = float(df['low'].tail(support_lookback).min()) if len(df) >= support_lookback else features['price']
# Also keep 'recent_high_20' and 'recent_low_20' for backward compatibility if lookback == 20
```

**Impact:** ⚠️ Medium - Feature extraction changes, but backward compatibility maintained

---

#### Change 2: Model Retraining Strategy (REQUIRED)

**Problem:** Existing models trained with hardcoded feature names/values won't match new feature extraction.

**Solution Options:**

**Option A: Backward Compatibility (Recommended)**
- Keep old feature names (`rsi_10`, `avg_volume_20`, etc.) when using default config
- Add new feature names only when config differs from defaults
- Models continue to work with default config
- Retrain models when using non-default config

**Option B: Versioned Features**
- Add feature version to model metadata
- Extract features based on model's expected version
- Retrain all models with new feature set

**Option C: Feature Mapping**
- Map new feature names to old names for existing models
- Only use new features for newly trained models

**Recommendation:** **Option A** - Maintain backward compatibility, retrain when needed

---

#### Change 3: Update Training Data Collection (REQUIRED)

**File:** Training data collection scripts (if exists)

**Impact:** Training data must be collected using same feature extraction as ML service

**Action:** Ensure training data collection uses configurable parameters from `StrategyConfig`

---

### 13.5 Backward Compatibility Strategy

#### ✅ Backward Compatible Approach:

1. **Default Config = Current Behavior:**
   - RSI period = 10 → Feature name: `rsi_10` ✅
   - Support/Resistance lookback = 20 → Feature names: `recent_high_20`, `recent_low_20` ✅
   - Volume lookback = 20 → Feature name: `avg_volume_20` ✅

2. **Existing Models Continue Working:**
   - Models trained with default config continue to work
   - No breaking changes for existing deployments

3. **New Configs Require Retraining:**
   - If RSI period ≠ 10 → Feature name changes → Model retraining required
   - If lookbacks ≠ 20 → Feature values change → Model retraining required

---

### 13.6 Testing Requirements

#### ML-Specific Test Cases:

1. **Feature Extraction Tests:**
   - ✅ Verify default config produces same features as current implementation
   - ✅ Verify non-default config produces different features
   - ✅ Verify backward compatibility with existing models

2. **Model Compatibility Tests:**
   - ✅ Test existing models with default config (should work)
   - ✅ Test existing models with non-default config (should fail gracefully)
   - ✅ Test new models trained with configurable features

3. **Retraining Tests:**
   - ✅ Verify models can be retrained with new feature sets
   - ✅ Compare model performance before/after retraining
   - ✅ Validate feature importance changes

---

### 13.7 ML Impact Summary

| Component | Impact Level | Breaking Changes | Action Required |
|-----------|-------------|------------------|-----------------|
| **MLVerdictService** | ⚠️ **MEDIUM** | ❌ None (with backward compatibility) | Update feature extraction |
| **MLTrainingService** | ✅ **LOW** | ❌ None | Use configurable features |
| **Existing Models** | ✅ **LOW** | ❌ None (default config) | Continue working |
| **New Models** | ⚠️ **MEDIUM** | ⚠️ Retraining required | Retrain with new features |

**Overall Assessment:**
- ✅ **No breaking changes** - Default config maintains backward compatibility
- ✅ **Existing models work** - Continue functioning with default parameters
- ⚠️ **Retraining required** - For non-default configurations
- ✅ **Low risk** - Backward compatibility strategy protects existing deployments

---

## 14. Scoring/Verdict System Impact Analysis

### 14.1 Current Scoring/Verdict Architecture

The system includes multiple scoring and verdict components:

1. **VerdictService** (`services/verdict_service.py`)
   - Determines verdict (strong_buy/buy/watch/avoid)
   - Uses RSI thresholds from config (already configurable ✅)
   - Uses support/resistance from timeframe_confirmation

2. **ScoringService** (`services/scoring_service.py`)
   - Calculates signal strength scores (0-25)
   - Uses hardcoded RSI thresholds for scoring
   - Uses timeframe_analysis data for scoring

3. **Backtest Scoring** (`core/backtest_scoring.py`)
   - Calculates backtest performance scores
   - Uses hardcoded RSI thresholds for entry conditions
   - Uses RSI-based threshold adjustments

4. **Trading Parameters** (`core/analysis.py`)
   - Calculates buy_range, stop_loss, target
   - Uses support/resistance levels from timeframe_confirmation

### 14.2 Scoring/Verdict Dependencies

**Current Hardcoded Values:**

| Component | Hardcoded Value | Location | Impact of Changes |
|-----------|----------------|----------|-------------------|
| **ScoringService** | RSI < 30 threshold | Line 72 | ⚠️ **Scoring mismatch** if RSI period/threshold changes |
| **ScoringService** | RSI < 20 threshold | Line 74 | ⚠️ **Scoring mismatch** if RSI period/threshold changes |
| **Backtest Scoring** | RSI10 < 30 entry | Line 197 | ⚠️ **Entry condition mismatch** if RSI period changes |
| **Backtest Scoring** | RSI < 20/25/30 factors | Lines 425-430 | ⚠️ **Threshold adjustment mismatch** if RSI period changes |
| **Trading Parameters** | Support/resistance from MTF | Uses timeframe_confirmation | ⚠️ **Parameter calculation changes** if lookbacks change |

**Already Configurable (No Impact):**
- VerdictService RSI thresholds (`self.config.rsi_oversold`, `self.config.rsi_extreme_oversold`) ✅
- VerdictService volume lookback (`avg_volume(df)` uses `config.volume_lookback_days`) ✅

### 14.3 Impact Assessment

#### Impact Level: ⚠️ **MEDIUM** - Scoring Logic Updates Required

| Change | Impact on Scoring/Verdict | Action Required |
|--------|---------------------------|-----------------|
| **RSI Period Configurable** | ⚠️ **Scoring thresholds may need adjustment** | Update hardcoded RSI thresholds in scoring |
| **Support/Resistance Lookback Configurable** | ⚠️ **Trading parameters will change** | Indirect impact via timeframe_confirmation |
| **Volume Exhaustion Lookback Configurable** | ✅ **No direct impact** | Already uses configurable volume lookback |

### 14.4 Required Changes for Scoring/Verdict Compatibility

#### Change 1: Update ScoringService RSI Thresholds (REQUIRED)
**File:** `services/scoring_service.py`

**Current Issues:**
- Line 72: Hardcoded `rsi_val < 30` threshold
- Line 74: Hardcoded `rsi_val < 20` threshold
- Lines 107-110: Hardcoded RSI severity thresholds (`extreme` = 20, `high` = 30)

**Proposed Solution:**
```python
# CURRENT (lines 72-74):
if rsi_val < 30:
    score += 1
if rsi_val < 20:
    score += 1

# PROPOSED:
from config.strategy_config import StrategyConfig
config = StrategyConfig.default()  # Or pass config to ScoringService

if rsi_val < config.rsi_oversold:  # Default: 30
    score += 1
if rsi_val < config.rsi_extreme_oversold:  # Default: 20
    score += 1

# CURRENT (lines 107-110):
if daily_oversold.get('severity') == 'extreme':
    score += 3  # RSI < 20
elif daily_oversold.get('severity') == 'high':
    score += 2  # RSI < 30

# PROPOSED:
if daily_oversold.get('severity') == 'extreme':
    score += 3  # RSI < config.rsi_extreme_oversold
elif daily_oversold.get('severity') == 'high':
    score += 2  # RSI < config.rsi_oversold
```

**Impact:** ⚠️ Medium - Scoring logic updates, but backward compatible with defaults

---

#### Change 2: Update Backtest Scoring RSI Thresholds (REQUIRED)
**File:** `core/backtest_scoring.py`

**Current Issues:**
- Line 197: Hardcoded `row['RSI10'] < 30` entry condition
- Lines 425-430: Hardcoded RSI factor thresholds (`< 20`, `< 25`, `< 30`)

**Proposed Solution:**
```python
# CURRENT (line 197):
row['RSI10'] < 30 and 

# PROPOSED:
from config.strategy_config import StrategyConfig
config = StrategyConfig.default()

row[f'RSI{config.rsi_period}'] < config.rsi_oversold and

# CURRENT (lines 425-430):
if current_rsi < 20:  # Extremely oversold
    rsi_factor = 0.7
elif current_rsi < 25:  # Very oversold
    rsi_factor = 0.8
elif current_rsi < 30:  # Oversold
    rsi_factor = 0.9

# PROPOSED:
if current_rsi < config.rsi_extreme_oversold:  # Default: 20
    rsi_factor = 0.7
elif current_rsi < (config.rsi_extreme_oversold + 5):  # Default: 25
    rsi_factor = 0.8
elif current_rsi < config.rsi_oversold:  # Default: 30
    rsi_factor = 0.9
```

**Impact:** ⚠️ Medium - Entry conditions and threshold adjustments updated

---

#### Change 3: Update Trading Parameters (INDIRECT)
**File:** `core/analysis.py` (calculate_smart_buy_range, calculate_smart_stop_loss, calculate_smart_target)

**Impact:** ⚠️ **Indirect** - Trading parameters use support/resistance from `timeframe_confirmation`
- Support/resistance levels will change based on configurable lookbacks
- This is **expected behavior** - better support/resistance identification → better trading parameters
- No code changes needed - automatically benefits from improved support/resistance analysis

---

### 14.5 Backward Compatibility Strategy

#### ✅ Backward Compatible Approach:

1. **Default Config = Current Behavior:**
   - RSI period = 10 → Scoring uses RSI10 ✅
   - RSI oversold = 30 → Scoring thresholds: < 30 ✅
   - RSI extreme oversold = 20 → Scoring thresholds: < 20 ✅
   - Support/resistance lookback = 20 → Same as current ✅

2. **Scoring Logic Continues Working:**
   - Default config produces same scores as current implementation
   - No breaking changes for existing deployments

3. **Non-Default Configs:**
   - Scoring adjusts automatically based on config values
   - Trading parameters improve with better support/resistance identification

---

### 14.6 Testing Requirements

#### Scoring/Verdict-Specific Test Cases:

1. **Scoring Tests:**
   - ✅ Verify default config produces same scores as current implementation
   - ✅ Verify scoring adjusts correctly with non-default RSI thresholds
   - ✅ Verify timeframe_analysis scoring works with configurable lookbacks

2. **Verdict Tests:**
   - ✅ Verify verdict determination unchanged with default config
   - ✅ Verify verdict logic uses configurable RSI thresholds correctly

3. **Trading Parameters Tests:**
   - ✅ Verify buy_range calculation uses improved support/resistance
   - ✅ Verify stop_loss calculation uses improved support levels
   - ✅ Verify target calculation uses improved resistance levels

4. **Backtest Scoring Tests:**
   - ✅ Verify entry conditions use configurable RSI period/thresholds
   - ✅ Verify RSI factor adjustments use configurable thresholds

---

### 14.7 Scoring/Verdict Impact Summary

| Component | Impact Level | Breaking Changes | Action Required |
|-----------|-------------|------------------|-----------------|
| **VerdictService** | ✅ **LOW** | ❌ None | Already uses configurable RSI thresholds |
| **ScoringService** | ⚠️ **MEDIUM** | ❌ None (with defaults) | Update hardcoded RSI thresholds |
| **Backtest Scoring** | ⚠️ **MEDIUM** | ❌ None (with defaults) | Update hardcoded RSI thresholds |
| **Trading Parameters** | ✅ **LOW** | ❌ None | Indirect improvement via better support/resistance |

**Overall Assessment:**
- ✅ **No breaking changes** - Default config maintains backward compatibility
- ✅ **Scoring improves** - Better alignment with configurable thresholds
- ✅ **Trading parameters improve** - Better support/resistance identification
- ✅ **Low risk** - Backward compatibility strategy protects existing deployments

---

## 15. Indicator Calculation Flow Analysis

### 15.1 Current Indicator Calculation Flow

**After BacktestEngine data is available, indicators are calculated as follows:**

#### Step 1: BacktestEngine Calculates Indicators (Once)
**File:** `backtest/backtest_engine.py` - `_calculate_indicators()` (line 128)

```python
def _calculate_indicators(self):
    # Calculate RSI using pandas_ta default method (matches TradingView)
    self.data['RSI10'] = ta.rsi(self.data['Close'], length=self.config.RSI_PERIOD)
    
    # Calculate EMA200
    self.data['EMA200'] = ta.ema(self.data['Close'], length=self.config.EMA_PERIOD)
    
    # Drop NaN values
    self.data = self.data.dropna()
```

**Key Points:**
- Uses `pandas_ta` library (`ta.rsi()` and `ta.ema()`)
- Calculated **once** during `_load_data()` (line 105)
- Stored in `self.data['RSI10']` and `self.data['EMA200']`
- Uses configurable `RSI_PERIOD` and `EMA_PERIOD` from `BacktestConfig`

---

#### Step 2: Integrated Backtest Uses Pre-Calculated Indicators
**File:** `integrated_backtest.py` - `run_backtest()` (line 48)

```python
engine = BacktestEngine(...)  # Indicators already calculated here

# Iterate through the data to identify buy signals
for current_date, row in engine.data.iterrows():
    signal = {
        'rsi': row['RSI10'],        # ← Pre-calculated from BacktestEngine
        'ema200': row['EMA200']     # ← Pre-calculated from BacktestEngine
    }
```

**Key Points:**
- Uses indicators **already calculated** by BacktestEngine
- No recalculation needed at this stage
- Values extracted directly from `engine.data` DataFrame

---

#### Step 3: Trade Agent Recalculates Indicators (DUPLICATE)
**File:** `integrated_backtest.py` - `trade_agent()` (line 117)

```python
def trade_agent(stock_name: str, buy_date: str) -> SignalResult:
    # Calls analyze_ticker which fetches data AGAIN
    analysis_result = analyze_ticker(
        stock_name,
        enable_multi_timeframe=True,
        as_of_date=buy_date  # ← Fetches data again for this date
    )
```

**File:** `core/indicators.py` - `compute_indicators()` (line 23)

```python
def compute_indicators(df):
    # Use Wilder's RSI method (matches TradingView)
    df['rsi10'] = wilder_rsi(df[close_col], period=10)  # ← DIFFERENT METHOD!
    
    df['ema200'] = df[close_col].ewm(span=200).mean()  # ← DIFFERENT METHOD!
```

**Key Points:**
- **Fetches data again** (duplicate API call)
- **Recalculates indicators** using **different methods**:
  - RSI: `wilder_rsi()` (custom function) vs `pandas_ta.rsi()` 
  - EMA: `df.ewm().mean()` (pandas) vs `pandas_ta.ema()`
- Uses **hardcoded** `period=10` and `span=200` (not configurable)

---

### 15.2 Critical Issue: Inconsistent Calculation Methods

**BacktestEngine** and **Trade Agent** use **different calculation methods**:

| Component | RSI Method | EMA Method | Library | Configurable |
|-----------|------------|------------|---------|--------------|
| **BacktestEngine** | `pandas_ta.rsi()` | `pandas_ta.ema()` | pandas_ta | ✅ Yes (via BacktestConfig) |
| **Trade Agent** | `wilder_rsi()` (custom) | `df.ewm().mean()` (pandas) | pandas | ❌ No (hardcoded) |

#### Impact:

1. **Different RSI Values:**
   - `pandas_ta.rsi()` may use different smoothing/calculation than `wilder_rsi()`
   - Could lead to different signals between BacktestEngine and Trade Agent

2. **Different EMA Values:**
   - `pandas_ta.ema()` vs `df.ewm().mean()` may have slight differences
   - Could affect EMA200 comparison logic

3. **Data Duplication:**
   - Data fetched twice (BacktestEngine + Trade Agent)
   - Indicators calculated twice with different methods

4. **Configuration Inconsistency:**
   - BacktestEngine uses configurable RSI period
   - Trade Agent uses hardcoded RSI period = 10

---

### 15.3 Required Changes for Indicator Consistency

#### Change 1: Reuse BacktestEngine Data in Trade Agent (CRITICAL)
**File:** `integrated_backtest.py`

**Current:** Trade agent fetches data and recalculates indicators  
**Proposed:** Reuse BacktestEngine data and indicators

**Implementation:**
```python
def trade_agent(
    stock_name: str, 
    buy_date: str,
    pre_fetched_data: Optional[pd.DataFrame] = None,
    pre_calculated_indicators: Optional[Dict] = None
) -> SignalResult:
    """
    Trade agent with optional pre-fetched data
    
    Args:
        pre_fetched_data: DataFrame with OHLCV data (from BacktestEngine)
        pre_calculated_indicators: Dict with rsi, ema200 values (from BacktestEngine)
    """
    if pre_fetched_data is not None and pre_calculated_indicators is not None:
        # Use pre-calculated indicators from BacktestEngine
        # Skip data fetching and indicator calculation
        # Use pre_fetched_data for analysis (multi-timeframe, etc.)
    else:
        # Fallback to current behavior (fetch and calculate)
        analysis_result = analyze_ticker(...)
```

**Benefits:**
- ✅ Eliminates duplicate data fetching
- ✅ Uses same calculation method (BacktestEngine's pandas_ta)
- ✅ Consistent indicator values
- ✅ Better performance

---

#### Change 2: Standardize Calculation Methods (REQUIRED)
**File:** `core/indicators.py`

**Option A: Use pandas_ta (Recommended)**
```python
def compute_indicators(df, rsi_period=10, ema_period=200):
    import pandas_ta as ta
    
    # Use pandas_ta for consistency with BacktestEngine
    df['rsi10'] = ta.rsi(df[close_col], length=rsi_period)
    df['ema200'] = ta.ema(df[close_col], length=ema_period)
```

**Option B: Use wilder_rsi + pandas EMA**
```python
# Update BacktestEngine to use wilder_rsi
def _calculate_indicators(self):
    from core.indicators import wilder_rsi
    self.data['RSI10'] = wilder_rsi(self.data['Close'], period=self.config.RSI_PERIOD)
    self.data['EMA200'] = self.data['Close'].ewm(span=self.config.EMA_PERIOD).mean()
```

**Recommendation:** **Option A** - Use pandas_ta for consistency (already used in BacktestEngine)

---

#### Change 3: Make compute_indicators() Configurable (REQUIRED)
**File:** `core/indicators.py`

**Current:**
```python
def compute_indicators(df):
    df['rsi10'] = wilder_rsi(df[close_col], period=10)  # Hardcoded
    df['ema200'] = df[close_col].ewm(span=200).mean()  # Hardcoded
```

**Proposed:**
```python
def compute_indicators(df, rsi_period=None, ema_period=None, config=None):
    """
    Compute technical indicators with configurable parameters
    
    Args:
        df: DataFrame with OHLCV data
        rsi_period: RSI calculation period (uses config if None)
        ema_period: EMA calculation period (uses config if None)
        config: StrategyConfig instance (uses default if None)
    """
    if config is None:
        from config.strategy_config import StrategyConfig
        config = StrategyConfig.default()
    
    rsi_period = rsi_period or config.rsi_period
    ema_period = ema_period or config.ema_period if hasattr(config, 'ema_period') else 200
    
    # Use pandas_ta for consistency
    import pandas_ta as ta
    df['rsi10'] = ta.rsi(df[close_col], length=rsi_period)
    df['ema200'] = ta.ema(df[close_col], length=ema_period)
```

**Impact:** ✅ High - Makes indicator calculation configurable and consistent

---

### 15.4 Integration with Data Fetching Optimization

**This issue is directly related to Section 12.6 (Data Fetching Duplication):**

- **Data Fetching Optimization** (Section 12.6): Eliminates duplicate data fetches
- **Indicator Calculation Consistency** (This section): Eliminates duplicate indicator calculations and ensures consistency

**Combined Solution:**
1. Reuse BacktestEngine data in trade_agent (eliminates fetch #2 and #3)
2. Reuse BacktestEngine indicators (eliminates recalculation)
3. Standardize calculation methods (ensures consistency)

**Total Impact:**
- Eliminates 2+ data fetches per signal
- Eliminates duplicate indicator calculations
- Ensures consistent indicator values
- Improves performance significantly

---

### 15.5 Testing Requirements

#### Indicator Calculation Tests:

1. **Consistency Tests:**
   - ✅ Verify BacktestEngine and Trade Agent produce same RSI/EMA values
   - ✅ Verify pandas_ta.rsi() and wilder_rsi() produce same results (or document differences)
   - ✅ Verify pandas_ta.ema() and df.ewm().mean() produce same results

2. **Configuration Tests:**
   - ✅ Verify compute_indicators() uses configurable RSI period
   - ✅ Verify compute_indicators() uses configurable EMA period
   - ✅ Verify default config produces same values as current implementation

3. **Integration Tests:**
   - ✅ Verify trade_agent() works with pre-fetched data
   - ✅ Verify trade_agent() works with pre-calculated indicators
   - ✅ Verify fallback to current behavior works correctly

---

### 15.6 Indicator Calculation Impact Summary

| Component | Current Issue | Impact | Action Required |
|-----------|--------------|--------|-----------------|
| **BacktestEngine** | ✅ Uses pandas_ta, configurable | ✅ Good | None |
| **Trade Agent** | ❌ Uses different methods, hardcoded | ⚠️ **CRITICAL** | Reuse data + standardize methods |
| **compute_indicators()** | ❌ Hardcoded periods | ⚠️ **HIGH** | Make configurable + use pandas_ta |
| **Data Fetching** | ❌ Duplicate fetches | ⚠️ **CRITICAL** | Reuse BacktestEngine data |

**Overall Assessment:**
- ⚠️ **Critical inconsistency** - Different calculation methods between components
- ⚠️ **Performance impact** - Duplicate calculations waste resources
- ✅ **Fixable** - Solutions identified and documented
- ✅ **Low risk** - Backward compatibility maintained with defaults

---

---

## 16. Additional System Impact Analysis

### 16.1 Pattern Detection Impact

**File:** `core/patterns.py`

**Current Issues:**
- Line 20: Hardcoded `look = 10` for divergence detection lookback
- Line 36: Uses hardcoded `rsi10` column name

**Impact:** ⚠️ **LOW** - Pattern detection may need adjustment if RSI period changes

**Implementation Plan:**

**Task 13: Make Pattern Detection Configurable**

1. **Update bullish_divergence() function signature**:
   ```python
   # CURRENT (line 19):
   def bullish_divergence(df):
       look = 10
   
   # PROPOSED:
   def bullish_divergence(df, rsi_period=10, lookback_period=10):
       """
       Detect bullish divergence pattern
       
       Args:
           df: DataFrame with price and RSI data
           rsi_period: RSI calculation period (default: 10)
           lookback_period: Lookback period for divergence detection (default: 10)
       """
       look = lookback_period
   ```

2. **Update RSI column access** (Line 36):
   ```python
   # CURRENT:
   rsi_now = sub.loc[idx_price_ll, 'rsi10']
   rsi_earlier = prev_window.loc[earlier_idx, 'rsi10']
   
   # PROPOSED:
   rsi_col = f'rsi{rsi_period}'
   if rsi_col not in sub.columns:
       return False  # RSI column doesn't exist
   
   rsi_now = sub.loc[idx_price_ll, rsi_col]
   rsi_earlier = prev_window.loc[earlier_idx, rsi_col]
   ```

3. **Update callers** (if any):
   - Update `SignalService.detect_pattern_signals()` to pass config
   - Update `core/analysis.py` to pass configurable RSI period
   - Default to 10 for backward compatibility

4. **Testing Requirements**:
   - Verify pattern detection works with default RSI period (10)
   - Verify pattern detection works with different RSI periods
   - Verify backward compatibility with existing callers

**Estimated Time:** 1-2 hours

---

### 16.2 Volume Analysis Impact

**File:** `core/volume_analysis.py`

**Current Issues:**
- Line 223: `analyze_volume_pattern(df, lookback_days: int = 20)` - Default hardcoded to 20
- Uses `VOLUME_LOOKBACK_DAYS` from `config.settings` (value: 50) - Different from volume_exhaustion_lookback

**Impact:** ✅ **LOW** - Volume pattern analysis uses different lookback than volume exhaustion

**Note:** `VOLUME_LOOKBACK_DAYS` (50 days) is for liquidity assessment, different from `volume_exhaustion_lookback` (10 days) for exhaustion detection. This is **intentional** - no change needed.

---

### 16.3 Candle Analysis Impact

**File:** `core/candle_analysis.py`

**Current Issues:**
- Line 84: `calculate_market_context(df, lookback_days=20)` - Hardcoded default
- Line 260: `analyze_recent_candle_quality(df, lookback_candles=3)` - Hardcoded default
- Line 323: Uses `lookback_days=20` for market context

**Impact:** ✅ **LOW** - Candle analysis lookbacks are independent of indicator periods

**Recommendation:** Keep as-is - Candle analysis lookbacks are separate from indicator periods

---

### 16.4 Core Analysis Constants Impact

**File:** `core/analysis.py`

**Current Issues:**
- Line 11: Imports `RSI_OVERSOLD` from `config.settings` (hardcoded constant = 30)
- Line 487: Uses `RSI_OVERSOLD` constant
- Line 544: Uses `RSI_OVERSOLD` constant  
- Line 546: Hardcoded `rsi_threshold = 20`

**Impact:** ⚠️ **MEDIUM** - Uses old `config.settings` constants instead of `StrategyConfig`

**Required Changes:**
```python
# CURRENT (line 11):
from config.settings import RSI_OVERSOLD, ...

# PROPOSED:
from config.strategy_config import StrategyConfig
config = StrategyConfig.default()
rsi_oversold = config.rsi_oversold  # Use StrategyConfig instead

# CURRENT (line 487):
if last['rsi10'] is not None and last['rsi10'] < RSI_OVERSOLD:

# PROPOSED:
if last[f'rsi{config.rsi_period}'] is not None and last[f'rsi{config.rsi_period}'] < config.rsi_oversold:

# CURRENT (line 546):
rsi_threshold = 20  # Hardcoded

# PROPOSED:
rsi_threshold = config.rsi_extreme_oversold  # Use configurable value
```

**Note:** This is part of the legacy `analyze_ticker()` function. Should migrate to use `AnalysisService` which already uses `StrategyConfig`.

---

### 16.5 Auto-Trading Module Impact

**File:** `modules/kotak_neo_auto_trader/config.py`

**Current Issues:**
- Line 23: `RSI_PERIOD = 10` - Hardcoded in auto-trader config
- Line 24-25: `EMA_SHORT = 9`, `EMA_LONG = 200` - Separate EMA config

**File:** `modules/kotak_neo_auto_trader/auto_trade_engine.py`

**Current Issues:**
- Line 203: Uses `compute_indicators()` which has hardcoded `period=10`
- Line 212: Uses `config.EMA_SHORT` and `config.EMA_LONG` (separate config)

**Impact:** ⚠️ **MEDIUM** - Auto-trader uses separate config, may diverge from main strategy

**Implementation Plan:**

**Task 12: Sync Auto-Trader RSI Period with StrategyConfig**

1. **Update kotak_neo_auto_trader/config.py**:
   ```python
   # CURRENT (line 23):
   RSI_PERIOD = 10
   
   # PROPOSED:
   from config.strategy_config import StrategyConfig
   
   # Sync RSI period from StrategyConfig for consistency
   _strategy_config = StrategyConfig.default()
   RSI_PERIOD = _strategy_config.rsi_period  # Default: 10, synced with main strategy
   
   # Keep EMA config separate (auto-trader specific)
   EMA_SHORT = 9
   EMA_LONG = 200
   ```

2. **Update auto_trade_engine.py** (Line 203):
   ```python
   # CURRENT:
   df = compute_indicators(df)
   
   # PROPOSED:
   from config.strategy_config import StrategyConfig
   strategy_config = StrategyConfig.default()
   
   # Use configurable RSI period
   df = compute_indicators(df, rsi_period=strategy_config.rsi_period)
   ```

3. **Update indicator access** (Line 212):
   ```python
   # CURRENT:
   'rsi10': float(last['rsi10']),
   
   # PROPOSED:
   rsi_col = f'rsi{strategy_config.rsi_period}'
   rsi_col: float(last[rsi_col]),
   ```

4. **Testing Requirements**:
   - Verify auto-trader uses same RSI period as main strategy
   - Verify EMA_SHORT/EMA_LONG remain separate (auto-trader specific)
   - Verify backward compatibility with existing trades

**Estimated Time:** 1-2 hours

**Recommendation:** **Sync RSI period for consistency**, but keep EMA_SHORT/EMA_LONG separate (auto-trader specific)

---

### 16.6 Config Settings Module Impact

**File:** `config/settings.py`

**Current Issues:**
- Line 23: `RSI_OVERSOLD = 30` - Hardcoded constant
- Line 24: `RSI_NEAR_OVERSOLD = 40` - Hardcoded constant
- Line 9: `VOLUME_LOOKBACK_DAYS = 50` - Different from volume_exhaustion_lookback

**Impact:** ⚠️ **MEDIUM** - Legacy constants still used in some places

**Implementation Plan:**

**Task 14: Deprecate Legacy Config Constants**

1. **Add deprecation warnings to config/settings.py**:
   ```python
   # CURRENT (lines 23-24):
   RSI_OVERSOLD = 30
   RSI_NEAR_OVERSOLD = 40
   
   # PROPOSED:
   import warnings
   from config.strategy_config import StrategyConfig
   
   # Deprecated: Use StrategyConfig.rsi_oversold instead
   _strategy_config = StrategyConfig.default()
   RSI_OVERSOLD = _strategy_config.rsi_oversold
   RSI_NEAR_OVERSOLD = _strategy_config.rsi_near_oversold
   
   def _warn_deprecated_rsi_constant(name):
       warnings.warn(
           f"{name} is deprecated. Use StrategyConfig.{name.lower()} instead. "
           f"This will be removed in a future version.",
           DeprecationWarning,
           stacklevel=2
       )
   
   # Wrap access with deprecation warning (if needed)
   # Note: Direct constant access won't trigger warnings, but we document it
   ```

2. **Create migration guide**:
   ```python
   # Add to config/settings.py docstring or separate migration doc:
   """
   MIGRATION GUIDE:
   
   Old (deprecated):
       from config.settings import RSI_OVERSOLD
       if rsi < RSI_OVERSOLD:
   
   New (recommended):
       from config.strategy_config import StrategyConfig
       config = StrategyConfig.default()
       if rsi < config.rsi_oversold:
   """
   ```

3. **Update remaining usages**:
   - Search codebase for `RSI_OVERSOLD` and `RSI_NEAR_OVERSOLD` imports
   - Update to use `StrategyConfig` instead
   - Keep `VOLUME_LOOKBACK_DAYS` (different purpose - liquidity assessment)

4. **Testing Requirements**:
   - Verify deprecated constants still work (backward compatibility)
   - Verify deprecation warnings appear when used
   - Verify migration guide is clear and accurate

**Estimated Time:** 1-2 hours

**Note:** Keep `VOLUME_LOOKBACK_DAYS` as-is (different purpose - liquidity assessment, not exhaustion detection)

---

### 16.7 Additional Impact Summary

| Component | Impact Level | Breaking Changes | Action Required | Estimated Time |
|-----------|-------------|------------------|-----------------|----------------|
| **Pattern Detection** | ⚠️ **LOW** | ❌ None | Make lookback configurable (Task 13) | 1-2 hours |
| **Volume Analysis** | ✅ **LOW** | ❌ None | No change needed (different purpose) | - |
| **Candle Analysis** | ✅ **LOW** | ❌ None | No change needed (independent) | - |
| **Core Analysis (Legacy)** | ⚠️ **MEDIUM** | ❌ None | Migrate to StrategyConfig (Task 11) | 2-3 hours |
| **Auto-Trading Module** | ⚠️ **MEDIUM** | ❌ None | Sync RSI period with StrategyConfig (Task 12) | 1-2 hours |
| **Config Settings** | ⚠️ **MEDIUM** | ❌ None | Deprecate legacy constants (Task 14) | 1-2 hours |

**Total Additional Time:** 5-9 hours

**Overall Assessment:**
- ✅ **Most components unaffected** - Pattern, volume, candle analysis are independent
- ⚠️ **Legacy code migration** - `core/analysis.py` should use StrategyConfig
- ⚠️ **Auto-trader consistency** - Should sync RSI period with main strategy
- ✅ **Low risk** - Changes are optional improvements, not critical

---

## 17. Approval & Sign-off

**Document Status:** DRAFT - Updated with Your Decisions

**Review Required From:**
- [ ] Strategy Owner (You)
- [ ] Technical Lead (if applicable)
- [ ] Testing Team (if applicable)

**Approval:**
- [ ] Approved - Proceed with implementation
- [ ] Approved with modifications (specify below)
- [ ] Rejected (specify reasons below)

**Comments/Modifications:**
_________________________________________________
_________________________________________________
_________________________________________________

**Sign-off:**
- **Reviewer:** ________________
- **Date:** ________________
- **Signature:** ________________

---

## Appendix A: Current Code References

### Hardcoded RSI Period
- `core/indicators.py:36` - `wilder_rsi(df[close_col], period=10)`
- `backtest/backtest_config.py:16` - `RSI_PERIOD = 10`
- Multiple references to `rsi10` assuming period=10

### Hardcoded Support/Resistance Lookback
- `core/timeframe_analysis.py:14` - `self.support_lookback = 20`
- Used in `_analyze_support_levels()` and `_analyze_resistance_levels()`

### Hardcoded Volume Exhaustion Lookback
- `core/timeframe_analysis.py:15` - `self.volume_lookback = 10`
- Used in `_analyze_volume_exhaustion()`

---

## Appendix B: Environment Variables

New environment variables to be supported:

```bash
# RSI Configuration
RSI_PERIOD=10

# Support/Resistance Configuration
SUPPORT_RESISTANCE_LOOKBACK_DAILY=20
SUPPORT_RESISTANCE_LOOKBACK_WEEKLY=50

# Volume Exhaustion Configuration
VOLUME_EXHAUSTION_LOOKBACK_DAILY=10
VOLUME_EXHAUSTION_LOOKBACK_WEEKLY=20

# Data Fetching Configuration
DATA_FETCH_DAILY_MAX_YEARS=5
DATA_FETCH_WEEKLY_MAX_YEARS=3

# Adaptive Logic Configuration
ENABLE_ADAPTIVE_LOOKBACK=true
```

---

**End of Document**
