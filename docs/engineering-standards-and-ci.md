## Overview

This document captures the coding standards, tooling, CI gates, and local workflows enforced in this repository for both the backend API (FastAPI/Python) and the web UI (React/TypeScript).

### Quick Commands (PowerShell)

- First-time setup:

```powershell
.\scripts\dev.ps1 setup
```

- Lint:

```powershell
.\scripts\dev.ps1 lint
```

- Typecheck:

```powershell
.\scripts\dev.ps1 typecheck
```

- Tests:

```powershell
.\scripts\dev.ps1 test
```

---

## Coding Standards

### Server (Python)

- Format: black (line length 100)
- Lint: ruff (rules include E/F/I, bugbear, pyupgrade, bandit subset, pylint-subset)
- Types: mypy (strict defaults for new code; gradual adoption for existing modules)
- Layering:
  - `server/app/core/` – settings, security, dependencies
  - `server/app/routers/` – thin API endpoints, no DB or business logic
  - `server/app/schemas/` – Pydantic models
  - `src/infrastructure/**` – DB/IO implementations
  - `src/application/**` – application/services/use-cases
  - `src/domain/**` – domain entities and interfaces
- Practices:
  - Explicit function signatures and return types
  - Avoid broad exceptions; return explicit 4xx/5xx
  - No ORM usage in routers; all DB via repositories
  - Config exclusively via Pydantic Settings (`server/app/core/config.py`)

### Web (TypeScript/React)

- Lint: ESLint v9 flat config (`web/eslint.config.js`) with TypeScript, React, Hooks, and `jsx-a11y`
- Format: Prettier (100 col, tabs enabled to match repo)
- TS: Strict mode; avoid `any` unless necessary; prefer named exports
- Foldering:
  - `src/routes/**` – pages
  - `src/components/**` – reusable UI
  - `src/api/**` – thin API clients
  - `src/state/**` – Zustand stores
  - `src/mocks/**` – MSW handlers
  - `src/test/**` – testing utilities
- Practices:
  - Components remain presentational; data fetching via React Query in hooks or route modules
  - Include empty and error states
  - Accessible form controls and labels

---

## Tooling and Config Files

- `.editorconfig`: unified whitespace/EOL conventions across the repo (tabs generally; spaces for Python)
- `pyproject.toml`: black and ruff configuration (line length 100; import/order)
- `mypy.ini`: strictness defaults with allowances for gradual typing
- `.pre-commit-config.yaml`: ruff (fix+format), black, YAML/whitespace fixers
- `requirements-dev.txt`: adds black, ruff, mypy, coverage plugins

Web:
- `web/eslint.config.js`: ESLint v9 flat config; deprecates `.eslintrc.*`
- `web/.prettierrc.json`: Prettier formatting
- `web/tsconfig.json`: adds `vite/client` and `vitest/globals` types

---

## CI Gates

GitHub Actions:
- API (`.github/workflows/api-tests.yml`):
  - Install `requirements.txt`, `server/requirements.txt`, `requirements-dev.txt`
  - Run ruff, black --check, mypy
  - Run focused tests with coverage (coverage gate ≥80%)
- Web (`.github/workflows/web-ui-tests.yml`):
  - `npm ci`
  - Lint + typecheck
  - Vitest with coverage (coverage gate ≥80%)

---

## Local Workflows

- Pre-commit
  - Install once via `.\scripts\dev.ps1 setup` (installs and enables hooks)
  - Run on-demand with `.\scripts\dev.ps1 pre-commit`

- Lint & Format
  - Server: `ruff check server src` and `black --check server src`
  - Web: `eslint .` (configured for ESLint v9 flat config)

- Typecheck
  - Server: `mypy` (warnings currently tolerated where legacy code conflicts; will tighten gradually)
  - Web: `tsc --noEmit` (strict mode)

- Tests
  - API tests use a dedicated SQLite file DB to ensure tables persist on app startup:
    - `DB_URL="sqlite:///./data/test_api.db"` (set in `scripts/dev.ps1` for test runs)
  - UI tests run with Vitest + RTL + MSW, plus optional Playwright smoke

---

## Summary of Recent Changes

- Added and configured: ruff, black, mypy, pre-commit hooks, .editorconfig
- Web migrated to ESLint v9 flat config; removed legacy `.eslintrc.cjs`
- Added Prettier config and web type definitions for Vite and Vitest
- CI now runs lint/typecheck/tests for both API and Web with coverage thresholds (≥80%)
- Introduced `scripts/dev.ps1` to unify local workflows on Windows PowerShell:
  - `setup`, `lint`, `typecheck`, `test`, `pre-commit`, `ci-*`
- Adjusted API test runner to use file-backed SQLite DB to avoid transient table issues

---

## Next Steps (Optional Enhancements)

- Auto-fix pass for Python `src/**` to reduce ruff warnings (batch PR)
- Enforce mypy on more subpackages (reduce ignores/gradually raise strictness)
- Add Playwright E2E smoke tests to CI
- Separate Makefile/Noxfile (Linux/macOS) mirroring PowerShell `scripts/dev.ps1`

---

## Scope Checklist (What this doc covers)

- Coding standards for Server (black/ruff/mypy, layering, practices)
- Coding standards for Web (ESLint v9 flat, Prettier, TS strict, structure)
- Tooling setup (.editorconfig, pyproject, mypy.ini, pre-commit, dev requirements)
- Web tooling/migration (eslint.config.js, Prettier config, tsconfig types)
- CI workflows (API and Web jobs; lint/typecheck/test; coverage ≥80% gates)
- Local developer workflow (PowerShell script for setup/lint/typecheck/test)
- Test DB stability change (file-backed SQLite for API tests)
- Repository hygiene (.gitignore entries for web build/vendor/coverage output)
- Troubleshooting (pre-commit hooks and how they interact with vendor files)

If you add new checks or workflows, update the relevant sections above and this checklist.

---

## Implemented UI Features (Web App)

### Auth and Session
- Login (`/login`) with API integration; error states surfaced
- Signup (`/signup`) with API integration; error/validation surfaced
- Session store using Zustand (`src/state/sessionStore.ts`) tracks auth and user profile
- Protected routes via `RequireAuth` component and React Router guards
- App shell (`AppShell`) shows logged-in email, logout action clears session and navigates to login

### Dashboard Pages
- Buying Zone (`/dashboard/buying-zone`):
  - Fetches signals via `src/api/signals.ts` (React Query under the hood via component usage)
  - Displays symbols and filters/criteria (RSI10 < 30, price > EMA200, etc.)
  - Clean JSX rendering (escaped `>{' '}` usage where needed)
- Settings (`/dashboard/settings`):
  - Loads current user settings from API (`trade_mode`, broker config/state)
  - Edit and save settings (PUT) with optimistic UX and success/error handling
  - Broker integration:
    - Form fields for API key/secret (when trade_mode is "broker")
    - "Save Credentials" button to encrypt and store broker credentials
    - "Test Connection" button to validate broker credentials
    - Live status display (Connected/Disconnected/Stored/Error)
    - API client in `src/api/user.ts` with broker-specific methods
- Orders (`/dashboard/orders`):
  - Tabbed view for AMO, Ongoing, Sell, Closed
  - Data via `src/api/orders.ts` with status filter; React Query caching per tab
  - Empty and loading states handled
- Admin • Users (`/dashboard/admin/users`):
  - RBAC-guarded page (visible only for admins)
  - List existing users, create new users, update role/active, delete user
  - React Query for data and invalidation on mutations; API in `src/api/admin.ts`
- PnL (`/dashboard/pnl`):
  - Daily PnL table and summary (total, days green/red) via `src/api/pnl.ts`
  - React Query with date range support
- Activity (`/dashboard/activity`):
  - Activity log with level filter (info/warn/error/all) via `src/api/activity.ts`
  - React Query with level query param
- Targets (`/dashboard/targets`):
  - Targets list via `src/api/targets.ts` (currently placeholder until persistence added)
- Dashboard Home (`/dashboard`):
  - Placeholder overview page

### API Clients and Routing
- Axios client with base config (`src/api/client.ts`)
- API modules for `auth`, `user`, `signals`, `orders`, `pnl`, `activity`, `targets`, `admin` (`src/api/*.ts`)
- Broker integration methods in `src/api/user.ts`: `saveBrokerCreds()`, `testBrokerConnection()`, `getBrokerStatus()`
- Centralized routing in `src/router.tsx` with nested dashboard routes

### Testing (UI)
- Vitest + React Testing Library + MSW
  - `src/test/setup.ts` boots MSW handlers (`src/mocks/test-handlers.ts`)
  - Unit/integration tests for Login, Signup, Settings, Buying Zone, RequireAuth, AppShell, Admin Users, Orders
  - Coverage on relevant UI modules >90% locally (threshold gate in CI is ≥80%)
 - Playwright E2E (smoke)
   - Config: `web/playwright.config.ts`
   - Smoke spec: `web/tests/e2e/smoke.spec.ts` (auth → dashboard → admin → orders tabs)
   - CI workflow: `.github/workflows/web-e2e.yml` (starts API + Vite and runs E2E)

### Developer Commands (Web UI)
- Lint:
```powershell
cd web; npm run lint
```
- Typecheck:
```powershell
cd web; npm run typecheck
```
- Tests with coverage:
```powershell
cd web; npm run test
```
- Run UI against local API on port 8001:
```powershell
cd web; npm run dev:api8001
```
  - Alternatively set the env before starting dev:
```powershell
$env:VITE_API_URL="http://localhost:8001"; cd web; npm run dev
```

- Run UI against local API on port 8000:
```powershell
cd web; npm run dev:api8000
```
  - Alternatively:
```powershell
$env:VITE_API_URL="http://localhost:8000"; cd web; npm run dev
```

### Run E2E locally
1) Start API:
```powershell
$env:DB_URL="sqlite:///./data/e2e.db"; .\.venv\Scripts\python.exe -m uvicorn server.app.main:app --port 8000 --reload
```
2) Start Vite (new shell):
```powershell
cd web; $env:VITE_API_URL="http://localhost:8000"; npm run dev
```
3) In another shell, run Playwright:
```powershell
cd web; npx playwright install chromium; npm run test:e2e
```

---

## Implemented API Endpoints (New/Updated)

### Auth
- POST `/api/v1/auth/signup` → { access_token, token_type }
- POST `/api/v1/auth/login` → { access_token, token_type }
- GET `/api/v1/auth/me` → current user profile

### User Settings
- GET `/api/v1/user/settings`
- PUT `/api/v1/user/settings`

### Orders
- GET `/api/v1/user/orders/` — Query params: `status=pending|ongoing|failed|closed|cancelled`, `failure_reason=<partial_match>`, `from_date=YYYY-MM-DD`, `to_date=YYYY-MM-DD`
  - Returns: list of orders for the authenticated user, filtered by status if provided
  - Note: `status=pending` includes orders previously marked as `amo` or `pending_execution`
  - Note: `status=failed` includes orders previously marked as `failed`, `retry_pending`, or `rejected`
  - Note: Use `side=buy` or `side=sell` to filter by order type (SELL status removed)
- POST `/api/v1/user/orders/{id}/retry` — Retry a failed order
  - Returns: updated order with incremented retry_count
- DELETE `/api/v1/user/orders/{id}` — Drop a failed order from retry queue
  - Returns: success message

### PnL
- GET `/api/v1/user/pnl/daily` — Query params (optional): `start=YYYY-MM-DD`, `end=YYYY-MM-DD`
  - Returns: array of `{ date, pnl }` for the authenticated user
- GET `/api/v1/user/pnl/summary` — same optional params
  - Returns: `{ totalPnl, daysGreen, daysRed }`

### Activity
- GET `/api/v1/user/activity/` — Query param: `level=info|warn|error|all` (default `all`)
  - Returns: recent activity rows for the authenticated user

### Targets
- GET `/api/v1/user/targets/`
  - Returns: list of targets (currently placeholder empty list until persistence is added)

### Broker Integration
- POST `/api/v1/user/broker/creds` — Save encrypted broker credentials
  - Body: `{ broker: str, api_key: str, api_secret: str, mobile_number?: str, password?: str, mpin?: str, totp_secret?: str, environment?: str }`
  - Returns: `{ status: "ok" }`
  - Credentials are encrypted server-side using Fernet (symmetric encryption) and stored in `user_settings.broker_creds_encrypted`
  - Supports saving basic credentials (api_key/api_secret) or full authentication credentials (including mobile, password, MPIN)
- POST `/api/v1/user/broker/test` — Test broker connection
  - Body: `{ broker: str, api_key: str, api_secret: str, mobile_number?: str, password?: str, mpin?: str, totp_secret?: str, environment?: str }`
  - Returns: `{ ok: bool, message: str }`
  - **Basic test**: Only requires `api_key` and `api_secret` - validates client initialization
  - **Full test**: Requires `mobile_number`, `password`, and `mpin` - performs actual login and 2FA authentication with Kotak Neo SDK
  - Uses existing `neo_api_client` SDK integration for real authentication testing
- GET `/api/v1/user/broker/status` — Get current broker connection status
  - Returns: `{ broker: str | null, status: str | null }`
- GET `/api/v1/user/broker/creds/info` — Get stored broker credentials information
  - Query params: `show_full: bool` (default: false)
  - Returns masked credentials by default (last 4 characters visible)
  - Returns full credentials when `show_full=true` (for viewing/editing)
  - Returns: `{ has_creds: bool, api_key?: str, api_secret?: str, mobile_number?: str, password?: str, mpin?: str, api_key_masked?: str, api_secret_masked?: str }`

**Security Notes:**
- Credentials are encrypted at rest using `cryptography.fernet` with a key derived from `ENCRYPTION_KEY` env var (or auto-generated for dev)
- Encryption key should be set via environment variable in production: `ENCRYPTION_KEY=<base64-encoded-32-byte-key>`
- Full credentials are only returned when explicitly requested via `show_full=true` query parameter
- Masked credentials (last 4 characters) are shown by default for security
- Credentials are isolated per user (row-level security via `user_id`)

**UI Features:**
- Settings page shows stored credentials on page load (masked by default)
- "Show/Hide Full Credentials" toggle to view/edit all stored values
- Supports saving and updating all credential types (basic + full auth)
- Connection test supports both basic (client init) and full (login + 2FA) modes
- Test button automatically uses stored credentials if available

### Signals
- GET `/api/v1/signals/buying-zone`
  - Returns: buying-zone signals (DB-backed)

Notes
- All “user/*” endpoints are row-scoped by the authenticated user; app-level isolation enforced via `get_current_user` and repository filters on `user_id`.
- For development, SQLite is used; for production, recommend PostgreSQL (optionally add RLS as an additional layer).

### Admin bootstrap (one-time)
- If the database has zero users on startup and the following env vars are set, an admin will be created automatically:
  - `ADMIN_EMAIL`, `ADMIN_PASSWORD` (optional `ADMIN_NAME`)
- Example (PowerShell):
```powershell
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="StrongPassword123!"
$env:ADMIN_NAME="Admin"
.\.venv\Scripts\python.exe -m uvicorn server.app.main:app --port 8000 --reload
```
This runs only when there are no users; subsequent restarts won’t create duplicates.

### One-off admin creation script
You can also create or promote an admin manually:
```powershell
# optional: $env:DB_URL="sqlite:///./data/app.db"
.\.venv\Scripts\python.exe scripts\create_admin.py --email admin@example.com --password "StrongPassword123!" --name "Admin"
```
If the user exists, the script promotes them to admin and activates the account.

### Dev Experience
- ESLint v9 flat config (`eslint.config.js`) with TypeScript, React, Hooks, and `jsx-a11y`
- Prettier formatting aligned with repo conventions
- Vite + React + TS + Tailwind configured; `@` alias to `src/`
