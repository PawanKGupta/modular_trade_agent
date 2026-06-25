# Linux Deployment Guide

> **Platform-Specific Guide** - This guide covers Linux-specific deployment steps including Docker Engine installation and complete Docker deployment procedures.

Complete guide for deploying Rebound — Modular Trade Agent on Linux (Ubuntu, Debian, CentOS, etc.).

## 📋 Prerequisites

### System Requirements

- **OS**: Linux distribution (Ubuntu 20.04+, Debian 11+, CentOS 8+, or similar)
- **RAM**: Minimum 2GB (4GB recommended)
- **CPU**: 2 cores minimum
- **Disk**: 10GB free space minimum
- **Access**: SSH or local terminal with sudo privileges

### Required Software

1. **Docker Engine** (version 20.10+)
   - Installation varies by distribution
   - See [Docker installation guide](https://docs.docker.com/engine/install/)

2. **Docker Compose** (version 1.29.2+)
   - Standalone binary or plugin
   - See installation instructions below

## 🚀 Quick Start (Image-Based — Recommended)

No git clone required. Pull pre-built images from GitHub Container Registry.

```bash
# Create a working directory
mkdir rebound && cd rebound

# Download Compose files
curl -O https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/docker/docker-compose.yml
curl -O https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/docker/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/.env.example

# Configure environment
cp .env.example .env
# Edit .env — set JWT_SECRET, POSTGRES_PASSWORD, SMTP settings, ADMIN_EMAIL, ADMIN_PASSWORD

# Pull images and start
export APP_VERSION=v26.2.3.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 🔧 Linux-Specific Configuration

### Docker Installation

#### Ubuntu/Debian

```bash
# Update package index
sudo apt update

# Install prerequisites
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group (to run without sudo)
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

#### CentOS/RHEL

```bash
# Install prerequisites
sudo yum install -y yum-utils

# Add Docker repository
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Install Docker Engine
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER
```

### Docker Compose (v2 plugin)

The `docker-compose-plugin` package installed above provides `docker compose` (v2). Verify:

```bash
docker compose version
# Should show Docker Compose version v2.x.x
```

### Firewall Configuration

> **Production note:** Port 8000 (API server) should ideally be restricted to loopback (`127.0.0.1`) and fronted by an nginx/Caddy reverse proxy with TLS. Opening it directly to `0.0.0.0/0` exposes the API and its `/docs` endpoint to the internet without transport encryption. See [HTTPS Setup Guide](../HTTPS_ORACLE_DUCKDNS.md) if you plan to expose this server publicly.

#### Ubuntu/Debian (UFW)

```bash
# Allow ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 5173/tcp  # Web UI
sudo ufw allow 8000/tcp  # API (restrict to reverse-proxy IP in production)

# Enable firewall
sudo ufw enable
```

#### CentOS/RHEL (firewalld)

```bash
# Allow ports
sudo firewall-cmd --permanent --add-port=22/tcp   # SSH
sudo firewall-cmd --permanent --add-port=5173/tcp # Web UI
sudo firewall-cmd --permanent --add-port=8000/tcp # API (restrict to reverse-proxy IP in production)

# Reload firewall
sudo firewall-cmd --reload
```

### Systemd Service (Optional)

For automatic startup on boot:

```bash
# Create systemd service file
sudo nano /etc/systemd/system/tradeagent-docker.service
```

```ini
[Unit]
Description=Trading Agent Docker Services
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/modular_trade_agent
ExecStart=/usr/local/bin/docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down
User=your-username
Group=your-group

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable tradeagent-docker
sudo systemctl start tradeagent-docker
```

## 📝 Configuration

### Environment Variables

The `.env` file in the project root controls configuration:

```bash
# Database (PostgreSQL in Docker)
# Note: Docker Compose overrides this with PostgreSQL connection string
# The DB_URL here is for reference - Docker uses PostgreSQL container
DB_URL=postgresql+psycopg2://trader:<your-db-password>@tradeagent-db:5432/tradeagent
# Set POSTGRES_PASSWORD in .env to the same value used above

# Timezone
TZ=Asia/Kolkata

# Encryption key for credential encryption (generate with command below)
# Generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
APP_DATA_ENCRYPTION_KEY=<generate-using-command-above>

# Admin User Auto-Creation (only on first deployment when database is empty)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<set-a-strong-unique-password>
# Generate: python3 -c "import secrets; print(secrets.token_urlsafe(16))"
ADMIN_NAME=Admin User
```

**Note:**
- The `.env` file is automatically created by the quickstart scripts (with SQLite for local dev).
- For production, edit `.env` and set `DB_URL` to PostgreSQL (as shown above) and generate `APP_DATA_ENCRYPTION_KEY`.
- Docker Compose will use PostgreSQL container regardless of `.env` DB_URL value.
- If serving over HTTPS (recommended for production), set `AUTH_COOKIE_SECURE=true` in `.env` so session cookies are only sent over encrypted connections.

### Credential Management

**Important:** Broker credentials are managed via the Web UI, not environment files.

1. Start services
2. Access Web UI at `http://localhost:5173` (or `http://your-server-ip:5173`)
3. Login with admin credentials
4. Go to Settings → Broker Credentials
5. Enter and save credentials (encrypted in database)

## 🌐 Access Services

After deployment:

- **Web Frontend**: http://localhost:5173 (or http://your-server-ip:5173)
- **API Server**: http://localhost:8000 (or http://your-server-ip:8000)
- **Health Check**: http://localhost:8000/health
- **API Docs**: http://localhost:8000/docs — disable in production if not needed (exposes full API schema)

> **Production:** Use HTTPS to protect credentials in transit. See [HTTPS Setup Guide](../HTTPS_ORACLE_DUCKDNS.md).

## 🔄 Updating the Application

Preserves all data (database, credentials, trading history) — volumes are not removed.

```bash
# Set the new version
export APP_VERSION=v26.2.3.1   # replace with target version

# Pull new images and restart
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

### Rollback

```bash
export APP_VERSION=v26.2.3    # previous version
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

### Complete Reset (Removes All Data)

**⚠️ WARNING:** This removes all volumes and deletes all data including the database.

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down -v
export APP_VERSION=v26.2.3.1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

## 🔄 Service Management

**Note:** Use the same compose files that were used to start the services. If you used the quickstart script, use just `docker-compose.yml`. If you manually deployed with production mode, use both files.

### Check Status

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps
```

### View Logs

```bash
# All services
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f api-server
```

### Stop/Start Services

```bash
# Stop
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml stop

# Start
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml start

# Restart
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart
```

## 🐛 Troubleshooting

> **For comprehensive troubleshooting covering common Docker issues, see [Docker Deployment Troubleshooting Guide](../TROUBLESHOOTING.md).**
> The sections below cover Linux-specific issues. For general issues (database, services, logs, etc.), refer to the common troubleshooting guide.

### Docker Permission Denied

**Issue**: `permission denied while trying to connect to the Docker daemon socket`

**Solution**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or:
newgrp docker
```

### Port Already in Use

**Issue**: Port 5173 or 8000 already in use

**Solution**:
```bash
# Find process using port
sudo lsof -i :5173
sudo lsof -i :8000

# Or
sudo netstat -tulpn | grep :5173
sudo netstat -tulpn | grep :8000

# Stop the process or change ports in docker-compose.yml
```

### Docker Service Not Running

**Issue**: Docker daemon not running

**Solution**:
```bash
# Start Docker service
sudo systemctl start docker

# Enable on boot
sudo systemctl enable docker

# Check status
sudo systemctl status docker
```

### Disk Space Issues

**Issue**: Running out of disk space

**Solution**:
```bash
# Clean up Docker resources
docker system prune -a

# Remove unused volumes
docker volume prune

# Check disk usage
df -h
docker system df
```

### SELinux Issues (CentOS/RHEL)

**Issue**: SELinux blocking Docker

**Solution**:
```bash
# Configure SELinux for Docker (permanent — preferred)
sudo setsebool -P container_manage_cgroup on

# Temporary diagnosis only — do NOT leave this in place on production
sudo setenforce 0
```

## 🔧 Trading Services Management

Trading services (analysis, buy orders, sell monitoring, etc.) are managed via the Web UI:

1. Access Web UI: http://localhost:5173 (or http://your-server-ip:5173)
2. Login with admin credentials
3. Go to Service Status page
4. Start/stop unified service or individual tasks
5. Services run automatically on schedule

**Note:** Trading services are not managed via Docker commands. Use the Web UI for all trading service operations.

## 🗄️ Database Management

### Access Database

```bash
# PostgreSQL (production)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -d tradeagent
```

### Run Migrations

```bash
# Migrations run automatically on API server startup
# Or manually:
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server alembic upgrade head
```

### Backup Database

```bash
# Backup PostgreSQL
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db pg_dump -U trader tradeagent > backup_$(date +%Y%m%d).sql
```

For detailed backup and restore procedures, see [Backup & Restore Guide](../BACKUP_RESTORE_UNINSTALL_GUIDE.md).

## 📚 Next Steps

1. **Access Web UI**: http://localhost:5173 (or http://your-server-ip:5173)
2. **Login** with admin credentials (from `.env`)
3. **Configure Broker Credentials** via Settings page
4. **Start Trading Services** via Service Status page

## 🔗 Related Documentation

- [Deployment Guide](../DEPLOYMENT.md) - Deployment index and routing guide
- [Troubleshooting Guide](../TROUBLESHOOTING.md) - Comprehensive troubleshooting for all platforms
- [Cloud Deployment Guides](../cloud/) - Cloud provider specific guides
- [Backup & Restore Guide](../BACKUP_RESTORE_UNINSTALL_GUIDE.md)
- [Health Check Guide](../HEALTH_CHECK.md)
