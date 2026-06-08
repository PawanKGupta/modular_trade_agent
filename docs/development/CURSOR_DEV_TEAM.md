# Cursor dev team (Path A)

**Purpose:** Run a small **autonomous engineering loop** inside Cursor using rules, slash commands, subagents, and Graphify — without a custom Python/LangGraph orchestrator.

**Audience:** Developers and AI agents working in this repository.

---

## Overview

Path A uses Cursor as the orchestrator:

```text
Requirement → Planner → Implementer → Reviewer → Tester → Documenter → (user commit)
```

| Artifact | Location |
|----------|----------|
| Agent constitution | [`AGENTS.md`](../../AGENTS.md) |
| Dev team rule | [`.cursor/rules/dev-team.mdc`](../../.cursor/rules/dev-team.mdc) |
| Slash commands | [`.cursor/commands/`](../../.cursor/commands/) |
| Graphify MCP | [`.cursor/mcp.json`](../../.cursor/mcp.json) + [`tools/graphify_mcp_stdio.py`](../../tools/graphify_mcp_stdio.py) |

---

## Prerequisites

1. **Root Python venv (mandatory for dev + test)** — **only** `.venv/` at repo root for every `python` / `pytest` / Ruff / uvicorn run. Never system Python, bare `pytest`, or `server/.venv`. See [`python.mdc`](../../.cursor/rules/python.mdc).
   - Windows: `.\.venv\Scripts\python.exe -m pytest …`
   - Unix: `.venv/bin/python -m pytest …`
2. **Graphify venv** — `.venv-graphify/` for graphify CLI/MCP only (not for app tests).
3. **Knowledge graph** — from repo root:

   ```powershell
   .\.venv-graphify\Scripts\graphify update .
   ```

4. **MCP sanity check:**

   ```powershell
   .\.venv-graphify\Scripts\python.exe tools\validate_graphify_mcp.py
   ```

   Expect `Result: PASS` and `graph_stats` lines.

5. **Cursor** — enable **graphify** under Settings → MCP; reload window after `mcp.json` changes.

---

## Workflow

### 1. Plan (`/plan-feature`)

- Planner produces tasks, paths, risks, acceptance criteria.
- Uses Graphify for cross-module impact.
- **No code edits.**

### 2. Implement (`/implement-plan` or Agent with plan in context)

- Small diffs; follow `AGENTS.md` and stack rules.
- All Python tooling via **root `.venv`** (implementer does not run pytest — tester does).
- `graphify update .` after substantive edits (`.venv-graphify`).

### 3. Review (`/review-changes` or reviewer subagent)

- Read-only checklist: layers, security, trading paths, tests, docs.
- Output: **PASS** or **FAIL** with fix list.

### 4. Test (`/tester`)

The tester agent has **two phases**:

1. **Write or update tests** for the change set (`tests/unit/`, `tests/integration/`, or web Vitest).
2. **Run with coverage and parallel execution**:
   - Python: repo root cwd, **`.\.venv\Scripts\python.exe -m pytest`** (never bare `pytest`), `$env:DB_URL="sqlite:///:memory:"`, `-n auto` (pytest-xdist)
   - Coverage: `pytest.ini` scopes + `--cov-fail-under=90` (**>90%**; 95%+ for critical trading/auth paths)
   - Web: `cd web && npm run test -- --run <pattern>` (Vitest with coverage)

See [`docs/testing/TESTING_RULES.md`](../testing/TESTING_RULES.md). Report pass/fail and coverage; loop back to implementer on failure.

### 5. Document (`/documenter`)

After tests pass, update documentation so it matches the change set:

- Follow [`docs/DOCUMENTATION_RULES.md`](../DOCUMENTATION_RULES.md) — canonical pages, amend over add, no duplication
- Update user-visible guides, API/architecture docs, config/env sections, and **docstrings** for public Python/TS surface
- State **N/A** with reason for trivial or test-only changes
- Verify steps, env names, paths, and relative links

Hand back to **Implementer** if docs reveal code/API gaps. Do not commit.

### 6. Human gate

- User reviews diff.
- Commit only when user asks (see git policy in `project-development.mdc`).
- No push/PR without explicit permission.

---

## Subagents (optional)

| Role | Suggested subagent | When |
|------|-------------------|------|
| Explore / map codebase | `explore` | Planner, unfamiliar area |
| Review | `generalPurpose` (readonly) | Independent review pass |
| Test authoring + parallel coverage | Agent with `/tester` or `shell` subagent | After review pass |
| Documentation | Agent with `/documenter` | After tester pass |
| CI failure | `ci-investigator` | After PR checks fail |

Enable **dev-team** rule (`@dev-team` or rule picker) when running the full loop.

---

## Trading and safety

- Extra scrutiny on broker, orders, paper vs live, and user-scoped data.
- Never commit secrets; no credential logging.
- Prefer paper paths and existing guards when validating behavior.

---

## Why not Path B?

A Python `agents/` + LangGraph loop duplicates Cursor, adds maintenance, and is risky for money-moving code without strong human gates. Path B is only worth it for **headless** automation outside the IDE (scheduled jobs, bots). This repo standardizes on **Path A**.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Graphify MCP won't start | From repo root: `.\.venv-graphify\Scripts\python.exe tools\validate_graphify_mcp.py` — expect `Result: PASS` and `graph_stats` lines. If FAIL: install `pip install "graphifyy[mcp]"` in `.venv-graphify`, then `graphify update .`, and re-run validate. |
| Unsure Graphify is wired correctly | Same validate command (see [Prerequisites](#prerequisites) step 4). FAIL usually means missing `graphify-out/graph.json`, missing `GRAPH_REPORT.md`, or graphify not installed in `.venv-graphify`. |
| Missing `graph.json` | `graphify update .` from repo root |
| Stale graph after edits | `graphify update .` (clean rebuild if `.graphifyignore` changed — see `graphify.mdc`) |
| Commands not visible | Confirm files under `.cursor/commands/`; reload Cursor |

---

## Related

- [`AGENTS.md`](../../AGENTS.md) — full agent operating instructions
- [`.cursor/rules/graphify.mdc`](../../.cursor/rules/graphify.mdc) — Graphify CLI and MCP
- [`docs/DOCUMENTATION_RULES.md`](../DOCUMENTATION_RULES.md) — doc and docstring policy
