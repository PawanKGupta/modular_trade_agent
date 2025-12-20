# Deployment Guide

> **Deployment Index** - This guide serves as an entry point to route you to the appropriate deployment guide based on your platform and requirements.

## 🎯 Recommended: Docker Deployment

**Docker is the recommended deployment method** for all platforms. It provides:
- ✅ Platform independence (Windows, Linux, macOS, Cloud)
- ✅ Simplified setup (one command)
- ✅ Consistent environment across platforms
- ✅ Easy updates and maintenance
- ✅ Better isolation and security

## 📚 Choose Your Deployment Guide

### Platform-Specific Guides (Recommended)

Select your operating system for complete Docker deployment instructions:

- **[Windows Deployment Guide](platforms/windows.md)** ⭐ - Windows 10/11 deployment
  - Docker Desktop installation
  - WSL2 configuration
  - Complete Docker deployment steps
  - Windows-specific troubleshooting

- **[Linux Deployment Guide](platforms/linux.md)** ⭐ - Linux (Ubuntu, Debian, CentOS) deployment
  - Docker Engine installation
  - Complete Docker deployment steps
  - Linux-specific troubleshooting

- **[macOS Deployment Guide](platforms/macos.md)** ⭐ - macOS deployment
  - Docker Desktop installation
  - Apple Silicon support
  - Complete Docker deployment steps
  - macOS-specific troubleshooting

### Cloud Provider Guides

For cloud provider specific deployment instructions:

- **[Oracle Cloud](cloud/oracle-cloud.md)** - Oracle Cloud Infrastructure (OCI) deployment
  - VM creation and configuration
  - Firewall setup
  - Complete Docker deployment on Oracle Cloud

### Supporting Guides

- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common troubleshooting issues and solutions
- **[Backup & Restore Guide](BACKUP_RESTORE_UNINSTALL_GUIDE.md)** - Database backup and restore procedures
- **[Health Check Guide](HEALTH_CHECK.md)** - Monitoring and health check procedures

## 🚀 Quick Start

### Windows
```powershell
.\docker\docker-quickstart.ps1
```

### Linux/Mac
```bash
./docker/docker-quickstart.sh
```

**Access:**
- Web UI: http://localhost:5173
- API: http://localhost:8000
- Health: http://localhost:8000/health

## 📋 Deployment Checklist

- [ ] Docker installed (version 20.10+)
- [ ] Docker Compose installed (version 1.29.2+)
- [ ] Repository cloned with Git LFS
- [ ] `.env` file configured
- [ ] Services started and running
- [ ] Web UI accessible
- [ ] Admin user created
- [ ] Broker credentials configured via Web UI
- [ ] Trading services started via Web UI
- [ ] Health check passing

## 🔗 Related Documentation

- [Docker README](../../docker/README.md) - Docker-specific documentation
- [Getting Started Guide](../guides/GETTING_STARTED.md) - Initial setup guide
- [User Guide](../guides/USER_GUIDE.md) - End-user documentation
- [API Documentation](../API.md) - API reference

## 💡 Need Help?

- Check [Troubleshooting Guide](TROUBLESHOOTING.md) - Comprehensive troubleshooting for all platforms
- See platform-specific guides above for complete deployment instructions
- See cloud provider guides for cloud-specific deployment
