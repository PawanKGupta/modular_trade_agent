"""
Pytest configuration for services unit tests

Sets up the Python path before any test files are imported.
"""

import sys
from pathlib import Path

# Add project root to path BEFORE any test imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
