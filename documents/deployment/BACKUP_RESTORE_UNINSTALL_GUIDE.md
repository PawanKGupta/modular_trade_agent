# Backup, Restore & Uninstallation Guide

## Overview
This guide covers the backup/restore utilities and uninstallation procedures for the Modular Trade Agent.

---

## Backup Utility

### BACKUP_DATA.bat

A convenient batch script to backup all important data files before making changes or troubleshooting.

### Features
- Creates timestamped backup directories
- Backs up all JSON data files
- Backs up CSV files (if present)
- Backs up configuration files
- Provides detailed summary

### Usage

**Simple Backup:**
```batch
BACKUP_DATA.bat
```

**What Gets Backed Up:**
- `data/*.json` - All trading data and history
- `data/*.csv` - CSV data files
- `config/*.json` - Configuration files

**Backup Location:**
```
data_backups\YYYYMMDD_HHMMSS\
```

### Output Example
```
============================================================
MODULAR TRADE AGENT - DATA BACKUP
============================================================

Creating backup directory: data_backups\20251028_101234

Backing up data files...
  ✓ JSON files backed up successfully
  ✓ CSV files backed up
  ✓ Config files backed up

============================================================
BACKUP SUMMARY
============================================================
Backup Location: data_backups\20251028_101234

Files backed up:
trades_history.json
system_recommended_symbols.json
pending_orders.json

Total files: 3

============================================================
✓ BACKUP COMPLETED SUCCESSFULLY
============================================================

Backup saved to: C:\Personal\Projects\TradingView\modular_trade_agent\data_backups\20251028_101234
```

---

## Restore Procedures

### Manual Restore

**Restore from latest backup:**
```powershell
# PowerShell
$latestBackup = Get-ChildItem data_backups\ -Directory | Sort-Object Name -Descending | Select-Object -First 1
Copy-Item "$($latestBackup.FullName)\*.json" data\ -Force
```

**Restore from specific backup:**
```batch
# Command Prompt
copy data_backups\20251028_101234\*.json data\ /Y
```

```powershell
# PowerShell
Copy-Item data_backups\20251028_101234\*.json data\ -Force
```

### Verify Restoration

**Check file integrity:**
```powershell
# Verify JSON files are valid
Get-Content data\system_recommended_symbols.json | ConvertFrom-Json
Get-Content data\pending_orders.json | ConvertFrom-Json
Get-Content data\trades_history.json | ConvertFrom-Json
```

### When to Restore

1. **JSON File Corruption**
   - Syntax errors in data files
   - Invalid JSON structure
   - Missing required fields

2. **Data Loss**
   - Accidental deletion
   - Failed update operation
   - System crash during write

3. **Testing Rollback**
   - After failed testing
   - To reset to known good state
   - Before major changes

---

## Uninstallation

### UNINSTALL.bat

Comprehensive uninstallation script that removes all Modular Trade Agent components from your system.

### Prerequisites
- **Administrator rights required**
- Close all running agent instances
- Stop all services before running

### What Gets Removed

1. **Windows Services:**
   - ModularTradeAgent_Main
   - ModularTradeAgent_Monitor
   - ModularTradeAgent_EOD
   - ModularTradeAgent_Sell

2. **Installation Directory:**
   - `C:\ProgramData\ModularTradeAgent\`
   - All subdirectories and files

3. **Desktop Shortcut:**
   - `Trading Agent.lnk`

4. **Environment Variables (Optional):**
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID

### Data Protection

**Automatic Backup:**
The uninstaller automatically backs up your data before removal:
- Backup location: `C:\ProgramData\ModularTradeAgent_Backup_YYYYMMDD_HHMMSS\`
- Includes: data files, logs, configuration

### Usage

**Run Uninstaller:**
1. Right-click `UNINSTALL.bat`
2. Select "Run as Administrator"
3. Confirm uninstallation when prompted
4. Optionally remove environment variables

**Interactive Prompts:**
```batch
# Confirmation prompt
Are you sure you want to uninstall? (yes/no): yes

# Environment variables prompt
Remove environment variables? (yes/no): yes
```

### Uninstallation Process

```
1. Check administrator rights
2. Confirm uninstallation
3. Stop all Windows services
4. Remove services from system
5. Backup data files
6. Remove installation directory
7. Remove desktop shortcut
8. (Optional) Clean environment variables
9. Display summary
```

### Output Example

```
============================================================
MODULAR TRADE AGENT - UNINSTALLATION
============================================================

WARNING: This will remove all Modular Trade Agent services and files!

Are you sure you want to uninstall? (yes/no): yes

============================================================
STOPPING AND REMOVING SERVICES
============================================================

Checking service: ModularTradeAgent_Main
  Stopping ModularTradeAgent_Main...
  Removing ModularTradeAgent_Main...
  ✓ Service ModularTradeAgent_Main removed

...

============================================================
BACKING UP DATA FILES
============================================================

Creating backup at: C:\ProgramData\ModularTradeAgent_Backup_20251028_101234
  ✓ Data backed up to: C:\ProgramData\ModularTradeAgent_Backup_20251028_101234

============================================================
REMOVING INSTALLATION DIRECTORY
============================================================

Removing: C:\ProgramData\ModularTradeAgent
  ✓ Installation directory removed

============================================================
REMOVING DESKTOP SHORTCUT
============================================================

  ✓ Desktop shortcut removed

============================================================
UNINSTALLATION SUMMARY
============================================================

✓ UNINSTALLATION COMPLETED SUCCESSFULLY

All components have been removed.

Your data has been backed up to:
C:\ProgramData\ModularTradeAgent_Backup_20251028_101234
```

### Troubleshooting Uninstallation

**Service Removal Fails:**
```batch
# Manually stop service
net stop ModularTradeAgent_Main

# Force delete service
sc delete ModularTradeAgent_Main
```

**Directory Removal Fails:**
```batch
# Check for locked files
handle "C:\ProgramData\ModularTradeAgent"

# Close applications and retry
rmdir /S /Q "C:\ProgramData\ModularTradeAgent"
```

**Permission Issues:**
```batch
# Take ownership
takeown /F "C:\ProgramData\ModularTradeAgent" /R /D Y
icacls "C:\ProgramData\ModularTradeAgent" /grant administrators:F /T

# Then retry deletion
rmdir /S /Q "C:\ProgramData\ModularTradeAgent"
```

---

## Creating Installer EXE

### Using PyInstaller

**Install PyInstaller:**
```powershell
pip install pyinstaller
```

**Create Installer EXE:**
```powershell
pyinstaller --onefile --name "TradeAgentInstaller" installer\setup.py
```

**With Icon:**
```powershell
pyinstaller --onefile --icon=icon.ico --name "TradeAgentInstaller" installer\setup.py
```

**Output:**
- EXE file: `dist\TradeAgentInstaller.exe`
- Spec file: `TradeAgentInstaller.spec`
- Build files: `build\` (can be deleted)

### PyInstaller Options

| Option | Description |
|--------|-------------|
| `--onefile` | Bundle into single EXE |
| `--onedir` | Create folder with dependencies |
| `--noconsole` | Hide console window (GUI apps) |
| `--windowed` | Same as --noconsole |
| `--icon=file.ico` | Add custom icon |
| `--name "Name"` | Custom EXE name |
| `--add-data "src;dest"` | Include data files |
| `--hidden-import module` | Include missing imports |
| `--clean` | Clean cache before building |

### Advanced Build

**Include Additional Files:**
```powershell
pyinstaller --onefile `
    --name "TradeAgentInstaller" `
    --icon=icon.ico `
    --add-data "config;config" `
    --add-data "README.md;." `
    installer\setup.py
```

**For GUI Applications:**
```powershell
pyinstaller --onefile --noconsole --name "TradeAgentGUI" gui_app.py
```

### Testing the EXE

```powershell
# Test the generated EXE
.\dist\TradeAgentInstaller.exe
```

### Distribution

**Single File Distribution:**
```
dist\
  └── TradeAgentInstaller.exe  (Distribute this file)
```

**Cleanup Build Artifacts:**
```powershell
# Remove build files
Remove-Item -Recurse build, __pycache__
Remove-Item *.spec
```

---

## Best Practices

### Backup Strategy

1. **Before Major Changes:**
   - Run `BACKUP_DATA.bat` before updates
   - Keep multiple backup versions
   - Test restore procedure periodically

2. **Regular Backups:**
   - Daily: After trading session
   - Weekly: Archive to external storage
   - Monthly: Long-term storage

3. **Backup Retention:**
   - Keep last 7 daily backups
   - Keep last 4 weekly backups
   - Keep monthly backups indefinitely

### Uninstallation Checklist

- [ ] Stop all running services
- [ ] Close agent applications
- [ ] Verify backup location
- [ ] Note environment variables
- [ ] Run as Administrator
- [ ] Confirm data backup created
- [ ] Verify uninstallation success
- [ ] Keep backup for 30 days

### Reinstallation After Uninstall

1. **Verify clean uninstall:**
```powershell
# Check no services remain
Get-Service | Where-Object {$_.Name -like "*ModularTradeAgent*"}

# Check directory removed
Test-Path "C:\ProgramData\ModularTradeAgent"
```

2. **Restore configuration (if needed):**
```powershell
# Copy env file from backup
Copy-Item "C:\ProgramData\ModularTradeAgent_Backup_*\kotak_neo.env" .
```

3. **Run new installation:**
```batch
TradeAgentInstaller.exe
```

---

## Related Documentation

- [Installation Guide](WINDOWS_SERVICES_GUIDE.md)
- [Testing Guide](TESTING_GUIDE_PHASE1_PHASE2.md)
- [Deployment Guide](DEPLOYMENT_READY.md)
- [Health Check Guide](HEALTH_CHECK.md)

---

## Support

For issues with backup, restore, or uninstallation:

1. Check backup directory exists: `data_backups\`
2. Verify administrator rights for uninstall
3. Review error messages in script output
4. Check system logs: Event Viewer → Windows Logs → Application
5. Ensure all services are stopped before uninstall

---

**Last Updated:** 2025-10-28  
**Version:** 25.4.0 - Q4 2025
