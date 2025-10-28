#!/bin/bash
# Make all shell scripts executable
chmod +x setup_ubuntu.sh
chmod +x fix_ubuntu_system.sh
chmod +x verify_installation.sh
chmod +x build_linux.sh
chmod +x backup_data.sh
chmod +x install_service.sh
echo "✓ All scripts are now executable"
echo ""
echo "Available commands:"
echo "  ./setup_ubuntu.sh          - Install the trading agent"
echo "  ./fix_ubuntu_system.sh     - Fix system issues"
echo "  ./verify_installation.sh   - Verify installation"
