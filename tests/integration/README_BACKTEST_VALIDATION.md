# Backtest Verdict Validation Test

## Overview

This test script performs a comprehensive 5-year backtest and validates:
1. **Verdict Calculations**: Verifies that all verdicts are calculated correctly for each signal
2. **Trade Execution**: Validates that trades are executed perfectly on each signal

## What It Tests

### Verdict Calculation Validation

For each signal, the test validates:

1. **RSI Value Consistency**: Verifies that RSI values match between signal and analysis
2. **EMA200 Position Consistency**: Checks that EMA200 position (above/below) is consistent
3. **Chart Quality Check**: Validates that chart quality filter is applied correctly
4. **RSI Threshold Validation**: 
   - Above EMA200: RSI < 30 required for buy verdict
   - Below EMA200: RSI < 20 required for buy verdict
5. **Volume Check**: Verifies volume requirements are met for buy verdicts
6. **Fundamental Check**: Validates fundamental filters are applied
7. **Verdict Logic Validation**: Recalculates expected verdict and compares with actual
8. **Trading Parameters Validation**: Validates buy_range, target, and stop loss are calculated correctly

### Trade Execution Validation

For each executed trade, the test validates:

1. **Execution Date**: Verifies execution is on next trading day after signal
2. **Entry Price**: Validates entry price matches execution price (next day's open)
3. **Market Data Consistency**: Checks entry price matches market data
4. **Target Price**: Validates target price is set and greater than entry price
5. **Position Size**: Verifies position size matches capital allocation

## Usage

### As a Standalone Script

```bash
# Run with default settings (RELIANCE.NS, 5 years)
python tests/integration/test_backtest_verdict_validation.py

# Run with custom stock and period
python tests/integration/test_backtest_verdict_validation.py --symbol TCS.NS --years 3

# Run with custom capital
python tests/integration/test_backtest_verdict_validation.py --symbol RELIANCE.NS --capital 200000
```

### As a Pytest Test

```bash
# Run the test
pytest tests/integration/test_backtest_verdict_validation.py -v

# Run with specific stock
pytest tests/integration/test_backtest_verdict_validation.py::test_backtest_validation -v -k "RELIANCE"
```

## Command Line Arguments

- `--symbol`: Stock symbol to test (default: RELIANCE.NS)
- `--years`: Number of years to backtest (default: 5)
- `--capital`: Capital per position in rupees (default: 100000)

## Output

The test generates a comprehensive report including:

1. **Signal Analysis**: List of all signals found during backtest
2. **Verdict Validations**: Results of verdict calculation validation for each signal
3. **Trade Execution Validations**: Results of trade execution validation for each trade
4. **Summary Statistics**:
   - Total signals found
   - Verdict validation pass/fail counts
   - Trade execution validation pass/fail counts
   - Verdict distribution (strong_buy/buy/watch/avoid)
   - All errors and warnings

## Example Output

```
================================================================================
COMPREHENSIVE BACKTEST VALIDATION
================================================================================
Stock: RELIANCE.NS
Period: 5 years
Capital per position: ₹100,000
================================================================================

📊 Step 1: Running backtest to identify signals...
✅ Found 15 potential signals

📈 Step 2: Running integrated backtest to get trade execution data...
🚀 Starting Integrated Backtest for RELIANCE.NS
...

🔍 Step 3: Validating verdict calculations and trade executions...
  Signal 1/15: 2020-03-15
    Reason: Initial entry: RSI 28.5 < 30 (above EMA200)
    RSI: 28.50
    ✅ Verdict validation: PASSED (verdict=buy)
    ✅ Trade execution validation: PASSED
...

================================================================================
VALIDATION SUMMARY
================================================================================
Total Signals: 15

Verdict Validations:
  Total: 15
  Passed: 15
  Failed: 0
  Pass Rate: 100.0%
  Verdict Distribution: {'buy': 10, 'strong_buy': 2, 'watch': 2, 'avoid': 1}

Trade Execution Validations:
  Total: 12
  Passed: 12
  Failed: 0
  Pass Rate: 100.0%

Overall Validation: ✅ PASSED
================================================================================
```

## Expected Results

A successful validation should show:

1. **100% Verdict Validation Pass Rate**: All verdicts are calculated correctly
2. **100% Trade Execution Pass Rate**: All trades are executed correctly
3. **No Errors**: All validations pass without errors
4. **Reasonable Warnings**: Minor warnings (e.g., rounding differences) are acceptable

## Troubleshooting

### Common Issues

1. **Verdict Mismatch Errors**: 
   - Check if verdict calculation logic has changed
   - Verify RSI thresholds are correct
   - Check volume and fundamental filters

2. **Trade Execution Errors**:
   - Verify entry price matches next day's open
   - Check position size calculations
   - Validate target/stop loss calculations

3. **Market Data Issues**:
   - Ensure market data is available for the test period
   - Check data format (column names, date formats)
   - Verify data completeness

### Debugging

To debug specific issues:

1. **Enable Detailed Logging**: Set `DETAILED_LOGGING = True` in backtest config
2. **Check Individual Signals**: Review validation results for specific signals
3. **Compare with Manual Analysis**: Run manual analysis for problematic dates
4. **Review Error Messages**: Check error messages for specific validation failures

## Integration with CI/CD

This test can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Backtest Validation
  run: |
    python tests/integration/test_backtest_verdict_validation.py --symbol RELIANCE.NS --years 2
```

## Performance Considerations

- **5-year backtest**: Takes ~5-10 minutes depending on stock and system
- **3-year backtest**: Takes ~3-5 minutes
- **2-year backtest**: Takes ~2-3 minutes (recommended for CI/CD)

For faster testing, use a shorter period (2-3 years) or a single stock.

## Notes

- This test validates the **logic** of verdict calculation and trade execution
- It does not validate **performance** (returns, win rate, etc.)
- For performance validation, use the regular backtest reports
- The test uses the same logic as the production system, ensuring consistency




