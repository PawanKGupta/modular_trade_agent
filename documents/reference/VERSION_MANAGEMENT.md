# Version Management Guide

## Overview

The Modular Trade Agent uses **Calendar Versioning (CalVer)** based on quarters, making it easy to identify when a release was made.

## Version Format

```
YY.Q.PATCH
```

Where:
- **YY**: Last 2 digits of year (e.g., 25 = 2025)
- **Q**: Quarter number (1-4)
- **PATCH**: Patch/bugfix number (0, 1, 2, ...)

## Quarter Mapping

| Quarter | Months | Example Version |
|---------|--------|-----------------|
| Q1 | Jan-Mar | 25.1.0, 25.1.1 |
| Q2 | Apr-Jun | 25.2.0, 25.2.1 |
| Q3 | Jul-Sep | 25.3.0, 25.3.1 |
| Q4 | Oct-Dec | 25.4.0, 25.4.1 |

## Version Examples

```
25.4.0  →  Q4 2025 (Oct-Dec), initial quarterly release
25.4.1  →  Q4 2025, patch 1
25.4.2  →  Q4 2025, patch 2
26.1.0  →  Q1 2026 (Jan-Mar), new quarterly release
```

## Current Version

**Version**: `25.4.0`
- **Quarter**: Q4 2025 (October-December)
- **Patch**: 0 (initial release)

## Checking Version

### From Source
```bash
python show_version.py
```

### From Installed System
Check the `VERSION` file in installation directory:
```
C:\ProgramData\ModularTradeAgent\VERSION
```

### Programmatically
```python
from utils.version import get_installed_version, format_version_info

version = get_installed_version()
if version:
    print(format_version_info(version))
    # Output: Version 25.4.0 - Q4 2025 (Oct-Dec)
```

## Version Comparison

The `Version` class supports comparison operators:

```python
from utils.version import Version

v1 = Version("25.4.0")
v2 = Version("25.4.1")
v3 = Version("26.1.0")

print(v1 < v2)  # True (patch update)
print(v2 < v3)  # True (quarter update)
print(v1 == v1) # True
```

## Releasing New Versions

### Patch Release (Bug fixes)

When releasing a bugfix for the current quarter:

1. **Bump patch number**:
   ```bash
   # If current version is 25.4.0
   # New version becomes 25.4.1
   echo "25.4.1" > VERSION
   ```

2. **Update CHANGELOG**:
   ```markdown
   ## [25.4.1] - 2025-10-29
   ### Fixed
   - Fixed sell order retry logic
   - Corrected quantity mismatch handling
   ```

3. **Rebuild installer**:
   ```powershell
.\scripts\build\build_installer.ps1
   ```

4. **Tag release**:
   ```bash
   git tag -a v25.4.1 -m "Patch release: Bug fixes"
   git push origin v25.4.1
   ```

### Quarterly Release (New features)

When releasing at the start of a new quarter:

1. **Generate new version**:
   ```python
   from utils.version import Version
   
   new_version = Version.generate_version()  # Auto-generates YY.Q.0
   print(new_version)  # e.g., 26.1.0 for Q1 2026
   ```

2. **Update VERSION file**:
   ```bash
   echo "26.1.0" > VERSION
   ```

3. **Update CHANGELOG**:
   ```markdown
   ## [26.1.0] - 2026-01-15
   ### Added
   - New feature XYZ
   - Enhanced monitoring
   
   ### Changed
   - Improved performance
   ```

4. **Rebuild and tag**:
   ```powershell
   .\build_installer.ps1
   git tag -a v26.1.0 -m "Q1 2026 release"
   git push origin v26.1.0
   ```

## Installer Behavior

The installer automatically:

1. **Detects installed version**
2. **Compares with installer version**
3. **Shows status**:
   - "New installation" (no previous install)
   - "Upgrading from 25.4.0 to 25.4.1"
   - "Reinstalling same version"
   - "Downgrading from 25.4.1 to 25.4.0" (if needed)

4. **Saves version** to `C:\ProgramData\ModularTradeAgent\VERSION`

## Version in Services

Each service logs its version on startup:

```
[2025-10-28 09:00:00] ModularTradeAgent_Main v25.4.0 starting...
[2025-10-28 09:00:01] Configuration loaded
[2025-10-28 09:00:02] Connected to broker
```

## Update Checking (Future Feature)

The version module includes infrastructure for update checking:

```python
from utils.version import check_for_updates, get_installed_version

current = get_installed_version()
latest = check_for_updates(current, "https://your-server.com/version.json")

if latest:
    print(f"Update available: {current} → {latest}")
```

**Server JSON format**:
```json
{
  "version": "25.4.1",
  "released": "2025-10-29",
  "download_url": "https://...",
  "changelog": "Bug fixes and improvements"
}
```

## Benefits of This Versioning

### Easy to Understand
- ✅ Know immediately when software was released (Q4 2025)
- ✅ Clear distinction between features (quarter) and fixes (patch)

### Professional
- ✅ Follows CalVer standard used by Ubuntu, PyCharm, etc.
- ✅ Predictable release schedule (quarterly)

### Traceable
- ✅ Git tags match version: `v25.4.0`
- ✅ Installer filename: `ModularTradeAgent_Setup_v25.4.0.exe`
- ✅ Logs show version for troubleshooting

## Migration from Old Versions

If you had a version before this system:

1. **Manual migration**:
   ```bash
   # Create VERSION file
   echo "25.4.0" > C:\ProgramData\ModularTradeAgent\VERSION
   ```

2. **Reinstall**:
   - Run new installer
   - It will detect as upgrade

## Version in Build Artifacts

### Installer Filename
Recommended naming:
```
ModularTradeAgent_Setup_v25.4.0.exe
ModularTradeAgent_Setup_v25.4.1.exe
```

### Git Tags
Format: `v{VERSION}`
```bash
git tag -a v25.4.0 -m "Q4 2025 initial release"
git tag -a v25.4.1 -m "Patch: Bug fixes"
```

### GitHub Releases
Title format:
```
v25.4.0 - Q4 2025 Release
v25.4.1 - Bug Fix Patch
```

## Roadmap

Based on version numbers, plan features by quarter:

```
25.4.x (Q4 2025) - Current
  - ✅ Multi-service architecture
  - ✅ Version management
  - ⏳ Health checks
  - ⏳ Auto-update

26.1.x (Q1 2026) - Planned
  - 📋 Advanced analytics dashboard
  - 📋 Multi-account support
  - 📋 Cloud sync

26.2.x (Q2 2026) - Future
  - 📋 Machine learning integration
  - 📋 Mobile app
```

## Summary

- **Current Version**: `25.4.0` (Q4 2025)
- **Format**: `YY.Q.PATCH`
- **Location**: `VERSION` file in project root and installation
- **Tools**: `show_version.py`, `utils/version.py`
- **Tags**: `v25.4.0`, `v25.4.1`, etc.

**Simple, clear, and professional!** 🎯
