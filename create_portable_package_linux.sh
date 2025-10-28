#!/bin/bash
################################################################################
# Create Portable Linux Package
# Packages the executable with all necessary files for distribution
################################################################################

set -e

echo "========================================================================"
echo "Creating Portable Linux Package"
echo "========================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Read version
if [ -f "VERSION" ]; then
    VERSION=$(cat VERSION)
else
    VERSION="1.0.0"
fi

PACKAGE_NAME="ModularTradeAgent-Linux-v${VERSION}"
PACKAGE_DIR="dist/${PACKAGE_NAME}"

# Check if executable exists
if [ ! -f "dist/ModularTradeAgent" ]; then
    echo -e "${RED}❌ ERROR: Executable not found!${NC}"
    echo "Please run ./build_linux.sh first"
    exit 1
fi

# Create package directory
echo "Creating package structure..."
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR/data"
mkdir -p "$PACKAGE_DIR/documents"

# Copy executable
echo "Copying executable..."
cp dist/ModularTradeAgent "$PACKAGE_DIR/"
chmod +x "$PACKAGE_DIR/ModularTradeAgent"

# Copy scripts
echo "Copying scripts..."
cp start.sh "$PACKAGE_DIR/"
cp backup_data.sh "$PACKAGE_DIR/"
cp health_check.sh "$PACKAGE_DIR/"
cp install_service.sh "$PACKAGE_DIR/"
cp uninstall_service.sh "$PACKAGE_DIR/"
chmod +x "$PACKAGE_DIR"/*.sh

# Copy configuration templates
echo "Copying configuration files..."
if [ -f "modules/kotak_neo_auto_trader/kotak_neo.env.example" ]; then
    cp modules/kotak_neo_auto_trader/kotak_neo.env.example "$PACKAGE_DIR/"
fi

# Copy documentation
echo "Copying documentation..."
cp README.md "$PACKAGE_DIR/" 2>/dev/null || true
cp EXECUTABLE_README_LINUX.md "$PACKAGE_DIR/README.md" 2>/dev/null || true
cp documents/LINUX_EXECUTABLE_GUIDE.md "$PACKAGE_DIR/documents/" 2>/dev/null || true
cp documents/LINUX_SERVICES_GUIDE.md "$PACKAGE_DIR/documents/" 2>/dev/null || true
cp documents/BACKUP_RESTORE_UNINSTALL_GUIDE.md "$PACKAGE_DIR/documents/" 2>/dev/null || true
cp documents/HEALTH_CHECK.md "$PACKAGE_DIR/documents/" 2>/dev/null || true

# Copy version file
cp VERSION "$PACKAGE_DIR/" 2>/dev/null || echo "$VERSION" > "$PACKAGE_DIR/VERSION"

# Create .gitkeep in data directory
touch "$PACKAGE_DIR/data/.gitkeep"

# Create archive
echo ""
echo "Creating tar.gz archive..."
cd dist
tar -czf "${PACKAGE_NAME}.tar.gz" "$PACKAGE_NAME"
cd ..

# Calculate size
SIZE=$(du -sh "dist/${PACKAGE_NAME}.tar.gz" | cut -f1)

echo ""
echo -e "${GREEN}========================================================================"
echo "✅ PACKAGE CREATED SUCCESSFULLY!"
echo "========================================================================${NC}"
echo ""
echo "Package: dist/${PACKAGE_NAME}.tar.gz"
echo "Size: $SIZE"
echo ""
echo "Contents:"
echo "  - ModularTradeAgent (executable)"
echo "  - start.sh (launcher)"
echo "  - backup_data.sh (backup utility)"
echo "  - health_check.sh (system monitor)"
echo "  - install_service.sh (systemd service installer)"
echo "  - uninstall_service.sh (service uninstaller)"
echo "  - kotak_neo.env.example (configuration template)"
echo "  - Documentation (README, guides)"
echo "  - data/ (for trade history)"
echo ""
echo "To distribute:"
echo "  scp dist/${PACKAGE_NAME}.tar.gz user@server:/path/"
echo ""
echo "To extract on target system:"
echo "  tar -xzf ${PACKAGE_NAME}.tar.gz"
echo "  cd ${PACKAGE_NAME}"
echo "  ./start.sh"
echo ""
