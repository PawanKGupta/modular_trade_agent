"""
PositionMonitorService Interface - Domain Layer

Abstract interface for checking position health, determining re-entry levels based on RSI,
and assessing whether re-entries have already occurred today or at a specific level.
"""

from abc import ABC, abstractmethod
from typing import Any


class IPositionMonitorService(ABC):
    """Interface for monitoring positions and determining re-entry thresholds."""

    @abstractmethod
    def determine_reentry_level(
        self, entry_rsi: float, current_rsi: float, position: Any
    ) -> tuple[int | None, dict[str, Any]]:
        """
        Determine next re-entry level based on entry RSI and current RSI.

        Args:
            entry_rsi: RSI10 value at initial entry
            current_rsi: Current RSI10 value
            position: Position object (for tracking reset state)

        Returns:
            Tuple of (next_level, metadata_updates)
        """
        raise NotImplementedError

    @abstractmethod
    def has_reentry_at_level(self, base_symbol: str, level: int, allow_reset: bool = False) -> bool:
        """
        Check if there's a reentry for a given level in the current cycle.

        Args:
            base_symbol: Base ticker symbol
            level: RSI level (e.g. 30, 20, 10)
            allow_reset: Allow resetting if the cycle changes

        Returns:
            True if reentry at level exists, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def has_reentry_at_level_today(self, base_symbol: str, level: int) -> bool:
        """
        Check if a same-day reentry has occurred for a given level.

        Args:
            base_symbol: Base ticker symbol
            level: RSI level (e.g. 30, 20, 10)

        Returns:
            True if same-day reentry at level exists, False otherwise
        """
        raise NotImplementedError
