# ruff: noqa: PLR0912, PLR0913, PLC0415, PLR2004
"""
Concrete implementation of OrderPlacementService.
"""

from typing import Any

from src.domain.interfaces.order_placement_service import IOrderPlacementService
from utils.logger import logger

try:
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus
except ImportError:
    DbOrderStatus = None


class OrderPlacementService(IOrderPlacementService):
    """Concrete implementation of IOrderPlacementService."""

    def __init__(
        self,
        orders=None,
        auth=None,
        scrip_master=None,
        strategy_config=None,
        orders_repo=None,
        user_id=None,
        telegram_notifier=None,
        db_session=None,
    ):
        self.orders = orders
        self.auth = auth
        self.scrip_master = scrip_master
        self.strategy_config = strategy_config
        self.orders_repo = orders_repo
        self.user_id = user_id
        self.telegram_notifier = telegram_notifier
        self.db = db_session

    @staticmethod
    def _symbol_variants(base: str) -> list[str]:
        base = base.upper()
        return [base, f"{base}-EQ", f"{base}-BE", f"{base}-BL", f"{base}-BZ"]

    def has_active_buy_order(self, base_symbol: str) -> bool:
        variants = set(self._symbol_variants(base_symbol))

        # 1) Check broker API first (primary source)
        if self.orders:
            try:
                pend = self.orders.get_pending_orders() or []
                for o in pend:
                    txn = str(o.get("transactionType") or "").upper()
                    sym = str(o.get("tradingSymbol") or "").upper()
                    if txn.startswith("B") and sym in variants:
                        return True
            except Exception as e:
                logger.warning(
                    f"Broker API check for active buy order failed for {base_symbol}: {e}. "
                    "Falling back to database check."
                )

        # 2) Database fallback
        if self.orders_repo and self.user_id:
            try:
                existing_orders, _ = self.orders_repo.list(self.user_id)
                for existing_order in existing_orders:
                    order_symbol_base = (
                        existing_order.symbol.upper()
                        .replace("-EQ", "")
                        .replace("-BE", "")
                        .replace("-BL", "")
                        .replace("-BZ", "")
                    )
                    base_symbol_clean = (
                        base_symbol.upper()
                        .replace("-EQ", "")
                        .replace("-BE", "")
                        .replace("-BL", "")
                        .replace("-BZ", "")
                    )

                    if (
                        existing_order.side == "buy"
                        and existing_order.status
                        in {
                            DbOrderStatus.PENDING,
                            DbOrderStatus.ONGOING,
                            DbOrderStatus.CLOSED,
                        }
                        and order_symbol_base == base_symbol_clean
                    ):
                        if existing_order.execution_qty is None:
                            logger.debug(
                                f"Database check: {base_symbol} already has unfilled buy order "
                                f"(status: {existing_order.status}, order_id: {existing_order.id})"
                            )
                            return True
                        else:
                            logger.debug(
                                f"Database check: {base_symbol} has filled buy order "
                                f"(execution_qty={existing_order.execution_qty}), "
                                "not blocking re-entry "
                                f"(status: {existing_order.status}, order_id: {existing_order.id})"
                            )
            except Exception as e:
                logger.warning(f"Database check for active buy order failed for {base_symbol}: {e}")

        return False

    def get_order_variety_for_market_hours(self) -> str:
        from core.volume_analysis import is_market_hours

        if is_market_hours():
            return "REGULAR"
        else:
            try:
                from .. import config

                default_variety = config.DEFAULT_VARIETY
            except ImportError:
                default_variety = "AMO"

            return self.strategy_config.default_variety if self.strategy_config else default_variety

    def sync_order_status_snapshot(
        self, order_id: str, symbol: str | None = None, quantity: int | None = None
    ) -> None:
        if not (self.orders and self.orders_repo and self.user_id):
            return

        try:
            from modules.kotak_neo_auto_trader.utils.order_field_extractor import (
                OrderFieldExtractor,
            )

            orders_response = self.orders.get_orders() or {}
            broker_orders = (
                orders_response.get("data", []) if isinstance(orders_response, dict) else []
            )
            target = None
            for broker_order in broker_orders:
                if OrderFieldExtractor.get_order_id(broker_order) == str(order_id):
                    target = broker_order
                    break

            if not target:
                return

            db_order = self.orders_repo.get_by_broker_order_id(
                self.user_id, str(order_id)
            ) or self.orders_repo.get_by_order_id(self.user_id, str(order_id))
            if not db_order:
                return

            status = OrderFieldExtractor.get_status(target)
            status_lower = status.lower()
            if not status_lower:
                return

            self.orders_repo.update_status_check(db_order)

            if status_lower in {"rejected", "reject"}:
                rejection_reason = (
                    OrderFieldExtractor.get_rejection_reason(target) or "Rejected by broker"
                )
                self.orders_repo.mark_rejected(db_order, rejection_reason)
            elif status_lower in {"cancelled", "cancel"}:
                cancelled_reason = OrderFieldExtractor.get_rejection_reason(target) or "Cancelled"
                self.orders_repo.mark_cancelled(db_order, cancelled_reason)
            elif status_lower in {"executed", "filled", "complete"}:
                execution_price = OrderFieldExtractor.get_price(target)
                execution_qty = (
                    OrderFieldExtractor.get_quantity(target) or quantity or db_order.quantity
                )
                from src.infrastructure.db.timezone_utils import ist_now_naive

                placed_at = getattr(db_order, "placed_at", None)
                if placed_at is not None:
                    placed_naive = (
                        placed_at.replace(tzinfo=None)
                        if getattr(placed_at, "tzinfo", None) is not None
                        else placed_at
                    )
                    age_s = (ist_now_naive() - placed_naive).total_seconds()
                    if age_s < 120:
                        logger.debug(
                            f"Deferring immediate execute sync for {order_id} "
                            f"({age_s:.0f}s after placement) to order monitor"
                        )
                        return
                if execution_price and execution_qty and execution_price > 0 and execution_qty > 0:
                    self.orders_repo.mark_executed(
                        order=db_order,
                        execution_price=execution_price,
                        execution_qty=execution_qty,
                    )
            elif status_lower in {
                "pending",
                "open",
                "trigger_pending",
                "partially_filled",
                "partially filled",
            }:
                if db_order.status != DbOrderStatus.PENDING:
                    self.orders_repo.update(db_order, status=DbOrderStatus.PENDING)

        except Exception as e:
            logger.debug(
                f"Immediate order status sync failed for {symbol or order_id}: {e}",
                exc_info=False,
            )

    def check_for_manual_orders(
        self, symbol: str, cached_pending_orders: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        result = {
            "has_manual_order": False,
            "has_system_order": False,
            "manual_orders": [],
            "system_orders": [],
        }

        if not self.orders or not self.orders_repo or not self.user_id:
            return result

        try:
            if cached_pending_orders is not None:
                pending_orders = cached_pending_orders
            else:
                pending_orders = self.orders.get_pending_orders() or []
            variants = set(self._symbol_variants(symbol))

            from modules.kotak_neo_auto_trader.utils.order_field_extractor import (
                OrderFieldExtractor,
            )

            for order in pending_orders:
                order_symbol = OrderFieldExtractor.get_symbol(order).upper()
                transaction_type = OrderFieldExtractor.get_transaction_type(order)

                if not transaction_type.startswith("B"):
                    continue

                if order_symbol not in variants:
                    continue

                order_id = OrderFieldExtractor.get_order_id(order)
                if not order_id:
                    continue

                quantity = OrderFieldExtractor.get_quantity(order)
                price = OrderFieldExtractor.get_price(order)

                order_info = {
                    "order_id": order_id,
                    "symbol": order_symbol,
                    "quantity": quantity,
                    "price": price,
                    "broker_order": order,
                }

                db_order = self.orders_repo.get_by_broker_order_id(self.user_id, order_id)

                if db_order:
                    result["has_system_order"] = True
                    result["system_orders"].append(order_info)
                else:
                    result["has_manual_order"] = True
                    result["manual_orders"].append(order_info)

        except Exception as e:
            logger.warning(f"check_for_manual_orders failed for {symbol}: {e}")

        return result
