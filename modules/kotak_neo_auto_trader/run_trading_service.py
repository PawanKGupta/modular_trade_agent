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

import sys
import time
import signal
import argparse
from pathlib import Path
from datetime import datetime, time as dt_time
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

try:
    from .auth import KotakNeoAuth
    from .sell_engine import SellOrderManager
    from .auto_trade_engine import AutoTradeEngine
    from .orders import KotakNeoOrders
    from .portfolio import KotakNeoPortfolio
    from .scrip_master import KotakNeoScripMaster
    from .live_price_cache import LivePriceCache
    from .storage import cleanup_expired_failed_orders
    from . import config
    from .utils.service_conflict_detector import prevent_service_conflict
except ImportError:
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
    from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
    from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache
    from modules.kotak_neo_auto_trader.storage import cleanup_expired_failed_orders
    from modules.kotak_neo_auto_trader import config
    from modules.kotak_neo_auto_trader.utils.service_conflict_detector import prevent_service_conflict


class TradingService:
    """
    Unified trading service that runs all tasks with single persistent session
    """
    
    def __init__(self, env_file: str = "modules/kotak_neo_auto_trader/kotak_neo.env"):
        """Initialize trading service"""
        self.env_file = env_file
        self.auth: Optional[KotakNeoAuth] = None
        self.engine: Optional[AutoTradeEngine] = None
        self.sell_manager: Optional[SellOrderManager] = None
        self.price_cache: Optional[LivePriceCache] = None
        self.scrip_master: Optional[KotakNeoScripMaster] = None
        self.running = False
        self.shutdown_requested = False
        
        # Task execution flags (reset daily)
        self.tasks_completed = {
            'analysis': False,
            'buy_orders': False,
            'eod_cleanup': False,
            'premarket_retry': False,
            'sell_monitor_started': False,
            'position_monitor': {}  # Track hourly runs
        }
        
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
            logger.info("Authenticating with Kotak Neo...")
            self.auth = KotakNeoAuth(self.env_file)
            
            if not self.auth.login():
                logger.error("Authentication failed")
                return False
            
            logger.info("Authentication successful - session active for the day")
            
            # Initialize trading engine
            logger.info("Initializing trading engine...")
            self.engine = AutoTradeEngine(env_file=self.env_file, auth=self.auth)
            
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
    
    def _initialize_live_prices(self):
        """
        Initialize real-time price feed via WebSocket
        
        Creates:
        - Scrip master for symbol/token mapping
        - LivePriceCache for WebSocket price streaming
        """
        try:
            # Load scrip master
            logger.info("Loading scrip master...")
            self.scrip_master = KotakNeoScripMaster(
                auth_client=self.auth.client,
                exchanges=['NSE']
            )
            self.scrip_master.load_scrip_master(force_download=False)
            logger.info("✅ Scrip master loaded")
            
            # Initialize price cache with WebSocket
            logger.info("Starting WebSocket price feed...")
            self.price_cache = LivePriceCache(
                auth_client=self.auth.client,
                scrip_master=self.scrip_master,
                stale_threshold_seconds=60,
                reconnect_delay_seconds=5
            )
            
            # Start WebSocket service
            self.price_cache.start()
            logger.info("✅ WebSocket price feed started")
            
            # Wait for connection to be established before subscribing
            logger.info("Waiting for WebSocket connection...")
            if self.price_cache.wait_for_connection(timeout=10):
                logger.info("✅ WebSocket connection established")
            else:
                logger.warning("⚠️ WebSocket connection timeout, subscriptions may fail")
            
            # Subscribe to any existing open positions
            self._subscribe_to_open_positions()
            
        except Exception as e:
            logger.error(f"Failed to initialize live prices: {e}")
            logger.warning("⚠️ Will fall back to yfinance for LTP (15min delayed)")
            self.price_cache = None
            self.scrip_master = None
            # Don't fail initialization - system can work with yfinance fallback
    
    def _subscribe_to_open_positions(self):
        """
        Subscribe WebSocket to symbols with active pending sell orders.
        This ensures real-time prices for sell order monitoring.
        
        Note: This method is called at startup. The SellOrderManager will
        subscribe to additional symbols as sell orders are placed during runtime.
        """
        if not self.price_cache:
            logger.warning("⚠️ Price cache not initialized, cannot subscribe to open positions")
            return
        
        try:
            # Get pending sell orders from broker
            if not self.auth:
                logger.warning("⚠️ Auth not initialized, skipping WebSocket subscription")
                return
            
            logger.info("Getting pending sell orders to subscribe to WebSocket...")
            from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
            orders_client = KotakNeoOrders(self.auth)
            pending_orders = orders_client.get_pending_orders()
            
            logger.debug(f"Retrieved {len(pending_orders) if pending_orders else 0} pending orders")
            
            if not pending_orders:
                logger.info("No pending orders to subscribe to WebSocket")
                return
            
            # Extract symbols from SELL orders only
            symbols = set()
            for order in pending_orders:
                # Check if this is a SELL order
                txn_type = (order.get('trnsTp') or order.get('transactionType') or '').upper()
                if txn_type not in ['S', 'SELL']:
                    logger.debug(f"Skipping non-SELL order: {txn_type}")
                    continue
                
                # Extract symbol (keep full trading symbol like 'DALBHARAT-EQ' for accurate lookup)
                symbol = order.get('trdSym') or order.get('tradingSymbol') or ''
                if not symbol:
                    logger.debug(f"Order missing symbol: {order}")
                    continue
                    
                # Keep the full symbol (e.g., 'DALBHARAT-EQ') to get correct instrument token
                # Don't strip the suffix as different segments (-EQ, -BL, etc.) have different tokens
                symbol = symbol.upper()
                
                if symbol:
                    symbols.add(symbol)
                    logger.debug(f"Found SELL order for symbol: {symbol}")
            
            if symbols:
                logger.info(f"Subscribing to {len(symbols)} active sell order(s) on WebSocket: {', '.join(sorted(symbols))}")
                self.price_cache.subscribe(list(symbols))
                logger.info(f"✅ Subscribed to WebSocket for sell orders: {', '.join(sorted(symbols))}")
            else:
                logger.info("No SELL orders found to subscribe (all orders may be BUY or no valid symbols)")
                
        except Exception as e:
            logger.error(f"Failed to subscribe to open positions: {e}", exc_info=True)
            # Not critical - subscriptions will happen later
    
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
                auth_client=self.auth.client if hasattr(self.auth, 'client') else None,
                exchanges=['NSE']
            )
            self.scrip_master.load_scrip_master(force_download=False)
            logger.info("✓ Scrip master loaded")
            
            # Initialize LivePriceCache with WebSocket connection
            # Pass auth object so LivePriceCache can get fresh client after re-auth
            self.price_cache = LivePriceCache(
                auth_client=self.auth.client if hasattr(self.auth, 'client') else None,
                scrip_master=self.scrip_master,
                stale_threshold_seconds=60,
                reconnect_delay_seconds=5,
                auth=self.auth  # Pass auth reference for re-auth handling
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
                
                if orders_response and 'data' in orders_response:
                    for order in orders_response['data']:
                        # Check order status
                        status = (order.get('orderStatus') or order.get('ordSt') or order.get('status') or '').lower()
                        
                        # Check transaction type - only SELL orders need real-time prices
                        txn_type = (order.get('transactionType') or order.get('trnsTp') or order.get('txnType') or '').upper()
                        
                        # Keep the full trading symbol (e.g., 'DALBHARAT-EQ') to get correct instrument token
                        # Don't strip the suffix as different segments (-EQ, -BL, etc.) have different tokens
                        broker_symbol = (order.get('tradingSymbol') or order.get('trdSym') or order.get('symbol') or '').strip()
                        
                        # Only subscribe to symbols with active SELL orders
                        if status in ['open', 'pending'] and txn_type in ['S', 'SELL'] and broker_symbol:
                            if broker_symbol not in symbols:
                                symbols.append(broker_symbol)
            except Exception as e:
                logger.debug(f"Could not fetch orders for subscription: {e}")
            
            if symbols:
                # Subscribe to positions for real-time prices (only SELL orders)
                self.price_cache.subscribe(symbols)
                logger.info(f"Subscribed to WebSocket for sell orders: {', '.join(symbols)}")
            else:
                logger.debug("No active sell orders found to subscribe (will subscribe as orders are placed)")
                
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
        time_diff = (now.hour * 60 + now.minute) - (scheduled_time.hour * 60 + scheduled_time.minute)
        return 0 <= time_diff < 2  # Run if within 2 minutes of scheduled time
    
    def run_premarket_retry(self):
        """9:00 AM - Retry failed orders from previous day"""
        try:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TASK: PRE-MARKET RETRY (9:00 AM)")
            logger.info("=" * 80)
            
            # Run AMO placement (it handles retries automatically)
            recs = self.engine.load_latest_recommendations()
            if recs:
                summary = self.engine.place_new_entries(recs)
                logger.info(f"Pre-market retry summary: {summary}")
            else:
                logger.info("No recommendations to retry")
            
            self.tasks_completed['premarket_retry'] = True
            logger.info("Pre-market retry completed")
            
        except Exception as e:
            logger.error(f"Pre-market retry failed: {e}")
            import traceback
            traceback.print_exc()
    
    def run_sell_monitor(self):
        """9:15 AM - Place sell orders and start monitoring (runs continuously)"""
        try:
            if not self.tasks_completed['sell_monitor_started']:
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
                            symbol = trade.get('symbol', '').upper()
                            if symbol and symbol not in symbols:
                                symbols.append(symbol)
                        
                        # Also get symbols from existing sell orders
                        from .utils.order_field_extractor import OrderFieldExtractor
                        from .utils.order_status_parser import OrderStatusParser
                        from .utils.symbol_utils import extract_base_symbol
                        from .domain.value_objects.order_enums import OrderStatus
                        
                        orders_api = KotakNeoOrders(self.auth)
                        orders_response = orders_api.get_orders()
                        
                        if orders_response and 'data' in orders_response:
                            for order in orders_response['data']:
                                status = OrderStatusParser.parse_status(order)
                                txn_type = OrderFieldExtractor.get_transaction_type(order)
                                broker_symbol = OrderFieldExtractor.get_symbol(order)
                                base_symbol = extract_base_symbol(broker_symbol) if broker_symbol else ''
                                
                                if status == OrderStatus.OPEN and txn_type == 'S' and base_symbol:
                                    if base_symbol not in symbols:
                                        symbols.append(base_symbol)
                        
                        if symbols:
                            # Subscribe to any new symbols (existing ones already subscribed)
                            self.price_cache.subscribe(symbols)
                            logger.debug(f"Subscribed to {len(symbols)} symbols for sell monitoring: {', '.join(symbols)}")
                            
                    except Exception as e:
                        logger.debug(f"Failed to subscribe to symbols: {e}")
                
                # Place sell orders at market open
                orders_placed = self.sell_manager.run_at_market_open()
                logger.info(f"Placed {orders_placed} sell orders")
                
                self.tasks_completed['sell_monitor_started'] = True
            
            # Monitor and update every minute during market hours
            if self.is_market_hours():
                stats = self.sell_manager.monitor_and_update()
                logger.debug(f"Sell monitor: {stats['checked']} checked, {stats['updated']} updated, {stats['executed']} executed")
                
        except Exception as e:
            logger.error(f"Sell monitor failed: {e}")
            import traceback
            traceback.print_exc()
    
    def run_position_monitor(self):
        """9:30 AM (hourly) - Monitor positions for reentry/exit signals"""
        try:
            current_hour = datetime.now().hour
            
            # Run once per hour, skip if already done this hour
            if self.tasks_completed['position_monitor'].get(current_hour):
                return
            
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"TASK: POSITION MONITOR ({current_hour}:30)")
            logger.info("=" * 80)
            
            # Monitor positions for signals (pass shared price_cache to avoid duplicate auth)
            summary = self.engine.monitor_positions(live_price_manager=self.price_cache)
            logger.info(f"Position monitor summary: {summary}")
            
            self.tasks_completed['position_monitor'][current_hour] = True
            logger.info("Position monitoring completed")
            
        except Exception as e:
            logger.error(f"Position monitor failed: {e}")
            import traceback
            traceback.print_exc()
    
    def run_analysis(self):
        """4:00 PM - Analyze stocks and generate recommendations"""
        max_retries = 3
        base_delay = 30.0  # Start with 30 seconds delay
        timeout_seconds = 1800  # 30 minutes timeout for market analysis
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{max_retries} for market analysis...")
                    time.sleep(base_delay * attempt)  # Exponential backoff
                
                logger.info("")
                logger.info("=" * 80)
                logger.info("TASK: MARKET ANALYSIS (4:00 PM)")
                logger.info("=" * 80)
                
                # Run trade_agent.py --backtest with timeout
                import subprocess
                try:
                    result = subprocess.run(
                        [sys.executable, "trade_agent.py", "--backtest"],
                        cwd=project_root,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',  # Replace problematic Unicode chars instead of failing
                        timeout=timeout_seconds  # 30 minute timeout
                    )
                    
                    if result.returncode == 0:
                        logger.info("Market analysis completed successfully")
                        self.tasks_completed['analysis'] = True
                        return  # Success - exit retry loop
                    else:
                        # Log both stdout and stderr for better debugging
                        error_msg = f"Market analysis failed with return code {result.returncode}"
                        if result.stderr:
                            error_msg += f"\nSTDERR:\n{result.stderr}"
                        if result.stdout:
                            # Show last 500 chars of stdout to avoid log spam
                            stdout_snippet = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
                            error_msg += f"\nSTDOUT (last 500 chars):\n{stdout_snippet}"
                        
                        logger.error(error_msg)
                        
                        # Check if it's a network-related error that we should retry
                        error_text = (result.stderr + result.stdout).lower()
                        network_keywords = ['timeout', 'connection', 'socket', 'urllib3', 'recv_into', 'network']
                        is_network_error = any(keyword in error_text for keyword in network_keywords)
                        
                        if is_network_error and attempt < max_retries - 1:
                            logger.warning(f"Network error detected - will retry in {base_delay * (attempt + 1):.0f} seconds...")
                            continue  # Retry on network errors
                        else:
                            # Non-network error or final attempt - mark as failed
                            self.tasks_completed['analysis'] = True  # Mark as attempted to prevent infinite retries
                            return
                            
                except subprocess.TimeoutExpired:
                    logger.error(f"Market analysis timed out after {timeout_seconds} seconds")
                    if attempt < max_retries - 1:
                        logger.warning(f"Will retry analysis in {base_delay * (attempt + 1):.0f} seconds...")
                        continue
                    else:
                        logger.error("Max retries exceeded for market analysis timeout")
                        self.tasks_completed['analysis'] = True
                        return
                        
            except Exception as e:
                logger.error(f"Analysis failed with exception: {e}")
                import traceback
                traceback.print_exc()
                
                # Check if it's a network-related exception
                error_str = str(e).lower()
                network_keywords = ['timeout', 'connection', 'socket', 'network']
                is_network_error = any(keyword in error_str for keyword in network_keywords)
                
                if is_network_error and attempt < max_retries - 1:
                    logger.warning(f"Network exception detected - will retry in {base_delay * (attempt + 1):.0f} seconds...")
                    continue
                else:
                    # Final attempt or non-network error
                    self.tasks_completed['analysis'] = True
                    return
        
        # If we get here, all retries exhausted
        logger.error("Market analysis failed after all retry attempts")
        self.tasks_completed['analysis'] = True
    
    def run_buy_orders(self):
        """4:05 PM - Place AMO buy orders for next day"""
        try:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TASK: PLACE BUY ORDERS (4:05 PM)")
            logger.info("=" * 80)
            
            recs = self.engine.load_latest_recommendations()
            if recs:
                summary = self.engine.place_new_entries(recs)
                logger.info(f"Buy orders summary: {summary}")
            else:
                logger.info("No buy recommendations to place")
            
            self.tasks_completed['buy_orders'] = True
            logger.info("Buy orders placement completed")
            
        except Exception as e:
            logger.error(f"Buy orders failed: {e}")
            import traceback
            traceback.print_exc()
    
    def run_eod_cleanup(self):
        """6:00 PM - End-of-day cleanup"""
        try:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TASK: END-OF-DAY CLEANUP (6:00 PM)")
            logger.info("=" * 80)
            
            # Clean up expired failed orders
            # This removes failed orders that are older than 1 day (after market open)
            # or 2+ days old, keeping only today's orders and yesterday's orders before market open
            try:
                removed_count = cleanup_expired_failed_orders(config.TRADES_HISTORY_PATH)
                if removed_count > 0:
                    logger.info(f"Cleaned up {removed_count} expired failed order(s)")
                else:
                    logger.debug("No expired failed orders to clean up")
            except Exception as e:
                logger.warning(f"Failed to cleanup expired orders: {e}")
            
            # Run EOD cleanup if available
            if hasattr(self.engine, 'eod_cleanup') and self.engine.eod_cleanup:
                self.engine.eod_cleanup.run_eod_cleanup()
                logger.info("EOD cleanup completed")
            else:
                logger.info("EOD cleanup not configured")
            
            self.tasks_completed['eod_cleanup'] = True
            
            # Reset task completion flags for next day
            logger.info("EOD cleanup completed - resetting for next trading day")
            self.tasks_completed['analysis'] = False
            self.tasks_completed['buy_orders'] = False
            self.tasks_completed['premarket_retry'] = False
            self.tasks_completed['sell_monitor_started'] = False
            self.tasks_completed['position_monitor'] = {}
            logger.info("Service ready for next trading day")
            
        except Exception as e:
            logger.error(f"EOD cleanup failed: {e}")
            import traceback
            traceback.print_exc()
    
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
        logger.info(f"Is trading day: {self.is_trading_day()} (weekday: {now_init.weekday()}, 0=Mon, 4=Fri)")
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
                    logger.info(f"Scheduler loop iteration #{loop_count} at {now.strftime('%H:%M:%S')}")
                
                # Run tasks only once per minute (on trading days only)
                if current_minute != last_minute:
                    last_minute = current_minute
                    logger.debug(f"Scheduler check at {current_time.strftime('%H:%M:%S')} (loop #{loop_count})")
                    
                    # Only run tasks on trading days (Mon-Fri)
                    if self.is_trading_day():
                        logger.debug(f"  → Trading day detected - checking tasks...")
                        # 9:00 AM - Pre-market retry
                        if self.should_run_task('premarket_retry', dt_time(9, 0)):
                            self.run_premarket_retry()
                        
                        # 9:15 AM onwards - Sell monitoring (continuous)
                        if current_time >= dt_time(9, 15) and self.is_market_hours():
                            self.run_sell_monitor()
                        
                        # 9:30 AM, 10:30 AM, 11:30 AM, etc. - Position monitoring (hourly)
                        if current_time.minute == 30 and 9 <= current_time.hour <= 15:
                            self.run_position_monitor()
                        
                        # 4:00 PM - Analysis
                        if self.should_run_task('analysis', dt_time(16, 0)):
                            self.run_analysis()
                        
                        # 4:05 PM - Buy orders
                        if self.should_run_task('buy_orders', dt_time(16, 5)):
                            self.run_buy_orders()
                        
                        # 6:00 PM - EOD cleanup (resets for next day)
                        if self.should_run_task('eod_cleanup', dt_time(18, 0)):
                            self.run_eod_cleanup()
                
                # Periodic heartbeat log (every 5 minutes to show service is alive)
                if now.minute % 5 == 0 and now.second < 30:
                    logger.info(f"Scheduler heartbeat: {now.strftime('%Y-%m-%d %H:%M:%S')} - Service running (loop #{loop_count})...")
                
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
                logger.error("Service will continue after error - waiting 60 seconds before retry...")
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
        help="Path to Kotak Neo credentials env file"
    )
    
    args = parser.parse_args()
    
    # Create and run service
    service = TradingService(env_file=args.env)
    service.run()


if __name__ == "__main__":
    main()
