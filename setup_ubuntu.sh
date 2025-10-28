#!/bin/bash
################################################################################
# Modular Trade Agent - Ubuntu Installer Setup Script
# Complete installation wizard for Ubuntu/Debian systems
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Installation configuration
INSTALL_DIR="$HOME/modular_trade_agent"
VENV_DIR="$INSTALL_DIR/.venv"
CONFIG_FILE="$INSTALL_DIR/cred.env"
VERSION="1.0.0"

# Function to print colored messages
print_header() {
    echo ""
    echo -e "${BLUE}========================================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${BLUE}========================================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Check if running on Ubuntu/Debian
check_os() {
    if [ ! -f /etc/os-release ]; then
        print_error "Cannot determine OS. This script is for Ubuntu/Debian systems."
        exit 1
    fi
    
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]] && [[ "$ID" != "debian" ]]; then
        print_warning "This script is designed for Ubuntu/Debian. Your OS: $ID"
        read -p "Continue anyway? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    print_success "OS Check: $PRETTY_NAME"
}

# Check Python version
check_python() {
    print_info "Checking Python installation..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed!"
        echo "Install with: sudo apt-get install python3 python3-pip python3-venv"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        print_error "Python 3.8 or higher required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "Python version: $PYTHON_VERSION"
}

# Install system dependencies
install_system_deps() {
    print_header "Installing System Dependencies"
    
    print_info "Updating package list..."
    sudo apt-get update -qq
    
    print_info "Installing required packages..."
    
    PACKAGES=(
        python3-pip
        python3-venv
        python3-dev
        build-essential
        git
        curl
        wget
        chromium-browser
        chromium-chromedriver
    )
    
    for package in "${PACKAGES[@]}"; do
        if dpkg -l | grep -q "^ii  $package"; then
            print_success "$package already installed"
        else
            print_info "Installing $package..."
            sudo apt-get install -y $package -qq
            print_success "$package installed"
        fi
    done
}

# Create installation directory
create_install_dir() {
    print_header "Setting Up Installation Directory"
    
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Installation directory already exists: $INSTALL_DIR"
        read -p "Remove and reinstall? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
            print_success "Old installation removed"
        else
            print_info "Using existing directory"
        fi
    fi
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/logs"
    mkdir -p "$INSTALL_DIR/data"
    mkdir -p "$INSTALL_DIR/analysis_results"
    mkdir -p "$INSTALL_DIR/backtest_reports"
    mkdir -p "$INSTALL_DIR/backtest_exports"
    
    print_success "Installation directory created: $INSTALL_DIR"
}

# Clone or copy repository
setup_repository() {
    print_header "Setting Up Repository"
    
    # Check if we're running from the repo
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    
    if [ -f "$SCRIPT_DIR/requirements.txt" ] && [ -f "$SCRIPT_DIR/trade_agent.py" ]; then
        print_info "Copying files from current directory..."
        
        # Copy all necessary files
        cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/" 2>/dev/null || true
        cp -r "$SCRIPT_DIR"/.github "$INSTALL_DIR/" 2>/dev/null || true
        
        print_success "Files copied to installation directory"
    else
        print_info "Please provide repository URL:"
        read -p "Git repository URL (or press Enter to skip): " REPO_URL
        
        if [ -n "$REPO_URL" ]; then
            git clone "$REPO_URL" "$INSTALL_DIR"
            print_success "Repository cloned"
        else
            print_error "No repository source provided"
            exit 1
        fi
    fi
}

# Create virtual environment
create_virtualenv() {
    print_header "Creating Virtual Environment"
    
    if [ -d "$VENV_DIR" ]; then
        print_warning "Virtual environment already exists"
        rm -rf "$VENV_DIR"
    fi
    
    print_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    print_success "Virtual environment created"
}

# Install Python dependencies
install_dependencies() {
    print_header "Installing Python Dependencies"
    
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    print_info "Upgrading pip..."
    pip install --upgrade pip -q
    
    if [ -f "$INSTALL_DIR/requirements.txt" ]; then
        print_info "Installing dependencies from requirements.txt..."
        pip install -r "$INSTALL_DIR/requirements.txt" -q
        print_success "Dependencies installed"
    else
        print_error "requirements.txt not found!"
        exit 1
    fi
}

# Configure environment variables
configure_environment() {
    print_header "Configuration Setup"
    
    if [ -f "$CONFIG_FILE" ]; then
        print_warning "Configuration file already exists"
        read -p "Reconfigure? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing configuration"
            return
        fi
    fi
    
    print_info "Setting up Telegram credentials..."
    echo ""
    echo "You can find your bot token from @BotFather on Telegram"
    echo "You can find your chat ID from @userinfobot on Telegram"
    echo ""
    
    read -p "Telegram Bot Token: " TELEGRAM_BOT_TOKEN
    read -p "Telegram Chat ID: " TELEGRAM_CHAT_ID
    
    # Create configuration file
    cat > "$CONFIG_FILE" << EOF
# Modular Trade Agent Configuration
# Generated: $(date)

# Telegram Configuration (Required)
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID

# Retry Configuration
RETRY_MAX_ATTEMPTS=3
RETRY_BASE_DELAY=1.0
RETRY_MAX_DELAY=30.0
RETRY_BACKOFF_MULTIPLIER=2.0

# Circuit Breaker Configuration
CIRCUITBREAKER_FAILURE_THRESHOLD=3
CIRCUITBREAKER_RECOVERY_TIMEOUT=60.0

# News Sentiment Configuration
NEWS_SENTIMENT_ENABLED=true
NEWS_SENTIMENT_LOOKBACK_DAYS=30
NEWS_SENTIMENT_MIN_ARTICLES=2
NEWS_SENTIMENT_POS_THRESHOLD=0.25
NEWS_SENTIMENT_NEG_THRESHOLD=-0.25

# Trading Parameters (Optional - defaults in config/settings.py)
# LOOKBACK_DAYS=90
# MIN_VOLUME_MULTIPLIER=1.0
# RSI_OVERSOLD=30
EOF
    
    chmod 600 "$CONFIG_FILE"
    print_success "Configuration saved to: $CONFIG_FILE"
}

# Test installation
test_installation() {
    print_header "Testing Installation"
    
    cd "$INSTALL_DIR"
    source "$VENV_DIR/bin/activate"
    
    print_info "Testing Python imports..."
    python3 -c "
import sys
import yfinance as yf
import pandas as pd
import numpy as np
from selenium import webdriver
print('All imports successful!')
" && print_success "Python packages OK" || print_error "Python import test failed"
    
    print_info "Testing Telegram configuration..."
    if [ -f "test_telegram.py" ]; then
        python3 test_telegram.py && print_success "Telegram test OK" || print_warning "Telegram test failed (check credentials)"
    else
        print_warning "test_telegram.py not found, skipping"
    fi
}

# Create launcher scripts
create_launchers() {
    print_header "Creating Launcher Scripts"
    
    # Main launcher
    cat > "$INSTALL_DIR/run_agent.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python3 trade_agent.py "$@"
EOF
    
    # With backtest
    cat > "$INSTALL_DIR/run_agent_backtest.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python3 trade_agent.py --backtest "$@"
EOF
    
    # Backtest only
    cat > "$INSTALL_DIR/run_backtest.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python3 run_backtest.py "$@"
EOF
    
    # Make executable
    chmod +x "$INSTALL_DIR/run_agent.sh"
    chmod +x "$INSTALL_DIR/run_agent_backtest.sh"
    chmod +x "$INSTALL_DIR/run_backtest.sh"
    
    print_success "Launcher scripts created"
}

# Setup systemd service (optional)
setup_systemd_service() {
    print_header "Systemd Service Setup (Optional)"
    
    read -p "Install as systemd service for automatic execution? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Skipping systemd service setup"
        return
    fi
    
    print_info "Creating systemd service..."
    
    # Create service file
    SERVICE_FILE="/tmp/modular-trade-agent.service"
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Modular Trade Agent - Automated Trading System
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/trade_agent.py --backtest
Restart=on-failure
RestartSec=60
StandardOutput=append:$INSTALL_DIR/logs/service.log
StandardError=append:$INSTALL_DIR/logs/service_error.log

# Environment
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    
    # Create timer for daily execution at 4PM
    TIMER_FILE="/tmp/modular-trade-agent.timer"
    cat > "$TIMER_FILE" << EOF
[Unit]
Description=Modular Trade Agent Daily Timer
Requires=modular-trade-agent.service

[Timer]
OnCalendar=Mon-Fri 16:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF
    
    # Install service
    sudo cp "$SERVICE_FILE" /etc/systemd/system/
    sudo cp "$TIMER_FILE" /etc/systemd/system/
    
    sudo systemctl daemon-reload
    sudo systemctl enable modular-trade-agent.timer
    sudo systemctl start modular-trade-agent.timer
    
    print_success "Systemd service installed"
    print_info "Service will run daily at 4:00 PM IST (Mon-Fri)"
    
    echo ""
    echo "Service management commands:"
    echo "  View status:   systemctl status modular-trade-agent.timer"
    echo "  View logs:     journalctl -u modular-trade-agent.service -f"
    echo "  Manual run:    systemctl start modular-trade-agent.service"
    echo "  Stop timer:    sudo systemctl stop modular-trade-agent.timer"
}

# Create desktop shortcut (optional)
create_desktop_shortcut() {
    print_header "Desktop Shortcut (Optional)"
    
    read -p "Create desktop shortcut? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return
    fi
    
    DESKTOP_FILE="$HOME/Desktop/ModularTradeAgent.desktop"
    
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Modular Trade Agent
Comment=Automated Trading System
Exec=gnome-terminal -- $INSTALL_DIR/run_agent.sh
Icon=utilities-terminal
Path=$INSTALL_DIR
Terminal=true
Categories=Office;Finance;
EOF
    
    chmod +x "$DESKTOP_FILE"
    print_success "Desktop shortcut created"
}

# Print final summary
print_summary() {
    print_header "Installation Complete! 🚀"
    
    echo -e "${GREEN}Installation Directory:${NC} $INSTALL_DIR"
    echo -e "${GREEN}Configuration File:${NC} $CONFIG_FILE"
    echo -e "${GREEN}Virtual Environment:${NC} $VENV_DIR"
    echo ""
    
    echo -e "${CYAN}Quick Start:${NC}"
    echo "  cd $INSTALL_DIR"
    echo "  ./run_agent.sh                  # Run standard analysis"
    echo "  ./run_agent_backtest.sh         # Run with backtest validation"
    echo "  ./run_backtest.sh RELIANCE.NS 2022-01-01 2023-12-31"
    echo ""
    
    echo -e "${CYAN}Manual Execution:${NC}"
    echo "  source $VENV_DIR/bin/activate"
    echo "  python3 trade_agent.py --help"
    echo ""
    
    if systemctl is-active --quiet modular-trade-agent.timer 2>/dev/null; then
        echo -e "${CYAN}Systemd Service:${NC}"
        echo "  systemctl status modular-trade-agent.timer"
        echo "  journalctl -u modular-trade-agent.service -f"
        echo ""
    fi
    
    echo -e "${CYAN}Configuration:${NC}"
    echo "  Edit: $CONFIG_FILE"
    echo "  Trading params: $INSTALL_DIR/config/settings.py"
    echo ""
    
    echo -e "${CYAN}Logs:${NC}"
    echo "  Application: $INSTALL_DIR/logs/"
    echo "  Analysis results: $INSTALL_DIR/analysis_results/"
    echo ""
    
    echo -e "${YELLOW}⚠ Important:${NC}"
    echo "  - Test with paper trading first!"
    echo "  - Verify Telegram alerts are working"
    echo "  - Review trading parameters in config/settings.py"
    echo "  - Monitor logs during first few runs"
    echo ""
    
    echo -e "${GREEN}Happy Trading! 📈${NC}"
}

# Main installation flow
main() {
    print_header "Modular Trade Agent - Ubuntu Installation Wizard v$VERSION"
    
    echo "This script will install the Modular Trade Agent on your Ubuntu system."
    echo ""
    read -p "Continue with installation? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Installation cancelled"
        exit 0
    fi
    
    check_os
    check_python
    install_system_deps
    create_install_dir
    setup_repository
    create_virtualenv
    install_dependencies
    configure_environment
    create_launchers
    test_installation
    setup_systemd_service
    create_desktop_shortcut
    print_summary
}

# Run main installation
main
