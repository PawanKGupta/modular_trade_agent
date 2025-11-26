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
            db_session: SQLAlchemy database session
            broker_creds: Decrypted broker credentials dict (None for paper trading mode)
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
        self.unified_order_monitor = None  # Phase 2: Unified order monitor
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
            "premarket_amo_adjustment": False,
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
            # For buy_orders task, WebSocket is not needed (AMO orders don't need real-time prices)
            # Skip WebSocket initialization to avoid blocking - buy orders use yfinance for prices
            logger.info(
                "Skipping WebSocket initialization for buy_orders (not needed for AMO orders)"
            )
            self.price_cache = None
            self.scrip_master = None

            # Update portfolio with price manager for WebSocket LTP access
            if self.engine.portfolio and self.price_cache:
                self.engine.portfolio.price_manager = self.price_cache

            # Initialize sell order manager (will be started at market open)
            # For buy_orders task, this is not needed, but initialize it anyway for consistency
            try:
                logger.info("Initializing sell order manager...")
                # Pass positions_repo and user_id if available for direct DB updates
                positions_repo = (
                    self.engine.positions_repo if hasattr(self.engine, "positions_repo") else None
                )
                user_id = self.user_id
                # Phase 3.2: Pass OrderStatusVerifier to SellOrderManager for shared results
                order_verifier = (
                    self.engine.order_verifier
                    if self.engine and hasattr(self.engine, "order_verifier")
                    else None
                )
                self.sell_manager = SellOrderManager(
                    self.auth,
                    price_manager=self.price_cache,
                    positions_repo=positions_repo,
                    user_id=user_id,
                    order_verifier=order_verifier,  # Phase 3.2: Share OrderStatusVerifier results
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
                    logger.info("Unified order monitor initialized")
                except Exception as e:
                    logger.warning(f"Unified order monitor initialization failed: {e}")
                    self.unified_order_monitor = None
            except Exception as e:
                logger.warning(
                    f"Sell order manager initialization failed (non-critical for buy orders): {e}"
                )
                self.sell_manager = None
                self.unified_order_monitor = None

            # Subscribe to open positions immediately to avoid reconnect loops
            # For buy_orders task, this is not needed (AMO orders don't need real-time prices)
            # Skip it to avoid blocking
            logger.info("Skipping position subscription for buy_orders (not needed for AMO orders)")
            # try:
            #     self._subscribe_to_open_positions()
            # except Exception as e:
            #     logger.warning(f"Position subscription failed (non-critical for buy orders): {e}")

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

        # Allow 1 minute window for task execution
        time_diff = (now.hour * 60 + now.minute) - (
            scheduled_time.hour * 60 + scheduled_time.minute
        )
        return 0 <= time_diff < 2  # Run if within 2 minutes of scheduled time

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
                        f"{stats.get('rejected', 0)} rejected, {stats.get('cancelled', 0)} cancelled"
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
            self.tasks_completed["premarket_amo_adjustment"] = False
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
                        logger.debug("  -> Trading day detected - checking tasks...")
                        # 9:00 AM - Pre-market retry
                        if self.should_run_task("premarket_retry", dt_time(9, 0)):
                            self.run_premarket_retry()

                        # 9:05 AM - Pre-market AMO quantity adjustment
                        if self.should_run_task("premarket_amo_adjustment", dt_time(9, 5)):
                            self.run_premarket_amo_adjustment()

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
