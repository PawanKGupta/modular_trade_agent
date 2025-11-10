# Chart Quality Filtering - Usage Guide

## Overview

Chart quality filtering is a **REQUIRED** feature in the live trading system that filters out stocks with poor chart patterns (gaps, no movement, extreme candles). This helps avoid bad trades and improves overall strategy performance.

## Important: Chart Quality is REQUIRED

### ⚠️ CRITICAL: Chart Quality Must Be ENABLED in Production

- **Chart quality filtering is ENABLED by default**
- **DO NOT disable chart quality in live trading**
- **Chart quality helps avoid bad charts and improves trade quality**
- **Disabling chart quality is ONLY for testing/data collection purposes**

---

## Configuration

### Default Settings (Production)

```python
# config/strategy_config.py
chart_quality_enabled: bool = True  # REQUIRED in production
chart_quality_enabled_in_backtest: bool = True  # Default: enabled
chart_quality_min_score: float = 60.0  # Minimum score for acceptance (0-100)
```

### Environment Variables

```bash
# Chart Quality Settings (Production)
CHART_QUALITY_ENABLED=true  # REQUIRED - DO NOT set to false in production
CHART_QUALITY_ENABLED_IN_BACKTEST=true  # Default: enabled
CHART_QUALITY_MIN_SCORE=60.0  # Minimum score for acceptance
CHART_QUALITY_MAX_GAP_FREQUENCY=20.0  # Max gap frequency (%)
CHART_QUALITY_MIN_DAILY_RANGE_PCT=1.5  # Min daily range (%)
CHART_QUALITY_MAX_EXTREME_CANDLE_FREQUENCY=15.0  # Max extreme candle frequency (%)
```

---

## Usage in Live Trading

### Standard Usage (Recommended)

Chart quality filtering is **automatically enabled** in:
- `trade_agent.py` - Main trading agent
- `AnalysisService` - Stock analysis service
- `VerdictService` - Verdict determination
- `AutoTradeEngine` - Live trading engine

**No action required** - chart quality is enabled by default.

### Verification

To verify chart quality is enabled:

```python
from config.strategy_config import StrategyConfig

config = StrategyConfig.default()
print(f"Chart quality enabled: {config.chart_quality_enabled}")
print(f"Chart quality enabled in backtest: {config.chart_quality_enabled_in_backtest}")
```

**Expected output:**
```
Chart quality enabled: True
Chart quality enabled in backtest: True
```

---

## Usage for Data Collection (Testing Only)

### When to Disable Chart Quality

Chart quality filtering can be **temporarily disabled** for:
- **ML training data collection** - To get more training examples
- **Backtesting analysis** - To analyze all stocks, not just clean charts
- **Testing purposes** - To test strategy without chart quality filters

### ⚠️ WARNING: Testing Only

**DO NOT disable chart quality in production!**

Chart quality filtering is required to:
- Avoid stocks with too many gaps
- Avoid stocks with no movement
- Avoid stocks with extreme candles
- Improve overall trade quality

### How to Disable (Testing Only)

#### Option 1: Command Line Flag (Recommended)

```bash
# For data collection only
python scripts/collect_ml_training_data_full.py \
    --max-stocks 500 \
    --years-back 10 \
    --disable-chart-quality  # ⚠️ TESTING ONLY

# For backtest analysis
python scripts/bulk_backtest_all_stocks.py \
    --max-stocks 200 \
    --disable-chart-quality  # ⚠️ TESTING ONLY
```

#### Option 2: Environment Variable (Temporary)

```bash
# ⚠️ TESTING ONLY - DO NOT use in production
export CHART_QUALITY_ENABLED_IN_BACKTEST=false

# Run data collection
python scripts/collect_ml_training_data_full.py --max-stocks 500

# Restore default (IMPORTANT!)
export CHART_QUALITY_ENABLED_IN_BACKTEST=true
```

#### Option 3: Code Configuration (Temporary)

```python
from config.strategy_config import StrategyConfig

# ⚠️ TESTING ONLY - DO NOT use in production
config = StrategyConfig.default()
config.chart_quality_enabled_in_backtest = False  # Only for testing

# Run backtest with disabled chart quality
# ... your testing code ...

# Restore default (IMPORTANT!)
config.chart_quality_enabled_in_backtest = True
```

---

## Impact of Disabling Chart Quality

### With Chart Quality Enabled (Production)

- **Filters out bad charts** (gaps, no movement, extreme candles)
- **Higher quality trades** (cleaner charts)
- **Better trade success rate** (fewer false signals)
- **Lower number of trades** (more selective)

### With Chart Quality Disabled (Testing Only)

- **Includes all stocks** (even with poor charts)
- **More training examples** (for ML model training)
- **More backtest data** (for analysis)
- **Lower trade quality** (includes bad charts)
- **Higher number of trades** (less selective)

### Example Impact

| Scenario | Stocks Processed | Trades Generated | Trade Quality |
|----------|-----------------|------------------|---------------|
| **Chart Quality Enabled** (Production) | 200 | 62 | High (clean charts) |
| **Chart Quality Disabled** (Testing) | 200 | 200+ | Mixed (includes bad charts) |

---

## Best Practices

### For Production

1. ✅ **Always enable chart quality** in live trading
2. ✅ **Use default settings** (chart_quality_enabled = True)
3. ✅ **Verify chart quality is enabled** before deploying
4. ✅ **Monitor chart quality metrics** in production

### For Data Collection

1. ✅ **Disable chart quality only for data collection**
2. ✅ **Re-enable chart quality after data collection**
3. ✅ **Use `--disable-chart-quality` flag** (not environment variables)
4. ✅ **Document when/why chart quality was disabled**

### For Testing

1. ✅ **Disable chart quality only for specific tests**
2. ✅ **Restore chart quality after testing**
3. ✅ **Never disable in production code**
4. ✅ **Add warnings when chart quality is disabled**

---

## Troubleshooting

### Chart Quality Not Working

**Symptom:** Chart quality filtering not working in live trading

**Solution:**
1. Check `config/strategy_config.py`: `chart_quality_enabled = True`
2. Check environment variables: `CHART_QUALITY_ENABLED=true`
3. Verify `ChartQualityService` is being used in `AnalysisService`
4. Check logs for chart quality assessment results

### Too Many Stocks Filtered

**Symptom:** Too many stocks filtered out by chart quality

**Solution:**
1. Check chart quality thresholds (may be too strict)
2. Adjust `chart_quality_min_score` (default: 60.0)
3. Adjust `chart_quality_max_gap_frequency` (default: 20.0)
4. Review filtered stocks to understand why they were filtered

### Chart Quality Disabled in Production

**Symptom:** Chart quality is disabled in production (unintentionally)

**Solution:**
1. **IMMEDIATELY re-enable chart quality**
2. Check environment variables: `CHART_QUALITY_ENABLED=true`
3. Check code: `config.chart_quality_enabled = True`
4. Verify no `--disable-chart-quality` flags in production scripts
5. Review logs to identify when/why it was disabled

---

## Summary

### Key Points

1. ✅ **Chart quality is REQUIRED in production**
2. ✅ **Chart quality is ENABLED by default**
3. ✅ **Disable chart quality ONLY for testing/data collection**
4. ✅ **Always re-enable chart quality after testing**
5. ✅ **Never disable chart quality in production**

### Quick Reference

| Scenario | Chart Quality | Command |
|----------|---------------|---------|
| **Live Trading** | ✅ Enabled (Required) | `python trade_agent.py` |
| **Data Collection** | ⚠️ Disabled (Testing) | `--disable-chart-quality` |
| **Backtesting** | ✅ Enabled (Default) | `python trade_agent.py --backtest` |
| **ML Training** | ⚠️ Disabled (Testing) | `--disable-chart-quality` |

---

## Related Documentation

- [Chart Quality & Capital Adjustment Features](../features/CHART_QUALITY_AND_CAPITAL_ADJUSTMENT.md)
- [Configuration Settings](../../new_documentation/configuration/SETTINGS.md)
- [Backtest Investigation Results](../../BACKTEST_INVESTIGATION_RESULTS.md)




