#!/usr/bin/env python3
"""
Unified Order Monitor
Monitors both buy (AMO) and sell orders during market hours.

Phase 2: Unified order monitoring implementation.
Extends SellOrderManager to handle buy order monitoring alongside sell orders.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from utils.logger import logger

try:
    from .sell_engine import SellOrderManager
    from .orders import KotakNeoOrders
    from .order_state_manager import OrderStateManager
    from .utils.order_field_extractor import OrderFieldExtractor
    from .utils.symbol_utils import extract_base_symbol
except ImportError:
    from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
    from modules.kotak_neo_auto_trader.order_state_manager import OrderStateManager
    from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
    from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

# Try to import database dependencies
try:
    from sqlalchemy.orm import Session
    from src.infrastructure.persistence.orders_repository import OrdersRepository
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database dependencies not available. Buy order monitoring will be limited.")


class UnifiedOrderMonitor:
    """
    Unified order monitor that handles both buy (AMO) and sell orders.

    Extends SellOrderManager functionality to monitor:
    - Sell orders (existing functionality)
    - AMO buy orders (new functionality)
    """

    def __init__(
        self,
        sell_order_manager: SellOrderManager,
        db_session: Optional[Session] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize unified order monitor.

        Args:
            sell_order_manager: Existing SellOrderManager instance
            db_session: Optional database session for buy order tracking
            user_id: Optional user ID for filtering orders
        """
        self.sell_manager = sell_order_manager
        self.orders = sell_order_manager.orders
        self.db_session = db_session
        self.user_id = user_id

        # Track active buy orders {order_id: {'symbol': str, 'quantity': float, 'order_id': str, ...}}
        self.active_buy_orders: Dict[str, Dict[str, Any]] = {}

        # Initialize orders repository if DB is available
        self.orders_repo = None
        if DB_AVAILABLE and db_session:
            try:
                self.orders_repo = OrdersRepository(db_session)
                logger.info("OrdersRepository initialized for buy order monitoring")
            except Exception as e:
                logger.warning(f"Failed to initialize OrdersRepository: {e}")
                self.orders_repo = None

        logger.info("UnifiedOrderMonitor initialized")

    def load_pending_buy_orders(self) -> int:
        """
        Load pending AMO buy orders from database.

        Returns:
            Number of buy orders loaded
        """
        if not self.orders_repo or not self.user_id:
            logger.debug("Cannot load buy orders: DB not available or user_id not set")
            return 0

        try:
            # Get pending AMO orders
            pending_orders = self.orders_repo.get_pending_amo_orders(self.user_id)

            loaded_count = 0
            for order in pending_orders:
                order_id = order.broker_order_id or order.order_id
                if not order_id:
                    logger.warning(f"Order {order.id} has no broker_order_id, skipping")
                    continue

                # Add to active tracking
                self.active_buy_orders[str(order_id)] = {
                    "symbol": order.symbol,
                    "quantity": order.quantity,
                    "order_id": str(order_id),
                    "db_order_id": order.id,
                    "status": order.status.value if order.status else "amo",
                    "placed_at": order.placed_at,
                }
                loaded_count += 1

            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count} pending AMO buy orders from database")
            else:
                logger.debug("No pending AMO buy orders found in database")

            return loaded_count

        except Exception as e:
            logger.error(f"Error loading pending buy orders: {e}")
            return 0

    def register_buy_orders_with_state_manager(self) -> int:
        """
        Register loaded buy orders with OrderStateManager.

        Phase 4: Integration with OrderStateManager for unified state tracking.

        Returns:
            Number of buy orders registered
        """
        if not self.sell_manager or not hasattr(self.sell_manager, "state_manager"):
            logger.debug("OrderStateManager not available, skipping registration")
            return 0

        state_manager = self.sell_manager.state_manager
        if not state_manager:
            logger.debug("OrderStateManager is None, skipping registration")
            return 0

        registered_count = 0
        for order_id, order_info in self.active_buy_orders.items():
            try:
                result = state_manager.register_buy_order(
                    symbol=order_info.get("symbol", ""),
                    order_id=order_id,
                    quantity=order_info.get("quantity", 0),
                    price=order_info.get("price"),  # May be None for market orders
                    ticker=order_info.get("ticker"),
                )
                if result:
                    registered_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to register buy order {order_id} with state manager: {e}"
                )

        if registered_count > 0:
            logger.info(
                f"Registered {registered_count}/{len(self.active_buy_orders)} "
                "buy orders with OrderStateManager"
            )

        return registered_count

    def check_buy_order_status(self, broker_orders: Optional[List[Dict[str, Any]]] = None) -> Dict[str, int]:
        """
        Check status of active buy orders from broker.

        Args:
            broker_orders: Optional pre-fetched broker orders list

        Returns:
            Dict with statistics: {'checked': int, 'executed': int, 'rejected': int, 'cancelled': int}
        """
        stats = {"checked": 0, "executed": 0, "rejected": 0, "cancelled": 0}

        if not self.active_buy_orders:
            logger.debug("No active buy orders to check")
            return stats

        try:
            # Fetch broker orders if not provided
            if broker_orders is None:
                orders_response = self.orders.get_orders() if self.orders else None
                broker_orders = orders_response.get("data", []) if orders_response else []

            # Check each active buy order
            order_ids_to_remove = []

            for order_id, order_info in list(self.active_buy_orders.items()):
                stats["checked"] += 1

                # Find order in broker orders
                broker_order = None
                for bo in broker_orders:
                    broker_order_id = OrderFieldExtractor.get_order_id(bo)
                    if broker_order_id == order_id:
                        broker_order = bo
                        break

                if broker_order:
                    # Extract status
                    status = OrderFieldExtractor.get_status(broker_order)
                    status_lower = status.lower() if status else ""

                    # Update order status in database
                    if self.orders_repo and order_info.get("db_order_id"):
                        try:
                            db_order = self.orders_repo.get(order_info["db_order_id"])
                            if db_order:
                                self._update_buy_order_status(db_order, broker_order, status_lower)
                        except Exception as e:
                            logger.error(f"Error updating buy order {order_id} in DB: {e}")

                    # Handle different statuses
                    if status_lower in ["executed", "filled", "complete"]:
                        stats["executed"] += 1
                        self._handle_buy_order_execution(order_id, order_info, broker_order)
                        order_ids_to_remove.append(order_id)
                    elif status_lower in ["rejected", "reject"]:
                        stats["rejected"] += 1
                        self._handle_buy_order_rejection(order_id, order_info, broker_order)
                        order_ids_to_remove.append(order_id)
                    elif status_lower in ["cancelled", "cancel"]:
                        stats["cancelled"] += 1
                        self._handle_buy_order_cancellation(order_id, order_info, broker_order)
                        order_ids_to_remove.append(order_id)
                else:
                    # Order not found in broker - might be executed or cancelled
                    # Check if it's been a while since placement (could be executed)
                    placed_at = order_info.get("placed_at")
                    if placed_at:
                        # If order was placed more than 1 hour ago and not found, assume executed
                        # (This is a heuristic - in production, we'd check executed orders API)
                        logger.debug(f"Buy order {order_id} not found in broker orders")

            # Remove processed orders from tracking
            for order_id in order_ids_to_remove:
                if order_id in self.active_buy_orders:
                    del self.active_buy_orders[order_id]

            if stats["checked"] > 0:
                logger.debug(
                    f"Buy order status check: {stats['checked']} checked, "
                    f"{stats['executed']} executed, {stats['rejected']} rejected, "
                    f"{stats['cancelled']} cancelled"
                )

        except Exception as e:
            logger.error(f"Error checking buy order status: {e}")

        return stats

    def _update_buy_order_status(
        self, db_order: Any, broker_order: Dict[str, Any], status: str
    ) -> None:
        """
        Update buy order status in database based on broker response.

        Args:
            db_order: Database order object
            broker_order: Broker order dict
            status: Order status from broker
        """
        if not self.orders_repo:
            return

        try:
            # Update last status check
            self.orders_repo.update_status_check(db_order)

            # Map broker status to our status
            if status in ["executed", "filled", "complete"]:
                execution_price = OrderFieldExtractor.get_price(broker_order)
                execution_qty = OrderFieldExtractor.get_quantity(broker_order)
                self.orders_repo.mark_executed(
                    db_order,
                    execution_price=execution_price,
                    execution_qty=execution_qty or db_order.quantity,
                )
            elif status in ["rejected", "reject"]:
                rejection_reason = OrderFieldExtractor.get_rejection_reason(broker_order)
                self.orders_repo.mark_rejected(db_order, rejection_reason or "Rejected by broker")
            elif status in ["cancelled", "cancel"]:
                cancelled_reason = OrderFieldExtractor.get_rejection_reason(broker_order)
                self.orders_repo.mark_cancelled(db_order, cancelled_reason or "Cancelled")

        except Exception as e:
            logger.error(f"Error updating buy order status in DB: {e}")

    def _handle_buy_order_execution(
        self, order_id: str, order_info: Dict[str, Any], broker_order: Dict[str, Any]
    ) -> None:
        """
        Handle executed buy order.

        Phase 4: Integrates with OrderStateManager for unified state tracking.

        Args:
            order_id: Order ID
            order_info: Order tracking info
            broker_order: Broker order dict
        """
        symbol = order_info.get("symbol", "")
        execution_price = OrderFieldExtractor.get_price(broker_order)
        execution_qty = OrderFieldExtractor.get_quantity(broker_order) or order_info.get("quantity", 0)

        logger.info(
            f"Buy order executed: {symbol} - Order ID {order_id}, "
            f"Price: Rs {execution_price:.2f}, Qty: {execution_qty}"
        )

        # Phase 4: Update OrderStateManager if available
        if (
            self.sell_manager
            and hasattr(self.sell_manager, "state_manager")
            and self.sell_manager.state_manager
        ):
            try:
                self.sell_manager.state_manager.mark_buy_order_executed(
                    symbol=symbol,
                    order_id=order_id,
                    execution_price=execution_price,
                    execution_qty=execution_qty,
                )
            except Exception as e:
                logger.warning(f"Failed to update OrderStateManager for executed buy order: {e}")

        # Update in database (already done in _update_buy_order_status)

    def _handle_buy_order_rejection(
        self, order_id: str, order_info: Dict[str, Any], broker_order: Dict[str, Any]
    ) -> None:
        """
        Handle rejected buy order.

        Phase 4: Integrates with OrderStateManager for unified state tracking.

        Args:
            order_id: Order ID
            order_info: Order tracking info
            broker_order: Broker order dict
        """
        symbol = order_info.get("symbol", "")
        rejection_reason = OrderFieldExtractor.get_rejection_reason(broker_order)

        logger.warning(
            f"Buy order rejected: {symbol} - Order ID {order_id}, "
            f"Reason: {rejection_reason or 'Unknown'}"
        )

        # Phase 4: Update OrderStateManager if available
        if (
            self.sell_manager
            and hasattr(self.sell_manager, "state_manager")
            and self.sell_manager.state_manager
        ):
            try:
                self.sell_manager.state_manager.remove_buy_order_from_tracking(
                    order_id=order_id, reason=f"Rejected: {rejection_reason or 'Unknown'}"
                )
            except Exception as e:
                logger.warning(f"Failed to update OrderStateManager for rejected buy order: {e}")

        # Status already updated in database via _update_buy_order_status

    def _handle_buy_order_cancellation(
        self, order_id: str, order_info: Dict[str, Any], broker_order: Dict[str, Any]
    ) -> None:
        """
        Handle cancelled buy order.

        Phase 4: Integrates with OrderStateManager for unified state tracking.

        Args:
            order_id: Order ID
            order_info: Order tracking info
            broker_order: Broker order dict
        """
        symbol = order_info.get("symbol", "")
        cancelled_reason = OrderFieldExtractor.get_rejection_reason(broker_order)

        logger.info(
            f"Buy order cancelled: {symbol} - Order ID {order_id}, "
            f"Reason: {cancelled_reason or 'Unknown'}"
        )

        # Phase 4: Update OrderStateManager if available
        if (
            self.sell_manager
            and hasattr(self.sell_manager, "state_manager")
            and self.sell_manager.state_manager
        ):
            try:
                self.sell_manager.state_manager.remove_buy_order_from_tracking(
                    order_id=order_id, reason=f"Cancelled: {cancelled_reason or 'Unknown'}"
                )
            except Exception as e:
                logger.warning(f"Failed to update OrderStateManager for cancelled buy order: {e}")

        # Status already updated in database via _update_buy_order_status

    def monitor_all_orders(self) -> Dict[str, int]:
        """
        Monitor both buy and sell orders in a unified loop.

        Returns:
            Dict with combined statistics
        """
        # Load pending buy orders at start (only if not already loaded)
        if not self.active_buy_orders and self.orders_repo:
            self.load_pending_buy_orders()

        # Fetch broker orders once for both buy and sell order checking
        broker_orders = None
        try:
            orders_response = self.orders.get_orders() if self.orders else None
            broker_orders = orders_response.get("data", []) if orders_response else []
        except Exception as e:
            logger.error(f"Error fetching broker orders: {e}")

        # Monitor sell orders (existing functionality)
        sell_stats = self.sell_manager.monitor_and_update()

        # Monitor buy orders (new functionality)
        buy_stats = self.check_buy_order_status(broker_orders=broker_orders)

        # Combine statistics
        combined_stats = {
            "checked": sell_stats.get("checked", 0) + buy_stats.get("checked", 0),
            "updated": sell_stats.get("updated", 0),
            "executed": sell_stats.get("executed", 0) + buy_stats.get("executed", 0),
            "rejected": buy_stats.get("rejected", 0),
            "cancelled": buy_stats.get("cancelled", 0),
        }

        return combined_stats

