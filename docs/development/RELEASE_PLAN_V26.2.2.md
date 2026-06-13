# Release Plan v26.2.2

**Branch:** `releases/rebound_2622`
**Version:** 26.2.2 (CalVer Q2 2026 patch)
**Status:** Ready for tag and deploy after checklist below
**Release notes:** Full branch scope — see [CHANGELOG.md](../../CHANGELOG.md) `[26.2.2]`

---

## Scope

Major themes on this branch (since `releases/rebound_2621`):

| Theme | Operator impact |
|-------|-----------------|
| User data security | Refresh-token rotation, session invalidation, MFA schema, audit trail; **read pre-deploy checklist** |
| Auth UX | Email domain allowlist for signup/profile; login lockout warnings and countdown |
| Paper / live trading | Morning buy parity, re-entry guards, sell sync, scheduler lock restore, holdings target fix |
| Notifications | Service status off by default; order + balance-shortfall multi-channel alerts |
| OHLCV / NSE | Bhavcopy publish window gating; skip pre-close intraday gap-fill |
| Platform | In-app `/help`; Alembic stale-version prune; E2E auth stabilization |

---

## Pre-release verification

| Gate | Result (2026-06-14 local) |
|------|---------------------------|
| Auth pytest (`test_auth.py`, `test_auth_and_settings.py`) | **67 passed** |
| Billing pytest (5 modules under `tests/unit/.../billing*`) | **50 passed** |
| Web Vitest + coverage | **90.21%** lines |
| `tools/verify_db_schema.py` | Run on **staging/prod Postgres after** `alembic upgrade head` |
| Alembic | **4 new revisions** since 26.2.1 — rehearse `alembic upgrade head` on DB backup copy before prod |

**Staging / production:** Repeat full backend CI (`pytest`) and Playwright E2E if configured.

---

## Deploy steps

1. **Backup** Postgres ([POSTGRES_DOCKER_BACKUP_CRON.md](../deployment/POSTGRES_DOCKER_BACKUP_CRON.md)).
2. Pull `releases/rebound_2622` (or tag `v26.2.2`).
3. Update `.env` from [`.env.example`](../../.env.example) — review auth/security, notification, and OHLCV vars (see [USER_DATA_SECURITY.md](../security/USER_DATA_SECURITY.md)).
4. Rebuild and restart Docker stack (or redeploy API + web).
5. Confirm migrations: `alembic current` shows head; API starts via [`docker/api-entrypoint.sh`](../../docker/api-entrypoint.sh).
6. **Post-deploy smoke:**
   - Login → refresh page (session persists)
   - Signup with allowed email domain; blocked domain rejected
   - Service Status page loads; start/stop one service
   - Paper or live morning buy path (operator environment)
   - `/help` loads without login
   - Admin run-once analysis completes (if used)

---

## Rollback

- **Failed migration:** Restore DB backup; redeploy previous image/tag (`v26.2.1` / prior production revision).
- **App-only issue:** Redeploy previous container image; DB left at current revision only if migrations succeeded and are backward-compatible (prefer full restore if unsure).

Document `alembic current` revision before and after upgrade.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| User-data-security migration | Staging rehearsal; backup before `alembic upgrade head` |
| Email allowlist blocks signups | Configure `EMAIL_DOMAIN_ALLOWLIST_EXTRA` or disable allowlist until ready |
| Cookie auth without HTTPS | `AUTH_COOKIE_SECURE=true` in production ([USER_DATA_SECURITY.md](../security/USER_DATA_SECURITY.md)) |
| Multi-replica login lockout | `RATE_LIMIT_BACKEND=redis` + `REDIS_URL` |
| Service schedule changes | Redeploy or restart workers after admin schedule edits |
| Session invalidation after deploy | Users re-login once if `token_version` bumped by admin password reset |

---

## Deliverables checklist

- [x] Version `26.2.2` in `VERSION` and `web/package.json`
- [x] `CHANGELOG.md` `[26.2.2]`
- [x] This release plan
- [x] Upgrade notes in [DEPLOYMENT.md](../deployment/DEPLOYMENT.md#upgrading-to-2622)
- [ ] Staging: `alembic upgrade head` + smoke on operator environment
- [ ] Tag `v26.2.2` on branch tip (local; push with explicit approval)
- [ ] Production deploy + post-deploy smoke

---

## Related docs

- [Upgrading to 26.2.2](../deployment/DEPLOYMENT.md#upgrading-to-2622)
- [User data security pre-deploy](../security/USER_DATA_SECURITY.md)
- [Upgrading from 26.2.1](../deployment/DEPLOYMENT.md#upgrading-to-2621)
- [Getting Started — SMTP for auth](../guides/GETTING_STARTED.md)
