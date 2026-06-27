"""
TradeHistoryStore Interface - Domain Layer

Abstract interface for loading, saving, and appending trade history,
plus managing the failed-order retry queue. Implementations encapsulate
the persistence mechanism (e.g. JSON file) so callers depend only on this
contract rather than on concrete storage details.
"""

from abc import ABC, abstractmethod
from typing import Any


class ITradeHistoryStore(ABC):
    """Interface for trade history and failed-order persistence."""

    @abstractmethod
    def load_history(self) -> dict[str, Any]:
        """Load the full trades history dictionary (creating defaults if absent)."""
        raise NotImplementedError

    @abstractmethod
    def save_history(self, history: dict[str, Any]) -> None:
        """Persist the full trades history dictionary."""
        raise NotImplementedError

    @abstractmethod
    def append_trade(self, trade: dict[str, Any]) -> None:
        """Append a single trade record and stamp ``last_run``."""
        raise NotImplementedError

    @abstractmethod
    def get_failed_orders(
        self, include_previous_day_before_market: bool = False
    ) -> list[dict[str, Any]]:
        """
        Return failed orders eligible for retry.

        Args:
            include_previous_day_before_market: When True, apply the date window
                (today always; yesterday only before the 09:15 open; older excluded).
                When False, return all stored failed orders unfiltered.
        """
        raise NotImplementedError

    @abstractmethod
    def add_failed_order(self, failed_order: dict[str, Any]) -> None:
        """Add (or update, de-duplicated by symbol) a failed-order retry entry."""
        raise NotImplementedError

    @abstractmethod
    def remove_failed_order(self, symbol: str) -> None:
        """Remove failed orders matching a specific symbol."""
        raise NotImplementedError

    @abstractmethod
    def cleanup_expired_failed_orders(self) -> int:
        """Remove expired failed orders; return the number removed."""
        raise NotImplementedError

    @abstractmethod
    def mark_position_closed(self, symbol: str, exit_price: float, sell_order_id: str) -> bool:
        """Mark the open trade for ``symbol`` as closed with P&L; return True if updated."""
        raise NotImplementedError
