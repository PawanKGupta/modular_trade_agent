# Docker Setup Guide

Complete guide for running the Trading Agent with Docker.

## 🚀 Quick Start

### Windows (PowerShell)
```powershell
# From project root
.\docker\docker-quickstart.ps1
```

### Linux/Mac
```bash
# From project root
./docker/docker-quickstart.sh
```

### Manual Start
```bash
cd docker
docker compose -f docker-compose.yml up -d
```

**Access:**
- Web UI: http://localhost:5173
- API: http://localhost:8000
- Health: http://localhost:8000/health

---

## 📋 Prerequisites

- Docker Desktop installed and running

---

## ⚙️ Configuration

### 1. Create `.env` File (Project Root)

Create `.env` in the project root with:

```bash
# Database
DB_URL=sqlite:///./data/app.db

# Timezone
TZ=Asia/Kolkata

# Admin User (auto-created on first deployment when DB is empty)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change_me
ADMIN_NAME=Admin User

# Optional: Encryption key for credential encryption
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# APP_DATA_ENCRYPTION_KEY=your_base64_encoded_key

# Optional: Telegram Bot Token (for notifications)
# Get from @BotFather on Telegram
# TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Optional: Email Notifications (SMTP Configuration)
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password-here
# SMTP_FROM_EMAIL=your-email@gmail.com
# SMTP_USE_TLS=true
```

**Important:** Admin user is only created automatically when:
- Database is empty (0 users)
- `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set in `.env`

### 2. Credentials Management

**All credentials are stored in the database** (not in `.env` files):

1. Start Docker: `docker compose -f docker-compose.yml up -d`
2. Access web UI: http://localhost:5173
3. Login with admin credentials
4. Go to **Settings**:
   - Configure **Broker credentials** (Kotak Neo)
   - Configure **Telegram settings**

**Note:** No `.env` file fallback for credentials - configure via web UI only.

---

## 🛠️ Common Commands

### Start Services
```bash
cd docker
docker compose -f docker-compose.yml up -d
```

### Stop Services
```bash
docker compose -f docker-compose.yml down
```

### View Logs
```bash
# All services
docker compose -f docker-compose.yml logs -f

# Specific service
docker compose -f docker-compose.yml logs -f api-server
docker compose -f docker-compose.yml logs -f web-frontend
```

### Restart Service
```bash
docker compose -f docker-compose.yml restart api-server
```

### Pull a New Image Version
```bash
export APP_VERSION=v26.2.3.1   # Linux/macOS
# $env:APP_VERSION = "v26.2.3.1"  # Windows PowerShell
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### News sentiment (CPU Transformers)

The **`api-server`** image (`Dockerfile.api`) installs **CPU PyTorch** and **`requirements-sentiment.txt`** (`transformers`, `safetensors`) so **`NEWS_SENTIMENT_BACKEND=auto`** can load a HF sentiment pipeline without extra pip on the host. Expect a **larger image** and a **first-run model download** to the Hugging Face cache inside the container. Tune with env vars (`NEWS_SENTIMENT_TRANSFORMER_MODEL`, etc.); see `docs/guides/TRADING_CONFIG.md`.

### Run Database Migrations Manually
```bash
# If you need to run migrations manually (usually runs automatically on startup)
docker compose -f docker-compose.yml exec api-server python -m alembic upgrade head
```

### Upgrading to 26.2.1

1. Backup Postgres (`docker/scripts/backup_postgres_docker.sh` or your operator backup).
2. Update `.env` from repo `.env.example` (SMTP, billing, OHLCV).
3. `APP_VERSION=v26.2.1 docker compose -f docker-compose.yml -f docker-compose.prod.yml pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
4. Confirm API logs show Alembic upgrade success; run `verify_db_schema` on Postgres if needed.

See [docs/deployment/DEPLOYMENT.md](../docs/deployment/DEPLOYMENT.md#upgrading-to-2621) and [RELEASE_PLAN_V26.2.1.md](../docs/development/RELEASE_PLAN_V26.2.1.md).

### Upgrading to 26.2.2

1. Backup Postgres (`docker/scripts/backup_postgres_docker.sh` or your operator backup).
2. Update `.env` from repo `.env.example` (auth allowlist, cookie/rate-limit, notifications).
3. `APP_VERSION=v26.2.2 docker compose -f docker-compose.yml -f docker-compose.prod.yml pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
4. Confirm API logs show Alembic upgrade success; run `verify_db_schema` on Postgres if needed.

See [docs/deployment/DEPLOYMENT.md](../docs/deployment/DEPLOYMENT.md#upgrading-to-2622) and [RELEASE_PLAN_V26.2.2.md](../docs/development/RELEASE_PLAN_V26.2.2.md).

### Check Status
```bash
docker compose -f docker-compose.yml ps
```

---

## 🔧 Development Mode (Windows)

For hot reload and live code editing:

```powershell
cd docker
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

**Features:**
- API server auto-reloads on code changes
- Web frontend uses Vite dev server (HMR)
- Source code mounted for live editing

---

## ☁️ Production Deployment (Oracle Ubuntu)

```bash
# 1. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
newgrp docker

# 2. Create working directory and fetch Compose files
mkdir rebound && cd rebound
curl -O https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/docker/docker-compose.yml
curl -O https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/docker/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/.env.example

# 3. Create .env file
cp .env.example .env
# Edit .env — set JWT_SECRET, POSTGRES_PASSWORD, SMTP settings, ADMIN_EMAIL, ADMIN_PASSWORD

# 4. Pull images and start
export APP_VERSION=v26.2.3.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 5. Check status
docker compose -f docker-compose.yml ps
```

For full Oracle Cloud setup (VM creation, firewall rules), see [docs/deployment/cloud/oracle-cloud.md](../docs/deployment/cloud/oracle-cloud.md).

---

## 🔐 First Login

After starting Docker:

1. **Wait for services to start** (10-15 seconds)
2. **Access web UI**: http://localhost:5173
3. **Login with admin credentials**:
   - Email: (value from `ADMIN_EMAIL` in `.env`)
   - Password: (value from `ADMIN_PASSWORD` in `.env`)
4. **Change password** immediately after first login (recommended)

---

## 🐛 Troubleshooting

### Port Already Allocated
```bash
# Find process using port
netstat -ano | findstr :5173  # Windows
lsof -i :5173                 # Linux/Mac

# Stop and remove containers
docker compose -f docker-compose.yml down

# Restart
docker compose -f docker-compose.yml up -d
```

### Can't Access Web UI (404)
- Check if container is running: `docker compose -f docker-compose.yml ps`
- Check logs: `docker compose -f docker-compose.yml logs web-frontend`
- Pull a fresh image: `APP_VERSION=v26.2.3.1 docker compose -f docker-compose.yml -f docker-compose.prod.yml pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

### Login Fails
- Verify admin user exists: Check logs for `[Startup] Creating admin user`
- Verify `.env` has `ADMIN_EMAIL` and `ADMIN_PASSWORD` set
- Check API logs: `docker compose -f docker-compose.yml logs api-server`

### Database Issues
- Delete database to reset: `Remove-Item data\app.db` (Windows) or `rm data/app.db` (Linux/Mac)
- Restart API server: `docker compose -f docker-compose.yml restart api-server`
- Admin user will be auto-created if DB is empty

### Services Not Starting
```bash
# Check all logs
docker compose -f docker-compose.yml logs

# Pull fresh images and restart
APP_VERSION=v26.2.3.1 docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
APP_VERSION=v26.2.3.1 docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 📁 Project Structure

```
docker/
├── Dockerfile              # Main trading service
├── Dockerfile.api          # FastAPI server
├── Dockerfile.web          # React frontend (production)
├── Dockerfile.web.dev      # React frontend (development)
├── docker-compose.yml      # Main orchestration
├── docker-compose.dev.yml  # Development overrides
├── docker-compose.prod.yml # Production overrides
├── docker-quickstart.sh    # Quick start (Linux/Mac)
├── docker-quickstart.ps1   # Quick start (Windows)
└── README.md              # This file
```

**Note:** All paths in `docker-compose.yml` are relative to the **project root**, not the `docker/` folder.

---

## 🔄 Environment-Specific Configs

### Development (Windows Local)
- Uses `docker-compose.dev.yml`
- Hot reload enabled
- Source code mounted

### Production (Oracle Ubuntu)
- Uses `docker-compose.prod.yml`
- Resource limits optimized for free tier
- Named volumes for data persistence
- **PostgreSQL backup, cron, and restore:** see [docs/deployment/POSTGRES_DOCKER_BACKUP_CRON.md](../docs/deployment/POSTGRES_DOCKER_BACKUP_CRON.md) and `docker/scripts/backup_postgres_docker.sh`

---

## 📝 Notes

- **Credentials**: All broker and Telegram credentials are stored encrypted in the database via web UI
- **Admin User**: Auto-created only on first deployment (when DB is empty)
- **Database**: SQLite by default (can switch to PostgreSQL)
- **Ports**:
  - Web: 5173
  - API: 8000

---

## 🆘 Need Help?

1. Check logs: `docker compose -f docker-compose.yml logs -f`
2. Verify services are running: `docker compose -f docker-compose.yml ps`
3. Check `.env` file exists and has required variables
4. Ensure Docker Desktop is running
