# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
