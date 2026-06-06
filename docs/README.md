# Documentation Index

Complete documentation for Rebound — Modular Trade Agent.

## 📚 Getting Started

- **[Getting Started Guide](guides/GETTING_STARTED.md)** - Complete setup walkthrough for new users
- **[Docker Guide](../docker/README.md)** - Docker deployment (recommended for beginners)

## 🏗️ Architecture & Development

- **[Architecture Overview](ARCHITECTURE.md)** - System architecture, components, and design patterns
- **[API Documentation](API.md)** - Complete REST API reference
- **[Deployment Guide](deployment/DEPLOYMENT.md)** - Production deployment instructions
- **[Engineering Standards](engineering-standards-and-ci.md)** - Development standards and CI

### Advanced Documentation

- **[ML Integration Guide](architecture/ML_COMPLETE_GUIDE.md)** - Complete ML training and integration guide
- **[Order Management Guide](guides/ORDER_MANAGEMENT_COMPLETE.md)** - Complete order management documentation
- **[Service Architecture](architecture/SERVICE_ARCHITECTURE.md)** - Service layer architecture details
- **[Kotak Neo Trader Guide](kotak_neo_trader/README.md)** - Broker integration and AMO executor
- **[Paper Trading Guide](guides/PAPER_TRADING_COMPLETE.md)** - Complete paper trading system guide
- **[ML Monitoring Mode](guides/ML_MONITORING_MODE_GUIDE.md)** - ML monitoring mode usage guide

### Troubleshooting & Support

- **[Edge Cases](troubleshooting/EDGE_CASES.md)** - Known edge cases and resolutions
- **[Known Issues](troubleshooting/KNOWN_ISSUES.md)** - Current known issues and workarounds

## 👤 User Guides

- **[User Guide](guides/USER_GUIDE.md)** - Complete guide to using the web interface
- **[UI Guide](guides/UI_GUIDE.md)** - Complete page-by-page UI documentation
- **[Trading Configuration](guides/TRADING_CONFIG.md)** - Detailed trading parameters guide
- **[Features Documentation](guides/FEATURES.md)** - Complete features reference
- **[Paper Trading Guide](guides/PAPER_TRADING_COMPLETE.md)** - Complete paper trading system guide

### Feature-Specific Guides

- **[Service Status & Trading Config UI](features/SERVICE_STATUS_AND_TRADING_CONFIG_UI.md)** - Service management and trading configuration UI guide
- **[Individual Service Management](features/INDIVIDUAL_SERVICE_MANAGEMENT_USER_GUIDE.md)** - Running individual trading tasks
- **[Chart Quality Guide](features/CHART_QUALITY_USAGE_GUIDE.md)** - Chart quality filtering and capital adjustment
- **[Verdict and Scoring Reference](features/VERDICT_AND_SCORING.md)** - `VerdictService` and `ScoringService` behavior (verdict rules, strength/priority/combined scores)
- **[Backtesting Guide](backtest/README.md)** - Backtesting framework documentation

## 📋 Quick Reference

### Quick Start
1. **Docker (Recommended):**
   - Windows: `.\docker\docker-quickstart.ps1`
   - Linux/Mac: `./docker/docker-quickstart.sh`
   - Access: http://localhost:5173

2. **Manual Setup:**
   - See [Getting Started Guide](guides/GETTING_STARTED.md) for detailed instructions

### Key Features
- **Trading:** Mean reversion to EMA9 strategy with automated execution
- **Multi-User:** User-scoped data isolation and configuration
- **Paper Trading:** Risk-free strategy testing
- **ML-Enhanced:** Machine learning predictions for signal quality
- **Notifications:** Multi-channel (Telegram, Email, In-App) with granular preferences
- **Web-Based:** Modern React UI with real-time updates

### Technology Stack
- **Frontend:** React 18 + TypeScript + Vite
- **Backend:** FastAPI + Python 3.12+
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **Deployment:** Docker (recommended)

## 📁 Documentation Structure

```
docs/
├── README.md                    # This file - Documentation index
├── guides/                      # User guides
│   ├── GETTING_STARTED.md
│   ├── USER_GUIDE.md
│   ├── UI_GUIDE.md
│   ├── TRADING_CONFIG.md
│   └── FEATURES.md
├── architecture/                # Architecture documentation
│   ├── ARCHITECTURE.md
│   ├── SERVICE_ARCHITECTURE.md
│   └── ML_COMPLETE_GUIDE.md
├── features/                    # Feature documentation
│   └── [feature guides]
├── deployment/                  # Deployment guides
│   ├── DEPLOYMENT.md            # ⭐ Deployment index (entry point)
│   ├── BACKUP_RESTORE_UNINSTALL_GUIDE.md
│   ├── HEALTH_CHECK.md
│   ├── platforms/               # Platform-specific guides (OS)
│   │   ├── windows.md
│   │   ├── linux.md
│   │   └── macos.md
│   └── cloud/                    # Cloud provider guides
│       └── oracle-cloud.md
├── kotak_neo_trader/           # Broker integration docs
│   └── [broker guides]
├── reference/                   # Reference documentation
│   ├── COMMANDS.md
│   ├── CLI_USAGE.md
│   └── VERSION_MANAGEMENT.md
├── testing/                     # Testing documentation
│   ├── TESTING_RULES.md
│   └── [test guides]
├── security/                    # Security documentation
│   └── TOKEN_SECURITY.md
├── backtest/                    # Backtesting docs
│   └── README.md
├── troubleshooting/             # Troubleshooting & support
│   ├── EDGE_CASES.md
│   └── KNOWN_ISSUES.md
└── development/                 # Development/internal docs
    └── [implementation details, migration guides, test reports]
```

## 📦 Archived Documentation

Historical and outdated documentation has been moved to the `archive/` folder for reference:

- **`archive/documents/`** - Historical documentation (175+ files)
  - Migration documents (completed)
  - Phase completion reports (historical)
  - Old deployment guides (superseded)
  - Bug fix documentation (historical)
  - Implementation plans (completed)

- **`archive/docs/`** - Old documentation structure
- **`archive/old_documentation/`** - Previous documentation versions

**Note:** Archived documentation is kept for historical reference only. For current documentation, use the files in `docs/`. See [`archive/README.md`](../archive/README.md) for details.

## 🆘 Getting Help

1. Check [Getting Started](guides/GETTING_STARTED.md) for setup issues
2. Review [User Guide](guides/USER_GUIDE.md) for feature usage
3. Check [Troubleshooting](troubleshooting/KNOWN_ISSUES.md) for known issues
4. Review [Edge Cases](troubleshooting/EDGE_CASES.md) for edge case resolutions
5. Check [API Documentation](API.md) for programmatic access
6. Review logs in the web UI (Admin → Logs)

## 📝 Documentation Status

**Current Documentation (2025):**
- ✅ Getting Started Guide
- ✅ Architecture Documentation
- ✅ API Documentation
- ✅ User Guide
- ✅ UI Guide (Complete page-by-page documentation)
- ✅ Features Documentation (All features reference)
- ✅ Trading Configuration Guide (Detailed parameters)
- ✅ Deployment Guide
- ✅ Docker Guide
- ✅ Engineering Standards

**Additional Documentation:**
- ✅ Order Management Complete Guide
- ✅ ML Integration Guide
- ✅ Service Architecture Documentation
- ✅ Broker Integration Guide (Kotak Neo)
- ✅ Edge Cases Documentation
- ✅ Individual Service Management Guide
- ✅ Backtesting Framework Guide

**Reference Documentation:**
- See `docs/` folder for all documentation organized by category
- See [`docs/DOCUMENTATION_RULES.md`](DOCUMENTATION_RULES.md) for documentation standards and guidelines
