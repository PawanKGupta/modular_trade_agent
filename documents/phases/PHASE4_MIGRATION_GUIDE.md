# Phase 4: Migration Guide - From core.* to Services

**Date:** 2025-11-02  
**Status:** Active  
**Version:** Phase 4

---

## Overview

This guide helps migrate code from legacy `core.*` modules to the new service layer. All `core.*` functions are **deprecated** in Phase 4 and will be removed in a future version.

---

## Migration Map

### Core Analysis Functions

| Legacy Function | Service Replacement | Status |
|----------------|---------------------|--------|
| `core.analysis.analyze_ticker()` | `services.AnalysisService.analyze_ticker()` | ✅ Available |
| `core.analysis.analyze_multiple_tickers()` | `services.AsyncAnalysisService.analyze_batch_async()` | ✅ Available |
| `core.analysis.calculate_smart_buy_range()` | `services.VerdictService.calculate_trading_parameters()` | ✅ Available |
| `core.analysis.calculate_smart_stop_loss()` | `services.VerdictService.calculate_trading_parameters()` | ✅ Available |
| `core.analysis.calculate_smart_target()` | `services.VerdictService.calculate_trading_parameters()` | ✅ Available |

### Core Scoring Functions

| Legacy Function | Service Replacement | Status |
|----------------|---------------------|--------|
| `core.scoring.compute_strength_score()` | `services.ScoringService.compute_strength_score()` | ✅ Available |

### Core Backtest Functions

| Legacy Function | Service Replacement | Status |
|----------------|---------------------|--------|
| `core.backtest_scoring.add_backtest_scores_to_results()` | `services.BacktestService.add_backtest_scores_to_results()` | ✅ Available |
| `core.backtest_scoring.run_stock_backtest()` | `services.BacktestService.run_stock_backtest()` | ✅ Available |
| `core.backtest_scoring.calculate_backtest_score()` | `services.BacktestService.calculate_backtest_score()` | ✅ Available |

---

## Detailed Migration Examples

### 1. Single Ticker Analysis

**OLD (deprecated):**
```python
from core.analysis import analyze_ticker

result = analyze_ticker(
    ticker="RELIANCE.NS",
    enable_multi_timeframe=True,
    export_to_csv=False
)
```

**NEW (recommended):**
```python
from services import AnalysisService

service = AnalysisService()
result = service.analyze_ticker(
    ticker="RELIANCE.NS",
    enable_multi_timeframe=True,
    export_to_csv=False
)
```

**Benefits:**
- ✅ Better testability (dependency injection)
- ✅ Type safety with typed models (Phase 2)
- ✅ Async support available (Phase 2)
- ✅ Pipeline pattern available (Phase 3)
- ✅ Event-driven architecture (Phase 3)

---

### 2. Multiple Ticker Analysis (Batch)

**OLD (deprecated):**
```python
from core.analysis import analyze_multiple_tickers

results, csv_file = analyze_multiple_tickers(
    tickers=["RELIANCE.NS", "TCS.NS", "INFY.NS"],
    enable_multi_timeframe=True,
    export_to_csv=True
)
```

**NEW (recommended):**
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
- ✅ **80% faster** - Parallel processing
- ✅ Better error handling per ticker
- ✅ Progress tracking
- ✅ Async/await support

---

### 3. Strength Score Calculation

**OLD (deprecated):**
```python
from core.scoring import compute_strength_score

score = compute_strength_score(analysis_result)
```

**NEW (recommended):**
```python
from services import ScoringService

service = ScoringService()
score = service.compute_strength_score(analysis_result)

# Also available: priority scoring
priority = service.compute_trading_priority_score(analysis_result)

# Combined scoring
combined = service.compute_combined_score(
    current_score=score,
    backtest_score=backtest_score,
    current_weight=0.5,
    backtest_weight=0.5
)
```

**Benefits:**
- ✅ Service layer benefits
- ✅ Additional methods available
- ✅ Dependency injection ready

---

### 4. Backtest Scoring

**OLD (deprecated):**
```python
from core.backtest_scoring import add_backtest_scores_to_results

enhanced_results = add_backtest_scores_to_results(
    stock_results=results,
    years_back=2,
    dip_mode=False
)
```

**NEW (recommended):**
```python
from services import BacktestService

service = BacktestService(default_years_back=2, dip_mode=False)
enhanced_results = service.add_backtest_scores_to_results(results)

# Or with custom parameters:
enhanced_results = service.add_backtest_scores_to_results(
    results,
    years_back=3,  # Override default
    dip_mode=True   # Override default
)
```

**Benefits:**
- ✅ Configurable defaults
- ✅ Better error handling
- ✅ Service layer benefits

---

### 5. Trading Parameters Calculation

**OLD (deprecated):**
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

**NEW (recommended):**
```python
from services import VerdictService

service = VerdictService()
trading_params = service.calculate_trading_parameters(
    current_price=current_price,
    verdict=verdict,
    recent_low=recent_low,
    recent_high=recent_high,
    timeframe_confirmation=timeframe_confirmation,
    df=df
)

# Access results:
buy_range = trading_params['buy_range']
stop = trading_params['stop_loss']
target = trading_params['target']
risk_reward = trading_params['risk_reward_ratio']
```

**Benefits:**
- ✅ Single method call (simpler)
- ✅ Returns complete trading parameters
- ✅ Calculates risk-reward ratio automatically
- ✅ Consistent parameter calculation

---

## Pipeline Pattern (Phase 3)

**NEW: Pipeline-based analysis (advanced):**
```python
from services import create_analysis_pipeline

# Create pipeline
pipeline = create_analysis_pipeline(
    enable_fundamentals=False,
    enable_multi_timeframe=True
)

# Execute pipeline
context = pipeline.execute("RELIANCE.NS")

# Access results
verdict = context.results['verdict']
trading_params = context.results.get('trading_params')
signals = context.results.get('signals', [])

print(f"Verdict: {verdict}")
print(f"Buy Range: {trading_params['buy_range']}")
```

**Benefits:**
- ✅ Pluggable steps (add/remove/reorder)
- ✅ Event-driven (subscribe to events)
- ✅ Better observability
- ✅ Easy to extend

---

## Event-Driven Architecture (Phase 3)

**NEW: Subscribe to analysis events:**
```python
from services import get_event_bus, EventType
from services.event_bus import Event

bus = get_event_bus()

# Subscribe to events
def on_analysis_complete(event: Event):
    ticker = event.data['ticker']
    verdict = event.data['verdict']
    print(f"Analysis complete: {ticker} -> {verdict}")

def on_signal_detected(event: Event):
    ticker = event.data['ticker']
    signal = event.data['signal']
    print(f"Signal detected for {ticker}: {signal}")

bus.subscribe(EventType.ANALYSIS_COMPLETED, on_analysis_complete)
bus.subscribe(EventType.SIGNAL_DETECTED, on_signal_detected)

# Run analysis - events are automatically published
from services import AnalysisService
service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")
```

---

## Deprecation Warnings

When using deprecated functions, you'll see warnings like:

```
DeprecationWarning: DEPRECATED: core.analysis.analyze_ticker() is deprecated in Phase 4.
Replacement: services.AnalysisService.analyze_ticker() or services.AsyncAnalysisService.analyze_batch_async()
Will be removed in a future version.
```

**To suppress warnings (not recommended):**
```python
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
```

**Recommended:** Migrate to new services instead of suppressing warnings.

---

## Migration Checklist

- [ ] Replace `core.analysis.analyze_ticker()` → `services.AnalysisService`
- [ ] Replace `core.analysis.analyze_multiple_tickers()` → `services.AsyncAnalysisService`
- [ ] Replace `core.scoring.compute_strength_score()` → `services.ScoringService`
- [ ] Replace `core.backtest_scoring.add_backtest_scores_to_results()` → `services.BacktestService`
- [ ] Replace `core.analysis.calculate_smart_*()` → `services.VerdictService.calculate_trading_parameters()`
- [ ] Test migrated code
- [ ] Remove old imports
- [ ] Update documentation

---

## Common Issues & Solutions

### Issue 1: Import Errors

**Problem:** `ImportError: cannot import name 'AnalysisService' from 'services'`

**Solution:** Ensure you're using the latest version:
```python
# Correct:
from services import AnalysisService

# Or:
from services.analysis_service import AnalysisService
```

### Issue 2: Function Signature Differences

**Problem:** Service methods have slightly different signatures

**Solution:** Check service documentation. Most maintain backward compatibility:
```python
# Old signature:
analyze_ticker(ticker, enable_multi_timeframe=True, export_to_csv=False)

# New signature (same):
service.analyze_ticker(ticker, enable_multi_timeframe=True, export_to_csv=False)
```

### Issue 3: Async Functions

**Problem:** Async services require `await` and `asyncio.run()`

**Solution:** Wrap in async function:
```python
import asyncio

async def main():
    from services import AsyncAnalysisService
    service = AsyncAnalysisService()
    results = await service.analyze_batch_async(tickers=["RELIANCE.NS"])
    return results

results = asyncio.run(main())
```

---

## Timeline

**Current Status:** Phase 4 (Deprecation phase)
- ✅ All core.* functions marked as deprecated
- ✅ Migration warnings active
- ✅ Service replacements available

**Future:**
- Phase 4.6: Remove duplicate functionality
- Phase 4.7: Update documentation
- Phase 4.8: Final validation
- **Future Version:** Remove deprecated `core.*` functions

---

## Support

For migration assistance:
1. Check this guide
2. Review service documentation in `services/`
3. See examples in `scripts/`
4. Review Phase 1-3 completion docs

---

## Related Documents

- `documents/phases/PHASE1_COMPLETE.md` - Service layer foundation
- `documents/phases/PHASE2_COMPLETE.md` - Async & caching
- `documents/phases/PHASE3_COMPLETE.md` - Event-driven & pipeline
- `documents/phases/PHASE4_PLAN.md` - Phase 4 plan
- `utils/deprecation.py` - Deprecation utilities

