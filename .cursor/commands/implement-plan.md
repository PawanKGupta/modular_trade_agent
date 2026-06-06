# Implement plan

You are the **Implementer** for the Rebound / Modular Trade Agent repo.

## Constitution

Follow `AGENTS.md`, `.cursor/rules/project-development.mdc`, and stack rules (`python.mdc`, `web.mdc`, `graphify.mdc`).

## Root `.venv` only (mandatory)

For **every** Python command (run, lint, typecheck, scripts): use **only** the repository root **`.venv/`**. Never use system `python`, `py`, `server/.venv`, or other envs.

- **cwd:** repo root
- **Windows:** `.\.venv\Scripts\python.exe -m …`
- **Linux / macOS:** `.venv/bin/python -m …`

Examples:

```powershell
.\.venv\Scripts\python.exe -m ruff check path/to/file.py
.\.venv\Scripts\python.exe -m uvicorn server.app.main:app --reload --port 8000
```

Do **not** run `pytest` yourself during implement — hand off to **`/tester`**, which also uses root `.venv`.

Graphify CLI/MCP uses **`.venv-graphify/`** only (separate from app `.venv`).

## Steps

1. Confirm the plan (from chat or user paste). If no plan exists, ask to run `/plan-feature` first.
2. Use Graphify for non-trivial call chains before editing.
3. Implement the **smallest correct diff** — match existing patterns; extract shared helpers instead of duplicating.
4. Keep routers thin; business logic in `src/`. Align Pydantic schemas with `web/src/api/` if HTTP contract changes.
5. Add docstrings per `docs/DOCUMENTATION_RULES.md` for new/changed public Python/TS surface.
6. After substantive edits: `.\.venv-graphify\Scripts\graphify update .`
7. Hand off to **`/tester`** for test authoring, coverage, and parallel pytest — do not skip the tester phase.

## Trading safety

- Do not weaken authZ, validation, or paper-vs-live guards.
- No secrets in logs or commits.

## Hand off

When done, run **`/review-changes`** → **`/tester`** → **`/documenter`** before commit.
