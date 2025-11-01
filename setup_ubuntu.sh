#!/bin/bash

################################################################################
# Modular Trade Agent - Ubuntu Setup Script
# 
# This script sets up all 5 systemd services for automated trading:
# 1. Trade Analysis Service (4:00 PM) - Generate signals
# 2. Auto Trade Service (9:00 AM & 4:05 PM) - Place orders
# 3. Position Monitor Service (Every 1 min) - Monitor positions
# 4. Sell Orders Service (9:15 AM) - Manage sell orders
# 5. EOD Cleanup Service (3:35 PM) - Daily reconciliation
#
# Usage: sudo ./setup_ubuntu.sh
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
echo -e "${BLUE}    Modular Trade Agent - Ubuntu Setup${NC}"
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

echo -e "${BLUE}[1/7] Checking Python version...${NC}"

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

echo -e "${BLUE}[2/7] Checking virtual environment...${NC}"

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

echo -e "${BLUE}[3/7] Checking dependencies...${NC}"

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

echo -e "${BLUE}[4/7] Checking configuration files...${NC}"

CONFIG_MISSING=false

if [ ! -f "$PROJECT_DIR/cred.env" ] && [ ! -f "$PROJECT_DIR/kotak_neo.env" ]; then
    echo -e "${YELLOW}⚠ Warning: No configuration files found (cred.env or kotak_neo.env)${NC}"
    CONFIG_MISSING=true
fi

if [ -f "$PROJECT_DIR/cred.env" ]; then
    echo -e "${GREEN}✓ Found cred.env${NC}"
fi

if [ -f "$PROJECT_DIR/kotak_neo.env" ]; then
    echo -e "${GREEN}✓ Found kotak_neo.env${NC}"
fi

if [ "$CONFIG_MISSING" = true ]; then
    echo -e "${YELLOW}You'll need to create configuration files before services can run.${NC}"
    echo -e "${YELLOW}See: documents/getting-started/GETTING_STARTED.md${NC}"
fi

echo ""

################################################################################
# Step 5: Create Systemd Service Files
################################################################################

echo -e "${BLUE}[5/7] Creating systemd service files...${NC}"

# Service 1: Trade Analysis
cat > /etc/systemd/system/tradeagent-analysis.service <<EOF
[Unit]
Description=Modular Trade Agent - Analysis Service
After=network.target

[Service]
Type=oneshot
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PYTHON_BIN $PROJECT_DIR/trade_agent.py --backtest
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tradeagent-analysis

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/tradeagent-analysis.timer <<EOF
[Unit]
Description=Modular Trade Agent - Analysis Timer (4:00 PM IST)
Requires=tradeagent-analysis.service

[Timer]
OnCalendar=Mon-Fri *-*-* 16:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Created tradeagent-analysis service${NC}"

# Service 2: Auto Trade
cat > /etc/systemd/system/tradeagent-autotrade.service <<EOF
[Unit]
Description=Modular Trade Agent - Auto Trade Service
After=network.target

[Service]
Type=oneshot
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PYTHON_BIN $PROJECT_DIR/modules/kotak_neo_auto_trader/run_auto_trade.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tradeagent-autotrade

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/tradeagent-autotrade.timer <<EOF
[Unit]
Description=Modular Trade Agent - Auto Trade Timer (9:00 AM & 4:05 PM IST)
Requires=tradeagent-autotrade.service

[Timer]
OnCalendar=Mon-Fri *-*-* 09:00:00
OnCalendar=Mon-Fri *-*-* 16:05:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Created tradeagent-autotrade service${NC}"

# Service 3: Position Monitor
cat > /etc/systemd/system/tradeagent-monitor.service <<EOF
[Unit]
Description=Modular Trade Agent - Position Monitor Service
After=network.target

[Service]
Type=oneshot
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PYTHON_BIN $PROJECT_DIR/modules/kotak_neo_auto_trader/run_position_monitor.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tradeagent-monitor

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/tradeagent-monitor.timer <<EOF
[Unit]
Description=Modular Trade Agent - Position Monitor Timer (Every 1 minute, 9:15 AM - 3:30 PM IST)
Requires=tradeagent-monitor.service

[Timer]
# Start at 9:15 AM on weekdays
OnCalendar=Mon-Fri *-*-* 09:15:00
# Then run every 1 minute
OnUnitActiveSec=1min
# Stop is handled by service itself or manual stop at 3:30 PM
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Create a oneshot service to stop the monitor timer
cat > /etc/systemd/system/tradeagent-monitor-stop.service <<EOF
[Unit]
Description=Stop Position Monitor Timer

[Service]
Type=oneshot
ExecStart=/bin/systemctl stop tradeagent-monitor.timer
EOF

cat > /etc/systemd/system/tradeagent-monitor-stop.timer <<EOF
[Unit]
Description=Stop Position Monitor at 3:30 PM

[Timer]
OnCalendar=Mon-Fri *-*-* 15:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Created tradeagent-monitor service${NC}"

# Service 4: Sell Orders
cat > /etc/systemd/system/tradeagent-sell.service <<EOF
[Unit]
Description=Modular Trade Agent - Sell Orders Service
After=network.target

[Service]
Type=oneshot
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PYTHON_BIN $PROJECT_DIR/modules/kotak_neo_auto_trader/run_sell_orders.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tradeagent-sell

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/tradeagent-sell.timer <<EOF
[Unit]
Description=Modular Trade Agent - Sell Orders Timer (9:15 AM IST)
Requires=tradeagent-sell.service

[Timer]
OnCalendar=Mon-Fri *-*-* 09:15:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Created tradeagent-sell service${NC}"

# Service 5: EOD Cleanup
cat > /etc/systemd/system/tradeagent-eod.service <<EOF
[Unit]
Description=Modular Trade Agent - EOD Cleanup Service
After=network.target

[Service]
Type=oneshot
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PYTHON_BIN $PROJECT_DIR/modules/kotak_neo_auto_trader/run_eod_cleanup.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tradeagent-eod

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/tradeagent-eod.timer <<EOF
[Unit]
Description=Modular Trade Agent - EOD Cleanup Timer (3:35 PM IST)
Requires=tradeagent-eod.service

[Timer]
OnCalendar=Mon-Fri *-*-* 15:35:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Created tradeagent-eod service${NC}"
echo ""

################################################################################
# Step 6: Enable and Start Services
################################################################################

echo -e "${BLUE}[6/7] Enabling and starting services...${NC}"

# Reload systemd daemon
systemctl daemon-reload

# Enable all timers
systemctl enable tradeagent-analysis.timer
systemctl enable tradeagent-autotrade.timer
systemctl enable tradeagent-monitor.timer
systemctl enable tradeagent-monitor-stop.timer
systemctl enable tradeagent-sell.timer
systemctl enable tradeagent-eod.timer

# Start all timers
systemctl start tradeagent-analysis.timer
systemctl start tradeagent-autotrade.timer
systemctl start tradeagent-monitor.timer
systemctl start tradeagent-monitor-stop.timer
systemctl start tradeagent-sell.timer
systemctl start tradeagent-eod.timer

echo -e "${GREEN}✓ All services enabled and started${NC}"
echo ""

################################################################################
# Step 7: Verify Installation
################################################################################

echo -e "${BLUE}[7/7] Verifying installation...${NC}"
echo ""

echo -e "${BLUE}Service Status:${NC}"
systemctl list-timers tradeagent-* --no-pager

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Installation Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}📋 Services Installed:${NC}"
echo -e "  1. ${GREEN}tradeagent-analysis${NC} - Generate signals (4:00 PM)"
echo -e "  2. ${GREEN}tradeagent-autotrade${NC} - Place orders (9:00 AM & 4:05 PM)"
echo -e "  3. ${GREEN}tradeagent-monitor${NC} - Monitor positions (Every 1 min)"
echo -e "  4. ${GREEN}tradeagent-sell${NC} - Manage sells (9:15 AM)"
echo -e "  5. ${GREEN}tradeagent-eod${NC} - Daily cleanup (3:35 PM)"
echo ""

echo -e "${BLUE}📅 Daily Schedule:${NC}"
echo -e "  09:00 AM - Auto Trade (Retry failed orders)"
echo -e "  09:15 AM - Sell Orders + Position Monitor starts"
echo -e "  09:15-15:30 - Monitor runs every 1 minute"
echo -e "  15:35 PM - EOD Cleanup"
echo -e "  16:00 PM - Analysis (Generate signals)"
echo -e "  16:05 PM - Auto Trade (Place new orders)"
echo ""

echo -e "${BLUE}🔧 Management Commands:${NC}"
echo -e "  View all timers:  systemctl list-timers tradeagent-*"
echo -e "  View logs:        journalctl -u tradeagent-analysis.service -f"
echo -e "  Stop all:         sudo systemctl stop tradeagent-*.timer"
echo -e "  Manual run:       sudo systemctl start tradeagent-analysis.service"
echo ""

if [ "$CONFIG_MISSING" = true ]; then
    echo -e "${YELLOW}⚠ IMPORTANT: Configuration Required${NC}"
    echo -e "${YELLOW}Services won't run without configuration files:${NC}"
    echo -e "  - cred.env (for Telegram alerts)"
    echo -e "  - kotak_neo.env (for automated trading)"
    echo ""
    echo -e "${YELLOW}See: documents/getting-started/GETTING_STARTED.md${NC}"
    echo ""
fi

echo -e "${BLUE}📚 Documentation:${NC}"
echo -e "  Setup Guide:      documents/getting-started/PYTHON_SETUP.md"
echo -e "  Service Details:  documents/deployment/ubuntu/SERVICES_COMPARISON.md"
echo -e "  Quickstart:       documents/deployment/ubuntu/UBUNTU_QUICKSTART.md"
echo ""

echo -e "${GREEN}Happy Trading! 📈${NC}"
