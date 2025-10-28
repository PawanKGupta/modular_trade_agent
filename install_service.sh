#!/bin/bash
################################################################################
# Install Trade Agent as systemd Service
# Sets up automatic execution at specified times
################################################################################

set -e

echo "========================================================================"
echo "Installing Modular Trade Agent as systemd Service"
echo "========================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Get installation directory
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXECUTABLE="${INSTALL_DIR}/ModularTradeAgent"

# Check if executable exists
if [ ! -f "$EXECUTABLE" ]; then
    echo -e "${RED}❌ Executable not found: $EXECUTABLE${NC}"
    exit 1
fi

# Get current user (the one who invoked sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
ACTUAL_GROUP=$(id -gn $ACTUAL_USER)

echo "Installation directory: $INSTALL_DIR"
echo "Running as user: $ACTUAL_USER:$ACTUAL_GROUP"
echo ""

# Create systemd service file
echo "Creating systemd service file..."
cat > /etc/systemd/system/tradeagent.service << EOF
[Unit]
Description=Modular Trade Agent - Automated Trading System
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$EXECUTABLE
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true

# Resource limits
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Service file created${NC}"

# Create timer for scheduled execution (4:00 PM buy, 9:15 AM sell)
echo ""
echo "Creating systemd timers for scheduled execution..."

# Buy timer (4:00 PM IST on weekdays)
cat > /etc/systemd/system/tradeagent-buy.timer << EOF
[Unit]
Description=Trade Agent Buy Orders Timer
Requires=tradeagent-buy.service

[Timer]
OnCalendar=Mon-Fri 16:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

# Buy service
cat > /etc/systemd/system/tradeagent-buy.service << EOF
[Unit]
Description=Trade Agent Buy Orders Execution
After=network-online.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$EXECUTABLE --mode buy
StandardOutput=journal
StandardError=journal
EOF

# Sell timer (9:15 AM IST on weekdays)
cat > /etc/systemd/system/tradeagent-sell.timer << EOF
[Unit]
Description=Trade Agent Sell Orders Timer
Requires=tradeagent-sell.service

[Timer]
OnCalendar=Mon-Fri 09:15:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

# Sell service
cat > /etc/systemd/system/tradeagent-sell.service << EOF
[Unit]
Description=Trade Agent Sell Orders Execution
After=network-online.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$EXECUTABLE --mode sell
StandardOutput=journal
StandardError=journal
EOF

echo -e "${GREEN}✓ Timer files created${NC}"

# Reload systemd
echo ""
echo "Reloading systemd daemon..."
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"

# Enable and start timers
echo ""
echo "Enabling and starting timers..."
systemctl enable tradeagent-buy.timer
systemctl enable tradeagent-sell.timer
systemctl start tradeagent-buy.timer
systemctl start tradeagent-sell.timer
echo -e "${GREEN}✓ Timers enabled and started${NC}"

# Show status
echo ""
echo "========================================================================"
echo -e "${GREEN}✅ INSTALLATION COMPLETE${NC}"
echo "========================================================================"
echo ""
echo "Service Details:"
echo "  - Buy orders: Daily at 4:00 PM IST (Mon-Fri)"
echo "  - Sell orders: Daily at 9:15 AM IST (Mon-Fri)"
echo "  - Running as: $ACTUAL_USER:$ACTUAL_GROUP"
echo "  - Working directory: $INSTALL_DIR"
echo ""
echo "Management Commands:"
echo "  View buy timer:   systemctl status tradeagent-buy.timer"
echo "  View sell timer:  systemctl status tradeagent-sell.timer"
echo "  View logs:        journalctl -u tradeagent-buy.service -f"
echo "  View logs:        journalctl -u tradeagent-sell.service -f"
echo "  Manual run (buy): systemctl start tradeagent-buy.service"
echo "  Manual run (sell): systemctl start tradeagent-sell.service"
echo "  Stop timers:      systemctl stop tradeagent-*.timer"
echo "  Uninstall:        sudo ./uninstall_service.sh"
echo ""
echo "Next timer executions:"
systemctl list-timers tradeagent-* --no-pager
echo ""
