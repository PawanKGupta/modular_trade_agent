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
- `auth_cookie_secure=true` when serving HTTPS
- Remove `ADMIN_PASSWORD` from `.env` after first bootstrap

## Retention

- DB error/log rows: `log_retention_days` (default 90) via `LogRetentionService`
- Per-user log files: `server/app/core/log_retention.py` cleanup job (daily)
- PostgreSQL backups: `docker/scripts/backup_postgres_docker.sh` (optional GPG via `BACKUP_GPG_RECIPIENT`)

## User rights

- **Export:** `GET /api/v1/auth/export` — profile, orders, PnL (broker creds redacted)
- **Delete:** `DELETE /api/v1/auth/account` — soft-delete user, wipe broker creds, revoke tokens

## Operator checklist

- [ ] Run `tools/audit_password_hashes.py` after upgrades
- [ ] Confirm `GET /api/v1/admin/monitoring/security-metrics` for auth anomalies
- [ ] Review `GET /api/v1/admin/audit-logs` after admin or broker credential changes
- [ ] Encrypted DB backups stored with separate key from app encryption key

## Related

- [TOKEN_SECURITY.md](TOKEN_SECURITY.md) — log masking and broker token handling
- [ARCHITECTURE.md](../ARCHITECTURE.md) — security architecture section
