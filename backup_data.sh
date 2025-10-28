#!/bin/bash
################################################################################
# Backup Data Script for Linux
# Creates timestamped backups of trade data and configuration
################################################################################

echo "========================================================================"
echo "Modular Trade Agent - Data Backup"
echo "========================================================================"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create backup directory
BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"

# Generate timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

mkdir -p "$BACKUP_PATH"

echo "Creating backup: $BACKUP_NAME"
echo ""

# Backup data directory
if [ -d "data" ]; then
    echo "✓ Backing up data directory..."
    cp -r data "$BACKUP_PATH/"
fi

# Backup configuration
if [ -f "kotak_neo.env" ]; then
    echo "✓ Backing up configuration..."
    cp kotak_neo.env "$BACKUP_PATH/"
fi

# Backup logs if they exist
if [ -d "logs" ]; then
    echo "✓ Backing up logs..."
    cp -r logs "$BACKUP_PATH/"
fi

# Create archive
echo ""
echo "Creating compressed archive..."
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"
cd ..

# Get backup size
BACKUP_SIZE=$(du -sh "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)

echo ""
echo "========================================================================"
echo "✅ BACKUP COMPLETED SUCCESSFULLY!"
echo "========================================================================"
echo ""
echo "Backup file: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
echo "Size: $BACKUP_SIZE"
echo ""
echo "To restore this backup:"
echo "  tar -xzf ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz -C ${BACKUP_DIR}"
echo "  cp -r ${BACKUP_DIR}/${BACKUP_NAME}/* ."
echo ""

# Clean old backups (keep last 10)
echo "Cleaning old backups (keeping last 10)..."
cd "$BACKUP_DIR"
ls -t backup_*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm
BACKUP_COUNT=$(ls -1 backup_*.tar.gz 2>/dev/null | wc -l)
echo "✓ Total backups: $BACKUP_COUNT"
cd ..

echo ""
read -p "Press Enter to continue..."
