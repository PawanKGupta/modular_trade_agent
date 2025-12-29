"""
Paper Trading Service Adapter

Provides a TradingService-compatible interface for paper trading mode.
Uses PaperTradingBrokerAdapter instead of real broker authentication.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import (
    PaperTradingBrokerAdapter,
)
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter
from src.infrastructure.db.models import TradeMode
from src.infrastructure.logging import get_user_logger

logger = logging.getLogger(__name__)


class PaperTradingServiceAdapter:
    """
    Adapter that provides TradingService-compatible interface for paper trading.

    This allows individual services to work in paper trading mode without
    requiring broker credentials.
    """

    def __init__(
        self,
        user_id: int,
        db_session,
        strategy_config=None,
        initial_capital: float = 100000.0,
        storage_path: str | None = None,
        skip_execution_tracking: bool = False,
    ):
        """
        Initialize paper trading service adapter.

        Args:
            user_id: User ID for this service instance
            db_session: SQLAlchemy database session
            strategy_config: User-specific StrategyConfig (optional)
            initial_capital: Starting virtual capital (default Rs 1 lakh)
            storage_path: Where to store paper trading data (user-specific if None)
            skip_execution_tracking: If True, skip execution tracking in wrapper
        """
        self.user_id = user_id
        self.db = db_session
        self.strategy_config = strategy_config
        self.skip_execution_tracking = skip_execution_tracking

        # Set storage path to user-specific if not provided
        if storage_path is None:
            storage_path = f"paper_trading/user_{user_id}"

        self.initial_capital = initial_capital
        self.storage_path = storage_path

        # Paper trading components
        self.config: PaperTradingConfig | None = None
        self.broker: PaperTradingBrokerAdapter | None = None
        self.reporter: PaperTradeReporter | None = None

        # User-scoped logger
        self.logger = get_user_logger(user_id=user_id, db=db_session, module="PaperTradingService")

        # Task execution flags
        self.tasks_completed = {
            "buy_orders": False,
            "eod_cleanup": False,
            "premarket_retry": False,
            "premarket_amo_adjustment": False,
            "sell_monitor_started": False,
        }

        # Engine-like interface for compatibility
        self.engine = None  # Will be set up to use paper trading broker

        # Sell order tracking - Frozen EMA9 strategy (matches backtest)
        # Format: {symbol: {'order_id': str, 'target_price': float,
        #                   'qty': int, 'entry_date': str, 'ticker': str}}
        self.active_sell_orders = {}
        self._sell_orders_file = Path(self.storage_path) / "active_sell_orders.json"

        # RSI Exit: Cache for RSI10 values {symbol: rsi10_value}
        # Cached at market open (previous day's RSI10), updated with real-time if available
        self.rsi10_cache: dict[str, float] = {}

        # RSI Exit: Track orders converted to market {symbol}
        # Prevents duplicate conversion attempts
        self.converted_to_market: set[str] = set()

        # Service state (for scheduler control)
        self.running = False
        self.shutdown_requested = False

    def initialize(self) -> bool:
        """
        Initialize paper trading service.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info("=" * 80, action="initialize")
            self.logger.info("PAPER TRADING SERVICE INITIALIZATION", action="initialize")
            self.logger.info("=" * 80, action="initialize")
            self.logger.info(
                f"[WARN]?  PAPER TRADING MODE - NO REAL MONEY "
                f"(Capital: Rs {self.initial_capital:,.2f})",
                action="initialize",
            )
            self.logger.info("=" * 80, action="initialize")

            # Create paper trading configuration
            # For paper trading, max_position_size should match paper_trading_initial_capital
            # This allows the full capital to be used for a single position if needed
            max_position_size = self.initial_capital  # Use paper trading capital
            self.logger.info(
                f"Paper Trading Config - Initial Capital: Rs {self.initial_capital:,.2f}, "
                f"Max Position Size: Rs {max_position_size:,.2f}",
                action="initialize",
            )

            self.logger.info(
                f"Creating paper trading config (Capital: Rs {self.initial_capital:,.2f}, "
                f"Max Position Size: Rs {max_position_size:,.2f})...",
                action="initialize",
            )
            self.config = PaperTradingConfig(
                initial_capital=self.initial_capital,
                enable_slippage=True,
                enable_fees=True,
                enforce_market_hours=False,  # Allow testing anytime
                price_source="live",  # Use live prices
                storage_path=self.storage_path,
                auto_save=True,
                max_position_size=max_position_size,  # Use user's trading config
            )

            # Initialize paper trading broker
            self.logger.info("Initializing paper trading broker...", action="initialize")
            try:
                self.broker = PaperTradingBrokerAdapter(self.config)
            except Exception as broker_init_error:
                self.logger.error(
                    f"Failed to create paper trading broker: {broker_init_error}",
                    exc_info=True,
                    action="initialize",
                )
                raise RuntimeError(
                    f"Failed to create paper trading broker: {broker_init_error}"
                ) from broker_init_error

            try:
                if not self.broker.connect():
                    self.logger.error(
                        "Failed to connect to paper trading system", action="initialize"
                    )
                    raise RuntimeError("Failed to connect to paper trading system")
            except Exception as connect_error:
                self.logger.error(
                    f"Failed to connect to paper trading system: {connect_error}",
                    exc_info=True,
                    action="initialize",
                )
                raise RuntimeError(
                    f"Failed to connect to paper trading system: {connect_error}"
                ) from connect_error

            self.logger.info("? Paper trading broker connected", action="initialize")

            # Load existing sell orders from file to avoid duplicates on restart
            self._load_sell_orders_from_file()

            # Execute any pending MARKET orders from previous sessions
            try:
                pending_orders = self.broker.get_pending_orders()
                market_orders = [o for o in pending_orders if o.order_type.value == "MARKET"]
                if market_orders:
                    self.logger.info(
                        f"Found {len(market_orders)} pending MARKET orders from previous session",
                        action="initialize",
                    )
                    for order in market_orders:
                        self.logger.info(
                            f"Executing pending order: {order.symbol} x{order.quantity}",
                            action="initialize",
                        )
                        self.broker._execute_order(order)
                    self.logger.info(
                        f"Executed {len(market_orders)} pending orders", action="initialize"
                    )
            except Exception as e:
                self.logger.warning(f"Failed to execute pending orders: {e}", action="initialize")

            # Initialize reporter
            self.reporter = PaperTradeReporter(self.broker.store)

            # Create a mock engine object that uses paper trading broker
            # This allows AutoTradeEngine methods to work with paper trading
            self.engine = PaperTradingEngineAdapter(
                broker=self.broker,
                user_id=self.user_id,
                db_session=self.db,
                strategy_config=self.strategy_config,
                logger=self.logger,
                storage_path=self.storage_path,
            )

            self.logger.info("Service initialized successfully", action="initialize")
            self.logger.info("=" * 80, action="initialize")

            # Show current portfolio status
            self._show_portfolio_status()

            return True

        except Exception as e:
            self.logger.error(
                f"Service initialization failed: {e}", exc_info=e, action="initialize"
            )
            return False

    def _show_portfolio_status(self):
        """Display current portfolio status"""
        try:
            if not self.broker:
                return

            balance = self.broker.get_available_balance()
            holdings = self.broker.get_holdings()

            self.logger.info(f"? Available Balance: Rs {balance.amount:,.2f}", action="initialize")
            self.logger.info(f"? Holdings: {len(holdings)}", action="initialize")

            if holdings:
                for holding in holdings:
                    pnl = holding.calculate_pnl()
                    self.logger.info(
                        f"  - {holding.symbol}: {holding.quantity} shares @ "
                        f"Rs {holding.average_price.amount:.2f} (P&L: Rs {pnl.amount:.2f})",
                        action="initialize",
                    )
        except Exception as e:
            self.logger.warning(f"Could not display portfolio status: {e}", action="initialize")

    def run_buy_orders(self):
        """4:05 PM - Place AMO buy orders for next day (paper trading)"""
        from src.application.services.task_execution_wrapper import execute_task

        summary_result = {}

        with execute_task(
            self.user_id,
            self.db,
            "buy_orders",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            self.logger.info("", action="run_buy_orders")
            self.logger.info("=" * 80, action="run_buy_orders")
            self.logger.info(
                "TASK: PLACE BUY ORDERS (4:05 PM) - PAPER TRADING", action="run_buy_orders"
            )
            self.logger.info("=" * 80, action="run_buy_orders")

            if not self.engine:
                error_msg = "Paper trading engine not initialized. Call initialize() first."
                self.logger.error(error_msg, action="run_buy_orders")
                raise RuntimeError(error_msg)

            # Verify broker is connected
            if not self.broker or not self.broker.is_connected():
                error_msg = "Paper trading broker not connected. Reconnecting..."
                self.logger.warning(error_msg, action="run_buy_orders")
                if self.broker and not self.broker.connect():
                    raise RuntimeError("Failed to connect to paper trading broker")

            # Load recommendations using the same logic as real trading
            recs = self.engine.load_latest_recommendations()
            self.logger.info(
                f"Loaded {len(recs)} recommendations from CSV", action="run_buy_orders"
            )

            if recs:
                # Filter to only buy/strong_buy (same as real trading)
                buy_recs = [r for r in recs if r.verdict.lower() in ["buy", "strong_buy"]]
                self.logger.info(
                    f"Filtered to {len(buy_recs)} buy/strong_buy recommendations",
                    action="run_buy_orders",
                )

                if buy_recs:
                    # Place orders using paper trading broker
                    summary = self.engine.place_new_entries(buy_recs)
                    self.logger.info(f"Buy orders summary: {summary}", action="run_buy_orders")
                    task_context["recommendations_count"] = len(buy_recs)
                    task_context["summary"] = summary
                    summary_result = summary
                else:
                    self.logger.info(
                        "No buy/strong_buy recommendations to place", action="run_buy_orders"
                    )
                    task_context["recommendations_count"] = 0
                    summary_result = {"message": "No buy/strong_buy recommendations found"}
            else:
                self.logger.warning(
                    "No recommendations found in CSV files. Make sure analysis has been run.",
                    action="run_buy_orders",
                )
                task_context["recommendations_count"] = 0
                summary_result = {"message": "No recommendations found in CSV files"}

            # Check and place re-entry orders (same as real trading)
            # Re-entry should be checked regardless of whether there are fresh entry recommendations
            self.logger.info("Checking re-entry conditions...", action="run_buy_orders")
            reentry_summary = self.engine.place_reentry_orders()
            self.logger.info(f"Re-entry orders summary: {reentry_summary}", action="run_buy_orders")
            self.logger.info(
                f"  - Attempted: {reentry_summary.get('attempted', 0)}, "
                f"Placed: {reentry_summary.get('placed', 0)}, "
                f"Failed (balance): {reentry_summary.get('failed_balance', 0)}, "
                f"Skipped: {reentry_summary.get('skipped_duplicates', 0) + reentry_summary.get('skipped_invalid_rsi', 0) + reentry_summary.get('skipped_missing_data', 0) + reentry_summary.get('skipped_invalid_qty', 0)}",
                action="run_buy_orders",
            )

            self.tasks_completed["buy_orders"] = True
            self.logger.info("Buy orders placement completed", action="run_buy_orders")

        # Return summary for execution details (after context manager exits)
        return summary_result

    def run_premarket_retry(self):
        """9:00 AM - Retry failed orders from previous day (paper trading)"""
        from src.application.services.task_execution_wrapper import execute_task

        with execute_task(
            self.user_id,
            self.db,
            "premarket_retry",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            self.logger.info("", action="run_premarket_retry")
            self.logger.info("=" * 80, action="run_premarket_retry")
            self.logger.info(
                "TASK: PREMARKET RETRY (9:00 AM) - PAPER TRADING", action="run_premarket_retry"
            )
            self.logger.info("=" * 80, action="run_premarket_retry")

            if not self.engine:
                error_msg = "Paper trading engine not initialized. Call initialize() first."
                self.logger.error(error_msg, action="run_premarket_retry")
                raise RuntimeError(error_msg)

            # Load recommendations and retry failed orders
            recs = self.engine.load_latest_recommendations()
            if recs:
                summary = self.engine.place_new_entries(recs)
                self.logger.info(
                    f"Pre-market retry summary: {summary}", action="run_premarket_retry"
                )
                task_context["recommendations_count"] = len(recs)
                task_context["summary"] = summary
            else:
                self.logger.info("No recommendations to retry", action="run_premarket_retry")
                task_context["recommendations_count"] = 0

            self.tasks_completed["premarket_retry"] = True
            self.logger.info("Pre-market retry completed", action="run_premarket_retry")

    def adjust_amo_quantities_premarket(self) -> dict[str, int]:
        """
        9:05 AM - Pre-market AMO quantity adjustment (paper trading)

        Adjusts AMO order quantities based on pre-market prices to keep capital constant.
        This matches the real broker behavior where quantities are adjusted before market open.

        Returns:
            Summary dict with adjustment statistics
        """
        from src.application.services.task_execution_wrapper import execute_task

        summary = {
            "total_orders": 0,
            "adjusted": 0,
            "no_adjustment_needed": 0,
            "price_unavailable": 0,
            "modification_failed": 0,
            "skipped_not_enabled": 0,
            "cancelled_above_ema9": 0,
        }

        with execute_task(
            self.user_id,
            self.db,
            "premarket_amo_adjustment",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            self.logger.info("", action="adjust_amo_quantities_premarket")
            self.logger.info("=" * 80, action="adjust_amo_quantities_premarket")
            self.logger.info(
                "TASK: PRE-MARKET AMO ADJUSTMENT (9:05 AM) - PAPER TRADING",
                action="adjust_amo_quantities_premarket",
            )
            self.logger.info("=" * 80, action="adjust_amo_quantities_premarket")

            if not self.broker or not self.broker.is_connected():
                self.logger.error(
                    "Paper trading broker not connected", action="adjust_amo_quantities_premarket"
                )
                return summary

            # Get all pending AMO buy orders
            pending_orders = self.broker.get_pending_orders()
            amo_buy_orders = [
                order
                for order in pending_orders
                if order.is_amo_order() and order.is_buy_order() and order.is_active()
            ]

            if not amo_buy_orders:
                self.logger.info(
                    "No pending AMO buy orders found", action="adjust_amo_quantities_premarket"
                )
                task_context["total_orders"] = 0
                return summary

            summary["total_orders"] = len(amo_buy_orders)
            task_context["total_orders"] = len(amo_buy_orders)
            self.logger.info(
                f"Found {len(amo_buy_orders)} pending AMO buy orders",
                action="adjust_amo_quantities_premarket",
            )

            # Get target capital from strategy config
            target_capital = (
                self.strategy_config.user_capital
                if self.strategy_config and hasattr(self.strategy_config, "user_capital")
                else 200000.0
            )

            from math import floor

            # Process each AMO order
            for order in amo_buy_orders:
                try:
                    # Get original ticker from metadata for price fetching
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
                    elif not price_symbol.endswith(".NS") and not price_symbol.endswith(".BO"):
                        price_symbol = f"{price_symbol}.NS"

                    # Fetch pre-market price
                    premarket_price = self.broker.price_provider.get_price(price_symbol)
                    if not premarket_price or premarket_price <= 0:
                        self.logger.warning(
                            f"{order.symbol}: Pre-market price not available",
                            action="adjust_amo_quantities_premarket",
                        )
                        summary["price_unavailable"] += 1
                        continue

                    original_qty = order.quantity
                    self.logger.info(
                        f"{order.symbol}: Pre-market price = Rs {premarket_price:.2f}, "
                        f"current qty = {original_qty}",
                        action="adjust_amo_quantities_premarket",
                    )

                    # Check if pre-market price is above EMA9-1% (cancel order if so)
                    ema9 = None
                    try:
                        ema9 = self._calculate_ema9(price_symbol)
                    except Exception as e:
                        self.logger.warning(
                            f"{order.symbol}: Failed to calculate EMA9: {e}",
                            action="adjust_amo_quantities_premarket",
                        )

                    # Check if pre-market price > EMA9 - 1%
                    if ema9 and ema9 > 0:
                        ema9_threshold = ema9 * 0.99  # EMA9 - 1%
                        if premarket_price > ema9_threshold:
                            self.logger.warning(
                                f"{order.symbol}: Pre-market price (Rs {premarket_price:.2f}) > EMA9-1% "
                                f"(Rs {ema9_threshold:.2f}, EMA9: Rs {ema9:.2f}) - Cancelling order",
                                action="adjust_amo_quantities_premarket",
                            )
                            try:
                                self.broker.cancel_order(order.order_id)
                                self.logger.info(
                                    f"✅ {order.symbol}: Order cancelled due to gap-up above EMA9-1%",
                                    action="adjust_amo_quantities_premarket",
                                )
                                summary["cancelled_above_ema9"] += 1

                                # Update database order status if available
                                if self.db:
                                    try:
                                        from src.infrastructure.db.models import (
                                            OrderStatus as DbOrderStatus,
                                        )
                                        from src.infrastructure.persistence.orders_repository import (
                                            OrdersRepository,
                                        )

                                        orders_repo = OrdersRepository(self.db)
                                        db_order = orders_repo.get_by_broker_order_id(
                                            self.user_id, order.order_id
                                        )
                                        if db_order:
                                            orders_repo.update(
                                                db_order,
                                                status=DbOrderStatus.CANCELLED,
                                                reason=f"Pre-market price (Rs {premarket_price:.2f}) > EMA9-1% (Rs {ema9_threshold:.2f})",
                                            )
                                            self.logger.info(
                                                f"{order.symbol}: DB order record updated - cancelled due to EMA9 validation",
                                                action="adjust_amo_quantities_premarket",
                                            )
                                    except Exception as db_err:
                                        self.logger.warning(
                                            f"{order.symbol}: Failed to update DB record: {db_err}",
                                            action="adjust_amo_quantities_premarket",
                                        )

                                continue  # Skip quantity adjustment for cancelled order
                            except Exception as cancel_err:
                                self.logger.error(
                                    f"{order.symbol}: Error cancelling order above EMA9-1%: {cancel_err}",
                                    exc_info=True,
                                    action="adjust_amo_quantities_premarket",
                                )
                                summary["modification_failed"] += 1
                    elif ema9 is None:
                        self.logger.warning(
                            f"{order.symbol}: EMA9 calculation failed - proceeding with quantity adjustment",
                            action="adjust_amo_quantities_premarket",
                        )

                    # Recalculate quantity to keep capital constant
                    new_qty = max(1, floor(target_capital / premarket_price))

                    # Check if adjustment is needed
                    if new_qty == original_qty:
                        self.logger.info(
                            f"{order.symbol}: No adjustment needed (qty={original_qty})",
                            action="adjust_amo_quantities_premarket",
                        )
                        summary["no_adjustment_needed"] += 1
                        continue

                    # Calculate gap percentage
                    original_price = float(order.price.amount) if order.price else premarket_price
                    gap_pct = ((premarket_price - original_price) / original_price) * 100

                    self.logger.info(
                        f"{order.symbol}: Adjusting AMO order: "
                        f"qty {original_qty} → {new_qty}, "
                        f"price Rs {original_price:.2f} → Rs {premarket_price:.2f} "
                        f"(gap: {gap_pct:+.2f}%, capital: Rs {target_capital:,.0f})",
                        action="adjust_amo_quantities_premarket",
                    )

                    # Update order quantity (cancel old and place new)
                    # For MARKET orders, only quantity needs to be updated
                    # Price is logged for tracking but not used (MARKET orders execute at market price)
                    try:
                        # Cancel old order
                        self.broker.cancel_order(order.order_id)

                        # Create new order with adjusted quantity
                        # For MARKET orders, price parameter is not needed
                        # For LIMIT orders, update price to pre-market price
                        from modules.kotak_neo_auto_trader.domain import (
                            Money,
                            Order,
                        )

                        # Use pre-market price for LIMIT orders, None for MARKET orders
                        new_price = (
                            Money(premarket_price)
                            if order.order_type.value == "LIMIT"
                            else (order.price if order.price else None)
                        )

                        new_order = Order(
                            symbol=order.symbol,
                            quantity=new_qty,
                            order_type=order.order_type,
                            transaction_type=order.transaction_type,
                            price=new_price,
                            variety=order.variety,
                            exchange=order.exchange,
                            validity=order.validity,
                        )

                        # Preserve metadata
                        if hasattr(order, "metadata") and order.metadata:
                            new_order.metadata = order.metadata
                        elif hasattr(order, "_metadata") and order._metadata:
                            new_order._metadata = order._metadata

                        # Place new order
                        new_order_id = self.broker.place_order(new_order)
                        self.logger.info(
                            f"✅ {order.symbol}: AMO order modified successfully "
                            f"(#{order.order_id} → #{new_order_id}, "
                            f"qty: {original_qty} → {new_qty}, "
                            f"price logged: Rs {original_price:.2f} → Rs {premarket_price:.2f}, "
                            f"capital: Rs {original_qty * original_price:,.0f} → Rs {new_qty * premarket_price:,.0f})",
                            action="adjust_amo_quantities_premarket",
                        )
                        summary["adjusted"] += 1

                    except Exception as modify_error:
                        self.logger.error(
                            f"{order.symbol}: Failed to modify AMO order: {modify_error}",
                            exc_info=True,
                            action="adjust_amo_quantities_premarket",
                        )
                        summary["modification_failed"] += 1

                except Exception as e:
                    self.logger.error(
                        f"Error processing AMO order {order.symbol}: {e}",
                        exc_info=True,
                        action="adjust_amo_quantities_premarket",
                    )
                    summary["modification_failed"] += 1

            task_context["summary"] = summary
            self.logger.info(
                f"Pre-market AMO adjustment completed: {summary}",
                action="adjust_amo_quantities_premarket",
            )

        return summary

    def execute_amo_orders_at_market_open(self) -> dict[str, int]:
        """
        9:15 AM - Execute pending AMO orders at market open (paper trading)

        Executes all pending AMO buy orders that were placed during off-market hours.
        This matches the real broker behavior where AMO orders execute at market open.

        Returns:
            Summary dict with execution statistics
        """
        from src.application.services.task_execution_wrapper import execute_task

        summary = {
            "total_orders": 0,
            "executed": 0,
            "failed": 0,
            "still_pending": 0,
        }

        with execute_task(
            self.user_id,
            self.db,
            "execute_amo_orders",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            self.logger.info("", action="execute_amo_orders_at_market_open")
            self.logger.info("=" * 80, action="execute_amo_orders_at_market_open")
            self.logger.info(
                "TASK: EXECUTE AMO ORDERS AT MARKET OPEN (9:15 AM) - PAPER TRADING",
                action="execute_amo_orders_at_market_open",
            )
            self.logger.info("=" * 80, action="execute_amo_orders_at_market_open")

            if not self.broker or not self.broker.is_connected():
                self.logger.error(
                    "Paper trading broker not connected", action="execute_amo_orders_at_market_open"
                )
                return summary

            # Get all pending AMO buy orders
            pending_orders = self.broker.get_pending_orders()
            amo_buy_orders = [
                order
                for order in pending_orders
                if order.is_amo_order() and order.is_buy_order() and order.is_active()
            ]

            if not amo_buy_orders:
                self.logger.info(
                    "No pending AMO buy orders to execute",
                    action="execute_amo_orders_at_market_open",
                )
                task_context["total_orders"] = 0
                return summary

            summary["total_orders"] = len(amo_buy_orders)
            task_context["total_orders"] = len(amo_buy_orders)
            self.logger.info(
                f"Found {len(amo_buy_orders)} pending AMO buy orders to execute",
                action="execute_amo_orders_at_market_open",
            )

            # Execute each AMO order
            for order in amo_buy_orders:
                try:
                    self.logger.info(
                        f"Executing AMO order: {order.symbol} x{order.quantity}",
                        action="execute_amo_orders_at_market_open",
                    )

                    # Execute the order (this will use the opening price logic)
                    self.broker._execute_order(order)

                    # Check if order executed successfully
                    if order.is_executed():
                        summary["executed"] += 1
                        self.logger.info(
                            f"✅ AMO order executed: {order.symbol} x{order.quantity} "
                            f"@ Rs {order.executed_price.amount:.2f}",
                            action="execute_amo_orders_at_market_open",
                        )
                    else:
                        summary["still_pending"] += 1
                        self.logger.warning(
                            f"⚠️ AMO order still pending: {order.symbol} "
                            f"(Status: {order.status.value})",
                            action="execute_amo_orders_at_market_open",
                        )

                except Exception as e:
                    summary["failed"] += 1
                    self.logger.error(
                        f"❌ Failed to execute AMO order {order.symbol}: {e}",
                        exc_info=True,
                        action="execute_amo_orders_at_market_open",
                    )

            task_context["summary"] = summary
            self.logger.info(
                f"AMO order execution completed: {summary}",
                action="execute_amo_orders_at_market_open",
            )

        return summary

    def run_sell_monitor(self):
        """
        9:15 AM - Place sell orders and start monitoring (paper trading)

        Strategy: FROZEN EMA9 (matches backtest with 76% success rate)
        - Place limit sell orders at current EMA9
        - Target is FROZEN (not updated)
        - Exit conditions: High >= Target OR RSI > 50
        - Matches 10-year backtest data used for ML training
        """
        from src.application.services.task_execution_wrapper import execute_task

        # Only log to database on first start, not on every monitoring cycle
        if not self.tasks_completed.get("sell_monitor_started"):
            with execute_task(
                self.user_id,
                self.db,
                "sell_monitor",
                self.logger,
                track_execution=not self.skip_execution_tracking,
            ) as task_context:
                self.logger.info("", action="run_sell_monitor")
                self.logger.info("=" * 80, action="run_sell_monitor")
                self.logger.info(
                    "TASK: SELL MONITOR (9:15 AM) - PAPER TRADING", action="run_sell_monitor"
                )
                self.logger.info("=" * 80, action="run_sell_monitor")
                self.logger.info(
                    "STRATEGY: Frozen EMA9 target (76% success rate in backtest)",
                    action="run_sell_monitor",
                )
                self.logger.info("=" * 80, action="run_sell_monitor")

                if not self.engine:
                    error_msg = "Paper trading engine not initialized. Call initialize() first."
                    self.logger.error(error_msg, action="run_sell_monitor")
                    raise RuntimeError(error_msg)

                if not self.broker:
                    error_msg = "Paper trading broker not initialized."
                    self.logger.error(error_msg, action="run_sell_monitor")
                    raise RuntimeError(error_msg)

                # Place sell orders for all holdings at frozen EMA9 target
                try:
                    self._place_sell_orders()
                    task_context["sell_orders_placed"] = len(self.active_sell_orders)
                except Exception as e:
                    self.logger.error(
                        f"Failed to place sell orders: {e}",
                        exc_info=True,
                        action="run_sell_monitor",
                    )

                self.tasks_completed["sell_monitor_started"] = True

        # Monitor sell orders every minute during market hours
        # Check exit conditions: High >= Target OR RSI > 50
        try:
            self._monitor_sell_orders()
        except Exception as e:
            self.logger.error(
                f"Sell monitoring error: {e}", exc_info=True, action="run_sell_monitor"
            )

    def run_eod_cleanup(self):
        """6:00 PM - End-of-day cleanup (paper trading)"""
        from src.application.services.task_execution_wrapper import execute_task

        with execute_task(
            self.user_id,
            self.db,
            "eod_cleanup",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            self.logger.info("", action="run_eod_cleanup")
            self.logger.info("=" * 80, action="run_eod_cleanup")
            self.logger.info(
                "TASK: EOD CLEANUP (6:00 PM) - PAPER TRADING", action="run_eod_cleanup"
            )
            self.logger.info("=" * 80, action="run_eod_cleanup")

            # Generate daily report
            if self.reporter:
                try:
                    self.logger.info("? Generating daily report...", action="run_eod_cleanup")
                    self.reporter.print_summary()

                    # Export report
                    from datetime import datetime

                    timestamp = datetime.now().strftime("%Y%m%d")
                    report_path = f"{self.storage_path}/reports/report_{timestamp}.json"
                    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
                    self.reporter.export_to_json(report_path)
                    self.logger.info(f"? Report saved to: {report_path}", action="run_eod_cleanup")
                    task_context["report_path"] = report_path
                except Exception as e:
                    self.logger.error(
                        f"Failed to generate report: {e}", exc_info=e, action="run_eod_cleanup"
                    )

            # Reset flags for next day
            self.logger.info(
                "Resetting task flags for next trading day...", action="run_eod_cleanup"
            )
            self.tasks_completed = {
                "buy_orders": False,
                "eod_cleanup": False,
                "premarket_retry": False,
                "premarket_amo_adjustment": False,
                "sell_monitor_started": False,
            }
            task_context["tasks_reset"] = True

            self.logger.info("Service ready for next trading day", action="run_eod_cleanup")
            self.tasks_completed["eod_cleanup"] = True

    def _place_sell_orders(self):
        """
        Place sell orders for all holdings at frozen EMA9 target.

        Strategy: Frozen EMA9 (matches 10-year backtest with 76% success rate)
        - Calculate current EMA9 for each holding
        - Place limit sell order at EMA9 price
        - Target is FROZEN (never updated)
        - Track in active_sell_orders
        """
        from datetime import datetime

        from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType

        holdings = self.broker.get_holdings()

        if not holdings:
            self.logger.info("No holdings to place sell orders for", action="_place_sell_orders")
            return

        self.logger.info(
            f"Placing sell orders for {len(holdings)} holdings...", action="_place_sell_orders"
        )

        # Get pending sell orders from broker to avoid duplicates
        pending_orders = self.broker.get_pending_orders() if self.broker else []
        # Normalize pending order symbols for comparison (extract base symbols)
        from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

        pending_sell_base_symbols = {
            extract_base_symbol(o.symbol).upper()
            for o in pending_orders
            if o.is_sell_order() and o.is_active()
        }
        # Also create a map of base symbol -> full symbol for active_sell_orders lookup
        active_sell_base_symbols = {
            extract_base_symbol(s).upper(): s for s in self.active_sell_orders.keys()
        }

        for holding in holdings:
            try:
                symbol = holding.symbol  # Full symbol from holdings (e.g., "RELIANCE-EQ")
                symbol_base = extract_base_symbol(symbol).upper()  # Base symbol for comparison
                ticker = f"{symbol_base}.NS"  # Use base symbol for ticker
                quantity = holding.quantity

                # Skip if already have active sell order (in memory or broker)
                # Compare using base symbols since active_sell_orders might have base symbols
                if (
                    symbol_base in active_sell_base_symbols
                    or symbol_base in pending_sell_base_symbols
                ):
                    self.logger.debug(
                        f"Skipping {symbol} - already has active sell order "
                        f"(in memory: {symbol_base in active_sell_base_symbols}, "
                        f"in broker: {symbol_base in pending_sell_base_symbols})",
                        action="_place_sell_orders",
                    )
                    # If it's in broker but not in memory, add it to memory for tracking
                    if (
                        symbol_base in pending_sell_base_symbols
                        and symbol_base not in active_sell_base_symbols
                    ):
                        # Try to find the order details from broker
                        for order in pending_orders:
                            order_base = extract_base_symbol(order.symbol).upper()
                            if (
                                order_base == symbol_base
                                and order.is_sell_order()
                                and order.is_active()
                            ):
                                # Estimate target price from order price if available
                                target_price = (
                                    float(order.price.amount)
                                    if hasattr(order, "price") and hasattr(order.price, "amount")
                                    else None
                                )
                                if target_price:
                                    # Use base symbol as key to match existing convention
                                    self.active_sell_orders[symbol_base] = {
                                        "order_id": (
                                            order.order_id
                                            if hasattr(order, "order_id")
                                            else "unknown"
                                        ),
                                        "target_price": target_price,
                                        "qty": quantity,
                                        "ticker": ticker,
                                        "entry_date": datetime.now().strftime("%Y-%m-%d"),
                                    }
                                    self.logger.info(
                                        f"Restored sell order tracking for {symbol_base} from broker",
                                        action="_place_sell_orders",
                                    )
                    # Check if holdings quantity has increased (re-entry happened)
                    # and update sell order quantity and target to match
                    # Use base symbol to find the order in active_sell_orders
                    if symbol_base in active_sell_base_symbols:
                        order_key = active_sell_base_symbols[symbol_base]
                        current_order_qty = self.active_sell_orders[order_key].get("qty", 0)
                        if quantity > current_order_qty:
                            self.logger.info(
                                f"Holdings increased for {symbol_base} ({current_order_qty} -> {quantity}), "
                                f"updating sell order quantity and target",
                                action="_place_sell_orders",
                            )
                            # Recalculate EMA9 target (matches backtest behavior)
                            new_target = self._calculate_ema9(ticker)
                            self._update_sell_order_quantity(order_key, quantity, new_target)
                    continue

                # Calculate EMA9 target (initial entry - will be updated on re-entry)
                ema9_target = self._calculate_ema9(ticker)

                if ema9_target is None or ema9_target <= 0:
                    self.logger.warning(
                        f"Could not calculate EMA9 for {symbol}, skipping",
                        action="_place_sell_orders",
                    )
                    continue

                # Create and place sell order at EMA9 target
                from modules.kotak_neo_auto_trader.domain import Money

                order = Order(
                    symbol=symbol,
                    quantity=quantity,
                    order_type=OrderType.LIMIT,
                    transaction_type=TransactionType.SELL,
                    price=Money(ema9_target),
                )
                order._metadata = {"original_ticker": ticker}

                order_id = self.broker.place_order(order)

                if order_id:
                    # Track this sell order (target will be updated on re-entry)
                    self.active_sell_orders[symbol] = {
                        "order_id": order_id,
                        "target_price": ema9_target,  # Updated on re-entry (EMA9)
                        "qty": quantity,
                        "ticker": ticker,
                        "entry_date": datetime.now().strftime("%Y-%m-%d"),
                    }

                    self.logger.info(
                        f"? Placed SELL order: {symbol} x{quantity} @ Rs {ema9_target:.2f} "
                        f"(EMA9 target) | Order ID: {order_id}",
                        action="_place_sell_orders",
                    )
                else:
                    self.logger.warning(
                        f"Failed to place sell order for {symbol}", action="_place_sell_orders"
                    )

            except Exception as e:
                self.logger.error(
                    f"Error placing sell order for {holding.symbol}: {e}",
                    exc_info=True,
                    action="_place_sell_orders",
                )

        self.logger.info(
            f"Sell orders placed: {len(self.active_sell_orders)} active orders",
            action="_place_sell_orders",
        )

        # Initialize RSI10 cache for all active sell orders (previous day's RSI10)
        self._initialize_rsi10_cache_paper()

        # Save active sell orders to JSON for UI display
        self._save_sell_orders_to_file()

    def _monitor_sell_orders(self):
        """
        Monitor sell orders for exit conditions (matches backtest strategy).

        Exit conditions (from 10-year backtest):
        1. High >= Target (EMA9) - 90% of exits, 76% profitable
        2. RSI > 50 - 10% of exits, 37% profitable (falling knives)

        NOTE: Target price is recalculated as EMA9 when re-entry happens (matches backtest).
        """
        # First, check and execute any pending limit orders
        try:
            execution_summary = self.broker.check_and_execute_pending_orders()
            if execution_summary["executed"] > 0:
                self.logger.info(
                    f"Executed {execution_summary['executed']} pending sell orders",
                    action="_monitor_sell_orders",
                )
        except Exception as e:
            self.logger.error(
                f"Error checking pending orders: {e}",
                action="_monitor_sell_orders",
            )

        if not self.active_sell_orders:
            return

        import pandas_ta as ta

        from core.data_fetcher import fetch_ohlcv_yf

        symbols_to_remove = []

        for symbol, order_info in list(self.active_sell_orders.items()):
            try:
                ticker = order_info["ticker"]
                target_price = order_info["target_price"]  # Updated on re-entry (EMA9)

                # Fetch recent data for exit condition checks (60 days for stable indicators)
                data = fetch_ohlcv_yf(ticker, days=60, interval="1d")

                if data is None or data.empty:
                    continue

                # Get today's data
                latest = data.iloc[-1]
                high = latest["high"]
                close = latest["close"]

                # Calculate RSI for exit condition 2
                data["rsi10"] = ta.rsi(data["close"], length=10)
                rsi = data.iloc[-1]["rsi10"]

                # Exit Condition 1: High >= Frozen Target (primary exit)
                # When high touches target, force execution at target price
                if high >= target_price:
                    self.logger.info(
                        f"? EXIT CONDITION MET: {symbol} - "
                        f"High {high:.2f} >= Target {target_price:.2f}",
                        action="_monitor_sell_orders",
                    )

                    entry_price = order_info.get("entry_price", target_price)
                    pnl_pct = (
                        (target_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
                    )

                    self.logger.info(
                        f"? Target reached: {symbol} @ Rs {target_price:.2f} "
                        f"(Est. P&L: {pnl_pct:+.2f}%)",
                        action="_monitor_sell_orders",
                    )

                    # Force execute at target price since high touched it
                    # Even if current price dropped below, we assume fill at target
                    from modules.kotak_neo_auto_trader.domain import (
                        Order,
                        OrderType,
                        TransactionType,
                        Money,
                    )

                    target_order = Order(
                        symbol=symbol,
                        quantity=order_info["qty"],
                        order_type=OrderType.MARKET,  # Use MARKET to force immediate execution
                        transaction_type=TransactionType.SELL,
                        price=Money(target_price),  # Will execute at this price
                    )
                    target_order._metadata = {
                        "original_ticker": ticker,
                        "exit_reason": "Target Hit",
                    }

                    try:
                        # Cancel existing limit order if any
                        pending_orders = self.broker.get_all_orders()
                        for pending in pending_orders:
                            if (
                                pending.symbol.replace(".NS", "").replace("-EQ", "") == symbol
                                and pending.transaction_type.value == "SELL"
                                and pending.status.value in ["PENDING", "OPEN"]
                            ):
                                try:
                                    self.broker.cancel_order(pending.order_id)
                                except Exception:
                                    pass  # Ignore if already executed/cancelled
                                break

                        # Place market order - will execute immediately at target price
                        self.broker.place_order(target_order)

                        # Verify position is actually closed before removing from tracking
                        holding = self.broker.get_holding(symbol)
                        if not holding or holding.quantity == 0:
                            symbols_to_remove.append(symbol)
                            self.logger.info(
                                f"Position closed for {symbol} @ Rs {target_price:.2f}",
                                action="_monitor_sell_orders",
                            )
                        else:
                            self.logger.warning(
                                f"Target exit placed for {symbol} but position still open - will retry",
                                action="_monitor_sell_orders",
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to execute target exit for {symbol}: {e}",
                            action="_monitor_sell_orders",
                        )

                    continue

                # Exit Condition 2: RSI > 50 (secondary exit for failing stocks)
                # Use cache-based RSI (previous day first, then real-time)
                # Skip if already converted
                if symbol in self.converted_to_market:
                    continue

                rsi10 = self._get_current_rsi10_paper(symbol, ticker)
                RSI_EXIT_THRESHOLD = 50  # From backtest: 10% of exits, 37% win rate

                if rsi10 is not None and rsi10 > RSI_EXIT_THRESHOLD:
                    self.logger.info(
                        f"? EXIT TRIGGERED: {symbol} - RSI {rsi10:.1f} > 50 (falling knife exit)",
                        action="_monitor_sell_orders",
                    )

                    # Execute market sell at current price
                    from modules.kotak_neo_auto_trader.domain import (
                        Order,
                        OrderType,
                        TransactionType,
                    )

                    market_order = Order(
                        symbol=symbol,
                        quantity=order_info["qty"],
                        order_type=OrderType.MARKET,
                        transaction_type=TransactionType.SELL,
                    )
                    market_order._metadata = {
                        "original_ticker": ticker,
                        "exit_reason": "RSI > 50",
                    }

                    # Cancel the limit order and place market order
                    try:
                        # In paper trading, just remove the order and execute at market
                        self.broker.place_order(market_order)
                        symbols_to_remove.append(symbol)
                        self.converted_to_market.add(symbol)  # Track conversion

                        self.logger.info(
                            f"? RSI exit: {symbol} @ Rs {close:.2f} (RSI: {rsi10:.1f})",
                            action="_monitor_sell_orders",
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to execute RSI exit for {symbol}: {e}",
                            action="_monitor_sell_orders",
                        )

            except Exception as e:
                self.logger.error(
                    f"Error monitoring {symbol}: {e}", exc_info=True, action="_monitor_sell_orders"
                )

        # Remove executed orders from tracking
        for symbol in symbols_to_remove:
            if symbol in self.active_sell_orders:
                del self.active_sell_orders[symbol]

        if symbols_to_remove:
            self.logger.info(
                f"Removed {len(symbols_to_remove)} executed orders. "
                f"Active orders: {len(self.active_sell_orders)}",
                action="_monitor_sell_orders",
            )
            # Update saved file after removing executed orders
            self._save_sell_orders_to_file()

    def _initialize_rsi10_cache_paper(self) -> None:
        """
        Initialize RSI10 cache with previous day's RSI10 for all active sell orders.
        Called at market open (when sell orders are placed).

        Paper trading version - uses fetch_ohlcv_yf directly.
        """
        if not self.active_sell_orders:
            return

        self.logger.info(
            f"Initializing RSI10 cache for {len(self.active_sell_orders)} positions...",
            action="_initialize_rsi10_cache_paper",
        )

        for symbol, order_info in self.active_sell_orders.items():
            ticker = order_info.get("ticker")

            if not ticker:
                continue

            try:
                # Get previous day's RSI10
                previous_rsi = self._get_previous_day_rsi10_paper(ticker)
                if previous_rsi is not None:
                    self.rsi10_cache[symbol] = previous_rsi
                    self.logger.debug(
                        f"Cached previous day RSI10 for {symbol}: {previous_rsi:.2f}",
                        action="_initialize_rsi10_cache_paper",
                    )
                else:
                    self.logger.warning(
                        f"Could not get previous day RSI10 for {symbol}, will use real-time when available",
                        action="_initialize_rsi10_cache_paper",
                    )
            except Exception as e:
                self.logger.warning(
                    f"Error caching RSI10 for {symbol}: {e}",
                    action="_initialize_rsi10_cache_paper",
                )

        self.logger.info(
            f"RSI10 cache initialized for {len(self.rsi10_cache)} positions",
            action="_initialize_rsi10_cache_paper",
        )

    def _get_previous_day_rsi10_paper(self, ticker: str) -> float | None:
        """
        Get previous day's RSI10 value (paper trading).

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Previous day's RSI10 value, or None if unavailable
        """
        try:
            import pandas_ta as ta

            from core.data_fetcher import fetch_ohlcv_yf

            # Get price data (exclude current day to get previous day's data)
            data = fetch_ohlcv_yf(ticker, days=200, interval="1d", add_current_day=False)

            if data is None or data.empty or len(data) < 2:
                return None

            # Calculate RSI
            data["rsi10"] = ta.rsi(data["close"], length=10)

            if data is None or data.empty or len(data) < 2:
                return None

            # Get second-to-last row (previous day)
            previous_day = data.iloc[-2]
            previous_rsi = previous_day.get("rsi10", None)

            if previous_rsi is not None:
                # Check if NaN
                if not pd.isna(previous_rsi):
                    return float(previous_rsi)

            return None
        except Exception as e:
            self.logger.debug(
                f"Error getting previous day RSI10 for {ticker}: {e}",
                action="_get_previous_day_rsi10_paper",
            )
            return None

    def _get_current_rsi10_paper(self, symbol: str, ticker: str) -> float | None:
        """
        Get current RSI10 value with real-time calculation and fallback to cache (paper trading).

        Priority:
        1. Try to calculate real-time RSI10 (update cache if available)
        2. Fallback to cached previous day's RSI10

        Args:
            symbol: Stock symbol (for cache lookup)
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Current RSI10 value, or None if unavailable
        """
        try:
            import pandas_ta as ta

            from core.data_fetcher import fetch_ohlcv_yf

            # Try to get real-time RSI10 (include current day)
            data = fetch_ohlcv_yf(ticker, days=200, interval="1d", add_current_day=True)

            if data is not None and not data.empty:
                # Calculate RSI
                data["rsi10"] = ta.rsi(data["close"], length=10)

                if data is not None and not data.empty:
                    # Get latest row (current day)
                    latest = data.iloc[-1]
                    current_rsi = latest.get("rsi10", None)

                    if current_rsi is not None and not pd.isna(current_rsi):
                        # Update cache with real-time value
                        self.rsi10_cache[symbol] = float(current_rsi)
                        self.logger.debug(
                            f"Updated RSI10 cache for {symbol} with real-time value: {current_rsi:.2f}",
                            action="_get_current_rsi10_paper",
                        )
                        return float(current_rsi)
        except Exception as e:
            self.logger.debug(
                f"Error calculating real-time RSI10 for {symbol}: {e}",
                action="_get_current_rsi10_paper",
            )

        # Fallback to cached previous day's RSI10
        cached_rsi = self.rsi10_cache.get(symbol)
        if cached_rsi is not None:
            self.logger.debug(
                f"Using cached RSI10 for {symbol}: {cached_rsi:.2f}",
                action="_get_current_rsi10_paper",
            )
            return cached_rsi

        self.logger.debug(
            f"RSI10 unavailable for {symbol} (no cache, real-time failed)",
            action="_get_current_rsi10_paper",
        )
        return None

    def _load_sell_orders_from_file(self):
        """Load active sell orders from JSON file on service startup"""
        try:
            import json

            if not self._sell_orders_file.exists():
                self.logger.debug(
                    f"No existing sell orders file found at {self._sell_orders_file}",
                    action="_load_sell_orders_from_file",
                )
                return

            with open(self._sell_orders_file) as f:
                loaded_orders = json.load(f)

            # Validate and filter out orders for symbols that no longer have holdings
            holdings = self.broker.get_holdings() if self.broker else []
            # Extract base symbols from holdings for comparison (holdings have full symbols like RELIANCE-EQ)
            from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

            holding_base_symbols = {extract_base_symbol(h.symbol).upper() for h in holdings}

            # Also check pending orders from broker to avoid duplicates
            pending_orders = self.broker.get_pending_orders() if self.broker else []
            # Extract base symbols from pending orders for comparison
            pending_sell_base_symbols = {
                extract_base_symbol(o.symbol).upper()
                for o in pending_orders
                if o.is_sell_order() and o.is_active()
            }

            valid_orders = {}
            for symbol, order_info in loaded_orders.items():
                # Normalize symbol from file (might be base or full symbol)
                symbol_base = extract_base_symbol(symbol).upper()
                # Keep order if:
                # 1. Symbol still has holdings, OR
                # 2. Symbol has a pending sell order in broker
                if symbol_base in holding_base_symbols or symbol_base in pending_sell_base_symbols:
                    valid_orders[symbol] = order_info
                else:
                    self.logger.debug(
                        f"Removed stale sell order for {symbol} (no holdings or pending order)",
                        action="_load_sell_orders_from_file",
                    )

            self.active_sell_orders = valid_orders

            if valid_orders:
                self.logger.info(
                    f"Loaded {len(valid_orders)} active sell orders from file",
                    action="_load_sell_orders_from_file",
                )
            else:
                self.logger.debug(
                    "No valid sell orders found in file",
                    action="_load_sell_orders_from_file",
                )

        except Exception as e:
            self.logger.warning(
                f"Failed to load sell orders from file: {e}",
                action="_load_sell_orders_from_file",
            )
            # On error, start with empty dict (safe default)
            self.active_sell_orders = {}

    def _sync_sell_order_quantities_with_holdings(
        self, symbol_targets: dict[str, float] | None = None
    ) -> int:
        """
        Sync sell order quantities with current holdings (after re-entry).

        This ensures that when re-entry happens and holdings increase,
        the sell order quantity and target price are updated to match total holdings
        and recalculated EMA9 target (matches backtest behavior).

        Args:
            symbol_targets: Optional dict mapping symbol to new EMA9 target price.
                          If provided, uses these targets; otherwise calculates them.

        Returns:
            Number of sell orders updated
        """
        if not self.broker:
            return 0

        holdings = self.broker.get_holdings()
        # Holdings have full symbols (RELIANCE-EQ), but active_sell_orders might have base symbols (RELIANCE)
        # Normalize for comparison
        from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

        holdings_map = {extract_base_symbol(h.symbol).upper(): h.quantity for h in holdings}

        updated_count = 0
        for symbol, order_info in list(self.active_sell_orders.items()):
            # Normalize symbol from active_sell_orders (might be base or full)
            symbol_base = extract_base_symbol(symbol).upper()
            if symbol_base in holdings_map:
                current_qty = order_info.get("qty", 0)
                holdings_qty = holdings_map[symbol_base]

                # If holdings quantity is greater than sell order quantity, update it
                if holdings_qty > current_qty:
                    # Get new target from provided dict, or calculate it
                    new_target = None
                    if symbol_targets and symbol in symbol_targets:
                        new_target = symbol_targets[symbol]
                    elif symbol_targets is None:
                        # Calculate EMA9 target (matches backtest behavior)
                        ticker = order_info.get("ticker", f"{symbol}.NS")
                        new_target = self._calculate_ema9(ticker)

                    if self._update_sell_order_quantity(symbol, holdings_qty, new_target):
                        updated_count += 1

        return updated_count

    def _update_sell_order_quantity(
        self, symbol: str, new_quantity: int, new_target: float | None = None
    ) -> bool:
        """
        Update sell order quantity and target price (after re-entry).

        Strategy: Cancel old order and place new one with updated quantity and target.
        Target price is recalculated as EMA9 (matches backtest behavior).

        Args:
            symbol: Trading symbol
            new_quantity: New quantity to match holdings
            new_target: New target price (EMA9). If None, will be calculated.

        Returns:
            True if successfully updated, False otherwise
        """
        if symbol not in self.active_sell_orders:
            return False

        order_info = self.active_sell_orders[symbol]
        old_qty = order_info.get("qty", 0)
        old_target = order_info.get("target_price")
        order_id = order_info.get("order_id")
        ticker = order_info.get("ticker", f"{symbol}.NS")

        if not old_target or new_quantity <= old_qty:
            return False

        try:
            from datetime import datetime

            from modules.kotak_neo_auto_trader.domain import (
                Money,
                Order,
                OrderType,
                TransactionType,
            )

            # Calculate new target if not provided (recalculate EMA9)
            if new_target is None:
                new_target = self._calculate_ema9(ticker)
                if new_target is None or new_target <= 0:
                    self.logger.warning(
                        f"Failed to calculate new EMA9 target for {symbol}, keeping old target",
                        action="_update_sell_order_quantity",
                    )
                    new_target = old_target  # Fallback to old target

            # Cancel old sell order if it exists
            if order_id and order_id != "unknown":
                try:
                    self.broker.cancel_order(order_id)
                    self.logger.debug(
                        f"Cancelled old sell order {order_id} for {symbol}",
                        action="_update_sell_order_quantity",
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to cancel old order {order_id}: {e}",
                        action="_update_sell_order_quantity",
                    )
                    # Continue anyway - may have already been executed

            # Place new sell order with updated quantity and recalculated target
            new_order = Order(
                symbol=symbol,
                quantity=new_quantity,
                order_type=OrderType.LIMIT,
                transaction_type=TransactionType.SELL,
                price=Money(new_target),  # Updated target (EMA9 recalculated)
            )
            new_order._metadata = {"original_ticker": ticker}

            new_order_id = self.broker.place_order(new_order)

            if new_order_id:
                # Update tracking with new order ID, quantity, and target
                self.active_sell_orders[symbol] = {
                    "order_id": new_order_id,
                    "target_price": new_target,  # Updated target (EMA9)
                    "qty": new_quantity,  # Updated quantity
                    "ticker": ticker,
                    "entry_date": order_info.get("entry_date", datetime.now().strftime("%Y-%m-%d")),
                }

                target_change = f"{old_target:.2f} -> {new_target:.2f}"
                self.logger.info(
                    f"? Updated sell order for {symbol}: {old_qty} -> {new_quantity} shares "
                    f"@ Rs {new_target:.2f} (target: {target_change}) | New Order ID: {new_order_id}",
                    action="_update_sell_order_quantity",
                )

                # Save updated state
                self._save_sell_orders_to_file()
                return True
            else:
                self.logger.warning(
                    f"Failed to place updated sell order for {symbol}",
                    action="_update_sell_order_quantity",
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Error updating sell order quantity for {symbol}: {e}",
                exc_info=True,
                action="_update_sell_order_quantity",
            )
            return False

    def _save_sell_orders_to_file(self):
        """Save active sell orders to JSON file for UI display"""
        try:
            import json

            self._sell_orders_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._sell_orders_file, "w") as f:
                json.dump(self.active_sell_orders, f, indent=2)

            self.logger.debug(
                f"Saved {len(self.active_sell_orders)} sell orders to {self._sell_orders_file}",
                action="_save_sell_orders_to_file",
            )
        except Exception as e:
            self.logger.warning(f"Failed to save sell orders to file: {e}")

    def _calculate_ema9(self, ticker: str) -> float | None:
        """
        Calculate EMA9 for a ticker.

        Args:
            ticker: Stock ticker (e.g., "RELIANCE.NS")

        Returns:
            EMA9 value or None if calculation fails
        """
        try:
            import pandas_ta as ta

            from core.data_fetcher import fetch_ohlcv_yf

            # Fetch data (need at least 50 days for stable EMA9)
            data = fetch_ohlcv_yf(ticker, days=60, interval="1d")

            if data is None or data.empty:
                return None

            # Calculate EMA9
            data["ema9"] = ta.ema(data["close"], length=9)
            ema9 = data.iloc[-1]["ema9"]

            return float(ema9) if not pd.isna(ema9) else None

        except Exception as e:
            self.logger.debug(f"Failed to calculate EMA9 for {ticker}: {e}")
            return None


class PaperTradingEngineAdapter:
    """
    Adapter that provides AutoTradeEngine-compatible interface using paper trading broker.

    This allows existing code that uses AutoTradeEngine to work with paper trading.
    """

    def __init__(  # noqa: PLR0913
        self, broker, user_id, db_session, strategy_config, logger, storage_path=None
    ):
        """
        Initialize paper trading engine adapter.

        Args:
            broker: PaperTradingBrokerAdapter instance
            user_id: User ID
            db_session: Database session
            strategy_config: Strategy configuration
            logger: Logger instance
            storage_path: Storage path for metadata files
        """
        self.broker = broker
        self.user_id = user_id
        self.db = db_session
        self.strategy_config = strategy_config
        self.logger = logger
        self.storage_path = storage_path or broker.store.storage_path

    def load_latest_recommendations(self):
        """
        Load latest recommendations from database (Signals table).

        Returns:
            List of Recommendation objects
        """
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from src.infrastructure.persistence.signals_repository import (  # noqa: PLC0415
            SignalsRepository,
        )

        try:
            # Query Signals table for buy/strong_buy recommendations
            signals_repo = SignalsRepository(self.db, user_id=self.user_id)

            # Mark time-expired signals before loading to ensure database consistency
            # This prevents trading on expired signals
            signals_repo.mark_time_expired_signals()

            # Get latest signals (today's or most recent)
            from src.infrastructure.db.models import SignalStatus  # noqa: PLC0415
            from src.infrastructure.db.timezone_utils import ist_now

            today = ist_now().date()
            signals = signals_repo.by_date(today, limit=500)

            # If no signals for today, get recent ones
            if not signals:
                signals = signals_repo.recent(limit=500)

            if not signals:
                self.logger.warning("No signals found in database", action="load_recommendations")
                return []

            self.logger.info(
                f"Found {len(signals)} signals in database", action="load_recommendations"
            )

            # Filter signals by effective status (considering per-user status)
            # Only include ACTIVE signals - skip TRADED, REJECTED, and EXPIRED
            active_signals = []
            for signal in signals:
                # Get effective status (user-specific if exists, otherwise base status)
                # IMPORTANT: EXPIRED base status cannot be overridden by user status
                # However, TRADED/REJECTED user status takes precedence over EXPIRED base status
                # (from our recent fix - user actions are preserved even when base expires)
                user_status = signals_repo.get_user_signal_status(signal.id, self.user_id)

                # Determine effective status:
                # 1. If user has TRADED, REJECTED, or FAILED override, use that (completed actions take precedence)
                # 2. If base signal is EXPIRED and no user override, effective_status is EXPIRED
                # 3. Otherwise, use user status if exists, otherwise use base signal status
                if user_status in [SignalStatus.TRADED, SignalStatus.REJECTED, SignalStatus.FAILED]:
                    # User has completed an action (TRADED/REJECTED/FAILED) - this takes precedence
                    effective_status = user_status
                elif signal.status == SignalStatus.EXPIRED:
                    # Base signal is EXPIRED and no user action - cannot be overridden with ACTIVE
                    effective_status = SignalStatus.EXPIRED
                else:
                    # Use user status if exists, otherwise use base signal status
                    effective_status = user_status if user_status is not None else signal.status

                # Only include ACTIVE signals
                if effective_status != SignalStatus.ACTIVE:
                    user_status_str = user_status.value if user_status else "none"
                    self.logger.debug(
                        f"Skipping signal {signal.symbol}: "
                        f"status={effective_status.value} "
                        f"(base={signal.status.value}, user={user_status_str})",
                        action="load_recommendations",
                    )
                    continue

                active_signals.append(signal)

            self.logger.info(
                f"Filtered to {len(active_signals)} ACTIVE signals "
                f"(user {self.user_id}, skipped {len(signals) - len(active_signals)} non-ACTIVE)",
                action="load_recommendations",
            )

            if not active_signals:
                self.logger.warning(
                    "No ACTIVE signals found after filtering", action="load_recommendations"
                )
                return []

            # Convert Signals to Recommendation objects
            # Use a set to track normalized symbols to prevent duplicates
            # (e.g., "XYZ" and "XYZ.NS" should be treated as the same symbol)
            seen_symbols = set()
            recommendations = []
            for signal in active_signals:
                # Determine verdict (prioritize final_verdict, then verdict, then ml_verdict)
                verdict = None
                if signal.final_verdict and signal.final_verdict.lower() in ["buy", "strong_buy"]:
                    verdict = signal.final_verdict.lower()
                elif signal.verdict and signal.verdict.lower() in ["buy", "strong_buy"]:
                    verdict = signal.verdict.lower()
                elif signal.ml_verdict and signal.ml_verdict.lower() in ["buy", "strong_buy"]:
                    verdict = signal.ml_verdict.lower()

                # Only include buy/strong_buy signals
                if not verdict:
                    continue

                # Convert symbol to ticker format (add .NS if not present)
                ticker = signal.symbol.upper()
                if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
                    ticker = f"{ticker}.NS"

                # Normalize ticker for deduplication (remove .NS suffix and uppercase)
                normalized_symbol = ticker.replace(".NS", "").replace(".BO", "").upper()

                # Skip if we've already seen this normalized symbol
                if normalized_symbol in seen_symbols:
                    self.logger.debug(
                        f"Skipping duplicate symbol: {ticker} (normalized: {normalized_symbol})",
                        action="load_recommendations",
                    )
                    continue

                # Get last_close price
                last_close = signal.last_close or 0.0
                if last_close <= 0:
                    self.logger.warning(
                        f"Skipping {ticker}: invalid last_close ({last_close})",
                        action="load_recommendations",
                    )
                    continue

                # Calculate execution_capital if available from
                # liquidity_recommendation or trading_params
                # or use default (will be calculated in place_new_entries if None)
                execution_capital = None
                if signal.liquidity_recommendation and isinstance(
                    signal.liquidity_recommendation, dict
                ):
                    execution_capital = signal.liquidity_recommendation.get("execution_capital")
                elif signal.trading_params and isinstance(signal.trading_params, dict):
                    execution_capital = signal.trading_params.get("execution_capital")

                # Create Recommendation object
                rec = Recommendation(
                    ticker=ticker,
                    verdict=verdict,
                    last_close=last_close,
                    execution_capital=execution_capital,
                )
                recommendations.append(rec)
                seen_symbols.add(normalized_symbol)

            self.logger.info(
                f"Converted {len(recommendations)} buy/strong_buy recommendations from database",
                action="load_recommendations",
            )

            return recommendations

        except Exception as e:
            self.logger.error(
                f"Failed to load recommendations from database: {e}",
                exc_info=e,
                action="load_recommendations",
            )
            return []

    def place_new_entries(self, recommendations):
        """
        Place new buy orders using paper trading broker.

        Args:
            recommendations: List of Recommendation objects

        Returns:
            Summary dict with placement statistics
        """
        from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType

        summary = {
            "attempted": 0,
            "placed": 0,
            "failed_balance": 0,
            "skipped_duplicates": 0,
            "skipped_portfolio_limit": 0,
        }

        if not self.broker:
            self.logger.error("Paper trading broker not initialized", action="place_new_entries")
            return summary

        if not self.broker.is_connected():
            self.logger.warning(
                "Paper trading broker not connected, attempting to connect...",
                action="place_new_entries",
            )
            if not self.broker.connect():
                self.logger.error(
                    "Failed to connect to paper trading broker", action="place_new_entries"
                )
                return summary

        # Get current holdings and pending orders to check for duplicates
        holdings = self.broker.get_holdings()
        pending_orders = self.broker.get_all_orders()

        # Normalize symbols from holdings (extract base symbol from full symbols like RELIANCE-EQ)
        # This matches the normalization in load_latest_recommendations()
        from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

        current_symbols = {extract_base_symbol(h.symbol).upper() for h in holdings}

        # Also check pending/open buy orders to prevent duplicates
        for order in pending_orders:
            if order.is_buy_order() and order.is_active():
                # Normalize symbol (extract base symbol from full symbols)
                normalized_symbol = extract_base_symbol(order.symbol).upper()
                current_symbols.add(normalized_symbol)
                self.logger.debug(
                    f"Found pending buy order for {order.symbol} (Status: {order.status})",
                    action="place_new_entries",
                )

        # Also check database for completed/ongoing buy orders from today to prevent duplicates
        # This catches cases where orders were placed in previous runs but aren't in broker yet
        if self.user_id and self.db:
            from src.infrastructure.db.timezone_utils import ist_now
            from src.infrastructure.persistence.orders_repository import OrdersRepository

            orders_repo = OrdersRepository(self.db)
            today = ist_now().date()

            # Get all buy orders from today (any status except CANCELLED/FAILED)
            # This includes ONGOING and CLOSED orders which indicate a position was opened
            from src.infrastructure.db.models import OrderStatus

            today_orders = orders_repo.list(self.user_id, status=None)
            for order in today_orders:
                if (
                    order.side == "buy"
                    and order.placed_at
                    and order.placed_at.date() == today
                    and order.status
                    not in [OrderStatus.CANCELLED, OrderStatus.FAILED]  # Skip cancelled/failed
                ):
                    # Normalize symbol (extract base symbol from full symbols)
                    from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

                    normalized_symbol = extract_base_symbol(order.symbol).upper()
                    current_symbols.add(normalized_symbol)
                    self.logger.debug(
                        f"Found today's buy order in DB for {order.symbol} "
                        f"(Status: {order.status.value}, Placed: {order.placed_at})",
                        action="place_new_entries",
                    )

        # Check portfolio limit (from strategy config or default 6)
        # CRITICAL FIX: Use current_symbols (includes holdings + pending orders + DB orders)
        # instead of just holdings, to properly respect max_portfolio_size
        max_portfolio_size = 6  # Default
        if self.strategy_config and hasattr(self.strategy_config, "max_portfolio_size"):
            # Ensure we get an actual int, not a Mock object
            portfolio_size_value = self.strategy_config.max_portfolio_size
            if isinstance(portfolio_size_value, int):
                max_portfolio_size = portfolio_size_value
        current_portfolio_count = len(current_symbols)
        if current_portfolio_count >= max_portfolio_size:
            self.logger.warning(
                f"Portfolio limit reached ({current_portfolio_count}/{max_portfolio_size})",
                action="place_new_entries",
            )
            summary["skipped_portfolio_limit"] = len(recommendations)
            return summary

        # OPTIMIZATION: Pre-fetch prices for all recommendation tickers (batch operation)
        # This warms the price provider cache and reduces latency during order execution
        cached_prices: dict[str, float | None] = {}
        if recommendations and hasattr(self.broker, "price_provider"):
            tickers_to_fetch = [rec.ticker for rec in recommendations]
            self.logger.info(
                f"Pre-fetching prices for {len(tickers_to_fetch)} tickers...",
                action="place_new_entries",
            )
            try:
                # Use batch price fetching if available
                if hasattr(self.broker.price_provider, "get_prices"):
                    batch_prices = self.broker.price_provider.get_prices(tickers_to_fetch)
                    if isinstance(batch_prices, dict):
                        cached_prices.update(batch_prices)
                        successful_fetches = sum(1 for v in cached_prices.values() if v is not None)
                        self.logger.info(
                            f"Pre-fetched {successful_fetches}/"
                            f"{len(tickers_to_fetch)} prices (batch)",
                            action="place_new_entries",
                        )
                    else:
                        # Fallback to individual fetches if batch method returns unexpected format
                        for ticker in tickers_to_fetch:
                            try:
                                price = self.broker.price_provider.get_price(ticker)
                                cached_prices[ticker] = price
                            except Exception as e:
                                self.logger.warning(
                                    f"Failed to pre-fetch price for {ticker}: {e}",
                                    action="place_new_entries",
                                )
                                cached_prices[ticker] = None
                else:
                    # Fallback: individual fetches if batch method not available
                    for ticker in tickers_to_fetch:
                        try:
                            price = self.broker.price_provider.get_price(ticker)
                            cached_prices[ticker] = price
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to pre-fetch price for {ticker}: {e}",
                                action="place_new_entries",
                            )
                            cached_prices[ticker] = None
            except Exception as e:
                self.logger.warning(
                    f"Failed to batch pre-fetch prices: {e}, will fetch individually",
                    action="place_new_entries",
                )

        for rec in recommendations:
            summary["attempted"] += 1

            # Normalize ticker for comparison (remove .NS/.BO suffix and uppercase)
            # This matches the normalization in load_latest_recommendations()
            # Normalize ticker to base symbol (extract base from full symbols like RELIANCE-EQ.NS)
            # First remove .NS/.BO suffix, then extract base symbol (handles -EQ, -BE suffixes)
            ticker_without_suffix = rec.ticker.replace(".NS", "").replace(".BO", "").upper()
            normalized_ticker = extract_base_symbol(ticker_without_suffix).upper()

            # Skip if already in portfolio or has pending buy order
            if normalized_ticker in current_symbols:
                self.logger.debug(
                    f"Skipping {rec.ticker} - already in portfolio or has pending order",
                    action="place_new_entries",
                )
                summary["skipped_duplicates"] += 1
                continue

            try:
                # Calculate quantity based on execution capital or use strategy config
                execution_capital = getattr(rec, "execution_capital", None)
                if not execution_capital or execution_capital <= 0:
                    # Use user_capital from strategy config (default: 200000.0)
                    execution_capital = (
                        self.strategy_config.user_capital
                        if self.strategy_config and hasattr(self.strategy_config, "user_capital")
                        else 200000.0
                    )

                price = rec.last_close
                if price <= 0:
                    self.logger.warning(
                        f"Invalid price for {rec.ticker}: {price}", action="place_new_entries"
                    )
                    continue

                # Get max position size from broker config (which is set from
                # strategy_config.user_capital).
                # This ensures we use the user's configured capital per trade
                max_position_size = (
                    self.broker.config.max_position_size if self.broker.config else 50000.0
                )

                # Limit execution_capital to max_position_size
                if execution_capital > max_position_size:
                    self.logger.info(
                        f"Limiting execution_capital for {rec.ticker} from "
                        f"Rs {execution_capital:,.0f} to Rs {max_position_size:,.0f} "
                        f"(max position size from config)",
                        action="place_new_entries",
                    )
                    execution_capital = max_position_size

                from math import floor

                qty = max(1, floor(execution_capital / price))

                # Check balance before placing order (for paper trading, check available cash)
                # This prevents placing orders that will fail on execution
                if self.broker and hasattr(self.broker, "store"):
                    try:
                        account = self.broker.store.get_account()
                        available_cash = account.get("available_cash", 0.0) if account else 0.0
                        order_value = price * qty
                        # Add estimated charges (typically ~0.1% for buy orders)
                        estimated_charges = order_value * 0.001
                        total_required = order_value + estimated_charges

                        if total_required > available_cash:
                            self.logger.warning(
                                f"Insufficient balance for {rec.ticker}: "
                                f"Need Rs {total_required:,.2f}, Available Rs {available_cash:,.2f}",
                                action="place_new_entries",
                            )
                            summary["failed_balance"] += 1
                            continue
                    except Exception as balance_error:
                        # If balance check fails, log warning but continue (don't block order placement)
                        self.logger.warning(
                            f"Failed to check balance for {rec.ticker}: {balance_error}. "
                            "Proceeding with order placement.",
                            action="place_new_entries",
                        )

                # Double-check: ensure order value doesn't exceed max_position_size
                order_value = price * qty
                if order_value > max_position_size:
                    # Adjust quantity to fit within max position size
                    qty = max(1, floor(max_position_size / price))
                    order_value = price * qty
                    self.logger.info(
                        f"Adjusted quantity for {rec.ticker} to {qty} shares "
                        f"(order value: Rs {order_value:,.2f})",
                        action="place_new_entries",
                    )

                if qty <= 0:
                    self.logger.warning(
                        f"Invalid quantity for {rec.ticker}: {qty}", action="place_new_entries"
                    )
                    continue

                # Extract base symbol (remove .NS suffix if present) for order placement
                symbol = rec.ticker.replace(".NS", "").upper()

                # Create MARKET order - variety depends on market hours
                # During market hours: REGULAR orders execute immediately
                # Outside market hours: AMO orders execute at next market open
                from core.volume_analysis import is_market_hours
                from modules.kotak_neo_auto_trader.domain import OrderVariety

                # Determine order variety based on market hours
                if is_market_hours():
                    order_variety = OrderVariety.REGULAR
                    self.logger.debug(f"Market is open - using REGULAR order variety for {symbol}")
                else:
                    order_variety = OrderVariety.AMO
                    self.logger.debug(f"Market is closed - using AMO order variety for {symbol}")

                order = Order(
                    symbol=symbol,
                    quantity=qty,
                    order_type=OrderType.MARKET,  # MARKET order (matches real broker)
                    transaction_type=TransactionType.BUY,
                    # price=None for MARKET orders (not used, executes at market price)
                    variety=order_variety,
                )

                # Store original ticker in order metadata for price fetching
                # The price provider may need the full ticker (with .NS) to fetch prices
                if hasattr(order, "metadata"):
                    order.metadata = {"original_ticker": rec.ticker}
                elif not hasattr(order, "_metadata"):
                    order._metadata = {"original_ticker": rec.ticker}

                # Place order using paper trading broker
                try:
                    order_id = self.broker.place_order(order)
                    self.logger.info(
                        f"? Placed paper buy order: {rec.ticker} x {qty} @ Rs {price:.2f} "
                        f"(Order ID: {order_id}, Capital: Rs {execution_capital:,.0f})",
                        action="place_new_entries",
                    )
                    summary["placed"] += 1
                    # Add to current_symbols to prevent duplicates within same batch
                    # This handles cases where recommendations have both "XYZ" and "XYZ.NS"
                    current_symbols.add(normalized_ticker)

                    # Save to database (similar to place_reentry_orders)
                    if self.user_id and self.db:
                        try:
                            from src.infrastructure.persistence.orders_repository import (
                                OrdersRepository,
                            )

                            orders_repo = OrdersRepository(self.db)
                            # Determine order type string
                            order_type_str = (
                                "market" if order.order_type.value == "MARKET" else "limit"
                            )
                            # Get order metadata if available
                            order_metadata = None
                            if hasattr(order, "metadata") and order.metadata:
                                order_metadata = order.metadata
                            elif hasattr(order, "_metadata") and order._metadata:
                                order_metadata = order._metadata

                            orders_repo.create_amo(
                                user_id=self.user_id,
                                symbol=symbol,
                                side="buy",
                                order_type=order_type_str,
                                quantity=qty,
                                price=price if order.order_type.value == "LIMIT" else None,
                                broker_order_id=order_id,
                                order_metadata=order_metadata,
                                entry_type="fresh",
                                trade_mode=TradeMode.PAPER,  # Phase 0.1: Explicit paper trading mode
                            )
                            # Note: create_amo already commits, but we keep commit here for safety
                            if not self.db.in_transaction():
                                self.db.commit()
                            self.logger.debug(
                                f"Saved order {order_id} to database for {symbol}",
                                action="place_new_entries",
                            )
                        except Exception as db_error:
                            # Don't fail order placement if database save fails
                            self.logger.warning(
                                f"Failed to save order to database for {symbol}: {db_error}",
                                action="place_new_entries",
                            )

                    # Mark signal as TRADED
                    try:
                        from src.infrastructure.persistence.signals_repository import (
                            SignalsRepository,
                        )

                        signals_repo = SignalsRepository(self.db, user_id=self.user_id)
                        if signals_repo.mark_as_traded(symbol, user_id=self.user_id):
                            self.logger.info(
                                f"Marked signal for {symbol} as TRADED (user {self.user_id})",
                                action="place_new_entries",
                            )
                    except Exception as mark_error:
                        # Don't fail order placement if marking fails
                        self.logger.warning(
                            f"Failed to mark signal as traded for {symbol}: {mark_error}",
                            action="place_new_entries",
                        )
                except Exception as order_error:
                    self.logger.error(
                        f"? Failed to place order for {rec.ticker}: {order_error}",
                        exc_info=order_error,
                        action="place_new_entries",
                    )
                    # Check if it's a balance issue
                    if (
                        "balance" in str(order_error).lower()
                        or "funds" in str(order_error).lower()
                        or "insufficient" in str(order_error).lower()
                    ):
                        summary["failed_balance"] += 1

            except Exception as e:
                self.logger.error(
                    f"Failed to place order for {rec.ticker}: {e}",
                    exc_info=e,
                    action="place_new_entries",
                )
                if (
                    "balance" in str(e).lower()
                    or "funds" in str(e).lower()
                    or "insufficient" in str(e).lower()
                ):
                    summary["failed_balance"] += 1

        return summary

    def monitor_positions(
        self,
    ):  # Deprecated: Position monitoring removed, re-entry now in buy order service
        """
        Monitor positions for reentry/exit signals (paper trading).

        Implements the same re-entry logic as real trading:
        - RSI-based re-entry at levels 30, 20, 10
        - Daily cap (1 re-entry per symbol per day)
        - Duplicate prevention (no active buy orders)
        - Reset logic (when RSI > 30)

        Returns:
            Summary dict with monitoring statistics
        """
        from datetime import datetime
        from math import floor

        summary = {"checked": 0, "reentries": 0, "skipped": 0}

        if not self.broker or not self.broker.is_connected():
            self.logger.error("Paper trading broker not connected", action="monitor_positions")
            return summary

        # Get current holdings
        holdings = self.broker.get_holdings()
        summary["checked"] = len(holdings)

        if not holdings:
            self.logger.debug("No holdings to monitor", action="monitor_positions")
            return summary

        # Load position metadata (levels_taken, reset_ready, reentry_dates)
        metadata = self._load_position_metadata()

        # Group holdings by symbol for re-entry evaluation
        for holding in holdings:
            symbol = holding.symbol.replace(".NS", "").replace(".BO", "").replace("-EQ", "")
            ticker = f"{symbol}.NS"

            try:
                # Get daily indicators (RSI, price, EMA9)
                indicators = self._get_daily_indicators(ticker)
                if not indicators:
                    self.logger.warning(
                        f"Skip {symbol}: missing indicators", action="monitor_positions"
                    )
                    continue

                rsi = indicators.get("rsi10", 0)
                price = indicators.get("close", 0)

                if price <= 0 or rsi <= 0:
                    continue

                # Initialize metadata for this symbol if not exists
                if symbol not in metadata:
                    metadata[symbol] = {
                        "levels_taken": {"30": False, "20": False, "10": False},
                        "reset_ready": False,
                        "reentry_dates": [],
                    }

                levels = metadata[symbol]["levels_taken"]
                reset_ready = metadata[symbol]["reset_ready"]
                reentry_dates = metadata[symbol].get("reentry_dates", [])

                # Reset handling: if RSI > 30, allow future cycles
                if rsi > 30:
                    metadata[symbol]["reset_ready"] = True
                    self.logger.debug(
                        f"{symbol}: RSI={rsi:.1f} > 30, marked reset_ready",
                        action="monitor_positions",
                    )

                # If reset_ready and RSI drops below 30 again, trigger NEW CYCLE
                if rsi < 30 and reset_ready:
                    # This is a NEW CYCLE - reset all levels
                    metadata[symbol]["levels_taken"] = {
                        "30": False,
                        "20": False,
                        "10": False,
                    }
                    metadata[symbol]["reset_ready"] = False
                    levels = metadata[symbol]["levels_taken"]
                    self.logger.info(
                        f"{symbol}: NEW CYCLE - RSI={rsi:.1f} < 30 after reset",
                        action="monitor_positions",
                    )
                    # Immediately trigger reentry at this RSI<30 level
                    next_level = 30
                else:
                    # Normal progression through levels
                    next_level = None
                    if levels.get("30") and not levels.get("20") and rsi < 20:
                        next_level = 20
                    elif levels.get("20") and not levels.get("10") and rsi < 10:
                        next_level = 10
                    elif not levels.get("30") and rsi < 30:
                        # First level entry
                        next_level = 30

                if next_level is not None:
                    # Daily cap: allow max 1 re-entry per symbol per day
                    today = datetime.now().date().isoformat()
                    today_reentries = sum(1 for d in reentry_dates if d == today)

                    if today_reentries >= 1:
                        self.logger.info(
                            f"Re-entry daily cap reached for {symbol}; skipping today",
                            action="monitor_positions",
                        )
                        summary["skipped"] += 1
                        continue

                    # Calculate execution capital based on liquidity
                    avg_vol = indicators.get("avg_volume", 0)
                    execution_capital = self._calculate_execution_capital(price, avg_vol)

                    qty = max(1, floor(execution_capital / price))

                    # Balance check for re-entry
                    account = self.broker.store.get_account()
                    available_cash = account.get("available_cash", 0) if account else 0
                    affordable = floor(available_cash / price) if price > 0 else 0

                    if affordable < 1:
                        self.logger.warning(
                            f"Re-entry skip {symbol}: insufficient funds (need Rs {price:.2f})",
                            action="monitor_positions",
                        )
                        summary["skipped"] += 1
                        continue

                    if qty > affordable:
                        self.logger.info(
                            f"Re-entry reducing qty from {qty} to {affordable} based on funds",
                            action="monitor_positions",
                        )
                        qty = affordable

                    if qty > 0:
                        # Re-entry duplicate protection: check for active buy orders
                        pending_orders = self.broker.get_all_orders()
                        has_active_buy = any(
                            order.symbol.replace(".NS", "").replace("-EQ", "") == symbol
                            and order.transaction_type.value == "BUY"
                            and order.status.value in ["PENDING", "OPEN"]
                            for order in pending_orders
                        )

                        if has_active_buy:
                            self.logger.info(
                                f"Re-entry skip {symbol}: pending buy order exists",
                                action="monitor_positions",
                            )
                            summary["skipped"] += 1
                            continue

                        # Place market buy order for re-entry (averaging down)
                        from modules.kotak_neo_auto_trader.domain import (
                            Order,
                            OrderType,
                            TransactionType,
                        )

                        reentry_order = Order(
                            symbol=ticker,
                            quantity=qty,
                            order_type=OrderType.MARKET,
                            transaction_type=TransactionType.BUY,
                        )

                        # Tag as re-entry with metadata for tracking
                        reentry_order._metadata = {
                            "original_ticker": ticker,
                            "entry_type": "REENTRY",
                            "rsi_level": next_level,
                            "rsi_value": round(rsi, 2),
                        }

                        order_id = self.broker.place_order(reentry_order)

                        if order_id:
                            self.logger.info(
                                f"Re-entry {symbol}: qty={qty} at ~Rs{price:.2f} "
                                f"(RSI={rsi:.1f}, Level={next_level})",
                                action="monitor_positions",
                            )

                            # Update metadata
                            metadata[symbol]["levels_taken"][str(next_level)] = True
                            metadata[symbol]["reentry_dates"].append(today)
                            summary["reentries"] += 1
                        else:
                            self.logger.warning(
                                f"Re-entry order failed for {symbol}", action="monitor_positions"
                            )
                            summary["skipped"] += 1

            except Exception as e:
                self.logger.error(
                    f"Error monitoring {symbol}: {e}",
                    exc_info=True,
                    action="monitor_positions",
                )

        # Save updated metadata
        self._save_position_metadata(metadata)

        self.logger.info(
            f"Position monitoring: checked={summary['checked']}, "
            f"reentries={summary['reentries']}, skipped={summary['skipped']}",
            action="monitor_positions",
        )

        return summary

    def _load_position_metadata(self) -> dict:
        """Load position metadata (levels_taken, reset_ready, reentry_dates)"""
        import json

        metadata_file = Path(self.storage_path) / "position_metadata.json"

        try:
            if metadata_file.exists():
                with open(metadata_file) as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load position metadata: {e}")

        return {}

    def _save_position_metadata(self, metadata: dict):
        """Save position metadata to file"""
        import json

        metadata_file = Path(self.storage_path) / "position_metadata.json"

        try:
            metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save position metadata: {e}")

    def _get_daily_indicators(self, ticker: str) -> dict | None:
        """
        Get daily indicators (RSI, EMA9, price, volume) for a ticker.

        Args:
            ticker: Stock ticker (e.g., "INFY.NS")

        Returns:
            Dict with indicators or None if failed
        """
        try:
            import pandas_ta as ta

            from core.data_fetcher import fetch_ohlcv_yf

            # Fetch 60 days of data for stable indicators
            data = fetch_ohlcv_yf(ticker, days=60, interval="1d")

            if data is None or len(data) < 30:
                return None

            # Calculate indicators
            data["rsi10"] = ta.rsi(data["close"], length=10)
            data["ema9"] = ta.ema(data["close"], length=9)

            # Get latest values
            latest = data.iloc[-1]

            return {
                "close": float(latest["close"]),
                "rsi10": float(latest["rsi10"]),
                "ema9": float(latest["ema9"]),
                "avg_volume": float(data["volume"].mean()),
            }
        except Exception as e:
            self.logger.warning(f"Failed to get indicators for {ticker}: {e}")
            return None

    def place_reentry_orders(self) -> dict[str, int]:
        """
        Check re-entry conditions and place AMO orders for re-entries (paper trading).

        Called at 4:05 PM (with buy orders), same as real trading.

        Returns:
            Summary dict with placement statistics
        """
        from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType

        summary = {
            "attempted": 0,
            "placed": 0,
            "failed_balance": 0,
            "skipped_duplicates": 0,
            "skipped_invalid_rsi": 0,
            "skipped_missing_data": 0,
            "skipped_invalid_qty": 0,
            "skipped_no_position": 0,
        }

        if not self.broker:
            self.logger.error("Paper trading broker not initialized", action="place_reentry_orders")
            return summary

        if not self.broker.is_connected():
            self.logger.warning("Paper trading broker not connected", action="place_reentry_orders")
            return summary

        # Get open positions from database
        try:
            from src.infrastructure.persistence.positions_repository import PositionsRepository

            positions_repo = PositionsRepository(self.db)
            open_positions = positions_repo.list(self.user_id)
            open_positions = [pos for pos in open_positions if pos.closed_at is None]

            if not open_positions:
                self.logger.info(
                    "No open positions for re-entry check", action="place_reentry_orders"
                )
                return summary

            self.logger.info(
                f"Checking re-entry conditions for {len(open_positions)} open positions...",
                action="place_reentry_orders",
            )

            # Get current holdings and pending orders for duplicate checks
            holdings = self.broker.get_holdings()
            pending_orders = self.broker.get_all_orders()
            current_symbols = {
                h.symbol.replace(".NS", "").replace(".BO", "").upper() for h in holdings
            }
            for order in pending_orders:
                if order.is_buy_order() and order.is_active():
                    normalized_symbol = order.symbol.replace(".NS", "").replace(".BO", "").upper()
                    current_symbols.add(normalized_symbol)

            for position in open_positions:
                symbol = position.symbol
                entry_rsi = position.entry_rsi

                # Default entry RSI to 29.5 if not available (assume entry at RSI < 30)
                if entry_rsi is None:
                    entry_rsi = 29.5
                    self.logger.debug(
                        f"Position {symbol} missing entry_rsi, defaulting to 29.5",
                        action="place_reentry_orders",
                    )

                summary["attempted"] += 1

                try:
                    # Construct ticker from symbol
                    ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol

                    # Get current indicators
                    ind = self._get_daily_indicators(ticker)
                    if not ind:
                        self.logger.warning(
                            f"Skipping {symbol}: missing indicators for re-entry evaluation",
                            action="place_reentry_orders",
                        )
                        summary["skipped_missing_data"] += 1
                        continue

                    current_rsi = ind.get("rsi10")
                    current_price = ind.get("close")
                    avg_volume = ind.get("avg_volume", 0)

                    if current_rsi is None or current_price is None:
                        self.logger.warning(
                            f"Skipping {symbol}: invalid indicators (RSI or price missing)",
                            action="place_reentry_orders",
                        )
                        summary["skipped_missing_data"] += 1
                        continue

                    # Determine next re-entry level based on entry RSI
                    # Enhanced Hybrid Approach: Returns tuple (next_level, metadata_updates)
                    next_level, metadata_updates = self._determine_reentry_level(
                        entry_rsi, current_rsi, position
                    )

                    # Update position metadata if there are updates
                    try:
                        if metadata_updates and any(
                            v is not None for v in metadata_updates.values()
                        ):
                            # Check if a reset happened (current_cycle changed)
                            reset_happened = metadata_updates.get("current_cycle") is not None
                            current_cycle = (
                                metadata_updates.get("current_cycle")
                                if reset_happened
                                else self._get_position_cycle_metadata(position).get(
                                    "current_cycle", 0
                                )
                            )

                            # Update position's reentries structure with new metadata
                            # Ensure position has reentries attribute (may be None for new positions)
                            if not hasattr(position, "reentries"):
                                position.reentries = (
                                    None  # Will be handled by _set_position_cycle_metadata
                                )

                            updated_reentries = self._set_position_cycle_metadata(
                                position,
                                current_cycle=metadata_updates.get("current_cycle"),
                                last_rsi_above_30=metadata_updates.get("last_rsi_above_30"),
                                last_rsi_value=metadata_updates.get("last_rsi_value"),
                            )

                            # Save updated metadata to database
                            from src.infrastructure.persistence.positions_repository import (
                                PositionsRepository,
                            )

                            positions_repo = PositionsRepository(self.db)
                            positions_repo.upsert(
                                user_id=self.user_id,
                                symbol=symbol,
                                reentries=updated_reentries,
                                auto_commit=False,  # Commit later with order
                            )

                            # Refresh position object for consistency
                            position = positions_repo.get_by_symbol(self.user_id, symbol)
                            if not position:
                                self.logger.warning(
                                    f"Position {symbol} not found after metadata update",
                                    action="place_reentry_orders",
                                )
                                summary["skipped_missing_data"] += 1
                                continue
                        else:
                            # No metadata updates, get current cycle from position
                            cycle_meta = self._get_position_cycle_metadata(position)
                            current_cycle = cycle_meta.get("current_cycle", 0)
                    except Exception as meta_error:
                        self.logger.warning(
                            f"Error updating position metadata for {symbol}: {meta_error}. "
                            f"Continuing with default cycle=0.",
                            action="place_reentry_orders",
                        )
                        current_cycle = 0  # Default to cycle 0 if metadata update fails

                    if next_level is None:
                        self.logger.debug(
                            f"No re-entry opportunity for {symbol} "
                            f"(entry_rsi={entry_rsi:.2f}, current_rsi={current_rsi:.2f})",
                            action="place_reentry_orders",
                        )
                        summary["skipped_invalid_rsi"] += 1
                        continue

                    # Enhanced Hybrid Approach: Check if re-entry at this level already exists
                    # Detect if a reset happened (current_cycle changed)
                    reset_happened = metadata_updates.get("current_cycle") is not None
                    # Normalize symbol for has_reentry_at_level (remove .NS/.BO suffix)
                    normalized_symbol = symbol.replace(".NS", "").replace(".BO", "").upper()
                    if self.has_reentry_at_level(
                        normalized_symbol, next_level, allow_reset=reset_happened
                    ):
                        self.logger.info(
                            f"Skipping {symbol}: re-entry at level {next_level} already exists "
                            f"in current cycle",
                            action="place_reentry_orders",
                        )
                        summary["skipped_duplicates"] += 1
                        continue

                    self.logger.info(
                        f"Re-entry opportunity for {symbol}: entry_rsi={entry_rsi:.2f}, "
                        f"current_rsi={current_rsi:.2f}, next_level={next_level}, "
                        f"cycle={current_cycle}",
                        action="place_reentry_orders",
                    )

                    # Check for duplicates (holdings or active buy orders)
                    # Normalize symbol for comparison (remove .NS/.BO suffix)
                    normalized_symbol = symbol.replace(".NS", "").replace(".BO", "").upper()
                    if normalized_symbol in current_symbols:
                        self.logger.info(
                            f"Skipping {symbol}: already in holdings or pending orders",
                            action="place_reentry_orders",
                        )
                        summary["skipped_duplicates"] += 1
                        continue

                    # Calculate execution capital and quantity
                    execution_capital = self._calculate_execution_capital(current_price, avg_volume)
                    qty = int(execution_capital / current_price)

                    if qty <= 0:
                        self.logger.warning(
                            f"Skipping {symbol}: invalid quantity ({qty})",
                            action="place_reentry_orders",
                        )
                        summary["skipped_invalid_qty"] += 1
                        continue

                    # Check balance and adjust quantity if needed
                    portfolio = self.broker.get_portfolio()
                    if portfolio:
                        available_cash = portfolio.get("availableCash", 0) or portfolio.get(
                            "cash", 0
                        )
                        affordable_qty = (
                            int(available_cash / current_price) if current_price > 0 else 0
                        )
                        if affordable_qty < qty:
                            self.logger.warning(
                                f"Insufficient balance for {symbol}: "
                                f"requested={qty}, affordable={affordable_qty}",
                                action="place_reentry_orders",
                            )
                            qty = affordable_qty
                            if qty <= 0:
                                # Save as failed order for retry (similar to real trading)
                                summary["failed_balance"] += 1
                                summary["skipped_invalid_qty"] += 1
                                continue
                    # If portfolio is None, proceed without balance check (for testing)

                    # Place re-entry order (AMO-like, similar to fresh entries)
                    from modules.kotak_neo_auto_trader.domain import Money

                    reentry_order = Order(
                        symbol=ticker,
                        quantity=qty,
                        order_type=OrderType.LIMIT,
                        transaction_type=TransactionType.BUY,
                        price=Money(current_price),  # AMO order at current price
                    )

                    # Tag as re-entry with metadata for tracking
                    # Enhanced Hybrid Approach: Include cycle number for tracking
                    reentry_order._metadata = {
                        "original_ticker": ticker,
                        "entry_type": "reentry",
                        "rsi_level": next_level,
                        "rsi_value": round(current_rsi, 2),
                        "entry_rsi": entry_rsi,
                        "reentry_level": next_level,
                        "cycle": current_cycle,  # Store cycle number for tracking
                        "rsi10": current_rsi,
                        "ema9": ind.get("ema9"),
                        "ema200": ind.get("ema200"),
                        "capital": execution_capital,
                    }

                    order_id = self.broker.place_order(reentry_order)

                    if order_id:
                        summary["placed"] += 1
                        self.logger.info(
                            f"Re-entry order placed: {symbol} (order_id: {order_id}, "
                            f"qty: {qty}, level: {next_level})",
                            action="place_reentry_orders",
                        )

                        # Save to database (similar to fresh entries)
                        if self.user_id and self.db:
                            from src.infrastructure.persistence.orders_repository import (
                                OrdersRepository,
                            )

                            orders_repo = OrdersRepository(self.db)
                            orders_repo.create_amo(
                                user_id=self.user_id,
                                symbol=normalized_symbol,
                                side="buy",
                                order_type="limit",
                                quantity=qty,
                                price=current_price,
                                broker_order_id=order_id,
                                order_metadata=reentry_order._metadata,
                                entry_type="reentry",
                                trade_mode=TradeMode.PAPER,  # Phase 0.1: Explicit paper trading mode
                            )
                            # Note: create_amo already commits, but we keep commit here for safety
                            if not self.db.in_transaction():
                                self.db.commit()
                    else:
                        self.logger.warning(
                            f"Failed to place re-entry order for {symbol}",
                            action="place_reentry_orders",
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error checking re-entry for {symbol}: {e}",
                        exc_info=True,
                        action="place_reentry_orders",
                    )
                    continue

            self.logger.info(
                f"Re-entry check complete: attempted={summary['attempted']}, "
                f"placed={summary['placed']}, failed_balance={summary['failed_balance']}, "
                f"skipped={summary['skipped_duplicates'] + summary['skipped_invalid_rsi'] + summary['skipped_missing_data'] + summary['skipped_invalid_qty']}",
                action="place_reentry_orders",
            )

        except Exception as e:
            self.logger.error(
                f"Error in place_reentry_orders: {e}",
                exc_info=True,
                action="place_reentry_orders",
            )

        return summary

    def _get_position_cycle_metadata(self, position: Any) -> dict[str, Any]:
        """
        Get cycle metadata from position's reentries structure.

        Enhanced Hybrid Approach: Extracts cycle tracking metadata from position.

        Args:
            position: Position object from database

        Returns:
            Dict with cycle metadata:
            {
                "current_cycle": int,  # Default: 0
                "last_rsi_above_30": str | None,  # ISO timestamp or None
                "last_rsi_value": float | None,  # Last known RSI value
            }
        """
        metadata = {
            "current_cycle": 0,
            "last_rsi_above_30": None,
            "last_rsi_value": None,
        }

        if not position or not hasattr(position, "reentries"):
            return metadata

        if not position.reentries:
            return metadata

        # Check if reentries is a dict with _cycle_metadata key (new format)
        if isinstance(position.reentries, dict):
            cycle_meta = position.reentries.get("_cycle_metadata")
            if isinstance(cycle_meta, dict):
                metadata["current_cycle"] = cycle_meta.get("current_cycle", 0)
                metadata["last_rsi_above_30"] = cycle_meta.get("last_rsi_above_30")
                metadata["last_rsi_value"] = cycle_meta.get("last_rsi_value")
            return metadata

        # If reentries is a list, metadata might be stored separately
        # For now, we'll extract from the structure
        # In the new format, we'll store metadata in a wrapper dict
        return metadata

    def _set_position_cycle_metadata(
        self,
        position: Any,
        current_cycle: int | None = None,
        last_rsi_above_30: str | None = None,
        last_rsi_value: float | None = None,
    ) -> dict:
        """
        Set cycle metadata in position's reentries structure.

        This creates/updates a wrapper structure:
        {
            "_cycle_metadata": {
                "current_cycle": int,
                "last_rsi_above_30": str | None,
                "last_rsi_value": float | None
            },
            "reentries": [...]
        }

        Args:
            position: Position object from database
            current_cycle: Current cycle number (None to keep existing)
            last_rsi_above_30: ISO timestamp when RSI was last above 30 (None to keep existing)
            last_rsi_value: Last known RSI value (None to keep existing)

        Returns:
            Updated reentries structure (dict with _cycle_metadata and reentries keys)
        """
        # Get existing metadata
        existing_meta = self._get_position_cycle_metadata(position)

        # Get existing reentries array
        existing_reentries = []
        if position.reentries:
            if isinstance(position.reentries, dict):
                # New format: extract reentries array
                existing_reentries = position.reentries.get("reentries", [])
                if not isinstance(existing_reentries, list):
                    existing_reentries = []
            elif isinstance(position.reentries, list):
                # Old format: reentries is directly a list
                existing_reentries = position.reentries

        # Update metadata
        if current_cycle is not None:
            existing_meta["current_cycle"] = current_cycle
        if last_rsi_above_30 is not None:
            existing_meta["last_rsi_above_30"] = last_rsi_above_30
        if last_rsi_value is not None:
            existing_meta["last_rsi_value"] = last_rsi_value

        # Return wrapper structure
        return {"_cycle_metadata": existing_meta, "reentries": existing_reentries}

    def has_reentry_at_level(self, base_symbol: str, level: int, allow_reset: bool = False) -> bool:
        """
        Check if a re-entry at the specified level already exists in the current cycle.

        Enhanced Hybrid Approach: Now checks by cycle number, not just level.
        This allows re-entries at the same level after a reset (new cycle).

        Args:
            base_symbol: Symbol to check
            level: Re-entry level (30, 20, or 10)
            allow_reset: If True, allow re-entry at this level even if initial entry was at this level

        Returns:
            True if re-entry at this level already exists in current cycle, False otherwise
        """
        try:
            from src.infrastructure.persistence.positions_repository import PositionsRepository

            positions_repo = PositionsRepository(self.db)
            position = positions_repo.get_by_symbol(self.user_id, base_symbol)
            if not position:
                return False

            # Get current cycle from metadata
            cycle_meta = self._get_position_cycle_metadata(position)
            current_cycle = cycle_meta.get("current_cycle", 0)

            # Check if initial entry was at this level
            # Exception: If allow_reset=True, skip this check
            entry_rsi = position.entry_rsi
            if entry_rsi is not None and not allow_reset:
                # Determine which level the initial entry was at
                if level == 30 and entry_rsi < 30:
                    return True
                elif level == 20 and entry_rsi < 20:
                    return True
                elif level == 10 and entry_rsi < 10:
                    return True

            # Check existing re-entries in current cycle
            if not position.reentries:
                return False

            # Extract reentries array (handle both old and new format)
            reentries = position.reentries
            if isinstance(reentries, dict):
                reentries = reentries.get("reentries", [])
            if not isinstance(reentries, list):
                return False

            for reentry in reentries:
                if not isinstance(reentry, dict):
                    continue

                reentry_level = reentry.get("level")
                if reentry_level is None:
                    continue

                try:
                    reentry_level_int = int(reentry_level) if reentry_level is not None else None
                    if reentry_level_int == level:
                        # Check cycle number (if stored)
                        reentry_cycle = reentry.get("cycle")
                        if reentry_cycle is not None:
                            # Only block if it's in the same cycle
                            if int(reentry_cycle) == current_cycle:
                                return True
                        # Backward compatibility: if cycle not stored, assume cycle 0
                        elif current_cycle == 0:
                            return True
                except (ValueError, TypeError):
                    continue

            return False
        except Exception as e:
            self.logger.error(
                f"Error checking reentry level for {base_symbol}: {e}",
                exc_info=True,
                action="has_reentry_at_level",
            )
            return False

    def _determine_reentry_level(
        self, entry_rsi: float, current_rsi: float, position: Any
    ) -> tuple[int | None, dict[str, Any]]:
        """
        Determine next re-entry level based on entry RSI and current RSI (paper trading).

        Enhanced Hybrid Approach: Implements cycle tracking with reset detection on startup.

        Logic:
        - Entry at RSI < 30 → Re-entry at RSI < 20 → RSI < 10 → Reset
        - Entry at RSI < 20 → Re-entry at RSI < 10 → Reset
        - Entry at RSI < 10 → Only Reset

        Reset mechanism:
        - When RSI > 30: Store last_rsi_above_30 timestamp in position metadata
        - When RSI drops < 30 after last_rsi_above_30 exists: Increment current_cycle, reset all levels
        - On startup: Check if current RSI < 30 and last_rsi_above_30 exists → Reset detected

        Args:
            entry_rsi: RSI10 value at initial entry
            current_rsi: Current RSI10 value
            position: Position object (for tracking reset state)

        Returns:
            Tuple of (next_level, metadata_updates):
            - next_level: Next re-entry level (30, 20, or 10), or None if no re-entry opportunity
            - metadata_updates: Dict with cycle metadata updates to apply:
              {
                  "current_cycle": int | None,  # None = no change
                  "last_rsi_above_30": str | None,  # ISO timestamp or None to clear
                  "last_rsi_value": float | None,  # None = no change
              }
        """
        from src.infrastructure.db.timezone_utils import ist_now

        # Get current cycle metadata
        cycle_meta = self._get_position_cycle_metadata(position)
        current_cycle = cycle_meta.get("current_cycle", 0)
        last_rsi_above_30 = cycle_meta.get("last_rsi_above_30")
        last_rsi_value = cycle_meta.get("last_rsi_value")

        # Initialize metadata updates (None = no change)
        metadata_updates = {
            "current_cycle": None,
            "last_rsi_above_30": None,
            "last_rsi_value": None,
        }

        levels_taken = {"30": False, "20": False, "10": False}

        # Determine initial levels_taken based on entry_rsi
        if entry_rsi < 10:
            # Entry at RSI < 10: All levels taken
            levels_taken = {"30": True, "20": True, "10": True}
        elif entry_rsi < 20:
            # Entry at RSI < 20: 30 and 20 taken
            levels_taken = {"30": True, "20": True, "10": False}
        elif entry_rsi < 30:
            # Entry at RSI < 30: Only 30 taken
            levels_taken = {"30": True, "20": False, "10": False}
        else:
            # Entry at RSI >= 30: No levels taken (shouldn't happen, but handle it)
            levels_taken = {"30": False, "20": False, "10": False}

        # Fix Issue 1: Update levels_taken based on executed re-entries in current cycle
        # Check reentries array to see which levels have been taken in the current cycle
        if position and position.reentries:
            reentries = position.reentries
            if isinstance(reentries, dict):
                # New format: extract reentries array
                reentries = reentries.get("reentries", [])
            if isinstance(reentries, list):
                for reentry in reentries:
                    if not isinstance(reentry, dict):
                        continue
                    # Check if this re-entry is in the current cycle
                    reentry_cycle = reentry.get("cycle")
                    if reentry_cycle is not None:
                        # Only consider re-entries in the current cycle
                        if int(reentry_cycle) == current_cycle:
                            reentry_level = reentry.get("level")
                            if reentry_level is not None:
                                try:
                                    level_int = int(reentry_level)
                                    if level_int == 30:
                                        levels_taken["30"] = True
                                    elif level_int == 20:
                                        levels_taken["20"] = True
                                    elif level_int == 10:
                                        levels_taken["10"] = True
                                except (ValueError, TypeError):
                                    pass
                    # Backward compatibility: if cycle not stored, assume cycle 0
                    elif current_cycle == 0:
                        reentry_level = reentry.get("level")
                        if reentry_level is not None:
                            try:
                                level_int = int(reentry_level)
                                if level_int == 30:
                                    levels_taken["30"] = True
                                elif level_int == 20:
                                    levels_taken["20"] = True
                                elif level_int == 10:
                                    levels_taken["10"] = True
                            except (ValueError, TypeError):
                                pass

        # Fix: Mark intermediate levels as taken to prevent backtracking
        # Rule: When a re-entry at level X is taken, mark all higher levels
        # (between entry level and X) as taken
        if levels_taken.get("10"):
            # If level 10 is taken, mark level 20 and 30 as taken (can't backtrack)
            levels_taken["20"] = True
            levels_taken["30"] = True
            self.logger.debug(
                "Level 10 is taken - marking levels 20 and 30 as taken to prevent backtracking",
                action="_determine_reentry_level",
            )
        elif levels_taken.get("20"):
            # If level 20 is taken, mark level 30 as taken (can't backtrack)
            levels_taken["30"] = True
            self.logger.debug(
                "Level 20 is taken - marking level 30 as taken to prevent backtracking",
                action="_determine_reentry_level",
            )

        # Enhanced reset detection with startup support
        # Step 1: If RSI > 30, store last_rsi_above_30 timestamp
        if current_rsi > 30:
            # Store timestamp when RSI goes above 30
            now = ist_now()
            metadata_updates["last_rsi_above_30"] = now.isoformat()
            metadata_updates["last_rsi_value"] = current_rsi
            self.logger.debug(
                f"RSI > 30 detected: {current_rsi:.2f}. Storing last_rsi_above_30 timestamp.",
                action="_determine_reentry_level",
            )
            # Don't return yet - continue to check if we should trigger reset immediately

        # Step 2: Check for reset condition (RSI < 30 AND last_rsi_above_30 exists)
        # This works both during runtime and on startup
        reset_detected = False
        if current_rsi < 30 and last_rsi_above_30:
            # Reset detected! Increment cycle and reset all levels
            new_cycle = current_cycle + 1
            metadata_updates["current_cycle"] = new_cycle
            metadata_updates["last_rsi_above_30"] = None  # Clear reset flag
            metadata_updates["last_rsi_value"] = current_rsi  # Update last RSI value
            reset_detected = True

            self.logger.info(
                f"Reset detected: RSI dropped to {current_rsi:.2f} after being above 30. "
                f"Incrementing cycle from {current_cycle} to {new_cycle}.",
                action="_determine_reentry_level",
            )

            # Reset all levels, treat as new cycle
            levels_taken = {"30": False, "20": False, "10": False}

            # Fix Issue 2: Reset should check current RSI level and trigger appropriate level
            # Don't always return level 30 - check what level the current RSI satisfies
            if current_rsi < 10:
                # RSI < 10: Trigger level 10 (highest priority)
                self.logger.info(
                    f"Reset triggers re-entry at level 10 (RSI {current_rsi:.2f} < 10)",
                    action="_determine_reentry_level",
                )
                return (10, metadata_updates)
            elif current_rsi < 20:
                # RSI < 20: Trigger level 20
                self.logger.info(
                    f"Reset triggers re-entry at level 20 (RSI {current_rsi:.2f} < 20)",
                    action="_determine_reentry_level",
                )
                return (20, metadata_updates)
            elif current_rsi < 30:
                # RSI < 30: Trigger level 30
                self.logger.info(
                    f"Reset triggers re-entry at level 30 (RSI {current_rsi:.2f} < 30)",
                    action="_determine_reentry_level",
                )
                return (30, metadata_updates)
            else:
                # Shouldn't happen (we're in reset condition with RSI < 30)
                self.logger.warning(
                    f"Reset detected but RSI {current_rsi:.2f} is not < 30. This shouldn't happen.",
                    action="_determine_reentry_level",
                )
                return (None, metadata_updates)

        # Step 3: Update last_rsi_value if RSI changed (for tracking)
        if last_rsi_value != current_rsi:
            metadata_updates["last_rsi_value"] = current_rsi

        # Normal progression through levels
        # Fix Issue 3: Allow skipping levels if RSI drops directly to a lower level
        # Check levels in priority order (10 > 20 > 30) - allows skipping levels
        next_level = None

        if current_rsi < 10:
            # RSI < 10: Check if level 10 is available
            if not levels_taken.get("10"):
                next_level = 10
                self.logger.debug(
                    f"RSI {current_rsi:.2f} < 10, level 10 available (allows skipping level 20)",
                    action="_determine_reentry_level",
                )
        elif current_rsi < 20:
            # RSI < 20: Check if level 20 is available
            if not levels_taken.get("20"):
                next_level = 20
                self.logger.debug(
                    f"RSI {current_rsi:.2f} < 20, level 20 available",
                    action="_determine_reentry_level",
                )
        elif current_rsi < 30:
            # RSI < 30: Check if level 30 is available
            if not levels_taken.get("30"):
                next_level = 30
                self.logger.debug(
                    f"RSI {current_rsi:.2f} < 30, level 30 available",
                    action="_determine_reentry_level",
                )

        return (next_level, metadata_updates)

    def _calculate_execution_capital(self, price: float, avg_volume: float) -> float:
        """
        Calculate execution capital based on liquidity (matches real trading logic).

        Args:
            price: Current stock price
            avg_volume: Average daily volume

        Returns:
            Execution capital in Rs
        """
        # Default capital from strategy config
        default_capital = (
            self.strategy_config.user_capital
            if self.strategy_config and hasattr(self.strategy_config, "user_capital")
            else 20000.0
        )

        # If volume data not available, use default
        if not avg_volume or avg_volume <= 0:
            return default_capital

        # Calculate liquidity-based capital
        # This matches the logic from AutoTradeEngine.calculate_execution_capital
        avg_value = price * avg_volume

        # Tiers based on daily value traded
        if avg_value >= 100_000_000:  # >= 10 crore
            return min(50000.0, default_capital * 2.5)
        elif avg_value >= 50_000_000:  # >= 5 crore
            return min(40000.0, default_capital * 2.0)
        elif avg_value >= 20_000_000:  # >= 2 crore
            return min(30000.0, default_capital * 1.5)
        else:
            return default_capital
