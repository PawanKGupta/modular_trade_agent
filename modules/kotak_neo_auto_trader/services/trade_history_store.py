"""
File-based TradeHistoryStore.

Encapsulates the JSON trade-history / failed-order persistence (modules/.../storage.py)
behind the ITradeHistoryStore contract. This is a one-way dependency: the store holds only
its history file path and delegates to the storage functions — it has no reference back to
the engine, broker, or DB session.
"""

from __future__ import annotations

from typing import Any

from src.domain.interfaces.trade_history_store import ITradeHistoryStore

from .. import storage


class TradeHistoryStore(ITradeHistoryStore):
    """ITradeHistoryStore backed by the JSON trades-history file."""

    def __init__(self, history_path: str):
        self.history_path = history_path

    def load_history(self) -> dict[str, Any]:
        return storage.load_history(self.history_path)

    def save_history(self, history: dict[str, Any]) -> None:
        storage.save_history(self.history_path, history)

    def append_trade(self, trade: dict[str, Any]) -> None:
        storage.append_trade(self.history_path, trade)

    def get_failed_orders(
        self, include_previous_day_before_market: bool = True
    ) -> list[dict[str, Any]]:
        return storage.get_failed_orders(self.history_path, include_previous_day_before_market)

    def add_failed_order(self, failed_order: dict[str, Any]) -> None:
        storage.add_failed_order(self.history_path, failed_order)

    def remove_failed_order(self, symbol: str) -> None:
        storage.remove_failed_order(self.history_path, symbol)

    def cleanup_expired_failed_orders(self) -> int:
        return storage.cleanup_expired_failed_orders(self.history_path)

    def mark_position_closed(self, symbol: str, exit_price: float, sell_order_id: str) -> bool:
        return storage.mark_position_closed(self.history_path, symbol, exit_price, sell_order_id)
