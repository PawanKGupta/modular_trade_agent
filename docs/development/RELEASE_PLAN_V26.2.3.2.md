# Release Plan v26.2.3.2

**Branch:** `releases/rebound_26232` (cut from `main`)
**Version:** 26.2.3.2 (CalVer Q2 2026 patch)
**Status:** Ready for tag and deploy after checklist below
**Release notes:** Full scope — see [CHANGELOG.md](../../CHANGELOG.md) `[26.2.3.2]`

---

## Scope

29 commits on top of `v26.2.3.1` (everything merged to `main` since the last tag):

| Theme | Operator impact |
|-------|-----------------|
| **Security — default-deny env + secure-by-default auth (C2)** | Production now **fails fast** if `JWT_SECRET` is default/unset or no Fernet key is set, and serves `Secure` cookies by default. An unset/typo'd `ENV` resolves to **production**. Eliminates a silent auth-downgrade (token-forgery / auth-bypass) path. |
| Per-user max order value | New per-user cap on order value — config + DB column + order-sizing enforcement across buy/re-entry/retry + dashboard UI. |
| ML price regressor beyond EMA9 | Price regressor can predict targets beyond EMA9; delete-model endpoint; collapsible training-jobs UI. |
| Paper trading morning fills | Morning AMO buys fill at the real 09:15 open, not the prior close. |
| Daily log rotation | Global log file rotates daily instead of once per process. |
| 401 polling loop fix | Resolves 401 loop on portfolio polling and login credential errors. |
| ML training correctness | Incremental-training freshness gate fixed (defaults to full retrain); EMA9 floor derived from actual `ema9`. |
| Docs | Image-based deployment guide; removed hardcoded default credentials; link/path/env alignment. |

---

## ⚠️ Breaking deployment change

Production is now **secure-by-default** and will **refuse to boot** unless:

- `JWT_SECRET` is a strong, non-default value
  (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- A Fernet key is set: `APP_DATA_ENCRYPTION_KEY` (or legacy `BROKER_SECRET_KEY` — same key, set only one)
  (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- The app is served over HTTPS (cookies default to `Secure` in production)

Non-production hosts that should run in dev mode must set `ENV=development` explicitly.

---

## Pre-release verification

| Gate | Result (2026-06-27 local) |
|------|---------------------------|
| Backend suite — `tests/unit tests/server tests/infrastructure tests/scripts tests/regression tests/security tests/paper_trading` (`-n auto`, `--import-mode=importlib`) | **5309 passed, 13 skipped, 0 failed** |
| `max_order_value` sizing + premarket adjustment tests | Passes (verified during integration) |
| C2 auth detection / fail-fast tests (`tests/security`, server auth) | Included in backend suite |
| Ruff + Black | N/A — release delta is version bumps + docs only; no Python changes vs `main` (code is the already-CI-validated `main` tip) |

> Note: the release branch is byte-identical to the `main` tip for all source code; only `VERSION`, `web/package.json`, `CHANGELOG.md`, `DEPLOYMENT.md`, and this plan are added. Every code commit in scope was CI-validated on merge to `main`.

---

## Deploy steps

1. **Backup** the database ([Postgres backup guide](../deployment/POSTGRES_DOCKER_BACKUP_CRON.md)).
2. **Verify auth secrets** (see breaking change above) are set in `.env` — the app fails fast otherwise.
3. Pull image `v26.2.3.2` (or check out the tag) and start:
   ```bash
   export APP_VERSION=v26.2.3.2
   docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull
   docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
   ```
4. **Apply the migration:** `alembic upgrade head` (adds the `max_order_value` column).
5. **Post-deploy smoke:**
   - API boots with no fail-fast secret error in logs.
   - `max_order_value` is configurable per user in the dashboard Capital config, and orders are capped accordingly.
   - Pre-open paper cycle: morning buys fill at the 09:15 open.

---

## Rollback

- Redeploy the previous tag/container image (`v26.2.3.1`).
- The `max_order_value` column is additive and nullable — it does not need to be dropped for a rollback (the prior image simply ignores it).

---

## Deliverables checklist

- [x] Version `26.2.3.2` in `VERSION` and `web/package.json`
- [x] `CHANGELOG.md` `[26.2.3.2]`
- [x] This release plan
- [x] Upgrade notes in [DEPLOYMENT.md](../deployment/DEPLOYMENT.md#upgrading-to-26232)
- [ ] Tag `v26.2.3.2` on branch tip (pending — triggers `docker-release.yml` image build/publish)

---

## Related docs

- [Upgrading to 26.2.3.2](../deployment/DEPLOYMENT.md#upgrading-to-26232)
- [User data security](../security/USER_DATA_SECURITY.md)
- [Release Plan v26.2.3.1](RELEASE_PLAN_V26.2.3.1.md)
