"""
Paper Trading Broker Adapter
Simulates broker operations without real money
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

from ...config.paper_trading_config import PaperTradingConfig
from ...domain import (
    Exchange,
    Holding,
    IBrokerGateway,
    Money,
    Order,
    OrderStatus,
    OrderType,
    OrderVariety,
    TransactionType,
)
from ..persistence import PaperTradeStore
from ..simulation import OrderSimulator, PortfolioManager, PriceProvider


class PaperTradingBrokerAdapter(IBrokerGateway):
    def _sync_order_failure_to_db(
        self, order: Order, failure_type: str, reason: str = "", user_id: int = None
    ) -> None:
        """
        Sync paper trading order failure to database (for signal status update).

        This updates the database order status, which automatically triggers
        signal FAILED status via OrdersRepository methods.

        Args:
            order: Order that failed
            failure_type: 'rejected', 'failed', or 'cancelled'
            reason: Reason for failure
            user_id: User ID for DB sync (optional)
        """
        if not self.db_session:
            # No database integration available, skip sync
            return

        try:
            from src.infrastructure.persistence.orders_repository import OrdersRepository

            repo = OrdersRepository(self.db_session)
            # Try user_id argument first, then order.user_id if present
            resolved_user_id = user_id
            if resolved_user_id is None:
                resolved_user_id = getattr(order, "user_id", None)
            if resolved_user_id is None:
                logger.warning(
                    f"[PaperTrading] Cannot sync order failure to DB: user_id missing for order {getattr(order, 'order_id', None)}"
                )
                return
            db_order = repo.get_by_broker_order_id(resolved_user_id, order.order_id)
            if not db_order:
                logger.debug(
                    f"[PaperTrading] DB order not found for sync: {order.order_id} (may be pre-DB integration order)"
                )
                return
            if failure_type == "rejected":
                repo.mark_rejected(db_order, reason or "Paper trading rejection")
            elif failure_type == "failed":
                repo.mark_failed(db_order, reason or "Paper trading failure")
            elif failure_type == "cancelled":
                repo.mark_cancelled(db_order, reason or "Paper trading cancelled")
            logger.debug(
                f"[PaperTrading] Synced order failure to DB: {order.order_id} ({failure_type})"
            )
        except Exception as ex:
            # Don't fail order processing if database sync fails
            logger.warning(
                f"[PaperTrading] Failed to sync order failure to DB: {ex}", exc_info=True
            )

    def _sync_order_execution_to_db(
        self, order: Order, execution_price: Money, trade_info: dict | None = None
    ) -> None:
        """
        Sync paper trading order execution to database (orders and positions tables).

        This updates:
        - Order status to ONGOING (for buy orders) or CLOSED (for sell orders)
        - Creates/updates position in positions table (for buy orders)
        - Updates/closes position in positions table (for sell orders)

        Args:
            order: Order that executed
            execution_price: Execution price
            trade_info: Trade info dict (for sell orders, contains entry_price, realized_pnl, etc.)
        """
        if not self.db_session:
            # No database integration available, skip sync
            return

        try:
            from src.infrastructure.db.timezone_utils import ist_now
            from src.infrastructure.persistence.orders_repository import OrdersRepository
            from src.infrastructure.persistence.positions_repository import PositionsRepository

            orders_repo = OrdersRepository(self.db_session)
            positions_repo = PositionsRepository(self.db_session)

            # Get database order by broker_order_id
            # CRITICAL: Always use user_id to avoid MultipleResultsFound error
            # Try to get user_id from order metadata first
            user_id = getattr(order, "user_id", None)
            if not user_id:
                # Try to get from order metadata
                metadata = getattr(order, "metadata", None) or getattr(order, "_metadata", None)
                if metadata and isinstance(metadata, dict):
                    user_id = metadata.get("user_id")

            db_order = None
            if user_id:
                # Try with user_id first (more efficient and safe)
                db_order = orders_repo.get_by_broker_order_id(user_id, order.order_id)

            # If not found and user_id is available, try one more time with direct query
            # (handles edge cases where get_by_broker_order_id might have issues)
            if not db_order and user_id:
                from sqlalchemy import select

                from src.infrastructure.db.models import Orders

                stmt = select(Orders).where(
                    Orders.user_id == user_id, Orders.broker_order_id == order.order_id
                )
                result = self.db_session.execute(stmt).scalar_one_or_none()
                if result:
                    db_order = result

            # CRITICAL FIX: If user_id is not available, try to find order and extract user_id from it
            # Use first() instead of scalar_one_or_none() to avoid MultipleResultsFound error
            # Then use that user_id for subsequent operations
            if not db_order and not user_id:
                from sqlalchemy import select

                from src.infrastructure.db.models import Orders

                logger.warning(
                    f"[PaperTrading] user_id not available for order {order.order_id}. "
                    f"Searching database to find order and extract user_id. "
                    f"This may return incorrect order if multiple users have same broker_order_id."
                )
                stmt = select(Orders).where(Orders.broker_order_id == order.order_id)
                results = list(self.db_session.execute(stmt).scalars().all())

                if len(results) > 1:
                    # Extract user_ids from all results for logging
                    user_ids_found = [o.user_id for o in results if hasattr(o, 'user_id')]

                    logger.error(
                        f"[PaperTrading] ⚠️ MULTIPLE ORDERS FOUND for broker_order_id={order.order_id}! "
                        f"Found {len(results)} orders for user_ids: {user_ids_found}. "
                        f"This indicates duplicate broker_order_ids across users. "
                        f"Using first order (user_id={user_ids_found[0] if user_ids_found else 'unknown'}). "
                        f"This may cause incorrect position tracking!"
                    )

                if results:
                    # Get first order from results
                    found_order = results[0]
                    user_id = found_order.user_id
                    db_order = found_order
                    logger.info(
                        f"[PaperTrading] Found order {order.order_id} for user_id={user_id}. "
                        f"Using this user_id for sync."
                    )
                else:
                    logger.warning(
                        f"[PaperTrading] Order {order.order_id} not found in database. "
                        f"Cannot sync execution without user_id."
                    )

            if not db_order:
                logger.warning(
                    f"[PaperTrading] DB order not found for execution sync: {order.order_id}. "
                    f"Order executed in file but position not tracked in DB. "
                    f"Attempting to create position from order data."
                )
                # Try to create position directly from order data if db_order not found
                # This handles edge cases where order was created before DB integration
                # Get user_id from order metadata if not already available
                if not user_id:
                    metadata = getattr(order, "metadata", None) or getattr(order, "_metadata", None)
                    if metadata and isinstance(metadata, dict):
                        user_id = metadata.get("user_id")

                if order.is_buy_order() and user_id:
                    try:
                        from modules.kotak_neo_auto_trader.utils.symbol_utils import (
                            normalize_symbol,
                        )

                        # Extract symbol from order
                        symbol = normalize_symbol(order.symbol)
                        if symbol.endswith(".NS") or symbol.endswith(".BO"):
                            symbol = symbol[:-3]

                        # Check if position already exists
                        existing_pos = positions_repo.get_by_symbol(user_id, symbol)
                        if existing_pos and existing_pos.closed_at is None:
                            # Update existing position
                            existing_qty = existing_pos.quantity
                            existing_avg_price = existing_pos.avg_price
                            execution_qty = float(order.quantity)
                            execution_price_float = float(execution_price.amount)

                            total_cost = (existing_qty * existing_avg_price) + (
                                execution_qty * execution_price_float
                            )
                            new_qty = existing_qty + execution_qty
                            new_avg_price = (
                                total_cost / new_qty if new_qty > 0 else execution_price_float
                            )

                            positions_repo.upsert(
                                user_id=user_id,
                                symbol=symbol,
                                quantity=new_qty,
                                avg_price=new_avg_price,
                                auto_commit=True,
                            )
                            logger.info(
                                f"[PaperTrading] Created/updated position for {symbol} "
                                f"from order {order.order_id} (no DB order found)"
                            )
                        else:
                            # Create new position
                            positions_repo.upsert(
                                user_id=user_id,
                                symbol=symbol,
                                quantity=float(order.quantity),
                                avg_price=float(execution_price.amount),
                                opened_at=ist_now(),
                                entry_rsi=29.5,  # Default RSI
                                initial_entry_price=float(execution_price.amount),
                                auto_commit=True,
                            )
                            logger.info(
                                f"[PaperTrading] Created position for {symbol} "
                                f"from order {order.order_id} (no DB order found)"
                            )
                    except Exception as create_ex:
                        logger.warning(
                            f"[PaperTrading] Failed to create position from order data: {create_ex}",
                            exc_info=True,
                        )
                return

            # Use user_id from db_order (most reliable source)
            user_id = db_order.user_id

            # Mark order as executed in database
            execution_price_float = float(execution_price.amount)
            execution_qty = float(order.quantity)

            orders_repo.mark_executed(
                db_order,
                execution_price=execution_price_float,
                execution_qty=execution_qty,
                auto_commit=False,  # Commit after position update
            )

            # Extract symbol from database order (matches database format)
            # Use symbol from db_order to ensure consistency with database
            from modules.kotak_neo_auto_trader.utils.symbol_utils import (
                normalize_symbol,
            )

            symbol = (
                normalize_symbol(db_order.symbol)
                if db_order.symbol
                else normalize_symbol(order.symbol)
            )

            # Normalize symbol: remove .NS/.BO suffix if present, keep broker suffixes like -EQ
            if symbol.endswith(".NS") or symbol.endswith(".BO"):
                symbol = symbol[:-3]

            # Extract entry RSI from order metadata
            entry_rsi = None
            if db_order.order_metadata:
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

            if order.is_buy_order():
                # BUY ORDER: Create or update position
                existing_pos = positions_repo.get_by_symbol(user_id, symbol)

                if existing_pos and existing_pos.closed_at is None:
                    # Update existing open position (reentry)
                    existing_qty = existing_pos.quantity
                    existing_avg_price = existing_pos.avg_price

                    # Calculate new average price
                    total_cost = (existing_qty * existing_avg_price) + (
                        execution_qty * execution_price_float
                    )
                    new_qty = existing_qty + execution_qty
                    new_avg_price = total_cost / new_qty if new_qty > 0 else execution_price_float

                    # Update reentry tracking
                    reentry_count = (existing_pos.reentry_count or 0) + 1
                    reentries_array = []
                    if existing_pos.reentries:
                        if isinstance(existing_pos.reentries, dict):
                            reentries_array = list(existing_pos.reentries.get("reentries", []))
                        elif isinstance(existing_pos.reentries, list):
                            reentries_array = list(existing_pos.reentries)

                    # Add new reentry entry
                    reentry_data = {
                        "qty": int(execution_qty),
                        "level": None,  # Will be set if available in metadata
                        "rsi": float(entry_rsi),
                        "price": float(execution_price_float),
                        "time": ist_now().isoformat(),
                        "placed_at": (
                            db_order.placed_at.date().isoformat()
                            if db_order.placed_at
                            else ist_now().date().isoformat()
                        ),
                        "order_id": order.order_id,
                    }

                    # Extract reentry level from metadata if available
                    if db_order.order_metadata:
                        metadata = (
                            db_order.order_metadata
                            if isinstance(db_order.order_metadata, dict)
                            else {}
                        )
                        if metadata.get("rsi_level") is not None:
                            reentry_data["level"] = int(metadata["rsi_level"])

                    reentries_array.append(reentry_data)

                    # Update position
                    positions_repo.upsert(
                        user_id=user_id,
                        symbol=symbol,
                        quantity=new_qty,
                        avg_price=new_avg_price,
                        reentry_count=reentry_count,
                        reentries={"reentries": reentries_array},
                        last_reentry_price=execution_price_float,
                        auto_commit=False,  # Commit with order
                    )
                    logger.debug(
                        f"[PaperTrading] Updated position for {symbol}: "
                        f"qty {existing_qty} -> {new_qty}, "
                        f"avg_price Rs {existing_avg_price:.2f} -> Rs {new_avg_price:.2f}, "
                        f"reentry_count: {reentry_count}"
                    )
                else:
                    # Create new position
                    positions_repo.upsert(
                        user_id=user_id,
                        symbol=symbol,
                        quantity=execution_qty,
                        avg_price=execution_price_float,
                        opened_at=ist_now(),
                        entry_rsi=entry_rsi,
                        initial_entry_price=execution_price_float,
                        auto_commit=False,  # Commit with order
                    )
                    logger.debug(
                        f"[PaperTrading] Created position for {symbol}: "
                        f"qty={execution_qty}, price=Rs {execution_price_float:.2f}, "
                        f"entry_rsi={entry_rsi:.2f}"
                    )

            else:
                # SELL ORDER: Update or close position
                existing_pos = positions_repo.get_by_symbol(user_id, symbol)
                if not existing_pos:
                    logger.warning(
                        f"[PaperTrading] Sell order executed for {symbol} but no position found in DB. "
                        f"Order {order.order_id} executed in file but position not tracked."
                    )
                elif existing_pos.closed_at is None:
                    # Validate execution quantity doesn't exceed position quantity
                    if execution_qty > existing_pos.quantity:
                        logger.warning(
                            f"[PaperTrading] Sell order quantity ({execution_qty}) exceeds "
                            f"position quantity ({existing_pos.quantity}) for {symbol}. "
                            f"Using position quantity instead."
                        )
                        execution_qty = existing_pos.quantity

                    # Calculate remaining quantity
                    remaining_qty = existing_pos.quantity - execution_qty

                    if remaining_qty <= 0:
                        # Close position completely
                        exit_price = execution_price_float
                        exit_reason = "PAPER_TRADE_SELL"
                        realized_pnl = trade_info.get("realized_pnl", 0.0) if trade_info else None
                        realized_pnl_pct = None
                        if (
                            realized_pnl is not None
                            and existing_pos.avg_price
                            and execution_qty > 0
                        ):
                            # Use execution_qty (sold quantity) instead of full position quantity
                            cost_basis = existing_pos.avg_price * execution_qty
                            realized_pnl_pct = (
                                (realized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0
                            )

                        positions_repo.mark_closed(
                            user_id=user_id,
                            symbol=symbol,
                            closed_at=ist_now(),
                            exit_price=exit_price,
                            exit_reason=exit_reason,
                            realized_pnl=realized_pnl,
                            realized_pnl_pct=realized_pnl_pct,
                            sell_order_id=db_order.id,
                            auto_commit=False,  # Commit with order
                        )
                        logger.debug(
                            f"[PaperTrading] Closed position for {symbol}: "
                            f"exit_price=Rs {exit_price:.2f}, realized_pnl=Rs {realized_pnl:.2f}"
                        )
                    else:
                        # Partial sell - update quantity
                        positions_repo.upsert(
                            user_id=user_id,
                            symbol=symbol,
                            quantity=remaining_qty,
                            avg_price=existing_pos.avg_price,  # Keep same avg price
                            auto_commit=False,  # Commit with order
                        )
                        logger.debug(
                            f"[PaperTrading] Updated position for {symbol}: "
                            f"qty {existing_pos.quantity} -> {remaining_qty} (partial sell)"
                        )

            # Commit both order and position updates together
            self.db_session.commit()
            logger.debug(
                f"[PaperTrading] Synced order execution to DB: {order.order_id} "
                f"({order.transaction_type.value} {order.symbol})"
            )

        except Exception as ex:
            # Don't fail order processing if database sync fails
            # Note: Order execution in file already happened, so we only rollback DB transaction
            # This is intentional - paper trading should work even if DB is unavailable
            logger.warning(
                f"[PaperTrading] Failed to sync order execution to DB: {ex}. "
                f"Order {order.order_id} executed in file but not synced to database. "
                f"This may cause position tracking inconsistencies.",
                exc_info=True,
            )
            # Rollback DB transaction on error (file execution already happened, which is fine)
            try:
                if self.db_session.in_transaction():
                    self.db_session.rollback()
            except Exception as rollback_ex:
                logger.debug(f"[PaperTrading] Rollback failed: {rollback_ex}")

    """
    Paper trading adapter implementing IBrokerGateway

    Simulates all broker operations:
    - Order placement and execution
    - Portfolio management
    - Balance tracking
    - P&L calculation

    No real money involved - perfect for testing strategies!
    """

    def __init__(
        self,
        user_id: int,
        config: PaperTradingConfig | None = None,
        storage_path: str | None = None,
        db_session=None,
    ):
        """
        Initialize paper trading adapter

        Args:
            user_id: User ID for generating user-specific order IDs (required)
            config: Paper trading configuration (uses default if None)
            storage_path: Custom storage path (optional)
            db_session: Database session for syncing order failures (optional)
        """
        if user_id is None:
            raise ValueError("user_id is required for PaperTradingBrokerAdapter")

        # Configuration
        self.config = config or PaperTradingConfig.default()

        # Storage
        storage_path = storage_path or self.config.storage_path
        self.store = PaperTradeStore(storage_path, auto_save=self.config.auto_save)

        # Database session for syncing order failures to database
        self.db_session = db_session

        # User ID for generating unique order IDs (required)
        self.user_id = user_id

        # Components
        self.price_provider = PriceProvider(
            mode=self.config.price_source,
            cache_duration_seconds=self.config.price_cache_duration_seconds,
        )
        self.order_simulator = OrderSimulator(self.config, self.price_provider)
        self.portfolio = PortfolioManager()

        # State
        self._connected = False
        self._order_counter = 0
        self._warned_symbols: set[str] = (
            set()
        )  # Track symbols we already warned about in this session

        # Initialize if needed
        self._initialize()

    def _initialize(self) -> None:
        """Initialize or restore state"""
        account = self.store.get_account()

        if account is None:
            # First time - initialize account
            logger.info(
                f"? Initializing new paper trading account with "
                f"Rs {self.config.initial_capital:,.2f}"
            )
            self.store.initialize_account(self.config.initial_capital, config=self.config.to_dict())
        else:
            # Restore existing state
            logger.info(
                f"?? Restoring paper trading account (Balance: Rs {account['available_cash']:,.2f})"
            )
            # Always save the current config to ensure max_position_size and other settings are up-to-date
            config_file = self.store.storage_path / "config.json"
            import json

            with open(config_file, "w") as f:
                json.dump(self.config.to_dict(), f, indent=2)
            self._restore_state()

    def _restore_state(self) -> None:
        """Restore portfolio from storage"""
        holdings = self.store.get_all_holdings()

        for symbol, holding_data in holdings.items():
            holding = Holding(
                symbol=symbol,
                exchange=Exchange[holding_data.get("exchange", "NSE")],
                quantity=holding_data["quantity"],
                average_price=Money(holding_data["average_price"]),
                current_price=Money(holding_data["current_price"]),
                last_updated=datetime.fromisoformat(holding_data["last_updated"]),
            )
            self.portfolio._holdings[symbol] = holding

        logger.info(f"?? Restored {len(holdings)} holdings")

    # ===== CONNECTION MANAGEMENT =====

    def connect(self) -> bool:
        """Establish connection (simulated)"""
        if self._connected:
            logger.info("? Already connected to paper trading")
            return True

        self._connected = True
        logger.info("? Connected to paper trading system")
        logger.info(f"? Available balance: Rs {self.get_available_balance().amount:,.2f}")
        logger.info(f"? Holdings: {len(self.portfolio.get_all_holdings())}")

        return True

    def disconnect(self) -> bool:
        """Disconnect (simulated)"""
        if not self._connected:
            return True

        # Save state before disconnect
        self.store.save_all()
        self._connected = False
        logger.info("? Disconnected from paper trading system")

        return True

    def is_connected(self) -> bool:
        """Check if connected"""
        return self._connected

    # ===== ORDER MANAGEMENT =====

    def place_order(self, order: Order) -> str:
        """
        Place an order (simulate execution)

        Args:
            order: Order to place

        Returns:
            Order ID

        Raises:
            ConnectionError: If not connected
            ValueError: If order validation fails
            RuntimeError: If order placement fails
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to paper trading system")

        # Generate order ID
        order_id = self._generate_order_id()

        logger.info(
            f"? Placing order: {order.transaction_type.value} "
            f"{order.quantity} {order.symbol} @ "
            f"{order.order_type.value}"
            f"{' (AMO)' if order.is_amo_order() else ''}"
        )

        try:
            # Mark as placed
            order.place(order_id)

            # Save order
            self._save_order(order)

            # For AMO orders: Always save as PENDING/OPEN, never execute immediately
            # Execution happens at 9:15 AM after quantity adjustment at 9:05 AM
            if order.is_amo_order():
                logger.info(
                    f"? AMO order placed - saved as PENDING (will execute at 9:15 AM): {order.symbol}"
                )
                # Order remains in OPEN status, will be executed at market open
            # For regular market orders, execute immediately if market is open
            elif order.order_type == OrderType.MARKET:
                # Check if market is open before executing
                if self.order_simulator._is_market_open(order):
                    self._execute_order(order)
                else:
                    logger.info(
                        f"? Market order placed during off-market hours - will execute when market opens: {order.symbol}"
                    )
            # For limit orders, they will be checked by check_and_execute_pending_orders()

            return order_id

        except Exception as e:
            import traceback

            logger.error(f"? Order placement failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Order placement failed: {e}")

    def _execute_order(self, order: Order) -> None:
        """
        Execute an order

        Args:
            order: Order to execute
        """
        # Get current balance
        account = self.store.get_account()
        available_cash = account["available_cash"]

        # For buy orders, validate funds first
        if order.is_buy_order():
            # Estimate order value
            # Try to get original ticker from order metadata (for .NS suffix)
            price_symbol = order.symbol
            if (
                hasattr(order, "metadata")
                and order.metadata
                and "original_ticker" in order.metadata
            ):
                price_symbol = order.metadata["original_ticker"]
            elif (
                hasattr(order, "_metadata")
                and order._metadata
                and "original_ticker" in order._metadata
            ):
                price_symbol = order._metadata["original_ticker"]
            # Try with .NS suffix if not present
            elif not price_symbol.endswith(".NS") and not price_symbol.endswith(".BO"):
                price_symbol = f"{price_symbol}.NS"

            estimated_price = self.price_provider.get_price(price_symbol)
            if estimated_price is None:
                order.reject(f"Price not available for {order.symbol} (tried {price_symbol})")
                self._save_order(order)
                self._sync_order_failure_to_db(
                    order, "rejected", f"Price not available for {order.symbol}"
                )
                return

            estimated_value = float(estimated_price) * float(order.quantity)

            # Validate order value
            is_valid, error = self.order_simulator.validate_order_value(
                estimated_value, available_cash
            )

            if not is_valid:
                logger.warning(f"[WARN]? Order validation failed: {error}")
                order.reject(error)
                self._save_order(order)
                self._sync_order_failure_to_db(order, "rejected", error)
                return

        # For sell orders, validate quantity
        if order.is_sell_order():
            can_sell, error = self.portfolio.can_sell(order.symbol, order.quantity)
            if not can_sell:
                logger.warning(f"[WARN]? Cannot sell: {error}")
                order.reject(error)
                self._save_order(order)
                self._sync_order_failure_to_db(order, "rejected", error)
                return

        # Execute order
        success, message, execution_price = self.order_simulator.execute_order(order)

        if success and execution_price:
            # Mark as executed
            order.execute(execution_price, order.quantity)

            # Update portfolio and get P&L for sell orders
            trade_info = self._update_portfolio_after_execution(order, execution_price)

            # Record transaction with P&L info
            self._record_transaction(order, execution_price, trade_info)

            # Sync successful execution to database (orders and positions tables)
            self._sync_order_execution_to_db(order, execution_price, trade_info)

            logger.info(
                f"? Order executed: {order.symbol} "
                f"{order.quantity} @ Rs {execution_price.amount:.2f}"
            )
        else:
            # Order execution failed or pending
            msg = (
                f"[WARN]? Order execution failed for {order.symbol}: {message}. "
                f"Order remains in {order.status.value} status."
            )
            if order.symbol in self._warned_symbols:
                logger.info(msg)  # Downgrade repeat warnings to INFO to reduce log noise
            else:
                logger.warning(msg)
                self._warned_symbols.add(order.symbol)
            # Sync failure to DB
            self._sync_order_failure_to_db(order, "failed", message)

        # Save updated order
        self._save_order(order)

    def _update_portfolio_after_execution(
        self, order: Order, execution_price: Money
    ) -> dict | None:
        """
        Update portfolio and balance after order execution

        Returns:
            Trade info dict for sell orders (entry_price, realized_pnl, etc.), None for buy orders
        """
        account = self.store.get_account()
        trade_info = None

        if order.is_buy_order():
            # Add holding
            self.portfolio.add_holding(
                order.symbol, order.quantity, execution_price, order.exchange
            )

            # Deduct cash
            order_value = float(execution_price.amount) * order.quantity
            charges = self.order_simulator.calculate_charges(order_value, is_buy=True)
            total_cost = order_value + charges

            new_balance = account["available_cash"] - total_cost
            self.store.update_balance(new_balance)

            logger.info(
                f"? Deducted Rs {total_cost:.2f} (Value: Rs {order_value:.2f}, "
                f"Charges: Rs {charges:.2f})"
            )

        else:  # SELL
            # Get entry price before reducing holding
            holding = self.portfolio.get_holding(order.symbol)
            entry_price = holding.average_price.amount if holding else 0.0

            # Reduce holding
            remaining_holding, realized_pnl = self.portfolio.reduce_holding(
                order.symbol, order.quantity, execution_price
            )

            # Add cash
            order_value = float(execution_price.amount) * order.quantity
            charges = self.order_simulator.calculate_charges(order_value, is_buy=False)
            net_proceeds = order_value - charges

            new_balance = account["available_cash"] + net_proceeds
            self.store.update_balance(new_balance)

            # Prepare trade info for transaction recording
            trade_info = {
                "entry_price": entry_price,
                "exit_price": execution_price.amount,
                "realized_pnl": realized_pnl.amount,
                "charges": charges,
            }

            logger.info(
                f"? Added Rs {net_proceeds:.2f} (Value: Rs {order_value:.2f}, "
                f"Charges: Rs {charges:.2f}, P&L: Rs {realized_pnl.amount:.2f})"
            )

        # Update P&L
        self._update_pnl()

        # Persist holdings
        self._persist_holdings()

        return trade_info

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled, False otherwise
        """
        if not self.is_connected():
            raise ConnectionError("Not connected")

        order_dict = self.store.get_order_by_id(order_id)
        if not order_dict:
            logger.warning(f"[WARN]? Order not found: {order_id}")
            return False

        # Check if order can be cancelled
        status = order_dict.get("status")
        if status not in ["PENDING", "OPEN"]:
            logger.warning(f"[WARN]? Cannot cancel order in {status} status")
            return False

        # Update order status
        self.store.update_order(
            order_id, {"status": "CANCELLED", "cancelled_at": datetime.now().isoformat()}
        )

        # Sync cancellation to DB using stored db_session
        if self.db_session:
            try:
                from src.infrastructure.persistence.orders_repository import OrdersRepository

                repo = OrdersRepository(self.db_session)
                # Try to get user_id from order_dict if present
                user_id = order_dict.get("user_id")
                db_order = None
                if user_id:
                    db_order = repo.get_by_broker_order_id(user_id, order_id)
                if db_order:
                    repo.mark_cancelled(db_order, "Paper trading cancelled")
                    logger.debug(f"[PaperTrading] Synced order cancellation to DB: {order_id}")
            except Exception as ex:
                # Don't fail cancellation if database sync fails
                logger.warning(
                    f"[PaperTrading] Failed to sync order cancellation to DB: {ex}", exc_info=True
                )

        logger.info(f"? Cancelled order: {order_id}")
        return True

    def get_order(self, order_id: str) -> Order | None:
        """Get order by ID"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        order_dict = self.store.get_order_by_id(order_id)
        if not order_dict:
            return None

        return self._dict_to_order(order_dict)

    def get_all_orders(self) -> list[Order]:
        """Get all orders"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders_data = self.store.get_all_orders()
        return [self._dict_to_order(o) for o in orders_data]

    def get_pending_orders(self) -> list[Order]:
        """Get pending orders"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders_data = self.store.get_pending_orders()
        return [self._dict_to_order(o) for o in orders_data]

    def check_and_execute_pending_orders(self) -> dict:
        """
        Check all pending limit orders and execute if price conditions are met
        This includes AMO orders that were placed during off-market hours

        Returns:
            Summary dict with counts of checked and executed orders
        """
        if not self.is_connected():
            raise ConnectionError("Not connected")

        summary = {"checked": 0, "executed": 0, "still_pending": 0, "amo_executed": 0}

        pending_orders = self.get_pending_orders()
        summary["checked"] = len(pending_orders)

        for order in pending_orders:
            # Check limit orders (including AMO orders)
            if order.order_type != OrderType.LIMIT:
                continue

            # For AMO orders, check if it's time to execute
            if order.is_amo_order():
                if not self.order_simulator.should_execute_amo(order):
                    # Not yet time to execute AMO order
                    summary["still_pending"] += 1
                    continue

            # Try to execute the order
            try:
                self._execute_order(order)

                # Check if order executed (status changed from OPEN/PENDING)
                if order.is_executed():
                    summary["executed"] += 1
                    if order.is_amo_order():
                        summary["amo_executed"] += 1

                    # Get execution price safely
                    execution_price_str = "N/A"
                    if order.executed_price:
                        try:
                            execution_price_str = f"Rs {order.executed_price.amount:.2f}"
                        except (AttributeError, TypeError):
                            execution_price_str = f"Rs {order.executed_price}"

                    logger.info(
                        f"Pending {'AMO ' if order.is_amo_order() else ''}limit order executed: {order.symbol} "
                        f"{order.transaction_type.value} @ {execution_price_str}"
                    )
                else:
                    summary["still_pending"] += 1
            except Exception as e:
                logger.error(f"Error checking/executing pending order {order.order_id}: {e}")
                summary["still_pending"] += 1

        if summary["executed"] > 0:
            logger.info(
                f"Pending orders check: {summary['executed']} executed "
                f"({summary['amo_executed']} AMO), {summary['still_pending']} still pending"
            )

        return summary

    # ===== PORTFOLIO MANAGEMENT =====

    def get_holdings(self) -> list[Holding]:
        """Get all holdings"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        # Update current prices
        holdings = self.portfolio.get_all_holdings()
        symbols = [h.symbol for h in holdings]

        if symbols:
            prices = self.price_provider.get_prices(symbols)
            self.portfolio.update_prices(prices)

        return holdings

    def get_holding(self, symbol: str) -> Holding | None:
        """Get holding for symbol"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        holding = self.portfolio.get_holding(symbol)

        if holding:
            # Update current price
            price = self.price_provider.get_price(symbol)
            if price:
                self.portfolio.update_price(symbol, Money(price))

        return holding

    # ===== ACCOUNT MANAGEMENT =====

    def get_account_limits(self) -> dict[str, Any]:
        """Get account limits"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        account = self.store.get_account()
        portfolio_value = self.portfolio.calculate_portfolio_value()

        return {
            "available_cash": Money(account["available_cash"]),
            "margin_used": Money(account.get("margin_used", 0.0)),
            "margin_available": Money(account["available_cash"]),
            "collateral": portfolio_value,
            "portfolio_value": portfolio_value,
            "total_value": Money(account["available_cash"]) + portfolio_value,
        }

    def get_available_balance(self) -> Money:
        """Get available cash balance"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        account = self.store.get_account()
        return Money(account["available_cash"])

    # ===== UTILITY METHODS =====

    def search_orders_by_symbol(self, symbol: str) -> list[Order]:
        """Search orders by symbol"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders_data = self.store.get_orders_by_symbol(symbol)
        return [self._dict_to_order(o) for o in orders_data]

    def cancel_pending_buys_for_symbol(self, symbol: str) -> int:
        """Cancel all pending BUY orders for symbol"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders = self.search_orders_by_symbol(symbol)
        cancelled_count = 0

        for order in orders:
            if order.is_buy_order() and order.is_active():
                if self.cancel_order(order.order_id):
                    cancelled_count += 1

        return cancelled_count

    # ===== HELPER METHODS =====

    def _generate_order_id(self) -> str:
        """
        Generate unique order ID with user_id to prevent collisions across users.

        Format: PT{timestamp}U{user_id}{counter:04d}
        Example: PT20260109U10001 (for user_id=1, counter=1 on 2026-01-09)
        """
        self._order_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d")
        # Include user_id in order ID to ensure uniqueness across users
        return f"PT{timestamp}U{self.user_id}{self._order_counter:04d}"

    def _save_order(self, order: Order) -> None:
        """Save order to storage"""
        order_dict = order.to_dict()

        # Convert price to float for JSON serialization
        if order_dict.get("price"):
            price_str = str(order_dict["price"])
            price_clean = price_str.replace("Rs ", "").replace(",", "").strip()
            order_dict["price"] = float(price_clean) if price_clean else None

        # Convert executed_price to float
        if order_dict.get("executed_price"):
            exec_price_str = str(order_dict["executed_price"])
            exec_price_clean = exec_price_str.replace("Rs ", "").replace(",", "").strip()
            order_dict["executed_price"] = float(exec_price_clean) if exec_price_clean else None

        # Check if order exists
        existing = self.store.get_order_by_id(order.order_id)

        if existing:
            # Update existing order
            self.store.update_order(order.order_id, order_dict)
        else:
            # Add new order
            self.store.add_order(order_dict)

    def _record_transaction(
        self, order: Order, execution_price: Money, trade_info: dict | None = None
    ) -> None:
        """
        Record a transaction with P&L for sell orders

        Args:
            order: The executed order
            execution_price: Execution price
            trade_info: Optional dict with entry_price, realized_pnl, etc. for sell orders
        """
        order_value = float(execution_price.amount) * order.quantity
        charges = self.order_simulator.calculate_charges(order_value, order.is_buy_order())

        transaction = {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "transaction_type": order.transaction_type.value,
            "quantity": order.quantity,
            "price": float(execution_price.amount),
            "order_value": order_value,
            "charges": charges,
            "timestamp": datetime.now().isoformat(),
        }

        # For sell orders, include P&L information from trade_info
        if order.is_sell_order() and trade_info:
            entry_price = trade_info["entry_price"]
            exit_price = trade_info["exit_price"]
            realized_pnl = trade_info["realized_pnl"]
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            transaction["entry_price"] = float(entry_price)
            transaction["exit_price"] = float(exit_price)
            transaction["realized_pnl"] = float(realized_pnl)
            transaction["pnl_percentage"] = float(pnl_pct)
            transaction["exit_reason"] = (
                order._metadata.get("exit_reason", "Target Hit")
                if hasattr(order, "_metadata") and order._metadata
                else "Manual"
            )

            logger.info(
                f"? Trade completed: {order.symbol} - "
                f"Entry: Rs {entry_price:.2f}, Exit: Rs {exit_price:.2f}, "
                f"P&L: Rs {realized_pnl:+.2f} ({pnl_pct:+.2f}%)"
            )

        self.store.add_transaction(transaction)

    def _update_pnl(self) -> None:
        """Update P&L in account"""
        realized_pnl = self.portfolio.get_realized_pnl()
        unrealized_pnl = self.portfolio.calculate_unrealized_pnl()
        total_pnl = realized_pnl + unrealized_pnl

        self.store.update_pnl(
            float(total_pnl.amount), float(realized_pnl.amount), float(unrealized_pnl.amount)
        )

    def _persist_holdings(self) -> None:
        """Persist holdings to storage"""
        holdings = self.portfolio.to_dict_list()

        for holding in holdings:
            # Convert Money strings to float values for JSON serialization
            holding_data = holding.copy()
            holding_data["average_price"] = float(
                holding["average_price"].replace("Rs ", "").replace(",", "")
            )
            holding_data["current_price"] = float(
                holding["current_price"].replace("Rs ", "").replace(",", "")
            )
            holding_data["cost_basis"] = float(
                holding["cost_basis"].replace("Rs ", "").replace(",", "")
            )
            holding_data["market_value"] = float(
                holding["market_value"].replace("Rs ", "").replace(",", "")
            )
            holding_data["pnl"] = float(
                holding["pnl"].replace("Rs ", "").replace(",", "").replace("+", "")
            )
            self.store.add_or_update_holding(holding["symbol"], holding_data)

    def _dict_to_order(self, order_dict: dict) -> Order:
        """Convert dictionary to Order entity"""
        # Parse price - handle both numeric and formatted strings (for backward compatibility)
        price = None
        if order_dict.get("price"):
            price_val = order_dict["price"]
            if isinstance(price_val, (int, float)):
                price = Money(float(price_val))
            else:
                # Handle formatted string (backward compatibility)
                price_str = str(price_val)
                price_clean = price_str.replace("Rs ", "").replace(",", "").strip()
                if price_clean:
                    price = Money(float(price_clean))

        # Restore variety (default to REGULAR if not present for backward compatibility)
        variety = OrderVariety.REGULAR
        if "variety" in order_dict:
            variety = OrderVariety[order_dict["variety"]]

        order = Order(
            symbol=order_dict["symbol"],
            quantity=order_dict["quantity"],
            order_type=OrderType[order_dict["order_type"]],
            transaction_type=TransactionType[order_dict["transaction_type"]],
            price=price,
            variety=variety,  # Restore variety
            order_id=order_dict.get("order_id"),
            status=OrderStatus[order_dict["status"]],
            remarks=order_dict.get("remarks", ""),
        )

        # Restore timestamps
        if order_dict.get("placed_at"):
            order.placed_at = datetime.fromisoformat(order_dict["placed_at"])
        if order_dict.get("executed_at"):
            order.executed_at = datetime.fromisoformat(order_dict["executed_at"])
        if order_dict.get("cancelled_at"):
            order.cancelled_at = datetime.fromisoformat(order_dict["cancelled_at"])

        return order

    # ===== ADMIN METHODS =====

    def reset(self) -> None:
        """Reset paper trading account (WARNING: Destructive!)"""
        logger.warning("[WARN]? Resetting paper trading account...")
        self.store.reset()
        self.portfolio.reset()
        self._order_counter = 0
        self._initialize()
        logger.info("? Account reset complete")

    def get_summary(self) -> dict:
        """Get comprehensive account summary"""
        if not self.is_connected():
            self.connect()

        account = self.store.get_account()
        portfolio_summary = self.portfolio.get_summary()

        return {
            "account": account,
            "portfolio": portfolio_summary,
            "statistics": self.store.get_statistics(),
            "price_cache": self.price_provider.get_cache_info(),
        }
