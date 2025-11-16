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
