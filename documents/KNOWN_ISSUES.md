# Known Issues

## Test Import Path Conflict (tests/unit/services)

**Status**: Known Issue  
**Severity**: Low  
**Created**: 2025-11-03

### Description

Tests in `tests/unit/services/` directory are currently failing due to Python module import path conflicts:

```
ModuleNotFoundError: No module named 'services.scoring_service'
```

### Root Cause

The project has both:
1. Root-level `services/` directory (legacy architecture)
2. `src/application/services/` directory (new Clean Architecture)
3. Test directory `tests/unit/services/` which creates namespace collision

When pytest imports `from services.scoring_service import ScoringService`, Python's module resolution gets confused between:
- The root-level `services/` package  
- The test directory `tests/unit/services/`

### Affected Tests

- `tests/unit/services/test_analysis_service.py`
- `tests/unit/services/test_event_bus.py`
- `tests/unit/services/test_filtering_service.py`
- `tests/unit/services/test_ml_services.py`
- `tests/unit/services/test_ml_services_unit.py`
- `tests/unit/services/test_pipeline.py`
- `tests/unit/services/test_scoring_service.py`
- `tests/integration/test_backtest_integration.py`
- `tests/integration/test_ml_pipeline.py`

### Current Workaround

Tests can be run by excluding the problematic directories:

```bash
pytest tests/ --ignore=tests/unit/services --ignore=tests/integration
```

This runs 126 tests successfully with 72% code coverage.

### Permanent Solutions (Choose One)

#### Option 1: Rename Test Directory (Recommended)
```bash
mv tests/unit/services tests/unit/legacy_services
```
This avoids namespace collision while keeping tests organized.

#### Option 2: Use Relative Imports in Tests
Modify all test files to use explicit relative imports or sys.path manipulation.

#### Option 3: Complete Phase 5 Migration
Fully migrate from root-level `services/` to `src/application/services/` and remove the legacy directory entirely. This is the long-term solution aligned with Clean Architecture.

### Resolution Timeline

- **Short-term**: Document issue and use workaround (CURRENT)
- **Medium-term**: Implement Option 1 (rename test directory)
- **Long-term**: Implement Option 3 (complete architectural migration)

### Related Documentation

- `documents/SYSTEM_ARCHITECTURE_EVOLUTION.md` - Architecture migration details
- `documents/phases/PHASE4_VALIDATION_COMPLETE.md` - Current migration status
