# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [26.2.3.1] - 2026-06-22

Hotfix release from branch `hotfix/limit_order_fill_price`. See [docs/development/RELEASE_PLAN_V26.2.3.1.md](docs/development/RELEASE_PLAN_V26.2.3.1.md) for deploy checklist.

### Fixed

- **Paper trading buy limit order fill price:** Buy limit orders now fill at `current_price` (the market price) rather than `order.price` (the limit price) when `current_price <= limit`. The limit price is the worst acceptable price — if the market is cheaper at execution, a real exchange fills at market. Previously, paper buy orders always executed at yesterday's indicator close even when the stock opened lower, overstating entry costs and understating P&L. Sell limit orders (EMA9 targets) are unaffected and continue to fill at `order.price` — the realistic fill path for sells is the daily-high touch check (`try_fill_sell_limit_on_session_high`), not a live price snapshot.

### No Alembic migrations

No database schema changes — `alembic upgrade head` is a no-op.

---

## [26.2.3] - 2026-06-20

Release from branch `releases/rebound_2623`. See [docs/development/RELEASE_PLAN_V26.2.3.md](docs/development/RELEASE_PLAN_V26.2.3.md) for deploy checklist.

### Added

- **ML leakage fixes (Phase 0):** Eliminated forward-looking features, calibration bug, and train/serve feature skew in verdict classifier. Walk-forward validated threshold set to 0.6 (was 0.5).
- **FinBERT + India sentiment overrides:** India-specific red-flag phrases (promoter pledge, SEBI notice, ED/CBI raids, F&O ban, NPA, etc.) now force news sentiment score to -1.0, overriding FinBERT's general-finance misclassification.
- **ML model persistence (Docker):** `trading_models` named volume mounts to `/app/models` in both `docker-compose.yml` and `docker-compose.prod.yml` — activated model artifacts survive container restarts and image rebuilds.
- **ML model auto-seed on first boot:** `api-entrypoint.sh` copies baseline models baked into the image (`/app/models_default/`) into the volume on first boot when the volume is empty. No manual intervention needed on fresh deploys.
- **Activate-and-deploy:** Activating a model version via UI or `POST /api/v1/admin/ml/models/{id}/activate` now copies the versioned artifact to the canonical runtime path (`models/verdict_model_random_forest.pkl`) immediately — no manual file copy required.
- **Register external model:** `POST /api/v1/admin/ml/models/register` endpoint and "Register Existing Model" UI form allow importing externally-trained `.pkl` files into the model registry with optional `auto_activate`.
- **ML help page:** New in-app help page at `/help/ml-signals` covering confidence thresholds, signal lifecycle, walk-forward validation, and tuning options.
- **ML section in Getting Started guide and FAQ.**

### Fixed

- **Stale buy signals after verdict downgrade:** `_persist_analysis_results` previously pre-filtered to `buy`/`strong_buy` only, preventing `deduplicate_and_update_signals` from expiring ACTIVE signals when a stock re-analysed to `watch`/`avoid`. Removed the pre-filter — downgraded verdicts now correctly expire their old signal.
- **ML confidence threshold default:** Frontend `DEFAULT_CONFIG` corrected from 0.7 → 0.6 to match backend default.
- **joblib unpickling failure** and hardcoded market-history cutoff resolved.
- **sklearn 1.8 calibration compatibility** and India VIX stub fixed.
- **Above-threshold ML prediction persistence** and cross-ticker leak prevented.

### Changed

- **ML confidence threshold default:** `ml_confidence_threshold` in `StrategyConfig` and `ML_CONFIDENCE_THRESHOLD` env default raised from 0.5 → 0.6 (walk-forward validated).
- **Trading Config UI:** All config sections now collapsed by default using the same `SectionCard` accordion pattern as Settings — SVG chevron, smooth CSS animation, single-open accordion, proper aria attributes.
- **Notification Preferences UI:** Same `SectionCard` accordion pattern applied to all sections; save action moved to a sticky bottom bar.
- **ML Training UI:** "New Training Job" form collapsed by default; "Register Existing Model" moved to bottom of page.

### No Alembic migrations

No database schema changes in this release — `alembic upgrade head` is a no-op.

---

## [26.2.2.1] - 2026-06-14

Hotfix release from branch `hotfix/rebound_26221`. See [docs/development/RELEASE_PLAN_V26.2.2.1.md](docs/development/RELEASE_PLAN_V26.2.2.1.md) for deploy checklist.

### Fixed

- **MFA QR code display:** Added client-side QR code generation using `qrcode` library to display a scannable QR code on setup.
- **MFA Login Challenge:** Capture and process `mfa_required` responses on login form submission, switching inline to verify the 6-digit authenticator code.
- **Settings Page Accordion:** Grouped User Profile and Trading Account configuration settings into collapsible panels, collapsed by default, to clean up scattered elements.
- **Login Form Polish:** Removed redundant static "Required fields" notice.
- **Unit Test Coverage:** Added unit tests for new MFA views/workflows to satisfy and exceed the 90% test coverage gate.

## [26.2.2] - 2026-06-14

Release from branch `releases/rebound_2622`. See [docs/development/RELEASE_PLAN_V26.2.2.md](docs/development/RELEASE_PLAN_V26.2.2.md) for deploy checklist.

### Added

- **User data security:** Refresh-token rotation with reuse detection, `token_version` session invalidation, optional MFA schema, soft-delete columns, audit logging for auth events; pre-deploy checklist in [USER_DATA_SECURITY.md](docs/security/USER_DATA_SECURITY.md).
- **Signup email allowlist:** Approved provider list at signup and profile email change; `EMAIL_DOMAIN_ALLOWLIST_EXTRA` for corporate domains.
- **Login lockout UX:** Pre-lockout warnings and live countdown from `429 retry_after_seconds`.
- **In-app help center:** Public `/help` onboarding and FAQ (broker-neutral).
- **Trading notifications:** Multi-channel delivery for order events; balance shortfall digest alerts; 9:05 pre-market depth logging and MARKET finalization path.
- **Screener tradability filter:** Unified equity tradability gate before analysis.
- **Service schedules:** Admin-editable buy margin preview and premarket AMO adjustment schedules (DB-backed; redeploy/restart to apply workers).
- **Dev tooling:** Cursor-native dev team workflow docs; cross-platform Graphify MCP launcher.

### Changed

- **Service status notifications:** Off by default; unified IST heartbeat display; hardened start/stop across redeploys.
- **Paper/live parity:** Morning buy staging, re-entry capital sizing, sell qty sync after re-entry fills, cycle-scoped closed-buy sync.
- **OHLCV / NSE:** Bhavcopy ingest and same-day re-entry RSI gated on publish window; skip intraday gap-fill for today before market close.
- **Portfolio limits:** `max_portfolio_size` counts system holdings only.
- **Re-entry guard:** Block duplicate same-day re-entries at the same RSI level.
- **Alembic:** Stale version-row prune instead of wiping migration metadata.

### Fixed

- Session restore on page refresh with httpOnly cookie auth (and dev localStorage path).
- Paper services stopping after redeploy (stale scheduler locks).
- Paper holdings target price from pending sell limit in DB.
- Sell placement blocked when executed buy cached in `OrderStatusVerifier`.
- Re-entry sell resize when broker pending order reports price zero.
- Weekly OHLCV cache rejection on incomplete Yahoo tail bar.
- Playwright E2E auth/session flakes in CI (Bearer-only test API, session-restore waits, single worker).
- Web unit test line coverage restored above 90% threshold.

### Migration

- **Required:** `alembic upgrade head` before starting API (4 revisions since 26.2.1: notification defaults, balance-shortfall prefs, user-data-security schema). Backup Postgres first in production.
- **Review `.env`:** `EMAIL_DOMAIN_ALLOWLIST_*`, `AUTH_COOKIE_SECURE`, `RATE_LIMIT_BACKEND`/`REDIS_URL` for multi-replica API; see [USER_DATA_SECURITY.md](docs/security/USER_DATA_SECURITY.md).

## [26.2.1] - 2026-06-06

Release from branch `releases/rebound_2621`. See [docs/development/RELEASE_PLAN_V26.2.1.md](docs/development/RELEASE_PLAN_V26.2.1.md) for deploy checklist.

### Added

- **Auth & onboarding:** Public signup, hard email verification (login blocked until verified), forgot/reset password, resend verification (72-hour token window), unified auth form validation.
- **Profile:** Self-service email and optional mobile number updates; admin create-user with optional mobile; `PATCH /api/v1/auth/profile`.
- **Billing (performance fees):** User Billing page, admin billing settings, Razorpay credentials (encrypted in DB), performance-fee invoices, offline UPI/QR payment (admin upload), admin cash payment recording, transaction history, reconcile overdue bills.
- **Trading / Kotak:** Morning REGULAR buy schedule and evening margin preview; sell monitor EMA rehydration after restart; NSE tick-band rounding and upper-circuit caps on live sells; T+1 holdings reconciliation; live position repair tool; Kotak live LTP for sell monitoring.
- **OHLCV / analysis:** Postgres OHLCV cache, NSE bhavcopy primary daily source, bulk analysis job with resume, admin-only market analysis run-once, stale today-bar fixes, premarket read-only price_cache refresh.
- **ML / verdict:** Versioned verdict feature manifest, dip episode dataset and ranking, optional CPU transformer news sentiment, composite news profiles, `VERDICT_AND_SCORING` documentation.
- **Paper trading:** DB-only portfolio/history metrics, unified EMA9 sell targets with live broker, improved fill/win-rate statistics.
- **Platform:** IST wall-clock consistency, Postgres Docker backup cron docs, `tools/verify_db_schema.py`, JWT/Fernet migration tool for broker secrets.

### Changed

- **Billing model:** In-app subscription catalog and SaaS checkout removed; performance-fee + offline UPI beta (Razorpay checkout optional when admin enables online payments).
- **Analysis access:** Bulk/market analysis restricted to admin role; shared signals remain user-visible via Buying Zone.
- **Activity logging:** Activity Log UI and `activity` table removed; use Log Viewer (JSONL file logs).
- **News sentiment:** Composite sources with cheap backtest profile and paid enrich on shortlisted names; env-tunable downgrade thresholds.
- **Dependencies:** Python and web stack upgrades (React 19, Tailwind v4 PostCSS); Vitest 90% line coverage CI gate.

### Fixed

- Performance bills use closed positions as PnL source of truth; PnL daily sync on full closes.
- Sell monitor false cancellation on mid-session restart; same-day buy/sell sizing for T+1.
- Paper sell monitor stale OHLCV guards; duplicate paper order rows.
- Run-once UI timer and conflict banner during long analysis subprocesses.
- Backtest scoring when only `total_trades` is set; bond ticker screener filter.
- Holdings pre-flight on stale Kotak holdings; CSV fallback when no ACTIVE signals.
- Admin ML training (XGBoost, sklearn 1.8, price regressors); integrated backtest offline-safe tests.
- Auth email SMTP mock in pytest (no real `@example.com` sends during tests).

### Removed

- Activity Log page (`/dashboard/activity`), `activity` router, and `activity` database table.
- Legacy subscription billing UI and user subscribe/cancel/plan-list APIs (webhooks may still update legacy rows).

### Documentation

- [Verdict and Scoring](docs/features/VERDICT_AND_SCORING.md), billing traceability matrices, bulk analysis reliability, HTTPS DuckDNS, auth/profile UI and API sections.
- Release plan and upgrade notes for 26.2.1.

### Migration

- **Required:** `alembic upgrade head` before starting API (18+ revisions on this branch, including billing, auth tokens, mobile number, OHLCV cache, activity drop). Backup Postgres first in production.
- **New env (see `.env.example`):** `SMTP_*` for auth emails; billing/Razorpay; OHLCV/NSE; optional news sentiment and transformer backend.
- **Operators:** Configure SMTP before enabling public signup; configure admin billing (offline QR or Razorpay) before performance-fee collection.

## [26.2] - 2026-04-14

### Added
- **Web branding and version**: Shared `BrandMark` (Rebound logo, product name, `v{version}` from `web/package.json`) on the app shell sidebar, login page, and sign-up page.

### Changed
- Upgraded Python and web dependencies; updated Tailwind v4 PostCSS integration.
- Updated frontend auth guard store selectors to avoid infinite render loops under React 19.

### Fixed
- Fixed test isolation for multi-user trading service shared lock state.
- Made integrated backtest unit tests offline-safe by resetting/mocking yfinance + circuit breaker.

## [26.1.0] - 2025-12-02

### Added
- **E2E Test Data Seeding Utility**: Comprehensive Python script (`web/tests/e2e/utils/seed-db.py`) to seed test database with signals, orders, and notifications for end-to-end testing
- **Test Admin User Management**: Automated script (`web/tests/e2e/utils/ensure-test-admin.py`) to ensure test admin user exists and is properly configured
- **Database Isolation**: Clear separation between development database (`app.db`) and E2E test database (`e2e.db`) with safeguards and warnings
- **E2E Test Infrastructure**: Complete E2E testing setup with Playwright, including 70+ tests covering authentication, trading, admin, settings, and error handling
- **Test Data Management**: Resilient test design that works with or without seeded data, including empty state validation
- **Test Cleanup Utilities**: Automatic cleanup of test-created users, configurations, and notifications via `testDataTracker` fixture
- **E2E Test Documentation**: Comprehensive documentation covering database setup, data management, cleanup procedures, and troubleshooting

### Changed
- **Database Schema Validation**: Seeding script now validates database schema and provides helpful error messages for outdated schemas
- **Test Runner Scripts**: Enhanced PowerShell and Bash scripts for better Python detection, error handling, and cross-platform compatibility
- **Test Admin Credentials**: Standardized test admin user (`testadmin@rebound.com`) across all test scripts and configurations
- **SQLAlchemy Version**: Updated to `>=2.0.44` for consistency across all requirements files

### Fixed
- **Missing Dependency**: Added `email-validator>=2.0.0` to `server/requirements.txt` to support Pydantic's `EmailStr` validation
- **Missing Test Dependency**: Added `httpx>=0.24.0` to `requirements-dev.txt` required by FastAPI's TestClient (used in conftest.py)
- **Test Loading State Detection**: Improved loading state test to handle fast responses and cached data gracefully
- **Test Cleanup Errors**: Fixed cleanup warnings for 401 Unauthorized errors during test teardown
- **PowerShell Script Syntax**: Replaced Unicode characters with ASCII-safe alternatives for better compatibility
- **Dockerfile Redundancy**: Removed redundant `pydantic[email]` installation from Dockerfile as `email-validator` is now explicitly listed
- **Strict Mode Violations**: Fixed Playwright strict mode violations by using more specific selectors (e.g., `getByRole('heading')` instead of `getByText()`)

### Documentation
- **Consolidated E2E Documentation**: Merged multiple documentation files into comprehensive guides:
  - `web/tests/e2e/DATABASE.md` - Database configuration and isolation guide
  - `web/tests/e2e/DATA_MANAGEMENT.md` - Test data management strategies
  - `web/tests/e2e/README.md` - Quick start and overview
- **Test Admin Setup Guide**: Added detailed instructions for test admin user configuration
- **Database Separation Guide**: Clear documentation on which database is used when (Docker vs E2E tests)

## [25.7.0] - 2025-11-09

### Added
- **RSI30 Requirement Enforcement**: Trading parameters only calculated when RSI < 30 (above EMA200) or RSI < 20 (below EMA200)
- **Single Stock Backtest Script**: New script `scripts/run_single_stock_backtest.py` for testing individual stocks
- **Enhanced CSV Export**: Added 30+ fields for ML training data collection (justification, pe, pb, rsi, volume analysis, etc.)
- **Unit Tests**: Added comprehensive unit tests for ML disabled logic, RSI30 requirement, and liquidity threshold
- **Regression Test Fix**: Fixed `test_backtest_validation_default` to handle RSI30 requirement and pyramiding trades

### Changed
- **ML Model Disabled**: Temporarily disabled ML model for verdict determination, using rule-based logic only until ML is fully trained
- **Liquidity Threshold Lowered**: Minimum absolute average volume reduced from 20,000 to 10,000 to allow more stocks
- **Chart Quality Thresholds Relaxed**:
  - Gap frequency: 25% max (was 20%)
  - Chart score: 50 minimum (was 60)
  - Daily range: 1.0% minimum (was 1.5%)
  - Extreme candles: 20% max (was 15%)
- **Volume Requirements Relaxed**:
  - Minimum volume: 70% of average (was 80%)
  - For RSI < 30 oversold conditions: 50% of average (RSI-based adjustment)
- **Weekly Uptrend Context Refined**:
  - Weekly trend up and price near support → +2 points
  - Weekly trend up but mid-range → +1 point
  - Weekly trend flat/down → 0 points
- **Fundamental Filter Flexible**:
  - Allows "watch" verdict for growth stocks (negative PE) if PB ratio < 5.0
  - Still forces "avoid" for loss-making companies (negative PE + PB > 5.0)
- **Trade Execution Validation**: Updated to handle pyramiding trades correctly (entry_price is average for pyramided positions)

### Fixed
- **Regression Test**: Fixed `test_backtest_validation_default` to account for RSI30 requirement and rule-based logic differences
- **Trading Parameters Validation**: Updated to check individual fields and handle RSI30 requirement correctly
- **Volume Check Validation**: Downgraded to warnings (RSI-based volume adjustment allows lower volume when RSI < 30)
- **Verdict Mismatch Validation**: Differentiated significant vs minor mismatches, downgraded minor mismatches to warnings
- **Capital Validation**: Added capital/quantity to position data, handle missing capital gracefully
- **Entry Price Validation**: Increased tolerance and handle pyramiding correctly

### Documentation
- **Consolidated Changes Document**: Created `documents/CHANGES_2025_11_09_CONSOLIDATED.md` summarizing all changes
- **Regression Test Fix Documentation**: Added `documents/REGRESSION_TEST_FIX_2025_11_09.md`
- **Verdict Watch Analysis**: Added `documents/VERDICT_WATCH_ANALYSIS.md` documenting root cause analysis

## [25.6.0] - 2025-11-02

### Added (Phase 4: Cleanup & Consolidation)

- **Additional Services** - Phase 4 service layer extensions
  - `services/scoring_service.py` - Scoring service (migrated from `core/scoring.py`)
  - `services/backtest_service.py` - Backtest integration service (wraps `core/backtest_scoring.py`)
  - **Benefits:** Service layer consistency, dependency injection ready

- **Deprecation Utilities** - Phase 4 deprecation management
  - `utils/deprecation.py` - Deprecation warnings and migration guides
  - Deprecation notices for all legacy `core.*` functions
  - Migration guides for smooth transition

- **Documentation** - Phase 4 documentation
  - `documents/phases/PHASE4_MIGRATION_GUIDE.md` - Comprehensive migration guide
  - `documents/phases/PHASE4_DUPLICATES_COMPLETE.md` - Duplicate consolidation report
  - `documents/phases/PHASE4_DEPRECATION_COMPLETE.md` - Deprecation status

### Changed (Phase 4: Cleanup & Consolidation)

- **Deprecated Legacy Functions** - Phase 4 deprecation warnings
  - `core.analysis.analyze_ticker()` → Use `services.AnalysisService`
  - `core.analysis.analyze_multiple_tickers()` → Use `services.AsyncAnalysisService`
  - `core.scoring.compute_strength_score()` → Use `services.ScoringService`
  - `core.backtest_scoring.add_backtest_scores_to_results()` → Use `services.BacktestService`
  - `core.analysis.calculate_smart_*()` → Use `services.VerdictService`
  - **Migration:** See `documents/phases/PHASE4_MIGRATION_GUIDE.md`

- **Consolidated Duplicates** - Phase 4 duplicate removal
  - Consolidated `src/application/services/scoring_service.py` → `services/scoring_service.py`
  - Eliminated ~213 lines of duplicate code
  - Single source of truth for all services

- **Updated trade_agent.py** - Phase 4 service migration
  - Now uses `services.ScoringService` instead of `core.scoring`
  - Now uses `services.BacktestService` instead of `core.backtest_scoring`
  - Refactored `compute_trading_priority_score()` to use `ScoringService`

- **Service Layer Updates** - Phase 4 infrastructure support
  - `services/data_service.py` - Supports infrastructure injection (future-ready)
  - `services/indicator_service.py` - Prepared for infrastructure migration
  - All services maintain backward compatibility with `core.*` modules

### Removed (Phase 4)

- **Duplicate Code** - Consolidated duplicate implementations
  - Removed duplicate `ScoringService` implementation in `src/application/services/`
  - Consolidated to single implementation in `services/scoring_service.py`

---

## [25.5.0] - 2025-11-02

### Added (Phase 1-3 Refactoring)

- **Service Layer Architecture** - Extracted monolithic `analyze_ticker()` into modular services (Phase 1)
  - `services/analysis_service.py` - Main orchestrator service
  - `services/data_service.py` - Data fetching service
  - `services/indicator_service.py` - Indicator calculation service
  - `services/signal_service.py` - Signal detection service
  - `services/verdict_service.py` - Verdict determination service
  - **Benefits:** Improved testability, maintainability, dependency injection ready

- **Async Processing** - Phase 2 async support
  - `services/async_analysis_service.py` - Async batch analysis
  - `services/async_data_service.py` - Async data fetching
  - **Benefits:** 80% faster batch analysis (25min → 5min for 50 stocks)

- **Caching Layer** - Phase 2 caching
  - `services/cache_service.py` - Memory-based cache
  - `services/cached_data_service.py` - Cached data fetching wrapper
  - **Benefits:** Reduces API calls by 70-90%

- **Event-Driven Architecture** - Phase 3 event bus
  - `services/event_bus.py` - Event bus with subscribe/publish
  - Event types and event handling infrastructure

- **Pipeline Pattern** - Phase 3 pipeline
  - `services/pipeline.py` - Analysis pipeline orchestrator
  - `services/pipeline_steps.py` - Pluggable pipeline steps
  - **Benefits:** Flexible, composable analysis workflow

- **Typed Data Classes** - Phase 2 models
  - `services/models.py` - Typed models (AnalysisResult, Verdict, TradingParameters, etc.)
  - **Benefits:** Type safety, IDE autocomplete, better documentation

- **Configuration Management** - Centralized strategy configuration (Phase 1)
  - `config/strategy_config.py` - StrategyConfig dataclass with all parameters
  - Environment variable support via `from_env()` method
  - **Benefits:** No more magic numbers, A/B testing capability, environment-specific configs

### Changed

- **Backward Compatibility** - All phases maintain backward compatibility
  - `core/analysis.py::analyze_ticker()` delegates to service layer
  - Maintains 100% backward compatibility
  - All existing code works without changes
  - Falls back to legacy implementation if service unavailable

### Impact

- **Code Quality:** Improved from monolithic (344 lines) to modular (5 services, 50-290 lines each)
- **Testability:** Each service can now be tested in isolation
- **Maintainability:** Clear separation of concerns, easier to modify
- **No Breaking Changes:** All existing code continues to work
- **Performance:** No regression (same underlying logic)

### Migration Guide

**For new code, prefer using service layer directly:**
```python
from services.analysis_service import AnalysisService

service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")
```

**For existing code (no changes needed):**
```python
from core.analysis import analyze_ticker

result = analyze_ticker("RELIANCE.NS")  # Still works, delegates to service layer
```

---

## [25.4.2] - 2025-11-13

### Changed

- **Documentation Organization** - Improved documentation structure and navigation
  - Updated `documents/README.md` with version info and better quick navigation
  - Removed duplicate `new_documentation/` folder (moved to archive)
  - Validated all 110 documentation files against current branch features
  - All documented features confirmed to exist in codebase

### Documentation

- Enhanced `documents/README.md` with version tracking and quick start reference
- Archived duplicate documentation structure
- Comprehensive validation of all feature documentation

### Impact

- Better documentation navigation
- No duplicate documentation structures
- All documentation validated as accurate
- Clean, organized structure maintained

---

## [25.4.1] - 2025-11-02

### Fixed
- **Conservative Bias in Backtest Scoring** - Reduced buy verdict thresholds by 10-20% to capture more profitable opportunities
  - High confidence (≥5 trades): buy threshold reduced from 40 to 35, combined score from 25 to 22
  - Low confidence (<5 trades): buy threshold reduced from 50 to 40, combined score from 35 to 28
  - Fixed issue where system missed 4 profitable trades (67% of executed trades)

- **Missing Target/Stop Parameters** - Added automatic parameter recalculation for upgraded verdicts
  - When verdict is upgraded from "avoid"/"watch" to "buy"/"strong_buy", system now automatically calculates missing buy_range, target, and stop parameters
  - Fixes Telegram alerts showing "target: 0" for upgraded stocks
  - Includes fallback to safe defaults if calculation fails

### Testing
- All tests passed: 137 passed, 2 skipped
- Test coverage: 76%
- Validated with 3 test stocks (SIMBHALS, FEL, SUDARSCHEM)

### Documentation
- Added comprehensive bug fix documentation: `documents/bug_fixes/FIX_CONSERVATIVE_BIAS_AND_MISSING_TARGETS.md`
- Added data flow documentation: `documents/DATA_FLOW_BACKTEST.md`
- Added architecture analysis: `documents/architecture/DESIGN_ANALYSIS_AND_RECOMMENDATIONS.md`

### Impact
- Expected to increase opportunity capture rate while maintaining 100% win rate quality
- No breaking changes - backward compatible

---

## [25.4.0] - 2025-10-15

### Initial Q4 2025 Release
- Core trading agent functionality
- Multi-timeframe analysis
- Backtest scoring integration
- Kotak Neo broker integration
- Telegram notifications
- Clean architecture implementation in `src/` directory

---

[26.2.2.1]: https://github.com/yourusername/modular_trade_agent/compare/v26.2.2...v26.2.2.1
[25.4.1]: https://github.com/yourusername/modular_trade_agent/compare/v25.4.0...v25.4.1
[25.4.0]: https://github.com/yourusername/modular_trade_agent/releases/tag/v25.4.0
