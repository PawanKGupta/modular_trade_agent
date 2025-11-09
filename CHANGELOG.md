# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [25.7.0] - 2025-11-09

### Added
- **RSI30 Requirement Enforcement**: Trading parameters only calculated when RSI < 30 (above EMA200) or RSI < 20 (below EMA200)
- **Single Stock Backtest Script**: New script `scripts/run_single_stock_backtest.py` for testing individual stocks
- **Enhanced CSV Export**: Added 30+ fields for ML training data collection (justification, pe, pb, rsi, volume analysis, etc.)
- **Unit Tests**: Added comprehensive unit tests for ML disabled logic, RSI30 requirement, and liquidity threshold
- **Regression Test Fix**: Fixed `test_backtest_validation_default` to handle RSI30 requirement and pyramiding trades

### Changed
- **ML Model Disabled**: Temporarily disabled ML model for verdict determination, using rule-based logic only until ML is fully trained
- **Liquidity Threshold Lowered**: Minimum absolute average volume reduced from 20,000 to 10,000 to allow more stocks
- **Chart Quality Thresholds Relaxed**: 
  - Gap frequency: 25% max (was 20%)
  - Chart score: 50 minimum (was 60)
  - Daily range: 1.0% minimum (was 1.5%)
  - Extreme candles: 20% max (was 15%)
- **Volume Requirements Relaxed**: 
  - Minimum volume: 70% of average (was 80%)
  - For RSI < 30 oversold conditions: 50% of average (RSI-based adjustment)
- **Weekly Uptrend Context Refined**: 
  - Weekly trend up and price near support → +2 points
  - Weekly trend up but mid-range → +1 point
  - Weekly trend flat/down → 0 points
- **Fundamental Filter Flexible**: 
  - Allows "watch" verdict for growth stocks (negative PE) if PB ratio < 5.0
  - Still forces "avoid" for loss-making companies (negative PE + PB > 5.0)
- **Trade Execution Validation**: Updated to handle pyramiding trades correctly (entry_price is average for pyramided positions)

### Fixed
- **Regression Test**: Fixed `test_backtest_validation_default` to account for RSI30 requirement and rule-based logic differences
- **Trading Parameters Validation**: Updated to check individual fields and handle RSI30 requirement correctly
- **Volume Check Validation**: Downgraded to warnings (RSI-based volume adjustment allows lower volume when RSI < 30)
- **Verdict Mismatch Validation**: Differentiated significant vs minor mismatches, downgraded minor mismatches to warnings
- **Capital Validation**: Added capital/quantity to position data, handle missing capital gracefully
- **Entry Price Validation**: Increased tolerance and handle pyramiding correctly

### Documentation
- **Consolidated Changes Document**: Created `documents/CHANGES_2025_11_09_CONSOLIDATED.md` summarizing all changes
- **Regression Test Fix Documentation**: Added `documents/REGRESSION_TEST_FIX_2025_11_09.md`
- **Verdict Watch Analysis**: Added `documents/VERDICT_WATCH_ANALYSIS.md` documenting root cause analysis

## [25.6.0] - 2025-11-02

### Added (Phase 4: Cleanup & Consolidation)

- **Additional Services** - Phase 4 service layer extensions
  - `services/scoring_service.py` - Scoring service (migrated from `core/scoring.py`)
  - `services/backtest_service.py` - Backtest integration service (wraps `core/backtest_scoring.py`)
  - **Benefits:** Service layer consistency, dependency injection ready

- **Deprecation Utilities** - Phase 4 deprecation management
  - `utils/deprecation.py` - Deprecation warnings and migration guides
  - Deprecation notices for all legacy `core.*` functions
  - Migration guides for smooth transition

- **Documentation** - Phase 4 documentation
  - `documents/phases/PHASE4_MIGRATION_GUIDE.md` - Comprehensive migration guide
  - `documents/phases/PHASE4_DUPLICATES_COMPLETE.md` - Duplicate consolidation report
  - `documents/phases/PHASE4_DEPRECATION_COMPLETE.md` - Deprecation status

### Changed (Phase 4: Cleanup & Consolidation)

- **Deprecated Legacy Functions** - Phase 4 deprecation warnings
  - `core.analysis.analyze_ticker()` → Use `services.AnalysisService`
  - `core.analysis.analyze_multiple_tickers()` → Use `services.AsyncAnalysisService`
  - `core.scoring.compute_strength_score()` → Use `services.ScoringService`
  - `core.backtest_scoring.add_backtest_scores_to_results()` → Use `services.BacktestService`
  - `core.analysis.calculate_smart_*()` → Use `services.VerdictService`
  - **Migration:** See `documents/phases/PHASE4_MIGRATION_GUIDE.md`

- **Consolidated Duplicates** - Phase 4 duplicate removal
  - Consolidated `src/application/services/scoring_service.py` → `services/scoring_service.py`
  - Eliminated ~213 lines of duplicate code
  - Single source of truth for all services

- **Updated trade_agent.py** - Phase 4 service migration
  - Now uses `services.ScoringService` instead of `core.scoring`
  - Now uses `services.BacktestService` instead of `core.backtest_scoring`
  - Refactored `compute_trading_priority_score()` to use `ScoringService`

- **Service Layer Updates** - Phase 4 infrastructure support
  - `services/data_service.py` - Supports infrastructure injection (future-ready)
  - `services/indicator_service.py` - Prepared for infrastructure migration
  - All services maintain backward compatibility with `core.*` modules

### Removed (Phase 4)

- **Duplicate Code** - Consolidated duplicate implementations
  - Removed duplicate `ScoringService` implementation in `src/application/services/`
  - Consolidated to single implementation in `services/scoring_service.py`

---

## [25.5.0] - 2025-11-02

### Added (Phase 1-3 Refactoring)

- **Service Layer Architecture** - Extracted monolithic `analyze_ticker()` into modular services (Phase 1)
  - `services/analysis_service.py` - Main orchestrator service
  - `services/data_service.py` - Data fetching service
  - `services/indicator_service.py` - Indicator calculation service
  - `services/signal_service.py` - Signal detection service
  - `services/verdict_service.py` - Verdict determination service
  - **Benefits:** Improved testability, maintainability, dependency injection ready

- **Async Processing** - Phase 2 async support
  - `services/async_analysis_service.py` - Async batch analysis
  - `services/async_data_service.py` - Async data fetching
  - **Benefits:** 80% faster batch analysis (25min → 5min for 50 stocks)

- **Caching Layer** - Phase 2 caching
  - `services/cache_service.py` - Memory-based cache
  - `services/cached_data_service.py` - Cached data fetching wrapper
  - **Benefits:** Reduces API calls by 70-90%

- **Event-Driven Architecture** - Phase 3 event bus
  - `services/event_bus.py` - Event bus with subscribe/publish
  - Event types and event handling infrastructure

- **Pipeline Pattern** - Phase 3 pipeline
  - `services/pipeline.py` - Analysis pipeline orchestrator
  - `services/pipeline_steps.py` - Pluggable pipeline steps
  - **Benefits:** Flexible, composable analysis workflow

- **Typed Data Classes** - Phase 2 models
  - `services/models.py` - Typed models (AnalysisResult, Verdict, TradingParameters, etc.)
  - **Benefits:** Type safety, IDE autocomplete, better documentation

- **Configuration Management** - Centralized strategy configuration (Phase 1)
  - `config/strategy_config.py` - StrategyConfig dataclass with all parameters
  - Environment variable support via `from_env()` method
  - **Benefits:** No more magic numbers, A/B testing capability, environment-specific configs

### Changed

- **Backward Compatibility** - All phases maintain backward compatibility
  - `core/analysis.py::analyze_ticker()` delegates to service layer
  - Maintains 100% backward compatibility
  - All existing code works without changes
  - Falls back to legacy implementation if service unavailable

### Impact

- **Code Quality:** Improved from monolithic (344 lines) to modular (5 services, 50-290 lines each)
- **Testability:** Each service can now be tested in isolation
- **Maintainability:** Clear separation of concerns, easier to modify
- **No Breaking Changes:** All existing code continues to work
- **Performance:** No regression (same underlying logic)

### Migration Guide

**For new code, prefer using service layer directly:**
```python
from services.analysis_service import AnalysisService

service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")
```

**For existing code (no changes needed):**
```python
from core.analysis import analyze_ticker

result = analyze_ticker("RELIANCE.NS")  # Still works, delegates to service layer
```

---

## [25.4.1] - 2025-11-02

### Fixed
- **Conservative Bias in Backtest Scoring** - Reduced buy verdict thresholds by 10-20% to capture more profitable opportunities
  - High confidence (≥5 trades): buy threshold reduced from 40 to 35, combined score from 25 to 22
  - Low confidence (<5 trades): buy threshold reduced from 50 to 40, combined score from 35 to 28
  - Fixed issue where system missed 4 profitable trades (67% of executed trades)
  
- **Missing Target/Stop Parameters** - Added automatic parameter recalculation for upgraded verdicts
  - When verdict is upgraded from "avoid"/"watch" to "buy"/"strong_buy", system now automatically calculates missing buy_range, target, and stop parameters
  - Fixes Telegram alerts showing "target: 0" for upgraded stocks
  - Includes fallback to safe defaults if calculation fails

### Testing
- All tests passed: 137 passed, 2 skipped
- Test coverage: 76%
- Validated with 3 test stocks (SIMBHALS, FEL, SUDARSCHEM)

### Documentation
- Added comprehensive bug fix documentation: `documents/bug_fixes/FIX_CONSERVATIVE_BIAS_AND_MISSING_TARGETS.md`
- Added data flow documentation: `documents/DATA_FLOW_BACKTEST.md`
- Added architecture analysis: `documents/architecture/DESIGN_ANALYSIS_AND_RECOMMENDATIONS.md`

### Impact
- Expected to increase opportunity capture rate while maintaining 100% win rate quality
- No breaking changes - backward compatible

---

## [25.4.0] - 2025-10-15

### Initial Q4 2025 Release
- Core trading agent functionality
- Multi-timeframe analysis
- Backtest scoring integration
- Kotak Neo broker integration
- Telegram notifications
- Clean architecture implementation in `src/` directory

---

[25.4.1]: https://github.com/yourusername/modular_trade_agent/compare/v25.4.0...v25.4.1
[25.4.0]: https://github.com/yourusername/modular_trade_agent/releases/tag/v25.4.0
