#!/usr/bin/env python3
"""
Unified Order Monitor
Monitors both buy (AMO) and sell orders during market hours.

Phase 2: Unified order monitoring implementation.
Extends SellOrderManager to handle buy order monitoring alongside sell orders.
"""

from typing import Any

from utils.logger import logger

try:
    from .sell_engine import SellOrderManager
    from .utils.order_field_extractor import OrderFieldExtractor
    from .utils.symbol_utils import extract_base_symbol
except ImportError:
    from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
    from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor

# Try to import database dependencies
try:
    from sqlalchemy.orm import Session

    from src.infrastructure.db.models import OrderStatus as DbOrderStatus
    from src.infrastructure.persistence.orders_repository import OrdersRepository
    from src.infrastructure.persistence.positions_repository import PositionsRepository

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
        db_session: Session | None = None,
        user_id: int | None = None,
        telegram_notifier=None,
    ):
        """
        Initialize unified order monitor.

        Phase 9: Added telegram_notifier for notifications.

        Args:
            sell_order_manager: Existing SellOrderManager instance
            db_session: Optional database session for buy order tracking
            user_id: Optional user ID for filtering orders
            telegram_notifier: Optional TelegramNotifier for sending notifications
        """
        self.sell_manager = sell_order_manager
        self.orders = sell_order_manager.orders
        self.db_session = db_session
        self.user_id = user_id
        self.telegram_notifier = telegram_notifier

        # Track active buy orders {order_id: {'symbol': str, 'quantity': float, 'order_id': str, ...}}
        self.active_buy_orders: dict[str, dict[str, Any]] = {}

        # Initialize orders repository if DB is available
        self.orders_repo = None
        self.positions_repo = None
        if DB_AVAILABLE and db_session:
            try:
                self.orders_repo = OrdersRepository(db_session)
                logger.info("OrdersRepository initialized for buy order monitoring")
            except Exception as e:
                logger.warning(f"Failed to initialize OrdersRepository: {e}")
                self.orders_repo = None

            try:
                self.positions_repo = PositionsRepository(db_session)
                logger.info("PositionsRepository initialized for position tracking")
            except Exception as e:
                logger.warning(f"Failed to initialize PositionsRepository: {e}")
                self.positions_repo = None

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
        Phase 10: Update OrderStateManager with telegram_notifier, orders_repo, and user_id.

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

        # Phase 10: Update OrderStateManager with notification and DB support
        if self.telegram_notifier:
            state_manager.telegram_notifier = self.telegram_notifier
        if self.orders_repo:
            state_manager.orders_repo = self.orders_repo
        if self.user_id:
            state_manager.user_id = self.user_id

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
                logger.warning(f"Failed to register buy order {order_id} with state manager: {e}")

        if registered_count > 0:
            logger.info(
                f"Registered {registered_count}/{len(self.active_buy_orders)} "
                "buy orders with OrderStateManager"
            )

        return registered_count

    def check_buy_order_status(
        self, broker_orders: list[dict[str, Any]] | None = None
    ) -> dict[str, int]:
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

            # Fetch holdings once for reconciliation (if needed)
            holdings_data = None
            if self.sell_manager and hasattr(self.sell_manager, "portfolio"):
                try:
                    holdings_response = self.sell_manager.portfolio.get_holdings()
                    holdings_data = (
                        holdings_response.get("data", [])
                        if isinstance(holdings_response, dict)
                        else []
                    )
                except Exception as e:
                    logger.debug(f"Could not fetch holdings for reconciliation: {e}")
                    holdings_data = []

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
                    # Use holdings() API to check if order was executed
                    # If symbol appears in holdings, order likely executed while service was down
                    symbol = order_info.get("symbol", "")
                    base_symbol = extract_base_symbol(symbol).upper() if symbol else ""

                    if base_symbol and holdings_data is not None:
                        try:
                            # Look for symbol in holdings (indicates order was executed)
                            found_in_holdings = False
                            holding_info = None

                            for holding in holdings_data:
                                # Try multiple field names for symbol matching
                                holding_symbol = (
                                    holding.get("displaySymbol")
                                    or holding.get("symbol")
                                    or holding.get("tradingSymbol")
                                    or ""
                                )
                                holding_base = extract_base_symbol(holding_symbol).upper()

                                if holding_base == base_symbol:
                                    found_in_holdings = True
                                    holding_info = holding
                                    break

                            if found_in_holdings and holding_info:
                                # Order was executed - symbol is in holdings
                                logger.info(
                                    f"Order {order_id} not in order_report but found in holdings - "
                                    f"order was executed while service was down. Reconciling..."
                                )

                                # Update order status in database
                                if self.orders_repo and order_info.get("db_order_id"):
                                    try:
                                        db_order = self.orders_repo.get(order_info["db_order_id"])
                                        if not db_order:
                                            continue

                                        # Extract execution details from holdings
                                        # For execution_price: prefer order price if available (limit order),
                                        # otherwise use averagePrice from holdings (approximation)
                                        order_price = order_info.get("price") or (
                                            float(db_order.price) if db_order.price else None
                                        )
                                        execution_price = (
                                            float(order_price)
                                            if order_price and float(order_price) > 0
                                            else (
                                                float(holding_info.get("averagePrice", 0))
                                                or float(holding_info.get("avgPrice", 0))
                                                or float(holding_info.get("closingPrice", 0))
                                                or 0.0
                                            )
                                        )
                                        # For execution_qty, prefer order quantity from DB if available
                                        # (holdings quantity is total position, not just this order)
                                        order_qty = (
                                            order_info.get("quantity", 0) or db_order.quantity
                                        )
                                        execution_qty = (
                                            float(order_qty)
                                            if order_qty and float(order_qty) > 0
                                            else (
                                                float(holding_info.get("quantity", 0))
                                                or float(holding_info.get("qty", 0))
                                                or 0.0
                                            )
                                        )

                                        # Mark as executed using holdings data
                                        if execution_price > 0 and execution_qty > 0:
                                            self.orders_repo.mark_executed(
                                                db_order,
                                                execution_price=execution_price,
                                                execution_qty=execution_qty,
                                            )
                                            logger.info(
                                                f"Reconciled order {order_id}: "
                                                f"executed at Rs {execution_price:.2f}, qty {execution_qty}"
                                            )

                                            # Create/update position
                                            self._create_position_from_executed_order(
                                                order_id,
                                                order_info,
                                                execution_price,
                                                execution_qty,
                                            )

                                            stats["executed"] += 1
                                            order_ids_to_remove.append(order_id)
                                        else:
                                            logger.warning(
                                                f"Holdings found for {base_symbol} but missing "
                                                f"price/qty data - cannot reconcile order {order_id}"
                                            )
                                    except Exception as e:
                                        logger.error(
                                            f"Error reconciling order {order_id} from holdings: {e}"
                                        )
                            else:
                                # Order not in holdings either - might be rejected/cancelled
                                # or holdings API unavailable
                                placed_at = order_info.get("placed_at")
                                if placed_at:
                                    logger.debug(
                                        f"Buy order {order_id} not found in broker orders or holdings"
                                    )
                        except Exception as e:
                            logger.warning(
                                f"Error checking holdings for order {order_id}: {e}. "
                                "Falling back to default behavior."
                            )
                            # Fallback to original behavior
                            placed_at = order_info.get("placed_at")
                            if placed_at:
                                logger.debug(f"Buy order {order_id} not found in broker orders")
                    else:
                        # No portfolio access or symbol info - use original behavior
                        placed_at = order_info.get("placed_at")
                        if placed_at:
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
        self, db_order: Any, broker_order: dict[str, Any], status: str
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
        self, order_id: str, order_info: dict[str, Any], broker_order: dict[str, Any]
    ) -> None:
        """
        Handle executed buy order.

        Phase 4: Integrates with OrderStateManager for unified state tracking.
        Phase 9: Sends notification for order execution.

        Args:
            order_id: Order ID
            order_info: Order tracking info
            broker_order: Broker order dict
        """
        symbol = order_info.get("symbol", "")
        execution_price = OrderFieldExtractor.get_price(broker_order)
        execution_qty = OrderFieldExtractor.get_quantity(broker_order) or order_info.get(
            "quantity", 0
        )

        logger.info(
            f"Buy order executed: {symbol} - Order ID {order_id}, "
            f"Price: Rs {execution_price:.2f}, Qty: {execution_qty}"
        )

        # Phase 9: Send notification
        if self.telegram_notifier and self.telegram_notifier.enabled:
            try:
                self.telegram_notifier.notify_order_execution(
                    symbol=symbol,
                    order_id=order_id,
                    quantity=int(execution_qty),
                    executed_price=execution_price,
                    user_id=self.user_id,
                )
            except Exception as e:
                logger.warning(f"Failed to send execution notification: {e}")

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

        # Create/update position with entry RSI from order metadata
        self._create_position_from_executed_order(
            order_id, order_info, execution_price, execution_qty
        )

    def _create_position_from_executed_order(
        self,
        order_id: str,
        order_info: dict[str, Any],
        execution_price: float,
        execution_qty: float,
    ) -> None:
        """
        Create or update position from executed buy order with entry RSI tracking.

        Phase 2: Entry RSI Tracking - Extracts entry RSI from order metadata and stores in position.

        Args:
            order_id: Order ID
            order_info: Order tracking info
            execution_price: Execution price
            execution_qty: Execution quantity
        """
        if not self.positions_repo or not self.user_id:
            logger.debug("Cannot create position: positions_repo or user_id not available")
            return

        if not self.orders_repo:
            logger.debug("Cannot create position: orders_repo not available")
            return

        try:
            symbol = order_info.get("symbol", "").upper()
            if not symbol:
                logger.warning("Cannot create position: symbol not found in order_info")
                return

            # Extract base symbol (remove -EQ suffix if present)
            base_symbol = extract_base_symbol(symbol).upper()

            # Get order from database to extract metadata
            db_order = None
            if order_info.get("db_order_id"):
                db_order = self.orders_repo.get(order_info["db_order_id"])
            else:
                # Try to find order by broker_order_id
                db_order = self.orders_repo.get_by_broker_order_id(self.user_id, order_id)

            # Extract entry RSI from order metadata
            entry_rsi = None
            if db_order and db_order.order_metadata:
                metadata = (
                    db_order.order_metadata if isinstance(db_order.order_metadata, dict) else {}
                )
                # Priority: rsi_entry_level > entry_rsi > rsi10
                if metadata.get("rsi_entry_level") is not None:
                    entry_rsi = float(metadata["rsi_entry_level"])
                elif metadata.get("entry_rsi") is not None:
                    entry_rsi = float(metadata["entry_rsi"])
                elif metadata.get("rsi10") is not None:
                    entry_rsi = float(metadata["rsi10"])

            # Default to 29.5 if no RSI data available (assume entry at RSI < 30)
            if entry_rsi is None:
                entry_rsi = 29.5
                logger.debug(
                    f"No entry RSI found in order metadata for {base_symbol}, defaulting to 29.5"
                )

            # Check if position already exists
            existing_pos = self.positions_repo.get_by_symbol(self.user_id, base_symbol)

            # Calculate execution time (use current time if not available)
            try:
                from src.infrastructure.db.timezone_utils import ist_now

                execution_time = ist_now()
            except ImportError:
                from datetime import datetime

                execution_time = datetime.now()
            if db_order and hasattr(db_order, "filled_at") and db_order.filled_at:
                execution_time = db_order.filled_at
            elif db_order and hasattr(db_order, "execution_time") and db_order.execution_time:
                execution_time = db_order.execution_time

            # Create or update position
            if existing_pos:
                # Update existing position (add to quantity, recalculate avg price)
                existing_qty = existing_pos.quantity
                existing_avg_price = existing_pos.avg_price

                # Calculate new average price
                total_cost = (existing_qty * existing_avg_price) + (execution_qty * execution_price)
                new_qty = existing_qty + execution_qty
                new_avg_price = total_cost / new_qty if new_qty > 0 else execution_price

                # Only update entry_rsi if it's not already set (preserve original entry RSI)
                entry_rsi_to_set = None
                if existing_pos.entry_rsi is None:
                    entry_rsi_to_set = entry_rsi

                # Reentry tracking: Detect if this is a reentry and update reentry fields
                is_reentry = False
                reentry_count = existing_pos.reentry_count or 0
                reentries_array = existing_pos.reentries if existing_pos.reentries else []
                last_reentry_price = existing_pos.last_reentry_price

                # Check if this is a reentry: existing position OR order marked as reentry
                if db_order and db_order.entry_type == "reentry":
                    is_reentry = True
                elif existing_pos:  # Position already exists, so this is likely a reentry
                    is_reentry = True

                if is_reentry:
                    # Extract reentry data from order metadata or construct from execution data
                    reentry_data = None
                    if db_order and db_order.order_metadata:
                        metadata = (
                            db_order.order_metadata
                            if isinstance(db_order.order_metadata, dict)
                            else {}
                        )
                        # Extract reentry fields from metadata
                        reentry_level = metadata.get("rsi_level") or metadata.get("level")
                        reentry_rsi = metadata.get("rsi") or metadata.get("rsi10") or entry_rsi
                        reentry_price = metadata.get("price") or execution_price

                        # Construct reentry data matching trade history structure
                        reentry_data = {
                            "qty": int(execution_qty),
                            "level": int(reentry_level) if reentry_level is not None else None,
                            "rsi": float(reentry_rsi) if reentry_rsi is not None else None,
                            "price": float(reentry_price),
                            "time": execution_time.isoformat(),
                        }
                    else:
                        # Fallback: construct minimal reentry data from execution
                        reentry_data = {
                            "qty": int(execution_qty),
                            "level": None,
                            "rsi": float(entry_rsi) if entry_rsi else None,
                            "price": float(execution_price),
                            "time": execution_time.isoformat(),
                        }

                    # Ensure reentries_array is a list
                    if not isinstance(reentries_array, list):
                        reentries_array = []

                    # Append new reentry
                    reentries_array.append(reentry_data)
                    reentry_count = len(reentries_array)
                    last_reentry_price = execution_price

                    logger.info(
                        f"Reentry detected for {base_symbol}: Adding reentry #{reentry_count} "
                        f"(qty: {execution_qty}, price: Rs {execution_price:.2f})"
                    )
                    # Note: Database is updated here (source of truth).
                    # JSON backup is synced during reconciliation via _load_trades_history()
                    # which reads from database and writes to JSON.

                self.positions_repo.upsert(
                    user_id=self.user_id,
                    symbol=base_symbol,
                    quantity=new_qty,
                    avg_price=new_avg_price,
                    opened_at=existing_pos.opened_at,  # Preserve original open time
                    entry_rsi=entry_rsi_to_set,  # Only set if not already set
                    reentry_count=reentry_count if is_reentry else None,
                    reentries=reentries_array if is_reentry else None,
                    last_reentry_price=last_reentry_price if is_reentry else None,
                )
                logger.info(
                    f"Updated position for {base_symbol}: qty {existing_qty} -> {new_qty}, "
                    f"avg_price Rs {existing_avg_price:.2f} -> Rs {new_avg_price:.2f}"
                    + (f", reentry_count: {reentry_count}" if is_reentry else "")
                )

                # Edge Case #1 Fix: Update existing sell order if quantity increased (reentry scenario)
                if new_qty > existing_qty and self.sell_manager:
                    try:
                        # Check for existing sell order
                        existing_orders = self.sell_manager.get_existing_sell_orders()
                        if base_symbol.upper() in existing_orders:
                            existing_order = existing_orders[base_symbol.upper()]
                            existing_order_qty = existing_order.get("qty", 0)
                            existing_order_price = existing_order.get("price", 0)
                            existing_order_id = existing_order.get("order_id")

                            if existing_order_id and new_qty > existing_order_qty:
                                logger.info(
                                    f"Reentry detected for {base_symbol}: Updating sell order quantity "
                                    f"from {existing_order_qty} to {new_qty} (Order ID: {existing_order_id})"
                                )

                                # Update sell order with new quantity (keep same price)
                                if self.sell_manager.update_sell_order(
                                    order_id=str(existing_order_id),
                                    symbol=base_symbol,
                                    qty=int(new_qty),
                                    new_price=existing_order_price,
                                ):
                                    logger.info(
                                        f"Successfully updated sell order for {base_symbol}: "
                                        f"{existing_order_qty} -> {new_qty} shares @ Rs {existing_order_price:.2f}"
                                    )
                                else:
                                    logger.warning(
                                        f"Failed to update sell order for {base_symbol}. "
                                        f"Order will be updated next day by run_at_market_open()."
                                    )
                    except Exception as e:
                        # Don't fail position update if sell order update fails
                        logger.warning(
                            f"Error updating sell order after reentry for {base_symbol}: {e}. "
                            f"Order will be updated next day by run_at_market_open()."
                        )
            else:
                # Create new position
                self.positions_repo.upsert(
                    user_id=self.user_id,
                    symbol=base_symbol,
                    quantity=execution_qty,
                    avg_price=execution_price,
                    opened_at=execution_time,
                    entry_rsi=entry_rsi,
                )
                logger.info(
                    f"Created position for {base_symbol}: qty={execution_qty}, "
                    f"price=Rs {execution_price:.2f}, entry_rsi={entry_rsi:.2f}"
                )

        except Exception as e:
            logger.error(f"Error creating/updating position from executed order {order_id}: {e}")

    def _handle_buy_order_rejection(
        self, order_id: str, order_info: dict[str, Any], broker_order: dict[str, Any]
    ) -> None:
        """
        Handle rejected buy order.

        Phase 4: Integrates with OrderStateManager for unified state tracking.
        Phase 9: Sends notification with broker rejection reason.

        Args:
            order_id: Order ID
            order_info: Order tracking info
            broker_order: Broker order dict
        """
        symbol = order_info.get("symbol", "")
        rejection_reason = OrderFieldExtractor.get_rejection_reason(broker_order) or "Unknown"
        quantity = order_info.get("quantity", 0)

        logger.warning(
            f"Buy order rejected: {symbol} - Order ID {order_id}, Reason: {rejection_reason}"
        )

        # Phase 9: Send notification with broker rejection reason
        if self.telegram_notifier and self.telegram_notifier.enabled:
            try:
                self.telegram_notifier.notify_order_rejection(
                    symbol=symbol,
                    order_id=order_id,
                    quantity=int(quantity),
                    rejection_reason=rejection_reason,
                    user_id=self.user_id,
                )
            except Exception as e:
                logger.warning(f"Failed to send rejection notification: {e}")

        # Phase 4: Update OrderStateManager if available
        if (
            self.sell_manager
            and hasattr(self.sell_manager, "state_manager")
            and self.sell_manager.state_manager
        ):
            try:
                self.sell_manager.state_manager.remove_buy_order_from_tracking(
                    order_id=order_id, reason=f"Rejected: {rejection_reason}"
                )
            except Exception as e:
                logger.warning(f"Failed to update OrderStateManager for rejected buy order: {e}")

        # Status already updated in database via _update_buy_order_status

    def _handle_buy_order_cancellation(
        self, order_id: str, order_info: dict[str, Any], broker_order: dict[str, Any]
    ) -> None:
        """
        Handle cancelled buy order.

        Phase 4: Integrates with OrderStateManager for unified state tracking.
        Phase 9: Sends notification for order cancellation.

        Args:
            order_id: Order ID
            order_info: Order tracking info
            broker_order: Broker order dict
        """
        symbol = order_info.get("symbol", "")
        cancelled_reason = OrderFieldExtractor.get_rejection_reason(broker_order) or "Unknown"

        logger.info(
            f"Buy order cancelled: {symbol} - Order ID {order_id}, Reason: {cancelled_reason}"
        )

        # Phase 9: Send notification
        if self.telegram_notifier and self.telegram_notifier.enabled:
            try:
                self.telegram_notifier.notify_order_cancelled(
                    symbol=symbol,
                    order_id=order_id,
                    cancellation_reason=cancelled_reason,
                    user_id=self.user_id,
                )
            except Exception as e:
                logger.warning(f"Failed to send cancellation notification: {e}")

        # Phase 4: Update OrderStateManager if available
        if (
            self.sell_manager
            and hasattr(self.sell_manager, "state_manager")
            and self.sell_manager.state_manager
        ):
            try:
                self.sell_manager.state_manager.remove_buy_order_from_tracking(
                    order_id=order_id, reason=f"Cancelled: {cancelled_reason}"
                )
            except Exception as e:
                logger.warning(f"Failed to update OrderStateManager for cancelled buy order: {e}")

        # Status already updated in database via _update_buy_order_status

    def monitor_all_orders(self) -> dict[str, int]:
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

        # Monitor buy orders (new functionality) - check for executions first
        buy_stats = self.check_buy_order_status(broker_orders=broker_orders)

        # Check for newly executed orders and place sell orders for them
        # This allows tracking holdings that were executed during the day
        new_holdings_sell_orders = self.check_and_place_sell_orders_for_new_holdings()

        # Monitor sell orders (existing functionality)
        sell_stats = self.sell_manager.monitor_and_update()

        # Combine statistics
        combined_stats = {
            "checked": sell_stats.get("checked", 0) + buy_stats.get("checked", 0),
            "updated": sell_stats.get("updated", 0),
            "executed": sell_stats.get("executed", 0) + buy_stats.get("executed", 0),
            "rejected": buy_stats.get("rejected", 0),
            "cancelled": buy_stats.get("cancelled", 0),
            "new_holdings_tracked": new_holdings_sell_orders,
        }

        return combined_stats

    def check_and_place_sell_orders_for_new_holdings(self) -> int:
        """
        Check for newly executed buy orders (ONGOING status) that were executed today
        and place sell orders for them if they don't already have sell orders.

        This allows the sell monitor to track holdings that were executed during the day,
        not just at market open.

        Returns:
            Number of sell orders placed for new holdings
        """
        if not self.orders_repo or not self.user_id:
            return 0

        if not self.sell_manager:
            return 0

        try:
            from datetime import datetime

            from src.infrastructure.db.timezone_utils import IST, ist_now

            # Get today's date
            today = ist_now().date()
            today_start = datetime.combine(today, datetime.min.time()).replace(
                tzinfo=ist_now().tzinfo
            )

            # Helper function to normalize datetime to IST timezone-aware
            def normalize_to_ist(dt: datetime | None) -> datetime | None:
                """Convert datetime to IST timezone-aware if it's naive"""
                if dt is None:
                    return None
                if dt.tzinfo is None:
                    # Assume naive datetime is in IST
                    return dt.replace(tzinfo=IST)
                # Already timezone-aware, convert to IST if needed
                return dt.astimezone(IST) if dt.tzinfo != IST else dt

            # Get all ONGOING buy orders executed today
            # We'll check orders that have execution_time >= today_start
            all_orders = self.orders_repo.list(self.user_id, status=DbOrderStatus.ONGOING)

            newly_executed_orders = []
            skipped_orders = []
            for order in all_orders:
                # Only process buy orders
                if order.side.lower() != "buy":
                    continue

                # Check if order was executed today
                # Use execution_time if available, otherwise use filled_at
                execution_time = getattr(order, "execution_time", None) or order.filled_at
                execution_time = normalize_to_ist(execution_time)

                if execution_time:
                    if execution_time >= today_start:
                        newly_executed_orders.append(order)
                    else:
                        skipped_orders.append(
                            f"{order.symbol}: executed {execution_time} (before today)"
                        )
                else:
                    skipped_orders.append(f"{order.symbol}: no execution_time or filled_at")

            if skipped_orders:
                logger.debug(
                    f"Skipped {len(skipped_orders)} ONGOING orders (not executed today): "
                    f"{', '.join(skipped_orders[:5])}"
                )

            if not newly_executed_orders:
                return 0

            logger.info(f"Found {len(newly_executed_orders)} newly executed buy orders today")

            # Get existing sell orders to avoid duplicates
            existing_sell_orders = self.sell_manager.get_existing_sell_orders()
            existing_symbols = {
                extract_base_symbol(symbol).upper() for symbol in existing_sell_orders.keys()
            }

            # Get currently tracked sell orders
            active_sell_symbols = {
                extract_base_symbol(symbol).upper()
                for symbol in self.sell_manager.active_sell_orders.keys()
            }

            orders_placed = 0

            for db_order in newly_executed_orders:
                try:
                    base_symbol = extract_base_symbol(db_order.symbol).upper()

                    # Skip if already has sell order
                    if base_symbol in existing_symbols or base_symbol in active_sell_symbols:
                        logger.info(f"Skipping {base_symbol}: Already has sell order")
                        continue

                    # Check if position already has a completed sell order
                    completed_order_info = self.sell_manager.has_completed_sell_order(base_symbol)
                    if completed_order_info:
                        logger.debug(f"Skipping {base_symbol}: Already has completed sell order")
                        continue

                    # Convert order to trade format
                    # Get ticker from order metadata or construct from symbol
                    ticker = None
                    if db_order.order_metadata and isinstance(db_order.order_metadata, dict):
                        ticker = db_order.order_metadata.get("ticker")

                    if not ticker:
                        # Construct ticker from symbol (e.g., "RELIANCE-EQ" -> "RELIANCE.NS")
                        base_sym = extract_base_symbol(db_order.symbol).upper()
                        ticker = f"{base_sym}.NS"

                    # Get execution price and quantity
                    execution_price = (
                        getattr(db_order, "execution_price", None)
                        or db_order.avg_price
                        or db_order.price
                    )
                    execution_qty = getattr(db_order, "execution_qty", None) or db_order.quantity

                    if not execution_price or execution_qty <= 0:
                        logger.warning(
                            f"Skipping {base_symbol}: Invalid execution price or quantity"
                        )
                        continue

                    # Get execution time for this order (normalize to IST)
                    order_execution_time = (
                        getattr(db_order, "execution_time", None) or db_order.filled_at
                    )
                    order_execution_time = (
                        normalize_to_ist(order_execution_time) if order_execution_time else None
                    )

                    # Create trade dict in format expected by place_sell_order
                    trade = {
                        "symbol": base_symbol,
                        "ticker": ticker,
                        "qty": int(execution_qty),
                        "entry_price": execution_price,
                        "placed_symbol": db_order.symbol,  # Keep original broker symbol
                        "entry_time": (
                            order_execution_time.isoformat()
                            if order_execution_time
                            else ist_now().isoformat()
                        ),
                    }

                    # Get current EMA9 as target
                    broker_sym = db_order.symbol
                    ema9 = self.sell_manager.get_current_ema9(ticker, broker_symbol=broker_sym)
                    if not ema9:
                        logger.warning(f"Skipping {base_symbol}: Failed to calculate EMA9")
                        continue

                    # Check if price is reasonable (not too far from entry)
                    if ema9 < execution_price * 0.95:  # More than 5% below entry
                        logger.warning(
                            f"Skipping {base_symbol}: EMA9 (Rs {ema9:.2f}) is too low "
                            f"(entry: Rs {execution_price:.2f})"
                        )
                        continue

                    # Place sell order
                    logger.info(
                        f"Placing sell order for {base_symbol}: qty={int(execution_qty)}, "
                        f"entry_price={execution_price:.2f}, ema9={ema9:.2f}"
                    )
                    order_id = self.sell_manager.place_sell_order(trade, ema9)

                    if order_id:
                        logger.info(f"Successfully placed sell order for {base_symbol}: {order_id}")
                        # Track the order
                        self.sell_manager._register_order(
                            symbol=base_symbol,
                            order_id=order_id,
                            target_price=ema9,
                            qty=int(execution_qty),
                            ticker=ticker,
                            placed_symbol=broker_sym,
                        )
                        self.sell_manager.lowest_ema9[base_symbol] = ema9
                        orders_placed += 1
                        logger.info(
                            f"Placed sell order for newly executed holding: {base_symbol} "
                            f"(Order ID: {order_id}, Target: Rs {ema9:.2f})"
                        )

                except Exception as e:
                    logger.error(f"Error placing sell order for {db_order.symbol}: {e}")

            if orders_placed > 0:
                logger.info(f"Placed {orders_placed} sell orders for newly executed holdings")

            return orders_placed

        except Exception as e:
            logger.error(f"Error checking for new holdings: {e}")
            return 0
