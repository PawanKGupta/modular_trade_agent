"""
Position Loader Service

Centralized service for loading open positions from trade history.
Eliminates duplicate code for position loading across services.

Phase 2.2: Portfolio & Position Services
"""

import os
import sys
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger  # noqa: E402

try:
    from ..storage import load_history
except ImportError:
    from modules.kotak_neo_auto_trader.storage import load_history


class PositionCache:
    """In-memory cache for loaded positions with file change detection"""

    def __init__(self):
        """Initialize position cache"""
        self._cache: dict[str, tuple[Any, float]] = {}  # path -> (data, file_mtime)
        self._lock = Lock()

    def get(self, path: str) -> tuple[Any, bool] | None:
        """
        Get cached positions if file hasn't changed

        Args:
            path: Path to history file

        Returns:
            Tuple of (cached_data, is_valid) or None if not cached
        """
        with self._lock:
            if path not in self._cache:
                return None

            cached_data, cached_mtime = self._cache[path]

            # Check if file has been modified
            try:
                if os.path.exists(path):
                    current_mtime = os.path.getmtime(path)
                    if current_mtime == cached_mtime:
                        return (cached_data, True)
                    # File changed, invalidate cache
                    del self._cache[path]
                    return None
                # File doesn't exist, invalidate cache
                del self._cache[path]
                return None
            except OSError:
                # Error accessing file, invalidate cache
                if path in self._cache:
                    del self._cache[path]
                return None

    def set(self, path: str, data: Any) -> None:
        """
        Cache positions with current file modification time

        Args:
            path: Path to history file
            data: Data to cache
        """
        with self._lock:
            try:
                if os.path.exists(path):
                    mtime = os.path.getmtime(path)
                    self._cache[path] = (data, mtime)
            except OSError:
                # Can't get mtime, don't cache
                pass

    def clear(self) -> None:
        """Clear all cached positions"""
        with self._lock:
            self._cache.clear()

    def invalidate(self, path: str) -> None:
        """Invalidate cache for specific file"""
        with self._lock:
            if path in self._cache:
                del self._cache[path]


# Singleton instance
_position_loader_instance: "PositionLoader | None" = None


def get_position_loader(
    history_path: str | None = None,
    enable_caching: bool = True,
) -> "PositionLoader":
    """
    Get or create PositionLoader singleton instance

    Args:
        history_path: Path to trade history file (optional, can be set later)
        enable_caching: Enable caching (default: True)

    Returns:
        PositionLoader instance
    """
    global _position_loader_instance  # noqa: PLW0603

    if _position_loader_instance is None:
        _position_loader_instance = PositionLoader(
            history_path=history_path, enable_caching=enable_caching
        )

    # Update history_path if provided
    if history_path is not None:
        _position_loader_instance.history_path = history_path

    return _position_loader_instance


class PositionLoader:
    """
    Centralized service for loading open positions from trade history

    Provides unified interface for:
    - Loading open positions as list
    - Loading open positions grouped by symbol
    - Caching with file change detection
    """

    def __init__(
        self,
        history_path: str | None = None,
        enable_caching: bool = True,
    ):
        """
        Initialize PositionLoader

        Args:
            history_path: Path to trade history file
            enable_caching: Enable caching (default: True)
        """
        self.history_path = history_path
        self.enable_caching = enable_caching
        self._cache = PositionCache() if enable_caching else None

    def load_open_positions(self, history_path: str | None = None) -> list[dict[str, Any]]:
        """
        Load all open positions from trade history as a list

        Replaces: SellOrderManager.get_open_positions()

        Args:
            history_path: Path to history file (uses self.history_path if None)

        Returns:
            List of open trade entries
        """
        path = history_path or self.history_path
        if not path:
            logger.warning("No history path provided for loading positions")
            return []

        # Check cache first
        if self.enable_caching and self._cache:
            cached_result = self._cache.get(path)
            if cached_result is not None:
                cached_data, is_valid = cached_result
                if is_valid:
                    return cached_data

        try:
            history = load_history(path)
            trades = history.get("trades", [])

            # Filter for open positions
            open_trades = [t for t in trades if t.get("status") == "open"]

            logger.debug(f"Loaded {len(open_trades)} open positions from {path}")

            # Cache the result
            if self.enable_caching and self._cache:
                self._cache.set(path, open_trades)

            return open_trades

        except Exception as e:
            logger.error(f"Error loading open positions from {path}: {e}")
            return []

    def get_positions_by_symbol(
        self, history_path: str | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Load all open positions grouped by symbol

        Replaces: PositionMonitor._get_open_positions()

        Args:
            history_path: Path to history file (uses self.history_path if None)

        Returns:
            Dictionary mapping symbol to list of trade entries
        """
        path = history_path or self.history_path
        if not path:
            logger.warning("No history path provided for loading positions")
            return {}

        # Check cache first (using list format, then convert)
        cache_key = f"{path}_grouped"
        if self.enable_caching and self._cache:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                cached_data, is_valid = cached_result
                if is_valid:
                    return cached_data

        try:
            # Load open positions as list
            open_trades = self.load_open_positions(path)

            # Group by symbol
            open_positions = defaultdict(list)
            for trade in open_trades:
                symbol = trade.get("symbol")
                if symbol:
                    open_positions[symbol].append(trade)

            result = dict(open_positions)

            logger.debug(
                f"Loaded {len(open_trades)} open positions grouped into {len(result)} symbols"
            )

            # Cache the grouped result
            if self.enable_caching and self._cache:
                self._cache.set(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"Error loading positions by symbol from {path}: {e}")
            return {}

    def clear_cache(self) -> None:
        """Clear all cached positions"""
        if self._cache:
            self._cache.clear()

    def invalidate_cache(self, history_path: str | None = None) -> None:
        """
        Invalidate cache for specific history file

        Args:
            history_path: Path to history file (uses self.history_path if None)
        """
        if self._cache:
            path = history_path or self.history_path
            if path:
                self._cache.invalidate(path)
                self._cache.invalidate(f"{path}_grouped")
