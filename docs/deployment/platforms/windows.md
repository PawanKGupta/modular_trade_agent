# Windows Deployment Guide

> **Platform-Specific Guide** - This guide covers Windows-specific deployment steps including Docker Desktop installation and complete Docker deployment procedures.

Complete guide for deploying Rebound — Modular Trade Agent on Windows.

## 📋 Prerequisites

### System Requirements

- **OS**: Windows 10 (64-bit) or Windows 11
- **RAM**: Minimum 4GB (8GB recommended)
- **CPU**: 2 cores minimum
- **Disk**: 10GB free space minimum
- **Virtualization**: Enabled (for WSL2/Docker Desktop)

### Required Software

1. **Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop
   - Includes Docker Engine, Docker Compose, and Kubernetes
   - Requires WSL2 backend (automatically configured)

2. **PowerShell 5.1+** (included with Windows 10/11)

## 🚀 Quick Start (Image-Based — Recommended)

No git clone required. Pull pre-built images from GitHub Container Registry.

```powershell
# Create a working directory
mkdir rebound; cd rebound

# Download Compose files
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/docker/docker-compose.yml" -OutFile docker-compose.yml
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/docker/docker-compose.prod.yml" -OutFile docker-compose.prod.yml
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/.env.example" -OutFile .env.example

# Configure environment
Copy-Item .env.example .env
# Edit .env — set JWT_SECRET, POSTGRES_PASSWORD, SMTP settings, ADMIN_EMAIL, ADMIN_PASSWORD

# Pull images and start
$env:APP_VERSION = "v26.2.3.1"
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 🔧 Windows-Specific Configuration

### WSL2 Backend

Docker Desktop for Windows uses WSL2 (Windows Subsystem for Linux 2) as the backend:

1. **Enable WSL2** (if not already enabled):
   ```powershell
   # Run PowerShell as Administrator
   wsl --install
   ```

2. **Verify WSL2**:
   ```powershell
   wsl --list --verbose
   ```

3. **Docker Desktop Settings**:
   - Open Docker Desktop
   - Go to Settings → General
   - Ensure "Use the WSL 2 based engine" is checked

### File Paths

- **Project Location**: Use standard Windows paths (e.g., `C:\Users\YourName\Projects\modular_trade_agent`)
- **Docker Volumes**: Mapped to Windows paths automatically
- **Line Endings**: Git should handle CRLF/LF conversion automatically

### Firewall Configuration

Windows Firewall may prompt for Docker network access:

1. **Allow Docker** when Windows Firewall prompts
2. **Or manually configure**:
   - Open Windows Defender Firewall
   - Allow Docker Desktop through firewall
   - Allow ports 5173 (frontend) and 8000 (API)

### Port Conflicts

If ports are already in use:

1. **Check port usage**:
   ```powershell
   netstat -ano | findstr :5173
   netstat -ano | findstr :8000
   ```

2. **Stop conflicting services** or change ports in `docker/docker-compose.yml`

## 📝 Configuration

### Environment Variables

The `.env` file in the project root controls configuration:

```bash
# Database (PostgreSQL in Docker)
# Note: Docker Compose overrides this with PostgreSQL connection string
# The DB_URL here is for reference - Docker uses PostgreSQL container
DB_URL=postgresql+psycopg2://trader:changeme@tradeagent-db:5432/tradeagent

# Timezone
TZ=Asia/Kolkata

# Encryption key for credential encryption (generate with command below)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
APP_DATA_ENCRYPTION_KEY=<generate-using-command-above>

# Admin User Auto-Creation (only on first deployment when database is empty)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeThisPassword123!
ADMIN_NAME=Admin User
```

**Note:**
- The `.env` file is automatically created by the quickstart scripts (with SQLite for local dev).
- For production, edit `.env` and set `DB_URL` to PostgreSQL (as shown above) and generate `APP_DATA_ENCRYPTION_KEY`.
- Docker Compose will use PostgreSQL container regardless of `.env` DB_URL value.

### Credential Management

**Important:** Broker credentials are managed via the Web UI, not environment files.

1. Start services
2. Access Web UI at `http://localhost:5173`
3. Login with admin credentials
4. Go to Settings → Broker Credentials
5. Enter and save credentials (encrypted in database)

## 🌐 Access Services

After deployment:

- **Web Frontend**: http://localhost:5173
- **API Server**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **API Docs**: http://localhost:8000/docs

## 🔄 Updating the Application

Preserves all data (database, credentials, trading history) — volumes are not removed.

```powershell
# Set the new version
$env:APP_VERSION = "v26.2.3.1"   # replace with target version

# Pull new images and restart
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

### Rollback

```powershell
$env:APP_VERSION = "v26.2.3"    # previous version
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

### Complete Reset (Removes All Data)

**⚠️ WARNING:** This removes all volumes and deletes all data including the database.

```powershell
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down -v
$env:APP_VERSION = "v26.2.3.1"
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

## 🔄 Service Management

### Using Docker Desktop GUI

1. Open Docker Desktop
2. Navigate to "Containers" tab
3. View logs, restart, stop services from GUI

### Using PowerShell

**Note:** Use the same compose files that were used to start the services. If you used the quickstart script, use just `docker-compose.yml`. If you manually deployed with production mode, use both files.

```powershell
# Check status (use same files as deployment)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps

# View logs
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f

# Stop services
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml stop

# Start services
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml start

# Restart services
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart
```

## 🐛 Troubleshooting

> **For comprehensive troubleshooting covering common Docker issues, see [Docker Deployment Troubleshooting Guide](../TROUBLESHOOTING.md).**
> The sections below cover Windows-specific issues. For general issues (database, services, logs, etc.), refer to the common troubleshooting guide.

### Docker Desktop Not Starting

**Issue**: Docker Desktop fails to start

**Solutions**:
1. Ensure WSL2 is installed and updated
2. Restart Windows
3. Check Windows updates
4. Reinstall Docker Desktop

### WSL2 Issues

**Issue**: WSL2 backend not working

**Solutions**:
```powershell
# Update WSL2
wsl --update

# Set default version
wsl --set-default-version 2

# Restart Docker Desktop
```

### Port Already in Use

**Issue**: Port 5173 or 8000 already in use

**Solutions**:
1. Find process using port:
   ```powershell
   netstat -ano | findstr :5173
   ```

2. Stop the process or change ports in `docker/docker-compose.yml`

### Slow Performance

**Issue**: Docker containers running slowly

**Solutions**:
1. Allocate more resources in Docker Desktop:
   - Settings → Resources → Advanced
   - Increase CPU and Memory limits

2. Ensure WSL2 integration is enabled:
   - Settings → Resources → WSL Integration
   - Enable integration with your WSL distro

### File Permission Issues

**Issue**: Permission errors when accessing files

**Solutions**:
1. Ensure Docker Desktop has access to the project folder
2. Check Windows file permissions
3. Run PowerShell as Administrator if needed

## 🔧 Trading Services Management

Trading services (analysis, buy orders, sell monitoring, etc.) are managed via the Web UI:

1. Access Web UI: http://localhost:5173
2. Login with admin credentials
3. Go to Service Status page
4. Start/stop unified service or individual tasks
5. Services run automatically on schedule

**Note:** Trading services are not managed via Docker commands. Use the Web UI for all trading service operations.

## 🗄️ Database Management

### Access Database

```powershell
# PostgreSQL (production)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -d tradeagent
```

### Run Migrations

```powershell
# Migrations run automatically on API server startup
# Or manually:
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server alembic upgrade head
```

### Backup Database

```powershell
# Backup PostgreSQL
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db pg_dump -U trader tradeagent > backup_$(Get-Date -Format 'yyyyMMdd').sql
```

For detailed backup and restore procedures, see [Backup & Restore Guide](../BACKUP_RESTORE_UNINSTALL_GUIDE.md).

## 📚 Next Steps

1. **Access Web UI**: http://localhost:5173
2. **Login** with admin credentials (from `.env`)
3. **Configure Broker Credentials** via Settings page
4. **Start Trading Services** via Service Status page

## 🔗 Related Documentation

- [Deployment Guide](../DEPLOYMENT.md) - Deployment index and routing guide
- [Troubleshooting Guide](../TROUBLESHOOTING.md) - Comprehensive troubleshooting for all platforms
- [Backup & Restore Guide](../BACKUP_RESTORE_UNINSTALL_GUIDE.md)
- [Health Check Guide](../HEALTH_CHECK.md)
