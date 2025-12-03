"""
Paper Trading Service Adapter

Provides a TradingService-compatible interface for paper trading mode.
Uses PaperTradingBrokerAdapter instead of real broker authentication.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import (
    PaperTradingBrokerAdapter,
)
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter
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
            "position_monitor": {},
        }

        # Engine-like interface for compatibility
        self.engine = None  # Will be set up to use paper trading broker

        # Sell order tracking - Frozen EMA9 strategy (matches backtest)
        # Format: {symbol: {'order_id': str, 'target_price': float,
        #                   'qty': int, 'entry_date': str, 'ticker': str}}
        self.active_sell_orders = {}
        self._sell_orders_file = Path(self.storage_path) / "active_sell_orders.json"

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
                    original_price = order.price.amount if order.price else premarket_price
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
                        from modules.kotak_neo_auto_trader.domain import (
                            Order,
                        )

                        new_order = Order(
                            symbol=order.symbol,
                            quantity=new_qty,
                            order_type=order.order_type,  # Keep as MARKET
                            transaction_type=order.transaction_type,
                            # price=None for MARKET orders (not used, executes at market price)
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

    def run_position_monitor(self):
        """9:30 AM (hourly) - Monitor positions for reentry/exit signals (paper trading)"""
        from datetime import datetime

        from src.application.services.task_execution_wrapper import execute_task

        current_hour = datetime.now().hour

        # Run once per hour, skip if already done this hour
        if self.tasks_completed["position_monitor"].get(current_hour):
            from src.application.services.task_execution_wrapper import skip_task

            skip_task(
                self.user_id,
                self.db,
                "position_monitor",
                f"Already monitored this hour ({current_hour}:00)",
                self.logger,
            )
            return

        with execute_task(
            self.user_id,
            self.db,
            "position_monitor",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            self.logger.info("", action="run_position_monitor")
            self.logger.info("=" * 80, action="run_position_monitor")
            self.logger.info(
                f"TASK: POSITION MONITOR ({current_hour}:30) - PAPER TRADING",
                action="run_position_monitor",
            )
            self.logger.info("=" * 80, action="run_position_monitor")

            if not self.engine:
                error_msg = "Paper trading engine not initialized. Call initialize() first."
                self.logger.error(error_msg, action="run_position_monitor")
                raise RuntimeError(error_msg)

            # Paper trading: Monitor positions
            summary = self.engine.monitor_positions()
            self.logger.info(f"Position monitor summary: {summary}", action="run_position_monitor")
            task_context["hour"] = current_hour
            task_context["summary"] = summary

            # If re-entries happened, sync sell order quantities and targets with updated holdings
            if summary.get("reentries", 0) > 0:
                self.logger.info(
                    f"Re-entries detected ({summary['reentries']}), syncing sell order quantities and targets...",
                    action="run_position_monitor",
                )

                # Calculate new EMA9 targets for symbols with re-entries (matches backtest)
                symbol_targets = {}
                holdings = self.broker.get_holdings() if self.broker else []
                for holding in holdings:
                    symbol = holding.symbol.replace(".NS", "").replace(".BO", "").replace("-EQ", "")
                    if symbol in self.active_sell_orders:
                        ticker = f"{symbol}.NS"
                        new_target = self._calculate_ema9(ticker)
                        if new_target:
                            symbol_targets[symbol] = new_target
                            self.logger.debug(
                                f"Calculated new EMA9 target for {symbol}: Rs {new_target:.2f}",
                                action="run_position_monitor",
                            )

                updated_count = self._sync_sell_order_quantities_with_holdings(symbol_targets)
                if updated_count > 0:
                    self.logger.info(
                        f"Updated {updated_count} sell order quantities and targets after re-entry",
                        action="run_position_monitor",
                    )
                    task_context["sell_orders_updated"] = updated_count

            self.tasks_completed["position_monitor"][current_hour] = True
            self.logger.info("Position monitoring completed", action="run_position_monitor")

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
                "position_monitor": {},
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
        pending_sell_symbols = {
            o.symbol for o in pending_orders if o.is_sell_order() and o.is_active()
        }

        for holding in holdings:
            try:
                symbol = holding.symbol
                ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
                quantity = holding.quantity

                # Skip if already have active sell order (in memory or broker)
                if symbol in self.active_sell_orders or symbol in pending_sell_symbols:
                    self.logger.debug(
                        f"Skipping {symbol} - already has active sell order "
                        f"(in memory: {symbol in self.active_sell_orders}, "
                        f"in broker: {symbol in pending_sell_symbols})",
                        action="_place_sell_orders",
                    )
                    # If it's in broker but not in memory, add it to memory for tracking
                    if symbol in pending_sell_symbols and symbol not in self.active_sell_orders:
                        # Try to find the order details from broker
                        for order in pending_orders:
                            if (
                                order.symbol == symbol
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
                                    self.active_sell_orders[symbol] = {
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
                                        f"Restored sell order tracking for {symbol} from broker",
                                        action="_place_sell_orders",
                                    )
                    # Check if holdings quantity has increased (re-entry happened)
                    # and update sell order quantity and target to match
                    if symbol in self.active_sell_orders:
                        current_order_qty = self.active_sell_orders[symbol].get("qty", 0)
                        if quantity > current_order_qty:
                            self.logger.info(
                                f"Holdings increased for {symbol} ({current_order_qty} -> {quantity}), "
                                f"updating sell order quantity and target",
                                action="_place_sell_orders",
                            )
                            # Recalculate EMA9 target (matches backtest behavior)
                            new_target = self._calculate_ema9(ticker)
                            self._update_sell_order_quantity(symbol, quantity, new_target)
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
                # Note: Sell order is already placed by _place_sell_orders()
                # This just logs and removes from tracking once executed
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
                    # Note: Actual order execution happens via check_and_execute_pending_orders()
                    # Remove from tracking if no longer in holdings
                    holding = self.broker.get_holding(symbol)
                    if not holding or holding.quantity == 0:
                        symbols_to_remove.append(symbol)
                        self.logger.info(
                            f"Position closed for {symbol}, removing from tracking",
                            action="_monitor_sell_orders",
                        )
                    continue

                # Exit Condition 2: RSI > 50 (secondary exit for failing stocks)
                RSI_EXIT_THRESHOLD = 50  # From backtest: 10% of exits, 37% win rate
                if not pd.isna(rsi) and rsi > RSI_EXIT_THRESHOLD:
                    self.logger.info(
                        f"? EXIT TRIGGERED: {symbol} - RSI {rsi:.1f} > 50 (falling knife exit)",
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

                        self.logger.info(
                            f"? RSI exit: {symbol} @ Rs {close:.2f} (RSI: {rsi:.1f})",
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
            holding_symbols = {h.symbol for h in holdings}

            # Also check pending orders from broker to avoid duplicates
            pending_orders = self.broker.get_pending_orders() if self.broker else []
            pending_sell_symbols = {
                o.symbol for o in pending_orders if o.is_sell_order() and o.is_active()
            }

            valid_orders = {}
            for symbol, order_info in loaded_orders.items():
                # Keep order if:
                # 1. Symbol still has holdings, OR
                # 2. Symbol has a pending sell order in broker
                if symbol in holding_symbols or symbol in pending_sell_symbols:
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
        holdings_map = {h.symbol: h.quantity for h in holdings}

        updated_count = 0
        for symbol, order_info in list(self.active_sell_orders.items()):
            if symbol in holdings_map:
                current_qty = order_info.get("qty", 0)
                holdings_qty = holdings_map[symbol]

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
                user_status = signals_repo.get_user_signal_status(signal.id, self.user_id)
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

        # Normalize symbols from holdings (remove .NS suffix and uppercase)
        current_symbols = {h.symbol.replace(".NS", "").upper() for h in holdings}

        # Also check pending/open buy orders to prevent duplicates
        for order in pending_orders:
            if order.is_buy_order() and order.is_active():
                normalized_symbol = order.symbol.replace(".NS", "").upper()
                current_symbols.add(normalized_symbol)
                self.logger.debug(
                    f"Found pending buy order for {order.symbol} (Status: {order.status})",
                    action="place_new_entries",
                )

        # Check portfolio limit (from strategy config or default 6)
        max_portfolio_size = (
            self.strategy_config.max_portfolio_size
            if self.strategy_config and hasattr(self.strategy_config, "max_portfolio_size")
            else 6
        )
        if len(holdings) >= max_portfolio_size:
            self.logger.warning(
                f"Portfolio limit reached ({len(holdings)}/{max_portfolio_size})",
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

            # Normalize ticker for comparison (remove .NS suffix and uppercase)
            normalized_ticker = rec.ticker.replace(".NS", "").upper()

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

    def monitor_positions(self):
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
