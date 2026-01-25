# Copilot instructions (modular_trade_agent)

## Big picture (where code lives)
- FastAPI API: `server/app/` (routers, schemas, auth). Entry: `server/app/main.py`.
- Clean Architecture core:
  - Domain: `src/domain/`
  - Use-cases/services: `src/application/services/` (multi-user service mgmt, scheduling, conflicts)
  - Infrastructure: `src/infrastructure/` (DB models, repositories, logging, external adapters)
- Analysis/strategy service layer (preferred): `services/` (Phase 1-4: async, caching, pipeline, event bus). Legacy `core/*` is deprecated.
- Broker integration: `modules/kotak_neo_auto_trader/` (Kotak Neo session + trading service).
- Web UI: `web/` (React+TS, TanStack Query, Zustand). API base URL via `VITE_API_URL`.

## Conventions that matter here
- Keep API routers thin: no ORM queries or business logic in `server/app/routers/*`; call `src/application/services/*` and/or `src/infrastructure/persistence/*`.
- Prefer `services/*` for analysis work (e.g., `AnalysisService`, `AsyncAnalysisService`, pipeline via `create_analysis_pipeline`). See `docs/architecture/SERVICE_ARCHITECTURE.md`.
- Multi-user service lifecycle is stateful:
  - `MultiUserTradingService` uses **module-level shared dicts/locks** to survive FastAPI DI creating new instances per request.
  - Individual tasks run as subprocesses via `IndividualServiceManager`.
  - If you change service start/stop/status, preserve locking + DB status updates.
- Windows console can choke on Unicode: avoid emojis/non-ASCII in console logs/prints (see `docs/engineering-standards-and-ci.md`). Use `[OK]`, `[WARN]`, `[FAIL]`.

## Local workflows (Windows-first)
- Python is configured for 3.12; formatting/linting: black+ruff (100 cols) in `pyproject.toml`.
- Common tasks (PowerShell):
  - Setup: `make setup`
  - Lint: `make lint` (Python ruff+black, Web eslint)
  - Typecheck: `make typecheck` (mypy + tsc)
  - Tests: `make test` (API + Web)
  - API-only tests: `make test-api` (sets `DB_URL="sqlite:///:memory:"`)
- Start API: `uvicorn server.app.main:app --reload --port 8000`
- Start web: `cd web; npm ci; npm run dev:api8000` (or `dev:api8001`)

## Runtime knobs you must not break
- DB bootstrapping: `server/app/main.py` auto-creates tables in dev if missing, but production should use Alembic (`alembic upgrade head`).
- Unified service in API process (to avoid multiple Kotak sessions):
  - `RUN_UNIFIED_IN_API=1` and `UNIFIED_USER_IDS=1,2` (see `server/app/main.py`).
  - Be careful: this creates background asyncio tasks at startup.
- Broker networking: IPv4-only resolution defaults on (`FORCE_IPV4=1`) for specific broker hosts; can be disabled via env.

## When adding/changing features
- New API endpoint: add router in `server/app/routers/`, request/response schemas in `server/app/schemas/`, wire in `server/app/main.py`.
- DB changes: update models in `src/infrastructure/db/models.py` (and related repos), then add an Alembic migration under `alembic/versions/`.
- New analysis capability: implement in `services/*` (typed models in `services/models.py`), then call from API/services layer.
- Tests:
  - API: `tests/server`, `tests/infrastructure`, `tests/scripts` (pytest uses `--import-mode=importlib`; see `pytest.ini`).
  - Web: Vitest + MSW; E2E via Playwright (`web/tests/e2e`).
