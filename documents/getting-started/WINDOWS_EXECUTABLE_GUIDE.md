# Windows Executable Build Guide

## Overview
This guide explains how to build a standalone Windows executable (`.exe`) for the Modular Trade Agent that can be distributed and run without requiring Python installation.

## Prerequisites

### On Build Machine (where you build the .exe):
- Python 3.8+ installed
- Virtual environment with all dependencies
- PyInstaller (will be installed automatically by build script)

### On Target Machine (where you run the .exe):
- Windows 10/11
- **NO Python required!** ✅
- Internet connection for API calls

## Building the Executable

### Method 1: Using PowerShell Script (Recommended)

```powershell
# Run the build script
pyinstaller --onefile --name ModularTradeAgent trade_agent.py
```

This will:
1. Check for virtual environment
2. Install PyInstaller if needed
3. Clean previous builds
4. Build the executable
5. Report success/failure with file size

### Method 2: Manual Build

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install PyInstaller
pip install pyinstaller

# Build using spec file
pyinstaller build\build_executable.spec --clean
```

## Build Output

After successful build, you'll find:

```
dist/
  └── ModularTradeAgent.exe    # Standalone executable (~50-100 MB)
```

The executable includes:
- ✅ All Python dependencies
- ✅ All project modules (core, config, utils, etc.)
- ✅ Documentation files
- ❌ Sensitive data (env files, trade history - intentionally excluded)

## Distribution

### Package for Distribution

Create a distribution folder with:

```
ModularTradeAgent/
  ├── ModularTradeAgent.exe
  ├── kotak_neo.env.example    # Template for credentials
  ├── README.md
  └── data/                     # Empty folder for trade history
```

### Transfer to Target Machine

1. **Copy the folder** to target machine
2. **Create `kotak_neo.env`** with actual credentials:
   ```env
   KOTAK_CONSUMER_KEY=your_key
   KOTAK_CONSUMER_SECRET=your_secret
   KOTAK_MOBILE_NUMBER=your_mobile
   KOTAK_PASSWORD=your_password
   KOTAK_MPIN=your_mpin
   ```
3. **Run the executable**:
   ```powershell
   .\ModularTradeAgent.exe
   ```

## Installation as Windows Service (Optional)

To run as a background service:

### Using NSSM (Non-Sucking Service Manager)

1. **Download NSSM**: https://nssm.cc/download
2. **Install service**:
   ```powershell
   nssm install ModularTradeAgent "C:\path\to\ModularTradeAgent.exe"
   ```
3. **Configure service**:
   ```powershell
   nssm set ModularTradeAgent AppDirectory "C:\path\to\ModularTradeAgent"
   nssm set ModularTradeAgent Description "Automated Trading Agent for Kotak Neo"
   nssm set ModularTradeAgent Start SERVICE_AUTO_START
   ```
4. **Start service**:
   ```powershell
   nssm start ModularTradeAgent
   ```

### Using Windows Task Scheduler (Simpler)

1. Open **Task Scheduler**
2. Create new task:
   - **General**: "Run whether user is logged on or not"
   - **Triggers**: At system startup (or scheduled time)
   - **Actions**: Start program → `ModularTradeAgent.exe`
   - **Conditions**: Uncheck "Start only if on AC power"
   - **Settings**: "Run task as soon as possible after scheduled start is missed"

## Customization

### Change Entry Point

Edit `build_executable.spec`:
```python
a = Analysis(
    ['modules/kotak_neo_auto_trader/run_position_monitor.py'],  # Different entry point
    ...
)
```

### Add Icon

1. Get a `.ico` file (e.g., `logo.ico`)
2. Edit `build_executable.spec`:
   ```python
   exe = EXE(
       ...
       icon='logo.ico',  # Add icon path
       ...
   )
   ```

### Reduce File Size

1. **Remove unused libraries** in `excludes`:
   ```python
   excludes=[
       'matplotlib',
       'tkinter',
       'IPython',
       'jupyter',
   ]
   ```

2. **Disable UPX compression** (if causing issues):
   ```python
   upx=False,
   ```

3. **Use --onedir instead of --onefile**:
   - Faster startup
   - Smaller download size with compression
   - Files in folder instead of single .exe

## Troubleshooting

### Build Fails

**Error**: `ModuleNotFoundError: No module named 'X'`
- **Solution**: Add module to `hiddenimports` in spec file

**Error**: `Permission denied`
- **Solution**: Close any running instances of the .exe

### Runtime Issues

**Error**: `Failed to execute script`
- **Solution**: Run from command line to see full error
- **Check**: Ensure `kotak_neo.env` is in same directory as .exe

**Error**: `Cannot find data files`
- **Solution**: Check `datas` section in spec file includes required files

### Large File Size (>200 MB)

- Remove unnecessary dependencies
- Exclude unused libraries in spec file
- Consider using `--onedir` mode

## Performance

| Mode | Size | Startup | Extraction |
|------|------|---------|------------|
| **--onefile** | Smaller download | Slower (extracts temp) | Every run |
| **--onedir** | Larger download | Faster | None |

**Recommendation**: Use `--onefile` for distribution, `--onedir` for development/testing.

## Security Considerations

### DO NOT Include in Executable:
- ❌ API credentials (`kotak_neo.env`)
- ❌ Trade history (`data/trades_history.json`)
- ❌ Secret keys or tokens

### MUST Be Provided Separately:
- ✅ User creates `kotak_neo.env` manually
- ✅ Data directory created on first run
- ✅ Configuration specific to user's account

## Updating the Executable

When you update the code:

1. Pull latest changes from git
2. Run build script again: `.\build.ps1`
3. Distribute new `ModularTradeAgent.exe`
4. **Users keep their env files** - just replace the .exe

## Testing

### Before Distribution:

1. **Test on clean VM** without Python:
   - Ensures no Python dependencies
   - Validates standalone operation

2. **Test with fresh env file**:
   - Ensures all config is externalized

3. **Test scheduled execution**:
   - Ensures works unattended

## Support

For issues with:
- **Building**: Check build.ps1 output and PyInstaller docs
- **Running**: Check logs in console/data directory
- **Configuration**: Verify kotak_neo.env format

## Advanced: Auto-Update System

For automatic updates, consider:
1. Version checking on startup
2. Download new .exe from server
3. Replace old .exe (requires process restart logic)
4. Use NSSM service control for seamless updates

Example version check:
```python
CURRENT_VERSION = "1.0.0"
UPDATE_URL = "https://your-server.com/version.json"

def check_for_updates():
    response = requests.get(UPDATE_URL)
    latest_version = response.json()['version']
    if latest_version > CURRENT_VERSION:
        # Download and replace
        pass
```

## Summary

✅ **Pros**:
- No Python installation required
- Easy distribution
- Professional deployment
- Runs as Windows service

❌ **Cons**:
- Large file size (50-100 MB)
- Slower startup (--onefile mode)
- Antivirus may flag (false positive)

**Best for**: Production deployment, client distribution, scheduled tasks
