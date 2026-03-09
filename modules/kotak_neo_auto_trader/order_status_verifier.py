#!/usr/bin/env python3
"""
Order Status Verifier Module
Periodically checks pending order statuses and handles status updates.

SOLID Principles:
- Single Responsibility: Only verifies order statuses
- Open/Closed: Extensible for different verification strategies
- Dependency Inversion: Abstract broker API interactions

Phase 2 Feature: Automated order status verification every 30 minutes
"""

# Use existing project logger
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from datetime import time as dt_time
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

# Import Phase 1 modules
from .order_tracker import OrderTracker, get_order_tracker
from .tracking_scope import TrackingScope, get_tracking_scope


class OrderStatusVerifier:
    """
    Periodically verifies pending order statuses with broker.
    Handles status updates, rejections, executions, and partial fills.
    """

    def __init__(
        self,
        broker_client,
        order_tracker: OrderTracker | None = None,
        tracking_scope: TrackingScope | None = None,
        check_interval_seconds: int = 1800,  # 30 minutes
        on_rejection_callback: Callable | None = None,
        on_execution_callback: Callable | None = None,
    ):
        """
        Initialize order status verifier.

        Args:
            broker_client: Broker API client with order_report() method
            order_tracker: OrderTracker instance (uses singleton if None)
            tracking_scope: TrackingScope instance (uses singleton if None)
            check_interval_seconds: Seconds between checks (default 1800 = 30 min)
            on_rejection_callback: Called when order rejected (symbol, order_id, reason)
            on_execution_callback: Called when order executed (symbol, order_id, qty)
        """
        self.broker_client = broker_client
        self.order_tracker = order_tracker or get_order_tracker()
        self.tracking_scope = tracking_scope or get_tracking_scope()
        self.check_interval_seconds = check_interval_seconds
        self.on_rejection_callback = on_rejection_callback
        self.on_execution_callback = on_execution_callback

        self._running = False
        self._thread: threading.Thread | None = None
        self._last_check_time: datetime | None = None

        # Phase 3.2: Store verification results for sharing
        self._verification_results: dict[str, dict[str, Any]] = {}  # order_id -> result
        self._last_verification_counts: dict[str, int] = {}  # Last verification counts

    def start(self, daemon: bool = True) -> None:
        """
        Start periodic verification in background thread.

        Args:
            daemon: Run as daemon thread (terminates with main thread)
        """
        if self._running:
            logger.warning("Order status verifier already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._verification_loop, daemon=daemon)
        self._thread.start()

        logger.info(
            f"Order status verifier started (check interval: {self.check_interval_seconds}s)"
        )

    def stop(self) -> None:
        """Stop periodic verification."""
        if not self._running:
            logger.warning("Order status verifier not running")
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        logger.info("Order status verifier stopped")

    def is_running(self) -> bool:
        """Check if verifier is running."""
        return self._running

    def _verification_loop(self) -> None:
        """Main verification loop (runs in background thread)."""
        logger.info("Order status verification loop started")

        while self._running:
            try:
                self.verify_pending_orders()
                self._last_check_time = datetime.now()

                # Sleep in small intervals to allow responsive shutdown
                sleep_interval = min(self.check_interval_seconds, 30)
                elapsed = 0
                while elapsed < self.check_interval_seconds and self._running:
                    time.sleep(sleep_interval)
                    elapsed += sleep_interval

            except Exception as e:
                logger.error(f"Error in verification loop: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute before retrying on error

    def verify_pending_orders(self) -> dict[str, int]:
        """
        Verify all pending orders with broker.

        Returns:
            Dict with counts: {
                'checked': int,
                'executed': int,
                'rejected': int,
                'partial': int,
                'still_pending': int
            }
        """
        pending_orders = self.order_tracker.get_pending_orders(status_filter="PENDING")

        if not pending_orders:
            logger.debug("No pending orders to verify")
            return {
                "checked": 0,
                "executed": 0,
                "rejected": 0,
                "cancelled": 0,
                "partial": 0,
                "still_pending": 0,
            }

        logger.info(f"Verifying {len(pending_orders)} pending order(s)")

        # Get current orders from broker
        try:
            broker_orders = self._fetch_broker_orders()
        except Exception as e:
            logger.error(f"Failed to fetch broker orders: {e}")
            return {
                "checked": len(pending_orders),
                "executed": 0,
                "rejected": 0,
                "cancelled": 0,
                "partial": 0,
                "still_pending": len(pending_orders),
            }

        counts = {
            "checked": len(pending_orders),
            "executed": 0,
            "rejected": 0,
            "cancelled": 0,
            "partial": 0,
            "still_pending": 0,
        }

        # Check each pending order
        for pending_order in pending_orders:
            order_id = pending_order["order_id"]
            symbol = pending_order["symbol"]
            expected_qty = pending_order["qty"]

            # Phase 3.2: Store initial state before verification
            initial_status = {
                "order_id": order_id,
                "symbol": symbol,
                "expected_qty": expected_qty,
                "status": "PENDING",
            }

            # Find order in broker's order book
            broker_order = self._find_order_in_broker_orders(order_id, broker_orders)

            if not broker_order:
                # Order not found in active orders - check if it was cancelled/executed
                # by checking order history (includes cancelled/executed orders)
                broker_order = self._check_order_history(order_id)

                if broker_order:
                    # Found in history - parse status and handle accordingly
                    broker_status = self._parse_broker_order_status(broker_order)

                    # Phase 3.2: Store verification result for sharing
                    self._verification_results[order_id] = {
                        "order_id": order_id,
                        "symbol": symbol,
                        "status": broker_status["status"],
                        "executed_qty": broker_status.get("executed_qty", 0),
                        "rejection_reason": broker_status.get("rejection_reason"),
                        "verified_at": datetime.now().isoformat(),
                        "broker_order": broker_order,
                    }

                    if broker_status["status"] == "CANCELLED":
                        self._handle_cancellation(pending_order, broker_order, broker_status)
                        counts["cancelled"] += 1
                        continue
                    elif broker_status["status"] == "EXECUTED":
                        self._handle_execution(pending_order, broker_order, broker_status)
                        counts["executed"] += 1
                        continue
                    elif broker_status["status"] == "REJECTED":
                        self._handle_rejection(pending_order, broker_order, broker_status)
                        counts["rejected"] += 1
                        continue

                # Still not found - check if we should assume cancellation based on time
                if self._should_assume_cancelled(pending_order):
                    logger.info(
                        f"Order {order_id} not found and appears to be broker-cancelled "
                        f"(placed at {pending_order.get('placed_at', 'unknown')}, "
                        f"current time after market close)"
                    )
                    # Create a mock broker order with cancelled status for handling
                    mock_cancelled_order = {
                        "nOrdNo": order_id,
                        "orderStatus": "cancelled",
                        "ordSt": "cancelled",
                        "tradingSymbol": pending_order.get("symbol", ""),
                        "quantity": pending_order.get("qty", 0),
                    }
                    broker_status = self._parse_broker_order_status(mock_cancelled_order)

                    # Phase 3.2: Store verification result for sharing
                    self._verification_results[order_id] = {
                        "order_id": order_id,
                        "symbol": symbol,
                        "status": broker_status["status"],
                        "executed_qty": 0,
                        "rejection_reason": None,
                        "verified_at": datetime.now().isoformat(),
                        "broker_order": mock_cancelled_order,
                    }

                    self._handle_cancellation(pending_order, mock_cancelled_order, broker_status)

                    # Phase 3.2: Store verification result for sharing
                    self._verification_results[order_id] = {
                        "order_id": order_id,
                        "symbol": symbol,
                        "status": broker_status["status"],
                        "executed_qty": 0,
                        "rejection_reason": None,
                        "verified_at": datetime.now().isoformat(),
                        "broker_order": mock_cancelled_order,
                    }

                    counts["cancelled"] += 1
                    continue

                # Still not found - check if order is stale (>12 hours old)
                # Only mark as FAILED if we got a successful API response (even if empty)
                # This prevents marking orders as failed when broker API is down or returning errors
                # (If API threw exception, we wouldn't reach here - caught at line 161)
                should_mark_failed = False
                age_hours = None

                if pending_order.get("placed_at"):
                    try:
                        placed_at = datetime.fromisoformat(
                            pending_order["placed_at"].replace("Z", "+00:00")
                        )
                        if placed_at.tzinfo:
                            placed_at = placed_at.replace(tzinfo=None)
                        age_hours = (datetime.now() - placed_at).total_seconds() / 3600

                        # Only mark as stale if order is > 12 hours old
                        if age_hours > 12:
                            should_mark_failed = True
                            logger.warning(
                                f"Order {order_id} not found in broker and is {age_hours:.1f}h old. "
                                "Marking as FAILED in database."
                            )
                    except Exception as e:
                        logger.debug(f"Error checking order age for {order_id}: {e}")

                # Mark stale orders as FAILED in database
                if (
                    should_mark_failed
                    and self.order_tracker.orders_repo
                    and self.order_tracker.user_id
                ):
                    try:
                        # Get database order
                        db_order = self.order_tracker.orders_repo.get_by_broker_order_id(
                            self.order_tracker.user_id, order_id
                        ) or self.order_tracker.orders_repo.get_by_order_id(
                            self.order_tracker.user_id, order_id
                        )

                        if db_order:
                            # Check if order has execution_qty > 0 (already processed)
                            if db_order.execution_qty and float(db_order.execution_qty) > 0:
                                logger.debug(
                                    f"Skipping marking order {order_id} as failed: "
                                    f"Already has execution_qty ({db_order.execution_qty})"
                                )
                                counts["still_pending"] += 1
                                continue

                            # Mark as failed
                            self.order_tracker.orders_repo.mark_failed(
                                db_order,
                                f"Stale order - not found in broker after {age_hours:.1f} hours",
                            )

                            # Phase 3.2: Store verification result
                            self._verification_results[order_id] = {
                                "order_id": order_id,
                                "symbol": symbol,
                                "status": "FAILED",
                                "executed_qty": 0,
                                "rejection_reason": f"Stale order - not found in broker after {age_hours:.1f} hours",
                                "verified_at": datetime.now().isoformat(),
                                "broker_order": None,
                            }

                            # Remove from pending tracking
                            self.order_tracker.remove_pending_order(order_id)
                            counts["rejected"] += 1  # Count as rejected for stats
                            continue  # Skip the "still_pending" increment below

                    except Exception as e:
                        logger.error(
                            f"Error marking stale order {order_id} as failed: {e}", exc_info=True
                        )

                # Still not found - log warning and mark as still pending
                logger.warning(
                    f"Order {order_id} not found in broker order book or history. "
                    f"May have been cancelled or expired."
                )

                # Phase 3.2: Store verification result even when not found
                self._verification_results[order_id] = {
                    "order_id": order_id,
                    "symbol": symbol,
                    "status": "NOT_FOUND",
                    "executed_qty": 0,
                    "rejection_reason": None,
                    "verified_at": datetime.now().isoformat(),
                    "broker_order": None,
                }

                counts["still_pending"] += 1
                continue

            # Parse broker order status
            broker_status = self._parse_broker_order_status(broker_order)

            # Phase 3.2: Store verification result for sharing
            self._verification_results[order_id] = {
                "order_id": order_id,
                "symbol": symbol,
                "status": broker_status["status"],
                "executed_qty": broker_status.get("executed_qty", 0),
                "rejection_reason": broker_status.get("rejection_reason"),
                "verified_at": datetime.now().isoformat(),
                "broker_order": broker_order,  # Store full broker order for reference
            }

            if broker_status["status"] == "EXECUTED":
                self._handle_execution(pending_order, broker_order, broker_status)
                counts["executed"] += 1

            elif broker_status["status"] == "REJECTED":
                self._handle_rejection(pending_order, broker_order, broker_status)
                counts["rejected"] += 1

            elif broker_status["status"] == "CANCELLED":
                self._handle_cancellation(pending_order, broker_order, broker_status)
                counts["cancelled"] += 1

            elif broker_status["status"] == "PARTIALLY_FILLED":
                self._handle_partial_fill(pending_order, broker_order, broker_status)
                counts["partial"] += 1

            elif broker_status["status"] in ["OPEN", "PENDING"]:
                # Still pending, no action needed
                counts["still_pending"] += 1

            else:
                logger.warning(f"Unknown broker status for {order_id}: {broker_status['status']}")
                if isinstance(broker_order, dict):
                    logger.warning(
                        "Unknown ordSt for order %s: raw ordSt=%r keys=%s",
                        order_id,
                        broker_order.get("ordSt"),
                        sorted(list(broker_order.keys())),
                    )
                counts["still_pending"] += 1

        logger.info(
            f"Verification complete: "
            f"{counts['executed']} executed, "
            f"{counts['rejected']} rejected, "
            f"{counts.get('cancelled', 0)} cancelled, "
            f"{counts['partial']} partial, "
            f"{counts['still_pending']} still pending"
        )

        # Phase 3.2: Store verification counts for sharing
        self._last_verification_counts = counts.copy()

        return counts

    def _fetch_broker_orders(self) -> list[dict[str, Any]]:
        """
        Fetch all orders from broker.

        Returns:
            List of order dicts from broker
        """
        try:
            def _has_callable_method(obj, name: str) -> bool:
                """
                Return True when object exposes a callable method name.

                Supports:
                - normal class-defined methods (e.g. KotakNeoOrders.get_orders)
                - explicitly attached mock methods in instance __dict__

                Avoids generic Mock attribute auto-creation being treated as real API methods.
                """
                try:
                    method = getattr(obj, name, None)
                    if not callable(method):
                        return False
                    return name in getattr(type(obj), "__dict__", {}) or name in getattr(
                        obj, "__dict__", {}
                    )
                except Exception:
                    return False

            # Prefer REST wrapper method
            if _has_callable_method(self.broker_client, "get_orders"):
                response = self.broker_client.get_orders()
            elif _has_callable_method(self.broker_client, "get_order_book"):
                response = self.broker_client.get_order_book()
            elif _has_callable_method(self.broker_client, "order_report"):
                response = self.broker_client.order_report()
            else:
                logger.error(
                    f"broker_client does not have get_orders()/get_order_book()/order_report(). Type: {type(self.broker_client)}"
                )
                return []

            if isinstance(response, list):
                return response
            elif isinstance(response, dict):
                # Handle dict response - check for 'data' key
                if "data" in response:
                    data = response["data"]
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        # Sometimes data is a dict with order details
                        return [data] if data else []
                    return []
                # Check if response itself is structured as orders
                if "orders" in response:
                    orders = response["orders"]
                    return orders if isinstance(orders, list) else []
                # Empty dict means no orders
                return []
            else:
                logger.error(f"Unexpected broker response format: {type(response)}")
                return []

        except Exception as e:
            logger.error(f"Error fetching broker orders: {e}", exc_info=True)
            return []

    def _find_order_in_broker_orders(
        self, order_id: str, broker_orders: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """
        Find order in broker's order list by order ID.

        Args:
            order_id: Order ID to find
            broker_orders: List of orders from broker

        Returns:
            Order dict if found, None otherwise
        """
        for broker_order in broker_orders:
            broker_order_id = (
                broker_order.get("nOrdNo")
                or broker_order.get("neoOrdNo")
                or broker_order.get("orderId")
                or broker_order.get("order_id")
            )

            if broker_order_id and str(broker_order_id) == str(order_id):
                return broker_order

        return None

    def _check_order_history(self, order_id: str) -> dict[str, Any] | None:
        """
        Check order history for cancelled/executed orders not in active list.

        When an order is cancelled by broker (e.g., at market close), it's removed
        from active orders but still exists in order history. This method checks
        order_report() (which includes all orders) to detect such cancellations.

        Note: Kotak Neo API's order_history(order_id) may not work for all orders.
        We use order_report() to get all orders and filter by order_id.

        Args:
            order_id: Order ID to check

        Returns:
            Order dict from order_report if found, None otherwise
        """
        try:
            # Use order_report() to get all orders (includes cancelled/executed orders)
            # Note: order_history(order_id) API may not work for all orders
            all_orders_response = self._fetch_broker_orders()

            # Search for order matching order_id in all orders
            for order in all_orders_response:
                broker_order_id = (
                    order.get("nOrdNo")
                    or order.get("neoOrdNo")
                    or order.get("orderId")
                    or order.get("order_id")
                )
                if broker_order_id and str(broker_order_id) == str(order_id):
                    return order

            return None

        except Exception as e:
            logger.debug(f"Error checking order history for {order_id}: {e}")
            return None

    def _should_assume_cancelled(self, pending_order: dict[str, Any]) -> bool:
        """
        Determine if an order should be assumed cancelled based on timing.

        Conditions:
        1. Order not found in active orders or order_report()
        2. Current time is after market close (15:30)
        3. At least 30 minutes have passed since market close (grace period for broker processing)
        4. Order was placed today (same day)
        5. Order was placed before market close

        This handles broker auto-cancellations which typically happen:
        - Around 4:27 PM (most common)
        - But can also happen at 4:30, 4:45, or 5:00 PM
        - Or even later in some cases

        Args:
            pending_order: Pending order dict with 'placed_at' timestamp

        Returns:
            True if order should be assumed cancelled, False otherwise
        """
        try:
            placed_at_str = pending_order.get("placed_at")
            if not placed_at_str:
                return False

            # Parse placed_at timestamp
            placed_at = datetime.fromisoformat(placed_at_str.replace("Z", "+00:00"))
            if placed_at.tzinfo:
                placed_at = placed_at.replace(tzinfo=None)

            now = datetime.now()
            current_time = now.time()
            market_close_time = dt_time(15, 30)  # 3:30 PM
            market_close_datetime = datetime.combine(now.date(), market_close_time)

            # Check if current time is after market close
            if current_time < market_close_time:
                return False  # Still during market hours, don't assume cancellation

            # Check if order was placed today
            if placed_at.date() != now.date():
                return False  # Order from different day, don't assume cancellation

            # Check if order was placed before market close today
            placed_time = placed_at.time()
            if placed_time > market_close_time:
                return False  # Order placed after market close (unusual), don't assume

            # Calculate time elapsed since market close
            time_since_close = now - market_close_datetime
            grace_period_minutes = (
                30  # Wait 30 minutes after market close before assuming cancellation
            )

            # Check if enough time has passed since market close
            # This accounts for broker cancellations happening at various times:
            # - 4:27 PM (most common)
            # - 4:30 PM
            # - 4:45 PM
            # - 5:00 PM
            # - Or even later
            if time_since_close.total_seconds() < (grace_period_minutes * 60):
                return False  # Not enough time has passed, broker might still be processing

            # Order was placed today, before market close, it's been at least 30 minutes
            # since market close, and order is not found - likely broker-cancelled
            logger.debug(
                f"Assuming cancellation: order placed at {placed_at}, "
                f"market close was {market_close_datetime}, "
                f"current time is {now}, "
                f"time since close: {time_since_close.total_seconds() / 60:.1f} minutes"
            )
            return True

        except Exception as e:
            logger.debug(f"Error checking if order should be assumed cancelled: {e}")
            return False

    def _parse_broker_order_status(self, broker_order: dict[str, Any]) -> dict[str, Any]:
        """
        Parse order status from broker order dict.

        Args:
            broker_order: Order dict from broker

        Returns:
            Dict with {
                'status': str,
                'executed_qty': int,
                'rejection_reason': Optional[str]
            }
        """
        # Map broker status to our internal status
        status_map = {
            "complete": "EXECUTED",
            "traded": "EXECUTED",
            "executed": "EXECUTED",
            "filled": "EXECUTED",
            "rejected": "REJECTED",
            "cancelled": "CANCELLED",
            "canceled": "CANCELLED",  # American spelling
            "cancelled after market order": "CANCELLED",
            "open": "OPEN",
            "pending": "PENDING",
            "trigger pending": "PENDING",
            "after market order req received": "PENDING",
            "after market order request received": "PENDING",
            "amo req received": "PENDING",
            "put order req received": "PENDING",
            "validation pending": "PENDING",
            "open pending": "PENDING",
            "modify pending": "PENDING",
            "modify validation pending": "PENDING",
            "cancel pending": "PENDING",
            "cancel validation pending": "PENDING",
            "partial fill": "PARTIALLY_FILLED",
            "partially filled": "PARTIALLY_FILLED",
            "partially executed": "PARTIALLY_FILLED",
        }

        # Use documented field from Kotak order APIs.
        raw_status = broker_order.get("ordSt") or ""
        broker_status = str(raw_status).strip().lower().replace("_", " ")
        internal_status = status_map.get(broker_status, "UNKNOWN")

        def _to_int(v: Any, default: int = 0) -> int:
            try:
                if v is None:
                    return default
                return int(float(str(v).replace(",", "").strip()))
            except Exception:
                return default

        executed_qty = _to_int(
            broker_order.get("fldQty")
            or broker_order.get("filledQty")
            or broker_order.get("execQty")
            or 0
        )
        rejection_reason = broker_order.get("rejRsn") or broker_order.get("rejectionReason")

        return {
            "status": internal_status,
            "executed_qty": executed_qty,
            "rejection_reason": rejection_reason,
        }

    def _handle_execution(
        self,
        pending_order: dict[str, Any],
        broker_order: dict[str, Any],
        broker_status: dict[str, Any],
    ) -> None:
        """
        Handle successfully executed order.

        Args:
            pending_order: Pending order from our tracker
            broker_order: Order from broker
            broker_status: Parsed broker status
        """
        order_id = pending_order["order_id"]
        symbol = pending_order["symbol"]
        executed_qty = broker_status["executed_qty"] or pending_order["qty"]

        logger.info(f"Order EXECUTED: {symbol} x{executed_qty} (order_id: {order_id})")

        # Update order tracker (best-effort; do not crash verifier on DB transaction state errors)
        try:
            self.order_tracker.update_order_status(
                order_id=order_id, status="EXECUTED", executed_qty=executed_qty
            )
        except Exception as e:
            logger.warning(f"Failed to update tracker for executed order {order_id}: {e}")

        # Update tracking scope quantity
        if self.tracking_scope.is_tracked(symbol):
            # Quantity already added when order was placed
            # Just log confirmation
            logger.debug(f"Confirmed execution for tracked symbol: {symbol}")

        # Remove from pending (execution complete), best-effort
        try:
            self.order_tracker.remove_pending_order(order_id)
        except Exception as e:
            logger.warning(f"Failed to remove executed order {order_id} from pending tracker: {e}")

        # Trigger callback
        if self.on_execution_callback:
            try:
                self.on_execution_callback(symbol, order_id, executed_qty)
            except Exception as e:
                logger.error(f"Error in execution callback: {e}")

    def _handle_rejection(
        self,
        pending_order: dict[str, Any],
        broker_order: dict[str, Any],
        broker_status: dict[str, Any],
    ) -> None:
        """
        Handle rejected order.

        Args:
            pending_order: Pending order from our tracker
            broker_order: Order from broker
            broker_status: Parsed broker status
        """
        order_id = pending_order["order_id"]
        symbol = pending_order["symbol"]
        qty = pending_order["qty"]
        rejection_reason = broker_status["rejection_reason"] or "Unknown reason"

        logger.warning(
            f"Order REJECTED: {symbol} x{qty} (order_id: {order_id}, reason: {rejection_reason})"
        )

        # Update order tracker (best-effort; do not crash verifier on DB transaction state errors)
        try:
            self.order_tracker.update_order_status(
                order_id=order_id, status="REJECTED", rejection_reason=rejection_reason
            )
        except Exception as e:
            logger.warning(f"Failed to update tracker for rejected order {order_id}: {e}")

        # Stop tracking this symbol (order failed)
        if self.tracking_scope.is_tracked(symbol):
            self.tracking_scope.stop_tracking(symbol, reason=f"Order rejected: {rejection_reason}")

        # Remove from pending (rejection finalized), best-effort
        try:
            self.order_tracker.remove_pending_order(order_id)
        except Exception as e:
            logger.warning(f"Failed to remove rejected order {order_id} from pending tracker: {e}")

        # Trigger callback
        if self.on_rejection_callback:
            try:
                self.on_rejection_callback(symbol, order_id, rejection_reason)
            except Exception as e:
                logger.error(f"Error in rejection callback: {e}")

    def _handle_cancellation(
        self,
        pending_order: dict[str, Any],
        broker_order: dict[str, Any],
        broker_status: dict[str, Any],
    ) -> None:
        """
        Handle cancelled order.

        Args:
            pending_order: Pending order from our tracker
            broker_order: Order from broker
            broker_status: Parsed broker status
        """
        order_id = pending_order["order_id"]
        symbol = pending_order["symbol"]
        qty = pending_order["qty"]

        logger.info(f"Order CANCELLED: {symbol} x{qty} (order_id: {order_id})")

        # Update order tracker (best-effort; do not crash verifier on DB transaction state errors)
        try:
            self.order_tracker.update_order_status(order_id=order_id, status="CANCELLED")
        except Exception as e:
            logger.warning(f"Failed to update tracker for cancelled order {order_id}: {e}")

        # Stop tracking this symbol (order cancelled)
        if self.tracking_scope.is_tracked(symbol):
            self.tracking_scope.stop_tracking(symbol, reason="Order cancelled")

        # Remove from pending (cancellation finalized), best-effort
        try:
            self.order_tracker.remove_pending_order(order_id)
        except Exception as e:
            logger.warning(f"Failed to remove cancelled order {order_id} from pending tracker: {e}")

        # Note: Cancellation callback can be added if needed
        # Similar to rejection callback, but typically cancellations
        # are handled differently (user-initiated vs broker-initiated)

    def _handle_partial_fill(
        self,
        pending_order: dict[str, Any],
        broker_order: dict[str, Any],
        broker_status: dict[str, Any],
    ) -> None:
        """
        Handle partially filled order.

        Args:
            pending_order: Pending order from our tracker
            broker_order: Order from broker
            broker_status: Parsed broker status
        """
        order_id = pending_order["order_id"]
        symbol = pending_order["symbol"]
        total_qty = pending_order["qty"]
        executed_qty = broker_status["executed_qty"]
        remaining_qty = total_qty - executed_qty

        logger.info(
            f"Order PARTIALLY FILLED: {symbol} "
            f"(filled: {executed_qty}/{total_qty}, remaining: {remaining_qty})"
        )

        # Update order tracker (best-effort; do not crash verifier on DB transaction state errors)
        try:
            self.order_tracker.update_order_status(
                order_id=order_id, status="PARTIALLY_FILLED", executed_qty=executed_qty
            )
        except Exception as e:
            logger.warning(f"Failed to update tracker for partially filled order {order_id}: {e}")

        # Note: Tracking scope already has full quantity tracked
        # Partial fills don't change the tracked quantity
        # (we track intent, not execution status)

        logger.debug(
            f"Partial fill tracked for {symbol}: {executed_qty} filled, {remaining_qty} pending"
        )

    def verify_order_by_id(self, order_id: str) -> str | None:
        """
        Verify specific order by ID (on-demand check).

        Args:
            order_id: Order ID to verify

        Returns:
            Current status string, or None if not found
        """
        pending_order = self.order_tracker.get_order_by_id(order_id)

        if not pending_order:
            logger.warning(f"Order {order_id} not found in pending orders")
            return None

        try:
            broker_orders = self._fetch_broker_orders()
            broker_order = self._find_order_in_broker_orders(order_id, broker_orders)

            if not broker_order:
                # Check order history for cancelled/executed orders
                broker_order = self._check_order_history(order_id)

                if not broker_order:
                    logger.warning(f"Order {order_id} not found in broker order book or history")
                    return None

            broker_status = self._parse_broker_order_status(broker_order)

            # Handle status update
            if broker_status["status"] == "EXECUTED":
                self._handle_execution(pending_order, broker_order, broker_status)
            elif broker_status["status"] == "REJECTED":
                self._handle_rejection(pending_order, broker_order, broker_status)
            elif broker_status["status"] == "CANCELLED":
                self._handle_cancellation(pending_order, broker_order, broker_status)
            elif broker_status["status"] == "PARTIALLY_FILLED":
                self._handle_partial_fill(pending_order, broker_order, broker_status)

            return broker_status["status"]

        except Exception as e:
            logger.error(f"Error verifying order {order_id}: {e}")
            return None

    def get_last_check_time(self) -> datetime | None:
        """Get timestamp of last verification check."""
        return self._last_check_time

    def get_next_check_time(self) -> datetime | None:
        """Get estimated timestamp of next verification check."""
        if not self._last_check_time:
            return None

        return self._last_check_time + timedelta(seconds=self.check_interval_seconds)

    def get_verification_result(self, order_id: str) -> dict[str, Any] | None:
        """
        Get verification result for specific order.

        Phase 3.2: Consolidate order verification

        Args:
            order_id: Order ID to check

        Returns:
            Verification result dict if found, None otherwise
        """
        return self._verification_results.get(order_id)

    def get_verification_results_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        """
        Get verification results for all orders matching symbol.

        Phase 3.2: Consolidate order verification

        Args:
            symbol: Symbol to check (supports variants)

        Returns:
            List of verification result dicts
        """
        # Normalize symbol for comparison
        base_symbol = (
            symbol.upper()
            .replace("-EQ", "")
            .replace("-BE", "")
            .replace("-BL", "")
            .replace("-BZ", "")
        )

        results = []
        for order_id, result in self._verification_results.items():
            result_symbol = (
                result.get("symbol", "")
                .upper()
                .replace("-EQ", "")
                .replace("-BE", "")
                .replace("-BL", "")
                .replace("-BZ", "")
            )
            if result_symbol == base_symbol:
                results.append(result)

        return results

    def get_last_verification_counts(self) -> dict[str, int]:
        """
        Get last verification counts.

        Phase 3.2: Consolidate order verification

        Returns:
            Dict with verification counts from last run
        """
        return self._last_verification_counts.copy()

    def should_skip_verification(self, minutes_threshold: int = 15) -> bool:
        """
        Check if verification should be skipped based on last check time.

        Phase 3.2: Consolidate order verification

        Args:
            minutes_threshold: Minutes since last check to skip verification (default: 15)

        Returns:
            True if verification should be skipped, False otherwise
        """
        if not self._last_check_time:
            return False  # Never checked, don't skip

        time_since_last_check = datetime.now() - self._last_check_time
        threshold_seconds = minutes_threshold * 60

        should_skip = time_since_last_check.total_seconds() < threshold_seconds

        if should_skip:
            logger.debug(
                f"Skipping verification: last check was "
                f"{time_since_last_check.total_seconds() / 60:.1f} minutes ago "
                f"(threshold: {minutes_threshold} minutes)"
            )

        return should_skip


# Singleton instance
_verifier_instance: OrderStatusVerifier | None = None


def get_order_status_verifier(broker_client, **kwargs) -> OrderStatusVerifier:
    """
    Get or create order status verifier singleton.

    Args:
        broker_client: Broker API client
        **kwargs: Additional arguments for OrderStatusVerifier

    Returns:
        OrderStatusVerifier instance
    """
    global _verifier_instance

    if _verifier_instance is None:
        _verifier_instance = OrderStatusVerifier(broker_client, **kwargs)

    return _verifier_instance
