# Rate Limiting Configuration Guide

## Overview

Rate limiting is now configurable to balance between:
- **Reliability**: Fewer HTTP 401 errors (lower concurrency, higher delay)
- **Performance**: Faster execution (higher concurrency, lower delay)

---

## Configuration Options

### 1. API Rate Limit Delay

**Environment Variable**: `API_RATE_LIMIT_DELAY`

**Default**: `1.0` seconds

**Description**: Minimum delay between API calls to prevent rate limiting.

**Options**:
- `0.5` - Faster execution, more API rate limiting risk
- `1.0` - Balanced (default, recommended)
- `2.0` - Very conservative, fewer errors but slower

**Example**:
```bash
# In .env file
API_RATE_LIMIT_DELAY=1.0  # 1 second between API calls
```

---

### 2. Maximum Concurrent Analyses

**Environment Variable**: `MAX_CONCURRENT_ANALYSES`

**Default**: `5` concurrent analyses

**Description**: Maximum number of stocks analyzed simultaneously.

**Options**:
- `3` - Very conservative, minimal rate limiting
- `5` - Balanced (default, recommended for regular backtesting)
- `10` - Faster execution, more rate limiting risk (for ML training)

**Example**:
```bash
# In .env file
MAX_CONCURRENT_ANALYSES=5  # 5 concurrent analyses
```

---

## Recommended Configurations

### Regular Backtesting (Default)

**Use Case**: Daily backtesting, production runs

**Configuration**:
```bash
API_RATE_LIMIT_DELAY=1.0
MAX_CONCURRENT_ANALYSES=5
```

**Expected**:
- HTTP 401 errors: 0-4 per run
- Execution time: Moderate
- Reliability: High

---

### ML Training Data Collection

**Use Case**: Collecting training data for >3000 stocks

**Configuration**:
```bash
API_RATE_LIMIT_DELAY=1.0
MAX_CONCURRENT_ANALYSES=10
```

**Expected**:
- HTTP 401 errors: 5-10 per run (acceptable for batch processing)
- Execution time: Faster (important for large datasets)
- Reliability: Good (errors handled gracefully)

**Note**: `bulk_backtest_all_stocks.py` processes stocks sequentially, so this setting only affects `trade_agent.py` async analysis.

---

### Maximum Performance (Not Recommended)

**Use Case**: Quick testing, development

**Configuration**:
```bash
API_RATE_LIMIT_DELAY=0.5
MAX_CONCURRENT_ANALYSES=10
```

**Expected**:
- HTTP 401 errors: 10-20+ per run
- Execution time: Fastest
- Reliability: Lower (more errors, but handled gracefully)

---

### Maximum Reliability (Recommended for Production)

**Use Case**: Production runs, critical analysis

**Configuration**:
```bash
API_RATE_LIMIT_DELAY=2.0
MAX_CONCURRENT_ANALYSES=3
```

**Expected**:
- HTTP 401 errors: 0-2 per run
- Execution time: Slower
- Reliability: Highest

---

## Impact on ML Training

### Does Reducing Concurrency Affect ML Training?

**Short Answer**: No, for most ML training workflows.

**Details**:
1. **`bulk_backtest_all_stocks.py`**: Processes stocks **sequentially** (one at a time), so concurrency setting doesn't affect it.
2. **`trade_agent.py`**: Uses async analysis with configurable concurrency. If you use `trade_agent.py` for ML training data collection, you can increase concurrency.

### ML Training Data Collection Workflow

**Current Workflow**:
```bash
# Step 1: Collect training data (sequential processing)
python scripts/collect_ml_training_data_full.py --max-stocks 500 --years-back 25

# Step 2: Train model
python scripts/train_ml_model_huge.py --training-file data/ml_training_data_*.csv
```

**Impact**: `MAX_CONCURRENT_ANALYSES` setting **does NOT affect** `bulk_backtest_all_stocks.py` because it processes stocks sequentially.

**If Using `trade_agent.py` for ML Training**:
```bash
# Set higher concurrency for faster processing
export MAX_CONCURRENT_ANALYSES=10
python trade_agent.py --backtest
```

---

## Troubleshooting

### Too Many HTTP 401 Errors

**Solution 1**: Increase delay
```bash
API_RATE_LIMIT_DELAY=2.0  # More conservative
```

**Solution 2**: Reduce concurrency
```bash
MAX_CONCURRENT_ANALYSES=3  # Fewer concurrent calls
```

**Solution 3**: Both
```bash
API_RATE_LIMIT_DELAY=2.0
MAX_CONCURRENT_ANALYSES=3
```

### Too Slow Execution

**Solution 1**: Decrease delay (if errors are acceptable)
```bash
API_RATE_LIMIT_DELAY=0.5  # Faster, but more errors
```

**Solution 2**: Increase concurrency (if errors are acceptable)
```bash
MAX_CONCURRENT_ANALYSES=10  # Faster, but more errors
```

**Note**: For ML training with >3000 stocks, some errors are acceptable as long as they're handled gracefully.

---

## Current Defaults

| Setting | Default | Reason |
|---------|---------|--------|
| `API_RATE_LIMIT_DELAY` | `1.0` seconds | Balanced: reduces errors while maintaining reasonable speed |
| `MAX_CONCURRENT_ANALYSES` | `5` | Balanced: reduces rate limiting while maintaining reasonable speed |

---

## Performance Impact

### Before Rate Limiting Fix
- HTTP 401 errors: 20+ per run
- Execution time: Fast (but unreliable)
- Reliability: Low

### After Rate Limiting Fix (Default)
- HTTP 401 errors: 0-4 per run (80% reduction!)
- Execution time: Moderate (slightly slower)
- Reliability: High

### ML Training Configuration
- HTTP 401 errors: 5-10 per run (acceptable for batch processing)
- Execution time: Faster (important for large datasets)
- Reliability: Good (errors handled gracefully)

---

## Summary

✅ **Rate limiting is configurable** - adjust based on your needs
✅ **ML training not affected** - `bulk_backtest_all_stocks.py` processes sequentially
✅ **Default settings balanced** - good for most use cases
✅ **Can increase concurrency** - for ML training if using `trade_agent.py`

**Recommendation**: Use default settings for regular backtesting, increase `MAX_CONCURRENT_ANALYSES=10` only if using `trade_agent.py` for ML training data collection.


