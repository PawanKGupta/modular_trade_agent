# Configuration Tuning Guide

**Version:** 1.0
**Date:** 2025-11-07
**Status:** Complete

---

## Overview

This guide helps you tune the configurable indicator parameters to optimize performance for different trading strategies, market conditions, and stock characteristics.

---

## Quick Start

### Default Configuration (Short-Term Trading)

The default configuration is optimized for short-term dip-buying strategy:

```python
from config.strategy_config import StrategyConfig

config = StrategyConfig.default()
# RSI period: 10
# Support/Resistance lookback (daily): 20
# Support/Resistance lookback (weekly): 50
# Volume exhaustion lookback (daily): 10
# Volume exhaustion lookback (weekly): 20
# Data fetch daily max years: 5
# Data fetch weekly max years: 3
# Enable adaptive lookback: True
```

**Best For:**
- Short-term trading (1-5 days)
- Quick entries and exits
- High volatility stocks
- Active trading

---

## Configuration Parameters

### 1. RSI Period (`rsi_period`)

**Default:** `10`
**Range:** `5-30`
**Recommended:** `10-14`

**What it does:**
- Controls the sensitivity of RSI indicator
- Lower values = more sensitive (more signals, more noise)
- Higher values = less sensitive (fewer signals, less noise)

**Tuning Guidelines:**

| Value | Sensitivity | Use Case |
|-------|-------------|----------|
| 5-7 | Very High | Day trading, very short-term |
| 10 | High | **Short-term (default)** |
| 14 | Medium | Medium-term, less noise |
| 20-30 | Low | Long-term, swing trading |

**Example:**
```python
# More sensitive (more signals)
config = StrategyConfig(rsi_period=7)

# Less sensitive (fewer signals, less noise)
config = StrategyConfig(rsi_period=14)
```

**Impact:**
- Lower RSI period = More buy signals, higher false positives
- Higher RSI period = Fewer buy signals, better quality signals

---

### 2. Support/Resistance Lookback (Daily) (`support_resistance_lookback_daily`)

**Default:** `20`
**Range:** `10-100`
**Recommended:** `20-50`

**What it does:**
- Number of daily periods to analyze for support/resistance levels
- Longer lookback = More historical context, better levels
- Shorter lookback = More recent levels, faster adaptation

**Tuning Guidelines:**

| Value | Context | Use Case |
|-------|---------|----------|
| 10-15 | Very Recent | Fast-moving markets, quick reversals |
| 20 | Recent | **Short-term (default)** |
| 30-50 | Medium-term | Better level identification |
| 50-100 | Long-term | Swing trading, major levels |

**Example:**
```python
# More recent levels (faster adaptation)
config = StrategyConfig(support_resistance_lookback_daily=15)

# More historical context (better levels)
config = StrategyConfig(support_resistance_lookback_daily=50)
```

**Impact:**
- Longer lookback = Better support/resistance levels, more accurate stop-loss
- Shorter lookback = Faster adaptation, more responsive to recent changes

---

### 3. Support/Resistance Lookback (Weekly) (`support_resistance_lookback_weekly`)

**Default:** `50`
**Range:** `20-200`
**Recommended:** `50-100`

**What it does:**
- Number of weekly periods to analyze for support/resistance levels
- Longer lookback = Major trend levels, better for swing trading
- Shorter lookback = Recent trend levels, better for short-term

**Tuning Guidelines:**

| Value | Context | Use Case |
|-------|---------|----------|
| 20-30 | Recent | Short-term trading |
| 50 | Medium-term | **Short-term with trend context (default)** |
| 100-150 | Long-term | Swing trading, major trends |
| 150-200 | Very Long-term | Position trading, major levels |

**Example:**
```python
# Recent trend levels
config = StrategyConfig(support_resistance_lookback_weekly=30)

# Major trend levels
config = StrategyConfig(support_resistance_lookback_weekly=100)
```

**Impact:**
- Longer lookback = Better trend context, major support/resistance levels
- Shorter lookback = More responsive to recent trends

---

### 4. Volume Exhaustion Lookback (Daily) (`volume_exhaustion_lookback_daily`)

**Default:** `10`
**Range:** `5-30`
**Recommended:** `10-20`

**What it does:**
- Number of daily periods to analyze for volume exhaustion patterns
- Longer lookback = More stable volume baseline
- Shorter lookback = More responsive to recent volume changes

**Tuning Guidelines:**

| Value | Stability | Use Case |
|-------|-----------|----------|
| 5-7 | Very Responsive | High volatility, fast markets |
| 10 | Responsive | **Short-term (default)** |
| 15-20 | Stable | Medium-term, stable baseline |
| 20-30 | Very Stable | Long-term, less noise |

**Example:**
```python
# More responsive
config = StrategyConfig(volume_exhaustion_lookback_daily=7)

# More stable baseline
config = StrategyConfig(volume_exhaustion_lookback_daily=20)
```

**Impact:**
- Longer lookback = More stable volume baseline, less false signals
- Shorter lookback = More responsive, faster detection of volume exhaustion

---

### 5. Volume Exhaustion Lookback (Weekly) (`volume_exhaustion_lookback_weekly`)

**Default:** `20`
**Range:** `10-50`
**Recommended:** `20-30`

**What it does:**
- Number of weekly periods to analyze for volume exhaustion patterns
- Longer lookback = More stable weekly volume baseline
- Shorter lookback = More responsive to recent weekly volume changes

**Tuning Guidelines:**

| Value | Stability | Use Case |
|-------|-----------|----------|
| 10-15 | Responsive | Short-term, fast markets |
| 20 | Balanced | **Short-term with trend context (default)** |
| 25-30 | Stable | Medium-term, stable baseline |
| 30-50 | Very Stable | Long-term, less noise |

**Example:**
```python
# More responsive
config = StrategyConfig(volume_exhaustion_lookback_weekly=15)

# More stable baseline
config = StrategyConfig(volume_exhaustion_lookback_weekly=30)
```

**Impact:**
- Longer lookback = More stable weekly volume baseline
- Shorter lookback = More responsive to recent weekly volume changes

---

### 6. Data Fetch Daily Max Years (`data_fetch_daily_max_years`)

**Default:** `5`
**Range:** `1-10`
**Recommended:** `3-5`

**What it does:**
- Maximum years of daily data to fetch
- More years = More historical context, better indicators
- Fewer years = Faster fetching, less data

**Tuning Guidelines:**

| Value | Context | Use Case |
|-------|---------|----------|
| 1-2 | Recent | Fast markets, quick analysis |
| 3-5 | Medium-term | **Balanced (default: 5)** |
| 5-7 | Long-term | Better indicators, more context |
| 7-10 | Very Long-term | Historical analysis, major trends |

**Example:**
```python
# Faster fetching
config = StrategyConfig(data_fetch_daily_max_years=3)

# More historical context
config = StrategyConfig(data_fetch_daily_max_years=7)
```

**Impact:**
- More years = Better EMA200 calculation, more historical context
- Fewer years = Faster fetching, less API usage

**Note:** EMA200 requires at least 1.5 years of data for reliable calculation.

---

### 7. Data Fetch Weekly Max Years (`data_fetch_weekly_max_years`)

**Default:** `3`
**Range:** `1-5`
**Recommended:** `3-5`

**What it does:**
- Maximum years of weekly data to fetch
- More years = More historical trend context
- Fewer years = Faster fetching, less data

**Tuning Guidelines:**

| Value | Context | Use Case |
|-------|---------|----------|
| 1-2 | Recent | Short-term, quick analysis |
| 3 | Medium-term | **Balanced (default)** |
| 3-5 | Long-term | Better trend context, major levels |
| 5 | Very Long-term | Historical analysis, major trends |

**Example:**
```python
# Faster fetching
config = StrategyConfig(data_fetch_weekly_max_years=2)

# More historical context
config = StrategyConfig(data_fetch_weekly_max_years=5)
```

**Impact:**
- More years = Better weekly trend context, major support/resistance levels
- Fewer years = Faster fetching, less API usage

---

### 8. Enable Adaptive Lookback (`enable_adaptive_lookback`)

**Default:** `True`
**Range:** `True/False`
**Recommended:** `True`

**What it does:**
- Automatically adjusts lookback periods based on available data
- Longer lookbacks when more data is available
- Shorter lookbacks when less data is available

**Tuning Guidelines:**

| Value | Behavior | Use Case |
|-------|----------|----------|
| `True` | Adaptive | **Recommended - Optimizes based on data** |
| `False` | Fixed | Consistent lookback, no adaptation |

**Example:**
```python
# Adaptive (recommended)
config = StrategyConfig(enable_adaptive_lookback=True)

# Fixed lookback
config = StrategyConfig(enable_adaptive_lookback=False)
```

**Impact:**
- `True` = Better utilization of available data, optimized lookbacks
- `False` = Consistent lookback, no adaptation

**Adaptive Logic:**
- **Daily:** If 5+ years available → 2.5x lookback (max 50), If 3+ years → 1.5x lookback (max 30)
- **Weekly:** If 3+ years available → 2.5x lookback (max 50), If 2+ years → 2x lookback (max 40)

---

## Configuration Presets

### Short-Term Trading (Default)

**Best for:** Quick entries/exits, 1-5 day holds, active trading

```python
config = StrategyConfig(
    rsi_period=10,
    support_resistance_lookback_daily=20,
    support_resistance_lookback_weekly=50,
    volume_exhaustion_lookback_daily=10,
    volume_exhaustion_lookback_weekly=20,
    data_fetch_daily_max_years=5,
    data_fetch_weekly_max_years=3,
    enable_adaptive_lookback=True
)
```

**Characteristics:**
- Fast signal generation
- Quick adaptation to market changes
- More signals (higher false positive rate)
- Good for volatile markets

---

### Medium-Term Trading

**Best for:** Swing trading, 1-4 week holds, trend following

```python
config = StrategyConfig(
    rsi_period=14,
    support_resistance_lookback_daily=50,
    support_resistance_lookback_weekly=100,
    volume_exhaustion_lookback_daily=20,
    volume_exhaustion_lookback_weekly=40,
    data_fetch_daily_max_years=5,
    data_fetch_weekly_max_years=3,
    enable_adaptive_lookback=True
)
```

**Characteristics:**
- More stable signals
- Better trend identification
- Fewer signals (better quality)
- Good for trending markets

---

### Long-Term Trading

**Best for:** Position trading, 1-3 month holds, major trends

```python
config = StrategyConfig(
    rsi_period=14,
    support_resistance_lookback_daily=100,
    support_resistance_lookback_weekly=200,
    volume_exhaustion_lookback_daily=50,
    volume_exhaustion_lookback_weekly=100,
    data_fetch_daily_max_years=10,
    data_fetch_weekly_max_years=5,
    enable_adaptive_lookback=True
)
```

**Characteristics:**
- Very stable signals
- Major trend identification
- Few signals (high quality)
- Good for stable markets

---

## Tuning Workflow

### Step 1: Identify Your Trading Style

- **Short-term:** Use default configuration
- **Medium-term:** Use medium-term preset
- **Long-term:** Use long-term preset

### Step 2: Backtest with Default Configuration

```bash
python trade_agent.py --backtest RELIANCE.NS 2023-01-01 2023-12-31
```

### Step 3: Analyze Results

Look for:
- **Too many signals:** Increase RSI period, increase lookbacks
- **Too few signals:** Decrease RSI period, decrease lookbacks
- **Poor stop-loss accuracy:** Increase support/resistance lookbacks
- **Slow performance:** Decrease data fetch max years

### Step 4: Adjust Parameters

Start with one parameter at a time:

```python
# Example: Too many false signals
config = StrategyConfig(
    rsi_period=14,  # Increased from 10
    # ... keep other defaults
)
```

### Step 5: Backtest Again

Compare results with previous configuration.

### Step 6: Iterate

Repeat steps 3-5 until optimal configuration is found.

---

## Common Tuning Scenarios

### Scenario 1: Too Many False Signals

**Symptoms:**
- Many buy signals but low win rate
- Frequent stop-loss hits
- High transaction costs

**Solution:**
```python
config = StrategyConfig(
    rsi_period=14,  # Increase from 10
    support_resistance_lookback_daily=30,  # Increase from 20
    volume_exhaustion_lookback_daily=15,  # Increase from 10
    # ... keep other defaults
)
```

---

### Scenario 2: Too Few Signals

**Symptoms:**
- Very few buy signals
- Missing opportunities
- Low trading frequency

**Solution:**
```python
config = StrategyConfig(
    rsi_period=7,  # Decrease from 10
    support_resistance_lookback_daily=15,  # Decrease from 20
    volume_exhaustion_lookback_daily=7,  # Decrease from 10
    # ... keep other defaults
)
```

---

### Scenario 3: Poor Stop-Loss Accuracy

**Symptoms:**
- Stop-loss hit too frequently
- Support/resistance levels not accurate
- Poor risk-reward ratio

**Solution:**
```python
config = StrategyConfig(
    support_resistance_lookback_daily=50,  # Increase from 20
    support_resistance_lookback_weekly=100,  # Increase from 50
    # ... keep other defaults
)
```

---

### Scenario 4: Slow Performance

**Symptoms:**
- Long backtest execution time
- High API usage
- Slow data fetching

**Solution:**
```python
config = StrategyConfig(
    data_fetch_daily_max_years=3,  # Decrease from 5
    data_fetch_weekly_max_years=2,  # Decrease from 3
    # ... keep other defaults
)
```

**Note:** Don't go below 3 years for daily (EMA200 needs at least 1.5 years).

---

## Best Practices

### 1. Start with Defaults

Always start with default configuration and adjust based on results.

### 2. Change One Parameter at a Time

This helps identify which parameter affects which behavior.

### 3. Backtest Thoroughly

Test with multiple stocks and time periods before using in production.

### 4. Monitor Performance

Track win rate, average return, and signal frequency with different configurations.

### 5. Use Adaptive Lookback

Keep `enable_adaptive_lookback=True` unless you have a specific reason to disable it.

### 6. Balance Signal Quality vs Quantity

- More signals = More opportunities but more false positives
- Fewer signals = Better quality but fewer opportunities

### 7. Consider Market Conditions

- **Volatile markets:** Lower RSI period, shorter lookbacks
- **Stable markets:** Higher RSI period, longer lookbacks
- **Trending markets:** Longer lookbacks for better trend identification

---

## Configuration Validation

### Minimum Requirements

- **RSI Period:** 5-30 (recommended: 10-14)
- **Support/Resistance Lookback Daily:** 10-100 (recommended: 20-50)
- **Support/Resistance Lookback Weekly:** 20-200 (recommended: 50-100)
- **Volume Exhaustion Lookback Daily:** 5-30 (recommended: 10-20)
- **Volume Exhaustion Lookback Weekly:** 10-50 (recommended: 20-30)
- **Data Fetch Daily Max Years:** 1-10 (recommended: 3-5, minimum: 2 for EMA200)
- **Data Fetch Weekly Max Years:** 1-5 (recommended: 3-5)

### Validation Function

```python
from config.strategy_config import StrategyConfig

def validate_config(config: StrategyConfig) -> bool:
    """Validate configuration parameters"""
    errors = []

    if not (5 <= config.rsi_period <= 30):
        errors.append(f"RSI period must be 5-30, got {config.rsi_period}")

    if not (10 <= config.support_resistance_lookback_daily <= 100):
        errors.append(f"Support/Resistance lookback daily must be 10-100, got {config.support_resistance_lookback_daily}")

    if not (20 <= config.support_resistance_lookback_weekly <= 200):
        errors.append(f"Support/Resistance lookback weekly must be 20-200, got {config.support_resistance_lookback_weekly}")

    if not (5 <= config.volume_exhaustion_lookback_daily <= 30):
        errors.append(f"Volume exhaustion lookback daily must be 5-30, got {config.volume_exhaustion_lookback_daily}")

    if not (10 <= config.volume_exhaustion_lookback_weekly <= 50):
        errors.append(f"Volume exhaustion lookback weekly must be 10-50, got {config.volume_exhaustion_lookback_weekly}")

    if not (2 <= config.data_fetch_daily_max_years <= 10):
        errors.append(f"Data fetch daily max years must be 2-10 (minimum 2 for EMA200), got {config.data_fetch_daily_max_years}")

    if not (1 <= config.data_fetch_weekly_max_years <= 5):
        errors.append(f"Data fetch weekly max years must be 1-5, got {config.data_fetch_weekly_max_years}")

    if errors:
        print("Configuration validation errors:")
        for error in errors:
            print(f"  - {error}")
        return False

    return True

# Example usage
config = StrategyConfig(rsi_period=14, support_resistance_lookback_daily=30)
if validate_config(config):
    print("Configuration is valid!")
```

---

## Troubleshooting

### Issue: Configuration Not Applied

**Solution:**
- Ensure environment variables are set before running
- Check that `StrategyConfig.default()` or custom config is passed to functions
- Verify configuration is loaded correctly

### Issue: Performance Degradation

**Solution:**
- Reduce `data_fetch_daily_max_years` and `data_fetch_weekly_max_years`
- Reduce lookback periods
- Disable adaptive lookback if not needed

### Issue: Too Many/Few Signals

**Solution:**
- Adjust RSI period (increase for fewer signals, decrease for more)
- Adjust lookback periods
- Review backtest results to find optimal balance

---

## Summary

This guide provides comprehensive tuning guidelines for all configurable parameters. Start with defaults, backtest thoroughly, and adjust based on results. Remember to:

1. ✅ Start with default configuration
2. ✅ Change one parameter at a time
3. ✅ Backtest thoroughly
4. ✅ Monitor performance
5. ✅ Use adaptive lookback
6. ✅ Balance signal quality vs quantity
7. ✅ Consider market conditions

For more information, see:
- `documents/IMPLEMENTATION_COMPREHENSIVE_STATUS.md` - Complete implementation status
- `documents/requirements/CONFIGURABLE_INDICATORS_REQUIREMENTS.md` - Requirements document
- `config/strategy_config.py` - Configuration source code

---

**Document Version:** 1.0
**Last Updated:** 2025-11-07
