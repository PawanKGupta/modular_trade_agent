#!/usr/bin/env python3
"""
Unified Trading Service for Kotak Neo
Runs all trading tasks with a single persistent client session throughout the day.

This service:
- Logs in ONCE at startup (no JWT expiry issues)
- Runs all scheduled tasks at their designated times
- Maintains single client session all day
- Gracefully shuts down at market close

Replaces 6 separate scheduled tasks with 1 unified service.

IMPORTANT: This is the ONLY entry point that creates new auth sessions.
All other components receive the shared auth session and only handle re-authentication.
"""

import argparse
import signal
import sys
import time
from datetime import datetime
from datetime import time as dt_time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

try:
    from . import config
    from .auth import KotakNeoAuth
    from .auto_trade_engine import AutoTradeEngine
    from .live_price_cache import LivePriceCache
    from .orders import KotakNeoOrders
    from .portfolio import KotakNeoPortfolio
    from .scrip_master import KotakNeoScripMaster
    from .sell_engine import SellOrderManager
    from .storage import cleanup_expired_failed_orders
    from .utils.service_conflict_detector import prevent_service_conflict
except ImportError:
    from modules.kotak_neo_auto_trader import config
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
    from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
    from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
    from modules.kotak_neo_auto_trader.storage import cleanup_expired_failed_orders
    from modules.kotak_neo_auto_trader.utils.service_conflict_detector import (
        prevent_service_conflict,
    )


class TradingService:
    """
    Unified trading service that runs all tasks with single persistent session.

    Phase 2.3: Now supports user-specific configuration and database integration.
    """

    def __init__(
        self,
        user_id: int,
        db_session,
        broker_creds: dict,
        strategy_config=None,  # StrategyConfig instance
        env_file: str | None = None,  # Deprecated: kept for backward compatibility
        skip_execution_tracking: bool = False,  # Set to True when called from individual services
    ):
        """
        Initialize trading service with user context.

        Args:
            user_id: User ID for this service instance
            db_session: SQLAlchemy database session
            broker_creds: Decrypted broker credentials dict
            strategy_config: User-specific StrategyConfig (optional, will be loaded if not provided)
            env_file: Deprecated - kept for backward compatibility only
        """
        self.user_id = user_id
        self.db = db_session
        self.broker_creds = broker_creds
        self.skip_execution_tracking = skip_execution_tracking

        # Load user-specific configuration if not provided
        if strategy_config is None:
            from src.application.services.config_converter import (
                user_config_to_strategy_config,
            )
            from src.infrastructure.persistence.user_trading_config_repository import (
                UserTradingConfigRepository,
            )

            config_repo = UserTradingConfigRepository(db_session)
            user_config = config_repo.get_or_create_default(user_id)
            self.strategy_config = user_config_to_strategy_config(user_config)
        else:
            self.strategy_config = strategy_config

        # Backward compatibility: env_file is deprecated but may be used for auth
        self.env_file = env_file

        # Initialize components
        self.auth: KotakNeoAuth | None = None
        self.engine: AutoTradeEngine | None = None
        self.sell_manager: SellOrderManager | None = None
        self.price_cache: LivePriceCache | None = None
        self.scrip_master: KotakNeoScripMaster | None = None
        self.running = False
        self.shutdown_requested = False

        # Task execution flags (reset daily)
        self.tasks_completed = {
            "analysis": False,
            "buy_orders": False,
            "eod_cleanup": False,
            "premarket_retry": False,
            "sell_monitor_started": False,
            "position_monitor": {},  # Track hourly runs
        }

        # User-scoped logger
        from src.infrastructure.logging import get_user_logger

        self.logger = get_user_logger(user_id=user_id, db=db_session, module="TradingService")

    def setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal"""
        logger.info("Shutdown signal received - stopping service gracefully...")
        self.shutdown_requested = True

    def initialize(self) -> bool:
        """
        Initialize service and login ONCE
        Returns True if successful
        """
        try:
            logger.info("=" * 80)
            logger.info("TRADING SERVICE INITIALIZATION")
            logger.info("=" * 80)

            # Check for service conflicts (prevent running with old services)
            if not prevent_service_conflict("run_trading_service.py", is_unified=True):
                logger.error("Service initialization aborted due to conflicts.")
                return False

            # Initialize authentication
            self.logger.info("Authenticating with Kotak Neo...", action="initialize")

            # Phase 2.4: Use env_file from decrypted credentials (or fallback for backward compatibility)
            if not self.env_file:
                if not self.broker_creds:
                    self.logger.error(
                        "No broker credentials or env_file provided", action="initialize"
                    )
                    return False
                # If broker_creds dict is provided but no env_file, create temp env file
                from src.application.services.broker_credentials import create_temp_env_file

                self.env_file = create_temp_env_file(self.broker_creds)
                self.logger.info(
                    "Created temporary env file from broker credentials", action="initialize"
                )

            # Initialize auth with env_file (Phase 2.4: env_file is created from decrypted credentials)
            self.auth = KotakNeoAuth(self.env_file)

            if not self.auth.login():
                self.logger.error("Authentication failed", action="initialize")
                return False

            self.logger.info(
                "Authentication successful - session active for the day", action="initialize"
            )

            # Initialize trading engine with user config
            self.logger.info("Initializing trading engine...", action="initialize")
            self.engine = AutoTradeEngine(
                env_file=self.env_file,
                auth=self.auth,
                user_id=self.user_id,
                db_session=self.db,
                strategy_config=self.strategy_config,
            )

            # Initialize engine (creates portfolio, orders, etc.)
            # Since auth is already logged in, this just initializes components without re-auth
            if not self.engine.login():
                logger.error("Engine initialization failed")
                return False

            # Initialize live prices (WebSocket for real-time LTP)
            self._initialize_live_prices()

            # Update portfolio with price manager for WebSocket LTP access
            if self.engine.portfolio and self.price_cache:
                self.engine.portfolio.price_manager = self.price_cache

            # Initialize sell order manager (will be started at market open)
            logger.info("Initializing sell order manager...")
            self.sell_manager = SellOrderManager(self.auth, price_manager=self.price_cache)

            # Subscribe to open positions immediately to avoid reconnect loops
            self._subscribe_to_open_positions()

            logger.info("Service initialized successfully")
            logger.info("=" * 80)
            return True

        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def is_trading_day(self) -> bool:
        """Check if today is a trading day (Monday-Friday)"""
        return datetime.now().weekday() < 5

    def is_market_hours(self) -> bool:
        """Check if currently in market hours (9:15 AM - 3:30 PM)"""
        now = datetime.now().time()
        return dt_time(9, 15) <= now <= dt_time(15, 30)

    def _initialize_live_prices(self):
        """
        Initialize LivePriceCache for real-time WebSocket prices.
        Loads scrip master and starts WebSocket connection.
        Graceful fallback if initialization fails.
        """
        try:
            logger.info("Initializing live price cache for real-time WebSocket prices...")

            # Load scrip master for symbol/token mapping
            self.scrip_master = KotakNeoScripMaster(
                auth_client=self.auth.client if hasattr(self.auth, "client") else None,
                exchanges=["NSE"],
            )
            self.scrip_master.load_scrip_master(force_download=False)
            logger.info("✓ Scrip master loaded")

            # Initialize LivePriceCache with WebSocket connection
            # Pass auth object so LivePriceCache can get fresh client after re-auth
            self.price_cache = LivePriceCache(
                auth_client=self.auth.client if hasattr(self.auth, "client") else None,
                scrip_master=self.scrip_master,
                stale_threshold_seconds=60,
                reconnect_delay_seconds=5,
                auth=self.auth,  # Pass auth reference for re-auth handling
            )

            # Start real-time price streaming
            self.price_cache.start()
            logger.info("✓ Live price cache started (WebSocket started)")

            # Wait for WebSocket connection to be established
            logger.info("Waiting for WebSocket connection...")
            if self.price_cache.wait_for_connection(timeout=10):
                logger.info("WebSocket connection established")
            else:
                logger.warning("WebSocket connection timeout, subscriptions may fail")

        except Exception as e:
            logger.warning(f"Failed to initialize live price cache: {e}")
            logger.info("Will fallback to yfinance for price data")
            self.price_cache = None
            self.scrip_master = None

    def _subscribe_to_open_positions(self):
        """
        Subscribe to symbols with active SELL orders only (not all open positions).
        Prevents reconnect loops from empty subscription list.

        Rationale:
        - Sell order monitoring only needs real-time prices for symbols with pending SELL orders
        - BUY orders don't need real-time prices (placed as AMO)
        - Open positions without sell orders don't need live tracking yet
        - SellOrderManager will subscribe to additional symbols as sell orders are placed at runtime
        """
        if not self.price_cache:
            return

        try:
            # Query broker for pending orders (only SELL orders need real-time prices)
            symbols = []
            try:
                from modules.kotak_neo_auto_trader.orders import KotakNeoOrders

                orders_api = KotakNeoOrders(self.auth)
                orders_response = orders_api.get_orders()

                if orders_response and "data" in orders_response:
                    for order in orders_response["data"]:
                        # Check order status
                        status = (
                            order.get("orderStatus")
                            or order.get("ordSt")
                            or order.get("status")
                            or ""
                        ).lower()

                        # Check transaction type - only SELL orders need real-time prices
                        txn_type = (
                            order.get("transactionType")
                            or order.get("trnsTp")
                            or order.get("txnType")
                            or ""
                        ).upper()

                        # Keep the full trading symbol (e.g., 'DALBHARAT-EQ') to get correct instrument token
                        # Don't strip the suffix as different segments (-EQ, -BL, etc.) have different tokens
                        broker_symbol = (
                            order.get("tradingSymbol")
                            or order.get("trdSym")
                            or order.get("symbol")
                            or ""
                        ).strip()

                        # Only subscribe to symbols with active SELL orders
                        if (
                            status in ["open", "pending"]
                            and txn_type in ["S", "SELL"]
                            and broker_symbol
                        ):
                            if broker_symbol not in symbols:
                                symbols.append(broker_symbol)
            except Exception as e:
                logger.debug(f"Could not fetch orders for subscription: {e}")

            if symbols:
                # Subscribe to positions for real-time prices (only SELL orders)
                self.price_cache.subscribe(symbols)
                logger.info(f"Subscribed to WebSocket for sell orders: {', '.join(symbols)}")
            else:
                logger.debug(
                    "No active sell orders found to subscribe (will subscribe as orders are placed)"
                )

        except Exception as e:
            logger.warning(f"Failed to subscribe to sell orders: {e}")
            # Don't fail initialization if subscription fails

    def should_run_task(self, task_name: str, scheduled_time: dt_time) -> bool:
        """
        Check if a task should run now

        Args:
            task_name: Name of task
            scheduled_time: Scheduled time for task

        Returns:
            True if task should run now
        """
        if self.tasks_completed.get(task_name):
            return False  # Already completed today

        now = datetime.now().time()

        # Allow 1 minute window for task execution
        time_diff = (now.hour * 60 + now.minute) - (
            scheduled_time.hour * 60 + scheduled_time.minute
        )
        return 0 <= time_diff < 2  # Run if within 2 minutes of scheduled time

    def run_premarket_retry(self):
        """9:00 AM - Retry failed orders from previous day"""
        from src.application.services.task_execution_wrapper import execute_task

        with execute_task(
            self.user_id,
            self.db,
            "premarket_retry",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TASK: PRE-MARKET RETRY (9:00 AM)")
            logger.info("=" * 80)

            # Run AMO placement (it handles retries automatically)
            recs = self.engine.load_latest_recommendations()
            if recs:
                summary = self.engine.place_new_entries(recs)
                logger.info(f"Pre-market retry summary: {summary}")
                task_context["recommendations_count"] = len(recs)
                task_context["summary"] = summary
            else:
                logger.info("No recommendations to retry")
                task_context["recommendations_count"] = 0

            self.tasks_completed["premarket_retry"] = True
            logger.info("Pre-market retry completed")

    def run_sell_monitor(self):
        """9:15 AM - Place sell orders and start monitoring (runs continuously)"""
        from src.application.services.task_execution_wrapper import execute_task

        # Only log to database on first start, not on every monitoring cycle
        if not self.tasks_completed["sell_monitor_started"]:
            with execute_task(
                self.user_id,
                self.db,
                "sell_monitor",
                self.logger,
                track_execution=not self.skip_execution_tracking,
            ) as task_context:
                logger.info("")
                logger.info("=" * 80)
                logger.info("TASK: SELL ORDER PLACEMENT (9:15 AM)")
                logger.info("=" * 80)

                # Subscribe to any new symbols when sell orders are placed
                if self.price_cache:
                    try:
                        # Get symbols from open positions (for orders to be placed)
                        open_positions = self.sell_manager.get_open_positions()
                        symbols = []
                        for trade in open_positions:
                            symbol = trade.get("symbol", "").upper()
                            if symbol and symbol not in symbols:
                                symbols.append(symbol)

                        # Also get symbols from existing sell orders
                        from .domain.value_objects.order_enums import OrderStatus
                        from .utils.order_field_extractor import OrderFieldExtractor
                        from .utils.order_status_parser import OrderStatusParser
                        from .utils.symbol_utils import extract_base_symbol

                        orders_api = KotakNeoOrders(self.auth)
                        orders_response = orders_api.get_orders()

                        if orders_response and "data" in orders_response:
                            for order in orders_response["data"]:
                                status = OrderStatusParser.parse_status(order)
                                txn_type = OrderFieldExtractor.get_transaction_type(order)
                                broker_symbol = OrderFieldExtractor.get_symbol(order)
                                base_symbol = (
                                    extract_base_symbol(broker_symbol) if broker_symbol else ""
                                )

                                if status == OrderStatus.OPEN and txn_type == "S" and base_symbol:
                                    if base_symbol not in symbols:
                                        symbols.append(base_symbol)

                        if symbols:
                            # Subscribe to any new symbols (existing ones already subscribed)
                            self.price_cache.subscribe(symbols)
                            logger.debug(
                                f"Subscribed to {len(symbols)} symbols for sell monitoring: {', '.join(symbols)}"
                            )

                    except Exception as e:
                        logger.debug(f"Failed to subscribe to symbols: {e}")

                # Place sell orders at market open
                orders_placed = self.sell_manager.run_at_market_open()
                logger.info(f"Placed {orders_placed} sell orders")
                task_context["orders_placed"] = orders_placed

                self.tasks_completed["sell_monitor_started"] = True

        # Monitor and update every minute during market hours (no DB logging for continuous monitoring)
        if self.is_market_hours():
            try:
                stats = self.sell_manager.monitor_and_update()
                logger.debug(
                    f"Sell monitor: {stats['checked']} checked, {stats['updated']} updated, {stats['executed']} executed"
                )
            except Exception as e:
                logger.error(f"Sell monitor update failed: {e}")

    def run_position_monitor(self):
        """9:30 AM (hourly) - Monitor positions for reentry/exit signals"""
        from src.application.services.task_execution_wrapper import execute_task

        current_hour = datetime.now().hour

        # Run once per hour, skip if already done this hour
        if self.tasks_completed["position_monitor"].get(current_hour):
            from src.application.services.task_execution_wrapper import skip_task

            skip_task(
                self.user_id,
                self.db,
                "position_monitor",
                f"Already executed for hour {current_hour}",
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
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"TASK: POSITION MONITOR ({current_hour}:30)")
            logger.info("=" * 80)

            # Monitor positions for signals (pass shared price_cache to avoid duplicate auth)
            summary = self.engine.monitor_positions(live_price_manager=self.price_cache)
            logger.info(f"Position monitor summary: {summary}")
            task_context["hour"] = current_hour
            task_context["summary"] = summary

            self.tasks_completed["position_monitor"][current_hour] = True
            logger.info("Position monitoring completed")

    def run_analysis(self):
        """4:00 PM - Analyze stocks and generate recommendations"""
        from src.application.services.task_execution_wrapper import execute_task

        max_retries = 3
        base_delay = 30.0  # Start with 30 seconds delay
        timeout_seconds = 1800  # 30 minutes timeout for market analysis

        with execute_task(
            self.user_id,
            self.db,
            "analysis",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            task_context["max_retries"] = max_retries
            task_context["timeout_seconds"] = timeout_seconds

            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        logger.info(
                            f"Retry attempt {attempt + 1}/{max_retries} for market analysis..."
                        )
                        time.sleep(base_delay * attempt)  # Exponential backoff
                        task_context["retry_attempt"] = attempt + 1

                    logger.info("")
                    logger.info("=" * 80)
                    logger.info("TASK: MARKET ANALYSIS (4:00 PM)")
                    logger.info("=" * 80)

                    # Run trade_agent.py --backtest with timeout
                    import subprocess

                    try:
                        result = subprocess.run(
                            [sys.executable, "trade_agent.py", "--backtest"],
                            check=False,
                            cwd=project_root,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",  # Replace problematic Unicode chars instead of failing
                            timeout=timeout_seconds,  # 30 minute timeout
                        )

                        if result.returncode == 0:
                            logger.info("Market analysis completed successfully")
                            task_context["return_code"] = 0
                            task_context["success"] = True
                            self.tasks_completed["analysis"] = True
                            return  # Success - exit retry loop
                        else:
                            # Log both stdout and stderr for better debugging
                            error_msg = (
                                f"Market analysis failed with return code {result.returncode}"
                            )
                            if result.stderr:
                                error_msg += f"\nSTDERR:\n{result.stderr}"
                            if result.stdout:
                                # Show last 500 chars of stdout to avoid log spam
                                stdout_snippet = (
                                    result.stdout[-500:]
                                    if len(result.stdout) > 500
                                    else result.stdout
                                )
                                error_msg += f"\nSTDOUT (last 500 chars):\n{stdout_snippet}"

                            logger.error(error_msg)
                            task_context["return_code"] = result.returncode
                            task_context["error_message"] = error_msg

                            # Check if it's a network-related error that we should retry
                            error_text = (result.stderr + result.stdout).lower()
                            network_keywords = [
                                "timeout",
                                "connection",
                                "socket",
                                "urllib3",
                                "recv_into",
                                "network",
                            ]
                            is_network_error = any(
                                keyword in error_text for keyword in network_keywords
                            )
                            task_context["is_network_error"] = is_network_error

                            if is_network_error and attempt < max_retries - 1:
                                logger.warning(
                                    f"Network error detected - will retry in {base_delay * (attempt + 1):.0f} seconds..."
                                )
                                continue  # Retry on network errors
                            else:
                                # Non-network error or final attempt - mark as failed
                                self.tasks_completed["analysis"] = (
                                    True  # Mark as attempted to prevent infinite retries
                                )
                                raise Exception(
                                    error_msg
                                )  # Raise to be caught by execute_task wrapper

                    except subprocess.TimeoutExpired:
                        logger.error(f"Market analysis timed out after {timeout_seconds} seconds")
                        task_context["timeout"] = True
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Will retry analysis in {base_delay * (attempt + 1):.0f} seconds..."
                            )
                            continue
                        else:
                            logger.error("Max retries exceeded for market analysis timeout")
                            self.tasks_completed["analysis"] = True
                            raise  # Raise to be caught by execute_task wrapper

                except Exception as e:
                    logger.error(f"Analysis failed with exception: {e}")
                    import traceback

                    traceback.print_exc()

                    # Check if it's a network-related exception
                    error_str = str(e).lower()
                    network_keywords = ["timeout", "connection", "socket", "network"]
                    is_network_error = any(keyword in error_str for keyword in network_keywords)
                    task_context["is_network_error"] = is_network_error

                    if is_network_error and attempt < max_retries - 1:
                        logger.warning(
                            f"Network exception detected - will retry in {base_delay * (attempt + 1):.0f} seconds..."
                        )
                        continue
                    else:
                        # Final attempt or non-network error
                        self.tasks_completed["analysis"] = True
                        raise  # Re-raise to be caught by execute_task wrapper

            # If we get here, all retries exhausted
            logger.error("Market analysis failed after all retry attempts")
            self.tasks_completed["analysis"] = True
            raise Exception("Market analysis failed after all retry attempts")

    def run_buy_orders(self):
        """4:05 PM - Place AMO buy orders for next day"""
        from src.application.services.task_execution_wrapper import execute_task

        with execute_task(
            self.user_id,
            self.db,
            "buy_orders",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TASK: PLACE BUY ORDERS (4:05 PM)")
            logger.info("=" * 80)

            recs = self.engine.load_latest_recommendations()
            if recs:
                summary = self.engine.place_new_entries(recs)
                logger.info(f"Buy orders summary: {summary}")
                task_context["recommendations_count"] = len(recs)
                task_context["summary"] = summary
            else:
                logger.info("No buy recommendations to place")
                task_context["recommendations_count"] = 0

            self.tasks_completed["buy_orders"] = True
            logger.info("Buy orders placement completed")

    def run_eod_cleanup(self):
        """6:00 PM - End-of-day cleanup"""
        from src.application.services.task_execution_wrapper import execute_task

        with execute_task(
            self.user_id,
            self.db,
            "eod_cleanup",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TASK: END-OF-DAY CLEANUP (6:00 PM)")
            logger.info("=" * 80)

            # Clean up expired failed orders
            # This removes failed orders that are older than 1 day (after market open)
            # or 2+ days old, keeping only today's orders and yesterday's orders before market open
            removed_count = 0
            try:
                # Phase 2.3: Use repository-based cleanup if available
                if hasattr(self.engine, "orders_repo") and self.engine.orders_repo:
                    # Repository-based cleanup (future implementation)
                    # For now, fallback to file-based if history_path exists
                    if hasattr(self.engine, "history_path") and self.engine.history_path:
                        removed_count = cleanup_expired_failed_orders(self.engine.history_path)
                else:
                    # Fallback to file-based cleanup
                    removed_count = cleanup_expired_failed_orders(config.TRADES_HISTORY_PATH)

                if removed_count > 0:
                    logger.info(f"Cleaned up {removed_count} expired failed order(s)")
                    task_context["removed_failed_orders"] = removed_count
                else:
                    logger.debug("No expired failed orders to clean up")
                    task_context["removed_failed_orders"] = 0
            except Exception as e:
                logger.warning(f"Failed to cleanup expired orders: {e}")
                task_context["cleanup_error"] = str(e)

            # Run EOD cleanup if available
            if hasattr(self.engine, "eod_cleanup") and self.engine.eod_cleanup:
                self.engine.eod_cleanup.run_eod_cleanup()
                logger.info("EOD cleanup completed")
                task_context["eod_cleanup_ran"] = True
            else:
                logger.info("EOD cleanup not configured")
                task_context["eod_cleanup_ran"] = False

            self.tasks_completed["eod_cleanup"] = True

            # Reset task completion flags for next day
            logger.info("EOD cleanup completed - resetting for next trading day")
            self.tasks_completed["analysis"] = False
            self.tasks_completed["buy_orders"] = False
            self.tasks_completed["premarket_retry"] = False
            self.tasks_completed["sell_monitor_started"] = False
            self.tasks_completed["position_monitor"] = {}
            task_context["tasks_reset"] = True
            logger.info("Service ready for next trading day")

    def run_scheduler(self):
        """Main scheduler loop - runs all tasks at their designated times"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("TRADING SERVICE STARTED (CONTINUOUS MODE)")
        logger.info("=" * 80)
        logger.info("Service will run continuously 24/7")
        logger.info("Tasks execute automatically on trading days (Mon-Fri)")
        logger.info("Press Ctrl+C to stop")
        logger.info("")

        # Log initial status
        now_init = datetime.now()
        logger.info(f"Current time: {now_init.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(
            f"Is trading day: {self.is_trading_day()} (weekday: {now_init.weekday()}, 0=Mon, 4=Fri)"
        )
        logger.info(f"Is market hours: {self.is_market_hours()}")
        logger.info("Starting scheduler loop...")
        logger.info("(Service will run continuously - tasks only execute on trading days)")
        logger.info("")

        last_minute = -1
        loop_count = 0

        while not self.shutdown_requested:
            loop_count += 1
            try:
                now = datetime.now()
                current_time = now.time()
                current_minute = now.minute

                # Log first few loops to confirm it's running
                if loop_count <= 3:
                    logger.info(
                        f"Scheduler loop iteration #{loop_count} at {now.strftime('%H:%M:%S')}"
                    )

                # Run tasks only once per minute (on trading days only)
                if current_minute != last_minute:
                    last_minute = current_minute
                    logger.debug(
                        f"Scheduler check at {current_time.strftime('%H:%M:%S')} (loop #{loop_count})"
                    )

                    # Only run tasks on trading days (Mon-Fri)
                    if self.is_trading_day():
                        logger.debug("  → Trading day detected - checking tasks...")
                        # 9:00 AM - Pre-market retry
                        if self.should_run_task("premarket_retry", dt_time(9, 0)):
                            self.run_premarket_retry()

                        # 9:15 AM onwards - Sell monitoring (continuous)
                        if current_time >= dt_time(9, 15) and self.is_market_hours():
                            self.run_sell_monitor()

                        # 9:30 AM, 10:30 AM, 11:30 AM, etc. - Position monitoring (hourly)
                        if current_time.minute == 30 and 9 <= current_time.hour <= 15:
                            self.run_position_monitor()

                        # 4:00 PM - Analysis
                        if self.should_run_task("analysis", dt_time(16, 0)):
                            self.run_analysis()

                        # 4:05 PM - Buy orders
                        if self.should_run_task("buy_orders", dt_time(16, 5)):
                            self.run_buy_orders()

                        # 6:00 PM - EOD cleanup (resets for next day)
                        if self.should_run_task("eod_cleanup", dt_time(18, 0)):
                            self.run_eod_cleanup()

                # Periodic heartbeat log (every 5 minutes to show service is alive)
                if now.minute % 5 == 0 and now.second < 30:
                    logger.info(
                        f"Scheduler heartbeat: {now.strftime('%Y-%m-%d %H:%M:%S')} - Service running (loop #{loop_count})..."
                    )

                # Sleep for 30 seconds between checks
                time.sleep(30)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                self.shutdown_requested = True
                break

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                import traceback

                traceback.print_exc()
                logger.error(
                    "Service will continue after error - waiting 60 seconds before retry..."
                )
                time.sleep(60)  # Wait a bit before retrying

    def shutdown(self):
        """Graceful shutdown"""
        try:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TRADING SERVICE SHUTDOWN")
            logger.info("=" * 80)

            # Clean up price cache
            if self.price_cache:
                try:
                    self.price_cache.stop()
                    logger.info("Price cache stopped")
                except Exception as e:
                    logger.warning(f"Error stopping price cache: {e}")

            # Logout from session
            if self.auth:
                self.auth.logout()
                logger.info("Logged out successfully")

            logger.info("Service stopped gracefully")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def run(self):
        """Main entry point - Runs continuously"""
        logger.info("Setting up signal handlers...")
        self.setup_signal_handlers()

        # Initialize service (single login)
        logger.info("Starting service initialization...")
        if not self.initialize():
            logger.error("Failed to initialize service - service will exit")
            return

        logger.info("Initialization complete - entering scheduler loop...")

        try:
            # Run scheduler continuously
            self.run_scheduler()
        except Exception as e:
            logger.error(f"Fatal error in scheduler: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # Always cleanup on exit
            logger.info("Entering shutdown sequence...")
            self.shutdown()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Unified Trading Service - Single login session for all trading tasks"
    )
    parser.add_argument(
        "--env",
        default="modules/kotak_neo_auto_trader/kotak_neo.env",
        help="Path to Kotak Neo credentials env file",
    )

    args = parser.parse_args()

    # Create and run service
    service = TradingService(env_file=args.env)
    service.run()


if __name__ == "__main__":
    main()
