# AGENTS.md — Operating instructions for AI agents

This document merges **repository standards** with **Cursor project rules** under `.cursor/`. It does **not** replace those rules; agents must still follow them in full.

**Authoritative sources (read before substantive work):**

| Source | Role |
|--------|------|
| [`.cursor/rules/project-development.mdc`](.cursor/rules/project-development.mdc) | Global map, quality bar, git policy, documentation policy, security |
| [`.cursor/rules/graphify.mdc`](.cursor/rules/graphify.mdc) | Graphify artifacts, CLI, MCP, update workflow |
| [`.cursor/rules/python.mdc`](.cursor/rules/python.mdc) | Python/FastAPI/`src/` layout, venv, Ruff/Black, tests |
| [`.cursor/rules/web.mdc`](.cursor/rules/web.mdc) | React/TypeScript, API client, Vite conventions |
| [`.cursor/mcp.json`](.cursor/mcp.json) | Graphify MCP server bootstrapping |
| [`docs/DOCUMENTATION_RULES.md`](docs/DOCUMENTATION_RULES.md) | Canonical documentation and docstring policy |

**Note:** This repo’s `.cursor/` tree contains **rules** (`.mdc`) and **MCP config**; there is no separate skills bundle checked in under `.cursor/`. If the host environment injects additional Cursor skills, they apply in addition to this file.

---

## 1. Project overview

**Purpose:** **Rebound — Modular Trade Agent** is a multi-user trading system for Indian equities (NSE), combining strategy/signal analysis, order execution (e.g. broker integrations), paper trading, ML-assisted signals, and a web-based control plane— with strong emphasis on **correctness**, **auditability**, and **no leakage of secrets**.

**Major areas:**

| Layer | Location | Responsibility |
|--------|-----------|----------------|
| Web UI | `web/` (Vite + React + TypeScript) | Operator UX; TanStack Query; API via `web/src/api/` |
| HTTP API | `server/app/` (FastAPI) | Routers (`routers/`), settings/deps/security (`core/`), Pydantic `schemas/` |
| Domain / services / persistence | `src/` | Business logic, services, infrastructure; imported as `src.*` from server |
| Migrations | `alembic/` | Schema evolution (prefer Alembic for DB changes) |
| Tests | `tests/` (`unit/`, `integration/`) | Regression and integration coverage |
| Operator / dev docs | `docs/` | Architecture, guides, API docs; see `docs/DOCUMENTATION_RULES.md` |

**Architecture style (high level):** **Layered monolith** — React frontend talks to a **FastAPI** surface; handlers stay thin while **services and persistence** live primarily in **`src/`** with **SQLAlchemy** (and configured DB backends). External broker/vendor APIs integrate via dedicated client/service boundaries (see code and `docs/` for specifics).

**Deeper reference:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`README.md`](README.md).

---

## 2. Repository understanding rules

- **Inspect real code and config** before explaining or changing behavior. Prefer **source of truth** (implementation, OpenAPI-derived contracts, Pydantic models) over assumptions.
- **Read call sites, imports, interfaces, and tests** relevant to the question. Trace **end-to-end** paths when behavior spans layers (`web/` ↔ `server/app/` ↔ `src/`).
- **Do not invent** modules, endpoints, tables, or flows. If the code is ambiguous, say so and point to what you verified.
- **Trading and money-moving paths** deserve extra rigor: verify conditions, side effects, and persistence effects against actual code.

---

## 3. Cursor rules integration

Before performing a task:

1. **Apply** [`project-development.mdc`](.cursor/rules/project-development.mdc) (always): structure, no duplication, logging not `print()` in API/`src/`, config not hardcoding, git remote restrictions, documentation policy, security.
2. **Apply** [`python.mdc`](.cursor/rules/python.mdc) for `**/*.py`: use **root `.venv/`** only for runs/tests/tools; keep routers thin; respect layering; Ruff/Black; docstrings per `DOCUMENTATION_RULES.md`.
3. **Apply** [`web.mdc`](.cursor/rules/web.mdc) for `web/src/**`: TanStack Query patterns, centralized `web/src/api/`, env via `import.meta.env` / `VITE_*`, avoid ad-hoc noise in production paths.
4. **Apply** [`graphify.mdc`](.cursor/rules/graphify.mdc) whenever reasoning about **symbol-level relationships** or **cross-module flows** (see §4).
5. **Keep HTTP contracts aligned:** Pydantic/OpenAPI ↔ `web/src/api` types and clients when the API surface changes.

**Git / remotes:** Do **not** `git push`, force-push, open PRs, or alter shared/release branches on the remote **unless the user explicitly asked** for that in the current task. Prepare changes locally.

---

## 4. Graphify — mandatory usage rules

Graphify maps **classes, functions, imports, and call relationships** into a queryable graph. “Flow” means **edges in that graph** (calls, imports, inferred links)—**not** an informal narrative sequence diagram.

### 4.1 When Graphify is mandatory

**Before answering** (or before editing in reliance on) any of the following, the agent **must** use Graphify **first** (MCP tools and/or committed artifacts / CLI as available):

- Technical **traversal** questions (how A connects to B in code)
- **Architecture** and dependency structure
- **Dependency / import** graphs and hub symbols
- **Call-chain** or **execution-path** tracing (statically, via graph + code)
- **Service-to-service** or **module-to-module** mapping
- **API-chain** questions (which code paths implement a route)
- **Code navigation** across non-trivial indirection
- **Graph/tree** exploration of symbols
- **Data/control flow** questions that require knowing **who calls whom**
- **Root-cause** analysis that depends on cross-file propagation

**Do not guess traversal flows. Do not assume architecture paths.** Validate with Graphify, then **cross-check** against the implementation (see workflow below).

### 4.2 Workflow (strict order)

1. **Read Graphify output or query the graph**
   - **Start:** `graphify-out/GRAPH_REPORT.md` (Summary, God nodes; search within—do not load entire huge files into chat).
   - **Graph data:** `graphify-out/graph.json` (via CLI or MCP).
   - **Navigation:** `graphify-out/wiki/index.md` if present.
   - **MCP (if enabled):** prefer `query_graph`, `shortest_path`, `god_nodes`, `get_node`, `get_neighbors`, `graph_stats` over blind whole-repo groping. Config: [`.cursor/mcp.json`](.cursor/mcp.json).
2. **Validate** the hypothesized chain (symbols, direction, key hubs) against the graph.
3. **Cross-check** by reading the **actual** source files for the edges you rely on.
4. **Answer**, citing **files / classes / functions** where possible.

### 4.3 When Graphify is missing, stale, incomplete, or unclear

If `graphify-out/graph.json` / `GRAPH_REPORT.md` is absent, clearly outdated relative to the question, incomplete for the symbols you need, or ambiguous:

1. **State this explicitly** in the response (what was missing or unreliable).
2. **Fall back to manual repository inspection** (targeted search, reading routers, services, `src/`, and related tests).
3. **State confidence limitations**—what you verified directly vs. what remains uncertain.

### 4.4 Maintainer / agent hygiene (code changes)

After substantive code edits in a session, refresh the graph per [`.cursor/rules/graphify.mdc`](.cursor/rules/graphify.mdc) (e.g. `graphify update .` from repo root, `.venv-graphify`; regenerate tree when needed). If `.graphifyignore` changes, follow the **clean rebuild** instructions in that rule file.

---

## 5. Architecture documentation rules

Maintain a **working mental model** aligned with code and Graphify. Prefer updating **existing** canonical docs in `docs/` over creating parallel summaries (per `project-development.mdc`).

**Conceptual stack (adjust names to match code under each path):**

```text
Frontend (web/src)
    ↓ HTTP (API client, TanStack Query)
FastAPI routers (server/app/routers)
    ↓ deps / security (server/app/core)
Application services (src/application, server-adjacent facades as used)
    ↓
Infrastructure / repositories / integrations (src/infrastructure, clients, brokers)
    ↓
Database / external vendor & broker APIs
```

**Also account for (when present in code):**

- **External HTTP/WebSocket APIs** (brokers, market data, notifications)
- **Internal** module calls and **shared utilities** (`server/app/core`, `src/`, `web/src` shared helpers)
- **Async** tasks, **workers**, schedulers, CLI entrypoints
- **Caching layers**, retries, idempotency (verify per feature)
- **Middleware**: auth, CORS, rate limits, request context (verify in `server/app`)

---

## 6. API path structure rules

For **each** route you discuss or change, map the **real** execution path by reading code (and use Graphify first for traversal questions per §4).

**Document / verify:**

| Aspect | What to identify (from code) |
|--------|------------------------------|
| HTTP method & path | OpenAPI / router decorator |
| Router module | `server/app/routers/...` |
| Handler dependencies | `Depends`, security schemes (`server/app/core`) |
| Service / use-case | `src/` or coordinated server modules |
| Persistence | Repositories, session usage, models |
| DB tables / entities | SQLAlchemy models / migrations |
| External calls | Broker/vendor HTTP clients, etc. |
| Request/response models | Pydantic `schemas/` |
| Validation | Pydantic, explicit checks, domain validators |
| AuthN / AuthZ | JWT, roles, policies |
| Errors | HTTPException, custom errors, logging |
| Retries / fallbacks | If implemented (confirm; do not assume) |

**Canonical patterns:**

```text
Router → Service / domain logic → Repository → DB
```

```text
Router → Service → internal helper / external API client
```

**Frontend contract:** mirror changes in `web/src/api/` (types, client functions) alongside Pydantic models.

---

## 7. Technical question handling rules

Before answering technical questions:

- Identify **affected modules** and **entrypoints** (router, UI page, worker).
- Read **related** implementation and **tests**.
- Trace **imports and calls**; for traversal-heavy questions use **Graphify first** (§4).
- Cite specific **files and symbols** when giving a definitive answer.

**Do not:** fabricate helpers or routes; skip middleware/deps; ignore async/context; confuse **paper trading** vs **live** paths without verifying guards in code.

---

## 8. Coding standards

- **Match existing patterns** in the touched file and feature area; small, reviewable diffs.
- **No duplication:** extract shared helpers / services instead of copy-paste (see global rules).
- **Config:** environment and settings—not inline magic values—for anything tunable or environment-specific.
- **Logging:** Python `logging.getLogger(__name__)` appropriately; avoid `print()` in API/`src/` operational code.
- **Typing & style:** Ruff/Black (Python); sound TypeScript types in `web/src` (avoid unnecessary `any`).
- **Compatibility:** preserve behavior unless the user requested a breaking change; if breaking, update API consumers and docs.

---

## 9. File navigation rules

- Read **neighboring** files and the **feature folder** before editing.
- Locate **existing** utilities/hooks/services and **reuse** them.
- Understand **exports and contracts** (Pydantic schemas, TS types, public service APIs) before changing them.
- After moves or renames, update **imports**, **tests**, and **docs** in the same change set when applicable.

---

## 10. Testing and validation rules

- After meaningful backend changes, run **targeted** `pytest` via **root `.venv/`** (see `python.mdc`).
- After meaningful frontend changes, use the **web** package’s lint/typecheck/test scripts as appropriate.
- Add or update **regression tests** for non-obvious bugs fixes.
- If the answer depended on Graphify, ensure the **explained traversal** matches **current** graph output or note staleness per §4.3.

---

## 11. Documentation rules

- For user-visible behavior, API surface, env/config, or deployment changes, update **existing** docs per [`docs/DOCUMENTATION_RULES.md`](docs/DOCUMENTATION_RULES.md).
- **Single canonical** doc per topic; cross-link instead of duplicating procedures.
- Keep **examples** aligned with actual code paths; **no secrets** in examples.
- Architecture or flow diagrams in prose should reflect what you **verified** (Graphify + code).

---

## 12. Security and safety rules

- **Never** commit or paste real **passwords, API keys, JWT secrets, encryption keys, or broker credentials**.
- **Logs and errors:** avoid PII and token material; don’t log full sensitive request bodies unless already an approved pattern.
- **AuthZ:** confirm role/ownership checks on user-scoped actions when touching those paths.
- **Input validation:** preserve or strengthen validation—don’t weaken checks to “make it work”.
- **Least privilege:** only the minimum scope of change required for the task.

---

## 13. Final response checklist

Before sending a substantive technical answer about this repo, confirm:

- [ ] **`.cursor` rules** and this **`AGENTS.md`** are respected for the task.
- [ ] **Graphify-first** satisfied for traversal/architecture/flow questions (§4), or §4.3 limitations explicitly stated.
- [ ] Claims are backed by **inspected** code, config, or graph output—not guesses.
- [ ] **Router → service → persistence / external API** stories match source.
- [ ] **Uncertainties** and **stale/missing graph** caveats are explicit where relevant.
- [ ] **Git remote** policy (no push/PR unless asked) observed.
- [ ] **Docs/tests** consideration noted when the change is user-facing or non-trivial.

---

## Quick reference — Graphify artifacts & commands

| Artifact / action | Location / command |
|-------------------|----------------------|
| Report (start here) | `graphify-out/GRAPH_REPORT.md` |
| Graph JSON | `graphify-out/graph.json` |
| Collapsible tree | `graphify-out/GRAPH_TREE.html` (open locally; don’t bulk-load into context) |
| Wiki index (optional) | `graphify-out/wiki/index.md` |
| Incremental update (repo root) | `.\.venv-graphify\Scripts\graphify update .` (see `graphify.mdc` for Unix/`PATH` equivalents) |
| MCP | [`.cursor/mcp.json`](.cursor/mcp.json) + `tools/graphify_mcp_stdio.py` |

For full detail, CLI options, `.graphifyignore`, and troubleshooting, read [`.cursor/rules/graphify.mdc`](.cursor/rules/graphify.mdc).
