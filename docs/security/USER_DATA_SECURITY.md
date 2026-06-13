# User Data Security

## Overview

How Rebound stores, protects, and retains user-related data. Operators and developers should read this before production deployment.

## Data categories

| Category | Storage | Protection |
|----------|---------|------------|
| Login password | `users.password_hash` | PBKDF2-SHA256 (one-way hash, configurable rounds) |
| Email / name / mobile | `users` columns | Plaintext; access via authenticated API only |
| Broker credentials | `user_settings.broker_creds_encrypted` | Fernet (AES-128); key from `APP_DATA_ENCRYPTION_KEY` or `BROKER_SECRET_KEY` |
| JWT sessions | Client cookies (prod) or dev localStorage | `token_version` invalidation on password change |
| Refresh tokens | `refresh_tokens.token_hash` | SHA-256 hash only; rotation + reuse detection |
| MFA secrets | `users.mfa_secret_encrypted` | Fernet-encrypted TOTP secret |
| Audit trail | `audit_logs` | No passwords/tokens in `changes` JSON |

## Production requirements

Set before `ENV=production` or `APP_ENV=production`:

- `JWT_SECRET` — strong random value (not `dev-secret-change`)
- `APP_DATA_ENCRYPTION_KEY` or `BROKER_SECRET_KEY` — Fernet key (`cryptography.fernet.Fernet.generate_key()`)
- `AUTH_USE_COOKIES=true` (default) — access/refresh tokens in httpOnly cookies in production paths
- `AUTH_COOKIE_SECURE=true` when serving HTTPS (default `false` is for local HTTP only)
- `RATE_LIMIT_BACKEND=redis` and `REDIS_URL` when running **more than one API worker/replica** (default in-memory limiter is per-process)
- Remove `ADMIN_PASSWORD` from `.env` after first bootstrap

## Pre-deploy checklist

Use this before enabling the user-data-security changes in production. These are **operational** items, not application code defects.

### Email allowlist

- [ ] Confirm pilot/corporate domains are listed in `EMAIL_DOMAIN_ALLOWLIST_EXTRA` (comma-separated), or disable with `EMAIL_DOMAIN_ALLOWLIST_ENABLED=false` if not ready
- [ ] Communicate to operators: **existing users** can still log in; allowlist applies to **new signups** and **profile email changes** only

Bundled consumer providers live in `server/app/resources/email_domain_allowlist.conf`. Custom domains (e.g. `@acmecorp.com`) are rejected until added to `EMAIL_DOMAIN_ALLOWLIST_EXTRA`.

### Cookie auth and HTTPS

- [ ] TLS terminates before the API (reverse proxy, load balancer, or ingress)
- [ ] `AUTH_COOKIE_SECURE=true` in production `.env`
- [ ] `FRONTEND_BASE_URL` matches the HTTPS origin users use (auth emails, redirects)

Cookie auth is **on by default** (`AUTH_USE_COOKIES=true`). Without HTTPS and `AUTH_COOKIE_SECURE`, session cookies are easier to expose on plain HTTP.

### Rate limiting (login lockout)

- [ ] Single API instance: default `RATE_LIMIT_BACKEND=memory` is acceptable
- [ ] Multiple workers/replicas: set `RATE_LIMIT_BACKEND=redis` and `REDIS_URL` so lockout is shared (otherwise each process has its own counter)
- [ ] Understand lockout scope: per **client IP + email**, not account-wide across all devices (see below)

Login lockout (default: 5 failures / 15-minute sliding window on in-memory backend) returns `429` with `retry_after_seconds` for the UI countdown. **Redis** uses a TTL-based counter (slightly different semantics than in-memory sliding window; both cap brute force).

### First admin bootstrap

- [ ] On an **empty** database, startup creates admin from `ADMIN_EMAIL` / `ADMIN_PASSWORD` and sets `must_change_password=true`
- [ ] Admin must change password on first login (most routes blocked until then)
- [ ] Remove or rotate `ADMIN_PASSWORD` from deploy secrets after bootstrap

### Dev-only repo files

- [ ] `.vscode/settings.json` — editor convenience only; **not** deployed with the app; no production action

### Optional hardening (low priority)

- CSRF is enforced on profile update, change password, and account delete when cookies are enabled; **`POST /logout`** and **`POST /mfa/disable`** do not require CSRF today. Risk is low (logout requires an active session; MFA disable requires password + TOTP/backup code). Consider adding CSRF in a follow-up if cookie-only production hardening is a goal.

## Login lockout behavior (operator reference)

| Topic | Behavior |
|-------|----------|
| Lockout key | `IP address` + `email` (not browser/device alone) |
| Same user, new IP | Separate counter (may log in from mobile data while home IP is locked) |
| Different user, same office IP | Separate counters per email |
| After lockout expires | Wrong password starts counting failures again; correct password clears the counter |
| Password reset during lockout | Forgot/reset flows are separate; **login** may remain locked until the window clears |

## Retention

- DB error/log rows: `log_retention_days` (default 90) via `LogRetentionService`
- Per-user log files: `server/app/core/log_retention.py` cleanup job (daily)
- PostgreSQL backups: `docker/scripts/backup_postgres_docker.sh` (optional GPG via `BACKUP_GPG_RECIPIENT`)

## User rights

- **Export:** `GET /api/v1/auth/export` — profile, orders, PnL (broker creds redacted)
- **Delete:** `DELETE /api/v1/auth/account` — soft-delete user, wipe broker creds, revoke tokens

## Registration

Signup and profile email changes accept only domains on a bundled **provider allowlist** (`server/app/resources/email_domain_allowlist.conf`) — major consumer mail (Gmail, Outlook, Yahoo, iCloud, Rediffmail, Zoho, Proton, etc.). Unknown or temporary-mail domains (e.g. `aratrin.com`) are rejected.

- `EMAIL_DOMAIN_ALLOWLIST_ENABLED` (default `true`)
- `EMAIL_DOMAIN_ALLOWLIST_EXTRA` — additional approved domains (e.g. corporate mail for pilot users)

## Post-deploy operator checklist

- [ ] Run `tools/audit_password_hashes.py` after upgrades (`.venv/bin/python` locally, or `docker exec tradeagent-api python /app/tools/audit_password_hashes.py` in Docker)
- [ ] Confirm `GET /api/v1/admin/monitoring/security-metrics` for auth anomalies
- [ ] Review `GET /api/v1/admin/audit-logs` after admin or broker credential changes
- [ ] Encrypted DB backups stored with separate key from app encryption key

## Related

- [TOKEN_SECURITY.md](TOKEN_SECURITY.md) — log masking and broker token handling
- [ARCHITECTURE.md](../ARCHITECTURE.md) — security architecture section
