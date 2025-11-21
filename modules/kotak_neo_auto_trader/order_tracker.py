#!/usr/bin/env python3
"""
Order Tracker Module
Manages pending orders and tracks their status lifecycle.

SOLID Principles:
- Single Responsibility: Only manages order tracking and status
- Interface Segregation: Clean API for order operations
- Dependency Inversion: Abstract order status checking
"""

import json
import os

# Use existing project logger
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger


class OrderTracker:
    """
    Tracks pending orders from placement to execution/rejection.
    Maintains order status and provides status verification.

    Phase 7: Supports dual-write (JSON + DB) and dual-read (DB first, JSON fallback).
    """

    def __init__(
        self,
        data_dir: str = "data",
        db_session=None,
        user_id: int | None = None,
        use_db: bool = True,
        db_only_mode: bool = False,  # Phase 11: DB-only mode (no JSON fallback)
    ):
        """
        Initialize order tracker.

        Phase 7: Added database support for dual-write/dual-read.
        Phase 11: Added db_only_mode to remove JSON dependency.

        Args:
            data_dir: Directory for storing pending orders data
            db_session: Optional database session for DB storage
            user_id: Optional user ID for filtering orders
            use_db: Whether to use database (default: True if db_session provided)
            db_only_mode: If True, use DB only (no JSON read/write). Default: False for backward compatibility.
        """
        self.data_dir = data_dir
        self.pending_file = os.path.join(data_dir, "pending_orders.json")
        self.db_session = db_session
        self.user_id = user_id
        self.use_db = use_db and db_session is not None and user_id is not None
        self.db_only_mode = db_only_mode and self.use_db  # Only enable if DB is available

        # Initialize orders repository if DB is available
        self.orders_repo = None
        if self.use_db:
            try:
                from src.infrastructure.persistence.orders_repository import OrdersRepository

                self.orders_repo = OrdersRepository(db_session)
                mode_str = "DB-only mode" if self.db_only_mode else "dual-write mode"
                logger.info(f"OrderTracker initialized with database support ({mode_str})")
            except Exception as e:
                logger.warning(f"Failed to initialize OrdersRepository: {e}")
                self.use_db = False
                self.orders_repo = None
                self.db_only_mode = False

        # Phase 11: Only ensure data file if not in DB-only mode
        if not self.db_only_mode:
            self._ensure_data_file()

    def _ensure_data_file(self) -> None:
        """Create pending orders file if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

        if not os.path.exists(self.pending_file):
            self._save_pending_data({"orders": []})

    def _load_pending_data(self) -> dict[str, Any]:
        """Load pending orders from file."""
        try:
            with open(self.pending_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load pending orders: {e}")
            return {"orders": []}

    def _save_pending_data(self, data: dict[str, Any]) -> None:
        """Save pending orders to file."""
        try:
            with open(self.pending_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save pending orders: {e}")

    @staticmethod
    def extract_order_id(response: dict[str, Any]) -> str | None:
        """
        Extract order ID from broker response.

        Handles multiple response formats from Kotak Neo API:
        - {'data': {'neoOrdNo': 'ORDER-123'}}
        - {'neoOrdNo': 'ORDER-123'}
        - {'orderId': 'ORDER-123'}

        Args:
            response: Response dict from broker API

        Returns:
            Order ID string or None if not found
        """
        if not isinstance(response, dict):
            return None

        # Try data field first
        data = response.get("data", response)

        # Try common field names (including Kotak Neo's nOrdNo)
        order_id = (
            data.get("nOrdNo")
            or data.get("neoOrdNo")
            or data.get("orderId")
            or data.get("order_id")
            or data.get("OrdId")
            or data.get("ordId")
        )

        if order_id:
            logger.debug(f"Extracted order ID: {order_id}")
            return str(order_id)

        logger.warning("Could not extract order ID from response")
        return None

    def add_pending_order(
        self,
        order_id: str,
        symbol: str,
        ticker: str,
        qty: int,
        order_type: str = "MARKET",
        variety: str = "AMO",
        price: float = 0.0,
        entry_type: str | None = None,
        order_metadata: dict | None = None,
    ) -> None:
        """
        Add order to pending tracking.

        Phase 7: Supports dual-write (JSON + DB).

        Args:
            order_id: Order ID from broker
            symbol: Trading symbol
            ticker: Full ticker symbol
            qty: Order quantity
            order_type: MARKET/LIMIT
            variety: AMO/REGULAR
            price: Limit price (0 for market orders)
        """
        # Phase 7: Check DB first if available
        if self.use_db and self.orders_repo:
            try:
                # Check if order already exists in DB
                existing_db_order = self.orders_repo.get_by_broker_order_id(
                    self.user_id, order_id
                ) or self.orders_repo.get_by_order_id(self.user_id, order_id)

                if existing_db_order:
                    logger.debug(
                        f"Order {order_id} already exists in database. "
                        f"Skipping duplicate add for {symbol}."
                    )
                    # Phase 11: In DB-only mode, skip JSON write
                    if self.db_only_mode:
                        return
                else:
                    # Create order in DB
                    from src.infrastructure.db.models import OrderStatus as DbOrderStatus

                    db_order = self.orders_repo.create_amo(
                        user_id=self.user_id,
                        symbol=symbol,
                        side="buy",  # Pending orders are typically buy orders
                        order_type=order_type.lower(),
                        quantity=qty,
                        price=price if price > 0 else None,
                        order_id=order_id,
                        broker_order_id=order_id,
                        entry_type=entry_type,
                        order_metadata=order_metadata,
                    )
                    # Update status to PENDING_EXECUTION if it's an AMO order
                    if variety == "AMO":
                        db_order.status = DbOrderStatus.PENDING_EXECUTION
                        self.orders_repo.update(db_order)
                    logger.debug(f"Added order {order_id} to database")
                    # Phase 11: In DB-only mode, skip JSON write
                    if self.db_only_mode:
                        logger.info(
                            f"Added to pending orders: {symbol} (order_id: {order_id}, qty: {qty})"
                        )
                        return
            except Exception as e:
                logger.warning(f"Failed to write order to database: {e}")
                # Phase 11: In DB-only mode, fail if DB write fails
                if self.db_only_mode:
                    raise

        # Phase 11: Skip JSON write in DB-only mode
        if self.db_only_mode:
            return

        # Always write to JSON for backward compatibility and fallback
        data = self._load_pending_data()

        # Check if order already exists in JSON (prevent duplicates)
        existing_order = None
        for order in data["orders"]:
            if order["order_id"] == order_id:
                existing_order = order
                break

        if existing_order:
            # Order already exists - log warning and skip adding duplicate
            logger.warning(
                f"Order {order_id} already exists in pending orders JSON. "
                f"Existing: symbol={existing_order.get('symbol')}, "
                f"status={existing_order.get('status')}, "
                f"price={existing_order.get('price')}. "
                f"Skipping duplicate add for {symbol}."
            )
            return

        pending_order = {
            "order_id": order_id,
            "symbol": symbol,
            "ticker": ticker,
            "qty": qty,
            "order_type": order_type,
            "variety": variety,
            "price": price,
            "placed_at": datetime.now().isoformat(),
            "last_status_check": datetime.now().isoformat(),
            "status": "PENDING",
            "rejection_reason": None,
            "check_count": 0,
            "executed_qty": 0,
        }

        data["orders"].append(pending_order)
        self._save_pending_data(data)

        logger.info(f"Added to pending orders: {symbol} (order_id: {order_id}, qty: {qty})")

    def get_pending_orders(
        self, status_filter: str | None = None, symbol_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get list of pending orders with optional filters.

        Phase 7: Supports dual-read (DB first, JSON fallback).

        Args:
            status_filter: Filter by status (PENDING/OPEN/PARTIALLY_FILLED)
            symbol_filter: Filter by symbol

        Returns:
            List of pending order dicts
        """
        orders = []

        # Phase 7: Read from DB first if available
        if self.use_db and self.orders_repo:
            try:
                from src.infrastructure.db.models import OrderStatus as DbOrderStatus

                # Get pending orders from DB
                db_orders = self.orders_repo.list(self.user_id)

                # Filter by status
                pending_statuses = {
                    DbOrderStatus.AMO,
                    DbOrderStatus.PENDING_EXECUTION,
                    DbOrderStatus.ONGOING,
                }
                db_orders = [o for o in db_orders if o.status in pending_statuses]

                # Convert DB orders to dict format
                for db_order in db_orders:
                    # Apply symbol filter
                    if symbol_filter and db_order.symbol.upper() != symbol_filter.upper():
                        continue

                    order_dict = {
                        "order_id": db_order.broker_order_id or db_order.order_id or "",
                        "symbol": db_order.symbol,
                        "ticker": getattr(db_order, "ticker", None),
                        "qty": db_order.quantity,
                        "order_type": (
                            db_order.order_type.upper() if db_order.order_type else "MARKET"
                        ),
                        "variety": "AMO" if db_order.status == DbOrderStatus.AMO else "REGULAR",
                        "price": db_order.price or 0.0,
                        "placed_at": (
                            db_order.placed_at.isoformat()
                            if db_order.placed_at
                            else datetime.now().isoformat()
                        ),
                        "last_status_check": (
                            db_order.last_status_check.isoformat()
                            if db_order.last_status_check
                            else datetime.now().isoformat()
                        ),
                        "status": db_order.status.value if db_order.status else "PENDING",
                        "rejection_reason": db_order.rejection_reason,
                        "check_count": 0,  # Not tracked in DB
                        "executed_qty": db_order.execution_qty or 0,
                    }

                    # Apply status filter
                    if status_filter:
                        # Map status filter to DB status values
                        # Note: "PENDING" filter matches both AMO (not yet placed) and PENDING_EXECUTION (placed, waiting)
                        # "OPEN" filter matches PENDING_EXECUTION (broker accepted, waiting execution)
                        status_map = {
                            "PENDING": [DbOrderStatus.AMO, DbOrderStatus.PENDING_EXECUTION],
                            "OPEN": [
                                DbOrderStatus.PENDING_EXECUTION
                            ],  # Broker accepted, waiting execution
                        }
                        if status_filter in status_map:
                            if db_order.status not in status_map[status_filter]:
                                continue
                        elif order_dict["status"] != status_filter:
                            continue

                    orders.append(order_dict)

                if orders:
                    logger.debug(f"Retrieved {len(orders)} pending orders from database")
                    return orders
            except Exception as e:
                logger.warning(f"Failed to read orders from database: {e}")
                # Phase 11: In DB-only mode, don't fallback to JSON
                if self.db_only_mode:
                    logger.error("DB-only mode enabled but DB read failed. Returning empty list.")
                    return []
                logger.warning("Falling back to JSON")

        # Phase 11: Fallback to JSON only if not in DB-only mode
        if self.db_only_mode:
            return []

        # Fallback to JSON
        data = self._load_pending_data()
        orders = data["orders"]

        # Apply filters
        if status_filter:
            orders = [o for o in orders if o["status"] == status_filter]

        if symbol_filter:
            orders = [o for o in orders if o["symbol"] == symbol_filter]

        return orders

    def update_order_status(
        self,
        order_id: str,
        status: str,
        executed_qty: int | None = None,
        rejection_reason: str | None = None,
    ) -> bool:
        """
        Update status of a pending order.

        Phase 7: Supports dual-write (JSON + DB).

        Args:
            order_id: Order ID to update
            status: New status (PENDING/OPEN/EXECUTED/REJECTED/CANCELLED/PARTIALLY_FILLED)
            executed_qty: Quantity executed (for partial fills)
            rejection_reason: Reason if rejected

        Returns:
            True if order found and updated, False otherwise
        """
        updated = False

        # Phase 7: Update in DB first if available
        if self.use_db and self.orders_repo:
            try:
                from src.infrastructure.db.models import OrderStatus as DbOrderStatus

                # Find order in DB
                db_order = self.orders_repo.get_by_broker_order_id(
                    self.user_id, order_id
                ) or self.orders_repo.get_by_order_id(self.user_id, order_id)

                if db_order:
                    # Map broker status string to DB status enum
                    # Note: "PENDING" from broker means "trigger pending" or "after market order req received"
                    # (broker is processing). "OPEN" means broker accepted, waiting execution.
                    # Both mean "order is with broker, waiting execution" → PENDING_EXECUTION
                    status_map = {
                        "EXECUTED": DbOrderStatus.ONGOING,  # Executed orders become ONGOING
                        "REJECTED": DbOrderStatus.REJECTED,
                        "CANCELLED": DbOrderStatus.CLOSED,  # Cancelled orders become CLOSED
                        "PENDING": DbOrderStatus.PENDING_EXECUTION,  # Broker processing (trigger pending, AMO req received)
                        "OPEN": DbOrderStatus.PENDING_EXECUTION,  # Broker accepted, waiting execution
                    }

                    new_db_status = status_map.get(status.upper())

                    # Handle rejected status specially
                    if rejection_reason and status.upper() == "REJECTED":
                        # Use mark_rejected for proper status update
                        self.orders_repo.mark_rejected(db_order, rejection_reason)
                        updated = True
                        logger.debug(f"Marked order {order_id} as rejected in database")
                    else:
                        # Handle other statuses
                        if new_db_status:
                            db_order.status = new_db_status

                        if executed_qty is not None:
                            db_order.execution_qty = executed_qty
                            db_order.execution_time = datetime.now()

                        db_order.last_status_check = datetime.now()
                        self.orders_repo.update(db_order)
                        updated = True
                        logger.debug(f"Updated order {order_id} status in database: {status}")
            except Exception as e:
                logger.warning(f"Failed to update order in database: {e}")
                # Phase 11: In DB-only mode, fail if DB update fails
                if self.db_only_mode:
                    raise

        # Phase 11: Skip JSON update in DB-only mode
        if self.db_only_mode:
            return updated

        # Always update JSON for backward compatibility
        data = self._load_pending_data()

        for order in data["orders"]:
            if order["order_id"] == order_id:
                old_status = order["status"]
                order["status"] = status
                order["last_status_check"] = datetime.now().isoformat()
                order["check_count"] = order.get("check_count", 0) + 1

                if executed_qty is not None:
                    order["executed_qty"] = executed_qty

                if rejection_reason:
                    order["rejection_reason"] = rejection_reason

                self._save_pending_data(data)

                logger.info(f"Updated order status: {order_id} {old_status} -> {status}")

                return True

        if not updated:
            logger.warning(f"Order {order_id} not found in pending orders")
        return updated

    def remove_pending_order(self, order_id: str) -> bool:
        """
        Remove order from pending tracking.

        Phase 7: Supports dual-write (JSON + DB).
        Note: In DB, we mark as CLOSED instead of deleting.

        Args:
            order_id: Order ID to remove

        Returns:
            True if order found and removed, False otherwise
        """
        removed = False

        # Phase 7: Update in DB if available (mark as closed instead of deleting)
        if self.use_db and self.orders_repo:
            try:
                # Find order in DB
                db_order = self.orders_repo.get_by_broker_order_id(
                    self.user_id, order_id
                ) or self.orders_repo.get_by_order_id(self.user_id, order_id)

                if db_order:
                    # Mark as closed instead of deleting
                    self.orders_repo.mark_cancelled(
                        db_order, cancelled_reason="Removed from pending tracking"
                    )
                    removed = True
                    logger.debug(f"Marked order {order_id} as closed in database")
            except Exception as e:
                logger.warning(f"Failed to remove order from database: {e}")
                # Phase 11: In DB-only mode, fail if DB removal fails
                if self.db_only_mode:
                    raise

        # Phase 11: Skip JSON update in DB-only mode
        if self.db_only_mode:
            return removed

        # Always update JSON for backward compatibility
        data = self._load_pending_data()

        original_count = len(data["orders"])
        data["orders"] = [o for o in data["orders"] if o["order_id"] != order_id]

        if len(data["orders"]) < original_count:
            self._save_pending_data(data)
            logger.info(f"Removed order from pending: {order_id}")
            return True

        if not removed:
            logger.warning(f"Order {order_id} not found in pending orders")
        return removed

    def get_order_by_id(self, order_id: str) -> dict[str, Any] | None:
        """
        Get pending order by order ID.

        Phase 7: Supports dual-read (DB first, JSON fallback).

        Args:
            order_id: Order ID to find

        Returns:
            Order dict or None if not found
        """
        # Phase 7: Read from DB first if available
        if self.use_db and self.orders_repo:
            try:
                from src.infrastructure.db.models import OrderStatus as DbOrderStatus

                # Find order in DB
                db_order = self.orders_repo.get_by_broker_order_id(
                    self.user_id, order_id
                ) or self.orders_repo.get_by_order_id(self.user_id, order_id)

                if db_order:
                    # Convert to dict format
                    return {
                        "order_id": db_order.broker_order_id or db_order.order_id or "",
                        "symbol": db_order.symbol,
                        "ticker": getattr(db_order, "ticker", None),
                        "qty": db_order.quantity,
                        "order_type": (
                            db_order.order_type.upper() if db_order.order_type else "MARKET"
                        ),
                        "variety": ("AMO" if db_order.status == DbOrderStatus.AMO else "REGULAR"),
                        "price": db_order.price or 0.0,
                        "placed_at": (
                            db_order.placed_at.isoformat()
                            if db_order.placed_at
                            else datetime.now().isoformat()
                        ),
                        "last_status_check": (
                            db_order.last_status_check.isoformat()
                            if db_order.last_status_check
                            else datetime.now().isoformat()
                        ),
                        "status": db_order.status.value if db_order.status else "PENDING",
                        "rejection_reason": db_order.rejection_reason,
                        "check_count": 0,
                        "executed_qty": db_order.execution_qty or 0,
                    }
            except Exception as e:
                logger.warning(f"Failed to read order from database: {e}")
                # Phase 11: In DB-only mode, don't fallback to JSON
                if self.db_only_mode:
                    logger.error("DB-only mode enabled but DB read failed. Returning None.")
                    return None
                logger.warning("Falling back to JSON")

        # Phase 11: Fallback to JSON only if not in DB-only mode
        if self.db_only_mode:
            return None

        # Fallback to JSON
        data = self._load_pending_data()

        for order in data["orders"]:
            if order["order_id"] == order_id:
                return order

        return None

    def search_order_in_broker_orderbook(
        self,
        orders_api_client,
        symbol: str,
        qty: int,
        after_timestamp: str,
        max_wait_seconds: int = 60,
    ) -> str | None:
        """
        Search for order in broker's order book when order_id not received.
        Implements 60-second fallback logic.

        Args:
            orders_api_client: Orders API client (with get_orders method)
            symbol: Trading symbol to search for
            qty: Expected quantity
            after_timestamp: Only consider orders after this time
            max_wait_seconds: Maximum seconds to wait (default 60)

        Returns:
            Order ID if found, None otherwise
        """
        logger.info(
            f"Searching order book for {symbol} (qty: {qty}) - waiting up to {max_wait_seconds}s"
        )

        time.sleep(max_wait_seconds)  # Wait for broker to process

        try:
            # Get all orders from broker
            orders_response = orders_api_client.get_orders()

            if not orders_response or "data" not in orders_response:
                logger.warning("Failed to fetch orders from broker")
                return None

            # Parse after_timestamp
            try:
                after_time = datetime.fromisoformat(after_timestamp)
            except Exception:
                after_time = datetime.now()

            # Search for matching order
            for order in orders_response["data"]:
                order_symbol = str(order.get("tradingSymbol", "")).upper()
                order_qty = int(order.get("quantity", 0))

                # Parse order time
                order_time_str = order.get("orderEntryTime") or order.get("timestamp")
                if order_time_str:
                    try:
                        order_time = datetime.fromisoformat(order_time_str)
                        if order_time < after_time:
                            continue  # Too old
                    except Exception:
                        pass

                # Check if match
                if symbol.upper() in order_symbol and order_qty == qty:
                    found_order_id = (
                        order.get("neoOrdNo") or order.get("orderId") or order.get("order_id")
                    )

                    if found_order_id:
                        logger.info(
                            f"Found order in broker order book: {found_order_id} for {symbol}"
                        )
                        return str(found_order_id)

            logger.warning(f"Order not found in broker order book: {symbol} x{qty}")
            return None

        except Exception as e:
            logger.error(f"Error searching order book: {e}")
            return None


# Singleton instance
_order_tracker_instance: OrderTracker | None = None


def configure_order_tracker(
    *,
    data_dir: str = "data",
    db_session=None,
    user_id: int | None = None,
    use_db: bool | None = None,
    db_only_mode: bool | None = None,
) -> OrderTracker:
    """
    Configure the global order tracker singleton with explicit settings.

    Calling this replaces any previously created tracker instance. This is needed
    when the trading engine boots with a live DB session so that pending orders
    get dual-written to the database immediately.
    """

    global _order_tracker_instance

    effective_use_db = use_db if use_db is not None else bool(db_session and user_id)
    if db_only_mode is None:
        env_value = os.getenv("ORDER_TRACKER_DB_ONLY_MODE", "")
        db_only_mode = env_value.strip().lower() in {"1", "true", "yes"}

    _order_tracker_instance = OrderTracker(
        data_dir=data_dir,
        db_session=db_session,
        user_id=user_id,
        use_db=effective_use_db,
        db_only_mode=db_only_mode,
    )

    return _order_tracker_instance


def get_order_tracker(data_dir: str = "data") -> OrderTracker:
    """
    Get or create order tracker singleton instance.

    Args:
        data_dir: Directory for pending orders data

    Returns:
        OrderTracker instance
    """
    global _order_tracker_instance

    if _order_tracker_instance is None:
        _order_tracker_instance = OrderTracker(data_dir)

    return _order_tracker_instance


# Convenience functions
def extract_order_id(response: dict[str, Any]) -> str | None:
    """Extract order ID from broker response."""
    return OrderTracker.extract_order_id(response)


def add_pending_order(*args, **kwargs) -> None:
    """Add order to pending tracking."""
    return get_order_tracker().add_pending_order(*args, **kwargs)


def get_pending_orders(**kwargs) -> list[dict[str, Any]]:
    """Get list of pending orders."""
    return get_order_tracker().get_pending_orders(**kwargs)


def update_order_status(*args, **kwargs) -> bool:
    """Update order status."""
    return get_order_tracker().update_order_status(*args, **kwargs)


def remove_pending_order(order_id: str) -> bool:
    """Remove order from pending."""
    return get_order_tracker().remove_pending_order(order_id)


def get_order_by_id(order_id: str) -> dict[str, Any] | None:
    """Get order by ID."""
    return get_order_tracker().get_order_by_id(order_id)


def search_order_in_broker_orderbook(*args, **kwargs) -> str | None:
    """Search for order in broker order book."""
    return get_order_tracker().search_order_in_broker_orderbook(*args, **kwargs)
