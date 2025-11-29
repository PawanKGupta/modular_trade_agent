# Service Architecture Guide

**Date:** 2025-01-15 (Updated)  
**Status:** Phase 1-4 Complete + Multi-User System  
**Architecture:** Service-based with multi-user support

---

## Overview

The system uses a **service-based architecture** introduced in Phase 1-4, with **multi-user support** added later, providing:
- ✅ **Modular design** - Single responsibility services
- ✅ **Dependency injection** - Swappable implementations
- ✅ **Async support** - 80% faster batch analysis (Phase 2)
- ✅ **Caching** - Reduces API calls by 70-90% (Phase 2)
- ✅ **Event-driven** - Pluggable event bus (Phase 3)
- ✅ **Pipeline pattern** - Flexible, composable workflow (Phase 3)
- ✅ **Type safety** - Typed data classes (Phase 2)
- ✅ **Multi-user architecture** - Per-user services, configs, and data
- ✅ **Web-based management** - Service control via web UI
- ✅ **Backward compatibility** - Legacy `core.*` still works

---

## Multi-User Architecture

### Per-User Services

Each user has their own:
- **Trading Service**: Per-user unified trading service instance
- **Trading Configuration**: User-specific strategy parameters
- **Paper Trading Portfolio**: Separate virtual portfolio per user
- **Order History**: User-scoped order tracking
- **P&L Tracking**: Individual performance metrics
- **Credentials**: Encrypted broker credentials per user

### Service Management

- **Unified Service**: One service per user, runs all trading tasks
- **Individual Services**: Can run specific tasks independently
- **Web UI Control**: Start/stop services via `/dashboard/service`
- **Conflict Detection**: Prevents conflicts between unified and individual services

### Database Schema

- **Users Table**: User accounts with roles (admin/user)
- **UserSettings Table**: Per-user settings and encrypted credentials
- **UserTradingConfig Table**: Per-user trading configuration
- **ServiceStatus Table**: Per-user service status tracking
- **IndividualServiceStatus Table**: Per-user individual service status

---

## Service Layer Structure

### Phase 1: Core Services (Foundation)

| Service | Responsibility | Status |
|---------|---------------|--------|
| `AnalysisService` | Main orchestrator | ✅ Complete |
| `DataService` | Data fetching | ✅ Complete |
| `IndicatorService` | Technical indicators | ✅ Complete |
| `SignalService` | Signal detection | ✅ Complete |
| `VerdictService` | Verdict determination | ✅ Complete |

**Benefits:**
- ✅ Modular, testable components
- ✅ Clear separation of concerns
- ✅ Dependency injection ready

---

### Phase 2: Performance & Quality

| Service | Responsibility | Status |
|---------|---------------|--------|
| `AsyncAnalysisService` | Async batch analysis | ✅ Complete |
| `AsyncDataService` | Async data fetching | ✅ Complete |
| `CacheService` | Memory-based caching | ✅ Complete |
| `CachedDataService` | Cached data wrapper | ✅ Complete |
| `models.py` | Typed data classes | ✅ Complete |

**Benefits:**
- ✅ **80% faster** batch analysis (25min → 5min for 50 stocks)
- ✅ **70-90% reduction** in API calls
- ✅ Type safety with typed models

---

### Phase 3: Event-Driven & Pipeline

| Component | Responsibility | Status |
|-----------|---------------|--------|
| `EventBus` | Event-driven architecture | ✅ Complete |
| `AnalysisPipeline` | Pipeline orchestrator | ✅ Complete |
| `PipelineSteps` | Pluggable pipeline steps | ✅ Complete |
| `Event` / `EventType` | Event models | ✅ Complete |

**Benefits:**
- ✅ Pluggable event handling
- ✅ Flexible pipeline workflow
- ✅ Easy to extend

---

### Phase 4: Additional Services & Cleanup

| Service | Responsibility | Status |
|---------|---------------|--------|
| `ScoringService` | Signal strength scoring | ✅ Complete |
| `BacktestService` | Backtest integration | ✅ Complete |
| `utils/deprecation.py` | Deprecation utilities | ✅ Complete |

**Benefits:**
- ✅ Service layer consistency
- ✅ Deprecated legacy code
- ✅ Migration guidance

---

## Service Usage Examples

### Basic Analysis (Phase 1)

```python
from services import AnalysisService

service = AnalysisService()
result = service.analyze_ticker(
    ticker="RELIANCE.NS",
    enable_multi_timeframe=True,
    export_to_csv=False
)
```

### Async Batch Analysis (Phase 2)

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

### Pipeline Pattern (Phase 3)

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
```

### Event-Driven (Phase 3)

```python
from services import get_event_bus, EventType
from services.event_bus import Event

bus = get_event_bus()

# Subscribe to events
def on_analysis_complete(event: Event):
    ticker = event.data['ticker']
    verdict = event.data['verdict']
    print(f"Analysis complete: {ticker} -> {verdict}")

bus.subscribe(EventType.ANALYSIS_COMPLETED, on_analysis_complete)

# Run analysis - events automatically published
from services import AnalysisService
service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")
```

### Scoring & Backtest (Phase 4)

```python
from services import ScoringService, BacktestService

# Scoring
scoring_service = ScoringService()
strength_score = scoring_service.compute_strength_score(result)
priority_score = scoring_service.compute_trading_priority_score(result)

# Backtest
backtest_service = BacktestService(default_years_back=2, dip_mode=False)
enhanced_results = backtest_service.add_backtest_scores_to_results([result])
```

---

## Migration from Legacy Code

### Legacy Code (Deprecated)

```python
# ⚠️ DEPRECATED in Phase 4
from core.analysis import analyze_ticker
from core.scoring import compute_strength_score
from core.backtest_scoring import add_backtest_scores_to_results

result = analyze_ticker("RELIANCE.NS")  # Shows deprecation warning
score = compute_strength_score(result)  # Shows deprecation warning
enhanced = add_backtest_scores_to_results([result])  # Shows deprecation warning
```

### Modern Code (Recommended)

```python
# ✅ Recommended (Phase 4)
from services import (
    AnalysisService,
    AsyncAnalysisService,
    ScoringService,
    BacktestService
)

# Single ticker
service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")

# Scoring
scoring = ScoringService()
score = scoring.compute_strength_score(result)

# Backtest
backtest = BacktestService()
enhanced = backtest.add_backtest_scores_to_results([result])
```

**See:** `documents/phases/PHASE4_MIGRATION_GUIDE.md` for detailed migration guide

---

## Service Dependencies

### AnalysisService Dependencies

```
AnalysisService
  ├── DataService (data fetching)
  ├── IndicatorService (indicators)
  ├── SignalService (signal detection)
  ├── VerdictService (verdict determination)
  └── CSVExporter (optional, CSV export)
```

### AsyncAnalysisService Dependencies

```
AsyncAnalysisService
  ├── AsyncDataService (async data fetching)
  ├── AnalysisService (core analysis logic)
  └── CacheService (optional, caching)
```

### ScoringService Dependencies

```
ScoringService
  └── (None - self-contained)
```

### BacktestService Dependencies

```
BacktestService
  ├── ScoringService (combined score calculation)
  └── core.backtest_scoring (legacy backtest functions - will be migrated)
```

---

## Configuration

### Strategy Configuration (Phase 1)

```python
from config.strategy_config import StrategyConfig

# Use defaults
config = StrategyConfig.default()

# Load from environment
config = StrategyConfig.from_env()

# Custom config
config = StrategyConfig(
    rsi_threshold=30.0,
    volume_multiplier=1.2,
    pe_max=50.0,
    backtest_weight=0.5
)
```

---

## Testing Services

### Unit Testing

```python
from services import AnalysisService, DataService

# Mock dependencies for testing
def test_analysis_service():
    mock_data_service = MockDataService()
    service = AnalysisService(data_service=mock_data_service)
    result = service.analyze_ticker("RELIANCE.NS")
    assert result['verdict'] == 'buy'
```

### Integration Testing

```python
from services import AnalysisService

# Use real services for integration tests
def test_integration():
    service = AnalysisService()  # Uses real dependencies
    result = service.analyze_ticker("RELIANCE.NS")
    assert result['status'] == 'success'
```

---

## Performance Metrics

### Phase 2 Async Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Batch Analysis (50 stocks) | 25 min | 5 min | **80% faster** |
| API Calls | 100% | 10-30% | **70-90% reduction** |
| Concurrent Requests | 1 | 10 | **10x parallelization** |

### Phase 2 Caching Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Data Fetch Calls | 100% | 10-30% | **70-90% reduction** |
| Response Time | Variable | Instant (cached) | **Cache hits: 0ms** |

---

## Best Practices

### 1. Use Services Directly

✅ **Recommended:**
```python
from services import AnalysisService
service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")
```

❌ **Deprecated:**
```python
from core.analysis import analyze_ticker  # ⚠️ Deprecated
result = analyze_ticker("RELIANCE.NS")  # Shows warning
```

### 2. Use Async for Batch Operations

✅ **Recommended:**
```python
from services import AsyncAnalysisService
import asyncio

async def analyze():
    service = AsyncAnalysisService(max_concurrent=10)
    return await service.analyze_batch_async(tickers=["RELIANCE.NS", "TCS.NS"])
```

❌ **Slower:**
```python
for ticker in tickers:
    result = analyze_ticker(ticker)  # Sequential, slow
```

### 3. Use Dependency Injection for Testing

✅ **Recommended:**
```python
class AnalysisService:
    def __init__(self, data_service=None):
        self.data_service = data_service or DataService()

# In tests
mock_data = MockDataService()
service = AnalysisService(data_service=mock_data)
```

### 4. Subscribe to Events for Extensibility

✅ **Recommended:**
```python
from services import get_event_bus, EventType

bus = get_event_bus()
bus.subscribe(EventType.ANALYSIS_COMPLETED, my_handler)
```

---

## Related Documents

- `documents/phases/PHASE1_COMPLETE.md` - Phase 1 foundation
- `documents/phases/PHASE2_COMPLETE.md` - Phase 2 async & caching
- `documents/phases/PHASE3_COMPLETE.md` - Phase 3 events & pipeline
- `documents/phases/PHASE4_MIGRATION_GUIDE.md` - Migration guide
- `documents/architecture/DESIGN_ANALYSIS_AND_RECOMMENDATIONS.md` - Original analysis
