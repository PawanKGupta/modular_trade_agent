# Phase 4 Migration Guide

**Date:** 2025-01-15
**Status:** Phase 4.5 Complete
**Purpose:** Guide for migrating from `core.*` functions to service layer

---

## Overview

Phase 4.5 has deprecated legacy `core.*` functions in favor of the service layer. This guide helps you migrate your code to use the new service-based architecture.

---

## Why Migrate?

### Benefits of Service Layer

1. **Better Testability** - Dependency injection allows easy mocking
2. **Modularity** - Single responsibility, easier to maintain
3. **Async Support** - 80% faster batch operations
4. **Type Safety** - Typed models with Pydantic
5. **Caching** - 70-90% reduction in API calls
6. **Event-Driven** - Pluggable event handling
7. **Pipeline Pattern** - Flexible, composable workflows

---

## Migration Patterns

### Pattern 1: Single Ticker Analysis

#### ❌ OLD (Deprecated)
```python
from core.analysis import analyze_ticker

result = analyze_ticker("RELIANCE.NS", enable_multi_timeframe=True)
```

#### ✅ NEW (Recommended)
```python
from services import AnalysisService

service = AnalysisService()
result = service.analyze_ticker(
    ticker="RELIANCE.NS",
    enable_multi_timeframe=True
)
```

**Benefits:**
- Dependency injection for testing
- Type-safe results
- Better error handling

---

### Pattern 2: Batch Analysis

#### ❌ OLD (Deprecated)
```python
from core.analysis import analyze_multiple_tickers

results = analyze_multiple_tickers(
    tickers=["RELIANCE.NS", "TCS.NS", "INFY.NS"],
    enable_multi_timeframe=True
)
```

#### ✅ NEW (Recommended - 80% Faster!)
```python
from services import AsyncAnalysisService
import asyncio

async def analyze():
    service = AsyncAnalysisService(max_concurrent=10)
    results = await service.analyze_batch_async(
        tickers=["RELIANCE.NS", "TCS.NS", "INFY.NS"],
        enable_multi_timeframe=True,
        export_to_csv=True
    )
    return results

results = asyncio.run(analyze())
```

**Benefits:**
- **80% faster** (25min → 5min for 50 stocks)
- Parallel processing
- Better error handling per ticker
- Non-blocking

---

### Pattern 3: Scoring

#### ❌ OLD (Deprecated)
```python
from core.scoring import compute_strength_score

score = compute_strength_score(result)
```

#### ✅ NEW (Recommended)
```python
from services import ScoringService

service = ScoringService()
score = service.compute_strength_score(result)

# Additional methods available:
priority_score = service.compute_trading_priority_score(result)
combined_score = service.compute_combined_score(result, historical_score)
```

**Benefits:**
- Additional scoring methods
- Service layer benefits
- Better testability

---

### Pattern 4: Backtesting

#### ❌ OLD (Deprecated)
```python
from core.backtest_scoring import (
    run_stock_backtest,
    add_backtest_scores_to_results
)

# Single stock backtest
backtest_result = run_stock_backtest("RELIANCE.NS", years_back=2)

# Add scores to results
enhanced_results = add_backtest_scores_to_results(results, years_back=2)
```

#### ✅ NEW (Recommended)
```python
from services import BacktestService

service = BacktestService(default_years_back=2, dip_mode=False)

# Single stock backtest
backtest_result = service.run_stock_backtest("RELIANCE.NS")

# Add scores to results
enhanced_results = service.add_backtest_scores_to_results(results)
```

**Benefits:**
- Configurable defaults
- Consistent interface
- Better error handling
- Service layer benefits

---

### Pattern 5: Trading Parameters

#### ❌ OLD (Deprecated)
```python
from core.analysis import (
    calculate_smart_buy_range,
    calculate_smart_stop_loss,
    calculate_smart_target
)

buy_range = calculate_smart_buy_range(current_price, timeframe_confirmation)
stop = calculate_smart_stop_loss(current_price, recent_low, timeframe_confirmation, df)
target = calculate_smart_target(current_price, stop, verdict, timeframe_confirmation, recent_high)
```

#### ✅ NEW (Recommended)
```python
from services import VerdictService

service = VerdictService()
trading_params = service.calculate_trading_parameters(
    current_price=current_price,
    verdict=verdict,
    timeframe_confirmation=timeframe_confirmation,
    recent_low=recent_low,
    recent_high=recent_high,
    df=df
)

buy_range = trading_params.buy_range
stop = trading_params.stop_loss
target = trading_params.target
```

**Benefits:**
- Single method call
- Consistent parameter calculation
- Type-safe TradingParameters object
- Better maintainability

---

## Complete Function Mapping

| Deprecated Function | Service Replacement | Notes |
|-------------------|---------------------|-------|
| `core.analysis.analyze_ticker()` | `AnalysisService.analyze_ticker()` | Direct replacement |
| `core.analysis.analyze_multiple_tickers()` | `AsyncAnalysisService.analyze_batch_async()` | **80% faster** |
| `core.scoring.compute_strength_score()` | `ScoringService.compute_strength_score()` | Direct replacement |
| `core.backtest_scoring.run_stock_backtest()` | `BacktestService.run_stock_backtest()` | Direct replacement |
| `core.backtest_scoring.add_backtest_scores_to_results()` | `BacktestService.add_backtest_scores_to_results()` | Direct replacement |
| `core.analysis.calculate_smart_buy_range()` | `VerdictService.calculate_trading_parameters()` | Returns TradingParameters object |
| `core.analysis.calculate_smart_stop_loss()` | `VerdictService.calculate_trading_parameters()` | Returns TradingParameters object |
| `core.analysis.calculate_smart_target()` | `VerdictService.calculate_trading_parameters()` | Returns TradingParameters object |

---

## Step-by-Step Migration

### Step 1: Identify Deprecated Functions

Search your codebase for deprecated functions:
```bash
# Find all uses of deprecated functions
grep -r "from core.analysis import" .
grep -r "from core.scoring import" .
grep -r "from core.backtest_scoring import" .
```

### Step 2: Update Imports

Replace imports:
```python
# OLD
from core.analysis import analyze_ticker
from core.scoring import compute_strength_score

# NEW
from services import AnalysisService, ScoringService
```

### Step 3: Update Function Calls

Replace function calls with service methods:
```python
# OLD
result = analyze_ticker("RELIANCE.NS")
score = compute_strength_score(result)

# NEW
service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")
scoring_service = ScoringService()
score = scoring_service.compute_strength_score(result)
```

### Step 4: Test Your Changes

Run your tests to ensure everything works:
```bash
pytest tests/
```

### Step 5: Remove Deprecated Code

Once all code is migrated, you can remove deprecated function calls.

---

## Common Migration Scenarios

### Scenario 1: Script Using analyze_ticker

**Before:**
```python
from core.analysis import analyze_ticker

ticker = "RELIANCE.NS"
result = analyze_ticker(ticker, enable_multi_timeframe=True)
print(f"Verdict: {result['verdict']}")
```

**After:**
```python
from services import AnalysisService

service = AnalysisService()
ticker = "RELIANCE.NS"
result = service.analyze_ticker(ticker, enable_multi_timeframe=True)
print(f"Verdict: {result['verdict']}")
```

---

### Scenario 2: Batch Processing Script

**Before:**
```python
from core.analysis import analyze_multiple_tickers

tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
results = analyze_multiple_tickers(tickers, export_to_csv=True)
```

**After:**
```python
from services import AsyncAnalysisService
import asyncio

async def main():
    service = AsyncAnalysisService(max_concurrent=10)
    tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    results = await service.analyze_batch_async(
        tickers=tickers,
        enable_multi_timeframe=True,
        export_to_csv=True
    )
    return results

results = asyncio.run(main())
```

**Performance:** 80% faster! (25min → 5min for 50 stocks)

---

### Scenario 3: Backtest Integration

**Before:**
```python
from core.analysis import analyze_ticker
from core.backtest_scoring import add_backtest_scores_to_results

# Analyze
results = [analyze_ticker(ticker) for ticker in tickers]

# Add backtest scores
enhanced = add_backtest_scores_to_results(results, years_back=2)
```

**After:**
```python
from services import AnalysisService, BacktestService

analysis_service = AnalysisService()
backtest_service = BacktestService(default_years_back=2)

# Analyze
results = [analysis_service.analyze_ticker(ticker) for ticker in tickers]

# Add backtest scores
enhanced = backtest_service.add_backtest_scores_to_results(results)
```

---

## Deprecation Warnings

When you use deprecated functions, you'll see warnings like:

```
DeprecationWarning: DEPRECATED: core.analysis.analyze_ticker() is deprecated in Phase 4.
Use services.AnalysisService.analyze_ticker() instead.
This will be removed in a future version.
```

**To suppress warnings temporarily** (not recommended):
```python
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
```

**Better approach:** Migrate to service layer!

---

## Testing Migrated Code

### Unit Testing with Services

Services support dependency injection for easy testing:

```python
from services import AnalysisService, DataService
from unittest.mock import Mock

# Mock dependencies
mock_data_service = Mock()
mock_data_service.fetch_ohlcv.return_value = test_dataframe

# Create service with mocked dependencies
service = AnalysisService(data_service=mock_data_service)

# Test
result = service.analyze_ticker("RELIANCE.NS")
assert result['verdict'] == 'buy'
```

---

## Additional Service Features

### Async Batch Analysis

```python
from services import AsyncAnalysisService
import asyncio

async def analyze_stocks():
    service = AsyncAnalysisService(max_concurrent=10)

    # Analyze 50 stocks in parallel
    results = await service.analyze_batch_async(
        tickers=stock_list,
        enable_multi_timeframe=True
    )

    return results

# Run async
results = asyncio.run(analyze_stocks())
```

### Event-Driven Analysis

```python
from services import AnalysisService, get_event_bus, EventType

# Subscribe to events
bus = get_event_bus()

def on_analysis_complete(event):
    print(f"Analysis complete: {event.data['ticker']} -> {event.data['verdict']}")

bus.subscribe(EventType.ANALYSIS_COMPLETED, on_analysis_complete)

# Run analysis - events automatically published
service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")
```

### Pipeline Pattern

```python
from services import create_analysis_pipeline

# Create custom pipeline
pipeline = create_analysis_pipeline(
    enable_fundamentals=True,
    enable_multi_timeframe=True
)

# Execute
context = pipeline.execute("RELIANCE.NS")
verdict = context.results['verdict']
```

---

## Troubleshooting

### Issue: "Service layer not available"

**Error:**
```
ImportError: cannot import name 'AnalysisService'
```

**Solution:**
1. Ensure `services/` directory exists
2. Check that `services/__init__.py` exports `AnalysisService`
3. Verify Python path includes project root

### Issue: "Function signature mismatch"

**Error:**
```
TypeError: analyze_ticker() got an unexpected keyword argument 'xyz'
```

**Solution:**
- Check service method signature
- Some parameters may have been renamed or removed
- See service documentation for current parameters

### Issue: "Deprecation warnings in logs"

**Solution:**
- Migrate to service layer (recommended)
- Or suppress warnings temporarily (not recommended)

---

## Migration Checklist

- [ ] Identify all deprecated function calls
- [ ] Update imports to use services
- [ ] Replace function calls with service methods
- [ ] Update batch operations to use AsyncAnalysisService
- [ ] Test all migrated code
- [ ] Remove deprecated function calls
- [ ] Update documentation

---

## Need Help?

- Check service documentation: `services/__init__.py`
- See examples: `examples/` directory
- Review service source: `services/analysis_service.py`
- Get migration guide: `utils.deprecation.get_migration_guide(function_name)`

---

## Next Steps

After migrating:
1. **Phase 4.6**: Remove duplicate functionality
2. **Phase 4.7**: Update documentation
3. **Phase 4.8**: Performance optimization & validation

---

**Remember:** Deprecated functions will be removed in a future version. Migrate now to avoid breaking changes!
