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

## 🔗 Related Documentation

- [Docker README](../../docker/README.md) - Docker-specific documentation
- [Getting Started Guide](../guides/GETTING_STARTED.md) - Initial setup guide
- [User Guide](../guides/USER_GUIDE.md) - End-user documentation
- [API Documentation](../API.md) - API reference

## 💡 Need Help?

- Check [Troubleshooting Guide](TROUBLESHOOTING.md) - Comprehensive troubleshooting for all platforms
- See platform-specific guides above for complete deployment instructions
- See cloud provider guides for cloud-specific deployment
