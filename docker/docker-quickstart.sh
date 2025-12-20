#!/bin/bash
# Quick Start Script for Docker Setup
# This script helps you get started with Docker quickly
# Run from project root: ./docker/docker-quickstart.sh

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$SCRIPT_DIR"

echo "🐳 Docker Quick Start for Trading Agent"
echo "========================================"
echo ""
echo "Project root: $PROJECT_ROOT"
echo "Docker dir: $DOCKER_DIR"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running!"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is installed and running"
echo ""

# Check for .env file in project root
cd "$PROJECT_ROOT"
if [ ! -f .env ]; then
    echo "⚠️  .env file not found in project root"
    echo "Creating .env from template..."
    cat > .env <<EOF
# Database
DB_URL=sqlite:///./data/app.db

# Timezone
TZ=Asia/Kolkata

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Admin User Auto-Creation (only on first deployment when database is empty)
# The API server will automatically create an admin user on startup if:
# 1. Database has zero users
# 2. ADMIN_EMAIL and ADMIN_PASSWORD are set below
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeThisPassword123!
ADMIN_NAME=Admin User
EOF
    echo "✅ Created .env file (please edit with your settings)"
else
    echo "✅ .env file exists"
fi

# Note: Credentials are now stored in database via web UI
# No need for cred.env or kotak_neo.env files
echo "ℹ️  Credentials are stored in database via web UI"
echo "   Configure them after starting services at http://localhost:5173"
echo ""
echo "ℹ️  Admin user will be auto-created on first startup (if DB is empty)"
echo "   Check .env file for ADMIN_EMAIL and ADMIN_PASSWORD"

echo ""
echo "📦 Building Docker images..."
echo "This may take 5-10 minutes on first run..."
cd "$PROJECT_ROOT"
docker-compose -f docker/docker-compose.yml build

echo ""
echo "🚀 Starting services..."
docker-compose -f docker/docker-compose.yml up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 5

echo ""
echo "📊 Service Status:"
docker-compose -f docker/docker-compose.yml ps

echo ""
echo "✅ Setup Complete!"
echo ""
echo "🌐 Access your services:"
echo "  - Web Frontend: http://localhost:5173"
echo "  - API Server:  http://localhost:8000"
echo "  - Health Check: http://localhost:8000/health"
echo ""
echo "📝 Useful commands (run from project root):"
echo "  View logs:        docker-compose -f docker/docker-compose.yml logs -f"
echo "  Stop services:    docker-compose -f docker/docker-compose.yml down"
echo "  Restart service:  docker-compose -f docker/docker-compose.yml restart <service-name>"
echo "  View status:      docker-compose -f docker/docker-compose.yml ps"
echo ""
echo "📚 For more help, see docker/README.md"
