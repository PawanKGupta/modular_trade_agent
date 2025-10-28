#!/bin/bash
################################################################################
# Uninstall Trade Agent systemd Service
# Removes all service and timer files
################################################################################

set -e

echo "========================================================================"
echo "Uninstalling Modular Trade Agent Service"
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

echo -e "${YELLOW}This will remove all Trade Agent services and timers.${NC}"
read -p "Are you sure? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Stop services and timers
echo ""
echo "Stopping services and timers..."
systemctl stop tradeagent-buy.timer 2>/dev/null || true
systemctl stop tradeagent-sell.timer 2>/dev/null || true
systemctl stop tradeagent-buy.service 2>/dev/null || true
systemctl stop tradeagent-sell.service 2>/dev/null || true
systemctl stop tradeagent.service 2>/dev/null || true
echo -e "${GREEN}✓ Services stopped${NC}"

# Disable services and timers
echo ""
echo "Disabling services and timers..."
systemctl disable tradeagent-buy.timer 2>/dev/null || true
systemctl disable tradeagent-sell.timer 2>/dev/null || true
systemctl disable tradeagent.service 2>/dev/null || true
echo -e "${GREEN}✓ Services disabled${NC}"

# Remove service files
echo ""
echo "Removing service files..."
rm -f /etc/systemd/system/tradeagent.service
rm -f /etc/systemd/system/tradeagent-buy.service
rm -f /etc/systemd/system/tradeagent-sell.service
rm -f /etc/systemd/system/tradeagent-buy.timer
rm -f /etc/systemd/system/tradeagent-sell.timer
echo -e "${GREEN}✓ Service files removed${NC}"

# Reload systemd
echo ""
echo "Reloading systemd daemon..."
systemctl daemon-reload
systemctl reset-failed
echo -e "${GREEN}✓ Systemd reloaded${NC}"

echo ""
echo "========================================================================"
echo -e "${GREEN}✅ UNINSTALLATION COMPLETE${NC}"
echo "========================================================================"
echo ""
echo "The Trade Agent service has been completely removed."
echo "Your data and configuration files remain intact."
echo ""
echo "To reinstall: sudo ./install_service.sh"
echo ""
