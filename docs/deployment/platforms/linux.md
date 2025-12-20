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

3. **Git** with Git LFS support
   ```bash
   sudo apt install git git-lfs  # Ubuntu/Debian
   sudo yum install git git-lfs  # CentOS/RHEL
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
# Ensure Docker is installed and running
docker --version
docker-compose --version

# Navigate to project root
cd /path/to/modular_trade_agent

# Create .env file (if not exists)
# Edit .env with your configuration

# Build and start (production mode with named volumes)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d

# Or for development (uses bind mounts, faster for code changes):
# docker-compose -f docker/docker-compose.yml build
# docker-compose -f docker/docker-compose.yml up -d
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

### Docker Compose Installation (Standalone)

If Docker Compose plugin is not available:

```bash
# Download Docker Compose v1
sudo curl -L "https://github.com/docker/compose/releases/download/v1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make executable
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker-compose --version
```

### Firewall Configuration

#### Ubuntu/Debian (UFW)

```bash
# Allow ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 5173/tcp  # Web UI
sudo ufw allow 8000/tcp  # API

# Enable firewall
sudo ufw enable
```

#### CentOS/RHEL (firewalld)

```bash
# Allow ports
sudo firewall-cmd --permanent --add-port=22/tcp   # SSH
sudo firewall-cmd --permanent --add-port=5173/tcp # Web UI
sudo firewall-cmd --permanent --add-port=8000/tcp # API

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
ExecStart=/usr/local/bin/docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down
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
2. Access Web UI at `http://localhost:5173` (or `http://your-server-ip:5173`)
3. Login with admin credentials
4. Go to Settings → Broker Credentials
5. Enter and save credentials (encrypted in database)

## 🌐 Access Services

After deployment:

- **Web Frontend**: http://localhost:5173 (or http://your-server-ip:5173)
- **API Server**: http://localhost:8000 (or http://your-server-ip:8000)
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

**Note:** Use the same compose files that were used to start the services. If you used the quickstart script, use just `docker-compose.yml`. If you manually deployed with production mode, use both files.

### Check Status

```bash
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps
```

### View Logs

```bash
# All services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f api-server
```

### Stop/Start Services

```bash
# Stop
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml stop

# Start
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml start

# Restart
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart
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
# Set SELinux to permissive (temporary)
sudo setenforce 0

# Or configure SELinux for Docker (permanent)
sudo setsebool -P container_manage_cgroup on
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
