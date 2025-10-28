#!/bin/bash
################################################################################
# Complete Systemd Services Setup (Aligned with Windows)
# Creates all 5 services matching the Windows installer
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================================================${NC}"
echo -e "${CYAN}Complete Systemd Services Setup (Aligned with Windows)${NC}"
echo -e "${CYAN}========================================================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
    exit 1
fi

INSTALL_DIR="$HOME/modular_trade_agent"
if [ -n "$SUDO_USER" ]; then
    INSTALL_DIR="/home/$SUDO_USER/modular_trade_agent"
    ACTUAL_USER=$SUDO_USER
else
    ACTUAL_USER=$USER
fi

VENV_DIR="$INSTALL_DIR/.venv"
ACTUAL_GROUP=$(id -gn $ACTUAL_USER)

echo "Installation directory: $INSTALL_DIR"
echo "Running as user: $ACTUAL_USER:$ACTUAL_GROUP"
echo ""

# Check if installation exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}❌ Installation directory not found: $INSTALL_DIR${NC}"
    echo "Run ./setup_ubuntu.sh first"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    exit 1
fi

# Check if Kotak Neo modules exist
KOTAK_DIR="$INSTALL_DIR/modules/kotak_neo_auto_trader"
if [ ! -d "$KOTAK_DIR" ]; then
    echo -e "${YELLOW}⚠ Warning: Kotak Neo auto-trader modules not found${NC}"
    echo -e "${YELLOW}  Location: $KOTAK_DIR${NC}"
    echo ""
    read -p "Continue anyway (will create signal service only)? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
    KOTAK_AVAILABLE=false
else
    KOTAK_AVAILABLE=true
fi

echo ""
echo -e "${CYAN}This will create the following services:${NC}"
echo ""
echo "  ${GREEN}Signal Generation:${NC}"
echo "  1. Trade Analysis Service (4:00 PM daily)"
echo "     - Analyzes stocks and sends BUY signals via Telegram"
echo ""

if [ "$KOTAK_AVAILABLE" = true ]; then
    echo "  ${GREEN}Automated Trading (Kotak Neo):${NC}"
    echo "  2. Auto Trade Service (4:05 PM daily)"
    echo "     - Places buy orders based on analysis signals"
    echo "  3. Position Monitor Service (every 5 min, market hours)"
    echo "     - Real-time position monitoring and alerts"
    echo "  4. Sell Orders Service (9:15 AM daily)"
    echo "     - Places and monitors sell orders with EMA9 targets"
    echo "  5. EOD Cleanup Service (3:35 PM daily)"
    echo "     - End-of-day reconciliation and summaries"
else
    echo "  ${YELLOW}(Kotak Neo services will be skipped - modules not found)${NC}"
fi

echo ""
read -p "Continue with service installation? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled"
    exit 0
fi

echo ""

##############################################################################
# SERVICE 1: Trade Analysis (Signal Generation)
##############################################################################

echo -e "${CYAN}[1/5] Creating Trade Analysis Service${NC}"
echo "----------------------------------------"

cat > /etc/systemd/system/tradeagent-analysis.service << EOF
[Unit]
Description=Modular Trade Agent - Analysis Service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/trade_agent.py --backtest
StandardOutput=append:$INSTALL_DIR/logs/analysis_service.log
StandardError=append:$INSTALL_DIR/logs/analysis_service_error.log

Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"

NoNewPrivileges=true
PrivateTmp=true
EOF

cat > /etc/systemd/system/tradeagent-analysis.timer << EOF
[Unit]
Description=Trade Analysis Timer (4:00 PM IST)
Requires=tradeagent-analysis.service

[Timer]
OnCalendar=Mon-Fri 16:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Trade Analysis service created${NC}"

if [ "$KOTAK_AVAILABLE" = false ]; then
    echo ""
    echo -e "${YELLOW}Skipping Kotak Neo services (modules not found)${NC}"
    
    # Reload and enable just the analysis service
    systemctl daemon-reload
    systemctl enable tradeagent-analysis.timer
    systemctl start tradeagent-analysis.timer
    
    echo ""
    echo -e "${GREEN}========================================================================${NC}"
    echo -e "${GREEN}✅ ANALYSIS SERVICE INSTALLED${NC}"
    echo -e "${GREEN}========================================================================${NC}"
    echo ""
    echo "Next run: $(systemctl list-timers tradeagent-analysis.timer --no-pager | tail -n +2 | head -n 1)"
    exit 0
fi

##############################################################################
# SERVICE 2: Auto Trade (Buy Orders)
##############################################################################

echo ""
echo -e "${CYAN}[2/5] Creating Auto Trade Service${NC}"
echo "----------------------------------------"

cat > /etc/systemd/system/tradeagent-autotrade.service << EOF
[Unit]
Description=Modular Trade Agent - Auto Trade Service
After=network-online.target tradeagent-analysis.service
Wants=network-online.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python -m modules.kotak_neo_auto_trader.run_auto_trade --env kotak_neo.env
StandardOutput=append:$INSTALL_DIR/logs/autotrade_service.log
StandardError=append:$INSTALL_DIR/logs/autotrade_service_error.log

Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$INSTALL_DIR"

NoNewPrivileges=true
PrivateTmp=true
EOF

cat > /etc/systemd/system/tradeagent-autotrade.timer << EOF
[Unit]
Description=Auto Trade Timer (4:05 PM & 9:00 AM IST)
Requires=tradeagent-autotrade.service

[Timer]
# Run at 4:05 PM (after analysis) and 9:00 AM (retry failed orders)
OnCalendar=Mon-Fri 09:00:00
OnCalendar=Mon-Fri 16:05:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Auto Trade service created (runs at 4:05 PM & 9:00 AM)${NC}"

##############################################################################
# SERVICE 3: Position Monitor
##############################################################################

echo ""
echo -e "${CYAN}[3/5] Creating Position Monitor Service${NC}"
echo "----------------------------------------"

cat > /etc/systemd/system/tradeagent-monitor.service << EOF
[Unit]
Description=Modular Trade Agent - Position Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python -m modules.kotak_neo_auto_trader.run_position_monitor
StandardOutput=append:$INSTALL_DIR/logs/monitor_service.log
StandardError=append:$INSTALL_DIR/logs/monitor_service_error.log

Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$INSTALL_DIR"

NoNewPrivileges=true
PrivateTmp=true
EOF

cat > /etc/systemd/system/tradeagent-monitor.timer << EOF
[Unit]
Description=Position Monitor Timer (Every 5 min during market hours)
Requires=tradeagent-monitor.service

[Timer]
# Run every 5 minutes during market hours (9:15 AM - 3:30 PM)
OnCalendar=Mon-Fri 09:15,09:20,09:25,09:30,09:35,09:40,09:45,09:50,09:55,10:00,10:05,10:10,10:15,10:20,10:25,10:30,10:35,10:40,10:45,10:50,10:55,11:00,11:05,11:10,11:15,11:20,11:25,11:30,11:35,11:40,11:45,11:50,11:55,12:00,12:05,12:10,12:15,12:20,12:25,12:30,12:35,12:40,12:45,12:50,12:55,13:00,13:05,13:10,13:15,13:20,13:25,13:30,13:35,13:40,13:45,13:50,13:55,14:00,14:05,14:10,14:15,14:20,14:25,14:30,14:35,14:40,14:45,14:50,14:55,15:00,15:05,15:10,15:15,15:20,15:25,15:30
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Position Monitor service created${NC}"

##############################################################################
# SERVICE 4: Sell Orders
##############################################################################

echo ""
echo -e "${CYAN}[4/5] Creating Sell Orders Service${NC}"
echo "----------------------------------------"

cat > /etc/systemd/system/tradeagent-sell.service << EOF
[Unit]
Description=Modular Trade Agent - Sell Orders Management
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python -m modules.kotak_neo_auto_trader.run_sell_orders --env kotak_neo.env --run-once
StandardOutput=append:$INSTALL_DIR/logs/sell_service.log
StandardError=append:$INSTALL_DIR/logs/sell_service_error.log

Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$INSTALL_DIR"

NoNewPrivileges=true
PrivateTmp=true
EOF

cat > /etc/systemd/system/tradeagent-sell.timer << EOF
[Unit]
Description=Sell Orders Timer (9:15 AM IST - market open)
Requires=tradeagent-sell.service

[Timer]
OnCalendar=Mon-Fri 09:15:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Sell Orders service created${NC}"

##############################################################################
# SERVICE 5: EOD Cleanup
##############################################################################

echo ""
echo -e "${CYAN}[5/5] Creating EOD Cleanup Service${NC}"
echo "----------------------------------------"

cat > /etc/systemd/system/tradeagent-eod.service << EOF
[Unit]
Description=Modular Trade Agent - EOD Cleanup
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python -m modules.kotak_neo_auto_trader.run_eod_cleanup --env kotak_neo.env
StandardOutput=append:$INSTALL_DIR/logs/eod_service.log
StandardError=append:$INSTALL_DIR/logs/eod_service_error.log

Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$INSTALL_DIR"

NoNewPrivileges=true
PrivateTmp=true
EOF

cat > /etc/systemd/system/tradeagent-eod.timer << EOF
[Unit]
Description=EOD Cleanup Timer (3:35 PM IST - after market close)
Requires=tradeagent-eod.service

[Timer]
OnCalendar=Mon-Fri 15:35:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ EOD Cleanup service created${NC}"

##############################################################################
# Enable and Start Services
##############################################################################

echo ""
echo -e "${CYAN}Reloading systemd...${NC}"
systemctl daemon-reload

echo ""
echo -e "${CYAN}Enabling and starting services...${NC}"

systemctl enable tradeagent-analysis.timer
systemctl enable tradeagent-autotrade.timer
systemctl enable tradeagent-monitor.timer
systemctl enable tradeagent-sell.timer
systemctl enable tradeagent-eod.timer

systemctl start tradeagent-analysis.timer
systemctl start tradeagent-autotrade.timer
systemctl start tradeagent-monitor.timer
systemctl start tradeagent-sell.timer
systemctl start tradeagent-eod.timer

echo ""
echo -e "${GREEN}========================================================================${NC}"
echo -e "${GREEN}✅ ALL SERVICES INSTALLED SUCCESSFULLY${NC}"
echo -e "${GREEN}========================================================================${NC}"
echo ""

echo -e "${CYAN}Services Created (Aligned with Windows):${NC}"
echo ""
echo "  1. Trade Analysis   - Daily at 4:00 PM IST"
echo "  2. Auto Trade       - Daily at 9:00 AM IST (retry failed orders)"
echo "                      - Daily at 4:05 PM IST (place new AMO orders)"
echo "  3. Position Monitor - Every 5 min (9:15 AM - 3:30 PM)"
echo "  4. Sell Orders      - Daily at 9:15 AM IST (market open)"
echo "  5. EOD Cleanup      - Daily at 3:35 PM IST (after market close)"
echo ""

echo -e "${CYAN}Service Management:${NC}"
echo "  View all timers:    systemctl list-timers tradeagent-*"
echo "  View all services:  systemctl list-units tradeagent-*"
echo ""
echo "  Analysis logs:      journalctl -u tradeagent-analysis.service -f"
echo "  Auto Trade logs:    journalctl -u tradeagent-autotrade.service -f"
echo "  Monitor logs:       journalctl -u tradeagent-monitor.service -f"
echo "  Sell logs:          journalctl -u tradeagent-sell.service -f"
echo "  EOD logs:           journalctl -u tradeagent-eod.service -f"
echo ""

echo -e "${CYAN}Manual Execution:${NC}"
echo "  Analysis:    sudo systemctl start tradeagent-analysis.service"
echo "  Auto Trade:  sudo systemctl start tradeagent-autotrade.service"
echo "  Monitor:     sudo systemctl start tradeagent-monitor.service"
echo "  Sell:        sudo systemctl start tradeagent-sell.service"
echo "  EOD:         sudo systemctl start tradeagent-eod.service"
echo ""

echo -e "${CYAN}Stop All Services:${NC}"
echo "  sudo systemctl stop tradeagent-*.timer"
echo ""

echo -e "${CYAN}Next Scheduled Runs:${NC}"
systemctl list-timers tradeagent-* --no-pager

echo ""
echo -e "${YELLOW}⚠ Important Notes:${NC}"
echo "  - Kotak Neo credentials must be configured in: $INSTALL_DIR/kotak_neo.env"
echo "  - Test services manually before relying on automation"
echo "  - Monitor logs for first few days"
echo ""
