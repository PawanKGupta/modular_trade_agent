"""
Pytest configuration for scripts unit tests

Sets up the Python path before any test files are imported.
This ensures tests work correctly on all platforms (Windows, Linux, Ubuntu).
"""

import sys
from pathlib import Path

# Add project root to path BEFORE any test imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
