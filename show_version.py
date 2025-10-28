#!/usr/bin/env python3
"""
Show version information for Modular Trade Agent
"""

from utils.version import get_package_version, get_installed_version, format_version_info
from pathlib import Path
import os

def main():
    print("="*60)
    print("MODULAR TRADE AGENT - VERSION INFORMATION")
    print("="*60)
    print()
    
    # Package version (from source)
    package_version = get_package_version()
    if package_version:
        print("Package Version (Source):")
        print(f"  {format_version_info(package_version)}")
        print()
    
    # Installed version
    install_dir = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'ModularTradeAgent'
    installed_version = get_installed_version(install_dir)
    
    if installed_version:
        print("Installed Version:")
        print(f"  {format_version_info(installed_version)}")
        print(f"  Location: {install_dir}")
        print()
    else:
        print("No installation found")
        print(f"  Checked: {install_dir}")
        print()
    
    # Version format explanation
    print("Version Format: YY.Q.PATCH")
    print("  YY    = Last 2 digits of year")
    print("  Q     = Quarter (1-4)")
    print("  PATCH = Patch number")
    print()
    print("Examples:")
    print("  25.4.0 = Q4 2025 (Oct-Dec), initial release")
    print("  25.4.1 = Q4 2025, patch 1")
    print("  26.1.0 = Q1 2026 (Jan-Mar), new release")
    print()


if __name__ == "__main__":
    main()
