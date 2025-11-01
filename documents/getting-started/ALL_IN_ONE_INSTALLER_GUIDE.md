# All-in-One Installer Guide

## Overview

This guide explains the **all-in-one installer** approach - a single `.exe` file that includes Python, dependencies, and provides a GUI wizard for complete automated setup.

## What is the All-in-One Installer?

A single executable (`ModularTradeAgent_Setup.exe`) that:
- ✅ Includes Python 3.11 embedded
- ✅ Includes all dependencies pre-installed
- ✅ Includes complete Trading Agent source code
- ✅ Provides GUI wizard for configuration
- ✅ Automatically installs as Windows service
- ✅ Creates desktop shortcuts
- ✅ **Zero manual steps** for end users!

## Build the Installer

```powershell
# Single command to build everything
.\build_installer.ps1
```

This will:
1. Create portable Python package (~200 MB)
2. Download NSSM for service installation
3. Bundle everything into single installer (.exe)
4. Output: `dist\ModularTradeAgent_Setup.exe` (~250-300 MB)

Build time: 10-15 minutes

## User Experience

### Step 1: Run the Installer
User double-clicks `ModularTradeAgent_Setup.exe`

### Step 2: GUI Configuration Wizard
![Configuration GUI](https://via.placeholder.com/500x450/4CAF50/FFFFFF?text=Configuration+Wizard)

A clean GUI prompts for:
- Consumer Key *
- Consumer Secret *
- Mobile Number *
- Password *
- MPIN *
- Telegram Bot Token (optional)
- Telegram Chat ID (optional)

### Step 3: Automatic Installation
Installer automatically:
1. Extracts Python to `C:\ProgramData\ModularTradeAgent`
2. Extracts Trading Agent source code
3. Saves `.env` file with entered credentials
4. Installs Windows service "ModularTradeAgent"
5. Creates launcher scripts
6. Creates desktop shortcut

### Step 4: Done!
User gets:
- Desktop shortcut to run agent
- Windows service installed
- Configuration complete
- Ready to trade!

## What Gets Installed

```
C:\ProgramData\ModularTradeAgent/
  ├── python/                    # Python 3.11 embedded
  │   ├── python.exe
  │   └── Lib/
  ├── TradingAgent/              # Your application
  │   ├── modules/
  │   ├── core/
  │   ├── config/
  │   └── data/
  ├── kotak_neo.env              # User's credentials
  ├── RUN_AGENT.bat              # Manual launcher
  ├── START_SERVICE.bat          # Start service
  ├── STOP_SERVICE.bat           # Stop service
  ├── logs/                      # Log files
  └── data/                      # Trade history

Desktop:
  └── Trading Agent.lnk          # Shortcut to RUN_AGENT.bat

Windows Services:
  └── ModularTradeAgent          # Automatic trading service
```

## Distribution

### Single File Distribution
```
ModularTradeAgent_Setup.exe    # ~250-300 MB
```

That's it! One file to distribute.

### Installation Instructions for End Users

**Step 1**: Download `ModularTradeAgent_Setup.exe`

**Step 2**: Right-click → "Run as Administrator"

**Step 3**: Enter your Kotak Neo credentials in the wizard

**Step 4**: Click "Install"

**Done!** The agent is installed and configured.

## Features

### Admin Elevation
- Installer automatically requests admin rights
- Required for Windows service installation
- User gets UAC prompt on launch

### GUI Configuration
- Clean, professional Tkinter GUI
- Input validation (required fields)
- Password fields masked
- Scrollable for many fields

### Fallback to Console
- If GUI unavailable, uses console prompts
- Same functionality, text-based

### Service Management
- Uses NSSM (Non-Sucking Service Manager)
- Service can start on boot
- Easy start/stop with bat files

### Desktop Integration
- Creates "Trading Agent" shortcut on desktop
- One-click access to agent

## Comparison with Other Approaches

| Feature | All-in-One Installer | Portable Package | PyInstaller .exe |
|---------|---------------------|------------------|------------------|
| **File Size** | 250-300 MB | 200-300 MB (folder) | 50-100 MB |
| **User Steps** | 1. Run, 2. Enter creds, 3. Done | Extract, Config, Run | Extract, Config, Run |
| **GUI Wizard** | ✅ Yes | ❌ No | ❌ No |
| **Service Install** | ✅ Automatic | ❌ Manual | ❌ Manual |
| **Desktop Shortcut** | ✅ Automatic | ❌ Manual | ❌ Manual |
| **Editable Code** | ✅ Yes (after install) | ✅ Yes | ❌ No |
| **Python Visible** | ✅ Yes (in install dir) | ✅ Yes | ❌ Embedded |

**Recommendation**: Use **All-in-One Installer** for:
- Non-technical users
- Corporate deployment
- Minimal support overhead
- Professional appearance

## Testing

### Test on Clean VM
1. Windows 10/11 without Python
2. Run installer as admin
3. Verify service installation
4. Test trading functionality

### Test Scenarios
- ✅ First-time installation
- ✅ Reinstall (upgrade)
- ✅ Configuration changes
- ✅ Service start/stop
- ✅ Manual vs service execution

## Customization

### Change Install Location

Edit `installer/setup.py` line 33:
```python
self.install_dir = Path("D:/TradingAgent")  # Custom location
```

### Change Service Name

Edit `installer/setup.py` line 227:
```python
service_name = "MyTradingBot"  # Custom service name
```

### Add More Config Fields

Edit `installer/setup.py` lines 134-142 (GUI) or 83-91 (console):
```python
fields = [
    ("KOTAK_NEO_CONSUMER_KEY", "Consumer Key *"),
    ("MY_CUSTOM_FIELD", "My Custom Setting"),  # Add here
    ...
]
```

### Change GUI Appearance

Edit `installer/setup.py` GUI section (lines 105-196):
- Window size: line 109
- Fonts: line 113-114
- Colors: Tkinter styling

## Troubleshooting

### Build Fails

**Error**: `portable_package not found`
- **Solution**: Run `create_portable_package.ps1` first manually

**Error**: `pyinstaller not found`
- **Solution**: Install in venv: `pip install pyinstaller`

### Installer Fails

**Error**: `Admin rights required`
- **Solution**: Right-click exe → "Run as Administrator"

**Error**: `NSSM not found`
- **Solution**: Service install skipped, use RUN_AGENT.bat instead

### Service Won't Start

**Error**: Service fails to start
- **Check**: Credentials in `kotak_neo.env`
- **Check**: Python path is correct
- **Check**: Event Viewer for detailed errors

## Advantages

### For Developer (You)
- ✅ Professional deployment method
- ✅ Minimal support requests
- ✅ One-file distribution
- ✅ Easy to update

### For End User
- ✅ No Python knowledge needed
- ✅ No command line usage
- ✅ GUI configuration
- ✅ Automatic everything
- ✅ Windows service integration

## Updates

### Pushing Updates

1. Update source code
2. Rebuild installer: `.\build_installer.ps1`
3. Distribute new `ModularTradeAgent_Setup.exe`

### User Update Process

Option A: **Reinstall**
- Run new installer
- Overwrites files
- Keeps configuration

Option B: **Replace Files**
- Copy new files to install directory
- Keep `kotak_neo.env` unchanged

## Security

### Credentials Storage
- `.env` file in install directory
- Plain text (as per original design)
- Protected by Windows file permissions

### Service Security
- Runs under SYSTEM account (default)
- Can be changed to specific user in NSSM config

### Distribution Security
- Consider code signing for professional deployment
- Antivirus may flag unsigned executables

## Advanced

### Code Signing

For professional deployment, sign the installer:

```powershell
# With certificate
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist\ModularTradeAgent_Setup.exe
```

### Silent Installation

Add command-line args to skip GUI:

```cmd
ModularTradeAgent_Setup.exe --silent --key=ABC123 --secret=XYZ789 ...
```

(Requires modification of `installer/setup.py`)

### Auto-Update

Implement update check:
1. Check version from server
2. Download new installer
3. Self-replace and restart

### Multi-Tenancy

Support multiple trading accounts:
- Install multiple instances with different service names
- Each with separate configuration

## Summary

**Best For**:
- ✅ Distribution to non-technical users
- ✅ Corporate/professional deployment
- ✅ Minimal manual intervention required
- ✅ Clean, polished user experience

**File**: `dist\ModularTradeAgent_Setup.exe` (~250-300 MB)

**User Steps**: 
1. Run installer
2. Enter credentials
3. Click Install
4. Done!

**Perfect solution for zero-friction deployment!** 🚀
