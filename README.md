# Modular Trade Agent

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
  - **Service Layer Architecture** (Phase 4): Modular, testable services
  - **Async Batch Processing**: 80% faster batch analysis (25min → 5min for 50 stocks)
  - **Caching**: 70-90% reduction in API calls
- **Order Management**: Automated buy/sell order placement via Kotak Neo API
- **Paper Trading**: Risk-free strategy testing with realistic simulation
- **ML Training**: Automated model training and retraining
- **Service Management**: Scheduled tasks for pre-market, monitoring, and EOD operations
- **PnL Tracking**: Comprehensive profit/loss tracking and reporting

### 🔐 Security
- **JWT Authentication**: Secure token-based auth with refresh tokens
- **Encrypted Credentials**: Broker and Telegram credentials encrypted in database
- **Role-Based Access**: Admin and User roles with appropriate permissions
- **Password Hashing**: Secure pbkdf2_sha256 password hashing

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Windows
.\docker\docker-quickstart.ps1

# Linux/Mac
./docker/docker-quickstart.sh
```

**Access:**
- Web UI: http://localhost:5173
- API: http://localhost:8000
- Health: http://localhost:8000/health

See [docker/README.md](docker/README.md) for detailed Docker setup.

### Manual Setup

1. **Install Dependencies**
   ```bash
   # Backend
   pip install -r requirements.txt
   pip install -r server/requirements.txt

   # Frontend
   cd web
   npm install
   ```

2. **Configure Environment**
   ```bash
   # Create .env file in project root
   DB_URL=sqlite:///./data/app.db
   ADMIN_EMAIL=admin@example.com
   ADMIN_PASSWORD=change_me
   ADMIN_NAME=Admin User
   JWT_SECRET=your-secret-key
   ENCRYPTION_KEY=your-encryption-key
   ```

3. **Initialize Database**
   ```bash
   # Run migrations (if using Alembic)
   alembic upgrade head

   # Or let the app auto-create tables on first run
   ```

4. **Start Services**
   ```bash
   # Backend (from project root)
   uvicorn server.app.main:app --reload --port 8000

   # Frontend (from web/)
   cd web
   npm run dev
   ```

5. **Configure Credentials**
   - Access web UI: http://localhost:5173
   - Login with admin credentials
   - Go to Settings → Configure broker and Telegram credentials

## 📚 Documentation

### Getting Started
- **[Getting Started Guide](docs/GETTING_STARTED.md)** - Complete setup walkthrough
- **[Docker Guide](docker/README.md)** - Docker deployment guide
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System architecture and design

### User Guides
- **[User Guide](docs/USER_GUIDE.md)** - Complete guide to using the web interface
- **[UI Guide](docs/UI_GUIDE.md)** - Complete page-by-page UI documentation
- **[Trading Configuration](docs/TRADING_CONFIG.md)** - Detailed trading parameters guide
- **[Features Documentation](docs/FEATURES.md)** - Complete features reference
- **[Paper Trading](../documents/paper_trading/README.md)** - Paper trading system guide

### Developer Guides
- **[API Documentation](docs/API.md)** - Complete REST API reference
- **[Architecture](docs/ARCHITECTURE.md)** - System architecture and design
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment
- **[Migration Guide (Phase 4)](docs/MIGRATION_GUIDE_PHASE4.md)** - Migrating from `core.*` to service layer
- **[Engineering Standards](docs/engineering-standards-and-ci.md)** - Code standards and CI

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
└── docs/                  # Documentation
```

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/signup` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Refresh access token
- `GET /api/auth/me` - Get current user

### Trading
- `GET /api/signals/buying-zone` - Get buying zone signals
- `GET /api/orders` - Get orders
- `GET /api/targets` - Get targets
- `GET /api/pnl` - Get P&L data
- `POST /api/paper-trading/execute` - Execute paper trade

### Configuration
- `GET /api/trading-config` - Get trading configuration
- `PUT /api/trading-config` - Update trading configuration
- `GET /api/broker/credentials` - Get broker credentials
- `PUT /api/broker/credentials` - Update broker credentials

### Admin
- `GET /api/admin/users` - List users (admin only)
- `GET /api/admin/ml/training` - ML training status
- `POST /api/admin/ml/train` - Start ML training

See [docs/API.md](docs/API.md) for complete API documentation.

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database operations
- **Pydantic** - Data validation
- **JWT** - Authentication tokens
- **Alembic** - Database migrations

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **TanStack Query** - Data fetching and caching
- **React Router** - Routing
- **Vite** - Build tool

### Infrastructure
- **Docker** - Containerization
- **SQLite** - Development database
- **PostgreSQL** - Production database (optional)
- **Nginx** - Reverse proxy (production)

## 📋 Requirements

- Python 3.12+
- Node.js 18+
- Docker (optional, for containerized deployment)
- PostgreSQL (optional, for production)

## 🔒 Security

- All passwords are hashed using pbkdf2_sha256
- Broker credentials are encrypted using Fernet (AES-128)
- JWT tokens with configurable expiration
- CORS protection
- SQL injection protection via SQLAlchemy

## 📝 License

This project is for educational and personal use only.

## ⚠️ Disclaimer

This software is for educational purposes only. It is not financial advice. Trading involves risk, and you should consult with a qualified financial advisor before making investment decisions. The authors are not responsible for any financial losses incurred through the use of this software.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For questions or issues:
1. Check the [documentation](docs/)
2. Review log files for error details
3. Create an issue with detailed error information
