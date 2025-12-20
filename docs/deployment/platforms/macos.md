# macOS Deployment Guide

> **Platform-Specific Guide** - This guide covers macOS-specific deployment steps including Docker installation and complete Docker deployment procedures.

Complete guide for deploying Rebound — Modular Trade Agent on macOS.

## 📋 Prerequisites

### System Requirements

- **OS**: macOS 10.15 (Catalina) or later (macOS 12+ recommended)
- **RAM**: Minimum 4GB (8GB recommended)
- **CPU**: Intel or Apple Silicon (M1/M2/M3)
- **Disk**: 10GB free space minimum

### Required Software

1. **Docker Desktop for Mac**
   - Download from: https://www.docker.com/products/docker-desktop
   - Includes Docker Engine, Docker Compose, and Kubernetes
   - Supports both Intel and Apple Silicon

2. **Git** (usually pre-installed)
   ```bash
   # Install Git LFS
   brew install git-lfs
   # Or download from: https://git-lfs.github.com
   ```

3. **Homebrew** (optional, for package management)
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

## 🚀 Quick Start

### Automated Deployment

```bash
# Clone repository
git clone <repository-url>
cd modular_trade_agent

# Install Git LFS (required for ML models)
git lfs install
git lfs pull

# Run quickstart script
./docker/docker-quickstart.sh
```

The script will:
1. ✅ Check Docker installation
2. ✅ Create `.env` file if missing
3. ✅ Build Docker images
4. ✅ Start all services
5. ✅ Display access URLs

### Manual Deployment

```bash
# Ensure Docker Desktop is running
# Check Docker status
docker --version
docker-compose --version

# Navigate to project root
cd ~/path/to/modular_trade_agent

# Create .env file (if not exists)
# Edit .env with your configuration

# Build and start (production mode with named volumes)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d

# Or for development (uses bind mounts, faster for code changes):
# docker-compose -f docker/docker-compose.yml build
# docker-compose -f docker/docker-compose.yml up -d
```

## 🔧 macOS-Specific Configuration

### Docker Desktop Setup

1. **Download and Install**:
   - Download Docker Desktop from https://www.docker.com/products/docker-desktop
   - Open the `.dmg` file and drag Docker to Applications

2. **First Launch**:
   - Open Docker Desktop from Applications
   - Grant necessary permissions when prompted
   - Wait for Docker to start (whale icon in menu bar)

3. **Configure Resources**:
   - Docker Desktop → Settings → Resources
   - Allocate at least 4GB RAM
   - Allocate at least 2 CPU cores

### Apple Silicon (M1/M2/M3) Considerations

Docker Desktop for Apple Silicon includes Rosetta 2 support:

1. **No special configuration needed** - Docker handles architecture translation
2. **Performance**: Native ARM images run faster, x86 images work via Rosetta
3. **Image compatibility**: Most images support multi-architecture

### File Paths

- **Project Location**: Use standard macOS paths (e.g., `~/Projects/modular_trade_agent`)
- **Docker Volumes**: Mapped to macOS paths automatically
- **Permissions**: macOS handles file permissions automatically

### Firewall Configuration

macOS Firewall may prompt for network access:

1. **System Preferences** → **Security & Privacy** → **Firewall**
2. **Allow Docker** when prompted
3. **Or manually allow**:
   - Click "Firewall Options"
   - Add Docker Desktop to allowed applications

### Port Conflicts

If ports are already in use:

1. **Check port usage**:
   ```bash
   lsof -i :5173
   lsof -i :8000
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
# Generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=<generate-using-command-above>

# Admin User Auto-Creation (only on first deployment when database is empty)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeThisPassword123!
ADMIN_NAME=Admin User
```

**Note:**
- The `.env` file is automatically created by the quickstart scripts (with SQLite for local dev).
- For production, edit `.env` and set `DB_URL` to PostgreSQL (as shown above) and generate `ENCRYPTION_KEY`.
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

### Option 1: Rebuild with Data Preservation (Recommended)

Preserves all data including database, credentials, and trading history:

```bash
# Pull latest code
git pull origin main
git lfs pull  # If ML models were updated

# Rebuild and restart (volumes preserved)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --build
```

### Option 2: Complete Rebuild (Removes All Data)

**⚠️ WARNING:** This removes all containers and volumes, deleting all data.

```bash
# Pull latest code
git pull origin main
git lfs pull

# Stop and remove containers (WARNING: Removes volumes and data!)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down

# Rebuild images
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build

# Start containers
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

### Rebuild Specific Service Only

```bash
# Rebuild and restart only API server
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --build api-server

# Rebuild and restart only frontend
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --build web-frontend
```

## 🔄 Service Management

### Using Docker Desktop GUI

1. Open Docker Desktop
2. Navigate to "Containers" tab
3. View logs, restart, stop services from GUI

### Using Terminal

**Note:** Use the same compose files that were used to start the services. If you used the quickstart script, use just `docker-compose.yml`. If you manually deployed with production mode, use both files.

```bash
# Check status (use same files as deployment)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps

# View logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f

# Stop services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml stop

# Start services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml start

# Restart services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart
```

## 🐛 Troubleshooting

> **For comprehensive troubleshooting covering common Docker issues, see [Docker Deployment Troubleshooting Guide](../TROUBLESHOOTING.md).**
> The sections below cover macOS-specific issues. For general issues (database, services, logs, etc.), refer to the common troubleshooting guide.

### Docker Desktop Not Starting

**Issue**: Docker Desktop fails to start

**Solutions**:
1. Restart Docker Desktop
2. Check Activity Monitor for stuck Docker processes
3. Restart macOS
4. Reinstall Docker Desktop

### Permission Issues

**Issue**: Permission denied errors

**Solutions**:
```bash
# Ensure Docker Desktop has Full Disk Access
# System Preferences → Security & Privacy → Privacy → Full Disk Access
# Add Docker Desktop

# Check Docker permissions
docker ps
```

### Port Already in Use

**Issue**: Port 5173 or 8000 already in use

**Solutions**:
```bash
# Find process using port
lsof -i :5173
lsof -i :8000

# Kill the process (if needed)
kill -9 <PID>

# Or change ports in docker-compose.yml
```

### Slow Performance

**Issue**: Docker containers running slowly

**Solutions**:
1. Allocate more resources in Docker Desktop:
   - Docker Desktop → Settings → Resources
   - Increase CPU and Memory limits

2. Check Activity Monitor for resource usage

3. Close unnecessary applications

### Apple Silicon Compatibility

**Issue**: Images not compatible with Apple Silicon

**Solutions**:
1. Most images support multi-architecture automatically
2. If issues occur, check image documentation
3. Use `--platform linux/amd64` flag if needed (slower via Rosetta)

### File Sharing Issues

**Issue**: Docker can't access project files

**Solutions**:
1. Ensure project is in an accessible location (not in system-protected folders)
2. Check Docker Desktop → Settings → Resources → File Sharing
3. Add project directory if needed

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

```bash
# PostgreSQL (production)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -d tradeagent
```

### Run Migrations

```bash
# Migrations run automatically on API server startup
# Or manually:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server alembic upgrade head
```

### Backup Database

```bash
# Backup PostgreSQL
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db pg_dump -U trader tradeagent > backup_$(date +%Y%m%d).sql
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
