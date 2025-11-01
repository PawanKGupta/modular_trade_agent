#!/bin/bash

################################################################################
# Modular Trade Agent - Ubuntu Unified Service Setup
# 
# This script sets up a single unified trading service that handles:
# - Signal generation (4:00 PM)
# - Auto trade (9:00 AM & 4:05 PM)
# - Position monitoring (continuous during market hours)
# - Sell orders (9:15 AM)
# - EOD cleanup (3:35 PM)
#
# Benefits:
# - Single persistent client session (no JWT expiry)
# - Better resource management
# - Simplified service management
#
# Usage: sudo ./setup_ubuntu_unified.sh
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}    Modular Trade Agent - Unified Service Setup${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}✗ Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo "~$ACTUAL_USER")

echo -e "${GREEN}✓ Running as root${NC}"
echo -e "${GREEN}✓ Target user: $ACTUAL_USER${NC}"
echo -e "${GREEN}✓ Project directory: $PROJECT_DIR${NC}"
echo ""

################################################################################
# Step 1: Check Python Version
################################################################################

echo -e "${BLUE}[1/6] Checking Python version...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    echo -e "${YELLOW}Installing Python 3.12...${NC}"
    apt-get update
    apt-get install -y python3.12 python3.12-venv python3-pip
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 12 ]); then
    echo -e "${RED}✗ Python 3.12+ is required (found $PYTHON_VERSION)${NC}"
    echo -e "${YELLOW}Please install Python 3.12+ first${NC}"
    echo -e "${YELLOW}See: documents/getting-started/PYTHON_SETUP.md${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python version: $PYTHON_VERSION${NC}"
echo ""

################################################################################
# Step 2: Check Virtual Environment
################################################################################

echo -e "${BLUE}[2/6] Checking virtual environment...${NC}"

if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    cd "$PROJECT_DIR"
    sudo -u "$ACTUAL_USER" python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
PIP_BIN="$PROJECT_DIR/.venv/bin/pip"

echo ""

################################################################################
# Step 3: Check Dependencies
################################################################################

echo -e "${BLUE}[3/6] Checking dependencies...${NC}"

if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    echo -e "${RED}✗ requirements.txt not found${NC}"
    exit 1
fi

echo -e "${YELLOW}Checking installed packages...${NC}"

# Check if key packages are installed
if ! sudo -u "$ACTUAL_USER" "$PIP_BIN" show pandas &> /dev/null; then
    echo -e "${YELLOW}Dependencies not installed. Installing...${NC}"
    echo -e "${YELLOW}This may take several minutes...${NC}"
    sudo -u "$ACTUAL_USER" "$PIP_BIN" install -r "$PROJECT_DIR/requirements.txt"
    sudo -u "$ACTUAL_USER" "$PIP_BIN" install -r "$PROJECT_DIR/requirements-dev.txt"
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi

echo ""

################################################################################
# Step 4: Check Configuration Files
################################################################################

echo -e "${BLUE}[4/6] Checking configuration files...${NC}"

CONFIG_MISSING=false

if [ ! -f "$PROJECT_DIR/kotak_neo.env" ]; then
    echo -e "${YELLOW}⚠ Warning: kotak_neo.env not found${NC}"
    CONFIG_MISSING=true
else
    echo -e "${GREEN}✓ Found kotak_neo.env${NC}"
fi

if [ "$CONFIG_MISSING" = true ]; then
    echo -e "${YELLOW}Unified service requires kotak_neo.env for automated trading.${NC}"
    echo -e "${YELLOW}See: documents/getting-started/GETTING_STARTED.md${NC}"
fi

echo ""

################################################################################
# Step 5: Create Unified Service
################################################################################

echo -e "${BLUE}[5/6] Creating unified trading service...${NC}"

cat > /etc/systemd/system/tradeagent-unified.service <<EOF
[Unit]
Description=Modular Trade Agent - Unified Trading Service
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PYTHON_BIN $PROJECT_DIR/modules/kotak_neo_auto_trader/run_trading_service.py
Restart=on-failure
RestartSec=60
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tradeagent-unified

# Resource limits
LimitNOFILE=65536
Nice=-5

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Created tradeagent-unified service${NC}"
echo ""

################################################################################
# Step 6: Enable and Start Service
################################################################################

echo -e "${BLUE}[6/6] Enabling and starting service...${NC}"

# Reload systemd daemon
systemctl daemon-reload

# Enable service
systemctl enable tradeagent-unified.service

# Start service
systemctl start tradeagent-unified.service

echo -e "${GREEN}✓ Unified service enabled and started${NC}"
echo ""

################################################################################
# Verify Installation
################################################################################

echo -e "${BLUE}Verifying installation...${NC}"
echo ""

echo -e "${BLUE}Service Status:${NC}"
systemctl status tradeagent-unified.service --no-pager -l

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Unified Service Installation Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}📋 Service Installed:${NC}"
echo -e "  ${GREEN}tradeagent-unified${NC} - Handles all trading tasks"
echo ""

echo -e "${BLUE}📅 What it does:${NC}"
echo -e "  - Maintains single persistent session all day"
echo -e "  - 09:00 AM - Retry failed orders"
echo -e "  - 09:15 AM - Place sell orders"
echo -e "  - 09:15-15:30 - Monitor positions continuously"
echo -e "  - 15:35 PM - EOD cleanup"
echo -e "  - 16:00 PM - Generate signals (via separate analysis service)"
echo -e "  - 16:05 PM - Place new AMO orders"
echo ""

echo -e "${BLUE}🔧 Management Commands:${NC}"
echo -e "  View status:      systemctl status tradeagent-unified.service"
echo -e "  View logs:        journalctl -u tradeagent-unified.service -f"
echo -e "  Stop service:     sudo systemctl stop tradeagent-unified.service"
echo -e "  Start service:    sudo systemctl start tradeagent-unified.service"
echo -e "  Restart service:  sudo systemctl restart tradeagent-unified.service"
echo ""

if [ "$CONFIG_MISSING" = true ]; then
    echo -e "${YELLOW}⚠ IMPORTANT: Configuration Required${NC}"
    echo -e "${YELLOW}Service won't run without kotak_neo.env${NC}"
    echo -e "  - Create kotak_neo.env with Kotak Neo credentials"
    echo -e "  - Add Telegram credentials for alerts"
    echo ""
    echo -e "${YELLOW}See: documents/getting-started/GETTING_STARTED.md${NC}"
    echo ""
fi

echo -e "${BLUE}📚 Documentation:${NC}"
echo -e "  Setup Guide:      documents/getting-started/PYTHON_SETUP.md"
echo -e "  Service Details:  documents/architecture/UNIFIED_TRADING_SERVICE.md"
echo ""

echo -e "${YELLOW}Note: Signal analysis (4:00 PM) should be set up separately${NC}"
echo -e "${YELLOW}Run: sudo ./setup_ubuntu.sh and choose analysis service only${NC}"
echo ""

echo -e "${GREEN}Happy Trading! 📈${NC}"
