# Trading System Documentation

## 📚 Quick Navigation

### Getting Started
- [Getting Started Guide](getting-started/GETTING_STARTED.md)
- [Quick Reference](getting-started/QUICK_NAV.md)
- [Documentation Index](getting-started/DOCUMENTATION_INDEX.md)

### Latest Updates (November 2025)

#### Integrated Backtest Refactor ⭐ NEW
- **[INTEGRATED_BACKTEST_REFACTOR_NOV_2025.md](INTEGRATED_BACKTEST_REFACTOR_NOV_2025.md)** - Complete refactor documentation
  - Fixed 3 critical bugs (exit tracking, level marking, logging)
  - Single-pass daily iteration (eliminates redundancy)
  - Signal numbering and consistent date logging
  - Re-entry logic clarification (no EMA200 check by design)

#### Superseded/Historical Documents
- ~~BACKTEST_DAILY_MONITORING_DESIGN.md~~ - Deleted (replaced by refactor doc)
- [architecture/INTEGRATED_README.md](architecture/INTEGRATED_README.md) ⚠️ - Describes old signal-based approach
- [features/BACKTEST_INTEGRATION_FIX.md](features/BACKTEST_INTEGRATION_FIX.md) ⚠️ - Pre-refactor fix

### Core Documentation

#### Architecture
- [System Architecture](architecture/ARCHITECTURE_GUIDE.md)
- [Integrated Backtest Architecture](architecture/INTEGRATED_README.md)
- [Service Architecture](architecture/SERVICE_ARCHITECTURE.md)

#### Backtest System
- **Current**: [Integrated Backtest Refactor (Nov 2025)](INTEGRATED_BACKTEST_REFACTOR_NOV_2025.md)
- [Data Flow: trade_agent.py --backtest](DATA_FLOW_BACKTEST.md)
- [Backtest README](backtest/README.md)

#### Kotak Neo Auto Trader
- [Auto Trader Logic](KOTAK_NEO_AUTO_TRADER_LOGIC.md)
- [Re-entry Logic Details](KOTAK_NEO_REENTRY_LOGIC_DETAILS.md)
- [Parallel Monitoring](kotak_neo_trader/PARALLEL_MONITORING.md)

#### Analysis & Scoring
- [Verdict Calculation Explanation](VERDICT_CALCULATION_EXPLANATION.md)
- [Chart Quality & Capital Adjustment](features/CHART_QUALITY_AND_CAPITAL_ADJUSTMENT.md)
- [ML Integration Guide](ML_IMPLEMENTATION_GUIDE.md)

### Features & Bug Fixes
- [Features Overview](features/)
- [Bug Fixes](features/BUG_FIXES.md)
- [Recent Changes (Nov 9, 2025)](CHANGES_2025_11_09_CONSOLIDATED.md)

### Testing
- [Testing Rules](testing/TESTING_RULES.md)
- [Test Organization](testing/)

### Deployment
- [Windows Deployment](deployment/windows/)
- [Ubuntu Deployment](deployment/ubuntu/)
- [Health Checks](deployment/HEALTH_CHECK.md)

## Key Concepts

### Backtest System
- **Single-Pass Daily Iteration**: Checks RSI every trading day
- **Trade Agent Validation**: Only for initial entries (re-entries are technical)
- **Exit Conditions**: High >= Target OR RSI > 50
- **Re-Entry Logic**: No EMA200 check (committed pyramiding strategy)
- **Signal Numbering**: All signals numbered for easy tracking

### Position Management
- **Initial Entry**: RSI < 30 AND Close > EMA200
- **Re-Entries**: RSI levels (30, 20, 10) with reset cycles
- **Level Marking**: All passed levels marked on initial entry
- **Daily Cap**: Max 1 re-entry per symbol per day
- **Target**: EMA9 at entry/re-entry date (fixed, not dynamic)

### Trade Agent
- **Multi-Timeframe Analysis**: Daily + Weekly alignment
- **Chart Quality Assessment**: Filters low-quality setups
- **News Sentiment**: Integrated for context
- **Historical Validation**: Backtest scoring integration

## Recent Improvements (November 2025)

1. ✅ **Fixed Exit Bug**: Positions now exit when conditions met (was staying open indefinitely)
2. ✅ **Fixed Level Marking**: All passed RSI levels marked on initial entry
3. ✅ **Fixed Logging**: Consistent execution dates throughout
4. ✅ **Added Signal Numbering**: Easy tracking of all signals
5. ✅ **Eliminated Redundancy**: Single-pass iteration (more efficient)
6. ✅ **Improved Accuracy**: Lower but correct returns reflecting proper trade management
7. ✅ **Documented Re-Entry Logic**: Clarified why EMA200 not checked for re-entries
8. ✅ **Thread-Safe**: Confirmed safe for parallel execution

## Performance Comparison

### Before Fixes (Buggy)
- RELIANCE.NS: +20.43% return, 18 trades (inflated by exit bug)
- Positions held 840 days when should exit in 4 days

### After Fixes (Accurate)
- RELIANCE.NS: +2.13% return, 10 trades (correct)
- Positions exit when target hit or RSI > 50

## Contact & Support

For questions or issues, refer to the specific documentation for each component.

---

**Last Updated**: November 10, 2025  
**Major Version**: v2.1 with Integrated Backtest Refactor
