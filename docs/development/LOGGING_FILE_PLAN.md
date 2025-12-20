# File-Only Activity Logging – Implementation Plan

## Goals
- Eliminate DB lock contention from high-volume activity logs.
- Keep logs visible in the UI with filtering/search for non-technical users.
- Preserve ErrorLog (exceptions) in DB; everything else in files.
- Keep the design simple and production-safe in Docker/SQLite setups.

## Scope (Phase 1)
- Activity logs: switch to per-user daily JSONL files. **Completed**
- API read path: stream JSONL with filters; stable IDs. **Completed**
- UI: keep existing endpoints/shape; no major UI redesign now. **Completed**
- Retention: 90 days (pruning job). **Completed**
- Live tail: included now (tail last N lines, best-effort). **Completed**

Out of scope (Phase 1): Multi-user admin scan across all users; full log analytics; hosted log backends.

## Design
- **Format**: One JSON object per line (JSONL). Fields: `timestamp`, `level`, `module`, `message`, `context` (dict), `user_id`.
- **Files**: `logs/users/user_{id}/service_YYYYMMDD.jsonl`, `errors_YYYYMMDD.jsonl`.
- **Timestamps**: Use `ist_now()` (or consistent TZ) for write; parse with same TZ.
- **IDs**: Use stable composite `"{file_name}:{line_number}"` (or short hash) returned as `id`.
- **Write path**: User file handler writes JSONL; daily file rollover only (no size-based rotation).
- **Read path**: Stream files newest-first, skip invalid/partial lines, stop at `limit`; bound `days_back`.

## Components (with status)
1) **Writer** — JSONL per user/day with context; daily rollover. **Completed**
2) **Reader** — Streaming JSONL; filters; caps; IDs `file:line`. **Completed**
3) **API** — `/user/logs`, `/service/logs`, `/admin/logs` file-based; admin requires `user_id`; caps enforced. **Completed**
4) **UI** — Existing table works with new `id` and context. **Completed**
5) **Retention** — File pruning (90 days). **Completed**
6) **ErrorLog (DB)** — Light retry/backoff; skip on failure. **Completed**
7) **Live tail** — Last 200 lines from latest file. **Completed**

## Corner Cases & Mitigations
- **File reading while writing**: skip invalid/partial lines; rely on next read to catch up.
- **Large files**: stream; enforce `limit` and `days_back`; daily files keep size bounded.
- **Multiline stack traces**: JSONL stores entire trace in a field; no line splitting.
- **Rotation boundary (day change)**: read yesterday + today; missing last partial line is acceptable.
- **ID collisions**: use `file:line` composite (or hash) to keep unique.
- **Admin all-users view**: not in Phase 1; require `user_id` or add a future scan/index.
- **Context search**: context preserved in JSON; text search over message + context stringified.
- **Timezone**: use consistent TZ for write/read (IST utility).
- **Permissions/IO errors**: log a warning once; skip file, don’t fail request.
- **Retention**: prune old files via job.

## Testing Plan
- Unit: writer emits valid JSONL; rollover at day boundary; reader parses with filters; skips invalid lines.
- Integration: API endpoints return expected shape; limits/days_back enforced; context available.
- Concurrency: simulate concurrent writes + reads; ensure no crashes and partial lines are skipped gracefully.
- Performance: large file streaming doesn’t OOM; capped by limits.

## Rollout Plan
- Implement behind a feature flag if desired; default to file mode once verified.
- Keep ErrorLog in DB; activity logs in files.
- Document admin limitation (must supply user_id) until multi-user scan is added.
- Existing text logs: ignored (no fallback). We start fresh with JSONL. Old text logs won’t be visible unless manually converted (not planned).
- Post-implementation cleanup: remove legacy DB logging code (DatabaseLogHandler, ServiceLogRepository usage for activity logs), DB-based log endpoints/branches, DB log retention for service logs, related config/env, and legacy tests/docs tied to DB activity logging.
- Data safety: Logging must never block or interfere with core DB reads/writes. Activity logs are file-only (no DB locks). ErrorLog writes remain low-volume; use short transactions and optional retry/backoff; if an error log can’t be written, skip it rather than block business flows—no feature data loss.
- Admin access to other users: Support `user_id` on admin log endpoints to view another user’s logs; multi-user scan remains out of scope for Phase 1.

## Defaults/Decisions
- Live tail: now.
- Retention: 90 days.
- Max `days_back`: 14.
- Max `limit`: 500.
- Tail lines: 200.
- Retention job: daily prune.
- Feature flag: none (direct rollout).
- ErrorLog: light retry/backoff on “database is locked”; skip if still failing (no feature blocking).
