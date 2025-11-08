# Chart Quality & Capital Adjustment Features

**Version**: 1.0  
**Last Updated**: 2025-11-08  
**Status**: ✅ Complete

---

## Overview

This document describes the chart quality filtering and dynamic capital adjustment features that were added to improve trade selection and position sizing.

---

## 🎯 Chart Quality Filtering

### Purpose
Automatically filters out stocks with poor chart patterns to improve trade quality and reduce false signals.

### ⚠️ IMPORTANT: Chart Quality is REQUIRED in Production

**Chart quality filtering is ENABLED by default and is REQUIRED in the live trading system.**

- ✅ **Enabled by default** in all live trading operations
- ✅ **Hard filter** - stocks with poor chart quality are immediately rejected
- ✅ **Required for production** - DO NOT disable in live trading
- ⚠️ **Can be disabled for testing/data collection ONLY** - Use `--disable-chart-quality` flag

### Features

#### 1. Gap Analysis
- **Detects**: Gap up and gap down patterns
- **Metric**: Gap frequency (% of days with gaps)
- **Threshold**: Default 20% max gap frequency
- **Why**: Stocks with too many gaps indicate irregular trading patterns

#### 2. Movement Analysis
- **Detects**: Flat/choppy charts with no movement
- **Metric**: Average daily range percentage
- **Threshold**: Default 1.5% min daily range
- **Why**: Stocks with no movement are hard to trade profitably

#### 3. Extreme Candle Analysis
- **Detects**: Big red/green candles (extreme price moves)
- **Metric**: Extreme candle frequency (% of days)
- **Threshold**: Default 15% max extreme candle frequency
- **Why**: Extreme candles indicate erratic price action

#### 4. Chart Cleanliness Score
- **Range**: 0-100 (higher is better)
- **Calculation**: Based on gap frequency, movement, and extreme candles
- **Threshold**: Default 60 minimum score for acceptance
- **Status Levels**:
  - `clean`: Score >= 80
  - `acceptable`: Score >= 60
  - `poor`: Score < 60

### Configuration

```bash
# Chart Quality Settings (Production)
# ⚠️ IMPORTANT: Chart quality is REQUIRED in production - DO NOT disable
CHART_QUALITY_ENABLED=true  # REQUIRED - DO NOT set to false in production
CHART_QUALITY_MIN_SCORE=60.0
CHART_QUALITY_MAX_GAP_FREQUENCY=20.0
CHART_QUALITY_MIN_DAILY_RANGE_PCT=1.5
CHART_QUALITY_MAX_EXTREME_CANDLE_FREQUENCY=15.0
CHART_QUALITY_ENABLED_IN_BACKTEST=true  # Default: enabled (can be disabled for data collection)
```

**⚠️ Warning**: Setting `CHART_QUALITY_ENABLED=false` or `CHART_QUALITY_ENABLED_IN_BACKTEST=false` will disable chart quality filtering, which is **NOT recommended for production**. Only disable for testing/data collection purposes using the `--disable-chart-quality` flag.

### Usage

```python
from services.chart_quality_service import ChartQualityService
import pandas as pd

service = ChartQualityService()
df = pd.DataFrame(...)  # OHLC data

# Check if chart is acceptable
is_acceptable = service.is_chart_acceptable(df)

# Get detailed analysis
result = service.assess_chart_quality(df)
print(f"Score: {result['score']}/100")
print(f"Status: {result['status']}")
print(f"Passed: {result['passed']}")
```

### Integration
- **Hard Filter**: Stocks with poor chart quality are immediately marked "avoid"
- **Early Check**: Chart quality is checked early in the analysis pipeline to save processing
- **Backtesting**: Chart quality filtering can be enabled/disabled in backtests
- **Scoring**: Cleaner charts receive bonus points in scoring (+1 to +3 points)

---

## 💰 Dynamic Capital Adjustment

### Purpose
Automatically adjusts position size based on stock liquidity to ensure safe position sizing and prevent over-trading illiquid stocks.

### Features

#### 1. Maximum Capital Calculation
- **Formula**: `max_capital = avg_volume * stock_price * max_position_volume_ratio`
- **Default Ratio**: 10% of daily volume
- **Why**: Limits position size to a safe percentage of daily trading volume

#### 2. Execution Capital Calculation
- **Formula**: `execution_capital = min(user_capital, max_capital)`
- **Default User Capital**: ₹200,000 (2L)
- **Auto-Adjustment**: Automatically reduces capital if liquidity is low
- **Why**: Ensures position size doesn't exceed safe liquidity limits

#### 3. Position Size Calculation
- **Formula**: `quantity = floor(execution_capital / stock_price)`
- **Safety**: Ensures quantity doesn't exceed capital available
- **Why**: Calculates exact number of shares to buy

### Configuration

```bash
# Capital & Liquidity Settings
USER_CAPITAL=200000.0
MAX_POSITION_VOLUME_RATIO=0.10
MIN_ABSOLUTE_AVG_VOLUME=20000
```

### Usage

```python
from services.liquidity_capital_service import LiquidityCapitalService

service = LiquidityCapitalService()

# Calculate execution capital
result = service.calculate_execution_capital(
    avg_volume=1000000,  # Average daily volume
    stock_price=500      # Current stock price
)

print(f"Execution Capital: ₹{result['execution_capital']:,.0f}")
print(f"Max Capital: ₹{result['max_capital']:,.0f}")
print(f"Capital Adjusted: {result['capital_adjusted']}")
```

### Integration
- **Live Trading**: Auto trader uses `execution_capital` from analysis CSV
- **Backtesting**: Uses execution capital per trade based on historical liquidity
- **CSV Export**: Includes execution capital, max capital, and adjustment flag
- **Telegram Alerts**: Includes capital information in trade alerts

---

## 🔧 Service Architecture

### ChartQualityService
- **File**: `services/chart_quality_service.py`
- **Methods**:
  - `analyze_gaps()`: Analyzes gap patterns
  - `analyze_movement()`: Analyzes chart movement
  - `analyze_extreme_candles()`: Analyzes extreme candles
  - `calculate_chart_cleanliness_score()`: Calculates overall score
  - `assess_chart_quality()`: Main entry point
  - `is_chart_acceptable()`: Hard filter check

### LiquidityCapitalService
- **File**: `services/liquidity_capital_service.py`
- **Methods**:
  - `calculate_max_capital()`: Calculates max capital from liquidity
  - `calculate_execution_capital()`: Calculates execution capital
  - `is_capital_safe()`: Checks if capital is safe
  - `calculate_position_size()`: Calculates position size

---

## 📊 Integration Points

### Analysis Pipeline
1. **Early Check**: Chart quality checked early to save processing
2. **Hard Filter**: Poor chart quality → "avoid" verdict
3. **Capital Calculation**: Execution capital calculated during volume analysis
4. **Scoring**: Chart quality included in scoring (+1 to +3 points)

### Backtesting
1. **Chart Quality Filter**: Filters stocks before backtest runs
2. **Dynamic Capital**: Uses execution capital per trade
3. **Weighted Returns**: Calculates returns based on capital-weighted ROI
4. **Results**: Includes chart quality and capital data

### Trade Execution
1. **CSV Import**: Reads `execution_capital` from analysis CSV
2. **Position Sizing**: Calculates quantity from execution capital
3. **Retry Logic**: Preserves execution capital for failed orders
4. **Re-entry Logic**: Calculates execution capital for re-entries

### Export & Notifications
1. **CSV Export**: Includes all new fields
2. **Telegram Alerts**: Includes capital and chart quality info

---

## 📈 Examples

### Example 1: High Liquidity Stock
```
Stock: RELIANCE.NS
Avg Volume: 5,000,000
Stock Price: ₹2,500
User Capital: ₹200,000

Max Capital: 5,000,000 * 2,500 * 0.10 = ₹1,250,000,000
Execution Capital: min(200,000, 1,250,000,000) = ₹200,000
Capital Adjusted: No (using full user capital)
```

### Example 2: Low Liquidity Stock
```
Stock: SMALLSTOCK.NS
Avg Volume: 50,000
Stock Price: ₹500
User Capital: ₹200,000

Max Capital: 50,000 * 500 * 0.10 = ₹2,500,000
Execution Capital: min(200,000, 2,500,000) = ₹200,000
Capital Adjusted: No (liquidity allows full capital)
```

### Example 3: Very Low Liquidity Stock
```
Stock: TINYSTOCK.NS
Avg Volume: 10,000
Stock Price: ₹100
User Capital: ₹200,000

Max Capital: 10,000 * 100 * 0.10 = ₹100,000
Execution Capital: min(200,000, 100,000) = ₹100,000
Capital Adjusted: Yes (reduced due to liquidity)
```

---

## 🧪 Testing

### Unit Tests
- **Coverage**: >90% for both services
- **Test Files**:
  - `tests/unit/services/test_chart_quality_service.py` (24 tests)
  - `tests/unit/services/test_liquidity_capital_service.py` (45 tests)

### Integration Tests
- **Test File**: `scripts/test_phases_complete.py`
- **Coverage**: All integration points tested
- **Results**: 5/5 tests passed

---

## 📝 Configuration Reference

### Environment Variables
See [SETTINGS.md](../../new_documentation/configuration/SETTINGS.md) for complete configuration reference.

### StrategyConfig
All settings are available in `StrategyConfig` with defaults:
- `chart_quality_enabled: bool = True`
- `chart_quality_min_score: float = 60.0`
- `user_capital: float = 200000.0`
- `max_position_volume_ratio: float = 0.10`

---

## 🔍 Troubleshooting

### Chart Quality Issues
- **Too many stocks filtered**: Lower `CHART_QUALITY_MIN_SCORE` or adjust thresholds
- **Gap detection issues**: May detect weekend/holiday gaps (expected behavior)
- **False positives**: Adjust `CHART_QUALITY_MAX_GAP_FREQUENCY` if needed

### Capital Adjustment Issues
- **Capital too low**: Increase `USER_CAPITAL` or check stock liquidity
- **Capital not adjusting**: Check if `MAX_POSITION_VOLUME_RATIO` is appropriate
- **Position size too small**: Verify stock liquidity and price

---

## 📚 Related Documentation
- [IMPLEMENTATION_SUMMARY.md](../../IMPLEMENTATION_SUMMARY.md) - Complete implementation summary
- [SETTINGS.md](../../new_documentation/configuration/SETTINGS.md) - Configuration reference
- [README.md](../../README.md) - Main project documentation

---

## ✅ Status

**Implementation Status**: ✅ Complete
- Chart Quality Service: ✅ Complete
- Liquidity Capital Service: ✅ Complete
- Analysis Integration: ✅ Complete
- Backtesting Integration: ✅ Complete
- Trade Execution Integration: ✅ Complete
- Export & Notifications: ✅ Complete
- Unit Tests: ✅ >90% coverage
- Integration Tests: ✅ All passing

**Ready for Production**: ✅ Yes

