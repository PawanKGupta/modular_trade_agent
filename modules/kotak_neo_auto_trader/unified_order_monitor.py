#!/usr/bin/env python3
"""
Unified Order Monitor
Monitors both buy (AMO) and sell orders during market hours.

Phase 2: Unified order monitoring implementation.
Extends SellOrderManager to handle buy order monitoring alongside sell orders.
"""

from datetime import datetime
from typing import Any

from utils.logger import logger

try:
    from src.infrastructure.db.timezone_utils import IST, ist_now
except ImportError:
    IST = None
    ist_now = None

try:
    from .sell_engine import SellOrderManager
    from .utils.order_field_extractor import OrderFieldExtractor
except ImportError:
    from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
    from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor

# Try to import database dependencies
try:
    from sqlalchemy.orm import Session

    from src.infrastructure.db.models import OrderStatus as DbOrderStatus
    from src.infrastructure.db.transaction import transaction
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
        Issue #1 Fix: db_session and user_id are required when DB_AVAILABLE is True.

        Args:
            sell_order_manager: Existing SellOrderManager instance
            db_session: Database session for buy order tracking (required if DB_AVAILABLE)
            user_id: User ID for filtering orders (required if DB_AVAILABLE)
            telegram_notifier: Optional TelegramNotifier for sending notifications

        Raises:
            ValueError: If DB_AVAILABLE is True but db_session or user_id is None
            RuntimeError: If repository initialization fails
        """
        self.sell_manager = sell_order_manager
        self.orders = sell_order_manager.orders
        self.db_session = db_session
        self.user_id = user_id
        self.telegram_notifier = telegram_notifier

        # Track active buy orders {order_id: {'symbol': str, 'quantity': float, ...}}
        self.active_buy_orders: dict[str, dict[str, Any]] = {}
        # Deduplicate buy execution handling/notifications within service runtime.
        self._processed_buy_execution_ids: set[str] = set()

        # Issue #1 Fix: Metrics tracking for position creation
        self._position_creation_metrics = {
            "success": 0,
            "failed_missing_repos": 0,
            "failed_missing_symbol": 0,
            "failed_exception": 0,
        }

        # Issue #1 Fix: Validate required parameters when DB is available
        if DB_AVAILABLE:
            if db_session is None:
                raise ValueError(
                    "UnifiedOrderMonitor requires db_session when database is available. "
                    "Position creation will fail without it."
                )
            if user_id is None:
                raise ValueError(
                    "UnifiedOrderMonitor requires user_id when database is available. "
                    "Position creation will fail without it."
                )

        # Issue #1 Fix: Initialize repositories and raise exception on failure
        self.orders_repo = None
        self.positions_repo = None
        if DB_AVAILABLE and db_session:
            try:
                self.orders_repo = OrdersRepository(db_session)
                logger.info("OrdersRepository initialized for buy order monitoring")
            except Exception as e:
                error_msg = (
                    f"CRITICAL: Failed to initialize OrdersRepository: {e}. "
                    f"Position creation will fail. Check database connection."
                )
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from e

            try:
                self.positions_repo = PositionsRepository(db_session)
                logger.info("PositionsRepository initialized for position tracking")
            except Exception as e:
                error_msg = (
                    f"CRITICAL: Failed to initialize PositionsRepository: {e}. "
                    f"Position creation will fail. Check database connection."
                )
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from e

        # Issue #1 Fix: Final validation - raise exception if critical dependencies missing
        if DB_AVAILABLE:
            if not self.orders_repo or not self.positions_repo:
                error_msg = (
                    "CRITICAL: UnifiedOrderMonitor initialized without required repositories. "
                    "Position creation will fail. This will prevent sell order placement. "
                    f"orders_repo={self.orders_repo is not None}, "
                    f"positions_repo={self.positions_repo is not None}, "
                    f"user_id={self.user_id is not None}"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            if not self.user_id:
                error_msg = (
                    "CRITICAL: UnifiedOrderMonitor initialized without user_id. "
                    "Position creation will fail. This will prevent sell order placement."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

        logger.info("UnifiedOrderMonitor initialized")

    def get_position_creation_metrics(self) -> dict[str, int]:
        """
        Get position creation metrics for monitoring.

        Issue #1 Fix: Returns metrics tracking position creation success/failure rates.

        Returns:
            Dict with metrics: success, failed_missing_repos,
            failed_missing_symbol, failed_exception
        """
        return self._position_creation_metrics.copy()

    def reset_position_creation_metrics(self) -> None:
        """
        Reset position creation metrics.

        Issue #1 Fix: Useful for periodic metric reporting.
        """
        self._position_creation_metrics = {
            "success": 0,
            "failed_missing_repos": 0,
            "failed_missing_symbol": 0,
            "failed_exception": 0,
        }

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
                # CRITICAL FIX: Safeguard - only process buy orders
                # This prevents sell orders from being incorrectly tracked as buy orders
                if order.side and order.side.lower() != "buy":
                    logger.warning(
                        f"Skipping non-buy order {order.id} ({order.side}) "
                        f"in load_pending_buy_orders()"
                    )
                    continue

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

        except ValueError as e:
            logger.error(f"Invalid data when loading pending buy orders: {e}", exc_info=True)
            return 0
        except Exception as e:
            logger.error(f"Unexpected error loading pending buy orders: {e}", exc_info=True)
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

    def _get_filled_quantity_from_order_history(  # noqa: PLR0911
        self, order_id: str
    ) -> dict[str, Any] | None:
        """
        Get filled quantity from order_history API (Edge Case #2 fix).

        Handles partial execution by extracting actual filled quantity (fldQty)
        from order_history response.

        Args:
            order_id: Order ID to look up

        Returns:
            Dict with 'filled_qty' and 'execution_price', or None if not found
        """
        if not self.orders:
            return None

        try:
            # Try specific order first (more efficient)
            response = self.orders.get_order_history(order_id=order_id)

            if not response:
                # Fallback: fetch full history and search
                response = self.orders.get_order_history()

            if not response or "data" not in response:
                return None

            # Handle nested data structure: response["data"]["data"]
            data_wrapper = response.get("data", {})
            if not isinstance(data_wrapper, dict):
                return None

            orders_list = data_wrapper.get("data", [])
            if not isinstance(orders_list, list):
                return None

            # Filter orders by order_id
            matching_orders = [
                order
                for order in orders_list
                if OrderFieldExtractor.get_order_id(order) == order_id
            ]

            if not matching_orders:
                return None

            # Find latest "complete" entry (highest updRecvTm with ordSt="complete")
            complete_orders = [
                order
                for order in matching_orders
                if OrderFieldExtractor.get_status(order) == "complete"
            ]

            if not complete_orders:
                # Order not complete yet
                return None

            # Get latest complete entry (highest timestamp)
            latest_complete = max(complete_orders, key=lambda o: o.get("updRecvTm", 0))

            filled_qty = OrderFieldExtractor.get_filled_quantity(latest_complete)
            avg_price_str = latest_complete.get("avgPrc", "0")
            avg_price = float(avg_price_str) if avg_price_str and avg_price_str != "0.00" else 0.0

            if filled_qty > 0:
                return {
                    "filled_qty": filled_qty,
                    "execution_price": avg_price,
                    "order_status": "complete",
                }

            return None

        except Exception as e:
            logger.warning(f"Error fetching order_history for {order_id}: {e}")
            return None

    def check_buy_order_status(  # noqa: PLR0912, PLR0915
        self, broker_orders: list[dict[str, Any]] | None = None
    ) -> dict[str, int]:
        """
        Check status of active buy orders from broker.

        Also checks ONGOING buy orders that are missing execution prices
        (orders that were executed but never synced properly).

        Args:
            broker_orders: Optional pre-fetched broker orders list

        Returns:
            Dict with statistics: {'checked': int, 'executed': int, 'rejected': int,
                'cancelled': int}
        """
        stats = {"checked": 0, "executed": 0, "rejected": 0, "cancelled": 0}

        # Load ONGOING orders with missing execution prices (need sync with broker)
        # These are orders that were executed but never had their execution price updated
        orders_to_check = dict(self.active_buy_orders)  # Start with active orders

        if self.orders_repo and self.user_id:
            try:
                # Get executed buy orders (ONGOING legacy or CLOSED = filled) for sync
                all_orders, _ = self.orders_repo.list(self.user_id)
                local_ist_now = ist_now
                if local_ist_now is None:
                    from src.infrastructure.db.timezone_utils import (
                        ist_now as local_ist_now,  # noqa: PLC0415
                    )
                today_start = datetime.combine(local_ist_now().date(), datetime.min.time()).replace(
                    tzinfo=local_ist_now().tzinfo
                )

                def _normalize_to_ist(dt: datetime | None) -> datetime | None:
                    if dt is None:
                        return None
                    if dt.tzinfo is None:
                        return dt.replace(tzinfo=IST)
                    return dt.astimezone(IST) if dt.tzinfo != IST else dt

                executed_buy_orders = []
                for o in all_orders:
                    if not (o.status in (DbOrderStatus.ONGOING, DbOrderStatus.CLOSED)):
                        continue
                    if not (o.side and o.side.lower() == "buy"):
                        continue

                    # Avoid replaying historical CLOSED buys forever.
                    # ONGOING buys are still tracked for backward compatibility.
                    if o.status == DbOrderStatus.CLOSED:
                        executed_at = _normalize_to_ist(
                            getattr(o, "execution_time", None) or getattr(o, "filled_at", None)
                        )
                        if not executed_at or executed_at < today_start:
                            continue

                    # This sync path is for missing execution data / missing open position only.
                    # Skip already-synced orders to avoid repeatedly adding same qty every cycle.
                    has_execution = bool(
                        getattr(o, "execution_price", None) and getattr(o, "execution_qty", None)
                    )
                    has_open_position = False
                    if self.positions_repo and getattr(o, "symbol", None):
                        try:
                            pos = self.positions_repo.get_by_symbol(self.user_id, str(o.symbol).upper())
                            has_open_position = bool(pos and pos.closed_at is None)
                        except Exception:
                            has_open_position = False
                    if has_execution and has_open_position:
                        continue

                    executed_buy_orders.append(o)
                for order in executed_buy_orders:
                    order_id = str(order.broker_order_id or order.order_id or "")
                    if order_id and order_id in self._processed_buy_execution_ids:
                        continue
                    # BUG FIX: Include orders WITH execution_price to check for missing positions
                    # Previously only orders WITHOUT execution_price were checked, causing
                    # positions to never be created for executed orders that already had
                    # execution_price
                    order_id = order.broker_order_id or order.order_id
                    if order_id and order_id not in orders_to_check:
                        orders_to_check[str(order_id)] = {
                            "symbol": order.symbol,
                            "quantity": order.quantity,
                            "order_id": str(order_id),
                            "db_order_id": order.id,
                            "status": order.status.value if order.status else "ongoing",
                            "placed_at": order.placed_at,
                        }
                        logger.debug(
                            f"Added executed order {order_id} ({order.symbol}) to sync - "
                            f"execution_price={'present' if order.execution_price else 'missing'}"
                        )
            except Exception as e:
                logger.error(f"Error loading executed orders for sync: {e}", exc_info=True)

        if not orders_to_check:
            logger.debug("No buy orders to check")
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

            # Check each buy order (active + ongoing with missing execution price)
            order_ids_to_remove = []

            for order_id, order_info in list(orders_to_check.items()):
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
                        # Edge Case #2: Use fldQty from broker_order if available
                        # (partial execution)
                        filled_qty = OrderFieldExtractor.get_filled_quantity(broker_order)
                        if filled_qty > 0:
                            # Override execution quantity with actual filled quantity
                            order_info["execution_qty"] = float(filled_qty)
                            logger.info(
                                f"Using fldQty from order_report() for {order_id}: "
                                f"qty={filled_qty} (handles partial execution)"
                            )
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
                    full_symbol = symbol.upper() if symbol else ""  # symbol is already full symbol

                    if full_symbol and holdings_data is not None:
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
                                holding_full_symbol = holding_symbol.upper()

                                if holding_full_symbol == full_symbol:  # ✅ Exact match
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

                                        # Edge Case #2 Fix: Use priority order for execution details
                                        # Priority 1: Try order_report() first (same-day orders)
                                        broker_order_from_report = None
                                        if broker_orders:
                                            for bo in broker_orders:
                                                if OrderFieldExtractor.get_order_id(bo) == order_id:
                                                    broker_order_from_report = bo
                                                    break

                                        execution_qty = None
                                        execution_price = None
                                        source = None

                                        # Priority 1: fldQty from order_report() (if found)
                                        if broker_order_from_report:
                                            filled_qty = OrderFieldExtractor.get_filled_quantity(
                                                broker_order_from_report
                                            )
                                            if filled_qty > 0:
                                                execution_qty = float(filled_qty)
                                                execution_price = OrderFieldExtractor.get_price(
                                                    broker_order_from_report
                                                )
                                                source = "order_report"
                                                logger.info(
                                                    f"Using fldQty from order_report() for {order_id}: "  # noqa: E501
                                                    f"qty={execution_qty}, "
                                                    f"price={execution_price:.2f}"
                                                )

                                        # Priority 2: fldQty from order_history()
                                        # (if not found in order_report)
                                        if execution_qty is None:
                                            history_data = (
                                                self._get_filled_quantity_from_order_history(
                                                    order_id
                                                )
                                            )
                                            if (
                                                history_data
                                                and history_data.get("filled_qty", 0) > 0
                                            ):
                                                execution_qty = float(history_data["filled_qty"])
                                                execution_price = history_data.get(
                                                    "execution_price", 0.0
                                                )
                                                source = "order_history"
                                                logger.info(
                                                    f"Using fldQty from order_history() for {order_id}: "  # noqa: E501
                                                    f"qty={execution_qty}, "
                                                    f"price={execution_price:.2f}"
                                                )

                                        # Priority 3: Holdings quantity (actual broker position)
                                        if execution_qty is None:
                                            holdings_qty = float(
                                                holding_info.get("quantity", 0)
                                                or holding_info.get("qty", 0)
                                                or 0.0
                                            )
                                            if holdings_qty > 0:
                                                execution_qty = holdings_qty
                                                execution_price = (
                                                    float(holding_info.get("averagePrice", 0))
                                                    or float(holding_info.get("avgPrice", 0))
                                                    or float(holding_info.get("closingPrice", 0))
                                                    or 0.0
                                                )
                                                source = "holdings"
                                            logger.info(
                                                f"Using holdings quantity for {order_id}: "  # noqa: E501
                                                f"qty={execution_qty}, price={execution_price:.2f} "
                                                f"(Note: This is total position, "
                                                f"not just this order)"
                                            )

                                        # Priority 4: DB order quantity (last resort)
                                        if execution_qty is None:
                                            order_qty = (
                                                order_info.get("quantity", 0) or db_order.quantity
                                            )
                                            if order_qty and float(order_qty) > 0:
                                                execution_qty = float(order_qty)
                                                order_price = order_info.get("price") or (
                                                    float(db_order.price)
                                                    if db_order.price
                                                    else None
                                                )
                                                execution_price = (
                                                    float(order_price)
                                                    if order_price and float(order_price) > 0
                                                    else (
                                                        float(holding_info.get("averagePrice", 0))
                                                        or float(holding_info.get("avgPrice", 0))
                                                        or float(
                                                            holding_info.get("closingPrice", 0)
                                                        )
                                                        or 0.0
                                                    )
                                                )
                                                source = "db_order"
                                                logger.warning(
                                                    f"Using DB order quantity for {order_id} "
                                                    f"(least reliable): qty={execution_qty}, "
                                                    f"price={execution_price:.2f}. "
                                                    f"Consider manual verification."
                                                )

                                        # Mark as executed using extracted data
                                        if (
                                            execution_price
                                            and execution_price > 0
                                            and execution_qty
                                            and execution_qty > 0
                                        ):
                                            # Wrap order execution and position creation in transaction  # noqa: E501
                                            # Both repositories share the same db_session, so one
                                            # transaction covers both
                                            with transaction(self.orders_repo.db):
                                                self.orders_repo.mark_executed(
                                                    db_order,
                                                    execution_price=execution_price,
                                                    execution_qty=execution_qty,
                                                    auto_commit=False,  # Transaction handles commit
                                                )
                                                logger.info(
                                                    f"Reconciled order {order_id} (source: {source}): "  # noqa: E501
                                                    f"executed at Rs {execution_price:.2f}, "
                                                    f"qty {execution_qty}"
                                                )

                                                # Create/update position (within same transaction)
                                                # SQLAlchemy will use savepoints for nested
                                                # transactions automatically
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
                                                f"Holdings found for {full_symbol} but missing "
                                                f"price/qty data - cannot reconcile order "
                                                f"{order_id}"
                                            )
                                    except Exception as e:
                                        logger.error(
                                            f"Error reconciling order {order_id} from holdings: {e}"
                                        )
                            else:
                                # Order not in holdings either - might be rejected/cancelled
                                # or holdings API unavailable, OR already executed days ago
                                # Check if order has execution_price/qty in DB but no position
                                # exists
                                if self.orders_repo and order_info.get("db_order_id"):
                                    try:
                                        db_order = self.orders_repo.get(order_info["db_order_id"])
                                        if (
                                            db_order
                                            and db_order.status
                                            in (DbOrderStatus.ONGOING, DbOrderStatus.CLOSED)
                                            and db_order.execution_price
                                            and db_order.execution_price > 0
                                            and db_order.execution_qty
                                            and db_order.execution_qty > 0
                                        ):
                                            # Order has execution data and is ONGOING
                                            # Check if position exists
                                            symbol = order_info.get("symbol", "")
                                            full_symbol = (
                                                symbol.upper() if symbol else ""
                                            )  # symbol is already full symbol
                                            if full_symbol and self.positions_repo:
                                                # Always call _create_position_from_executed_order
                                                # It handles both creating new positions and updating
                                                # existing ones (including reentries)
                                                existing_pos = self.positions_repo.get_by_symbol(
                                                    self.user_id, full_symbol
                                                )
                                                action = (
                                                    "updating existing position"
                                                    if existing_pos
                                                    else "creating position"
                                                )
                                                logger.info(
                                                    f"Order {order_id} has execution data. "
                                                    f"{action.capitalize()} from DB order data."
                                                )
                                                with transaction(self.orders_repo.db):
                                                    self._create_position_from_executed_order(
                                                        order_id,
                                                        order_info,
                                                        float(db_order.execution_price),
                                                        float(db_order.execution_qty),
                                                    )
                                                stats["executed"] += 1
                                                order_ids_to_remove.append(order_id)
                                    except Exception as e:
                                        logger.warning(
                                            f"Error checking/creating position for order "
                                            f"{order_id}: {e}"
                                        )

                                placed_at = order_info.get("placed_at")
                                if placed_at:
                                    logger.debug(
                                        f"Buy order {order_id} not found in broker orders "
                                        f"or holdings"
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
                        # But still check if order has execution data and needs position creation
                        if self.orders_repo and order_info.get("db_order_id"):
                            try:
                                db_order = self.orders_repo.get(order_info["db_order_id"])
                                if (
                                    db_order
                                    and db_order.status
                                    in (DbOrderStatus.ONGOING, DbOrderStatus.CLOSED)
                                    and db_order.execution_price
                                    and db_order.execution_price > 0
                                    and db_order.execution_qty
                                    and db_order.execution_qty > 0
                                ):
                                    # Order has execution data and is ONGOING
                                    # Check if position exists
                                    symbol = order_info.get("symbol", "")
                                    full_symbol = (
                                        symbol.upper() if symbol else ""
                                    )  # symbol is already full symbol
                                    if full_symbol and self.positions_repo:
                                        # Always call _create_position_from_executed_order
                                        # It handles both creating new positions and updating
                                        # existing ones (including reentries)
                                        existing_pos = self.positions_repo.get_by_symbol(
                                            self.user_id, full_symbol
                                        )
                                        action = (
                                            "updating existing position"
                                            if existing_pos
                                            else "creating position"
                                        )
                                        logger.info(
                                            f"Order {order_id} has execution data "
                                            f"(holdings API unavailable). "
                                            f"{action.capitalize()} from DB order data."
                                        )
                                        with transaction(self.orders_repo.db):
                                            self._create_position_from_executed_order(
                                                order_id,
                                                order_info,
                                                float(db_order.execution_price),
                                                float(db_order.execution_qty),
                                            )
                                        stats["executed"] += 1
                                        order_ids_to_remove.append(order_id)
                            except Exception as e:
                                logger.warning(
                                    f"Error checking/creating position for order {order_id}: {e}"
                                )

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

        except ValueError as e:
            logger.error(f"Invalid data when checking buy order status: {e}", exc_info=True)
        except KeyError as e:
            logger.error(
                f"Missing required field when checking buy order status: {e}", exc_info=True
            )
        except Exception as e:
            logger.error(f"Unexpected error checking buy order status: {e}", exc_info=True)

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
                # Prevent duplicate execution aggregation loops:
                # mark_executed() aggregates via fills table, so calling it again for the
                # same already-executed order inflates execution_qty (6->12->18...).
                if (
                    getattr(db_order, "status", None) == DbOrderStatus.CLOSED
                    and getattr(db_order, "execution_qty", None)
                    and float(getattr(db_order, "execution_qty", 0) or 0) > 0
                    and getattr(db_order, "execution_price", None)
                    and float(getattr(db_order, "execution_price", 0) or 0) > 0
                ):
                    return

                execution_price = OrderFieldExtractor.get_price(broker_order)
                # Edge Case #2: Use fldQty (filled quantity) if available,
                # otherwise use order quantity
                filled_qty = OrderFieldExtractor.get_filled_quantity(broker_order)
                if filled_qty > 0:
                    execution_qty = float(filled_qty)
                else:
                    execution_qty = (
                        OrderFieldExtractor.get_quantity(broker_order) or db_order.quantity
                    )
                self.orders_repo.mark_executed(
                    db_order,
                    execution_price=execution_price,
                    execution_qty=execution_qty,
                )
            elif status in ["rejected", "reject"]:
                rejection_reason = OrderFieldExtractor.get_rejection_reason(broker_order)
                self.orders_repo.mark_rejected(db_order, rejection_reason or "Rejected by broker")
            elif status in ["cancelled", "cancel"]:
                cancelled_reason = OrderFieldExtractor.get_rejection_reason(broker_order)
                self.orders_repo.mark_cancelled(db_order, cancelled_reason or "Cancelled")

        except ValueError as e:
            logger.error(f"Invalid data when updating buy order status in DB: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error updating buy order status in DB: {e}", exc_info=True)

    def _handle_buy_order_execution(
        self, order_id: str, order_info: dict[str, Any], broker_order: dict[str, Any]
    ) -> None:
        """
        Handle executed buy order.

        Phase 4: Integrates with OrderStateManager for unified state tracking.
        Phase 9: Sends notification for order execution.
        Edge Case #2: Uses fldQty (filled quantity) to handle partial execution.

        Args:
            order_id: Order ID
            order_info: Order tracking info
            broker_order: Broker order dict
        """
        symbol = order_info.get("symbol", "")
        if order_id in self._processed_buy_execution_ids:
            logger.debug(f"Skipping duplicate buy execution handling for order_id={order_id}")
            return
        execution_price = OrderFieldExtractor.get_price(broker_order)

        # Edge Case #2: Use fldQty (filled quantity) if available, otherwise use order quantity
        # Check if execution_qty was already set from order_report (handles partial execution)
        execution_qty = order_info.get("execution_qty")
        if execution_qty is None:
            # Try to get filled quantity from broker_order
            filled_qty = OrderFieldExtractor.get_filled_quantity(broker_order)
            if filled_qty > 0:
                execution_qty = float(filled_qty)
            else:
                # Fallback to order quantity
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
        self._processed_buy_execution_ids.add(order_id)

    def _validate_reentry_data(self, reentry_data: dict[str, Any]) -> bool:
        """
        Validate reentry data structure before writing to database.

        Ensures all required fields are present and have valid types/values.

        Args:
            reentry_data: Reentry data dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["qty", "price", "time"]
        for field in required_fields:
            if field not in reentry_data:
                logger.error(f"Missing required field '{field}' in reentry data: {reentry_data}")
                return False

        # Validate qty
        qty = reentry_data.get("qty")
        if not isinstance(qty, int) or qty <= 0:
            logger.error(f"Invalid qty in reentry data: {qty} (must be positive integer)")
            return False

        # Validate price
        price = reentry_data.get("price")
        if not isinstance(price, int | float) or price <= 0:
            logger.error(f"Invalid price in reentry data: {price} (must be positive number)")
            return False

        # Validate time format
        time_str = reentry_data.get("time")
        if not isinstance(time_str, str):
            logger.error(f"Invalid time type in reentry data: {type(time_str)} (must be string)")
            return False

        try:
            datetime.fromisoformat(time_str)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid time format in reentry data: {time_str} - {e}")
            return False

        return True

    def _create_position_from_executed_order(  # noqa: PLR0912, PLR0915
        self,
        order_id: str,
        order_info: dict[str, Any],
        execution_price: float,
        execution_qty: float,
    ) -> None:
        """
        Create or update position from executed buy order with entry RSI tracking.

        Phase 2: Entry RSI Tracking - Extracts entry RSI from order metadata and stores in position.
        Issue #1 Fix: Enhanced error handling, retry mechanism, and fallback symbol extraction.

        Args:
            order_id: Order ID
            order_info: Order tracking info
            execution_price: Execution price
            execution_qty: Execution quantity
        """
        # EDGE CASE FIX #1: Validate execution_price and execution_qty at the start
        if not execution_price or execution_price <= 0:
            logger.error(
                f"Invalid execution_price: {execution_price} for order {order_id}. "
                f"Cannot create position. This will prevent sell order placement."
            )
            self._position_creation_metrics["failed_invalid_data"] = (
                self._position_creation_metrics.get("failed_invalid_data", 0) + 1
            )
            return

        if not execution_qty or execution_qty <= 0:
            logger.error(
                f"Invalid execution_qty: {execution_qty} for order {order_id}. "
                f"Cannot create position. This will prevent sell order placement."
            )
            self._position_creation_metrics["failed_invalid_data"] = (
                self._position_creation_metrics.get("failed_invalid_data", 0) + 1
            )
            return

        # Issue #1 Fix: Enhanced validation with structured logging and alerting
        if not self.positions_repo or not self.user_id:
            # Issue #1 Fix: Track metrics
            self._position_creation_metrics["failed_missing_repos"] += 1
            logger.error(
                f"CRITICAL: Cannot create position for order {order_id}: "
                f"positions_repo={self.positions_repo is not None}, "
                f"user_id={self.user_id is not None}. "
                f"This will prevent sell order placement. "
                f"Execution: {execution_qty} @ Rs {execution_price:.2f}"
            )
            # Issue #1 Fix: Send alert if telegram notifier available
            if self.telegram_notifier and self.telegram_notifier.enabled:
                try:
                    symbol_hint = order_info.get("symbol", "UNKNOWN")
                    self.telegram_notifier.notify_system_alert(
                        alert_type="POSITION_CREATION_FAILED",
                        message_text=(
                            f"Order {order_id} executed but position not created. "
                            f"Symbol: {symbol_hint}, Qty: {execution_qty}, "
                            f"Price: Rs {execution_price:.2f}. "
                            f"Reason: Missing positions_repo or user_id. "
                            f"Sell order will NOT be placed."
                        ),
                        severity="ERROR",
                        user_id=self.user_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to send position creation failure alert: {e}")
            return

        if not self.orders_repo:
            # Issue #1 Fix: Track metrics
            self._position_creation_metrics["failed_missing_repos"] += 1
            logger.error(
                f"CRITICAL: Cannot create position for order {order_id}: "
                f"orders_repo not available. "
                f"This will prevent position creation. "
                f"Execution: {execution_qty} @ Rs {execution_price:.2f}"
            )
            # Issue #1 Fix: Send alert if telegram notifier available
            if self.telegram_notifier and self.telegram_notifier.enabled:
                try:
                    symbol_hint = order_info.get("symbol", "UNKNOWN")
                    self.telegram_notifier.notify_system_alert(
                        alert_type="POSITION_CREATION_FAILED",
                        message_text=(
                            f"Order {order_id} executed but position not created. "
                            f"Symbol: {symbol_hint}, Qty: {execution_qty}, "
                            f"Price: Rs {execution_price:.2f}. "
                            f"Reason: Missing orders_repo. Sell order will NOT be placed."
                        ),
                        severity="ERROR",
                        user_id=self.user_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to send position creation failure alert: {e}")
            return

        # BUG FIX: Initialize base_symbol early to ensure it's always defined in exception handlers
        base_symbol = None
        symbol = None

        try:
            # Issue #1 Fix: Enhanced symbol extraction with fallbacks
            symbol = order_info.get("symbol", "").upper()

            # Get order from database first (needed for fallback symbol extraction)
            db_order = None
            if order_info.get("db_order_id"):
                try:
                    db_order = self.orders_repo.get(order_info["db_order_id"])
                except Exception as e:
                    logger.warning(
                        f"Failed to get order by db_order_id {order_info['db_order_id']}: {e}. "
                        f"Will try broker_order_id fallback."
                    )

            if not db_order:
                # Try to find order by broker_order_id
                try:
                    db_order = self.orders_repo.get_by_broker_order_id(self.user_id, order_id)
                except Exception as e:
                    logger.warning(
                        f"Failed to get order by broker_order_id {order_id}: {e}. "
                        f"Will continue with symbol from order_info."
                    )

            # Issue #1 Fix: Fallback symbol extraction from db_order if not in order_info
            if not symbol and db_order:
                if hasattr(db_order, "symbol") and db_order.symbol:
                    symbol = db_order.symbol.upper()
                    logger.info(
                        f"Symbol not found in order_info for order {order_id}, "
                        f"using fallback from db_order: {symbol}"
                    )

            if not symbol:
                # Issue #1 Fix: Track metrics
                self._position_creation_metrics["failed_missing_symbol"] += 1
                logger.error(
                    f"CRITICAL: Cannot create position for order {order_id}: "
                    f"symbol not found in order_info or db_order. "
                    f"Execution: {execution_qty} @ Rs {execution_price:.2f}. "
                    f"This will prevent sell order placement."
                )
                # Issue #1 Fix: Send alert if telegram notifier available
                if self.telegram_notifier and self.telegram_notifier.enabled:
                    try:
                        self.telegram_notifier.notify_system_alert(
                            alert_type="POSITION_CREATION_FAILED",
                            message_text=(
                                f"Order {order_id} executed but position not created. "
                                f"Qty: {execution_qty}, Price: Rs {execution_price:.2f}. "
                                f"Reason: Symbol not found. Sell order will NOT be placed."
                            ),
                            severity="ERROR",
                            user_id=self.user_id,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send position creation failure alert: {e}")
                return

            # Use full symbol (already has suffix from broker/order)
            full_symbol = symbol.upper()
            base_symbol = full_symbol

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
                    f"No entry RSI found in order metadata for {full_symbol}, defaulting to 29.5"
                )

            # Check if position already exists
            # Use FOR UPDATE lock to prevent race conditions with concurrent reentry executions
            existing_pos = self.positions_repo.get_by_symbol_for_update(self.user_id, full_symbol)

            # Improvement: Check if position is closed - don't add reentry to closed positions
            if existing_pos and existing_pos.closed_at is not None:
                logger.warning(
                    f"Reentry order executed for closed position {full_symbol}. "
                    f"Position was closed at {existing_pos.closed_at}. "
                    f"Skipping reentry update to prevent reopening closed position."
                )
                return

            # Calculate execution time (use current time if not available)
            if ist_now:
                execution_time = ist_now()
            else:
                execution_time = datetime.now()
            if db_order and hasattr(db_order, "filled_at") and db_order.filled_at:
                execution_time = db_order.filled_at
            elif db_order and hasattr(db_order, "execution_time") and db_order.execution_time:
                execution_time = db_order.execution_time

            # EDGE CASE FIX #2: Check if this order was already processed to prevent duplicate position updates
            if existing_pos:
                # Check if order_id is already in reentries (indicates order was already processed)
                reentries_to_check = []
                if existing_pos.reentries:
                    if isinstance(existing_pos.reentries, dict):
                        reentries_to_check = list(existing_pos.reentries.get("reentries", []))
                    elif isinstance(existing_pos.reentries, list):
                        reentries_to_check = list(existing_pos.reentries)

                # Check if order_id matches any reentry
                order_already_processed = any(
                    r.get("order_id") == order_id for r in reentries_to_check
                )

                # Also check if position opened_at matches execution_time (within 1 hour window)
                # This handles cases where order was processed but reentry tracking wasn't set
                # IMPORTANT: Only skip if it's likely the FIRST order (no reentries exist yet)
                # For reentries, position quantity should be > execution_qty (includes previous orders)
                if not order_already_processed and existing_pos.opened_at and execution_time:
                    time_diff = abs((existing_pos.opened_at - execution_time).total_seconds())
                    # If position was opened within 1 hour of order execution, check if it's the first order
                    if time_diff < 3600:  # 1 hour window
                        # Only skip if:
                        # 1. Position quantity matches execution_qty (likely first order, not reentry)
                        # 2. AND no reentries exist yet (confirms it's the first order)
                        # For reentries, position quantity should be > execution_qty
                        qty_match = abs(existing_pos.quantity - execution_qty) <= max(
                            execution_qty * 0.1, 1
                        )
                        has_no_reentries = (
                            not existing_pos.reentries
                            or (
                                isinstance(existing_pos.reentries, list)
                                and len(existing_pos.reentries) == 0
                            )
                            or (
                                isinstance(existing_pos.reentries, dict)
                                and len(existing_pos.reentries.get("reentries", [])) == 0
                            )
                        )

                        # Only skip if quantities match AND no reentries exist (first order scenario)
                        if qty_match and has_no_reentries:
                            logger.info(
                                f"Order {order_id} for {full_symbol} appears to have already been processed "
                                f"(first order, no reentries). "
                                f"Position opened_at={existing_pos.opened_at}, "
                                f"order execution_time={execution_time}, "
                                f"time_diff={time_diff:.0f}s, qty_match={qty_match}. "
                                f"Skipping duplicate position update."
                            )
                            return
                        elif qty_match and not has_no_reentries:
                            # Position has reentries but quantities match - likely a reentry with same qty
                            # This is valid, proceed with reentry update
                            logger.debug(
                                f"Order {order_id} for {full_symbol}: quantities match but reentries exist. "
                                f"This is likely a reentry order. Proceeding with position update."
                            )

                if order_already_processed:
                    logger.info(
                        f"Order {order_id} for {full_symbol} already processed (found in reentries). "
                        f"Skipping duplicate position update."
                    )
                    return

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
                # Enhanced Hybrid Approach: Handle both old format (list) and
                # new format (dict with _cycle_metadata)
                if existing_pos.reentries:
                    if isinstance(existing_pos.reentries, dict):
                        # New format: extract reentries array from wrapper structure
                        reentries_array = list(existing_pos.reentries.get("reentries", []))
                    elif isinstance(existing_pos.reentries, list):
                        # Old format: reentries is directly a list
                        reentries_array = list(existing_pos.reentries)
                    else:
                        reentries_array = []
                else:
                    reentries_array = []
                last_reentry_price = existing_pos.last_reentry_price
                reentry_data = None  # Initialize to None, will be set if is_reentry is True

                # Check if this is a reentry: existing position OR order marked as reentry
                if db_order and db_order.entry_type == "reentry":
                    is_reentry = True
                elif existing_pos:  # Position already exists, so this is likely a reentry
                    is_reentry = True

                if is_reentry:
                    # Extract placed_at date for daily cap check (fixes issue where execution
                    # date is used instead of placement date for daily cap)
                    placed_at_date = None
                    if db_order and db_order.placed_at:
                        try:
                            # Normalize to IST for consistent date extraction
                            placed_at_dt = db_order.placed_at
                            if placed_at_dt.tzinfo is None:
                                # Naive datetime - assume IST
                                placed_at_dt = placed_at_dt.replace(tzinfo=IST)
                            elif placed_at_dt.tzinfo != IST:
                                # Different timezone - convert to IST
                                placed_at_dt = placed_at_dt.astimezone(IST)
                            placed_at_date = placed_at_dt.date().isoformat()
                        except Exception as e:
                            logger.warning(
                                f"Error extracting placed_at date for reentry {order_id}: {e}. "
                                f"Falling back to execution date."
                            )
                            # Fallback to execution date
                            placed_at_date = execution_time.date().isoformat()
                    else:
                        # Fallback: use execution date if placed_at not available
                        # (backward compatibility for orders without placed_at)
                        placed_at_date = execution_time.date().isoformat()

                    # Extract reentry data from order metadata or construct from execution data
                    # Enhanced Hybrid Approach: Include cycle number from order metadata
                    reentry_data = None
                    if db_order and db_order.order_metadata:
                        metadata = (
                            db_order.order_metadata
                            if isinstance(db_order.order_metadata, dict)
                            else {}
                        )
                        # Extract reentry fields from metadata
                        reentry_level = (
                            metadata.get("rsi_level")
                            or metadata.get("level")
                            or metadata.get("reentry_level")
                        )
                        reentry_rsi = metadata.get("rsi") or metadata.get("rsi10") or entry_rsi
                        reentry_price = metadata.get("price") or execution_price
                        reentry_cycle = metadata.get(
                            "cycle"
                        )  # Enhanced Hybrid Approach: Get cycle number

                        # Construct reentry data matching trade history structure
                        reentry_data = {
                            "qty": int(execution_qty),
                            "level": int(reentry_level) if reentry_level is not None else None,
                            "rsi": float(reentry_rsi) if reentry_rsi is not None else None,
                            "price": float(reentry_price),
                            "time": execution_time.isoformat(),  # Execution time
                            "placed_at": placed_at_date,  # Placement date (for daily cap check)
                            "order_id": order_id,  # Track which order created this reentry
                            "cycle": (
                                int(reentry_cycle) if reentry_cycle is not None else None
                            ),  # Enhanced Hybrid Approach: Store cycle number
                        }
                    else:
                        # Fallback: construct minimal reentry data from execution
                        # Try to get cycle from existing position metadata
                        reentry_cycle = None
                        if existing_pos and existing_pos.reentries:
                            # Get cycle from position metadata (if available)
                            # Enhanced Hybrid Approach: Extract cycle from _cycle_metadata structure
                            if isinstance(existing_pos.reentries, dict):
                                cycle_meta = existing_pos.reentries.get("_cycle_metadata", {})
                                if isinstance(cycle_meta, dict):
                                    reentry_cycle = cycle_meta.get("current_cycle")

                        reentry_data = {
                            "qty": int(execution_qty),
                            "level": None,
                            "rsi": float(entry_rsi) if entry_rsi else None,
                            "price": float(execution_price),
                            "time": execution_time.isoformat(),  # Execution time
                            "placed_at": placed_at_date,  # Placement date (for daily cap check)
                            "order_id": order_id,  # Track which order created this reentry
                            "cycle": (
                                int(reentry_cycle) if reentry_cycle is not None else None
                            ),  # Enhanced Hybrid Approach: Store cycle number
                        }

                    # Improvement: Validate reentry data before writing
                    if not self._validate_reentry_data(reentry_data):
                        logger.error(
                            f"Invalid reentry data for {full_symbol} (order_id: {order_id}). "
                            f"Skipping reentry update to prevent data corruption."
                        )
                        # Don't update reentry fields, but still update quantity and avg_price
                        is_reentry = False
                        reentry_count = existing_pos.reentry_count or 0
                        # Create a copy to avoid modifying the original list
                        reentries_array = (
                            list(existing_pos.reentries) if existing_pos.reentries else []
                        )
                        last_reentry_price = existing_pos.last_reentry_price
                    else:
                        # Ensure reentries_array is a list
                        if not isinstance(reentries_array, list):
                            reentries_array = []

                        # Improvement: Check for duplicate reentry (same order_id or very
                        # similar timestamp+qty). This prevents duplicate entries if order
                        # is processed multiple times
                        existing_reentry = next(
                            (
                                r
                                for r in reentries_array
                                if r.get("order_id") == order_id
                                or (
                                    r.get("time") == reentry_data["time"]
                                    and r.get("qty") == reentry_data["qty"]
                                    and abs(r.get("price", 0) - reentry_data["price"])
                                    < 0.01  # noqa: PLR2004
                                )
                            ),
                            None,
                        )
                        if existing_reentry:
                            logger.warning(
                                f"Duplicate reentry detected for {full_symbol} "
                                f"(order_id: {order_id}). Skipping to prevent duplicate entry."
                            )
                            # Don't update reentry fields, but still update quantity and avg_price
                            is_reentry = False
                            reentry_count = existing_pos.reentry_count or 0
                            # Create a copy to avoid modifying the original list
                            reentries_array = (
                                list(existing_pos.reentries) if existing_pos.reentries else []
                            )
                            last_reentry_price = existing_pos.last_reentry_price
                        else:
                            # Append new reentry (data is validated)
                            reentries_array.append(reentry_data)
                            reentry_count = len(reentries_array)
                            last_reentry_price = execution_price

                    logger.info(
                        f"Reentry detected for {full_symbol}: Adding reentry #{reentry_count} "
                        f"(qty: {execution_qty}, price: Rs {execution_price:.2f})"
                    )
                    # Note: Database is updated here (source of truth).
                    # JSON backup is synced during reconciliation via _load_trades_history()
                    # which reads from database and writes to JSON.

                # Wrap position updates in a transaction for atomicity
                # This ensures position update and integrity fix happen together or not at all
                # If already in a transaction, SQLAlchemy will use savepoints automatically
                with transaction(self.positions_repo.db):
                    # Race Condition Fix #4: Re-check if position is closed just before updating
                    # This prevents reopening a position that was closed during processing
                    # (e.g., if sell order executed while reentry was being processed)
                    current_position = self.positions_repo.get_by_symbol_for_update(
                        self.user_id, full_symbol
                    )
                    if current_position and current_position.closed_at is not None:
                        logger.warning(
                            f"Reentry order execution aborted for {full_symbol}: "
                            f"Position was closed at {current_position.closed_at} "
                            f"while reentry was being processed. "
                            f"Skipping update to prevent reopening closed position."
                        )
                        # Transaction will rollback automatically
                        return

                    # Flaw #8 Fix: Re-check for duplicate reentry just before updating
                    # This prevents duplicate entries if two processes process the same
                    # order concurrently. We already have the locked read from the
                    # closed_at check above
                    if is_reentry and current_position and reentry_data:
                        # Get latest reentries array from the locked position
                        # Enhanced Hybrid Approach: Handle both old and new format
                        if current_position.reentries:
                            if isinstance(current_position.reentries, dict):
                                latest_reentries = current_position.reentries.get("reentries", [])
                            elif isinstance(current_position.reentries, list):
                                latest_reentries = current_position.reentries
                            else:
                                latest_reentries = []
                        else:
                            latest_reentries = []

                        # Re-check for duplicate using latest data
                        # Only check if reentry_data is defined (it should be if is_reentry is True)
                        duplicate_found = None
                        if reentry_data:
                            duplicate_found = next(
                                (
                                    r
                                    for r in latest_reentries
                                    if r.get("order_id") == order_id
                                    or (
                                        r.get("time") == reentry_data["time"]
                                        and r.get("qty") == reentry_data["qty"]
                                        and abs(r.get("price", 0) - reentry_data["price"])
                                        < 0.01  # noqa: PLR2004
                                    )
                                ),
                                None,
                            )

                        if duplicate_found:
                            logger.warning(
                                f"Duplicate reentry detected for {full_symbol} "
                                f"(order_id: {order_id}) during final check. "
                                f"Another process may have already added this reentry. "
                                f"Skipping entire update to prevent duplicate entry "  # noqa: E501
                                f"and double-counting."
                            )
                            # If duplicate found, another process already processed this order
                            # and updated the position (including quantity and avg_price)
                            # Skip the entire update to avoid duplicate entry and double-counting
                            # Transaction will rollback automatically (no changes made)
                            return

                    # Flaw #9 Fix: Try broker API call BEFORE updating database
                    # If broker API fails, we still update position (primary operation -
                    # order executed). This prevents losing the position update, but
                    # creates temporary inconsistency. The sell order update will be
                    # retried later via periodic mismatch check (Flaw #7 fix)
                    sell_order_update_success = True
                    if new_qty > existing_qty and self.sell_manager:
                        try:
                            # Check for existing sell order
                            existing_orders = self.sell_manager.get_existing_sell_orders()
                            if full_symbol.upper() in existing_orders:
                                existing_order = existing_orders[full_symbol.upper()]
                                existing_order_qty = existing_order.get("qty", 0)
                                existing_order_price = existing_order.get("price", 0)
                                existing_order_id = existing_order.get("order_id")

                                # Update sell order if quantity doesn't match position
                                if existing_order_id and new_qty != existing_order_qty:
                                    if new_qty > existing_order_qty:
                                        logger.info(
                                            f"Reentry detected for {full_symbol}: "
                                            f"Updating sell order quantity from {existing_order_qty} "  # noqa: E501
                                            f"to {new_qty} (Order ID: {existing_order_id})"
                                        )
                                    else:
                                        logger.info(
                                            f"Sell order quantity mismatch for {full_symbol}: "
                                            f"Position={new_qty}, Sell order={existing_order_qty}. "
                                            f"Updating to match position "  # noqa: E501
                                            f"(Order ID: {existing_order_id})"
                                        )

                                    # Flaw #9 Fix: Try broker API call BEFORE updating database
                                    # If it fails, we'll still update position (primary operation)
                                    # but log warning for retry later (Flaw #7 fix handles this)
                                    sell_order_update_success = self.sell_manager.update_sell_order(
                                        order_id=str(existing_order_id),
                                        symbol=full_symbol,
                                        qty=int(new_qty),
                                        new_price=existing_order_price,
                                    )

                                    if sell_order_update_success:
                                        logger.info(
                                            f"Successfully updated sell order for {full_symbol}: "
                                            f"{existing_order_qty} -> {new_qty} shares "
                                            f"@ Rs {existing_order_price:.2f}"
                                        )
                                    else:
                                        logger.warning(
                                            f"Failed to update sell order for {full_symbol} "
                                            f"via broker API. Position will still be updated "
                                            f"(primary operation - order executed). "
                                            f"Sell order will be retried later via periodic "
                                            f"mismatch check (Flaw #7 fix)."
                                        )
                        except Exception as e:
                            # Broker API call failed - log warning but continue with position update
                            logger.warning(
                                f"Error updating sell order after reentry for {full_symbol}: {e}. "
                                f"Position will still be updated "  # noqa: E501
                                f"(primary operation - order executed). "
                                f"Sell order will be retried later via periodic mismatch check "
                                f"(Flaw #7 fix)."
                            )
                            sell_order_update_success = False

                    # Enhanced Hybrid Approach: Preserve cycle metadata structure when
                    # updating reentries
                    reentries_to_store = None
                    if is_reentry:
                        # Check if existing reentries has cycle metadata structure
                        if (
                            isinstance(existing_pos.reentries, dict)
                            and "_cycle_metadata" in existing_pos.reentries
                        ):
                            # Preserve existing cycle metadata structure
                            reentries_to_store = {
                                "_cycle_metadata": existing_pos.reentries["_cycle_metadata"],
                                "reentries": reentries_array,
                            }
                        else:
                            # Old format or no metadata - store as list (backward compatible)
                            # Cycle metadata will be added by _determine_reentry_level on next check
                            reentries_to_store = reentries_array

                    self.positions_repo.upsert(
                        user_id=self.user_id,
                        symbol=full_symbol,
                        quantity=new_qty,
                        avg_price=new_avg_price,
                        opened_at=existing_pos.opened_at,  # Preserve original open time
                        entry_rsi=entry_rsi_to_set,  # Only set if not already set
                        reentry_count=reentry_count if is_reentry else None,
                        reentries=reentries_to_store,
                        last_reentry_price=last_reentry_price if is_reentry else None,
                        auto_commit=False,  # Transaction handles commit
                    )

                    # Improvement: Verify data integrity after update
                    # Use FOR UPDATE lock to prevent race conditions during integrity check
                    if is_reentry:
                        updated_position = self.positions_repo.get_by_symbol_for_update(
                            self.user_id, full_symbol
                        )
                        if updated_position:
                            actual_count = len(updated_position.reentries or [])
                            if updated_position.reentry_count != actual_count:
                                logger.warning(
                                    f"Reentry count mismatch for {full_symbol}: "
                                    f"count={updated_position.reentry_count}, "  # noqa: E501
                                    f"array_length={actual_count}. "
                                    f"Fixing..."
                                )
                                # Fix the mismatch - preserve the last_reentry_price we just set
                                self.positions_repo.upsert(
                                    user_id=self.user_id,
                                    symbol=full_symbol,
                                    reentry_count=actual_count,
                                    # Preserve other fields including the newly set
                                    # last_reentry_price
                                    quantity=updated_position.quantity,
                                    avg_price=updated_position.avg_price,
                                    opened_at=updated_position.opened_at,
                                    entry_rsi=updated_position.entry_rsi,
                                    reentries=updated_position.reentries,
                                    last_reentry_price=last_reentry_price,  # Use value we set
                                    auto_commit=False,  # Transaction handles commit
                                )
                                # Refresh position after fix
                                self.positions_repo.db.refresh(updated_position)

                logger.info(
                    f"Updated position for {full_symbol}: qty {existing_qty} -> {new_qty}, "
                    f"avg_price Rs {existing_avg_price:.2f} -> Rs {new_avg_price:.2f}"
                    + (f", reentry_count: {reentry_count}" if is_reentry else "")
                )
            else:
                # Create new position (wrapped in transaction for consistency)
                # If already in a transaction, SQLAlchemy will use savepoints automatically
                with transaction(self.positions_repo.db):
                    self.positions_repo.upsert(
                        user_id=self.user_id,
                        symbol=full_symbol,
                        quantity=execution_qty,
                        avg_price=execution_price,
                        opened_at=execution_time,
                        entry_rsi=entry_rsi,
                        auto_commit=False,  # Transaction handles commit
                    )
                logger.info(
                    f"Created position for {full_symbol}: qty={execution_qty}, "
                    f"price=Rs {execution_price:.2f}, entry_rsi={entry_rsi:.2f}"
                )

            # Note: Order status is already correct (ONGOING legacy or CLOSED = executed order)
            # According to design: PENDING → CLOSED (when executed); position ongoing is in Positions.
            # If order has execution_price and status is ONGOING or CLOSED, that's the correct state.
            # We're only fixing the missing position creation here.

        except ValueError as e:
            # Issue #1 Fix: Track metrics and send alert
            self._position_creation_metrics["failed_exception"] += 1
            # BUG FIX: Use fallback symbol if base_symbol not set
            symbol_hint = base_symbol or symbol or order_info.get("symbol", "UNKNOWN") or order_id
            logger.error(
                f"Invalid data for position update: {symbol_hint}, order_id={order_id}: {e}. "
                f"Execution: {execution_qty} @ Rs {execution_price:.2f}. "
                f"This will prevent sell order placement.",
                exc_info=True,
            )
            # Issue #1 Fix: Send alert if telegram notifier available
            if self.telegram_notifier and self.telegram_notifier.enabled:
                try:
                    self.telegram_notifier.notify_system_alert(
                        alert_type="POSITION_CREATION_FAILED",
                        message_text=(
                            f"Order {order_id} executed but position not created. "
                            f"Symbol: {symbol_hint}, Qty: {execution_qty}, "
                            f"Price: Rs {execution_price:.2f}. "
                            f"Reason: Invalid data - {str(e)}. "
                            f"Sell order will NOT be placed."
                        ),
                        severity="ERROR",
                        user_id=self.user_id,
                    )
                except Exception as notify_err:
                    logger.warning(f"Failed to send position creation failure alert: {notify_err}")
        except KeyError as e:
            # Issue #1 Fix: Track metrics and send alert
            self._position_creation_metrics["failed_exception"] += 1
            # BUG FIX: Use fallback symbol if base_symbol not set
            symbol_hint = base_symbol or symbol or order_info.get("symbol", "UNKNOWN") or order_id
            logger.error(
                f"Missing required field in order_info for {symbol_hint}, "
                f"order_id={order_id}: {e}. "
                f"Execution: {execution_qty} @ Rs {execution_price:.2f}. "
                f"This will prevent sell order placement.",
                exc_info=True,
            )
            # Issue #1 Fix: Send alert if telegram notifier available
            if self.telegram_notifier and self.telegram_notifier.enabled:
                try:
                    self.telegram_notifier.notify_system_alert(
                        alert_type="POSITION_CREATION_FAILED",
                        message_text=(
                            f"Order {order_id} executed but position not created. "
                            f"Symbol: {symbol_hint}, Qty: {execution_qty}, "
                            f"Price: Rs {execution_price:.2f}. "
                            f"Reason: Missing field - {str(e)}. "
                            f"Sell order will NOT be placed."
                        ),
                        severity="ERROR",
                        user_id=self.user_id,
                    )
                except Exception as notify_err:
                    logger.warning(f"Failed to send position creation failure alert: {notify_err}")
        except Exception as e:
            # Issue #1 Fix: Track metrics and send alert
            self._position_creation_metrics["failed_exception"] += 1
            # BUG FIX: Use fallback symbol if base_symbol not set
            symbol_hint = base_symbol or symbol or order_info.get("symbol", "UNKNOWN") or order_id
            logger.error(
                f"Unexpected error updating position for {symbol_hint}, order_id={order_id}: {e}. "
                f"Execution: {execution_qty} @ Rs {execution_price:.2f}. "
                f"This will prevent sell order placement.",
                exc_info=True,
            )
            # Issue #1 Fix: Send alert if telegram notifier available
            if self.telegram_notifier and self.telegram_notifier.enabled:
                try:
                    self.telegram_notifier.notify_system_alert(
                        alert_type="POSITION_CREATION_FAILED",
                        message_text=(
                            f"Order {order_id} executed but position not created. "
                            f"Symbol: {symbol_hint}, Qty: {execution_qty}, "
                            f"Price: Rs {execution_price:.2f}. "
                            f"Reason: Unexpected error - {str(e)}. "
                            f"Sell order will NOT be placed."
                        ),
                        severity="ERROR",
                        user_id=self.user_id,
                    )
                except Exception as notify_err:
                    logger.warning(f"Failed to send position creation failure alert: {notify_err}")
        else:
            # Issue #1 Fix: Track successful position creation
            self._position_creation_metrics["success"] += 1

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
        # Note: get_orders() is already wrapped with timeout (30s) in orders.py
        broker_orders = None
        try:
            orders_response = self.orders.get_orders() if self.orders else None
            if orders_response is None:
                # Timeout or error occurred - log and continue with empty orders list
                logger.warning(
                    "get_orders() returned None (likely timeout or error). "
                    "Continuing monitoring with empty orders list."
                )
                broker_orders = []
            else:
                broker_orders = orders_response.get("data", []) if orders_response else []
        except ValueError as e:
            logger.error(f"Invalid data when fetching broker orders: {e}", exc_info=True)
            broker_orders = []
        except Exception as e:
            logger.error(f"Unexpected error fetching broker orders: {e}", exc_info=True)
            broker_orders = []

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

    def check_and_place_sell_orders_for_new_holdings(  # noqa: PLR0912, PLR0915
        self,
    ) -> int:
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
            # Get today's date
            local_ist_now = ist_now
            if local_ist_now is None:
                from src.infrastructure.db.timezone_utils import (
                    ist_now as local_ist_now,  # noqa: PLC0415
                )
            today = local_ist_now().date()
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

            # Get all executed buy orders (ONGOING legacy or CLOSED) executed today
            # We'll check orders that have execution_time >= today_start
            all_orders, _ = self.orders_repo.list(self.user_id)
            executed_buy_orders = [
                o
                for o in all_orders
                if o.status in (DbOrderStatus.ONGOING, DbOrderStatus.CLOSED)
                and o.side.lower() == "buy"
            ]

            newly_executed_orders = []
            skipped_orders = []
            for order in executed_buy_orders:
                # Skip manual orders - system does not track manual buys
                if order.orig_source and order.orig_source.lower() == "manual":
                    skipped_orders.append(f"{order.symbol}: manual order (not tracked)")
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

            # Guard against duplicate DB rows for the same broker execution.
            # Keep a single order per (broker_order_id, execution_qty) so downstream
            # position creation / sell-placement logic does not run twice in one cycle.
            deduped_orders: dict[str, Any] = {}
            duplicate_count = 0
            for order in newly_executed_orders:
                execution_qty = getattr(order, "execution_qty", None) or 0
                try:
                    normalized_exec_qty = int(float(execution_qty))
                except (TypeError, ValueError):
                    normalized_exec_qty = 0
                order_identity = str(
                    getattr(order, "broker_order_id", None) or getattr(order, "order_id", None) or ""
                ).strip()
                if not order_identity:
                    # Fallback identity for legacy rows without broker ids.
                    order_identity = f"db:{getattr(order, 'id', '')}"
                dedup_key = f"{order_identity}:{normalized_exec_qty}"

                if dedup_key in deduped_orders:
                    duplicate_count += 1
                    existing = deduped_orders[dedup_key]
                    existing_updated = getattr(existing, "updated_at", None) or getattr(
                        existing, "execution_time", None
                    )
                    current_updated = getattr(order, "updated_at", None) or getattr(
                        order, "execution_time", None
                    )
                    if current_updated and (not existing_updated or current_updated > existing_updated):
                        deduped_orders[dedup_key] = order
                else:
                    deduped_orders[dedup_key] = order

            if duplicate_count > 0:
                logger.info(
                    f"Deduplicated {duplicate_count} duplicate executed buy order row(s) "
                    "by broker_order_id+execution_qty."
                )
            newly_executed_orders = list(deduped_orders.values())

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
                symbol.upper() for symbol in existing_sell_orders.keys()  # Already full symbols
            }

            # Get currently tracked sell orders
            active_sell_symbols = {
                symbol.upper()
                for symbol in self.sell_manager.active_sell_orders.keys()  # Already full symbols
            }

            # Optimization: Fetch orders once and reuse for has_completed_sell_order checks
            all_orders_response = None
            try:
                all_orders_response = self.sell_manager.orders.get_orders()
            except Exception as e:
                logger.debug(f"Failed to fetch orders for place_sell_orders_for_new_positions: {e}")

            # Build current sellable quantity map from holdings to avoid re-placing
            # sells for non-sellable/T1-only inventory.
            sellable_qty_map: dict[str, int] = {}
            try:
                holdings_response = (
                    self.sell_manager.portfolio.get_holdings()
                    if self.sell_manager and hasattr(self.sell_manager, "portfolio")
                    else None
                )
                holdings_rows = []
                if isinstance(holdings_response, dict):
                    if isinstance(holdings_response.get("data"), list):
                        holdings_rows = holdings_response.get("data", [])
                    elif isinstance(holdings_response.get("holdings"), list):
                        holdings_rows = holdings_response.get("holdings", [])
                elif isinstance(holdings_response, list):
                    holdings_rows = holdings_response

                for h in holdings_rows:
                    if not isinstance(h, dict):
                        continue
                    symbol = (
                        h.get("tradingSymbol")
                        or h.get("symbol")
                        or h.get("trdSym")
                        or h.get("securitySymbol")
                        or ""
                    )
                    if not symbol:
                        continue
                    full_symbol = str(symbol).upper()
                    base_symbol = full_symbol.split("-")[0]
                    try:
                        # Prefer true sellable quantity. Fallback to quantity only when
                        # sellable fields are entirely absent in payload.
                        has_sellable_field = any(
                            k in h
                            for k in (
                                "sellableQuantity",
                                "sellQty",
                                "sellableQty",
                                "sellable_quantity",
                            )
                        )
                        if has_sellable_field:
                            raw_qty = (
                                h.get("sellableQuantity")
                                or h.get("sellQty")
                                or h.get("sellableQty")
                                or h.get("sellable_quantity")
                                or 0
                            )
                        else:
                            raw_qty = h.get("quantity") or h.get("qty") or 0
                        qty = int(float(raw_qty))
                    except (TypeError, ValueError):
                        qty = 0
                    qty = max(qty, 0)
                    sellable_qty_map[full_symbol] = qty
                    sellable_qty_map[base_symbol] = qty
            except Exception as e:
                logger.debug(f"Failed to build sellable quantity map for new holdings: {e}")
            has_sellable_data = len(sellable_qty_map) > 0

            orders_placed = 0

            for db_order in newly_executed_orders:
                try:
                    full_symbol = db_order.symbol.upper()  # Already full symbol from orders table

                    # Skip if already has sell order
                    if full_symbol in existing_symbols or full_symbol in active_sell_symbols:
                        logger.info(f"Skipping {full_symbol}: Already has sell order")
                        continue

                    # Check if position already has a completed sell order
                    # Reuse orders data to avoid duplicate API calls
                    completed_order_info = self.sell_manager.has_completed_sell_order(
                        full_symbol, all_orders_response
                    )
                    if completed_order_info:
                        logger.debug(f"Skipping {full_symbol}: Already has completed sell order")
                        continue

                    # Convert order to trade format
                    # Get ticker from order metadata or construct from symbol
                    ticker = None
                    if db_order.order_metadata and isinstance(db_order.order_metadata, dict):
                        ticker = db_order.order_metadata.get("ticker")

                    if not ticker:
                        # Use helper function to create ticker from full symbol
                        from modules.kotak_neo_auto_trader.utils.symbol_utils import (
                            get_ticker_from_full_symbol,
                        )

                        ticker = get_ticker_from_full_symbol(full_symbol)

                    # Get execution price and quantity
                    execution_price = (
                        getattr(db_order, "execution_price", None)
                        or db_order.avg_price
                        or db_order.price
                    )
                    execution_qty = getattr(db_order, "execution_qty", None)

                    if not execution_price or not execution_qty or execution_qty <= 0:
                        logger.warning(
                            f"Skipping {full_symbol}: Invalid execution price or quantity "
                            "(execution_qty missing from execution sync)"
                        )
                        continue

                    # Do not place sells when holdings are not sellable at broker side.
                    # This avoids repeated RMS rejections and quantity amplification loops.
                    sellable_qty = sellable_qty_map.get(full_symbol)
                    if sellable_qty is None:
                        sellable_qty = sellable_qty_map.get(full_symbol.split("-")[0])
                    if has_sellable_data and (sellable_qty is None or sellable_qty <= 0):
                        logger.info(
                            f"Skipping {full_symbol}: holdings sellableQuantity is 0/unknown "
                            "(likely T1/not yet sellable)."
                        )
                        continue

                    # FIX: Ensure position exists before placing sell order
                    # If position doesn't exist or is closed, create it from the executed order
                    # This handles cases where buy order executed but position was never created
                    # (e.g., if order was ONGOING when service started)
                    existing_position = None
                    if self.positions_repo:
                        try:
                            # First check for open position
                            existing_position = self.positions_repo.get_by_symbol(
                                self.user_id, full_symbol
                            )
                            # If no open position, check if closed position exists
                            if not existing_position:
                                existing_position = self.positions_repo.get_by_symbol_any(
                                    self.user_id, full_symbol, include_closed=True
                                )
                        except Exception as pos_check_err:
                            logger.warning(
                                f"Error checking position for {full_symbol}: {pos_check_err}"
                            )

                    # Create position if missing or closed
                    if not existing_position or (
                        existing_position and existing_position.closed_at is not None
                    ):
                        # Position doesn't exist or is closed - create new position from executed order
                        # This ensures position exists before placing sell order
                        logger.info(
                            f"Position missing or closed for {full_symbol} (order {db_order.broker_order_id}). "
                            f"Creating position before placing sell order."
                        )
                        try:
                            # Use existing _create_position_from_executed_order method
                            # This handles reentry logic, closed positions, and transactions correctly
                            order_info = {
                                "symbol": full_symbol,
                                "db_order_id": db_order.id,
                            }
                            self._create_position_from_executed_order(
                                str(db_order.broker_order_id or db_order.order_id),
                                order_info,
                                execution_price,
                                execution_qty,
                            )
                            logger.info(
                                f"Created/updated position for {full_symbol} from ONGOING order "
                                f"{db_order.broker_order_id}"
                            )
                        except Exception as pos_create_err:
                            logger.error(
                                f"Failed to create position for {full_symbol}: {pos_create_err}. "
                                f"Skipping sell order placement.",
                                exc_info=True,
                            )
                            continue

                    # Uniform sell quantity rule: qty = min(db_open_position_qty, broker_sellable_qty)
                    current_open_position = None
                    db_open_qty = 0.0
                    if self.positions_repo:
                        try:
                            current_open_position = self.positions_repo.get_by_symbol(
                                self.user_id, full_symbol
                            )
                            if current_open_position and current_open_position.closed_at is None:
                                db_open_qty = float(current_open_position.quantity or 0)
                        except Exception as pos_qty_err:
                            logger.warning(
                                f"Error fetching open position qty for {full_symbol}: {pos_qty_err}"
                            )

                    base_qty = float(db_open_qty) if db_open_qty > 0 else float(execution_qty)
                    if has_sellable_data and sellable_qty is not None:
                        place_qty = min(base_qty, float(sellable_qty))
                    else:
                        # Fallback when holdings payload is unavailable in this cycle.
                        # Keep execution-based sizing to avoid total failure due temporary DB read issues.
                        place_qty = base_qty
                    if place_qty <= 0:
                        logger.info(
                            f"Skipping {full_symbol}: computed sell qty is 0 "
                            f"(db_open_qty={db_open_qty}, execution_qty={execution_qty}, "
                            f"sellable_qty={sellable_qty})."
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
                        "symbol": full_symbol,  # ✅ Full symbol for matching
                        "ticker": ticker,
                        "qty": int(place_qty),
                        "entry_price": execution_price,
                        "placed_symbol": db_order.symbol,  # Keep original broker symbol (full)
                        "entry_time": (
                            order_execution_time.isoformat()
                            if order_execution_time
                            else ist_now().isoformat()
                        ),
                    }

                    # Issue #3 Fix: Get current EMA9 with retry and fallback
                    broker_sym = db_order.symbol
                    ema9 = self.sell_manager._get_ema9_with_retry(
                        ticker, broker_symbol=broker_sym, symbol=full_symbol
                    )
                    if not ema9:
                        logger.error(
                            f"Issue #3: Skipping {full_symbol}: Failed to calculate EMA9 after retries "
                            f"and fallback. Sell order cannot be placed."
                        )
                        continue

                    # Issue #4: EMA9 validation check removed - all positions will get sell orders
                    # This enables RSI 50 exit mechanism to work for all positions
                    # Note: Positions may be sold at loss if EMA9 is below entry price

                    # Place sell order
                    logger.info(
                        f"Placing sell order for {full_symbol}: qty={int(place_qty)}, "
                        f"entry_price={execution_price:.2f}, ema9={ema9:.2f}, "
                        f"db_open_qty={db_open_qty}, sellable_qty={sellable_qty}"
                    )
                    order_id = self.sell_manager.place_sell_order(trade, ema9)

                    if order_id:
                        logger.info(f"Successfully placed sell order for {full_symbol}: {order_id}")
                        # Track the order
                        self.sell_manager._register_order(
                            symbol=full_symbol,
                            order_id=order_id,
                            target_price=ema9,
                            qty=int(place_qty),
                            ticker=ticker,
                            placed_symbol=broker_sym,
                        )
                        self.sell_manager.lowest_ema9[full_symbol] = ema9
                        orders_placed += 1
                        logger.info(
                            f"Placed sell order for newly executed holding: {full_symbol} "
                            f"(Order ID: {order_id}, Target: Rs {ema9:.2f})"
                        )

                except Exception as e:
                    logger.error(f"Error placing sell order for {db_order.symbol}: {e}")

            if orders_placed > 0:
                logger.info(f"Placed {orders_placed} sell orders for newly executed holdings")

            return orders_placed

        except ValueError as e:
            logger.error(f"Invalid data when checking for new holdings: {e}", exc_info=True)
            return 0
        except Exception as e:
            logger.error(f"Unexpected error checking for new holdings: {e}", exc_info=True)
            return 0
