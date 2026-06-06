# Release Plan v26.2.1

**Branch:** `releases/rebound_2621`
**Version:** 26.2.1 (CalVer Q2 2026 patch)
**Status:** Ready for tag and deploy after checklist below
**Release notes:** Full branch scope — see [CHANGELOG.md](../../CHANGELOG.md) `[26.2.1]`

---

## Scope

Major themes on this branch (PR merges #153–#203):

| Theme | Operator impact |
|-------|-----------------|
| Auth & profile | Signup, hard email verification, password reset, profile email/mobile |
| Billing | Performance fees, offline UPI/QR, optional Razorpay checkout |
| Trading / Kotak | Sell monitor, morning schedule, OHLCV/T+1 fixes |
| OHLCV / analysis | Postgres cache, NSE bhavcopy, **admin-only** analysis |
| Platform | Activity Log removed → Log Viewer; IST; Alembic migrations |

---

## Pre-release verification

| Gate | Result (2026-06-06 local) |
|------|---------------------------|
| Auth pytest | 68 passed |
| Billing pytest | 39 passed |
| Web Vitest + coverage | 654 passed; **90.42%** lines |
| `tools/verify_db_schema.py` | Run on **staging/prod Postgres after** `alembic upgrade head` |
| Alembic | Rehearse `alembic upgrade head` on DB backup copy before prod |

**Staging / production:** Repeat full backend CI (`pytest`) and E2E auth/admin if Playwright is configured.

---

## Deploy steps

1. **Backup** Postgres ([POSTGRES_DOCKER_BACKUP_CRON.md](../deployment/POSTGRES_DOCKER_BACKUP_CRON.md)).
2. Pull `releases/rebound_2621` (or tag `v26.2.1`).
3. Update `.env` from [`.env.example`](../../.env.example) — at minimum review `SMTP_*`, billing, OHLCV, news vars.
4. Rebuild and restart Docker stack (or redeploy API + web).
5. Confirm migrations: `alembic current` shows head; API starts via [`docker/api-entrypoint.sh`](../../docker/api-entrypoint.sh).
6. **Post-deploy smoke:**
   - Signup → verify email → login (SMTP configured)
   - Settings: mobile update; email change + password
   - User Billing + Admin Billing (offline QR or Razorpay test keys)
   - Admin run-once analysis completes
   - Kotak sell monitor first session after restart (EMA targets)

---

## Rollback

- **Failed migration:** Restore DB backup; redeploy previous image/tag (`v26.2` / prior production revision).
- **App-only issue:** Redeploy previous container image; DB left at current revision only if migrations succeeded and are backward-compatible (prefer full restore if unsure).

Document `alembic current` revision before and after upgrade.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Long migration chain | Staging rehearsal; maintenance window |
| Signup blocked without SMTP | Configure `SMTP_*` before opening signup |
| Users expect self-serve analysis | Release notes: admin-only analysis |
| Billing misconfiguration | [BILLING traceability matrices](../features/BILLING_ADMIN_TRACEABILITY_MATRIX.md) |
| Sell-monitor regression | Live smoke first session; monitor logs |

---

## Deliverables checklist

- [x] Version `26.2.1` in `VERSION` and `web/package.json`
- [x] `CHANGELOG.md` `[26.2.1]`
- [x] This release plan
- [x] Doc alignment (API billing, UI billing, FEATURES, USER_GUIDE, upgrade notes)
- [ ] Staging: `alembic upgrade head` + smoke on operator environment
- [ ] Tag `v26.2.1` on branch tip (local; push with explicit approval)
- [ ] Production deploy + post-deploy smoke

---

## Related docs

- [Upgrading to 26.2.1](../deployment/DEPLOYMENT.md#upgrading-to-2621)
- [Getting Started — SMTP for auth](../guides/GETTING_STARTED.md)
- [Billing admin matrix](../features/BILLING_ADMIN_TRACEABILITY_MATRIX.md)
- [Billing user matrix](../features/BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md)
