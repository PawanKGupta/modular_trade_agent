"""
Session Management
Authentication and session handling for broker connections

Note: Uses existing auth.py from legacy code for now
Future: Can be refactored into auth_handler.py and session_cache_manager.py
"""

# For now, we'll use the existing auth.py from the parent module
# This allows backward compatibility while we migrate
import sys
from pathlib import Path
parent_path = Path(__file__).parent.parent
sys.path.insert(0, str(parent_path))

try:
    from auth import KotakNeoAuth
except ImportError:
    # Fallback for different import contexts
    from ...auth import KotakNeoAuth

__all__ = [
    "KotakNeoAuth",
]
