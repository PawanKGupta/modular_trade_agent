#!/usr/bin/env python3
"""
Version Management Module
Handles version tracking, comparison, and update checking

Version Format: YY.Q.PATCH
- YY: Last 2 digits of year (e.g., 25 for 2025)
- Q: Quarter (1-4)
- PATCH: Patch number (0, 1, 2, ...)

Examples:
- 25.4.0 = Q4 2025, initial release
- 25.4.1 = Q4 2025, patch 1
- 26.1.0 = Q1 2026, initial release
"""

import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple


class Version:
    """Version representation and comparison"""
    
    def __init__(self, version_string: str):
        """
        Initialize version from string.
        
        Args:
            version_string: Version in format YY.Q.PATCH (e.g., "25.4.0")
        """
        self.raw = version_string.strip()
        
        # Parse version
        match = re.match(r'^(\d{2})\.([1-4])\.(\d+)$', self.raw)
        if not match:
            raise ValueError(f"Invalid version format: {version_string}. Expected YY.Q.PATCH")
        
        self.year = int(match.group(1))
        self.quarter = int(match.group(2))
        self.patch = int(match.group(3))
    
    def __str__(self) -> str:
        return self.raw
    
    def __repr__(self) -> str:
        return f"Version('{self.raw}')"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Version):
            return False
        return (self.year, self.quarter, self.patch) == (other.year, other.quarter, other.patch)
    
    def __lt__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.year, self.quarter, self.patch) < (other.year, other.quarter, other.patch)
    
    def __le__(self, other) -> bool:
        return self == other or self < other
    
    def __gt__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.year, self.quarter, self.patch) > (other.year, other.quarter, other.patch)
    
    def __ge__(self, other) -> bool:
        return self == other or self > other
    
    @staticmethod
    def current_quarter() -> int:
        """Get current quarter (1-4) based on current date"""
        month = datetime.now().month
        return (month - 1) // 3 + 1
    
    @staticmethod
    def generate_version(patch: int = 0) -> 'Version':
        """
        Generate version for current quarter.
        
        Args:
            patch: Patch number (default: 0 for new release)
        
        Returns:
            Version object for current quarter
        """
        year = datetime.now().year % 100  # Last 2 digits
        quarter = Version.current_quarter()
        return Version(f"{year}.{quarter}.{patch}")
    
    def is_same_release(self, other: 'Version') -> bool:
        """Check if two versions are from same quarterly release (ignore patch)"""
        return self.year == other.year and self.quarter == other.quarter
    
    def bump_patch(self) -> 'Version':
        """Create new version with incremented patch number"""
        return Version(f"{self.year}.{self.quarter}.{self.patch + 1}")


def get_installed_version(install_dir: Path = None) -> Optional[Version]:
    """
    Get currently installed version from VERSION file.
    
    Args:
        install_dir: Installation directory (default: C:/ProgramData/ModularTradeAgent)
    
    Returns:
        Version object or None if not found
    """
    if install_dir is None:
        install_dir = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'ModularTradeAgent'
    
    version_file = install_dir / 'VERSION'
    
    try:
        if version_file.exists():
            version_string = version_file.read_text().strip()
            return Version(version_string)
    except Exception:
        pass
    
    return None


def get_package_version() -> Optional[Version]:
    """
    Get version of current package/installer.
    
    Returns:
        Version object or None if not found
    """
    # Try to find VERSION file relative to this module
    version_file = Path(__file__).parent.parent / 'VERSION'
    
    try:
        if version_file.exists():
            version_string = version_file.read_text().strip()
            return Version(version_string)
    except Exception:
        pass
    
    return None


def save_version(version: Version, install_dir: Path = None) -> bool:
    """
    Save version to installation directory.
    
    Args:
        version: Version to save
        install_dir: Installation directory
    
    Returns:
        True if successful
    """
    if install_dir is None:
        install_dir = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'ModularTradeAgent'
    
    version_file = install_dir / 'VERSION'
    
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        version_file.write_text(str(version))
        return True
    except Exception as e:
        print(f"Failed to save version: {e}")
        return False


def check_for_updates(current_version: Version, update_url: str = None) -> Optional[Version]:
    """
    Check if newer version is available.
    
    Args:
        current_version: Currently installed version
        update_url: URL to check for updates (optional)
    
    Returns:
        Latest version if update available, None otherwise
    """
    if update_url is None:
        # No update server configured
        return None
    
    try:
        import requests
        response = requests.get(update_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest_version = Version(data['version'])
            
            if latest_version > current_version:
                return latest_version
    except Exception:
        pass
    
    return None


def format_version_info(version: Version) -> str:
    """
    Format version information for display.
    
    Args:
        version: Version to format
    
    Returns:
        Formatted string
    """
    year = 2000 + version.year
    quarter_names = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    quarter_months = {
        1: "Jan-Mar",
        2: "Apr-Jun", 
        3: "Jul-Sep",
        4: "Oct-Dec"
    }
    
    quarter_name = quarter_names[version.quarter]
    months = quarter_months[version.quarter]
    
    info = f"Version {version} - {quarter_name} {year} ({months})"
    if version.patch > 0:
        info += f" - Patch {version.patch}"
    
    return info


# Example usage and tests
if __name__ == "__main__":
    # Test version parsing
    v1 = Version("25.4.0")
    print(f"Version: {v1}")
    print(f"Year: 20{v1.year}, Quarter: {v1.quarter}, Patch: {v1.patch}")
    print()
    
    # Test version comparison
    v2 = Version("25.4.1")
    v3 = Version("26.1.0")
    
    print(f"{v1} < {v2}: {v1 < v2}")  # True
    print(f"{v2} < {v3}: {v2 < v3}")  # True
    print(f"{v1} == {v1}: {v1 == v1}")  # True
    print()
    
    # Test current version generation
    current = Version.generate_version()
    print(f"Current quarter version: {current}")
    print(f"Formatted: {format_version_info(current)}")
    print()
    
    # Test patch bump
    patched = current.bump_patch()
    print(f"Patched version: {patched}")
    print(f"Formatted: {format_version_info(patched)}")
    print()
    
    # Test same release check
    print(f"{current} is same release as {patched}: {current.is_same_release(patched)}")
