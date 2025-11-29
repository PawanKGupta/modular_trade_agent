# Documents Folder Review

**Date:** 2025-01-15
**Purpose:** Identify outdated documentation in `documents/` folder

## Analysis Summary

After reviewing 177+ files in `documents/`, here's the categorization:

## ✅ Keep (Current/Useful)

### Core Feature Documentation
- `paper_trading/README.md` - Current paper trading guide
- `paper_trading/SETUP.md` - Paper trading setup
- `paper_trading/USAGE.md` - Paper trading usage
- `backtest/README.md` - Backtest system documentation
- `features/CHART_QUALITY_AND_CAPITAL_ADJUSTMENT.md` - Current feature
- `features/TWO_STAGE_CHART_QUALITY_ML_APPROACH.md` - Current feature
- `features/SERVICE_STATUS_AND_TRADING_CONFIG_UI.md` - Current UI feature
- `features/INDIVIDUAL_SERVICE_MANAGEMENT_USER_GUIDE.md` - Current feature

### Architecture (May be Current)
- `architecture/SERVICE_ARCHITECTURE.md` - May still be relevant
- `architecture/ML_INTEGRATION_GUIDE.md` - ML integration info
- `architecture/ML_TRAINING_WORKFLOW.md` - ML training workflow

### Deployment (Review Needed)
- `deployment/oracle/ORACLE_CLOUD_DEPLOYMENT.md` - May still be useful
- `deployment/HEALTH_CHECK.md` - Health check info
- `deployment/BACKUP_RESTORE_UNINSTALL_GUIDE.md` - Useful reference

### Reference
- `reference/COMMANDS.md` - CLI commands reference
- `reference/VERSION_MANAGEMENT.md` - Version management

### Security
- `security/TOKEN_SECURITY.md` - Security documentation

## ⚠️ Archive (Outdated/Historical)

### Bug Fix Documentation (Historical)
- `bug_fixes/*` - All bug fix documents (historical, already fixed)
- `changelog/*` - Historical changelogs
- `CHANGES_2025_11_09_CONSOLIDATED.md` - Historical changes
- `REGRESSION_TEST_FIX_2025_11_09.md` - Historical fix
- `REGRESSION_TEST_FIX_NOV_2025.md` - Historical fix
- `JWT_EXPIRY_AND_SERVICE_CONFLICTS_FIX.md` - Historical fix
- `CHART_QUALITY_BACKTEST_DATA_LEAK_FIX.md` - Historical fix
- `PYRAMIDING_SIGNAL_LABELING_FIX.md` - Historical fix

### Analysis Reports (Completed)
- `analysis/*` - All analysis documents (completed analyses)
- `investigation/*` - Investigation reports (completed)
- `HINDUNILVR_SIGNAL_EXECUTION_ANALYSIS.md` - Historical analysis
- `VERDICT_CALCULATION_ANALYSIS_AND_IMPROVEMENTS.md` - Historical
- `VERDICT_CALCULATION_EXPLANATION.md` - May be outdated
- `VERDICT_WATCH_ANALYSIS.md` - Historical analysis
- `IMPACT_ANALYSIS_ALL_FIXES.md` - Historical
- `DEPENDENCY_ANALYSIS_ALL_FIXES.md` - Historical

### Implementation Plans (Completed)
- `features/UNIFIED_ORDER_MONITORING_IMPLEMENTATION_PLAN.md` - Completed
- `features/UNIFIED_ORDER_MONITORING_IMPLEMENTATION_SUMMARY.md` - Completed
- `features/INDIVIDUAL_SERVICE_MANAGEMENT_IMPLEMENTATION_PLAN.md` - Completed
- `deployment/ORDER_STATUS_SIMPLIFICATION_DEPLOYMENT.md` - Completed
- `deployment/ORDER_STATUS_SIMPLIFICATION_DEPLOYMENT_SUMMARY.md` - Completed
- `deployment/ORDER_STATUS_SIMPLIFICATION_MONITORING.md` - Completed
- `testing/ORDER_STATUS_SIMPLIFICATION_*` - Completed testing docs

### Old Architecture Docs (Superseded)
- `architecture/ANALYSIS_SIMPLIFICATION.md` - Historical
- `architecture/DESIGN_ISSUES_VALIDATION_REPORT.md` - Historical
- `architecture/DESIGN_ANALYSIS_AND_RECOMMENDATIONS.md` - Historical
- `architecture/INTEGRATED_README.md` - Old approach (per documents/README.md)
- `architecture/KOTAK_NEO_ARCHITECTURE_PLAN.md` - Historical plan
- `architecture/KOTAK_NEO_IMPLEMENTATION_PROGRESS.md` - Historical
- `architecture/UNIFIED_TRADING_SERVICE.md` - Historical (superseded by multi-user)
- `SYSTEM_ARCHITECTURE_EVOLUTION.md` - Historical evolution

### Old Deployment Guides (Superseded by Docker)
- `deployment/windows/*` - Most Windows deployment guides (superseded by Docker)
- `deployment/ubuntu/*` - Most Ubuntu guides (superseded by Docker)
- `deployment/gcp/*` - GCP deployment (may be outdated)
- `deployment/DEPLOYMENT_READY.md` - Old deployment guide
- `deployment/windows/DEPLOYMENT_UPDATE_PHASE2.md` - Historical

### Old Getting Started (Superseded)
- `getting-started/GETTING_STARTED.md` - Old guide (superseded by docs/GETTING_STARTED.md)
- `getting-started/DOCUMENTATION_INDEX.md` - Old index
- `getting-started/DOCUMENTATION_REORGANIZATION.md` - Historical
- `getting-started/ALL_IN_ONE_INSTALLER_GUIDE.md` - Old installer guide
- `getting-started/WINDOWS_EXECUTABLE_GUIDE.md` - May be outdated

### ML Training Results (Historical)
- `ML_MODEL_TRAINING_RESULTS_20251112.md` - Historical results
- `ML_MODEL_V4_TRAINING_RESULTS_20251113.md` - Historical results
- `ML_TRAINING_DATA_UNFILTERED.md` - Historical
- `ML_TRAINING_HUGE_DATA.md` - Historical
- `ML_TRAINING_DATA_IMPROVEMENTS.md` - Historical

### Testing Documentation (Historical)
- `testing/TEST_YESBANK_BUY.md` - Historical test
- `testing/TEST_SUITE_V2_1.md` - Historical
- `testing/TEST_REORGANIZATION_COMPLETE.md` - Historical
- `testing/TEST_ORGANIZATION_PLAN.md` - Historical
- `testing/TEST_FAILURES_ANALYSIS.md` - Historical
- `testing/ROOT_TEST_FILES_CLEANUP_COMPLETE.md` - Historical
- `test_coverage_summary.md` - Historical summary

### Feature Fixes (Historical)
- `features/BACKTEST_INTEGRATION_FIX.md` - Historical fix (pre-refactor)
- `features/YFINANCE_STALE_DATA_FIX.md` - Historical fix
- `features/SELL_ENGINE_FIXES.md` - Historical fixes
- `features/SELL_ORDER_RETRY_LOGIC.md` - Historical
- `features/SELL_ORDER_MONITORING_FIX.md` - Historical
- `features/ORDER_REJECTION_TRACKING_ISSUE.md` - Historical
- `features/ORDER_MODIFICATION_IMPLEMENTATION.md` - Historical
- `features/RATE_LIMITING_FIX_ANALYSIS.md` - Historical
- `features/RATE_LIMITING_CONFIGURATION.md` - May be current, review
- `features/FILTERING_FIX.md` - Historical
- `features/FIX_INCOMPLETE_CANDLE.md` - Historical

### Kotak Neo Trader (Review Needed)
- `kotak_neo_trader/*` - Most files may be outdated, review individually
- `kotak_neo_trader/KOTAK_TEMP_CLEANUP_*` - Historical cleanup docs

### Refactoring (Historical)
- `refactoring/DUPLICATE_STEPS_REFACTORING_PLAN.md` - Historical
- `refactoring/DUPLICATE_STEPS_REFACTORING_IMPLEMENTATION.md` - Historical
- `refactoring/SERVICES_USAGE_GUIDE.md` - May be outdated

### Other Historical
- `INTEGRATED_BACKTEST_REFACTOR_NOV_2025.md` - Recent but may be historical now
- `DATA_FLOW_BACKTEST.md` - May be outdated
- `CONFIGURATION_TUNING_GUIDE.md` - May be outdated
- `ALIGNMENT_SCORE_CALCULATION.md` - May be outdated
- `CHART_QUALITY_GAP_EXPLANATION.md` - May be outdated
- `WEEKLY_DATA_FLEXIBLE_SOLUTION.md` - Historical solution
- `TEST_FIX_DATA_AVAILABILITY.md` - Historical
- `PENDING_APPROVAL_CHANGES.md` - Historical
- `KNOWN_ISSUES.md` - May be outdated, review

## 📋 Recommended Actions

### Immediate Archive (High Confidence)
1. All `bug_fixes/` files
2. All `changelog/` files
3. All `analysis/` files
4. All `investigation/` files
5. All implementation plans in `features/` and `deployment/`
6. Old getting started guides
7. Historical ML training results
8. Historical testing documentation

### Review Before Archiving (Medium Confidence)
1. `deployment/oracle/` - May still be useful
2. `kotak_neo_trader/` - Review individually
3. `architecture/` - Some may be current
4. Feature documentation - Some may be current

### Keep (Low Confidence to Archive)
1. `paper_trading/` - Current feature
2. `backtest/README.md` - Current system
3. `reference/` - May be useful
4. `security/` - Security docs

## Commands to Archive

See next section for PowerShell commands to move files to archive.
