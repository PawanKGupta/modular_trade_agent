# ML Training Data Collection (Unfiltered/Minimal Filters)

**Version**: 1.0
**Last Updated**: 2025-11-12
**Status**: ✅ Complete

---

## Overview

This document describes the new script `scripts/collect_training_data_unfiltered.py` that collects ML training data using **minimal filters** to avoid selection bias.

### Purpose

- Collect unbiased training data for ML model
- Let ML learn which dips bounce to EMA9 regardless of gaps/volatility
- As ML improves, gradually remove filters

---

## Filters Applied

### ✅ KEPT (Essential Filters)

1. **RSI10 < 30** - Oversold condition (core entry signal)
2. **Price > EMA200** - Above long-term trend (core entry signal)
3. **Minimal Chart Quality** - Movement only (flat charts won't bounce)

### ❌ SKIPPED (For Training Data)

1. **Trade Agent Validation** - No verdict filtering
2. **Volume Filters** - Let ML learn from volume patterns
3. **Fundamental Filters** - Let ML learn from fundamentals
4. **Gap Analysis** - Gaps don't prevent bounces
5. **Extreme Candle Analysis** - Volatility can help bounces

---

## Minimal Chart Quality Mode

The script uses `ChartQualityService` with `minimal_mode=True`:

- **Checks**: Movement only (flat charts won't bounce)
- **Skips**: Gap analysis, extreme candle analysis

### Why Minimal Mode?

- **Gaps**: Stocks with gaps can still bounce to EMA9 (gaps don't prevent mean reversion)
- **Extreme Candles**: Volatile stocks might bounce MORE (volatility = opportunity)
- **Flat Movement**: Flat charts won't bounce (makes sense to filter)

---

## Usage

### Basic Usage

```bash
python scripts/collect_training_data_unfiltered.py \
    --stocks-file data/all_nse_stocks.txt \
    --output data/ml_training_data_unfiltered.csv \
    --years-back 10
```

### Options

```bash
--stocks-file, -f    File with list of NSE stocks (default: data/all_nse_stocks.txt)
--output, -o         Output CSV file (default: auto-generated with timestamp)
--years-back, -y     Years of historical data (default: 10)
--max-stocks, -m     Maximum number of stocks to process (for testing)
--max-workers, -w    Maximum concurrent workers (default: from settings)
```

### Example: Quick Test

```bash
python scripts/collect_training_data_unfiltered.py \
    --stocks-file data/all_nse_stocks.txt \
    --output data/ml_training_test.csv \
    --years-back 2 \
    --max-stocks 10
```

---

## How It Works

### Step 1: Run Backtests with Minimal Filters

1. Load stocks from file
2. For each stock:
   - Check minimal chart quality (movement only)
   - Run integrated backtest with `skip_trade_agent_validation=True`
   - Collect backtest results

### Step 2: Extract Features and Labels

1. For each backtest result:
   - Extract features at each entry date (using signal date to avoid look-ahead bias)
   - Create labels based on P&L:
     - `strong_buy`: P&L >= 10%
     - `buy`: P&L >= 5%
     - `watch`: P&L >= 0%
     - `avoid`: P&L < 0%
   - Include re-entry fills (each fill gets its own training example)

### Step 3: Save Training Data

- Save final CSV with all features and labels
- Save intermediate backtest results CSV for debugging

---

## Output Format

The script generates two files:

1. **`*_backtest_results.csv`** - Intermediate backtest results
2. **`*_training_data.csv`** - Final training data with features and labels

### Training Data Columns

- All features from `extract_features_at_date()`:
  - RSI, price, EMA200, EMA9
  - Dip features (depth, speed, support distance, etc.)
  - Market regime features (Nifty trend, VIX, sector strength)
  - Time-based features (day of week, month, quarter)
  - Feature interactions (RSI×Volume, Dip×Support, etc.)
  - Re-entry context (is_reentry, fill_number, etc.)
- Label: `strong_buy`, `buy`, `watch`, or `avoid`
- P&L metrics: `pnl_pct`, `holding_days`, `max_drawdown_pct`

---

## Comparison with Filtered Approach

### Old Approach (Filtered)

```
Filters: RSI<30, Price>EMA200, Chart Quality (full), Trade Agent, Volume, Fundamentals
Result: Only "clean" stocks with "buy/strong_buy" verdicts
Problem: Selection bias - ML only sees filtered stocks
```

### New Approach (Minimal Filters)

```
Filters: RSI<30, Price>EMA200, Chart Quality (movement only)
Result: All stocks that meet basic conditions
Benefit: ML learns bounce patterns regardless of gaps/volatility
```

---

## Future: Gradual Filter Removal

As ML improves, you can gradually remove filters:

1. **Phase 1** (Current): Minimal chart quality (movement only)
2. **Phase 2**: Remove chart quality entirely (let ML learn from all charts)
3. **Phase 3**: Remove rule-based filters (let ML learn from all RSI<30 stocks)

This allows ML to become the primary filter, replacing rule-based logic.

---

## Technical Details

### Chart Quality Minimal Mode

```python
chart_quality_service = ChartQualityService(config=config, minimal_mode=True)
```

- `minimal_mode=True`: Only checks movement (flat charts)
- `minimal_mode=False`: Checks gaps, movement, extreme candles (full mode)

### Integrated Backtest Skip Validation

```python
backtest_result = run_integrated_backtest(
    stock_name=ticker,
    date_range=date_range,
    capital_per_position=50000,
    skip_trade_agent_validation=True  # Skip trade agent for training data
)
```

- `skip_trade_agent_validation=True`: Executes all RSI<30 & price>EMA200 signals
- `skip_trade_agent_validation=False`: Validates with trade agent (normal mode)

---

## Troubleshooting

### No Training Data Collected

- Check if stocks meet minimal filters (RSI<30, price>EMA200, movement)
- Check intermediate backtest results CSV
- Verify data availability for stocks

### Low Number of Examples

- Increase `--years-back` (more historical data)
- Process more stocks (remove `--max-stocks` limit)
- Check if minimal chart quality is too strict

### Memory Issues

- Reduce `--max-workers` (fewer concurrent processes)
- Process stocks in batches using `--max-stocks`

---

## Related Documents

- `documents/ML_TRAINING_DATA_GUIDE.md` - General ML training data guide
- `documents/ML_TRAINING_DATA_IMPROVEMENTS.md` - Training data improvements
- `documents/ML_MODEL_RETRAINING_GUIDE_ENHANCED.md` - Model retraining guide

---

## Summary

The `collect_training_data_unfiltered.py` script collects ML training data with minimal filters to avoid selection bias. It uses:

- ✅ RSI<30 & Price>EMA200 (core entry signals)
- ✅ Minimal chart quality (movement only)
- ❌ No trade agent validation
- ❌ No volume/fundamental filters
- ❌ No gap/extreme candle analysis

This allows ML to learn bounce patterns from a wider variety of stocks, improving its ability to predict which dips will bounce to EMA9.
