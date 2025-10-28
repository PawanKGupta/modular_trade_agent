#!/bin/bash
################################################################################
# Modular Trade Agent - Linux Startup Script
# Easy launcher for the trading agent
################################################################################

echo "========================================================================"
echo "Modular Trade Agent - Starting..."
echo "========================================================================"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if executable exists
if [ ! -f "./ModularTradeAgent" ]; then
    echo "❌ ERROR: ModularTradeAgent executable not found!"
    echo "Please ensure you're running this from the correct directory."
    exit 1
fi

# Check if config file exists
if [ ! -f "kotak_neo.env" ]; then
    echo "⚠ WARNING: kotak_neo.env not found!"
    echo ""
    echo "Creating template from kotak_neo.env.example..."
    if [ -f "kotak_neo.env.example" ]; then
        cp kotak_neo.env.example kotak_neo.env
        echo "✓ Template created. Please edit kotak_neo.env with your credentials."
        echo ""
        read -p "Press Enter to continue after editing kotak_neo.env..."
    else
        echo "❌ ERROR: kotak_neo.env.example not found!"
        exit 1
    fi
fi

# Run the application
echo "Starting Modular Trade Agent..."
echo ""
./ModularTradeAgent

# Capture exit code
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Application exited normally"
else
    echo "⚠ Application exited with code: $EXIT_CODE"
fi

echo ""
read -p "Press Enter to close..."
