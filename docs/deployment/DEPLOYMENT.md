# Deployment Guide

> **Deployment Index** - This guide serves as an entry point to route you to the appropriate deployment guide based on your platform and requirements.

## 🎯 Recommended: Docker Deployment

**Docker is the recommended deployment method** for all platforms. It provides:
- ✅ Platform independence (Windows, Linux, macOS, Cloud)
- ✅ Simplified setup (one command)
- ✅ Consistent environment across platforms
- ✅ Easy updates and maintenance
- ✅ Better isolation and security

## 📚 Choose Your Deployment Guide

### Platform-Specific Guides (Recommended)

Select your operating system for complete Docker deployment instructions:

- **[Windows Deployment Guide](platforms/windows.md)** ⭐ - Windows 10/11 deployment
  - Docker Desktop installation
  - WSL2 configuration
  - Complete Docker deployment steps
  - Windows-specific troubleshooting

- **[Linux Deployment Guide](platforms/linux.md)** ⭐ - Linux (Ubuntu, Debian, CentOS) deployment
  - Docker Engine installation
  - Complete Docker deployment steps
  - Linux-specific troubleshooting

- **[macOS Deployment Guide](platforms/macos.md)** ⭐ - macOS deployment
  - Docker Desktop installation
  - Apple Silicon support
  - Complete Docker deployment steps
  - macOS-specific troubleshooting

### Cloud Provider Guides

For cloud provider specific deployment instructions:

- **[Oracle Cloud](cloud/oracle-cloud.md)** - Oracle Cloud Infrastructure (OCI) deployment
  - VM creation and configuration
  - Firewall setup
  - Complete Docker deployment on Oracle Cloud
- **[HTTPS + DuckDNS](HTTPS_ORACLE_DUCKDNS.md)** - Let's Encrypt on `reboundsignals.duckdns.org` (host nginx → Docker)

### Supporting Guides

- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common troubleshooting issues and solutions
- **[Backup & Restore Guide](BACKUP_RESTORE_UNINSTALL_GUIDE.md)** - Database backup and restore procedures
- **[Health Check Guide](HEALTH_CHECK.md)** - Monitoring and health check procedures

## 🚀 Quick Start

### Windows
```powershell
.\docker\docker-quickstart.ps1
```

### Linux/Mac
```bash
./docker/docker-quickstart.sh
```

**Access:**
- Web UI: http://localhost:5173
- API: http://localhost:8000
- Health: http://localhost:8000/health

## 📋 Deployment Checklist

- [ ] Docker installed (version 20.10+)
- [ ] Docker Compose installed (version 1.29.2+)
- [ ] Repository cloned with Git LFS
- [ ] `.env` file configured
- [ ] Services started and running
- [ ] Web UI accessible
- [ ] Admin user created
- [ ] Broker credentials configured via Web UI
- [ ] Trading services started via Web UI
- [ ] Health check passing

## Upgrading to 26.2.1

From **v26.2**, **v26.2.0**, or **`releases/rebound_2620`** deployments:

1. **Backup** the database ([Postgres backup guide](POSTGRES_DOCKER_BACKUP_CRON.md)).
2. Pull branch `releases/rebound_2621` or tag **`v26.2.1`**.
3. Merge new variables from [`.env.example`](../../.env.example) — especially **`SMTP_*`**, billing/Razorpay, OHLCV/NSE, and news settings.
4. Rebuild and restart containers (see [Docker README](../../docker/README.md)).
5. Run **`alembic upgrade head`** (automatic on API startup in Docker; verify with `alembic current`).
6. Post-deploy smoke: signup/verify login, Billing pages, admin run-once analysis.

Full checklist: [RELEASE_PLAN_V26.2.1.md](../development/RELEASE_PLAN_V26.2.1.md). Release notes: [CHANGELOG.md](../../CHANGELOG.md).

**Breaking notes:** Activity Log UI removed (use Log Viewer); market analysis run-once is **admin-only**; in-app subscription catalog removed in favor of performance-fee billing.

## Upgrading to 26.2.2.1

From **`v26.2.2`**, **`releases/rebound_2622`**, or earlier 26.2.x deployments:

1. Pull branch `hotfix/rebound_26221` or tag **`v26.2.2.1`**.
2. Rebuild and restart Web UI containers (or package/deploy the updated frontend files).
3. Post-deploy smoke: verify MFA setup renders QR code, verify MFA login challenge is prompted inline at login.

Full checklist: [RELEASE_PLAN_V26.2.2.1.md](../development/RELEASE_PLAN_V26.2.2.1.md). Release notes: [CHANGELOG.md](../../CHANGELOG.md).

## Upgrading to 26.2.2

From **`v26.2.1`**, **`releases/rebound_2621`**, or earlier 26.2.x deployments:

1. **Backup** the database ([Postgres backup guide](POSTGRES_DOCKER_BACKUP_CRON.md)).
2. Pull branch `releases/rebound_2622` or tag **`v26.2.2`**.
3. Merge new variables from [`.env.example`](../../.env.example) — especially **`EMAIL_DOMAIN_ALLOWLIST_*`**, auth cookie/rate-limit settings, and notification prefs. Complete the [user data security pre-deploy checklist](../security/USER_DATA_SECURITY.md).
4. Rebuild and restart containers (see [Docker README](../../docker/README.md)).
5. Run **`alembic upgrade head`** (automatic on API startup in Docker; verify with `alembic current`). Four Alembic revisions since 26.2.1.
6. Post-deploy smoke: login + page refresh, signup allowlist, Service Status, `/help`, trading path in your environment.

Full checklist: [RELEASE_PLAN_V26.2.2.md](../development/RELEASE_PLAN_V26.2.2.md). Release notes: [CHANGELOG.md](../../CHANGELOG.md).

**Notable changes:** User-data-security schema and session model; service status notifications default off; paper/live trading parity fixes; email domain allowlist for new signups.

## Upgrading to 26.2.3.1

From **`v26.2.3`**, **`releases/rebound_2623`**, or earlier 26.2.x deployments:

1. Pull branch `hotfix/limit_order_fill_price` or tag **`v26.2.3.1`**.
2. Restart the Python trading service. No frontend rebuild or DB migration needed.
3. Post-deploy smoke: run a paper trading cycle and confirm limit buy orders fill at the opening price (not yesterday's close) when the stock gaps down.

Full checklist: [RELEASE_PLAN_V26.2.3.1.md](../development/RELEASE_PLAN_V26.2.3.1.md). Release notes: [CHANGELOG.md](../../CHANGELOG.md).

## Upgrading to 26.2.3

**Branch:** `releases/rebound_2623` · **No Alembic migrations** (safe, no DB changes)

1. **Backup** Postgres (always recommended before any deploy).
2. Pull `releases/rebound_2623` (or tag `v26.2.3`).
3. No `.env` changes required for standard usage. Optional: set `ML_CONFIDENCE_THRESHOLD=0.6` explicitly if previously overriding the old 0.5 default.
4. Rebuild and restart the Docker stack: `docker compose up --build -d`.
   - The `trading_models` volume is new in this release. On first start it will be created and auto-seeded from the image-baked baseline model. If you already have a custom model, activate it via the ML Training UI after startup — this writes it to the volume.
5. No `alembic upgrade head` required (no migrations). Verify with `alembic current` if desired.
6. **Post-deploy smoke:**
   - Login → Buying Zone (check ML Verdict / ML Confidence columns)
   - Trading Config → all sections collapsed; expand each, confirm values persist on save
   - Notification Preferences → accordion sections work
   - Admin → ML Training → activate a model and confirm analysis picks it up
   - `/help/ml-signals` loads without login

Full checklist: [RELEASE_PLAN_V26.2.3.md](../development/RELEASE_PLAN_V26.2.3.md). Release notes: [CHANGELOG.md](../../CHANGELOG.md).

**Notable changes:** ML leakage fixes and walk-forward validated threshold (0.6); Docker model persistence volume; UI accordion polish (Trading Config + Notifications); stale-signal expiry fix.

## ML Model Persistence (Docker)

The API container mounts a named Docker volume for ML model files:

```
trading_models:/app/models
```

This volume is declared in both `docker/docker-compose.yml` and `docker/docker-compose.prod.yml`. Key properties:

- **Survives restarts and rebuilds**: The canonical verdict model (`models/verdict_model_random_forest.pkl`) is not lost when you `docker compose up --build` or restart the container.
- **Auto-seeded on first boot**: If the volume is empty (fresh install), the entrypoint copies the baseline model baked into the image (`/app/models_default/`) into `/app/models/` before the server starts. Subsequent boots skip this step.
- **Activated models persist**: When you activate a model in the ML Training UI, the artifact is written to this volume and remains active across restarts.

If you ever need to reset to the image's bundled baseline model:
```bash
# Stop the stack, remove the volume, then restart (auto-seed re-runs)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down
docker volume rm trading_models
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

See [ML Complete Guide](../architecture/ML_COMPLETE_GUIDE.md) for full detail on model activation, registration, and the canonical path deploy.

## 🔗 Related Documentation

- [Docker README](../../docker/README.md) - Docker-specific documentation
- [Getting Started Guide](../guides/GETTING_STARTED.md) - Initial setup guide
- [User Guide](../guides/USER_GUIDE.md) - End-user documentation
- [API Documentation](../API.md) - API reference

## 💡 Need Help?

- Check [Troubleshooting Guide](TROUBLESHOOTING.md) - Comprehensive troubleshooting for all platforms
- See platform-specific guides above for complete deployment instructions
- See cloud provider guides for cloud-specific deployment
