"""
Paper Trading Service Adapter

Provides a TradingService-compatible interface for paper trading mode.
Uses PaperTradingBrokerAdapter instead of real broker authentication.
"""

from __future__ import annotations

import logging
from pathlib import Path

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
            initial_capital: Starting virtual capital (default ₹1 lakh)
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
            "sell_monitor_started": False,
            "position_monitor": {},
        }

        # Engine-like interface for compatibility
        self.engine = None  # Will be set up to use paper trading broker

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
                f"⚠️  PAPER TRADING MODE - NO REAL MONEY (Capital: ₹{self.initial_capital:,.2f})",
                action="initialize",
            )
            self.logger.info("=" * 80, action="initialize")

            # Create paper trading configuration
            # Set max_position_size from strategy_config.user_capital if available
            max_position_size = 50000.0  # Default
            if self.strategy_config and hasattr(self.strategy_config, "user_capital"):
                max_position_size = self.strategy_config.user_capital
                self.logger.info(
                    f"Using max_position_size from trading config: ₹{max_position_size:,.2f}",
                    action="initialize",
                )

            self.logger.info(
                f"Creating paper trading config (Capital: ₹{self.initial_capital:,.2f}, "
                f"Max Position Size: ₹{max_position_size:,.2f})...",
                action="initialize",
            )
            self.config = PaperTradingConfig(
                initial_capital=self.initial_capital,
                enable_slippage=True,
                enable_fees=True,
                enforce_market_hours=True,
                price_source="live",  # Use live prices
                storage_path=self.storage_path,
                auto_save=True,
                max_position_size=max_position_size,  # Use user's trading config
            )

            # Initialize paper trading broker
            self.logger.info("Initializing paper trading broker...", action="initialize")
            self.broker = PaperTradingBrokerAdapter(self.config)

            if not self.broker.connect():
                self.logger.error("Failed to connect to paper trading system", action="initialize")
                return False

            self.logger.info("✅ Paper trading broker connected", action="initialize")

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

            self.logger.info(f"💰 Available Balance: ₹{balance.amount:,.2f}", action="initialize")
            self.logger.info(f"📊 Holdings: {len(holdings)}", action="initialize")

            if holdings:
                for holding in holdings:
                    pnl = holding.calculate_pnl()
                    self.logger.info(
                        f"  • {holding.symbol}: {holding.quantity} shares @ "
                        f"₹{holding.average_price.amount:.2f} (P&L: ₹{pnl.amount:.2f})",
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

    def run_sell_monitor(self):
        """9:15 AM - Place sell orders and start monitoring (paper trading)"""
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

                if not self.engine:
                    error_msg = "Paper trading engine not initialized. Call initialize() first."
                    self.logger.error(error_msg, action="run_sell_monitor")
                    raise RuntimeError(error_msg)

                # Paper trading: Monitor sell conditions
                # For now, log that monitoring is active
                self.logger.info(
                    "Sell monitoring active (paper trading mode)", action="run_sell_monitor"
                )
                task_context["monitoring_active"] = True

                self.tasks_completed["sell_monitor_started"] = True

        # Monitor and update every minute during market hours
        # (In paper trading, this would check positions and update sell orders)
        self.logger.debug("Sell monitor check (paper trading)", action="run_sell_monitor")

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
                    self.logger.info("📊 Generating daily report...", action="run_eod_cleanup")
                    self.reporter.print_summary()

                    # Export report
                    from datetime import datetime

                    timestamp = datetime.now().strftime("%Y%m%d")
                    report_path = f"{self.storage_path}/reports/report_{timestamp}.json"
                    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
                    self.reporter.export_to_json(report_path)
                    self.logger.info(f"📄 Report saved to: {report_path}", action="run_eod_cleanup")
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
                "sell_monitor_started": False,
                "position_monitor": {},
            }
            task_context["tasks_reset"] = True

            self.logger.info("Service ready for next trading day", action="run_eod_cleanup")
            self.tasks_completed["eod_cleanup"] = True


class PaperTradingEngineAdapter:
    """
    Adapter that provides AutoTradeEngine-compatible interface using paper trading broker.

    This allows existing code that uses AutoTradeEngine to work with paper trading.
    """

    def __init__(self, broker, user_id, db_session, strategy_config, logger):
        """
        Initialize paper trading engine adapter.

        Args:
            broker: PaperTradingBrokerAdapter instance
            user_id: User ID
            db_session: Database session
            strategy_config: Strategy configuration
            logger: Logger instance
        """
        self.broker = broker
        self.user_id = user_id
        self.db = db_session
        self.strategy_config = strategy_config
        self.logger = logger

    def load_latest_recommendations(self):
        """
        Load latest recommendations from database (Signals table).

        Returns:
            List of Recommendation objects
        """
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from src.infrastructure.persistence.signals_repository import SignalsRepository

        try:
            # Query Signals table for buy/strong_buy recommendations
            signals_repo = SignalsRepository(self.db)

            # Get latest signals (today's or most recent)
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

            # Convert Signals to Recommendation objects
            recommendations = []
            for signal in signals:
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

                # Get last_close price
                last_close = signal.last_close or 0.0
                if last_close <= 0:
                    self.logger.warning(
                        f"Skipping {ticker}: invalid last_close ({last_close})",
                        action="load_recommendations",
                    )
                    continue

                # Calculate execution_capital if available from liquidity_recommendation or trading_params
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

        # Get current holdings to check for duplicates
        holdings = self.broker.get_holdings()
        # Normalize symbols (remove .NS suffix and uppercase)
        current_symbols = {h.symbol.replace(".NS", "").upper() for h in holdings}

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
                            f"Pre-fetched {successful_fetches}/{len(tickers_to_fetch)} prices (batch)",
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

            # Skip if already in portfolio
            if normalized_ticker in current_symbols:
                self.logger.debug(
                    f"Skipping {rec.ticker} - already in portfolio", action="place_new_entries"
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

                # Get max position size from broker config (which is set from strategy_config.user_capital)
                # This ensures we use the user's configured capital per trade
                max_position_size = (
                    self.broker.config.max_position_size if self.broker.config else 50000.0
                )

                # Limit execution_capital to max_position_size
                if execution_capital > max_position_size:
                    self.logger.info(
                        f"Limiting execution_capital for {rec.ticker} from ₹{execution_capital:,.0f} "
                        f"to ₹{max_position_size:,.0f} (max position size from config)",
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
                        f"(order value: ₹{order_value:,.2f})",
                        action="place_new_entries",
                    )

                if qty <= 0:
                    self.logger.warning(
                        f"Invalid quantity for {rec.ticker}: {qty}", action="place_new_entries"
                    )
                    continue

                # Extract base symbol (remove .NS suffix if present) for order placement
                symbol = rec.ticker.replace(".NS", "").upper()

                # Create order
                order = Order(
                    symbol=symbol,
                    quantity=qty,
                    order_type=OrderType.MARKET,
                    transaction_type=TransactionType.BUY,
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
                        f"✅ Placed paper buy order: {rec.ticker} x {qty} @ ₹{price:.2f} "
                        f"(Order ID: {order_id}, Capital: ₹{execution_capital:,.0f})",
                        action="place_new_entries",
                    )
                    summary["placed"] += 1
                except Exception as order_error:
                    self.logger.error(
                        f"❌ Failed to place order for {rec.ticker}: {order_error}",
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

        Returns:
            Summary dict with monitoring statistics
        """
        summary = {"checked": 0, "updated": 0, "executed": 0}

        if not self.broker or not self.broker.is_connected():
            self.logger.error("Paper trading broker not connected", action="monitor_positions")
            return summary

        # Get current holdings
        holdings = self.broker.get_holdings()
        summary["checked"] = len(holdings)

        # In paper trading, we would check positions and update sell orders
        # For now, just log that monitoring is active
        self.logger.debug(
            f"Monitoring {len(holdings)} positions (paper trading)", action="monitor_positions"
        )

        return summary
