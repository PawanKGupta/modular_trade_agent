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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from datetime import time as dt_time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

# Import holiday calendar for trading day checks
try:
    from src.infrastructure.db.timezone_utils import ist_now
    from src.infrastructure.utils.holiday_calendar import is_trading_day as is_trading_day_check
except ImportError:
    # Fallback if running from different context
    ist_now = None
    is_trading_day_check = None

try:
    from . import config
    from .auth import KotakNeoAuth
    from .auto_trade_engine import AutoTradeEngine, OrderPlacementError
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
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine, OrderPlacementError
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
        broker_creds: dict | None = None,  # None for paper trading mode
        strategy_config=None,  # StrategyConfig instance
        env_file: str | None = None,  # Deprecated: kept for backward compatibility
        skip_execution_tracking: bool = False,  # Set to True when called from individual services
    ):
        """
        Initialize trading service with user context.

        Args:
            user_id: User ID for this service instance
            db_session: SQLAlchemy database session (used for initialization only, thread-local session created in run())
            broker_creds: Decrypted broker credentials dict (None for paper trading mode)
            strategy_config: User-specific StrategyConfig (optional, will be loaded if not provided)
            env_file: Deprecated - kept for backward compatibility only
        """
        self.user_id = user_id
        self.db = db_session  # Initial session (for setup only)
        self.broker_creds = broker_creds
        self.skip_execution_tracking = skip_execution_tracking
        # Track async task futures to prevent re-queuing long-running tasks.
        # This is critical for continuous tasks like sell_monitor: if one run exceeds timeout,
        # it may continue running in background; without this guard we would queue duplicates
        # that then "time out before execution" behind the single-worker executor.
        self._task_futures: dict[str, object] = {}
        self._task_futures_lock = threading.Lock()
        # Per-user single-instance scheduler lock (table-based lock).
        # Prevents multiple scheduler loops for the same user across processes/containers.
        self._scheduler_lock_acquired: bool = False
        self._scheduler_lock_id: str | None = None  # Changed from lock_key to lock_id (table-based)

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
            self.strategy_config = user_config_to_strategy_config(
                user_config, db_session=db_session
            )
        else:
            self.strategy_config = strategy_config

        # Backward compatibility: env_file is deprecated but may be used for auth
        self.env_file = env_file

        # Initialize components
        self.auth: KotakNeoAuth | None = None
        self.engine: AutoTradeEngine | None = None
        self.sell_manager: SellOrderManager | None = None
        self.unified_order_monitor = None  # Phase 2: Unified order monitor
        self.price_cache: LivePriceCache | None = None
        self.scrip_master: KotakNeoScripMaster | None = None
        self.running = False

        # Initialize schedule manager for dynamic task scheduling
        from src.application.services.schedule_manager import ScheduleManager  # noqa: PLC0415

        self._schedule_manager = ScheduleManager(db_session)
        self.shutdown_requested = False

        # Thread pool executor for async task execution (prevents blocking scheduler loop)
        self.task_executor: ThreadPoolExecutor | None = None

        # Task execution flags (reset daily)
        self.tasks_completed = {
            "analysis": False,
            "buy_orders": False,
            "eod_cleanup": False,
            "premarket_retry": False,
            "premarket_amo_adjustment": False,
            "sell_monitor_started": False,
        }

        # User-scoped logger
        from src.infrastructure.logging import get_user_logger

        self.logger = get_user_logger(user_id=user_id, db=db_session, module="TradingService")

    def setup_signal_handlers(self):
        """
        Setup graceful shutdown handlers.

        Note: signal.signal() may not work in background threads on some platforms.
        This is expected and non-critical - the service can still be stopped via
        shutdown_requested flag or through the service management API.
        """
        try:
            signal.signal(signal.SIGINT, self._handle_shutdown)
            signal.signal(signal.SIGTERM, self._handle_shutdown)
        except (ValueError, OSError, RuntimeError):
            # Signal handlers can only be set from main thread on some platforms
            # This is expected behavior for background threads - re-raise to be handled by caller
            raise

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
            self.logger.info("=" * 80, action="initialize")
            self.logger.info("TRADING SERVICE INITIALIZATION", action="initialize")
            self.logger.info("=" * 80, action="initialize")

            # Check for service conflicts (prevent running with old services)
            self.logger.info("Checking for service conflicts...", action="initialize")
            if not prevent_service_conflict("run_trading_service.py", is_unified=True):
                self.logger.error(
                    "Service initialization aborted due to conflicts.", action="initialize"
                )
                return False
            self.logger.info("No service conflicts detected", action="initialize")

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

            # Use shared session manager to ensure ONE client object per user
            # This client is shared with web API and all other services
            from .shared_session_manager import get_shared_session_manager

            session_manager = get_shared_session_manager()
            self.auth = session_manager.get_or_create_session(self.user_id, self.env_file)

            if not self.auth:
                self.logger.error("Authentication failed", action="initialize")
                return False

            self.logger.info(
                f"Authentication successful - using shared session for user {self.user_id}",
                action="initialize",
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
                self.logger.error("Engine initialization failed", action="initialize")
                return False
            self.logger.info("Trading engine initialized successfully", action="initialize")

            # Initialize live prices (WebSocket for real-time LTP)
            # For buy_orders task, WebSocket is not needed (AMO orders don't need real-time prices)
            # Skip WebSocket initialization to avoid blocking - buy orders use yfinance for prices
            self.logger.info(
                "Skipping WebSocket initialization for buy_orders (not needed for AMO orders)",
                action="initialize",
            )
            self.price_cache = None
            self.scrip_master = None

            # Update portfolio with price manager for WebSocket LTP access
            if self.engine.portfolio and self.price_cache:
                self.engine.portfolio.price_manager = self.price_cache

            # Initialize sell order manager (will be started at market open)
            # For buy_orders task, this is not needed, but initialize it anyway for consistency
            try:
                self.logger.info("Initializing sell order manager...", action="initialize")
                # Get positions_repo and orders_repo from engine (required for database-only tracking)
                positions_repo = (
                    self.engine.positions_repo if hasattr(self.engine, "positions_repo") else None
                )
                orders_repo = (
                    self.engine.orders_repo if hasattr(self.engine, "orders_repo") else None
                )
                user_id = self.user_id

                if not positions_repo:
                    self.logger.error(
                        "PositionsRepository not available - sell order placement will fail. "
                        "Ensure AutoTradeEngine has positions_repo initialized.",
                        action="initialize",
                    )
                    # Don't raise - let it fail gracefully when get_open_positions() is called
                if not user_id:
                    self.logger.error(
                        "user_id not available - sell order placement will fail.",
                        action="initialize",
                    )
                    # Don't raise - let it fail gracefully when get_open_positions() is called

                # Phase 3.2: Pass OrderStatusVerifier to SellOrderManager for shared results
                order_verifier = (
                    self.engine.order_verifier
                    if self.engine and hasattr(self.engine, "order_verifier")
                    else None
                )
                self.sell_manager = SellOrderManager(
                    self.auth,
                    positions_repo=positions_repo,
                    user_id=user_id,
                    orders_repo=orders_repo,  # For metadata enrichment
                    price_manager=self.price_cache,
                    order_verifier=order_verifier,  # Phase 3.2: Share OrderStatusVerifier results
                    strategy_config=self.strategy_config,  # Pass user's trading config for exchange preference
                )

                # Phase 2: Initialize unified order monitor for buy and sell order monitoring
                # Phase 9: Pass telegram_notifier for notifications
                try:
                    from .unified_order_monitor import UnifiedOrderMonitor

                    telegram_notifier = (
                        self.engine.telegram_notifier
                        if self.engine and hasattr(self.engine, "telegram_notifier")
                        else None
                    )
                    self.unified_order_monitor = UnifiedOrderMonitor(
                        sell_order_manager=self.sell_manager,
                        db_session=self.db,
                        user_id=self.user_id,
                        telegram_notifier=telegram_notifier,
                    )
                    self.logger.info("Unified order monitor initialized", action="initialize")
                except Exception as e:
                    self.logger.warning(
                        f"Unified order monitor initialization failed: {e}",
                        action="initialize",
                    )
                    self.unified_order_monitor = None
            except Exception as e:
                self.logger.warning(
                    f"Sell order manager initialization failed (non-critical for buy orders): {e}",
                    action="initialize",
                )
                self.sell_manager = None
                self.unified_order_monitor = None

            # Subscribe to open positions immediately to avoid reconnect loops
            # For buy_orders task, this is not needed (AMO orders don't need real-time prices)
            # Skip it to avoid blocking
            self.logger.info(
                "Skipping position subscription for buy_orders (not needed for AMO orders)",
                action="initialize",
            )
            # try:
            #     self._subscribe_to_open_positions()
            # except Exception as e:
            #     self.logger.warning(f"Position subscription failed (non-critical for buy orders): {e}")

            self.logger.info("Service initialized successfully", action="initialize")
            self.logger.info("=" * 80, action="initialize")
            return True

        except Exception as e:
            self.logger.error(
                f"Service initialization failed: {e}", exc_info=True, action="initialize"
            )
            import traceback

            traceback.print_exc()
            return False

    def is_trading_day(self) -> bool:
        """Check if today is a trading day (Monday-Friday, excluding holidays)"""
        if is_trading_day_check and ist_now:
            return is_trading_day_check(ist_now().date())
        # Fallback to weekday check if imports failed
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
            logger.info("[OK] Scrip master loaded")

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
            logger.info("[OK] Live price cache started (WebSocket started)")

            # Wait for WebSocket connection to be established
            # Use shorter timeout to avoid blocking buy_orders task
            # Buy orders don't need WebSocket (AMO orders placed before market open)
            logger.info("Waiting for WebSocket connection (non-blocking, 3s timeout)...")
            try:
                if self.price_cache.wait_for_connection(timeout=3):  # Reduced timeout to 3s
                    logger.info("WebSocket connection established")
                else:
                    logger.warning(
                        "WebSocket connection timeout (non-critical for buy orders), will use fallback"
                    )
            except Exception as e:
                logger.warning(f"WebSocket wait failed (non-critical): {e}")

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
                # Phase 4.1: Use PriceService for centralized subscription management
                from modules.kotak_neo_auto_trader.services import get_price_service

                price_service = get_price_service(
                    live_price_manager=self.price_cache, enable_caching=True
                )
                subscribed = price_service.subscribe_to_symbols(symbols, service_id="sell_monitor")
                if subscribed:
                    logger.info(
                        f"Subscribed to WebSocket for sell orders: {', '.join(symbols)} "
                        f"(via PriceService - deduplication enabled)"
                    )
                else:
                    # Fallback to direct subscription if PriceService fails
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

        # Allow 2 minute window for task execution
        time_diff = (now.hour * 60 + now.minute) - (
            scheduled_time.hour * 60 + scheduled_time.minute
        )
        should_run = 0 <= time_diff < 2

        # Debug: log when a one-shot task is due or narrowly missed
        if task_name not in ("sell_monitor", "premarket_amo_adjustment"):
            if should_run:
                self.logger.info(
                    f"Task {task_name} is due: now={now.strftime('%H:%M:%S')}, "
                    f"scheduled={scheduled_time}, time_diff={time_diff}",
                    action="scheduler",
                )
            elif 0 <= time_diff < 5:
                # Just missed the window - log for debugging
                self.logger.info(
                    f"Task {task_name} window missed: now={now.strftime('%H:%M:%S')}, "
                    f"scheduled={scheduled_time}, time_diff={time_diff}, "
                    f"completed={self.tasks_completed.get(task_name, 'N/A')}",
                    action="scheduler",
                )

        return should_run

    def run_premarket_retry(self):
        """8:00 AM - Retry orders with RETRY_PENDING status from database"""
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
            logger.info("TASK: PRE-MARKET RETRY (8:00 AM)")
            logger.info("=" * 80)

            # Check if engine is initialized
            if not self.engine:
                error_msg = "Trading engine not initialized. Call initialize() first."
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Retry orders with RETRY_PENDING status from database
            summary = self.engine.retry_pending_orders_from_db()
            logger.info(f"Pre-market retry summary: {summary}")
            task_context["summary"] = summary
            task_context["retried"] = summary.get("retried", 0)
            task_context["placed"] = summary.get("placed", 0)
            task_context["failed"] = summary.get("failed", 0)
            task_context["skipped"] = summary.get("skipped", 0)

            self.tasks_completed["premarket_retry"] = True
            logger.info("Pre-market retry completed")

    def run_premarket_amo_adjustment(self):
        """9:05 AM - Adjust AMO order quantities based on pre-market prices"""
        from src.application.services.task_execution_wrapper import execute_task

        with execute_task(
            self.user_id,
            self.db,
            "premarket_amo_adjustment",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TASK: PRE-MARKET AMO ADJUSTMENT (9:05 AM)")
            logger.info("=" * 80)

            # Check if engine is initialized
            if not self.engine:
                error_msg = "Trading engine not initialized. Call initialize() first."
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Adjust AMO order quantities based on pre-market prices
            summary = self.engine.adjust_amo_quantities_premarket()
            logger.info(f"Pre-market AMO adjustment summary: {summary}")
            task_context["summary"] = summary
            task_context["total_orders"] = summary.get("total_orders", 0)
            task_context["adjusted"] = summary.get("adjusted", 0)
            task_context["no_adjustment_needed"] = summary.get("no_adjustment_needed", 0)
            task_context["price_unavailable"] = summary.get("price_unavailable", 0)
            task_context["modification_failed"] = summary.get("modification_failed", 0)
            task_context["skipped_not_enabled"] = summary.get("skipped_not_enabled", 0)

            self.tasks_completed["premarket_amo_adjustment"] = True
            logger.info("Pre-market AMO adjustment completed")

    def run_sell_monitor(self):
        """9:15 AM - Place sell orders and start monitoring (runs continuously)"""
        from src.application.services.task_execution_wrapper import execute_task

        # Respect stop request when used from unified service (do not place orders if stopped)
        if not getattr(self, "running", True) or getattr(self, "shutdown_requested", False):
            return

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
                            # Phase 4.1: Use PriceService for centralized subscription management
                            from modules.kotak_neo_auto_trader.services import get_price_service

                            price_service = get_price_service(
                                live_price_manager=self.price_cache, enable_caching=True
                            )
                            subscribed = price_service.subscribe_to_symbols(
                                symbols, service_id="sell_monitor"
                            )
                            if subscribed:
                                logger.debug(
                                    f"Subscribed to {len(symbols)} symbols for sell monitoring: "
                                    f"{', '.join(symbols)} (via PriceService - deduplication enabled)"
                                )
                            else:
                                # Fallback to direct subscription if PriceService fails
                                self.price_cache.subscribe(symbols)
                                logger.debug(
                                    f"Subscribed to {len(symbols)} symbols for sell monitoring: {', '.join(symbols)}"
                                )

                    except Exception as e:
                        logger.debug(f"Failed to subscribe to symbols: {e}")

                # Phase 4.2: Warm cache for open positions (pre-market warm-up)
                try:
                    from modules.kotak_neo_auto_trader.services import (
                        get_indicator_service,
                        get_price_service,
                    )

                    open_positions = self.sell_manager.get_open_positions()
                    if open_positions:
                        price_service = get_price_service(
                            live_price_manager=self.price_cache, enable_caching=True
                        )
                        indicator_service = get_indicator_service(
                            price_service=price_service, enable_caching=True
                        )

                        # Warm price and indicator caches
                        price_warm_stats = price_service.warm_cache_for_positions(open_positions)
                        indicator_warm_stats = indicator_service.warm_cache_for_positions(
                            open_positions
                        )
                        logger.info(
                            f"Cache warming complete: Price ({price_warm_stats['warmed']}/{len(open_positions)}), "
                            f"Indicators ({indicator_warm_stats['warmed']}/{len(open_positions)})"
                        )
                except Exception as e:
                    logger.debug(f"Cache warming failed (non-critical): {e}")

                # Skip placement if stop was requested during cache warming
                if not getattr(self, "running", True) or getattr(self, "shutdown_requested", False):
                    return

                # Place sell orders at market open
                orders_placed = self.sell_manager.run_at_market_open()
                logger.info(f"Placed {orders_placed} sell orders")
                task_context["orders_placed"] = orders_placed

                # Phase 4: Load and register buy orders at market open
                if self.unified_order_monitor:
                    try:
                        logger.info("Loading pending AMO buy orders from database...")
                        loaded_count = self.unified_order_monitor.load_pending_buy_orders()
                        logger.info(f"Loaded {loaded_count} pending AMO buy orders")

                        # Register loaded buy orders with OrderStateManager
                        if loaded_count > 0:
                            registered_count = (
                                self.unified_order_monitor.register_buy_orders_with_state_manager()
                            )
                            task_context["buy_orders_loaded"] = loaded_count
                            task_context["buy_orders_registered"] = registered_count
                    except Exception as e:
                        logger.error(f"Error loading/registering buy orders at market open: {e}")

                self.tasks_completed["sell_monitor_started"] = True

        # Monitor and update every minute during market hours (no DB logging for continuous monitoring)
        if self.is_market_hours():
            try:
                # Phase 2: Use unified order monitor if available, otherwise fallback to sell_manager
                if self.unified_order_monitor:
                    stats = self.unified_order_monitor.monitor_all_orders()
                    logger.debug(
                        f"Unified monitor: {stats.get('checked', 0)} checked, "
                        f"{stats.get('updated', 0)} updated, {stats.get('executed', 0)} executed, "
                        f"{stats.get('rejected', 0)} rejected, {stats.get('cancelled', 0)} cancelled, "
                        f"{stats.get('new_holdings_tracked', 0)} new holdings tracked"
                    )
                elif self.sell_manager:
                    stats = self.sell_manager.monitor_and_update()
                    logger.debug(
                        f"Sell monitor: {stats['checked']} checked, {stats['updated']} updated, {stats['executed']} executed"
                    )
            except Exception as e:
                logger.error(f"Order monitor update failed: {e}")
        else:
            # Phase 4: Market closed - stop tracking buy orders (they'll be picked up next day)
            # Only log once per minute to avoid spam
            now = datetime.now()
            if now.minute == 0 and now.second < 30:
                if self.unified_order_monitor and self.unified_order_monitor.active_buy_orders:
                    logger.info(
                        f"Market closed - {len(self.unified_order_monitor.active_buy_orders)} "
                        "buy orders still pending (will be tracked next market open)"
                    )

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

        # Log entry point to verify method is being called
        self.logger.info("run_buy_orders() method called", action="run_buy_orders")

        summary = {
            "attempted": 0,
            "placed": 0,
            "retried": 0,
            "failed_balance": 0,
            "skipped_portfolio_limit": 0,
            "skipped_duplicates": 0,
            "skipped_missing_data": 0,
            "skipped_invalid_qty": 0,
            "ticker_attempts": [],
        }

        self.logger.info("About to enter execute_task context", action="run_buy_orders")
        with execute_task(
            self.user_id,
            self.db,
            "buy_orders",
            self.logger,
            track_execution=not self.skip_execution_tracking,
        ) as task_context:
            # Use self.logger for user-scoped logging
            self.logger.info("Inside execute_task context", action="run_buy_orders")
            self.logger.info("", action="run_buy_orders")
            self.logger.info("=" * 80, action="run_buy_orders")
            self.logger.info("TASK: PLACE BUY ORDERS (4:05 PM)", action="run_buy_orders")
            self.logger.info("=" * 80, action="run_buy_orders")

            # Check if engine is initialized
            if not self.engine:
                error_msg = "Trading engine not initialized. Call initialize() first."
                self.logger.error(error_msg, action="run_buy_orders")
                raise RuntimeError(error_msg)

            self.logger.info("Loading latest recommendations...", action="run_buy_orders")
            recs = self.engine.load_latest_recommendations()
            self.logger.info(
                f"Loaded {len(recs)} recommendations for buy orders", action="run_buy_orders"
            )
            if recs:
                self.logger.info(
                    f"Processing {len(recs)} recommendations...", action="run_buy_orders"
                )
                try:
                    # Place fresh entry orders
                    summary = self.engine.place_new_entries(recs)
                    self.logger.info(f"Buy orders summary: {summary}", action="run_buy_orders")
                    # Log detailed summary
                    self.logger.info(
                        f"  - Attempted: {summary.get('attempted', 0)}, "
                        f"Placed: {summary.get('placed', 0)}, "
                        f"Retried: {summary.get('retried', 0)}, "
                        f"Failed (balance): {summary.get('failed_balance', 0)}, "
                        f"Skipped: {summary.get('skipped_duplicates', 0) + summary.get('skipped_portfolio_limit', 0) + summary.get('skipped_missing_data', 0) + summary.get('skipped_invalid_qty', 0)}",
                        action="run_buy_orders",
                    )
                except OrderPlacementError as exc:
                    # OrderPlacementError should no longer be raised (changed to continue)
                    # But keep this handler for backward compatibility
                    error_msg = (
                        f"Unexpected OrderPlacementError: {exc}. "
                        "This should not occur with current implementation."
                    )
                    self.logger.error(error_msg, action="run_buy_orders")
                    task_context["recommendations_count"] = len(recs)
                    task_context["error"] = str(exc)
                    if getattr(exc, "symbol", None):
                        task_context["failed_symbol"] = exc.symbol
                    # Don't raise - let the summary be returned
                    summary = {"attempted": 0, "placed": 0, "ticker_attempts": []}

                task_context["recommendations_count"] = len(recs)
                task_context["summary"] = summary
            else:
                self.logger.warning(
                    "No buy recommendations to place - check if analysis has run and signals exist in database/CSV",
                    action="run_buy_orders",
                )
                self.logger.warning(
                    "This could mean: (1) No analysis results available, (2) No buy/strong_buy signals, (3) Signals table is empty",
                    action="run_buy_orders",
                )
                task_context["recommendations_count"] = 0
                task_context["summary"] = summary  # Return empty summary

            # Check and place re-entry orders (regardless of whether there are fresh entry recommendations)
            # Re-entry should be checked independently of fresh entry orders
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

        return summary

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

            # EOD sync: Sync TRADED status from positions/orders
            # This ensures all signals are correctly marked before next trading day
            try:
                from src.infrastructure.persistence.signals_repository import (
                    SignalsRepository,
                )

                signals_repo = SignalsRepository(self.db, user_id=self.user_id)
                synced_count = signals_repo.sync_traded_status_from_positions_and_orders(
                    user_id=self.user_id
                )
                if synced_count > 0:
                    logger.info(
                        f"EOD sync: Marked {synced_count} signal(s) as TRADED (user {self.user_id})"
                    )
                    task_context["synced_signals"] = synced_count
            except Exception as e:
                logger.warning(f"EOD sync failed (user {self.user_id}): {e}")

            # Run EOD cleanup if available
            if hasattr(self.engine, "eod_cleanup") and self.engine.eod_cleanup:
                self.engine.eod_cleanup.run_eod_cleanup()
                logger.info("EOD cleanup completed")
                task_context["eod_cleanup_ran"] = True
            else:
                logger.info("EOD cleanup not configured")
                task_context["eod_cleanup_ran"] = False

            # Reset ALL task completion flags for next day
            # (eod_cleanup included — otherwise it stays True forever and
            #  never runs again on subsequent days, blocking all resets)
            logger.info("EOD cleanup completed - resetting for next trading day")
            self.tasks_completed["analysis"] = False
            self.tasks_completed["buy_orders"] = False
            self.tasks_completed["eod_cleanup"] = False
            self.tasks_completed["premarket_retry"] = False
            self.tasks_completed["premarket_amo_adjustment"] = False
            self.tasks_completed["sell_monitor_started"] = False
            task_context["tasks_reset"] = True
            logger.info("Service ready for next trading day")

    def _is_task_running(self, task_name: str) -> bool:
        """
        Check if a task is currently running/queued in THIS TradingService instance.

        Important: Unified TradingService task execution is not recorded to DB until completion
        (see execute_task / ServiceTaskRepository). So DB-based "running" checks won't work here.
        We must guard using in-memory futures to avoid executor queue buildup.

        Args:
            task_name: Name of the task to check

        Returns:
            True if task is running, False otherwise
        """
        with self._task_futures_lock:
            fut = self._task_futures.get(task_name)
            if fut is None:
                return False
            # concurrent.futures.Future API
            try:
                return not fut.done()
            except Exception:
                # If future object is unexpected, fail open (assume not running)
                return False

    def _cleanup_stale_scheduler_lock(self) -> bool:
        """
        Clean up stale table-based lock held by dead thread.

        Strategy:
        1. Delete expired locks (auto-cleanup)
        2. Delete lock for this user_id if it exists (force cleanup)
        3. Log detailed information for debugging

        Returns:
            True if lock was successfully cleaned up, False otherwise
        """
        if not self.db or not self.user_id:
            return True

        try:
            from src.infrastructure.db.models import SchedulerLock
            from src.infrastructure.db.timezone_utils import ist_now

            self.logger.debug(
                f"Attempting to clean up stale scheduler lock for user {self.user_id}",
                action="scheduler",
            )

            # Delete expired locks and locks for this user
            deleted = (
                self.db.query(SchedulerLock)
                .filter(
                    (SchedulerLock.user_id == self.user_id) | (SchedulerLock.expires_at < ist_now())
                )
                .delete()
            )
            self.db.commit()

            if deleted > 0:
                self.logger.info(
                    f"Successfully cleaned up {deleted} stale lock(s) for user {self.user_id}",
                    action="scheduler",
                )
                return True
            else:
                self.logger.debug(
                    f"No stale locks found for user {self.user_id}",
                    action="scheduler",
                )
                return True  # No locks to clean up is also success
        except Exception as e:
            self.logger.warning(
                f"Failed to cleanup stale lock for user {self.user_id}: {e}",
                action="scheduler",
            )
            self.db.rollback()
            return False

    def _try_acquire_scheduler_lock(self) -> bool:
        """
        Ensure only ONE unified TradingService scheduler loop runs per user.

        Why this is needed:
        - You can end up with multiple unified service instances for the same user (e.g., restart/race)
        - With max_workers=1, a long-running task causes subsequent submissions to queue
        - Those queued tasks then "time out" and are "cancelled before execution" repeatedly
          (exactly what you saw for sell_monitor and analysis).

        Implementation:
        - Uses table-based locking instead of PostgreSQL advisory locks (which are problematic
          with connection pooling). This works with any database and any connection.
        - Retry logic handles stale locks from dead threads
        """
        if not self.db or not self.user_id:
            return True

        try:
            import uuid
            from datetime import timedelta

            from src.infrastructure.db.models import SchedulerLock
            from src.infrastructure.db.timezone_utils import ist_now

            # Generate unique lock ID for this instance
            lock_id = str(uuid.uuid4())

            # Lock expires after 5 minutes (stale locks auto-cleanup)
            expires_at = ist_now() + timedelta(minutes=5)

            # Clean up stale locks first (expired locks)
            try:
                self.db.query(SchedulerLock).filter(SchedulerLock.expires_at < ist_now()).delete()
                self.db.commit()
            except Exception:
                self.db.rollback()

            # Try to acquire lock: INSERT if user_id doesn't exist
            try:
                # Use INSERT ... ON CONFLICT (PostgreSQL) or try/except (SQLite)
                bind = getattr(self.db, "bind", None)
                dialect_name = getattr(getattr(bind, "dialect", None), "name", "")

                if dialect_name == "postgresql":
                    from sqlalchemy import text  # noqa: PLC0415

                    # PostgreSQL: Use INSERT ... ON CONFLICT DO NOTHING
                    result = self.db.execute(
                        text(
                            """
                            INSERT INTO scheduler_lock (user_id, locked_at, lock_id, expires_at, created_at)
                            VALUES (:user_id, :locked_at, :lock_id, :expires_at, :created_at)
                            ON CONFLICT (user_id) DO NOTHING
                            RETURNING lock_id
                        """
                        ),
                        {
                            "user_id": self.user_id,
                            "locked_at": ist_now(),
                            "lock_id": lock_id,
                            "expires_at": expires_at,
                            "created_at": ist_now(),
                        },
                    )
                    row = result.fetchone()
                    if row:
                        # Lock acquired
                        self.db.commit()
                        self._scheduler_lock_id = lock_id
                        self._scheduler_lock_acquired = True
                        self.logger.info(
                            "Acquired scheduler lock (single-instance enforced)",
                            action="scheduler",
                        )
                        return True
                    else:
                        # Lock already held by another instance
                        self.db.rollback()
                        self.logger.warning(
                            f"Could not acquire scheduler lock for user {self.user_id}. "
                            "Another scheduler instance may be running.",
                            action="scheduler",
                        )
                        return False
                else:
                    # SQLite or other: Use try/except
                    try:
                        lock = SchedulerLock(
                            user_id=self.user_id,
                            locked_at=ist_now(),
                            lock_id=lock_id,
                            expires_at=expires_at,
                        )
                        self.db.add(lock)
                        self.db.commit()
                        self._scheduler_lock_id = lock_id
                        self._scheduler_lock_acquired = True
                        self.logger.info(
                            "Acquired scheduler lock (single-instance enforced)",
                            action="scheduler",
                        )
                        return True
                    except Exception:
                        # Lock already exists (unique constraint violation)
                        self.db.rollback()
                        self.logger.warning(
                            f"Could not acquire scheduler lock for user {self.user_id}. "
                            "Another scheduler instance may be running.",
                            action="scheduler",
                        )
                        return False
            except Exception as e:
                self.db.rollback()
                # Log but don't fail - allow scheduler to run
                self.logger.warning(
                    f"Failed to acquire scheduler lock (continuing without lock): {e}",
                    action="scheduler",
                )
                self._scheduler_lock_acquired = True
                return True
        except Exception as e:
            # Fail open (don't block startup if DB is weird), but log loudly.
            self.logger.warning(
                f"Failed to acquire scheduler lock (continuing without lock): {e}",
                action="scheduler",
            )
            self._scheduler_lock_acquired = True
            return True

    def _release_scheduler_lock(self) -> None:
        """Release table-based scheduler lock (best-effort)."""
        if not self.db or not self._scheduler_lock_acquired or self._scheduler_lock_id is None:
            return
        try:
            from src.infrastructure.db.models import SchedulerLock

            # Delete lock by lock_id (only release our own lock)
            self.db.query(SchedulerLock).filter(
                SchedulerLock.lock_id == self._scheduler_lock_id
            ).delete()
            self.db.commit()
        except Exception:
            self.db.rollback()
            pass

    def _execute_task_async(self, task_func, task_name: str, timeout_seconds: int = 300):
        """
        Execute a task asynchronously with timeout to prevent blocking the scheduler loop.

        IMPORTANT: If a task times out, it may continue running in the background.
        The scheduler loop will not be blocked, but the task won't be marked as completed.
        This allows the task to be retried on the next scheduled time.

        Args:
            task_func: The task function to execute
            task_name: Name of the task for logging
            timeout_seconds: Maximum time to wait for task completion (default: 5 minutes)

        Returns:
            True if task completed successfully, False if timed out or failed
        """
        if not self.task_executor:
            # Initialize executor on first use (max_workers=1 ensures tasks run sequentially)
            self.task_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="TradingTask")

        try:
            # Guard: don't queue if previous run is still running/queued in this service instance.
            if self._is_task_running(task_name):
                self.logger.debug(
                    f"Not queuing {task_name}: previous run still running/queued",
                    action="scheduler",
                )
                return False

            self.logger.info(
                f"Starting async execution of {task_name} (timeout: {timeout_seconds}s)",
                action="scheduler",
            )
            future = self.task_executor.submit(task_func)
            # Track future so subsequent scheduler ticks won't queue duplicates.
            with self._task_futures_lock:
                self._task_futures[task_name] = future

            def _clear_future(_fut):
                # Callback runs when the future completes (in worker thread).
                with self._task_futures_lock:
                    cur = self._task_futures.get(task_name)
                    if cur is _fut:
                        self._task_futures.pop(task_name, None)

            try:
                future.add_done_callback(_clear_future)
            except Exception:
                # Non-fatal; worst case we'll clear on next submit attempt when fut.done() is True
                pass

            try:
                future.result(timeout=timeout_seconds)
                self.logger.info(f"Task {task_name} completed successfully", action="scheduler")
                return True
            except FutureTimeoutError:
                # Task timed out - it may still be running in background
                # Note: future.cancel() only works if task hasn't started, so we can't stop it now
                self.logger.error(
                    f"Task {task_name} timed out after {timeout_seconds} seconds. "
                    f"Task may continue running in background. Scheduler loop continues.",
                    action="scheduler",
                )
                # Try to cancel (will only work if task hasn't started executing)
                cancelled = future.cancel()
                if cancelled:
                    self.logger.info(
                        f"Task {task_name} was cancelled before execution", action="scheduler"
                    )
                else:
                    self.logger.warning(
                        f"Task {task_name} could not be cancelled (already executing). "
                        f"It will continue in background but won't block scheduler.",
                        action="scheduler",
                    )
                # Don't mark task as completed - allow retry on next scheduled time
                return False
            except Exception as e:
                self.logger.error(
                    f"Task {task_name} failed with error: {e}", exc_info=True, action="scheduler"
                )
                # Don't mark task as completed on failure - allow retry
                return False
        except Exception as e:
            self.logger.error(
                f"Failed to submit task {task_name} to executor: {e}",
                exc_info=True,
                action="scheduler",
            )
            return False

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
        heartbeat_counter = 0  # Track heartbeat updates

        # Try to acquire lock - if it fails, attempt cleanup of stale locks
        if not self._try_acquire_scheduler_lock():
            # Lock acquisition failed - try to clean up stale locks from dead threads
            self.logger.info(
                f"Initial lock acquisition failed for user {self.user_id}. "
                "Attempting to clean up stale locks...",
                action="scheduler",
            )
            cleaned = self._cleanup_stale_scheduler_lock()
            if cleaned:
                # Try one more time after cleanup
                if not self._try_acquire_scheduler_lock():
                    self.logger.warning(
                        f"Still cannot acquire lock for user {self.user_id} after cleanup. "
                        "Exiting scheduler. Try restarting the service.",
                        action="scheduler",
                    )
                    return
            else:
                # Cleanup didn't work - lock may be legitimately held by another instance
                self.logger.warning(
                    f"Could not clean up stale lock for user {self.user_id}. "
                    "Another scheduler instance may be running. Exiting this instance.",
                    action="scheduler",
                )
                return

        try:
            while not self.shutdown_requested:
                loop_count += 1
                try:
                    now = datetime.now()
                    current_time = now.time()
                    current_minute = now.minute

                    # Log scheduler activity more frequently for better visibility
                    # Log first 10 iterations, then every 10 iterations
                    if loop_count <= 10 or loop_count % 10 == 0:
                        self.logger.info(
                            f"Scheduler loop iteration #{loop_count} at {now.strftime('%H:%M:%S')}",
                            action="scheduler",
                        )

                    # Run tasks only once per minute (on trading days only)
                    if current_minute != last_minute:
                        last_minute = current_minute
                        logger.debug(
                            f"Scheduler check at {current_time.strftime('%H:%M:%S')} (loop #{loop_count})"
                        )

                        # Only run tasks on trading days (Mon-Fri)
                        if self.is_trading_day():
                            logger.debug("  -> Trading day detected - checking tasks...")

                            # Pre-market retry (uses DB schedule) - 5 minute timeout
                            premarket_schedule = self._schedule_manager.get_schedule(
                                "premarket_retry"
                            )
                            if premarket_schedule and premarket_schedule.enabled:
                                premarket_time = premarket_schedule.schedule_time
                                if self.should_run_task(
                                    "premarket_retry",
                                    dt_time(premarket_time.hour, premarket_time.minute),
                                ):
                                    self._execute_task_async(
                                        self.run_premarket_retry,
                                        "premarket_retry",
                                        timeout_seconds=300,  # 5 minutes
                                    )

                            # Pre-market AMO quantity adjustment (hardcoded 9:05 AM - 5 mins after premarket retry) - 2 minute timeout
                            if self.should_run_task("premarket_amo_adjustment", dt_time(9, 5)):
                                self._execute_task_async(
                                    self.run_premarket_amo_adjustment,
                                    "premarket_amo_adjustment",
                                    timeout_seconds=120,  # 2 minutes
                                )

                            # Sell monitoring (continuous, uses DB schedule) - 60 second timeout
                            sell_schedule = self._schedule_manager.get_schedule("sell_monitor")
                            if (
                                sell_schedule
                                and sell_schedule.enabled
                                and sell_schedule.is_continuous
                            ):
                                start_time = sell_schedule.schedule_time
                                end_time = sell_schedule.end_time or dt_time(15, 30)
                                if current_time >= dt_time(
                                    start_time.hour, start_time.minute
                                ) and current_time <= dt_time(end_time.hour, end_time.minute):
                                    # Check if sell_monitor is already running before queuing
                                    if self._is_task_running("sell_monitor"):
                                        self.logger.debug(
                                            "Skipping sell_monitor - previous execution still running",
                                            action="scheduler",
                                        )
                                    else:
                                        self._execute_task_async(
                                            self.run_sell_monitor,
                                            "sell_monitor",
                                            timeout_seconds=60,  # 1 minute (should be quick)
                                        )

                            # Analysis (uses DB schedule) - 30 minute timeout
                            analysis_schedule = self._schedule_manager.get_schedule("analysis")
                            if analysis_schedule and analysis_schedule.enabled:
                                analysis_time = analysis_schedule.schedule_time
                                if self.should_run_task(
                                    "analysis", dt_time(analysis_time.hour, analysis_time.minute)
                                ):
                                    self._execute_task_async(
                                        self.run_analysis,
                                        "analysis",
                                        timeout_seconds=1800,  # 30 minutes
                                    )
                            elif not analysis_schedule:
                                logger.debug("Analysis schedule not found in DB")

                            # Buy orders (uses DB schedule) - 10 minute timeout
                            buy_schedule = self._schedule_manager.get_schedule("buy_orders")
                            if buy_schedule and buy_schedule.enabled:
                                buy_time = buy_schedule.schedule_time
                                if self.should_run_task(
                                    "buy_orders", dt_time(buy_time.hour, buy_time.minute)
                                ):
                                    self._execute_task_async(
                                        self.run_buy_orders,
                                        "buy_orders",
                                        timeout_seconds=600,  # 10 minutes
                                    )
                            elif not buy_schedule:
                                logger.debug("Buy orders schedule not found in DB")

                            # EOD cleanup (uses DB schedule) - 5 minute timeout
                            eod_schedule = self._schedule_manager.get_schedule("eod_cleanup")
                            if eod_schedule and eod_schedule.enabled:
                                eod_time = eod_schedule.schedule_time
                                if self.should_run_task(
                                    "eod_cleanup", dt_time(eod_time.hour, eod_time.minute)
                                ):
                                    self._execute_task_async(
                                        self.run_eod_cleanup,
                                        "eod_cleanup",
                                        timeout_seconds=300,  # 5 minutes
                                    )
                            elif not eod_schedule:
                                logger.debug("EOD cleanup schedule not found in DB")

                            # Log task status once per hour (at minute 0) for debugging
                            if current_minute == 0:
                                completed = [k for k, v in self.tasks_completed.items() if v]
                                pending = [k for k, v in self.tasks_completed.items() if not v]
                                self.logger.info(
                                    f"Hourly task status - completed: {completed or 'none'}, "
                                    f"pending: {pending or 'none'}",
                                    action="scheduler",
                                )

                    # Update heartbeat every minute using thread-local session
                    # Use retry logic for reliability (handles database lock contention)
                    heartbeat_update_successful = False
                    max_heartbeat_retries = 3
                    heartbeat_retry_delays = [0.1, 0.2, 0.4]

                    from sqlalchemy.exc import OperationalError  # noqa: PLC0415

                    self.logger.debug(
                        f"Attempting heartbeat update (user {self.user_id}, loop {loop_count})",
                        action="scheduler",
                    )

                    for retry_attempt in range(max_heartbeat_retries):
                        try:
                            # Create a fresh repository instance to ensure clean state
                            from src.infrastructure.persistence.service_status_repository import (
                                ServiceStatusRepository,
                            )

                            status_repo = ServiceStatusRepository(self.db)
                            status_repo.update_heartbeat(self.user_id)
                            self.db.commit()
                            heartbeat_update_successful = True
                            if retry_attempt > 0:
                                self.logger.info(
                                    f"Heartbeat update succeeded on retry attempt {retry_attempt + 1}",
                                    action="scheduler",
                                )
                            break
                        except OperationalError as op_err:
                            self.db.rollback()
                            # Expire all objects to ensure fresh state
                            self.db.expire_all()
                            is_locked_error = "database is locked" in str(op_err).lower()

                            self.logger.debug(
                                f"Heartbeat update attempt {retry_attempt + 1}/{max_heartbeat_retries} failed: "
                                f"{op_err} (is_locked: {is_locked_error})",
                                action="scheduler",
                            )

                            if retry_attempt < max_heartbeat_retries - 1 and is_locked_error:
                                # Retry on locked errors with exponential backoff
                                delay = heartbeat_retry_delays[retry_attempt]
                                self.logger.debug(
                                    f"Retrying heartbeat update after {delay}s delay",
                                    action="scheduler",
                                )
                                time.sleep(delay)
                                continue
                            else:
                                # Final failure - log error
                                if not is_locked_error:
                                    self.logger.warning(
                                        f"Failed to update heartbeat after {retry_attempt + 1} attempts: {op_err}",
                                        action="scheduler",
                                    )
                                else:
                                    self.logger.warning(
                                        f"Failed to update heartbeat after {max_heartbeat_retries} attempts "
                                        f"(database locked, all retries exhausted)",
                                        action="scheduler",
                                    )
                                break
                        except Exception as e:
                            self.db.rollback()
                            self.db.expire_all()
                            # Non-OperationalError - don't retry
                            self.logger.warning(
                                f"Failed to update heartbeat (non-retryable error): {e}",
                                action="scheduler",
                            )
                            break

                    if heartbeat_update_successful:
                        # Log heartbeat more frequently for better visibility
                        heartbeat_counter += 1
                        # Log every 10 iterations (5 minutes) instead of every 300 iterations
                        if heartbeat_counter == 1 or heartbeat_counter % 10 == 0:
                            try:
                                self.logger.info(
                                    f"💓 Scheduler heartbeat (running for {heartbeat_counter // 2} minutes, iteration #{loop_count})",
                                    action="scheduler",
                                )
                            except Exception:
                                # Logger might fail - continue without logging
                                pass
                    else:
                        self.logger.warning(
                            f"Heartbeat update failed for loop {loop_count} - service is running but heartbeat not updated",
                            action="scheduler",
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
        finally:
            self._release_scheduler_lock()

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

            # Shutdown task executor
            if self.task_executor:
                try:
                    self.task_executor.shutdown(wait=False, cancel_futures=True)
                    logger.info("Task executor shut down")
                except Exception as e:
                    logger.warning(f"Error shutting down task executor: {e}")

            # Logout from session
            if self.auth:
                self.auth.logout()
                logger.info("Logged out successfully")

            logger.info("Service stopped gracefully")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def run(self):
        """
        Main entry point - Runs continuously in background thread.

        CRITICAL: Creates its own database session to avoid thread-safety issues.
        SQLAlchemy sessions are NOT thread-safe and cannot be shared across threads.
        """
        # Create a new database session for this thread
        from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415

        thread_db = SessionLocal()

        try:
            # Recreate logger with thread-local database session
            from src.infrastructure.logging import get_user_logger  # noqa: PLC0415

            self.logger = get_user_logger(
                user_id=self.user_id, db=thread_db, module="TradingService"
            )

            # Update self.db to use thread-local session
            self.db = thread_db

            # Also update schedule manager to use thread-local session
            from src.application.services.schedule_manager import ScheduleManager  # noqa: PLC0415

            self._schedule_manager = ScheduleManager(thread_db)
            self.logger.info("Schedule manager recreated with thread-local session", action="run")

            self.logger.info("Setting up signal handlers...", action="run")
            try:
                self.setup_signal_handlers()
                self.logger.info("Signal handlers setup complete", action="run")
            except Exception as e:
                # Signal handlers may fail in background threads (expected on some platforms)
                # This is non-critical - service can still be stopped via shutdown_requested flag
                self.logger.warning(
                    f"Signal handlers setup failed (non-critical in background thread): {e}",
                    action="run",
                )
                # Continue anyway - signal handlers are not required for service operation

            # Initialize service (single login)
            self.logger.info("Starting service initialization...", action="run")
            try:
                if not self.initialize():
                    self.logger.error(
                        "Failed to initialize service - service will exit", action="run"
                    )
                    return
            except Exception as e:
                self.logger.error(
                    f"Exception during service initialization: {e}",
                    exc_info=True,
                    action="run",
                )
                return

            self.logger.info("Initialization complete - entering scheduler loop...", action="run")

            try:
                # Run scheduler continuously
                self.run_scheduler()
            except Exception as e:
                self.logger.error(f"Fatal error in scheduler: {e}", exc_info=True, action="run")
                import traceback

                traceback.print_exc()
            finally:
                # Always cleanup on exit
                self.logger.info("Entering shutdown sequence...", action="run")
                self.shutdown()
        finally:
            # Update database status to False when thread exits (CRITICAL - must succeed)
            # This ensures database reflects actual service state even if thread
            # crashes/exits unexpectedly
            # Use aggressive retry logic with emergency session fallback for reliability
            self.logger.info(
                "Updating service status to stopped in finally block",
                action="run",
            )

            max_exit_retries = 5
            exit_retry_delays = [0.2, 0.5, 1.0, 2.0, 5.0]
            exit_status_updated = False

            from sqlalchemy.exc import OperationalError  # noqa: PLC0415

            # Try with existing thread_db first (up to 5 retries)
            self.logger.debug(
                f"Attempting service status update with thread_db (user {self.user_id})",
                action="run",
            )
            for retry_attempt in range(max_exit_retries):
                try:
                    from src.infrastructure.persistence.service_status_repository import (
                        ServiceStatusRepository,
                    )

                    status_repo = ServiceStatusRepository(thread_db)
                    status_repo.update_running(self.user_id, running=False)
                    status_repo.update_heartbeat(self.user_id)
                    thread_db.commit()
                    exit_status_updated = True
                    self.logger.info(
                        f"Successfully updated service status to stopped on thread exit "
                        f"(attempt {retry_attempt + 1})",
                        action="run",
                    )
                    break
                except OperationalError as op_err:
                    thread_db.rollback()
                    thread_db.expire_all()
                    is_locked_error = "database is locked" in str(op_err).lower()

                    self.logger.debug(
                        f"Service status update attempt {retry_attempt + 1}/{max_exit_retries} failed: "
                        f"{op_err} (is_locked: {is_locked_error})",
                        action="run",
                    )

                    if retry_attempt < max_exit_retries - 1:
                        # Retry with increasing delays
                        delay = exit_retry_delays[retry_attempt]
                        self.logger.debug(
                            f"Retrying service status update after {delay}s delay",
                            action="run",
                        )
                        time.sleep(delay)
                        continue
                    else:
                        # Final failure with thread_db - will try emergency session below
                        self.logger.warning(
                            f"Service status update with thread_db failed after {max_exit_retries} attempts",
                            action="run",
                        )
                except Exception as e:
                    thread_db.rollback()
                    thread_db.expire_all()
                    # Non-OperationalError - try emergency session immediately
                    self.logger.warning(
                        f"Service status update failed with non-OperationalError: {e}. "
                        "Trying emergency session...",
                        action="run",
                    )
                    break

            # If exit status update failed, try with a fresh session (emergency fallback)
            if not exit_status_updated:
                self.logger.warning(
                    "Thread_db status update failed - attempting emergency session",
                    action="run",
                )
                try:
                    from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415

                    emergency_db = SessionLocal()
                    self.logger.debug(
                        "Created emergency session for service status update",
                        action="run",
                    )
                    try:
                        from src.infrastructure.persistence.service_status_repository import (
                            ServiceStatusRepository,
                        )

                        emergency_repo = ServiceStatusRepository(emergency_db)
                        emergency_repo.update_running(self.user_id, running=False)
                        emergency_repo.update_heartbeat(self.user_id)
                        emergency_db.commit()
                        exit_status_updated = True
                        self.logger.info(
                            "Successfully updated service status using emergency session",
                            action="run",
                        )
                    except Exception as e2:
                        emergency_db.rollback()
                        self.logger.error(
                            f"CRITICAL: Emergency service status update failed: {e2}",
                            action="run",
                        )
                    finally:
                        try:
                            emergency_db.close()
                            self.logger.debug("Emergency session closed", action="run")
                        except Exception:  # noqa: S110
                            pass  # Ignore close errors
                except Exception as e3:
                    self.logger.error(
                        f"CRITICAL: Could not create emergency session: {e3}",
                        action="run",
                    )

            # If still not updated, log critical error (but don't fail - cleanup must continue)
            if not exit_status_updated:
                self.logger.error(
                    "CRITICAL: Service status could not be updated on exit. "
                    "Database may show stale 'running' status!",
                    action="run",
                )
            else:
                self.logger.debug(
                    "Service status update completed successfully in finally block",
                    action="run",
                )

            # PERFORMANCE FIX: Clean up thread-local session to prevent "idle in transaction" leaks
            # This matches the pattern in get_session() to ensure proper transaction lifecycle:
            # - Rollback any pending transaction (safe even if already committed)
            # - Always close the session to return connection to pool
            # This prevents connection leaks when exceptions occur during service execution
            self.logger.debug("Cleaning up thread-local session", action="run")

            # Rollback any pending transaction (safe even if already committed/closed)
            # This prevents "idle in transaction" state if an exception occurred
            try:
                thread_db.rollback()
                self.logger.debug("Thread-local session rolled back", action="run")
            except Exception:
                # Ignore rollback errors (session may already be closed/rolled back)
                # This is safe - rollback is idempotent and won't cause harm
                pass

            # Always close the session to return connection to pool
            # This ensures connections are never left open, preventing connection exhaustion
            try:
                thread_db.close()
                self.logger.debug("Thread-local session closed", action="run")
            except Exception:
                # Ignore close errors if session is in bad state
                # This is safe - if close fails, the connection will be recycled by the pool
                pass


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
