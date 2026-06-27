"""
OrderPlacementService Interface - Domain Layer

Abstract interface for placing buy/sell orders, determining AMO vs Regular variety,
checking for active buy orders, checking manual order execution, and syncing status.
"""

from abc import ABC, abstractmethod
from typing import Any


class IOrderPlacementService(ABC):
    """Interface for order placement, tracking, and manual matching."""

    @abstractmethod
    def has_active_buy_order(self, base_symbol: str) -> bool:
        """
        Check if there is an active buy order for the symbol at the broker or in the DB.

        Args:
            base_symbol: The base symbol to check (e.g. RELIANCE)

        Returns:
            True if an active buy order exists, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def get_order_variety_for_market_hours(self) -> str:
        """
        Get the variety of order based on current market hours (e.g. Regular or AMO).

        Returns:
            variety string (e.g. "regular", "amo")
        """
        raise NotImplementedError

    @abstractmethod
    def sync_order_status_snapshot(
        self, order_id: str, symbol: str | None = None, quantity: int | None = None
    ) -> None:
        """
        Sync and return the status of an order from the broker to local tracking.

        Args:
            order_id: Broker order ID
            symbol: Optional symbol
            quantity: Optional quantity
        """
        raise NotImplementedError

    @abstractmethod
    def check_for_manual_orders(
        self, symbol: str, cached_pending_orders: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Check for manually placed buy/sell orders at the broker and reconcile them.

        Args:
            symbol: Symbol variant
            cached_pending_orders: Optional cached pending orders from the broker
        """
        raise NotImplementedError
