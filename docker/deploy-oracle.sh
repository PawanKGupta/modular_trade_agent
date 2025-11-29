#!/bin/bash
# Deployment script for Oracle Cloud Ubuntu
# Run this on your Oracle Cloud VM after cloning the repository

set -e

echo "🚀 Deploying Trading Agent to Oracle Cloud..."
echo "=============================================="
echo ""

# Check if running as ubuntu user
if [ "$USER" != "ubuntu" ]; then
    echo "⚠️  Warning: This script is designed for 'ubuntu' user"
    echo "   Current user: $USER"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker installed"
    echo "⚠️  Please log out and log back in, then run this script again"
    exit 0
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed!"
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose installed"
fi

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Project root: $PROJECT_ROOT"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  .env file not found"
    echo "Creating .env from template..."

    # Generate encryption key
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")

    cat > .env <<EOF
# Database
DB_URL=sqlite:///./data/app.db

# Timezone
TZ=Asia/Kolkata

# Encryption key for credential encryption
ENCRYPTION_KEY=$ENCRYPTION_KEY

# Admin User Auto-Creation (only on first deployment when database is empty)
# The API server will automatically create an admin user on startup if:
# 1. Database has zero users
# 2. ADMIN_EMAIL and ADMIN_PASSWORD are set below
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeThisPassword123!
ADMIN_NAME=Admin User
EOF
    echo "✅ Created .env file"
else
    echo "✅ .env file exists"
fi

# Navigate to docker folder
cd docker

echo ""
echo "📦 Building Docker images..."
echo "This may take 10-15 minutes on first run..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

echo ""
echo "🚀 Starting services..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

echo ""
echo "📊 Service Status:"
docker-compose -f docker-compose.yml ps

echo ""
echo "✅ Deployment Complete!"
echo ""
echo "🌐 Access your services:"
echo "  - Web Frontend: http://$(curl -s ifconfig.me):5173"
echo "  - API Server:  http://$(curl -s ifconfig.me):8000"
echo "  - Health Check: http://$(curl -s ifconfig.me):8000/health"
echo ""
echo "📝 Next Steps:"
echo "  1. Configure firewall rules in Oracle Cloud Console"
echo "  2. Access web UI and create admin account"
echo "  3. Configure credentials via Settings page"
echo ""
echo "📚 Useful commands:"
echo "  View logs:        cd docker && docker-compose -f docker-compose.yml logs -f"
echo "  Stop services:    cd docker && docker-compose -f docker-compose.yml down"
echo "  Restart service:  cd docker && docker-compose -f docker-compose.yml restart <service-name>"
echo "  View status:      cd docker && docker-compose -f docker-compose.yml ps"
echo ""
echo "📖 For more help, see docker/README.md"
