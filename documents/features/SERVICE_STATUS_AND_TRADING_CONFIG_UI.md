# Service Status & Trading Configuration UI Guide

**Version**: 2.0
**Last Updated**: 2025-11-18
**Status**: ✅ Phase 3 UI shipped (Service Mgmt + Trading Config + ML Training + Log Viewer + Individual Service Management)

---

## Overview

Phase 3 introduces three high-visibility dashboards in the Modular Trade Agent web app:

1. **Service Status Dashboard** – live view of the per-user trading service, with controls, task history, recent logs, and individual service management.
2. **Trading Configuration Workspace** – full-fidelity editor for every user-scoped strategy parameter, including presets and deltas vs defaults.
3. **Log Management Dashboard** – unified view of structured service logs and error reports (user + admin scopes) with resolution workflow.
4. **Individual Service Management** – run individual trading tasks independently, with conflict detection and schedule management.
5. **Admin Schedule Management** – configure service schedules, enable/disable tasks, and manage execution times (admin-only).

This document explains how to access the pages, what each widget does, the supporting APIs/tests, and how to demo the flow for stakeholders.

---

## Access & Navigation

| Flow | Path | Description |
| --- | --- | --- |
| Main layout | `web/src/routes/AppShell.tsx` | Adds “Service Status” + “Trading Config” links to the sidebar. |
| Service Status UI | `/dashboard/service` | Loads `ServiceStatusPage.tsx` with React Query auto-refresh and individual service controls. |
| Trading Config UI | `/dashboard/config` | Loads `TradingConfigPage.tsx` with TanStack Query + mutations. |
| ML Training UI (admin) | `/dashboard/admin/ml` | Loads `MLTrainingPage.tsx` for managing training jobs + models. |
| Log Management UI | `/dashboard/logs` | Loads `LogViewerPage.tsx` with user/admin scopes, filters, and error resolution. |
| Schedule Management UI (admin) | `/dashboard/admin/schedules` | Loads `ServiceSchedulePage.tsx` for managing service schedules. |

**Auth requirement**: Both routes are nested under the authenticated dashboard router. Users must be logged in; requests automatically include the JWT via the shared API client.

---

## 1. Service Status Dashboard

![Service Status Overview](./media/service-status-overview.svg)

### Key Widgets

| Component | File | Details |
| --- | --- | --- |
| Status card | `ServiceStatusPage.tsx` | Shows `service_running`, uptime, heartbeat, error count, and last task time. Auto-refreshes every 15s (faster when running). |
| Controls | `ServiceControls.tsx` | Start/Stop buttons with optimistic UI, disabled states, spinner feedback. |
| Individual Services | `IndividualServicesSection.tsx` | Grid of individual service cards with start/stop/run-once controls. |
| Individual Service Card | `IndividualServiceControls.tsx` | Per-service control card with status, last execution, next execution, and action buttons. |
| Task History | `ServiceTasksTable.tsx` | Paginated table of the last 50 executions, filterable by status + task. Rows expand to show payload metadata. |
| Logs Viewer | `ServiceLogsViewer.tsx` | Filter by level/module, shows timestamped log lines with copy-to-clipboard. |

### API Contracts

| Endpoint | Method | Schema |
| --- | --- | --- |
| `/api/v1/user/service/status` | `GET` | Returns `ServiceStatusResponse` (running flag, timestamps, heartbeat, error counts). |
| `/api/v1/user/service/start` | `POST` | Starts or queues the per-user worker. Returns updated status snapshot. |
| `/api/v1/user/service/stop` | `POST` | Gracefully stops the worker and flushes tasks. |
| `/api/v1/user/service/individual/status` | `GET` | Returns status of all individual services for the user. |
| `/api/v1/user/service/individual/start` | `POST` | Starts an individual service (only when unified service is not running). |
| `/api/v1/user/service/individual/stop` | `POST` | Stops an individual service. |
| `/api/v1/user/service/individual/run-once` | `POST` | Runs a task once immediately (with conflict detection). |
| `/api/v1/user/service/tasks` | `GET` | Returns paginated `ServiceTaskExecution` history + filters. |
| `/api/v1/user/service/logs` | `GET` | Returns recent structured logs with optional level/module filters. |
| `/api/v1/admin/schedules` | `GET` | Returns all service schedules (admin-only). |
| `/api/v1/admin/schedules/{task_name}` | `GET` | Returns schedule for a specific task (admin-only). |
| `/api/v1/admin/schedules/{task_name}` | `PUT` | Updates service schedule (admin-only). |
| `/api/v1/admin/schedules/{task_name}/enable` | `POST` | Enables a service schedule (admin-only). |
| `/api/v1/admin/schedules/{task_name}/disable` | `POST` | Disables a service schedule (admin-only). |

All endpoints live in `server/app/routers/service.py` with schemas defined under `server/app/schemas/service.py`.

### Usage Flow

1. Navigate to `/dashboard/service`.
2. Observe the status pill (`Running`, `Stopped`, or `Degraded` based on heartbeat drift and error counts).
3. Use **Start Service** whenever the worker is idle. The button shows `Starting…` until the API resolves.
4. Task history auto-refreshes alongside the status poller (shared refetch).
5. Use log filters (level/module) to drill into recent warnings or errors.

### Tests & Monitoring

| Layer | File | Coverage |
| --- | --- | --- |
| API unit tests | `tests/unit/server/test_service_api.py` | 16 tests covering auth, success paths, filters, and error states. |
| React component tests | `web/src/routes/__tests__/ServiceStatusPage.test.tsx` (plus component-specific suites) | Validates loading, auto-refresh, controls, filtering, accessibility labels. |
| Integration tests | `web/src/routes/__tests__/ServiceStatusPage.integration.test.tsx` | Exercises start/stop workflow with mocked API client. |
| E2E demo | `web/tests/e2e/service-status.spec.ts` | Playwright smoke covering navigation, task + log visibility, button states. |

### Demo Checklist

```bash
# Backend: ensure FastAPI server is running (e.g., uvicorn server.app.main:app --reload)
# Frontend: launch Vite dev server
cd web
npm install
npm run dev -- --host 0.0.0.0 --port 4173

# E2E (headless demo)
npm run test:e2e -- service-status.spec.ts
```

> Tip: For live demos without prod data, use the MSW mocks (`npm run dev:mock`) so the dashboard shows deterministic sample tasks/logs.

---

## 2. Trading Configuration Workspace

![Trading Config Overview](./media/trading-config-overview.svg)

### Layout

| Section | Component | Highlights |
| --- | --- | --- |
| Presets | `ConfigPresets.tsx` | One-click apply for Conservative/Moderate/Aggressive templates. |
| Strategy Params | `StrategyConfigSection.tsx` | RSI sliders, chart quality toggles, volume caps. Shows default comparisons and validation hints. |
| Capital & Positions | `CapitalConfigSection.tsx` | Capital per trade, max portfolio size with impact banner. |
| Risk | `RiskConfigSection.tsx` | Optional stop-loss tiers, target percentages, risk-reward ratios. |
| Orders | `OrderConfigSection.tsx` | Default exchange/product/order type/variety/validity selectors. |
| Behavior & Advanced | `BehaviorConfigSection.tsx` | Duplicate recommendations, exit rules, news sentiment, ML controls. |

### UX Enhancements

- **Unsaved Changes Detection**: Sticky banner + top-right badge when `localConfig` differs from server baseline.
- **Dual Save Controls**: Primary `Save Changes` near the header plus sticky footer CTA for long forms.
- **Null-safe optional fields**: Inputs render empty string when a server value is `null`; clearing an input sends `null` so optional configs can be unset.
- **Validation hints**: Inline warnings (e.g., “Must be > Tight Stop Loss”) rely on current values, ensuring the user sees constraints before saving.

### API Integration

| Call | Function | Notes |
| --- | --- | --- |
| Fetch | `getTradingConfig()` | Populates the entire page via React Query. |
| Update | `updateTradingConfig(partial)` | Sends only changed keys. The mutation converts `null` → `undefined` where required by the schema. |
| Reset | `resetTradingConfig()` | Restores defaults and clears local modifications. Confirmation dialog protects against accidental resets. |

See `web/src/api/trading-config.ts` for type definitions (`TradingConfig`, `TradingConfigUpdate`, `CONFIG_PRESETS`).

### Presets & Deltas

Each field shows `Default: X` beneath the input. When a value deviates from the default, a yellow badge `*` appears within the label. Presets apply a set of key overrides (strategy, risk, capital) and immediately mark the form as “unsaved” so the user can review before saving.

### Tests & Demos

| Layer | File(s) | Focus |
| --- | --- | --- |
| Component tests | `web/src/routes/__tests__/*ConfigSection*.test.tsx` | Accessibility (labels/ids), validation, onChange handlers. |
| Page unit tests | `web/src/routes/__tests__/TradingConfigPage.test.tsx` | Unsaved indicator, save/reset workflow, preset application. |
| Integration tests | `web/src/routes/__tests__/TradingConfigPage.integration.test.tsx` | End-to-end state transitions with mocked API client. |
| E2E | `web/tests/e2e/trading-config.spec.ts` | User navigates to config page, edits values, saves, resets. |

**Manual demo steps**:

```bash
# Start backend (FastAPI)
uvicorn server.app.main:app --reload

# Run frontend with mock data for deterministic demos
cd web
npm run dev:mock
# Visit http://localhost:4173/dashboard/config
```

During demos, highlight:
1. Applying the Conservative preset (notice capital + risk tiles update).
2. Editing RSI thresholds and watching contextual warnings.
3. Sticky footer “Cancel / Save Changes” CTA when scrolled to lower sections.

---

## 3. ML Training Management Dashboard (Phase 3.4)

### Snapshot
- **Path**: `/dashboard/admin/ml`
- **Audience**: Admins only (link hidden unless `isAdmin`)
- **Purpose**: Kick off ML training jobs, observe history, manage/activate model versions that user configs consume.

### Components
| Widget | File | Notes |
| --- | --- | --- |
| Training form | `MLTrainingForm.tsx` | Validates path + JSON hyperparameters, optional notes, auto-activate toggle. |
| Jobs table | `MLTrainingJobsTable.tsx` | Shows job ID, type, algorithm, status badge, accuracy, timestamps. Auto-refresh 12s + manual refresh. |
| Models table | `MLModelsTable.tsx` | Lists versions, accuracy, active state with Activate button (per-row loading). |
| Page shell | `MLTrainingPage.tsx` | Coordinates TanStack Query hooks, start/activate mutations, and section layout. |

### Backend Contracts
| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/v1/admin/ml/train` | `POST` | Starts a new job (admin only). Uses FastAPI `BackgroundTasks` with a fresh `SessionLocal` so long-running jobs never reuse closed request sessions. |
| `/api/v1/admin/ml/jobs` | `GET` | List jobs w/ optional status/model filters. |
| `/api/v1/admin/ml/jobs/{id}` | `GET` | Fetch a single job (detail view). |
| `/api/v1/admin/ml/models` | `GET` | List trained models (supports `model_type` + `active`). |
| `/api/v1/admin/ml/models/{id}/activate` | `POST` | Sets model active; deactivates siblings of same type. |

Implementation lives in:
- `src/application/services/ml_training_service.py`
- `server/app/routers/ml.py`
- `server/app/schemas/ml.py`

### Training Workflow
1. Admin fills out the training form (model type, algorithm, data path, hyperparams JSON, optional notes).
2. Submit → `startTrainingJob` mutation posts to `/train`.
3. Backend creates `MLTrainingJob` row, runs simulated training, writes artifact JSON under `models/{type}/{algorithm}-vN.json`, and creates an `MLModel` record.
4. Jobs + models queries auto-refresh so the UI reflects completion.
5. Admin can activate any inactive model; first model of each type auto-activates.
6. Users select `ml_model_version` (or default to active) via Trading Config.

### Tests
| Layer | Files |
| --- | --- |
| Backend unit | `tests/unit/application/test_ml_training_service.py` |
| Backend API | `tests/unit/server/test_ml_training_api.py` |
| Frontend unit | `web/src/routes/__tests__/MLTrainingForm.test.tsx`, `web/src/routes/__tests__/MLTrainingPage.test.tsx` |
| Frontend integration | `web/src/routes/__tests__/MLTrainingPage.integration.test.tsx` |
| E2E | `web/tests/e2e/ml-training.spec.ts` |

### Demo Tips
```bash
# Backend (FastAPI)
uvicorn server.app.main:app --reload

# Frontend with mocks
cd web
npm run dev:mock
# Visit http://localhost:4173/dashboard/admin/ml
```
- Start a job → watch table update (MSW returns deterministic job/model data)
- Activate another model to show state badge swap
- Highlight integration with Trading Config (users can enable ML + pick version)

---

## 4. Log Management Dashboard (Phase 3.5)

### Snapshot
- **Path**: `/dashboard/logs`
- **Audience**: All users (self view) + admins (“All users” scope with resolution controls)
- **Purpose**: Provide a one-stop view of structured service logs and error/exception reports with filtering, search, export, and resolution workflow.

### Components
| Widget | File | Notes |
| --- | --- | --- |
| Page shell | `LogViewerPage.tsx` | Handles filters, admin scope toggle, fetches service/error logs via TanStack Query. |
| Service log table | `LogTable.tsx` | Displays timestamp, level, module, message, and JSON context. |
| Error log table | `ErrorLogTable.tsx` | Expandable rows with traceback/context/resolution notes plus admin-only “Resolve” CTA. |

### Backend Contracts
| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/v1/user/logs` | `GET` | Current user’s structured logs with level/module/search/date filters + limits. |
| `/api/v1/user/logs/errors` | `GET` | Current user’s error logs with resolved filter and date range. |
| `/api/v1/admin/logs` | `GET` | Admin view across users (optional `user_id`) with the same filters. |
| `/api/v1/admin/logs/errors` | `GET` | Admin error view with `user_id`, `resolved`, search, and date filters. |
| `/api/v1/admin/logs/errors/{id}/resolve` | `POST` | Marks an error as resolved, capturing optional notes and resolver ID. |

Implementation lives in `server/app/routers/logs.py` with schemas under `server/app/schemas/logs.py`. Repository helpers (`ServiceLogRepository`, `ErrorLogRepository`) gained search + admin listing helpers.

### Workflow
1. Users land on `/dashboard/logs` and immediately see their own logs/errors (auto fetch).
2. Filters (level/module/search/date/limit) run entirely client-side and refetch on change.
3. Admins toggle “Scope → All users” to expose the `user_id` filter, global data, and “Resolve” buttons.
4. Clicking **Resolve** prompts for optional notes, calls `/admin/logs/errors/{id}/resolve`, and refreshes the table.
5. Expanded error rows reveal traceback, context, and resolution metadata for quick triage.
6. A background retention worker purges service/error logs older than **90 days** to keep the database lean (configurable via `LOG_RETENTION_DAYS`).

### Tests
| Layer | Files |
| --- | --- |
| Backend API | `tests/unit/server/test_logs_api.py` |
| Frontend unit | `web/src/routes/__tests__/LogViewerPage.test.tsx` |
| Frontend integration | `web/src/routes/__tests__/LogViewerPage.integration.test.tsx` |
| E2E | `web/tests/e2e/log-viewer.spec.ts` |

### Demo Tips
```bash
# Backend
uvicorn server.app.main:app --reload

# Frontend (with MSW mocks)
cd web
npm run dev:mock
# Visit http://localhost:4173/dashboard/logs
```
- Demonstrate level/search filters on the Service Logs table.
- Toggle scope to “All Users”, enter a user ID, and show the admin data set.
- Click “Resolve” on an unresolved error to showcase the prompt + updated badge/resolution notes.

---

## 5. Documentation & Hand-offs

- This guide is linked from `documents/getting-started/GETTING_STARTED.md#dashboard-access`.
- Update release notes referencing “Phase 3 UI” should point here for screenshots and API/testing context.
- When adding new UI sections, append them to the tables above and update the SVG mockups in `documents/features/media/`.

---

## 6. Known Limitations & Next Steps

| Area | Status | Planned Follow-up |
| --- | --- | --- |
| Real-time log streaming | ❌ Pending | WebSocket endpoint (`/user/logs/stream`) still TODO in Phase 3.5. |
| Admin ML training workspace | ✅ Delivered | Future iterations will add advanced scheduling (cron/backfill) and richer hyperparameter templates. |
| Config diff history | 🚧 Planned | Only current vs default is shown; historical snapshots will be tackled when audit trail UI is ready. |

---

## 7. Change Log

| Date | Change | Author |
| --- | --- | --- |
| 2025-11-17 | Initial guide covering Service Status + Trading Config UI, plus demo instructions and mock screenshots. | GPT-5.1 Codex |
