# Documentation Index

Complete documentation for Rebound — Modular Trade Agent.

## 📚 Getting Started

- **[Getting Started Guide](GETTING_STARTED.md)** - Complete setup walkthrough for new users
- **[Docker Guide](../docker/README.md)** - Docker deployment (recommended for beginners)

## 🏗️ Architecture & Development

- **[Architecture Overview](ARCHITECTURE.md)** - System architecture, components, and design patterns
- **[API Documentation](API.md)** - Complete REST API reference
- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment instructions
- **[Engineering Standards](engineering-standards-and-ci.md)** - Development standards and CI
- **[ML Integration Guide](../documents/architecture/ML_COMPLETE_GUIDE.md)** - Complete ML training and integration guide
- **[Order Management Guide](../documents/ORDER_MANAGEMENT_COMPLETE.md)** - Complete order management documentation

## 👤 User Guides

- **[User Guide](USER_GUIDE.md)** - Complete guide to using the web interface
- **[UI Guide](UI_GUIDE.md)** - Complete page-by-page UI documentation
- **[Trading Configuration](TRADING_CONFIG.md)** - Detailed trading parameters guide
- **[Features Documentation](FEATURES.md)** - Complete features reference
- **[Paper Trading](../documents/paper_trading/PAPER_TRADING_COMPLETE.md)** - Complete paper trading guide

## 📋 Quick Reference

### Setup
1. Read [Getting Started](GETTING_STARTED.md)
2. Use Docker: `.\docker\docker-quickstart.ps1` (Windows) or `./docker/docker-quickstart.sh` (Linux/Mac)
3. Access: http://localhost:5173

### Key Features
- Multi-user trading system
- Mean reversion to EMA9 strategy
- Automated order execution
- Paper trading
- ML-enhanced signals
- Web-based management

### Architecture
- **Frontend:** React + TypeScript
- **Backend:** FastAPI + Python
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **Deployment:** Docker (recommended)

## 🆘 Getting Help

1. Check [Getting Started](GETTING_STARTED.md) for setup issues
2. Review [User Guide](USER_GUIDE.md) for feature usage
3. Check [API Documentation](API.md) for programmatic access
4. Review logs in the web UI (Admin → Logs)

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

**Legacy Documentation:**
- Outdated migration and phase completion docs have been archived
- See `archive/` directory for historical reference
