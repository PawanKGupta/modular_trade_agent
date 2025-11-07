# Changelog: Chart Quality & Capital Adjustment Features

## Version 1.0.0 - 2025-11-08

### 🆕 New Features

#### Chart Quality Filtering
- **Chart Quality Service**: New service to analyze chart patterns and filter poor-quality charts
- **Gap Analysis**: Detects gap up/gap down frequency to identify irregular trading patterns
- **Movement Analysis**: Detects flat/choppy charts with no meaningful movement
- **Extreme Candle Analysis**: Detects big red/green candles indicating erratic price action
- **Chart Cleanliness Score**: Overall score (0-100) based on gap frequency, movement, and extreme candles
- **Hard Filter**: Stocks with score < 60 are immediately marked "avoid"
- **Configurable Thresholds**: All thresholds configurable via environment variables

#### Dynamic Capital Adjustment
- **Liquidity Capital Service**: New service to calculate execution capital based on stock liquidity
- **Maximum Capital Calculation**: Calculates max capital from liquidity (10% of daily volume default)
- **Execution Capital Calculation**: Uses min(user_capital, max_capital) for safe position sizing
- **Automatic Adjustment**: Automatically reduces capital when liquidity is low
- **Position Size Calculation**: Calculates exact number of shares based on execution capital
- **Capital Safety Checks**: Validates capital is safe for stock liquidity

### 🔧 Improvements

#### Analysis Pipeline
- **Early Chart Quality Check**: Chart quality checked early to save processing
- **Chart Quality in Scoring**: Cleaner charts receive bonus points (+1 to +3)
- **Chart Quality in Filtering**: Chart quality respected in candidate filtering
- **Capital in Volume Analysis**: Execution capital calculated during volume analysis

#### Backtesting
- **Chart Quality Filtering**: Filters stocks before backtest runs
- **Dynamic Capital**: Uses execution capital per trade based on historical liquidity
- **Weighted Returns**: Calculates returns based on capital-weighted ROI
- **Chart Quality in Results**: Includes chart quality data in backtest results

#### Trade Execution
- **Execution Capital from CSV**: Auto trader uses execution_capital from analysis CSV
- **Position Sizing**: Calculates quantity from execution capital
- **Retry Logic**: Preserves execution_capital for failed orders
- **Re-entry Logic**: Calculates execution_capital for re-entries

#### Export & Notifications
- **CSV Export**: Includes new fields:
  - `execution_capital`, `max_capital`, `capital_adjusted`
  - `chart_quality_score`, `chart_quality_status`, `chart_quality_passed`, `chart_quality_reason`
- **Telegram Alerts**: Includes capital and chart quality information

### 📊 Configuration Changes

#### New Environment Variables
```env
# Chart Quality
CHART_QUALITY_ENABLED=true
CHART_QUALITY_MIN_SCORE=60.0
CHART_QUALITY_MAX_GAP_FREQUENCY=20.0
CHART_QUALITY_MIN_DAILY_RANGE_PCT=1.5
CHART_QUALITY_MAX_EXTREME_CANDLE_FREQUENCY=15.0
CHART_QUALITY_ENABLED_IN_BACKTEST=true

# Capital & Liquidity
USER_CAPITAL=200000.0
MAX_POSITION_VOLUME_RATIO=0.10
MIN_ABSOLUTE_AVG_VOLUME=20000  # Lowered from 150000
```

#### Updated Settings
- **MIN_ABSOLUTE_AVG_VOLUME**: Lowered from 150000 to 20000 (minimal safety net)
- **StrategyConfig**: Added chart quality and capital configuration fields

### 🧪 Testing

#### Unit Tests
- **Chart Quality Service**: 92% coverage (24 tests)
- **Liquidity Capital Service**: 91% coverage (45 tests)
- **Total**: 69/69 tests passing
- **Coverage**: >90% for both services ✅

#### Integration Tests
- **Total**: 5/5 tests passing
- **Coverage**: All integration points tested ✅

### 📁 New Files
- `services/chart_quality_service.py` - Chart quality analysis
- `services/liquidity_capital_service.py` - Capital calculation
- `scripts/test_phases_complete.py` - Comprehensive test suite
- `tests/unit/services/test_chart_quality_service.py` - Unit tests for chart quality
- `tests/unit/services/test_liquidity_capital_service.py` - Unit tests for capital service
- `documents/features/CHART_QUALITY_AND_CAPITAL_ADJUSTMENT.md` - Feature documentation

### 📝 Modified Files
- `config/strategy_config.py` - Added chart quality and capital settings
- `config/settings.py` - Updated MIN_ABSOLUTE_AVG_VOLUME default
- `services/verdict_service.py` - Added chart quality hard filter
- `services/analysis_service.py` - Integrated chart quality and capital
- `services/scoring_service.py` - Added chart quality to scoring
- `services/filtering_service.py` - Respects chart quality
- `core/backtest_scoring.py` - Chart quality and dynamic capital
- `backtest/backtest_engine.py` - Chart quality filtering
- `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Uses execution_capital
- `core/csv_exporter.py` - Exports new fields
- `trade_agent.py` - Telegram notifications with new fields
- `src/application/dto/analysis_response.py` - Added new fields
- `src/application/use_cases/analyze_stock.py` - Includes new fields
- `core/volume_analysis.py` - Updated liquidity filter

### 📚 Documentation Updates
- **README.md**: Added new features section
- **SETTINGS.md**: Added configuration documentation
- **IMPLEMENTATION_SUMMARY.md**: Updated with test results
- **DOCUMENTATION_INDEX.md**: Added new features documentation link
- **CHART_QUALITY_AND_CAPITAL_ADJUSTMENT.md**: Complete feature documentation

### 🔄 Migration Notes

#### For Users
1. **No Breaking Changes**: Existing configurations continue to work
2. **New Defaults**: MIN_ABSOLUTE_AVG_VOLUME lowered to 20000 (was 150000)
3. **Optional Configuration**: Chart quality and capital settings have sensible defaults
4. **Backward Compatible**: Old analysis CSVs without new fields still work

#### For Developers
1. **New Services**: ChartQualityService and LiquidityCapitalService
2. **New Dependencies**: Services injected into VerdictService and AnalysisService
3. **New Fields**: Analysis results include chart_quality and execution_capital
4. **Test Coverage**: >90% coverage for both new services

### 🐛 Bug Fixes
- Fixed liquidity filtering to use minimal safety net instead of hard filter
- Fixed capital calculation to respect liquidity limits
- Fixed chart quality analysis to handle both yfinance and standard column formats

### ⚠️ Known Issues
- Gap detection may detect weekend/holiday gaps (expected behavior)
- Chart quality thresholds may need tuning based on market conditions
- Capital adjustment logging may be verbose for low-liquidity stocks

### 🎯 Future Improvements
1. Fine-tune gap detection to account for weekends/holidays more accurately
2. Add category-specific thresholds (large-cap vs small-cap)
3. Monitor capital adjustments in production
4. Gather feedback on chart quality filtering effectiveness

---

## Summary

This release adds comprehensive chart quality filtering and dynamic capital adjustment features to improve trade selection and position sizing. All features are fully tested (>90% coverage) and ready for production use.

