# Getting Started Guide

Complete guide to set up and run the Modular Trade Agent.

## Prerequisites

- **Python 3.12+** (for backend)
- **Node.js 18+** (for frontend)
- **Docker Desktop** (optional, for containerized deployment)
- **Git** (to clone the repository)

## Quick Start Options

### Option 1: Docker (Recommended for Beginners)

The easiest way to get started is using Docker:

```bash
# Windows
.\docker\docker-quickstart.ps1

# Linux/Mac
./docker/docker-quickstart.sh
```

This will:
1. Create a `.env` file if it doesn't exist
2. Start all services (database, API, web UI)
3. Create an admin user automatically

**Access:**
- Web UI: http://localhost:5173
- API: http://localhost:8000

See [docker/README.md](../docker/README.md) for detailed Docker documentation.

### Option 2: Manual Setup

For development or custom configuration:

#### Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd modular_trade_agent

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate
```

#### Step 2: Install Dependencies

```bash
# Install backend dependencies
pip install -r requirements.txt
pip install -r server/requirements.txt

# Install frontend dependencies
cd web
npm install
cd ..
```

#### Step 3: Configure Environment

Create a `.env` file in the project root:

```bash
# Database
DB_URL=sqlite:///./data/app.db

# Admin User (auto-created on first run if DB is empty)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change_me
ADMIN_NAME=Admin User

# JWT Secret (generate a random string)
JWT_SECRET=your-secret-key-here

# Encryption Key for credentials (optional, auto-generated if not provided)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-base64-encoded-key

# CORS (for development)
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000

# Timezone
TZ=Asia/Kolkata
```

#### Step 4: Initialize Database

The application will auto-create tables on first run. Alternatively, you can run migrations:

```bash
# If using Alembic migrations
alembic upgrade head
```

#### Step 5: Start Services

**Terminal 1 - Backend:**
```bash
# From project root
uvicorn server.app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
# From project root
cd web
npm run dev
```

#### Step 6: Access and Configure

1. Open http://localhost:5173
2. Login with admin credentials (from `.env`)
3. Go to **Settings**:
   - Configure **Broker Credentials** (Kotak Neo API)
   - Configure **Telegram Settings** (optional)
4. Go to **Trading Config** to adjust trading parameters

## First Steps After Setup

### 1. Configure Broker Credentials

1. Navigate to **Settings** in the web UI
2. Enter your Kotak Neo API credentials:
   - Consumer Key
   - Consumer Secret
   - Access Token
   - User ID
3. Click **Save** (credentials are encrypted and stored in database)

### 2. Configure Trading Parameters

1. Navigate to **Trading Config** in the web UI
2. Adjust parameters as needed:
   - RSI period (default: 10)
   - EMA periods (default: 9, 200)
   - Capital allocation
   - Risk management settings
3. Click **Save**

### 3. Test Paper Trading

Before live trading, test with paper trading:

1. Navigate to **Paper Trading** in the web UI
2. Set initial capital (default: ₹1,00,000)
3. Enable paper trading mode
4. Monitor simulated trades

### 4. View Signals

1. Navigate to **Buying Zone** to see trading signals
2. Signals are generated based on your strategy configuration
3. Review and approve/reject signals as needed

## Common Issues

### Port Already in Use

If port 8000 or 5173 is already in use:

```bash
# Backend - use different port
uvicorn server.app.main:app --reload --port 8001

# Frontend - edit web/vite.config.ts or use environment variable
VITE_API_URL=http://localhost:8001 npm run dev
```

### Database Errors

If you see database errors:

```bash
# Delete existing database (WARNING: loses data)
rm data/app.db

# Restart the application (will auto-create tables)
```

### Module Import Errors

Ensure virtual environment is activated and dependencies are installed:

```bash
# Reinstall dependencies
pip install -r requirements.txt
pip install -r server/requirements.txt
```

## Service Layer Usage (Phase 4)

The system uses a **service layer architecture** for analysis functionality. Legacy `core.*` functions are deprecated.

### Quick Example

```python
from services import AnalysisService, AsyncAnalysisService
import asyncio

# Single ticker analysis
service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS", enable_multi_timeframe=True)
print(f"Verdict: {result['verdict']}")

# Batch analysis (80% faster)
async def analyze_batch():
    async_service = AsyncAnalysisService(max_concurrent=10)
    results = await async_service.analyze_batch_async(
        tickers=["RELIANCE.NS", "TCS.NS", "INFY.NS"],
        enable_multi_timeframe=True
    )
    return results

results = asyncio.run(analyze_batch())
```

### Migration from Legacy Code

If you're using deprecated `core.*` functions, see:
- **[Migration Guide](MIGRATION_GUIDE_PHASE4.md)** - Complete migration instructions
- **[Architecture Documentation](ARCHITECTURE.md)** - Service layer details

**Key Services:**
- `AnalysisService` - Main analysis orchestration
- `AsyncAnalysisService` - Fast batch processing
- `ScoringService` - Signal scoring
- `BacktestService` - Historical backtesting
pip install -r server/requirements.txt
```

### Frontend Build Errors

```bash
# Clear node_modules and reinstall
cd web
rm -rf node_modules package-lock.json
npm install
```

## Next Steps

- Read [User Guide](USER_GUIDE.md) to learn how to use the web interface
- Review [Trading Configuration](TRADING_CONFIG.md) for strategy setup
- Check [Architecture](ARCHITECTURE.md) to understand the system design
- See [API Documentation](API.md) for programmatic access

## Getting Help

- Check [Troubleshooting](TROUBLESHOOTING.md) for common issues
- Review log files in `logs/` directory
- Check application logs in the web UI (Admin → Logs)
