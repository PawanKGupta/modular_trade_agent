"""
Pytest configuration for scripts integration tests

Sets up the Python path and database environment before any test files are imported.
This ensures tests work correctly on all platforms (Windows, Linux, Ubuntu).
"""

import os
import sys
from pathlib import Path

# CRITICAL: Force in-memory database BEFORE any imports that might use DB_URL
# This must happen at the very top of conftest.py, before any module imports
# This prevents the shared session.py engine from connecting to the real database
if "DB_URL" not in os.environ or not os.environ.get("DB_URL", "").startswith("sqlite:///:memory"):
    # Set to in-memory if not already set or not in-memory
    os.environ["DB_URL"] = "sqlite:///:memory:"

# Add project root to path BEFORE any test imports
# Use absolute path to ensure it works correctly in CI
project_root = Path(__file__).resolve().parent.parent.parent.parent
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
