# Archive Inventory

**Archive Date:** 2025-01-15  
**Total Files Archived:** 112

## Archive Summary

This archive contains outdated documentation that has been superseded by the new documentation structure in `docs/`.

## Categories Archived

### Migration Documents
- Migration completion reports
- Migration guides
- Comprehensive migration documents

### Phase Completion Reports
- Phase 1-5 validation reports
- Phase implementation progress
- Phase integration reports
- Phase benefits analysis

### Bug Fix Documentation
- Historical bug fixes (all files from `bug_fixes/`)
- Changelogs (all files from `changelog/`)
- Regression test fixes
- JWT and service conflict fixes
- Chart quality fixes
- Pyramiding signal fixes

### Analysis & Investigation Reports
- Order status simplification impact analysis
- Target lowest same value impact
- Verdict calculation analysis
- Dependency analysis
- Impact analysis
- Signal execution analysis

### Implementation Plans
- Unified order monitoring implementation
- Individual service management implementation
- Order status simplification deployment
- Phase-wise implementation plans

### Architecture Documentation (Historical)
- Analysis simplification
- Design issues validation
- Design analysis and recommendations
- Integrated README (old approach)
- Kotak Neo architecture plans
- Kotak Neo implementation progress
- Unified trading service (superseded by multi-user)
- System architecture evolution

### Deployment Guides (Superseded)
- Windows deployment guides (superseded by Docker)
- Ubuntu deployment guides (superseded by Docker)
- GCP deployment guides
- Phase 2 deployment updates
- Old deployment ready guides

### Getting Started Guides (Superseded)
- Old getting started guide (superseded by `docs/GETTING_STARTED.md`)
- Documentation index (old)
- Documentation reorganization
- All-in-one installer guide

### ML Training Results (Historical)
- Model training results from November 2025
- ML model V4 training results
- ML training data guides (unfiltered, huge data, improvements)

### Testing Documentation (Historical)
- Test suite V2.1
- Test reorganization
- Test organization plans
- Test failures analysis
- Root test files cleanup
- Test coverage summaries
- Order status simplification testing

### Feature Fixes (Historical)
- Backtest integration fixes
- YFinance stale data fixes
- Sell engine fixes
- Sell order retry logic
- Sell order monitoring fixes
- Order rejection tracking
- Order modification implementation
- Rate limiting fixes
- Filtering fixes
- Incomplete candle fixes

### Refactoring Documentation
- Duplicate steps refactoring plans
- Duplicate steps refactoring implementation

### Other Historical Documentation
- Integrated backtest refactor (Nov 2025)
- Data flow backtest
- Weekly data flexible solution
- Pending approval changes
- Alignment score calculation
- Chart quality gap explanation
- Configuration tuning guide
- Backtest errors and warnings analysis
- Backtest run analysis

## Archive Structure

```
archive/
├── documents/
│   ├── bug_fixes/          # Historical bug fixes
│   ├── changelog/          # Historical changelogs
│   ├── analysis/           # Completed analyses
│   ├── investigation/       # Investigation reports
│   ├── testing/            # Historical testing docs
│   ├── deployment/         # Old deployment guides
│   │   ├── windows/        # Windows deployment (superseded)
│   │   ├── ubuntu/         # Ubuntu deployment (superseded)
│   │   └── gcp/            # GCP deployment
│   ├── getting-started/    # Old getting started guides
│   ├── kotak_neo_trader/   # Historical Kotak Neo docs
│   ├── refactoring/        # Refactoring documentation
│   ├── architecture/       # Historical architecture docs
│   ├── features/           # Historical feature fixes
│   └── [root files]        # Various historical docs
├── docs/                   # Old docs structure
└── old_documentation/      # Previous documentation
```

## Why These Files Were Archived

1. **Completed Work** - Documents completed migrations, phases, and implementations
2. **Historical Fixes** - Bug fixes and issues that have been resolved
3. **Superseded Guides** - Replaced by new, consolidated documentation in `docs/`
4. **Outdated Architecture** - Describes old system architecture, not current state
5. **Historical Results** - Training results and test results from past dates
6. **Implementation Plans** - Plans that have been completed

## Current Documentation

For up-to-date documentation, see:
- `docs/README.md` - Documentation index
- `docs/GETTING_STARTED.md` - Setup guide
- `docs/ARCHITECTURE.md` - Current architecture
- `docs/API.md` - API reference
- `docs/USER_GUIDE.md` - User guide
- `docs/DEPLOYMENT.md` - Deployment guide
- `docker/README.md` - Docker guide

## Note

These files are kept for historical reference only. Do not use them for current development or deployment. All current documentation is in the `docs/` folder.

