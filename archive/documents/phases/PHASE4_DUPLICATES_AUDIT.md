# Phase 4.6: Duplicate Functionality Audit

**Date:** 2025-11-02  
**Status:** In Progress  
**Priority:** High

---

## Duplicate Services Identified

### 1. ScoringService (DUPLICATE) ⚠️

**Locations:**
- `services/scoring_service.py` - Phase 4 version (primary)
- `src/application/services/scoring_service.py` - Older src/ version (duplicate)

**Usage:**
- `services/scoring_service.py` - Used by `trade_agent.py`, Phase 4 services
- `src/application/services/scoring_service.py` - Used by:
  - `src/application/use_cases/analyze_stock.py`
  - `src/application/use_cases/bulk_analyze.py`
  - `src/infrastructure/di_container.py`
  - `tests/unit/services/test_scoring_service.py`
  - `tests/performance/test_services_performance.py`

**Action:** Consolidate - Update `src/application/services/scoring_service.py` to import from `services.scoring_service`

---

## Consolidation Strategy

### Strategy 1: Re-export (Recommended)
Make `src/application/services/scoring_service.py` import from `services/scoring_service.py`:

```python
# src/application/services/scoring_service.py
"""
Scoring Service (Re-export)

This module re-exports ScoringService from services package for backward compatibility
with src/ application layer code.

Phase 4: Consolidated to services/scoring_service.py
"""

from services.scoring_service import ScoringService

__all__ = ['ScoringService']
```

**Benefits:**
- No breaking changes
- Single source of truth
- Clean consolidation

---

### Strategy 2: Direct Import Update
Update all `src/` imports to use `services.ScoringService` directly:

```python
# Before:
from ..services.scoring_service import ScoringService

# After:
from services import ScoringService
```

**Benefits:**
- Cleaner imports
- Single import path
- Better consistency

**Drawback:**
- Requires updating multiple files

---

## Action Plan

1. ✅ **Consolidate ScoringService** - Make src/ version import from services/
2. ⏳ **Update test imports** - Update test files to use services/
3. ⏳ **Check for other duplicates** - Review other services
4. ⏳ **Remove unused code** - Identify and remove dead code
