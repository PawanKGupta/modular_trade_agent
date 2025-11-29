#!/usr/bin/env python3
"""
Unified Order State Manager
Consolidates order state management across multiple storage systems.

Provides single source of truth for:
- Active sell orders (in-memory)
- Pending orders (OrderTracker)
- Trade history (storage.trades_history.json)
- Failed orders (storage.trades_history.json)
"""

import threading
from datetime import datetime
from typing import Any

from utils.logger import logger

try:
    from .domain.value_objects.order_enums import OrderStatus
    from .order_tracker import OrderTracker
    from .storage import (
        append_trade,
        cleanup_expired_failed_orders,
        load_history,
        mark_position_closed,
    )
    from .utils.order_field_extractor import OrderFieldExtractor
    from .utils.order_status_parser import OrderStatusParser
    from .utils.symbol_utils import extract_base_symbol
except ImportError:
    from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import OrderStatus
    from modules.kotak_neo_auto_trader.order_tracker import OrderTracker
    from modules.kotak_neo_auto_trader.storage import (
        append_trade,
        cleanup_expired_failed_orders,
        load_history,
        mark_position_closed,
    )
    from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
    from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser
    from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol


class OrderStateManager:
    """
    Unified order state management providing single source of truth.

    Consolidates:
    - active_sell_orders (in-memory cache)
    - pending_orders (OrderTracker JSON)
    - trades (trades_history.json)
    - failed_orders (trades_history.json)

    Provides atomic updates across all state sources.
    """

    def __init__(
        self,
        history_path: str,
        data_dir: str = "data",
        telegram_notifier=None,
        orders_repo=None,
        user_id: int | None = None,
    ):
        """
        Initialize order state manager.

        Phase 10: Added telegram_notifier, orders_repo, and user_id for manual activity detection.

        Args:
            history_path: Path to trades_history.json
            data_dir: Directory for OrderTracker data
            telegram_notifier: Optional TelegramNotifier for sending notifications
            orders_repo: Optional OrdersRepository for database updates
            user_id: Optional user ID for database operations
        """
        self.history_path = history_path
        self.data_dir = data_dir
        self.telegram_notifier = telegram_notifier
        self.orders_repo = orders_repo
        self.user_id = user_id

        # In-memory cache for active sell orders
        # Format: {symbol: {'order_id': str, 'target_price': float, 'qty': int, ...}}
        self.active_sell_orders: dict[str, dict[str, Any]] = {}

        # Phase 3: In-memory cache for active buy orders
        # Format: {order_id: {'symbol': str, 'quantity': float, 'order_id': str, 'original_price': float, 'original_quantity': float, ...}}
        # Phase 10: Added original_price and original_quantity to track manual modifications
        self.active_buy_orders: dict[str, dict[str, Any]] = {}

        # Order tracker for pending orders
        self._order_tracker = OrderTracker(data_dir=data_dir)

        # Thread lock for atomic operations
        self._lock = threading.Lock()

        logger.info(
            f"OrderStateManager initialized (history: {history_path}, data_dir: {data_dir})"
        )

    def register_sell_order(
        self,
        symbol: str,
        order_id: str,
        target_price: float,
        qty: int,
        ticker: str | None = None,
        **kwargs,
    ) -> bool:
        """
        Register new sell order with atomic updates to all state sources.

        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            order_id: Order ID from broker
            target_price: Target sell price
            qty: Order quantity
            ticker: Full ticker symbol (e.g., 'RELIANCE.NS')
            **kwargs: Additional order metadata

        Returns:
            True if successfully registered, False otherwise
        """
        with self._lock:
            try:
                base_symbol = extract_base_symbol(symbol).upper()

                # Check if order already exists in active_sell_orders
                existing_order = self.active_sell_orders.get(base_symbol)
                if existing_order and existing_order.get("order_id") == order_id:
                    # Order already registered - check if price needs updating
                    existing_price = existing_order.get("target_price", 0)
                    if existing_price != target_price and target_price > 0:
                        # Price changed - update it
                        logger.debug(
                            f"Order {order_id} already registered for {base_symbol}. "
                            f"Updating price from Rs {existing_price:.2f} to Rs {target_price:.2f}"
                        )
                        self.active_sell_orders[base_symbol]["target_price"] = target_price
                        self.active_sell_orders[base_symbol][
                            "last_updated"
                        ] = datetime.now().isoformat()
                        return True  # Return True after updating price
                    else:
                        # Order already registered with same or better price
                        # Skip duplicate registration
                        logger.debug(
                            f"Order {order_id} already registered for {base_symbol}. "
                            f"Existing price: Rs {existing_price:.2f}, "
                            f"New price: Rs {target_price:.2f}. "
                            f"Skipping duplicate registration."
                        )
                        return True  # Return True since order is already tracked

                # 1. Update in-memory cache
                self.active_sell_orders[base_symbol] = {
                    "order_id": order_id,
                    "target_price": target_price,
                    "qty": qty,
                    "symbol": symbol,
                    "ticker": ticker,
                    "registered_at": datetime.now().isoformat(),
                    **kwargs,
                }

                # 2. Add to pending orders tracker
                # (will skip if duplicate due to fix in add_pending_order)
                if ticker:
                    self._order_tracker.add_pending_order(
                        order_id=order_id,
                        symbol=symbol,
                        ticker=ticker,
                        qty=qty,
                        order_type="LIMIT",
                        variety="REGULAR",
                        price=target_price,
                    )

                logger.info(
                    f"Registered sell order: {base_symbol} "
                    f"(order_id: {order_id}, price: Rs {target_price:.2f}, qty: {qty})"
                )

                return True

            except Exception as e:
                logger.error(f"Error registering sell order {order_id}: {e}")
                return False

    def register_buy_order(
        self,
        symbol: str,
        order_id: str,
        quantity: float,
        price: float | None = None,
        ticker: str | None = None,
        **kwargs,
    ) -> bool:
        """
        Register new buy order with atomic updates to all state sources.

        Phase 3: Buy order tracking support.

        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            order_id: Order ID from broker
            quantity: Order quantity
            price: Order price (optional, for limit orders)
            ticker: Full ticker symbol (e.g., 'RELIANCE.NS')
            **kwargs: Additional order metadata

        Returns:
            True if successfully registered, False otherwise
        """
        with self._lock:
            try:
                base_symbol = extract_base_symbol(symbol).upper()

                # Check if order already exists
                if order_id in self.active_buy_orders:
                    logger.debug(f"Buy order {order_id} already registered for {base_symbol}")
                    return True

                # 1. Update in-memory cache
                # Phase 10: Store original values to detect manual modifications
                self.active_buy_orders[order_id] = {
                    "symbol": base_symbol,
                    "quantity": quantity,
                    "order_id": order_id,
                    "price": price,
                    "ticker": ticker,
                    "registered_at": datetime.now().isoformat(),
                    "original_price": price,  # Phase 10: Track original price
                    "original_quantity": quantity,  # Phase 10: Track original quantity
                    "is_manual_cancelled": False,  # Phase 10: Track if manually cancelled
                    **kwargs,
                }

                # 2. Add to pending orders tracker
                if ticker:
                    self._order_tracker.add_pending_order(
                        order_id=order_id,
                        symbol=symbol,
                        ticker=ticker,
                        qty=int(quantity),
                        order_type="LIMIT" if price else "MARKET",
                        variety="REGULAR",
                        price=price or 0,
                    )

                logger.info(
                    f"Registered buy order: {base_symbol} "
                    f"(order_id: {order_id}, qty: {quantity}, price: {price or 'MARKET'})"
                )

                return True

            except Exception as e:
                logger.error(f"Error registering buy order {order_id}: {e}")
                return False

    def mark_order_executed(
        self,
        symbol: str,
        order_id: str,
        execution_price: float,
        execution_qty: int | None = None,
    ) -> bool:
        """
        Mark order as executed with atomic updates to all state sources.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            execution_price: Price at which order executed
            execution_qty: Quantity executed (defaults to full qty)

        Returns:
            True if successfully updated, False otherwise
        """
        with self._lock:
            try:
                base_symbol = extract_base_symbol(symbol).upper()

                # Get order info before removing
                order_info = self.active_sell_orders.get(base_symbol, {})
                execution_qty = execution_qty or order_info.get("qty", 0)

                # 1. Remove from active tracking
                if base_symbol in self.active_sell_orders:
                    del self.active_sell_orders[base_symbol]

                # 2. Update order tracker status
                self._order_tracker.update_order_status(
                    order_id=order_id, status="EXECUTED", executed_qty=execution_qty
                )

                # 3. Update trade history
                mark_position_closed(
                    history_path=self.history_path,
                    symbol=base_symbol,
                    exit_price=execution_price,
                    sell_order_id=order_id,
                )

                logger.info(
                    f"Marked order as executed: {base_symbol} "
                    f"(order_id: {order_id}, price: Rs {execution_price:.2f}, qty: {execution_qty})"
                )

                return True

            except Exception as e:
                logger.error(f"Error marking order {order_id} as executed: {e}")
                return False

    def mark_buy_order_executed(
        self,
        symbol: str,
        order_id: str,
        execution_price: float,
        execution_qty: float | None = None,
    ) -> bool:
        """
        Mark buy order as executed and add new position to trade history.

        Phase 3: Buy order execution tracking.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            execution_price: Price at which order executed
            execution_qty: Quantity executed (defaults to full qty)

        Returns:
            True if successfully updated, False otherwise
        """
        with self._lock:
            try:
                base_symbol = extract_base_symbol(symbol).upper()

                # Get order info before removing
                order_info = self.active_buy_orders.get(order_id, {})
                execution_qty = execution_qty or order_info.get("quantity", 0)

                # 1. Remove from active tracking
                if order_id in self.active_buy_orders:
                    del self.active_buy_orders[order_id]

                # 2. Update order tracker status
                self._order_tracker.update_order_status(
                    order_id=order_id, status="EXECUTED", executed_qty=int(execution_qty)
                )

                # 3. Add new position to trade history
                try:
                    new_trade = {
                        "symbol": base_symbol,
                        "ticker": order_info.get("ticker", base_symbol),
                        "entry_price": execution_price,
                        "qty": execution_qty,
                        "entry_time": datetime.now().isoformat(),
                        "status": "open",
                        "buy_order_id": order_id,
                        "source": "AMO",
                    }
                    append_trade(self.history_path, new_trade)

                    logger.info(
                        f"Added new position to trade history: {base_symbol} "
                        f"(order_id: {order_id}, "
                        f"entry_price: Rs {execution_price:.2f}, qty: {execution_qty})"
                    )
                except Exception as e:
                    logger.error(f"Error adding position to trade history: {e}")
                    # Continue even if trade history update fails

                logger.info(
                    f"Marked buy order as executed: {base_symbol} "
                    f"(order_id: {order_id}, price: Rs {execution_price:.2f}, qty: {execution_qty})"
                )

                return True

            except Exception as e:
                logger.error(f"Error marking buy order {order_id} as executed: {e}")
                return False

    def update_sell_order_price(self, symbol: str, new_price: float) -> bool:
        """
        Update target price for an active sell order.

        Args:
            symbol: Trading symbol
            new_price: New target price

        Returns:
            True if updated, False if order not found
        """
        with self._lock:
            base_symbol = extract_base_symbol(symbol).upper()

            if base_symbol in self.active_sell_orders:
                self.active_sell_orders[base_symbol]["target_price"] = new_price
                self.active_sell_orders[base_symbol]["last_updated"] = datetime.now().isoformat()
                logger.debug(f"Updated sell order price: {base_symbol} -> Rs {new_price:.2f}")
                return True

            return False

    def remove_from_tracking(self, symbol: str, reason: str | None = None) -> bool:
        """
        Remove order from active tracking (e.g., rejected, cancelled).

        Args:
            symbol: Trading symbol
            reason: Reason for removal (optional)

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            base_symbol = extract_base_symbol(symbol).upper()

            if base_symbol in self.active_sell_orders:
                order_info = self.active_sell_orders[base_symbol]
                order_id = order_info.get("order_id")

                # Remove from active tracking
                del self.active_sell_orders[base_symbol]

                # Update order tracker if order_id exists
                if order_id:
                    self._order_tracker.update_order_status(order_id=order_id, status="CANCELLED")

                logger.info(
                    f"Removed order from tracking: {base_symbol} (reason: {reason or 'unknown'})"
                )

                return True

            return False

    def remove_buy_order_from_tracking(self, order_id: str, reason: str | None = None) -> bool:
        """
        Remove buy order from active tracking (e.g., rejected, cancelled).

        Phase 3: Buy order tracking support.

        Args:
            order_id: Order ID
            reason: Reason for removal (optional)

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if order_id in self.active_buy_orders:
                order_info = self.active_buy_orders[order_id]
                symbol = order_info.get("symbol", "UNKNOWN")

                # Remove from active tracking
                del self.active_buy_orders[order_id]

                # Update order tracker
                self._order_tracker.update_order_status(order_id=order_id, status="CANCELLED")

                logger.info(
                    f"Removed buy order from tracking: {symbol} (order_id: {order_id}, "
                    f"reason: {reason or 'unknown'})"
                )

                return True

            return False

    def get_active_sell_orders(self) -> dict[str, dict[str, Any]]:
        """
        Get all active sell orders.

        Returns:
            Dict of active sell orders {symbol: order_info}
        """
        with self._lock:
            return self.active_sell_orders.copy()

    def get_active_order(self, symbol: str) -> dict[str, Any] | None:
        """
        Get active sell order for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Order info dict or None if not found
        """
        base_symbol = extract_base_symbol(symbol).upper()
        return self.active_sell_orders.get(base_symbol)

    def get_active_buy_orders(self) -> dict[str, dict[str, Any]]:
        """
        Get all active buy orders.

        Phase 3: Buy order tracking support.

        Returns:
            Dict of active buy orders {order_id: order_info}
        """
        with self._lock:
            return self.active_buy_orders.copy()

    def get_active_buy_order(self, order_id: str) -> dict[str, Any] | None:
        """
        Get active buy order by order ID.

        Phase 3: Buy order tracking support.

        Args:
            order_id: Order ID

        Returns:
            Order info dict or None if not found
        """
        return self.active_buy_orders.get(order_id)

    def sync_with_broker(  # noqa: PLR0912, PLR0915
        self, orders_api, broker_orders: list[dict[str, Any]] | None = None
    ) -> dict[str, int]:
        """
        Sync state with broker to detect manual orders and status changes.

        Phase 3: Extended to check both buy and sell orders.

        Args:
            orders_api: Orders API client (with get_orders method)
            broker_orders: Optional pre-fetched broker orders list

        Returns:
            Stats dict with sync results
        """
        stats = {
            "checked": 0,
            "executed": 0,
            "rejected": 0,
            "cancelled": 0,
            "manual_sells": 0,
            "buy_checked": 0,
            "buy_executed": 0,
            "buy_rejected": 0,
            "buy_cancelled": 0,
        }

        try:
            # Fetch broker orders if not provided
            if broker_orders is None:
                orders_response = orders_api.get_orders() if orders_api else None
                broker_orders = orders_response.get("data", []) if orders_response else []

            # Check each active sell order
            active_symbols = list(self.active_sell_orders.keys())

            for symbol in active_symbols:
                order_info = self.active_sell_orders.get(symbol)
                if not order_info:
                    continue

                order_id = order_info.get("order_id")
                if not order_id:
                    continue

                stats["checked"] += 1

                # Find order in broker orders
                broker_order = None
                for bo in broker_orders:
                    broker_order_id = OrderFieldExtractor.get_order_id(bo)
                    if broker_order_id == order_id:
                        broker_order = bo
                        break

                if broker_order:
                    # Check status
                    status = OrderStatusParser.parse_status(broker_order)

                    if status in {OrderStatus.COMPLETE, OrderStatus.EXECUTED}:
                        # Order executed
                        execution_price = OrderFieldExtractor.get_price(
                            broker_order
                        ) or order_info.get("target_price", 0)
                        execution_qty = OrderFieldExtractor.get_quantity(
                            broker_order
                        ) or order_info.get("qty", 0)

                        self.mark_order_executed(symbol, order_id, execution_price, execution_qty)
                        stats["executed"] += 1

                    elif status == OrderStatus.REJECTED:
                        # Order rejected
                        rejection_reason = broker_order.get("rejectionReason") or "Unknown"
                        self.remove_from_tracking(symbol, reason=f"Rejected: {rejection_reason}")
                        stats["rejected"] += 1

                    elif status == OrderStatus.CANCELLED:
                        # Order cancelled
                        self.remove_from_tracking(symbol, reason="Cancelled")
                        stats["cancelled"] += 1

                else:
                    # Order not found in broker orders - might be executed
                    # Check if symbol has any executed orders
                    executed_orders = [
                        bo
                        for bo in broker_orders
                        if OrderFieldExtractor.get_symbol(bo).upper().startswith(symbol.upper())
                        and OrderStatusParser.is_completed(bo)
                        and OrderFieldExtractor.is_sell_order(bo)
                    ]

                    if executed_orders:
                        # Manual sell detected
                        logger.warning(f"Manual sell detected for {symbol}")
                        stats["manual_sells"] += 1
                        # Handle manual sell (could mark as executed)
                        # This is a placeholder - actual handling depends on requirements
                        self.remove_from_tracking(symbol, reason="Manual sell detected")

            # Phase 3: Check each active buy order
            active_buy_order_ids = list(self.active_buy_orders.keys())

            for order_id in active_buy_order_ids:
                order_info = self.active_buy_orders.get(order_id)
                if not order_info:
                    continue

                stats["buy_checked"] += 1

                # Find order in broker orders
                broker_order = None
                for bo in broker_orders:
                    broker_order_id = OrderFieldExtractor.get_order_id(bo)
                    if broker_order_id == order_id:
                        broker_order = bo
                        break

                if broker_order:
                    # Check status
                    status = OrderStatusParser.parse_status(broker_order)
                    symbol = order_info.get("symbol", "UNKNOWN")

                    # Phase 10: Detect manual modifications before checking status
                    self._detect_manual_modifications(order_id, order_info, broker_order, stats)

                    if status in {OrderStatus.COMPLETE, OrderStatus.EXECUTED}:
                        # Buy order executed
                        execution_price = OrderFieldExtractor.get_price(
                            broker_order
                        ) or order_info.get("price", 0)
                        execution_qty = OrderFieldExtractor.get_quantity(
                            broker_order
                        ) or order_info.get("quantity", 0)

                        self.mark_buy_order_executed(
                            symbol, order_id, execution_price, execution_qty
                        )
                        stats["buy_executed"] += 1

                    elif status == OrderStatus.REJECTED:
                        # Buy order rejected
                        rejection_reason = (
                            OrderFieldExtractor.get_rejection_reason(broker_order) or "Unknown"
                        )
                        self.remove_buy_order_from_tracking(
                            order_id, reason=f"Rejected: {rejection_reason}"
                        )
                        stats["buy_rejected"] += 1

                    elif status == OrderStatus.CANCELLED:
                        # Phase 10: Detect manual cancellation
                        # Check if there's explicit indication of manual cancellation
                        rejection_reason = (
                            OrderFieldExtractor.get_rejection_reason(broker_order) or ""
                        )
                        is_explicitly_manual = (
                            "user" in rejection_reason.lower()
                            or "manual" in rejection_reason.lower()
                            or order_info.get("is_manual_cancelled", False)
                        )

                        # If order is still in tracking AND explicitly marked as manual, treat as manual cancellation
                        # Otherwise, treat as system cancellation
                        if is_explicitly_manual and order_id in self.active_buy_orders:
                            # Order was cancelled manually (not by us)
                            if not order_info.get("is_manual_cancelled", False):
                                order_info["is_manual_cancelled"] = True
                            self._handle_manual_cancellation(order_id, order_info, broker_order)
                            stats["buy_manual_cancelled"] = stats.get("buy_manual_cancelled", 0) + 1
                        else:
                            # Order cancelled by system
                            self.remove_buy_order_from_tracking(order_id, reason="Cancelled")
                            stats["buy_cancelled"] += 1

            return stats

        except Exception as e:
            logger.error(f"Error syncing with broker: {e}")
            return stats

    def _detect_manual_modifications(
        self,
        order_id: str,
        order_info: dict[str, Any],
        broker_order: dict[str, Any],
        stats: dict[str, int],
    ) -> None:
        """
        Detect manual modifications to buy orders (price/qty changes).

        Phase 10: Manual activity detection.

        Args:
            order_id: Order ID
            order_info: Stored order info
            broker_order: Current broker order data
            stats: Stats dict to update
        """
        try:
            # Get original values
            original_price = order_info.get("original_price")
            original_quantity = order_info.get("original_quantity", order_info.get("quantity", 0))

            # Get current broker values
            broker_price = OrderFieldExtractor.get_price(broker_order)
            broker_quantity = OrderFieldExtractor.get_quantity(broker_order)

            modifications = []

            # Check for price modification (only for limit orders)
            if original_price is not None and broker_price is not None:
                if (
                    abs(original_price - broker_price) > 0.01
                ):  # Allow small floating point differences
                    modifications.append(f"price: Rs {original_price:.2f} → Rs {broker_price:.2f}")

            # Check for quantity modification
            if broker_quantity is not None and abs(original_quantity - broker_quantity) > 0:
                modifications.append(f"quantity: {original_quantity} → {broker_quantity}")

            if modifications:
                # Manual modification detected
                symbol = order_info.get("symbol", "UNKNOWN")
                modification_text = ", ".join(modifications)

                logger.warning(
                    f"Manual modification detected for buy order {order_id} ({symbol}): {modification_text}"
                )

                # Update stored values
                if broker_price is not None:
                    order_info["price"] = broker_price
                if broker_quantity is not None:
                    order_info["quantity"] = broker_quantity

                # Update database if available
                self._update_db_for_manual_modification(
                    order_id, symbol, broker_price, broker_quantity
                )

                # Send notification
                self._notify_manual_modification(symbol, order_id, modification_text)

                stats["buy_manual_modified"] = stats.get("buy_manual_modified", 0) + 1

        except Exception as e:
            logger.error(f"Error detecting manual modifications for order {order_id}: {e}")

    def _handle_manual_cancellation(
        self,
        order_id: str,
        order_info: dict[str, Any],
        broker_order: dict[str, Any],
    ) -> None:
        """
        Handle manual cancellation of buy order.

        Phase 10: Manual activity detection.

        Args:
            order_id: Order ID
            order_info: Stored order info
            broker_order: Broker order data
        """
        try:
            symbol = order_info.get("symbol", "UNKNOWN")
            cancellation_reason = (
                OrderFieldExtractor.get_rejection_reason(broker_order) or "User cancelled"
            )

            logger.warning(
                f"Manual cancellation detected for buy order {order_id} ({symbol}): {cancellation_reason}"
            )

            # Mark as manually cancelled
            order_info["is_manual_cancelled"] = True

            # Update database if available
            self._update_db_for_manual_cancellation(order_id, symbol, cancellation_reason)

            # Send notification
            self._notify_manual_cancellation(symbol, order_id, cancellation_reason)

            # Remove from tracking
            self.remove_buy_order_from_tracking(
                order_id, reason=f"Manual cancellation: {cancellation_reason}"
            )

        except Exception as e:
            logger.error(f"Error handling manual cancellation for order {order_id}: {e}")

    def _update_db_for_manual_modification(
        self,
        order_id: str,
        symbol: str,
        new_price: float | None,
        new_quantity: float | None,
    ) -> None:
        """
        Update database for manual modification.

        Phase 10: Database updates for manual activity.

        Args:
            order_id: Order ID
            symbol: Trading symbol
            new_price: New price (if modified)
            new_quantity: New quantity (if modified)
        """
        if not self.orders_repo or not self.user_id:
            return

        try:
            # Find order in database
            all_orders = self.orders_repo.list(self.user_id)
            db_order = None
            for order in all_orders:
                if (
                    order.broker_order_id == order_id or order.order_id == order_id
                ) and order.symbol.upper() == symbol.upper():
                    db_order = order
                    break

            if db_order:
                # Update order with new values
                update_data = {}
                if new_price is not None:
                    update_data["price"] = new_price
                if new_quantity is not None:
                    update_data["quantity"] = new_quantity
                # Mark as manual
                update_data["is_manual"] = True

                self.orders_repo.update(db_order, **update_data)
                logger.debug(f"Updated DB order {db_order.id} for manual modification")

        except Exception as e:
            logger.warning(f"Failed to update DB for manual modification: {e}")

    def _update_db_for_manual_cancellation(
        self, order_id: str, symbol: str, cancellation_reason: str
    ) -> None:
        """
        Update database for manual cancellation.

        Phase 10: Database updates for manual activity.

        Args:
            order_id: Order ID
            symbol: Trading symbol
            cancellation_reason: Reason for cancellation
        """
        if not self.orders_repo or not self.user_id:
            return

        try:
            # Find order in database
            all_orders = self.orders_repo.list(self.user_id)
            db_order = None
            for order in all_orders:
                if (
                    order.broker_order_id == order_id or order.order_id == order_id
                ) and order.symbol.upper() == symbol.upper():
                    db_order = order
                    break

            if db_order:
                # Mark as cancelled and manual
                self.orders_repo.mark_cancelled(
                    order=db_order, cancelled_reason=f"Manual: {cancellation_reason}"
                )
                self.orders_repo.update(db_order, is_manual=True)
                logger.debug(f"Updated DB order {db_order.id} for manual cancellation")

        except Exception as e:
            logger.warning(f"Failed to update DB for manual cancellation: {e}")

    def _notify_manual_modification(
        self, symbol: str, order_id: str, modification_text: str
    ) -> None:
        """
        Send notification for manual modification.

        Phase 10: Notifications for manual activity.
        Phase 4: Updated to use notify_order_modified() with preference checking.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            modification_text: Description of modifications (e.g., "price: Rs 100.00 → Rs 105.00, quantity: 10 → 15")
        """
        if not self.telegram_notifier or not self.telegram_notifier.enabled:
            return

        try:
            # Phase 4: Parse modification_text into structured changes dict
            changes = {}
            # Parse format: "price: Rs 100.00 → Rs 105.00, quantity: 10 → 15"
            parts = modification_text.split(", ")
            for part in parts:
                if ":" in part and "→" in part:
                    # Extract field name and values
                    field_part, values_part = part.split(":", 1)
                    field = field_part.strip()
                    values = values_part.split("→")
                    if len(values) == 2:
                        old_str = values[0].strip()
                        new_str = values[1].strip()

                        # Parse values based on field type
                        if field == "price":
                            # Remove "Rs" prefix and parse float
                            old_value = float(old_str.replace("Rs", "").strip())
                            new_value = float(new_str.replace("Rs", "").strip())
                            changes["price"] = (old_value, new_value)
                        elif field == "quantity":
                            old_value = int(float(old_str))  # Handle float quantities
                            new_value = int(float(new_str))
                            changes["quantity"] = (old_value, new_value)
                        else:
                            # Generic: try to parse as number, fallback to string
                            try:
                                old_value = float(old_str) if "." in old_str else int(old_str)
                                new_value = float(new_str) if "." in new_str else int(new_str)
                            except ValueError:
                                old_value = old_str
                                new_value = new_str
                            changes[field] = (old_value, new_value)

            # Phase 4: Use notify_order_modified() with preference checking
            self.telegram_notifier.notify_order_modified(
                symbol=symbol,
                order_id=order_id,
                changes=changes,
                user_id=self.user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to send manual modification notification: {e}")

    def _notify_manual_cancellation(
        self, symbol: str, order_id: str, cancellation_reason: str
    ) -> None:
        """
        Send notification for manual cancellation.

        Phase 10: Notifications for manual activity.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            cancellation_reason: Reason for cancellation
        """
        if not self.telegram_notifier or not self.telegram_notifier.enabled:
            return

        try:
            self.telegram_notifier.notify_order_cancelled(
                symbol=symbol,
                order_id=order_id,
                cancellation_reason=f"Manual: {cancellation_reason}",
                user_id=self.user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to send manual cancellation notification: {e}")

    def get_pending_orders(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        """
        Get pending orders from OrderTracker.

        Args:
            status_filter: Optional status filter (PENDING/OPEN/EXECUTED/etc.)

        Returns:
            List of pending order dicts
        """
        return self._order_tracker.get_pending_orders(status_filter=status_filter)

    def cleanup_expired_failed_orders(self) -> int:
        """
        Clean up expired failed orders from trade history.

        Returns:
            Number of orders removed
        """
        return cleanup_expired_failed_orders(self.history_path)

    def get_trade_history(self) -> dict[str, Any]:
        """
        Get full trade history.

        Returns:
            Trade history dict
        """
        return load_history(self.history_path)

    def reload_state(self):
        """
        Reload state from storage (useful after external changes).

        Note: This does not reload active_sell_orders from broker.
        Use sync_with_broker() for that.
        """
        # OrderTracker automatically loads from file
        # Trade history is loaded on-demand
        logger.debug("State reloaded from storage")
