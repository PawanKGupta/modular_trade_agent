# Commands to Archive Outdated Documentation

Run these commands to move outdated documentation to `archive/`.

## Step 1: Create Archive Directories

```powershell
New-Item -ItemType Directory -Path "archive\documents\bug_fixes" -Force
New-Item -ItemType Directory -Path "archive\documents\changelog" -Force
New-Item -ItemType Directory -Path "archive\documents\analysis" -Force
New-Item -ItemType Directory -Path "archive\documents\investigation" -Force
New-Item -ItemType Directory -Path "archive\documents\testing" -Force
New-Item -ItemType Directory -Path "archive\documents\deployment\windows" -Force
New-Item -ItemType Directory -Path "archive\documents\deployment\ubuntu" -Force
New-Item -ItemType Directory -Path "archive\documents\deployment\gcp" -Force
New-Item -ItemType Directory -Path "archive\documents\getting-started" -Force
New-Item -ItemType Directory -Path "archive\documents\kotak_neo_trader" -Force
New-Item -ItemType Directory -Path "archive\documents\refactoring" -Force
New-Item -ItemType Directory -Path "archive\documents\architecture" -Force
New-Item -ItemType Directory -Path "archive\documents\features" -Force
```

## Step 2: Archive Bug Fixes and Changelogs

```powershell
Move-Item -Path "documents\bug_fixes\*" -Destination "archive\documents\bug_fixes\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\changelog\*" -Destination "archive\documents\changelog\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\CHANGES_2025_11_09_CONSOLIDATED.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\REGRESSION_TEST_FIX_2025_11_09.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\REGRESSION_TEST_FIX_NOV_2025.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\JWT_EXPIRY_AND_SERVICE_CONFLICTS_FIX.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\CHART_QUALITY_BACKTEST_DATA_LEAK_FIX.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\PYRAMIDING_SIGNAL_LABELING_FIX.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
```

## Step 3: Archive Analysis and Investigation

```powershell
Move-Item -Path "documents\analysis\*" -Destination "archive\documents\analysis\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\investigation\*" -Destination "archive\documents\investigation\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\HINDUNILVR_SIGNAL_EXECUTION_ANALYSIS.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\VERDICT_CALCULATION_ANALYSIS_AND_IMPROVEMENTS.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\VERDICT_CALCULATION_EXPLANATION.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\VERDICT_WATCH_ANALYSIS.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\IMPACT_ANALYSIS_ALL_FIXES.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\DEPENDENCY_ANALYSIS_ALL_FIXES.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
```

## Step 4: Archive Implementation Plans

```powershell
Move-Item -Path "documents\features\UNIFIED_ORDER_MONITORING_IMPLEMENTATION_PLAN.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\UNIFIED_ORDER_MONITORING_IMPLEMENTATION_SUMMARY.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\INDIVIDUAL_SERVICE_MANAGEMENT_IMPLEMENTATION_PLAN.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\deployment\ORDER_STATUS_SIMPLIFICATION_DEPLOYMENT.md" -Destination "archive\documents\deployment\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\deployment\ORDER_STATUS_SIMPLIFICATION_DEPLOYMENT_SUMMARY.md" -Destination "archive\documents\deployment\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\deployment\ORDER_STATUS_SIMPLIFICATION_MONITORING.md" -Destination "archive\documents\deployment\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\testing\ORDER_STATUS_SIMPLIFICATION_*" -Destination "archive\documents\testing\" -Force -ErrorAction SilentlyContinue
```

## Step 5: Archive Old Architecture Docs

```powershell
Move-Item -Path "documents\architecture\ANALYSIS_SIMPLIFICATION.md" -Destination "archive\documents\architecture\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\architecture\DESIGN_ISSUES_VALIDATION_REPORT.md" -Destination "archive\documents\architecture\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\architecture\DESIGN_ANALYSIS_AND_RECOMMENDATIONS.md" -Destination "archive\documents\architecture\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\architecture\INTEGRATED_README.md" -Destination "archive\documents\architecture\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\architecture\KOTAK_NEO_ARCHITECTURE_PLAN.md" -Destination "archive\documents\architecture\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\architecture\KOTAK_NEO_IMPLEMENTATION_PROGRESS.md" -Destination "archive\documents\architecture\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\architecture\UNIFIED_TRADING_SERVICE.md" -Destination "archive\documents\architecture\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\SYSTEM_ARCHITECTURE_EVOLUTION.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
```

## Step 6: Archive Old Deployment Guides

```powershell
Move-Item -Path "documents\deployment\windows\DEPLOYMENT_UPDATE_PHASE2.md" -Destination "archive\documents\deployment\windows\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\deployment\DEPLOYMENT_READY.md" -Destination "archive\documents\deployment\" -Force -ErrorAction SilentlyContinue
# Keep oracle deployment for now, archive others if needed
```

## Step 7: Archive Old Getting Started

```powershell
Move-Item -Path "documents\getting-started\GETTING_STARTED.md" -Destination "archive\documents\getting-started\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\getting-started\DOCUMENTATION_INDEX.md" -Destination "archive\documents\getting-started\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\getting-started\DOCUMENTATION_REORGANIZATION.md" -Destination "archive\documents\getting-started\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\getting-started\ALL_IN_ONE_INSTALLER_GUIDE.md" -Destination "archive\documents\getting-started\" -Force -ErrorAction SilentlyContinue
```

## Step 8: Archive Historical ML Training Results

```powershell
Move-Item -Path "documents\ML_MODEL_TRAINING_RESULTS_20251112.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\ML_MODEL_V4_TRAINING_RESULTS_20251113.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\ML_TRAINING_DATA_UNFILTERED.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\ML_TRAINING_HUGE_DATA.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\ML_TRAINING_DATA_IMPROVEMENTS.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
```

## Step 9: Archive Historical Testing Docs

```powershell
Move-Item -Path "documents\testing\TEST_YESBANK_BUY.md" -Destination "archive\documents\testing\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\testing\TEST_SUITE_V2_1.md" -Destination "archive\documents\testing\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\testing\TEST_REORGANIZATION_COMPLETE.md" -Destination "archive\documents\testing\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\testing\TEST_ORGANIZATION_PLAN.md" -Destination "archive\documents\testing\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\testing\TEST_FAILURES_ANALYSIS.md" -Destination "archive\documents\testing\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\testing\ROOT_TEST_FILES_CLEANUP_COMPLETE.md" -Destination "archive\documents\testing\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\test_coverage_summary.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\TEST_FIX_DATA_AVAILABILITY.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
```

## Step 10: Archive Historical Feature Fixes

```powershell
Move-Item -Path "documents\features\BACKTEST_INTEGRATION_FIX.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\YFINANCE_STALE_DATA_FIX.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\SELL_ENGINE_FIXES.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\SELL_ORDER_RETRY_LOGIC.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\SELL_ORDER_MONITORING_FIX.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\ORDER_REJECTION_TRACKING_ISSUE.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\ORDER_MODIFICATION_IMPLEMENTATION.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\RATE_LIMITING_FIX_ANALYSIS.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\FILTERING_FIX.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\features\FIX_INCOMPLETE_CANDLE.md" -Destination "archive\documents\features\" -Force -ErrorAction SilentlyContinue
```

## Step 11: Archive Refactoring Docs

```powershell
Move-Item -Path "documents\refactoring\DUPLICATE_STEPS_REFACTORING_PLAN.md" -Destination "archive\documents\refactoring\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\refactoring\DUPLICATE_STEPS_REFACTORING_IMPLEMENTATION.md" -Destination "archive\documents\refactoring\" -Force -ErrorAction SilentlyContinue
```

## Step 12: Archive Other Historical Docs

```powershell
Move-Item -Path "documents\INTEGRATED_BACKTEST_REFACTOR_NOV_2025.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\DATA_FLOW_BACKTEST.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\WEEKLY_DATA_FLEXIBLE_SOLUTION.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\PENDING_APPROVAL_CHANGES.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\ALIGNMENT_SCORE_CALCULATION.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\CHART_QUALITY_GAP_EXPLANATION.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\CONFIGURATION_TUNING_GUIDE.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\BACKTEST_ERRORS_WARNINGS_ANALYSIS.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\BACKTEST_RUN_ANALYSIS.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\BACKTEST_RUN_ANALYSIS_LATEST.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "documents\BACKTEST_WARNINGS_ANALYSIS.md" -Destination "archive\documents\" -Force -ErrorAction SilentlyContinue
```

## Verify Archive

```powershell
Get-ChildItem -Path "archive\documents" -Recurse -File | Measure-Object | Select-Object Count
```
