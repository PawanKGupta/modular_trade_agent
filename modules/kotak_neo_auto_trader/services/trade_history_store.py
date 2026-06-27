# ruff: noqa: PLR0912, PLR0915, S110, E501
"""
File-based TradeHistoryStore.

Encapsulates the JSON trade-history / failed-order persistence (modules/.../storage.py)
behind the ITradeHistoryStore contract. This is a one-way dependency: the store holds only
its history file path and delegates to the storage functions — it has no reference back to
the engine, broker, or DB session.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.exc import OperationalError

from src.domain.interfaces.trade_history_store import ITradeHistoryStore
from src.infrastructure.db.timezone_utils import ist_now, ist_now_naive
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository
from utils.logger import logger

try:
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus
except ImportError:
    DbOrderStatus = None

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
        self, include_previous_day_before_market: bool = False
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


class DatabaseTradeHistoryStore(ITradeHistoryStore):
    """ITradeHistoryStore backed by SQLAlchemy database repositories."""

    def __init__(
        self,
        db_session,
        user_id: int,
        orders_repo=None,
        positions_repo=None,
        telegram_notifier=None,
    ):
        self.db_session = db_session
        self.user_id = user_id
        self.telegram_notifier = telegram_notifier

        if orders_repo is None and db_session is not None:
            self.orders_repo = OrdersRepository(db_session)
        else:
            self.orders_repo = orders_repo

        if positions_repo is None and db_session is not None:
            self.positions_repo = PositionsRepository(db_session)
        else:
            self.positions_repo = positions_repo

    def load_history(self) -> dict[str, Any]:
        """Load trades history from repository."""
        if not self.orders_repo or not self.positions_repo:
            return {"trades": [], "failed_orders": [], "last_run": None}

        # Get open positions
        open_positions = self.positions_repo.list(self.user_id)
        open_positions = [p for p in open_positions if p.closed_at is None]

        # Get buy orders for these positions to reconstruct trade metadata
        all_orders, _ = self.orders_repo.list(self.user_id)
        buy_orders = [o for o in all_orders if o.side.lower() == "buy"]

        # Convert positions to trades format
        trades = []
        for pos in open_positions:
            # Find related buy orders for this position
            symbol_orders = [
                o for o in buy_orders if o.symbol.upper().split("-")[0] == pos.symbol.upper()
            ]
            if symbol_orders:
                # Use the first buy order's metadata
                first_order = symbol_orders[0]
                metadata = first_order.order_metadata or {}
            else:
                metadata = {}

            trade = {
                "symbol": pos.symbol,
                "placed_symbol": metadata.get("placed_symbol", pos.symbol),
                "ticker": metadata.get("ticker", f"{pos.symbol}.NS"),
                "entry_price": pos.avg_price,
                "entry_time": (
                    pos.opened_at.isoformat() if pos.opened_at else ist_now().isoformat()
                ),
                "rsi10": metadata.get("rsi10"),
                "ema9": metadata.get("ema9"),
                "ema200": metadata.get("ema200"),
                "capital": metadata.get("capital"),
                "qty": pos.quantity,
                "rsi_entry_level": metadata.get("rsi_entry_level"),
                "levels_taken": metadata.get(
                    "levels_taken", {"30": True, "20": False, "10": False}
                ),
                "reset_ready": metadata.get("reset_ready", False),
                "order_response": metadata.get("order_response"),
                "status": "open",
                "entry_type": metadata.get("entry_type", "system_recommended"),
                "reentries": metadata.get("reentries", []),
            }
            trades.append(trade)

        # Get closed positions (for historical reference)
        closed_positions = [
            p for p in self.positions_repo.list(self.user_id) if p.closed_at is not None
        ]
        for pos in closed_positions:
            # Find related orders
            symbol_orders = [
                o for o in all_orders if o.symbol.upper().split("-")[0] == pos.symbol.upper()
            ]
            if symbol_orders:
                first_order = symbol_orders[0]
                metadata = first_order.order_metadata or {}
            else:
                metadata = {}

            trade = {
                "symbol": pos.symbol,
                "placed_symbol": metadata.get("placed_symbol", pos.symbol),
                "ticker": metadata.get("ticker", f"{pos.symbol}.NS"),
                "entry_price": pos.avg_price,
                "entry_time": (
                    pos.opened_at.isoformat() if pos.opened_at else ist_now().isoformat()
                ),
                "exit_price": metadata.get("exit_price"),
                "exit_time": pos.closed_at.isoformat() if pos.closed_at else None,
                "exit_rsi10": metadata.get("exit_rsi10"),
                "exit_reason": metadata.get("exit_reason"),
                "qty": pos.quantity,
                "status": "closed",
                "entry_type": metadata.get("entry_type", "system_recommended"),
            }
            trades.append(trade)

        # Failed orders: stored in Orders with special metadata flag
        failed_orders = []
        for order in all_orders:
            metadata = order.order_metadata or {}
            if metadata.get("failed_order"):
                failed_orders.append(metadata.get("failed_order_data", {}))

        return {
            "trades": trades,
            "failed_orders": failed_orders,
            "last_run": ist_now().isoformat(),
        }

    def save_history(self, history: dict[str, Any]) -> None:
        """Save history by updating positions directly in database."""
        if self.positions_repo:
            trades = history.get("trades", [])
            for trade in trades:
                self.update_position_from_trade(trade)

    def append_trade(self, trade: dict[str, Any]) -> None:
        """Append trade to database."""
        if self.positions_repo:
            self.update_position_from_trade(trade)

    def get_failed_orders(
        self, include_previous_day_before_market: bool = False
    ) -> list[dict[str, Any]]:
        """Get failed orders from database."""
        if not self.orders_repo:
            return []

        try:
            failed_orders_db = self.orders_repo.get_failed_orders(self.user_id)
            failed_orders = []
            for order in failed_orders_db:
                failed_data = {
                    "symbol": order.symbol,
                    "ticker": getattr(order, "ticker", None),
                    "close": order.price,
                    "qty": order.quantity,
                    "reason": getattr(order, "reason", None) or "unknown",
                    "first_failed_at": (
                        order.first_failed_at.isoformat() if order.first_failed_at else None
                    ),
                    "retry_count": order.retry_count or 0,
                    "status": order.status.value if order.status else "failed",
                }
                failed_orders.append(failed_data)
            return failed_orders
        except Exception as e:
            logger.warning(f"Error getting failed orders from repository: {e}")
            # Fallback: Check status manually
            all_orders, _ = self.orders_repo.list(self.user_id)
            failed_orders = []
            for order in all_orders:
                if DbOrderStatus and order.status == DbOrderStatus.FAILED:
                    failed_data = {
                        "symbol": order.symbol,
                        "ticker": getattr(order, "ticker", None),
                        "close": order.price,
                        "qty": order.quantity,
                        "reason": getattr(order, "reason", None) or "unknown",
                        "first_failed_at": (
                            order.first_failed_at.isoformat() if order.first_failed_at else None
                        ),
                        "retry_count": order.retry_count or 0,
                        "status": order.status.value if order.status else "failed",
                    }
                    failed_orders.append(failed_data)
            return failed_orders

    def add_failed_order(self, failed_order: dict[str, Any]) -> None:
        """Add a failed order to retry queue in database."""
        if not self.orders_repo:
            return

        symbol = failed_order.get("symbol", "")
        if not symbol:
            return

        def normalize_symbol(sym: str) -> str:
            if not sym:
                return ""
            normalized = sym.upper().strip()
            if "-" in normalized:
                normalized = normalized.split("-")[0].strip()
            return normalized

        normalized_symbol = normalize_symbol(symbol)

        existing_orders, _ = self.orders_repo.list(self.user_id)
        existing_failed_orders = [
            o
            for o in existing_orders
            if DbOrderStatus
            and o.status == DbOrderStatus.FAILED
            and normalize_symbol(o.symbol) == normalized_symbol
        ]

        failure_reason = failed_order.get("reason", "unknown")
        is_retryable = failure_reason == "insufficient_balance" and not failed_order.get(
            "non_retryable", False
        )
        retry_pending = is_retryable

        reason_parts = [failure_reason]
        if failed_order.get("shortfall"):
            reason_parts.append(f"shortfall: Rs {failed_order['shortfall']:,.0f}")
        failure_reason_str = " - ".join(reason_parts)

        if existing_failed_orders:
            order = existing_failed_orders[0]
            try:
                retry_count = order.retry_count or 0
                self.orders_repo.mark_failed(
                    order=order,
                    failure_reason=failure_reason_str,
                    retry_pending=retry_pending,
                )
                logger.debug(f"Updated existing failed order for {symbol} (status: FAILED)")
                if self.telegram_notifier and self.telegram_notifier.enabled and retry_pending:
                    try:
                        self.telegram_notifier.notify_retry_queue_updated(
                            symbol=symbol,
                            action="updated",
                            retry_count=retry_count + 1,
                            additional_info={"reason": failure_reason_str},
                            user_id=self.user_id,
                        )
                    except Exception as notify_error:
                        logger.warning(
                            f"Failed to send retry queue update notification: {notify_error}"
                        )
            except Exception as update_error:
                logger.warning(
                    f"Failed to update failed order {symbol}: {update_error}",
                    exc_info=update_error,
                )
                if hasattr(self.orders_repo, "db"):
                    try:
                        self.orders_repo.db.rollback()
                    except Exception:
                        pass
        else:
            try:
                order_metadata = {}
                if failed_order.get("ticker"):
                    order_metadata["ticker"] = failed_order["ticker"]
                if failed_order.get("rsi10") is not None:
                    order_metadata["rsi10"] = failed_order["rsi10"]
                if failed_order.get("ema9") is not None:
                    order_metadata["ema9"] = failed_order["ema9"]
                if failed_order.get("ema200") is not None:
                    order_metadata["ema200"] = failed_order["ema200"]

                new_order = self.orders_repo.create_amo(
                    user_id=self.user_id,
                    symbol=symbol,
                    side="buy",
                    order_type="market",
                    quantity=failed_order.get("qty", 0),
                    price=failed_order.get("close"),
                    order_id=None,
                    broker_order_id=None,
                    order_metadata=order_metadata if order_metadata else None,
                )
            except Exception as create_error:
                if isinstance(create_error, OperationalError) or (
                    hasattr(create_error, "orig")
                    and isinstance(create_error.orig, Exception)
                    and "no column named" in str(create_error).lower()
                ):
                    logger.warning(
                        f"Database schema error when creating failed order for {symbol}: "
                        f"{create_error}. Migration may not have been applied. "
                        "Failed order won't be saved to database.",
                        exc_info=create_error,
                    )
                else:
                    logger.warning(
                        f"Failed to create failed order for {symbol}: {create_error}",
                        exc_info=create_error,
                    )
                if hasattr(self.orders_repo, "db"):
                    try:
                        self.orders_repo.db.rollback()
                    except Exception:
                        pass
                return

            try:
                self.orders_repo.mark_failed(
                    order=new_order,
                    failure_reason=failure_reason_str,
                    retry_pending=retry_pending,
                )
                logger.debug(f"Created new failed order for {symbol} (status: FAILED)")
                if self.telegram_notifier and self.telegram_notifier.enabled and retry_pending:
                    try:
                        self.telegram_notifier.notify_retry_queue_updated(
                            symbol=symbol,
                            action="added",
                            retry_count=0,
                            additional_info={"reason": failure_reason_str},
                            user_id=self.user_id,
                        )
                    except Exception as notify_error:
                        logger.warning(f"Failed to send retry queue notification: {notify_error}")
            except Exception as update_error:
                logger.warning(
                    f"Failed to mark new order as failed {symbol}: {update_error}",
                    exc_info=update_error,
                )
                if hasattr(self.orders_repo, "db"):
                    try:
                        self.orders_repo.db.rollback()
                    except Exception:
                        pass

    def remove_failed_order(self, symbol: str) -> None:
        """Remove a failed order from retry queue in database."""
        if not self.orders_repo:
            return

        all_orders, _ = self.orders_repo.list(self.user_id)
        for order in all_orders:
            if DbOrderStatus and order.status == DbOrderStatus.FAILED:
                order_symbol = order.symbol.upper().strip()
                if "-" in order_symbol:
                    order_symbol = order_symbol.split("-")[0].strip()
                symbol_normalized = symbol.upper().strip()
                if "-" in symbol_normalized:
                    symbol_normalized = symbol_normalized.split("-")[0].strip()

                if order_symbol == symbol_normalized:
                    try:
                        retry_count = order.retry_count or 0
                        self.orders_repo.mark_cancelled(
                            order=order, cancelled_reason="Removed from retry queue"
                        )
                        logger.debug(f"Removed failed order for {symbol} from retry queue")
                        if self.telegram_notifier and self.telegram_notifier.enabled:
                            try:
                                self.telegram_notifier.notify_retry_queue_updated(
                                    symbol=symbol,
                                    action="removed",
                                    retry_count=retry_count,
                                    user_id=self.user_id,
                                )
                            except Exception as notify_error:
                                logger.warning(
                                    f"Failed to send retry queue removal notification: {notify_error}"
                                )
                    except Exception as e:
                        logger.warning(f"Failed to remove failed order {symbol}: {e}")
                    break

    def cleanup_expired_failed_orders(self) -> int:
        """No-op for DB mode (handled via state/schedules)."""
        return 0

    def mark_position_closed(self, symbol: str, exit_price: float, sell_order_id: str) -> bool:
        """Mark position closed in database."""
        if not self.positions_repo:
            return False

        pos = self.positions_repo.get_by_symbol(self.user_id, symbol)
        if pos and pos.closed_at is None:
            sell_order_db_id = None
            if sell_order_id and self.orders_repo:
                try:
                    if isinstance(sell_order_id, int):
                        sell_order_db_id = sell_order_id
                    else:
                        all_orders, _ = self.orders_repo.list(self.user_id)
                        for order in all_orders:
                            if str(getattr(order, "broker_order_id", None) or "") == str(
                                sell_order_id
                            ) or str(getattr(order, "order_id", None) or "") == str(sell_order_id):
                                sell_order_db_id = order.id
                                break
                except Exception as e:
                    logger.debug(f"Could not find sell_order_id {sell_order_id}: {e}")

            try:
                self.positions_repo.mark_closed(
                    user_id=self.user_id,
                    symbol=pos.symbol,
                    closed_at=ist_now(),
                    exit_price=exit_price,
                    exit_reason="SELL_ORDER_EXECUTED",
                    sell_order_id=sell_order_db_id,
                    auto_commit=True,
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark position closed in DB: {e}")
                return False
        return False

    def update_position_from_trade(self, trade: dict[str, Any]) -> None:
        """Update positions directly in DB from a trade representation."""
        if not self.positions_repo or not self.user_id:
            return

        symbol = trade.get("symbol", "").upper()
        status = trade.get("status", "open")
        qty = trade.get("qty", 0)
        entry_price = trade.get("entry_price")

        if not symbol or not entry_price:
            return

        if status == "open":
            try:
                entry_time = datetime.fromisoformat(trade.get("entry_time", ist_now().isoformat()))
            except Exception:
                entry_time = ist_now_naive()

            reentries = trade.get("reentries", [])
            reentry_count = len(reentries) if isinstance(reentries, list) else 0

            initial_entry_price = entry_price
            last_reentry_price = None

            if reentries and isinstance(reentries, list) and len(reentries) > 0:
                last_reentry = reentries[-1]
                if isinstance(last_reentry, dict):
                    last_reentry_price = last_reentry.get("price")

            existing_pos = self.positions_repo.get_by_symbol(self.user_id, symbol)
            if existing_pos and existing_pos.initial_entry_price:
                initial_entry_price = existing_pos.initial_entry_price

            entry_rsi = None
            if trade.get("entry_rsi") is not None:
                entry_rsi = trade.get("entry_rsi")
            elif trade.get("rsi_entry_level") is not None:
                entry_rsi = trade.get("rsi_entry_level")
            elif trade.get("rsi10") is not None:
                entry_rsi = trade.get("rsi10")

            if existing_pos and existing_pos.entry_rsi is not None:
                entry_rsi = None

            self.positions_repo.upsert(
                user_id=self.user_id,
                symbol=symbol,
                quantity=qty,
                avg_price=entry_price,
                opened_at=entry_time,
                reentry_count=reentry_count,
                reentries=reentries if reentries else None,
                initial_entry_price=(initial_entry_price if not existing_pos else None),
                last_reentry_price=last_reentry_price,
                entry_rsi=entry_rsi,
            )
        elif status == "closed":
            pos = self.positions_repo.get_by_symbol(self.user_id, symbol)
            if pos:
                try:
                    exit_time = datetime.fromisoformat(
                        trade.get("exit_time", ist_now().isoformat())
                    )
                except Exception:
                    exit_time = ist_now_naive()

                exit_price = trade.get("exit_price")
                exit_reason = trade.get("exit_reason", "HISTORY_IMPORT")
                exit_rsi = trade.get("exit_rsi10")
                realized_pnl = trade.get("pnl")
                sell_order_id_str = trade.get("sell_order_id")

                sell_order_id = None
                if sell_order_id_str and self.orders_repo:
                    try:
                        if isinstance(sell_order_id_str, int):
                            sell_order_id = sell_order_id_str
                        else:
                            all_orders, _ = self.orders_repo.list(self.user_id)
                            for order in all_orders:
                                if str(getattr(order, "broker_order_id", None) or "") == str(
                                    sell_order_id_str
                                ) or str(getattr(order, "order_id", None) or "") == str(
                                    sell_order_id_str
                                ):
                                    sell_order_id = order.id
                                    break
                    except Exception as e:
                        logger.debug(f"Could not find sell_order_id {sell_order_id_str}: {e}")

                self.positions_repo.mark_closed(
                    user_id=self.user_id,
                    symbol=pos.symbol,
                    closed_at=exit_time,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    exit_rsi=exit_rsi,
                    realized_pnl=realized_pnl,
                    sell_order_id=sell_order_id,
                    auto_commit=True,
                )
