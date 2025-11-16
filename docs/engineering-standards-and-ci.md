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
- PnL, Orders, Activity, Targets, Dashboard Home:
  - Implemented as scaffolded placeholders (routes+components) ready for data wiring

### API Clients and Routing
- Axios client with base config (`src/api/client.ts`)
- API modules for `auth`, `user`, `signals` (`src/api/*.ts`)
- Centralized routing in `src/router.tsx` with nested dashboard routes

### Testing (UI)
- Vitest + React Testing Library + MSW
  - `src/test/setup.ts` boots MSW handlers (`src/mocks/test-handlers.ts`)
  - Unit/integration tests for Login, Signup, Settings, Buying Zone, RequireAuth, AppShell
  - Coverage on relevant UI modules ~95% (threshold gate in CI is ≥80%)

### Dev Experience
- ESLint v9 flat config (`eslint.config.js`) with TypeScript, React, Hooks, and `jsx-a11y`
- Prettier formatting aligned with repo conventions
- Vite + React + TS + Tailwind configured; `@` alias to `src/`
