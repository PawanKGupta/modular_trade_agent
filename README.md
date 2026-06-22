# Rebound — Modular Trade Agent

A professional-grade **multi-user trading system** for Indian stock markets (NSE) specializing in **mean reversion to EMA9 strategy** with automated order execution, paper trading, and comprehensive web-based management.

## ✨ Key Features

### 🎯 Trading Strategy
- **Mean Reversion to EMA9**: Identifies oversold dips (RSI10 < 30) in stocks above EMA200
- **Entry Filters**: RSI10 < 30, Price > EMA200, Clean chart, Near monthly support
- **Exit Target**: Always EMA9 (whether profit or loss)
- **Position Management**: No stop loss, averages down on further dips
- **ML Enhancement**: Predicts "Will this oversold dip bounce to EMA9?"

### 🏗️ Architecture
- **FastAPI Backend**: RESTful API with JWT authentication
- **React Frontend**: Modern web UI with real-time updates
- **Multi-User Support**: User-scoped data isolation and configuration
- **Database-Backed**: SQLite (dev) / PostgreSQL (prod) with encrypted credentials
- **Docker Ready**: Complete containerization for easy deployment

### 📊 Core Components
- **Signal Analysis**: Automated stock screening and signal generation
  - Service layer architecture with modular, testable services
  - Async batch processing (80% faster than sequential)
  - Intelligent caching (70-90% reduction in API calls)
  - T2T segment filtering (excludes Trade-to-Trade stocks)
- **Order Management**: Automated buy/sell order placement via Kotak Neo API
- **Paper Trading**: Risk-free strategy testing with realistic simulation
- **ML Training**: Automated model training and retraining
- **Service Management**: Scheduled tasks for pre-market, monitoring, and EOD operations
- **PnL Tracking**: Comprehensive profit/loss tracking and reporting
- **Notifications**: Multi-channel notifications (Telegram, Email, In-App) with granular preferences

### 🔐 Security
- **JWT Authentication:** Secure token-based auth with refresh tokens
- **Email verification:** Required for signup and email changes (configure SMTP)
- **Self-service auth:** Signup, forgot/reset password, profile updates
- **Encrypted Credentials:** Broker, Razorpay, and Telegram credentials encrypted in database
- **Role-Based Access:** Admin and User roles; market analysis run-once is admin-only
- **Password Hashing:** Secure pbkdf2_sha256 password hashing
- **Billing:** Performance-fee invoicing with offline UPI or optional Razorpay checkout

## 🚀 Quick Start

### Option 1: Docker — Pull Images (Recommended for New Deployments)

No git clone or build step required.

```bash
# Create a working directory
mkdir rebound && cd rebound

# Download Compose files
# Linux/macOS:
curl -O https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/docker/docker-compose.yml
curl -O https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/docker/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/PawanKGupta/modular_trade_agent/main/.env.example
cp .env.example .env
# Edit .env — set JWT_SECRET, APP_DATA_ENCRYPTION_KEY, POSTGRES_PASSWORD, ADMIN_EMAIL, ADMIN_PASSWORD

# Pull images and start
export APP_VERSION=v26.2.3.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Access:**
- Web UI: http://localhost:5173
- API: http://localhost:8000
- Health: http://localhost:8000/health

See [docs/deployment/DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md) for platform-specific guides (Windows, Linux, macOS, Oracle Cloud).

### Option 2: Manual Setup (Development)

For local development with hot-reload. Requires Python 3.12+ and Node.js 20+.

```bash
# 1. Create and activate virtualenv
python -m venv .venv
# Windows: .venv\Scripts\activate  |  Linux/macOS: source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r server/requirements.txt
cd web && npm install && cd ..

# 3. Configure environment — copy and edit the example
cp .env.example .env
# Minimum required variables:
#   ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME
#   JWT_SECRET   (generate: python -c "import secrets; print(secrets.token_hex(32))")
#   APP_DATA_ENCRYPTION_KEY  (generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 4. Run Alembic migrations
alembic upgrade head

# 5. Start services (two terminals)
uvicorn server.app.main:app --reload --port 8000   # Terminal 1
cd web && npm run dev                               # Terminal 2
```

Go to http://localhost:5173, log in with your admin credentials, then configure broker and notification settings under **Settings**.

See [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md) for the complete walkthrough.

## 📚 Documentation

### Getting Started
- **[Getting Started Guide](docs/guides/GETTING_STARTED.md)** - Complete setup walkthrough
- **[Docker Guide](docker/README.md)** - Docker deployment guide
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System architecture and design

### User Guides
- **[User Guide](docs/guides/USER_GUIDE.md)** - Complete guide to using the web interface
- **[UI Guide](docs/guides/UI_GUIDE.md)** - Complete page-by-page UI documentation
- **[Trading Configuration](docs/guides/TRADING_CONFIG.md)** - Detailed trading parameters guide
- **[Features Documentation](docs/guides/FEATURES.md)** - Complete features reference
- **[Paper Trading](docs/guides/FEATURES.md#5-paper-trading)** - Paper trading features (see Features Documentation)

### Developer Guides
- **[API Documentation](docs/API.md)** - Complete REST API reference
- **[Architecture](docs/ARCHITECTURE.md)** - System architecture and design
- **[Deployment Guide](docs/deployment/DEPLOYMENT.md)** - Production deployment
- **[Migration Guide (Phase 4)](docs/development/MIGRATION_GUIDE_PHASE4.md)** - Migrating from `core.*` to service layer
- **[Engineering Standards](docs/engineering-standards-and-ci.md)** - Code standards and CI

### Advanced Documentation
- **[ML Integration Guide](docs/architecture/ML_COMPLETE_GUIDE.md)** - Complete ML training and integration guide
- **[Order Management Guide](docs/guides/ORDER_MANAGEMENT_COMPLETE.md)** - Complete order management documentation
- **[Service Architecture](docs/architecture/SERVICE_ARCHITECTURE.md)** - Service layer architecture details
- **[Kotak Neo Trader Guide](docs/kotak_neo_trader/README.md)** - Broker integration and AMO executor
- **[Individual Service Management](docs/features/INDIVIDUAL_SERVICE_MANAGEMENT_USER_GUIDE.md)** - Running individual trading tasks
- **[Paper Trading Guide](docs/guides/PAPER_TRADING_COMPLETE.md)** - Complete paper trading system guide
- **[Edge Cases](docs/troubleshooting/EDGE_CASES.md)** - Known edge cases and resolutions
- **[Known Issues](docs/troubleshooting/KNOWN_ISSUES.md)** - Current known issues and workarounds
- **[Backtesting Guide](docs/backtest/README.md)** - Backtesting framework documentation

## 🏛️ Project Structure

```
modular_trade_agent/
├── server/                 # FastAPI backend
│   ├── app/
│   │   ├── routers/       # API route handlers
│   │   ├── schemas/       # Pydantic models
│   │   └── core/          # Core utilities (auth, config)
│   └── requirements.txt
├── web/                   # React frontend
│   ├── src/
│   │   ├── routes/        # Page components
│   │   ├── api/           # API client
│   │   └── components/    # Reusable components
│   └── package.json
├── src/                   # Core business logic
│   ├── application/       # Application services
│   ├── domain/            # Domain entities
│   └── infrastructure/    # Infrastructure adapters
├── modules/               # Trading modules
│   └── kotak_neo_auto_trader/  # Broker integration
├── services/             # Service layer (Phase 4: analysis, ML, etc.)
│                         # Primary implementation - use instead of core.*
├── docker/                # Docker configuration
├── tests/                 # Test suite
└── docs/                  # Documentation (consolidated)
    ├── guides/            # User guides
    ├── architecture/      # Architecture docs
    ├── features/          # Feature docs
    ├── deployment/        # Deployment guides
    ├── kotak_neo_trader/  # Broker integration
    ├── reference/         # Reference docs
    ├── testing/           # Testing docs
    └── internal/          # Internal/implementation docs
```

## 🔌 API Endpoints

All API endpoints use the `/api/v1` prefix. Here are the main endpoints:

### Authentication
- `POST /api/v1/auth/signup` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user

### Trading
- `GET /api/v1/signals/buying-zone` - Get buying zone signals
- `GET /api/v1/user/orders/` - List orders (paginated)
- `GET /api/v1/user/targets` - Get targets
- `GET /api/v1/user/pnl` - Get P&L data
- `POST /api/v1/user/paper-trading/execute` - Execute paper trade

### Configuration
- `GET /api/v1/user/trading-config` - Get trading configuration
- `PUT /api/v1/user/trading-config` - Update trading configuration
- `GET /api/v1/user/broker/credentials` - Get broker credentials
- `PUT /api/v1/user/broker/credentials` - Update broker credentials

### Admin
- `GET /api/v1/admin/users` - List users (admin only)
- `GET /api/v1/admin/ml/training` - ML training status
- `POST /api/v1/admin/ml/train` - Start ML training

See [docs/API.md](docs/API.md) for complete API documentation.

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database operations
- **Pydantic** - Data validation
- **JWT** - Authentication tokens
- **Alembic** - Database migrations

### Frontend
- **React 19** - UI framework
- **TypeScript** - Type safety
- **TanStack Query** - Data fetching and caching
- **React Router** - Routing
- **Vite** - Build tool

### Infrastructure
- **Docker** - Containerization
- **ghcr.io** - Pre-built images published on every release tag
- **SQLite** - Development database
- **PostgreSQL** - Production database (required for multi-user / persistent OHLCV cache)
- **Nginx** - Reverse proxy (production)

## 📋 Requirements

- Python 3.12+
- Node.js 20+
- Docker (for image-based deployment — recommended)
- PostgreSQL (required for production; SQLite for local dev only)


## 📝 License

This project is for educational and personal use only.

## ⚠️ Disclaimer

This software is for educational purposes only. It is not financial advice. Trading involves risk, and you should consult with a qualified financial advisor before making investment decisions. The authors are not responsible for any financial losses incurred through the use of this software.

## 📞 Support

For questions or issues:
1. Check the [documentation](docs/)
2. Review log files for error details
3. Create an issue with detailed error information
