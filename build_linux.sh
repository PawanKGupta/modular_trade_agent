#!/bin/bash
################################################################################
# Modular Trade Agent - Linux Build Script
# Builds a standalone Linux executable using PyInstaller
################################################################################

set -e  # Exit on error

echo "========================================================================"
echo "Modular Trade Agent - Linux Build Script"
echo "========================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3.11 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install/upgrade required packages
echo ""
echo "Installing build dependencies..."
pip install --upgrade pip
pip install pyinstaller
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf build dist
echo -e "${GREEN}✓ Cleaned build directories${NC}"

# Read version
if [ -f "VERSION" ]; then
    VERSION=$(cat VERSION)
    echo ""
    echo "Building version: $VERSION"
fi

# Build executable
echo ""
echo "========================================================================"
echo "Building Linux Executable..."
echo "========================================================================"
pyinstaller --clean --noconfirm build_executable_linux.spec

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================================================"
    echo "✅ BUILD SUCCESSFUL!"
    echo "========================================================================${NC}"
    echo ""
    echo "Executable location: dist/ModularTradeAgent"
    echo ""
    
    # Make executable
    chmod +x dist/ModularTradeAgent
    
    # Show file info
    ls -lh dist/ModularTradeAgent
    echo ""
    
    # Test executable
    echo "Testing executable..."
    if dist/ModularTradeAgent --version 2>/dev/null; then
        echo -e "${GREEN}✓ Executable test passed${NC}"
    else
        echo -e "${YELLOW}⚠ Could not test executable (--version flag may not be implemented)${NC}"
    fi
    
    echo ""
    echo "Next steps:"
    echo "1. Test: ./dist/ModularTradeAgent"
    echo "2. Create package: ./create_portable_package_linux.sh"
    echo ""
else
    echo ""
    echo -e "${RED}========================================================================"
    echo "❌ BUILD FAILED"
    echo "========================================================================${NC}"
    echo ""
    echo "Check the error messages above for details."
    exit 1
fi
