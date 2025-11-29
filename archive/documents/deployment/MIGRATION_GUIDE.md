# Migration Guide: Legacy to New CLI System

This guide documents the architectural changes and migration path from the legacy `trade_agent.py` system to the new modular CLI-based architecture.

## Table of Contents
- [Overview](#overview)
- [Key Changes](#key-changes)
- [Breaking Changes](#breaking-changes)
- [Migration Steps](#migration-steps)
- [Behavioral Differences](#behavioral-differences)
- [Troubleshooting](#troubleshooting)

## Overview

The new CLI system (`cli/commands/analyze_stocks.py`) introduces a clean architecture using Clean Architecture principles with DTOs, Use Cases, and dependency injection. This migration guide helps you understand the differences and migrate from the legacy system.

## Key Changes

### 1. Architecture Transformation

**Legacy System:**
- Monolithic `trade_agent.py` with inline logic
- Direct function calls and global state
- Mixed concerns (data fetching, analysis, alerting)

**New CLI System:**
- Clean Architecture with layers (DTOs, Use Cases, Services)
- Dependency injection via `ServiceContainer`
- Clear separation of concerns

### 2. Final Verdict Reclassification

The most critical change is the implementation of **final verdict logic** that was present in the legacy CSV exports but missing in the initial CLI implementation.

#### What is Final Verdict?

The `final_verdict` field represents a **reclassified recommendation** based on combined scores when backtest scoring is enabled. It can **downgrade or upgrade** the original analysis verdict:

- **Downgrade**: `strong_buy` → `buy` → `watch` → `avoid`
- **Upgrade**: `watch` → `buy` (under certain conditions)

#### Reclassification Rules

From `core/backtest_scoring.py`:

```python
def add_backtest_scores_to_results(results, backtest_scores):
    """
    Reclassification logic based on:
    - Combined Score (50% current + 50% backtest)
    - Backtest Score
    - Trade Count
    - RSI Level
    """

    # Downgrade if combined score is too low
    if combined_score < 5.0:
        final_verdict = "avoid"
    elif combined_score < 6.0:
        final_verdict = "watch"

    # Downgrade if insufficient backtest data
    if trade_count < 3:
        final_verdict = downgrade(final_verdict)

    # Downgrade if backtest score is poor
    if backtest_score < 4.0:
        final_verdict = downgrade(final_verdict)

    # Upgrade if severely oversold (RSI < 20) with decent scores
    if rsi < 20 and combined_score >= 6.5:
        final_verdict = upgrade(final_verdict)
```

### 3. Filtering Logic Changes

#### Legacy Behavior
```python
# In trade_agent.py (legacy)
buyable_stocks = [
    s for s in all_stocks
    if s.get('combined_score', 0) >= min_score_filter
]
```

#### New CLI Behavior
```python
# In cli/commands/analyze_stocks.py (new)
def is_buyable(stock_dto):
    # When backtest enabled: use final_verdict
    if backtest_enabled:
        return stock_dto.final_verdict in ['strong_buy', 'buy']

    # When backtest disabled: use original verdict + score filter
    return (
        stock_dto.verdict in ['strong_buy', 'buy']
        and stock_dto.combined_score >= min_score_filter
    )
```

### 4. Data Transfer Objects (DTOs)

New DTOs introduced for type safety and clear data contracts:

```python
@dataclass
class StockAnalysisDTO:
    symbol: str
    verdict: str              # Original verdict from analysis
    final_verdict: str        # Reclassified verdict (when backtest enabled)
    combined_score: float
    backtest_score: float
    current_score: float
    priority_rank: int
    # ... other fields
```

### 5. Service Container Pattern

```python
# Old: Direct instantiation
analyzer = StockAnalyzer()
result = analyzer.analyze(symbol)

# New: Dependency injection
container = ServiceContainer(config)
use_case = container.get_analyze_stock_use_case()
result = use_case.execute(symbol)
```

## Breaking Changes

### 1. ⚠️ Buyable Stock Counting

**Issue**: Initial CLI implementation didn't use `final_verdict` for buyable determination.

**Impact**:
- Different buyable counts compared to legacy
- Stocks with low combined scores were incorrectly included
- Telegram alerts showed wrong stock counts

**Fix Applied**:
```python
# cli/use_cases/analyze_stock.py
result_dict['final_verdict'] = self._compute_final_verdict(
    result_dict,
    backtest_score,
    trade_count
)

# cli/commands/analyze_stocks.py
def is_buyable(stock_dto):
    if config.enable_backtest_scoring:
        return stock_dto.final_verdict in ['strong_buy', 'buy']
    else:
        return (
            stock_dto.verdict in ['strong_buy', 'buy']
            and stock_dto.combined_score >= config.min_score_filter
        )
```

### 2. ⚠️ CSV Export Field Alignment

**Issue**: CSV exports use `final_verdict` but initial alerting logic used `verdict`.

**Impact**:
- Mismatch between CSV recommendations and Telegram alerts
- Confusion when cross-referencing data sources

**Fix Applied**:
```python
# cli/use_cases/send_alerts.py
for stock_dto in buyable_stocks:
    # Use final_verdict consistently when backtest enabled
    display_verdict = (
        stock_dto.final_verdict
        if config.enable_backtest_scoring
        else stock_dto.verdict
    )
```

### 3. ⚠️ Score Filtering Logic

**Issue**: Score filtering applied inconsistently between legacy and CLI.

**Fix Applied**:
```python
# Apply score filter only when backtest disabled
if not config.enable_backtest_scoring:
    buyable_stocks = [
        s for s in buyable_stocks
        if s.combined_score >= config.min_score_filter
    ]
```

## Migration Steps

### Step 1: Understand Your Current Usage

**If you're using:**
```bash
# Legacy
python trade_agent.py --backtest
```

**Migrate to:**
```bash
# New CLI
python -m cli.main analyze-stocks --backtest
```

### Step 2: Update Configuration Access

**Legacy:**
```python
from config.settings import RSI_OVERSOLD, LOOKBACK_DAYS
```

**New:**
```python
from cli.config import AnalysisConfig

config = AnalysisConfig()
rsi_oversold = config.rsi_oversold
lookback_days = config.lookback_days
```

### Step 3: Update Analysis Calls

**Legacy:**
```python
from core.analysis import analyze_ticker

result = analyze_ticker("RELIANCE.NS")
verdict = result.get('verdict')
score = result.get('score')
```

**New:**
```python
from cli.container import ServiceContainer
from cli.config import AnalysisConfig

config = AnalysisConfig()
container = ServiceContainer(config)
use_case = container.get_analyze_stock_use_case()

result_dto = use_case.execute("RELIANCE.NS")
verdict = result_dto.final_verdict if config.enable_backtest_scoring else result_dto.verdict
score = result_dto.combined_score
```

### Step 4: Update Filtering Logic

**Legacy:**
```python
buyable = [s for s in stocks if s.get('combined_score', 0) >= 7.0]
```

**New:**
```python
from cli.commands.analyze_stocks import is_buyable_stock

buyable = [s for s in stock_dtos if is_buyable_stock(s, config)]
```

### Step 5: Update Alert Logic

**Legacy:**
```python
send_telegram_alert(stock, verdict=stock['verdict'])
```

**New:**
```python
use_case = container.get_send_alerts_use_case()
use_case.execute(buyable_stocks, all_stocks, config)
```

## Behavioral Differences

### 1. Stock Classification

| Scenario | Legacy | New CLI |
|----------|--------|---------|
| **Backtest enabled, combined_score < 6.0** | Marked as "watch" in CSV, but might alert as "buy" | Consistently marked as "watch" everywhere |
| **Backtest disabled, score >= min_score** | Alerts as "buy" | Alerts as "buy" |
| **Insufficient trades (< 3)** | Downgraded in CSV only | Downgraded consistently |

### 2. Buyable Count Calculation

**Legacy:**
```python
# Sometimes inconsistent between logs and CSV
buyable_count = len([s for s in stocks if s['combined_score'] >= min_score])
```

**New CLI:**
```python
# Consistent everywhere using final_verdict
buyable_count = len([
    s for s in stock_dtos
    if is_buyable_stock(s, config)
])
```

### 3. Priority Ranking

Both systems rank by priority, but new CLI has explicit priority field:

**Legacy:**
```python
# Implicit via sorting
sorted_stocks = sorted(stocks, key=lambda x: x['combined_score'], reverse=True)
```

**New CLI:**
```python
# Explicit priority_rank field in DTO
stock_dto.priority_rank  # 1, 2, 3, ...
```

## Troubleshooting

### Issue: Different buyable counts between legacy and CLI

**Symptom:**
```
Legacy: 5 stocks buyable
New CLI: 3 stocks buyable
```

**Diagnosis:**
1. Check if backtest scoring is enabled in both
2. Verify `final_verdict` field is populated in CLI
3. Check `min_score_filter` value consistency

**Solution:**
Ensure CLI uses `final_verdict` when backtest enabled:
```python
# In analyze_stocks.py
if config.enable_backtest_scoring:
    buyable_stocks = [
        s for s in stock_dtos
        if s.final_verdict in ['strong_buy', 'buy']
    ]
```

### Issue: CSV shows "watch" but alert shows "buy"

**Symptom:**
- CSV recommendation: `watch`
- Telegram alert: `STRONG BUY` or `BUY`

**Diagnosis:**
Alert logic not using `final_verdict`

**Solution:**
Update alert logic to use `final_verdict`:
```python
display_verdict = (
    stock_dto.final_verdict
    if config.enable_backtest_scoring
    else stock_dto.verdict
)
```

### Issue: Scores don't match legacy system

**Symptom:**
```
Legacy: combined_score = 7.2
New CLI: combined_score = 7.2, but not buyable
```

**Diagnosis:**
`final_verdict` downgraded due to insufficient trades or poor backtest

**Solution:**
This is expected behavior. Check:
1. `trade_count` in backtest results
2. `backtest_score` value
3. `final_verdict` vs `verdict` difference

### Issue: Missing final_verdict field

**Symptom:**
```
AttributeError: 'StockAnalysisDTO' object has no attribute 'final_verdict'
```

**Diagnosis:**
`AnalyzeStockUseCase` not computing `final_verdict`

**Solution:**
Ensure use case computes final verdict:
```python
# In use_cases/analyze_stock.py
if self.config.enable_backtest_scoring:
    result_dict['final_verdict'] = self._compute_final_verdict(
        result_dict,
        backtest_score,
        trade_count
    )
else:
    result_dict['final_verdict'] = result_dict['verdict']
```

## Testing Migration

### Validation Checklist

- [ ] Run both systems with same stocks and compare:
  - [ ] Buyable stock count matches
  - [ ] Verdicts match (check `final_verdict` vs `verdict`)
  - [ ] Combined scores match
  - [ ] Priority ranks are consistent
  - [ ] CSV exports align with alerts

### Example Validation Script

```bash
# Run legacy
python trade_agent.py --backtest > legacy_output.txt

# Run new CLI
python -m cli.main analyze-stocks --backtest > cli_output.txt

# Compare buyable counts
grep "buyable stocks" legacy_output.txt
grep "buyable stocks" cli_output.txt

# Compare CSV files
diff legacy_recommendations_*.csv recommendations_*.csv
```

## Additional Resources

- **Legacy Code**: `trade_agent.py`
- **New CLI Code**: `cli/commands/analyze_stocks.py`
- **Final Verdict Logic**: `core/backtest_scoring.py`
- **DTOs**: `cli/dtos/stock_analysis.py`
- **Use Cases**: `cli/use_cases/`

## Summary

The key to successful migration is understanding that:

1. **Final verdict** is the authoritative recommendation when backtest is enabled
2. **Buyable determination** must use `final_verdict`, not `verdict`
3. **Score filtering** is applied differently based on backtest mode
4. **Consistency** between CSV, logs, and alerts is critical

The new CLI system reproduces legacy behavior exactly while providing better structure, testability, and maintainability.
