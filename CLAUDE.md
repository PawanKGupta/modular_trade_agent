# Claude Code — project instructions

This project's working rules live in `AGENTS.md` and `.cursor/rules/` (authored
for other agents/Cursor). They apply equally to Claude Code. **Read and follow them.**

## Always-on — operating manual + global rules

@AGENTS.md
@.cursor/rules/project-development.mdc

## Graphify is mandatory for traversal/architecture/flow/root-cause work

Per `AGENTS.md` §4: **before** answering or editing in reliance on any
call-chain, dependency, architecture, API-path, or cross-file root-cause
question, consult Graphify **first**, then cross-check the source.

- Start: `graphify-out/GRAPH_REPORT.md`; data: `graphify-out/graph.json`.
- The Graphify MCP may not be wired into a Claude Code session — use the
  committed artifacts / CLI (`.venv-graphify`) instead (§4.1 allows this).
- If the graph is missing/stale relative to the question, **say so** (§4.3).
- After substantive code edits, refresh: `.\.venv-graphify\Scripts\graphify update .` (§4.4).

## When editing Python (`**/*.py`)

@.cursor/rules/python.mdc

## When editing the web UI (`web/src/**`)

@.cursor/rules/web.mdc

## Quick reminders (most-missed)

- **Virtualenv:** use **only** the repo-root `.venv/` for every `python` / `pytest` / Ruff / Black run.
  Windows: `.\.venv\Scripts\python.exe -m pytest …`.
- **Before finishing:** Ruff + Black clean on edited files (don't rely on the pre-commit hook to reformat).
- **Before commit:** run the "verify documentation" pass from `project-development.mdc`, or record it as N/A with a one-line reason.
- **Bug fixes:** root-cause it, add a regression test for non-obvious failures, run targeted `pytest`.
- **Git:** never push or open PRs without explicit permission; local commits only unless asked.
