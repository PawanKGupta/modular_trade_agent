# Getting Started Guide

Complete guide to set up and run Rebound — Modular Trade Agent.

## Prerequisites

- **Python 3.12+** (for backend)
- **Node.js 20+** (for frontend)
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

# Optional: CPU headline sentiment (Hugging Face Transformers; no paid news API).
# Recommended on production Linux (e.g. Oracle Cloud) after installing PyTorch CPU wheels:
#   pip install torch --index-url https://download.pytorch.org/whl/cpu
#   pip install -r requirements-sentiment.txt
#
# See docs/guides/TRADING_CONFIG.md (News Sentiment) for env vars.

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

# Encryption Key for credentials (required for broker/MFA secret storage)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
APP_DATA_ENCRYPTION_KEY=your-base64-encoded-key

# CORS (for development)
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000

# Timezone
TZ=Asia/Kolkata

# Daily OHLCV (NSE bhavcopy → price_cache): see docs/guides/BULK_ANALYSIS_RELIABILITY.md
# OHLCV_DAILY_SOURCE=nse   # or nse_with_yahoo_fallback until backfill completes
```

#### Step 4: Initialize Database

The application will auto-create tables on first run. **Production and upgrades should use Alembic:**

```bash
alembic upgrade head
```

> **Auth emails (26.2.1+):** If you enable public signup, configure **`SMTP_HOST`**, **`SMTP_USER`**, **`SMTP_PASSWORD`**, and **`SMTP_FROM_EMAIL`** in `.env` before users sign up. Without SMTP, verification and password-reset emails cannot be sent. See [`.env.example`](../../.env.example).

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
     - Enter your Telegram Chat ID
     - Telegram Bot Token must be set in `.env` file (`TELEGRAM_BOT_TOKEN`)
   - Configure **Email Settings** (optional)
     - Enter your email address
     - SMTP configuration must be set in `.env` file (see SMTP settings above)
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

### 5. Check ML predictions

Rebound ships with a pre-trained ML classifier that runs on every analysis run and adds a confidence score to each signal. It is **on by default** — nothing to configure for standard usage.

**Verify it is active:**
1. Go to **Trading Config → ML Configuration**
2. Confirm **Enable ML Predictions** is checked
3. Note the **ML Confidence Threshold** (default 0.6 — signals must score ≥ 60 % to be promoted)

**See ML scores in Buying Zone:**
- Open **Buying Zone** and use the column selector to enable **ML Verdict** and **ML Confidence** columns
- Signals show both the rule-based assessment and the model's confidence side-by-side
- High-confidence signals (≥ 0.75) are the strongest combined picks

**Want to retrain on your own trade history?** Go to **Admin → ML Training** after building up trade records. See [ML Complete Guide](../architecture/ML_COMPLETE_GUIDE.md) for details.

### 6. Bulk backtest (CLI, optional)

For ChartInk list analysis with integrated backtest scoring:

```bash
# Merge config/bulk_reliability.env.example into .env (MAX_CONCURRENT_ANALYSES=1, etc.)
python trade_agent.py --backtest
```

See [Bulk analysis reliability](BULK_ANALYSIS_RELIABILITY.md) for engine labels (`backtest_mode` in CSV) and validation.

```bash
.venv\Scripts\python.exe tools/validate_bulk_analysis_final.py
```
3. Review and approve/reject signals as needed

## Common Issues

### Cursor / VS Code forwarding production to localhost

If **Docker is stopped** but `http://localhost:5173` still loads the app (often with `Server: nginx` in DevTools), **Cursor is port-forwarding** your live Oracle/DuckDNS stack (`5173` web, `8000` API) to your PC. That does **not** change production; it only hijacks local URLs.

**One-time cleanup (local only, production unaffected):**

1. In Cursor: **Ports** panel → stop forwarding **5173** and **8000** (or disconnect Remote SSH to the VM).
2. Reload the Cursor window so workspace settings apply (this repo disables auto-forward for those ports).

**Local dev on safe ports (recommended when forwards are active):**

```powershell
# Windows — starts API :8001 + Vite :5174
.\scripts\dev-local.ps1

# Or manually:
.\.venv\Scripts\python.exe -m uvicorn server.app.main:app --reload --port 8001
cd web
npm run dev:local
```

Open **http://localhost:5174** (not 5173). Check DevTools → Network: API calls should go to `http://localhost:8001/api/v1/...`.

```bash
# Linux/macOS
./scripts/dev-local.sh
```

### Port Already in Use

If port 8000 or 5173 is already in use:

```bash
# Backend - use different port
uvicorn server.app.main:app --reload --port 8001

# Frontend - edit web/vite.config.ts or use environment variable
VITE_API_URL=http://localhost:8001 npm run dev
# Or use the dedicated local script (web on 5174):
npm run dev:local
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

If the API fails to start with a `python_multipart` / multipart import error, you likely installed only the root `requirements.txt`. Admin billing QR upload needs **`python-multipart`** from `server/requirements.txt` — run the second `pip install` line above.

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

- Review log files in `logs/` directory
- Check application logs in the web UI (Admin → Logs)
- Review [User Guide](USER_GUIDE.md) for feature usage
- Check [API Documentation](API.md) for programmatic access
