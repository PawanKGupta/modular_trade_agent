# Phase 4: Pending Tasks

**Date:** 2025-01-15
**Status:** Phase 4.1-4.4 Complete, Phase 4.5-4.8 Pending
**Progress:** 50% (4/8 tasks complete)

---

## ✅ Completed Tasks

| Task | Status | Details |
|------|--------|---------|
| **Phase 4.1** | ✅ Complete | Analysis & Migration Map |
| **Phase 4.2** | ✅ Complete | Create Missing Services (ScoringService, BacktestService) |
| **Phase 4.3** | ✅ Complete | Update trade_agent.py to use new services |
| **Phase 4.4** | ✅ Complete | Update Service Imports to Use Infrastructure |

---

## ⏳ Pending Tasks

### Phase 4.5: Deprecate Legacy Code

**Status:** ⏳ Pending
**Priority:** Medium
**Estimated Effort:** 2-3 days

#### Tasks:
1. **Add deprecation warnings to `core.*` functions**
   - Add `DeprecationWarning` to all `core.*` functions that have service equivalents
   - Use `warnings.warn()` with appropriate messages
   - Include migration instructions in warning messages
   - Set `stacklevel=2` to show caller location

2. **Update `core/analysis.py`**
   - Remove legacy implementation
   - Keep wrapper only (delegates to service layer)
   - Maintain backward compatibility

3. **Create migration guide**
   - Document all `core.*` functions that are deprecated
   - Provide service layer equivalents
   - Include code examples for migration
   - Add to documentation

#### Files to Update:
- `core/analysis.py` - Remove legacy, keep wrapper
- `core/scoring.py` - Add deprecation warnings
- `core/backtest_scoring.py` - Add deprecation warnings
- `core/data_fetcher.py` - Add deprecation warnings (if applicable)
- `core/indicators.py` - Add deprecation warnings (if applicable)
- `core/patterns.py` - Add deprecation warnings (if applicable)
- `core/timeframe_analysis.py` - Add deprecation warnings (if applicable)

#### Example Implementation:
```python
import warnings
from services import AnalysisService

def analyze_ticker(ticker, **kwargs):
    """
    Analyze a ticker (DEPRECATED).

    .. deprecated:: 2025-01-15
        Use :class:`AnalysisService` instead.
        Example: AnalysisService().analyze_ticker(ticker, **kwargs)
    """
    warnings.warn(
        "analyze_ticker() is deprecated. Use AnalysisService().analyze_ticker() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    service = AnalysisService()
    return service.analyze_ticker(ticker, **kwargs)
```

---

### Phase 4.6: Remove Duplicate Functionality

**Status:** ⏳ Pending
**Priority:** Medium
**Estimated Effort:** 3-5 days

#### Tasks:
1. **Identify duplicates**
   - Search for duplicate functionality between `core/` and `services/`
   - Search for duplicate functionality between `core/` and `src/`
   - Create inventory of duplicates
   - Document which implementation to keep

2. **Consolidate implementations**
   - Choose best implementation (usually service layer)
   - Update all references to use consolidated version
   - Remove duplicate code
   - Ensure backward compatibility

3. **Remove unused code**
   - Identify unused functions/classes
   - Remove dead code
   - Clean up imports
   - Update tests

#### Areas to Check:
- Data fetching: `core/data_fetcher.py` vs `services/data_service.py`
- Indicators: `core/indicators.py` vs `services/indicator_service.py`
- Patterns: `core/patterns.py` vs `services/signal_service.py`
- Timeframe analysis: `core/timeframe_analysis.py` vs services
- Scoring: `core/scoring.py` vs `services/scoring_service.py`
- Backtest: `core/backtest_scoring.py` vs `services/backtest_service.py`

#### Tools to Use:
- Code search (grep/ripgrep) to find duplicate logic
- Static analysis tools to find unused code
- Test coverage to identify untested code

---

### Phase 4.7: Update Documentation

**Status:** ⏳ Pending
**Priority:** Low (but important)
**Estimated Effort:** 2-3 days

#### Tasks:
1. **Update README.md**
   - Document new service layer architecture
   - Update quick start to use services
   - Add migration guide link
   - Update project structure diagram

2. **Update architecture docs**
   - Document service layer structure
   - Update architecture diagrams
   - Document service dependencies
   - Add service usage examples

3. **Update getting started guides**
   - Update examples to use services
   - Remove references to deprecated `core.*` functions
   - Add service layer examples

4. **Update API documentation**
   - Document service APIs
   - Add service usage examples
   - Update code examples

#### Files to Update:
- `README.md` - Main project documentation
- `docs/ARCHITECTURE.md` - Architecture documentation
- `docs/GETTING_STARTED.md` - Getting started guide
- `docs/API.md` - API documentation (if applicable)
- Service-specific documentation

#### Documentation Structure:
```
docs/
├── ARCHITECTURE.md (updated)
│   ├── Service Layer Architecture
│   ├── Service Dependencies
│   └── Migration Guide
├── GETTING_STARTED.md (updated)
│   ├── Service Layer Examples
│   └── Migration from core.*
└── MIGRATION_GUIDE.md (new)
    ├── Deprecated Functions
    ├── Service Equivalents
    └── Code Examples
```

---

### Phase 4.8: Performance Optimization & Final Validation

**Status:** ⏳ Pending
**Priority:** High
**Estimated Effort:** 3-5 days

#### Tasks:
1. **Profile code for bottlenecks**
   - Use profiling tools (cProfile, py-spy, etc.)
   - Identify slow functions
   - Measure service layer performance
   - Compare with legacy `core.*` performance

2. **Optimize slow paths**
   - Optimize identified bottlenecks
   - Improve caching strategies
   - Optimize database queries (if applicable)
   - Reduce unnecessary computations

3. **Run comprehensive integration tests**
   - Test all service integrations
   - Test backward compatibility
   - Test migration paths
   - Test performance under load

4. **Validate backward compatibility**
   - Ensure all deprecated functions still work
   - Test that existing code continues to work
   - Verify no breaking changes
   - Test migration scenarios

#### Performance Metrics to Track:
- Service initialization time
- Analysis execution time
- Memory usage
- API call reduction
- Cache hit rates

#### Validation Checklist:
- [ ] All tests passing
- [ ] No performance regression
- [ ] Backward compatibility maintained
- [ ] Documentation complete
- [ ] Migration guide available
- [ ] Deprecation warnings working
- [ ] No duplicate code remaining
- [ ] Code coverage >80%

---

## 📊 Overall Status

| Phase | Status | Progress | Priority |
|-------|--------|----------|----------|
| 4.1 | ✅ Complete | 100% | - |
| 4.2 | ✅ Complete | 100% | - |
| 4.3 | ✅ Complete | 100% | - |
| 4.4 | ✅ Complete | 100% | - |
| **4.5** | ⏳ **Pending** | **0%** | **Medium** |
| **4.6** | ⏳ **Pending** | **0%** | **Medium** |
| **4.7** | ⏳ **Pending** | **0%** | **Low** |
| **4.8** | ⏳ **Pending** | **0%** | **High** |

**Overall Progress: 50% (4/8 tasks complete)**

---

## 🎯 Recommended Order

1. **Phase 4.5** (Deprecate Legacy Code) - Start here
   - Sets foundation for migration
   - Warns users about deprecated code
   - Low risk, high value

2. **Phase 4.6** (Remove Duplicates) - Next
   - Clean up codebase
   - Reduce maintenance burden
   - Medium risk, high value

3. **Phase 4.8** (Performance & Validation) - Then
   - Ensure everything works
   - Optimize performance
   - High priority for production

4. **Phase 4.7** (Update Documentation) - Finally
   - Document all changes
   - Help users migrate
   - Can be done in parallel with 4.8

---

## 📝 Notes

### Current Blockers:
- **Infrastructure Dependencies**: Infrastructure layer (`src/infrastructure/`) still depends on `core.*` modules, creating circular dependencies
- **Solution**: Services are ready for infrastructure injection, but full migration requires making infrastructure independent first

### Migration Path:
1. ✅ Services support infrastructure injection (Phase 4.4 complete)
2. ⏳ Make infrastructure independent of `core.*` (future task)
3. ⏳ Migrate services to use infrastructure exclusively (future task)

### Backward Compatibility:
- All changes maintain backward compatibility
- Deprecated functions delegate to service layer
- No breaking changes expected

---

## 📚 Related Documents

- `archive/documents/phases/PHASE4_PROGRESS.md` - Initial progress
- `archive/documents/phases/PHASE4_PROGRESS_UPDATE.md` - Latest update
- `archive/documents/phases/PHASE4_PLAN.md` - Detailed plan (if exists)
- `docs/MIGRATION_DOCUMENTS_INDEX.md` - Migration documents index

---

**Ready to continue Phase 4? Start with Phase 4.5 (Deprecate Legacy Code)!**
