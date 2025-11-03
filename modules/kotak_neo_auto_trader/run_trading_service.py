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
    from . import config
except ImportError:
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
    from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
    from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache
    from modules.kotak_neo_auto_trader import config


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
        logger.info("⚠️ Shutdown signal received - stopping service gracefully...")
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
            
            # Initialize authentication
            logger.info("Authenticating with Kotak Neo...")
            self.auth = KotakNeoAuth(self.env_file)
            
            if not self.auth.login():
                logger.error("❌ Authentication failed")
                return False
            
            logger.info("✅ Authentication successful - session active for the day")
            
            # Initialize trading engine
            logger.info("Initializing trading engine...")
            self.engine = AutoTradeEngine(env_file=self.env_file, auth=self.auth)
            
            # Initialize WebSocket live price feed
            logger.info("Initializing live price feed...")
            self._initialize_live_prices()
            
            # Initialize sell order manager with live prices
            logger.info("Initializing sell order manager...")
            self.sell_manager = SellOrderManager(
                self.auth, 
                price_manager=self.price_cache
            )
            
            logger.info("✅ Service initialized successfully")
            logger.info("=" * 80)
            return True
            
        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
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
            
            # Note: Symbols will be subscribed dynamically when sell orders are placed
            
        except Exception as e:
            logger.error(f"Failed to initialize live prices: {e}")
            logger.warning("⚠️ Will fall back to yfinance for LTP (15min delayed)")
            self.price_cache = None
            self.scrip_master = None
            # Don't fail initialization - system can work with yfinance fallback
    
    def is_trading_day(self) -> bool:
        """Check if today is a trading day (Monday-Friday)"""
        return datetime.now().weekday() < 5
    
    def is_market_hours(self) -> bool:
        """Check if currently in market hours (9:15 AM - 3:30 PM)"""
        now = datetime.now().time()
        return dt_time(9, 15) <= now <= dt_time(15, 30)
    
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
            logger.info("✅ Pre-market retry completed")
            
        except Exception as e:
            logger.error(f"❌ Pre-market retry failed: {e}")
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
                
                # Place sell orders at market open
                orders_placed = self.sell_manager.run_at_market_open()
                logger.info(f"✅ Placed {orders_placed} sell orders")
                
                self.tasks_completed['sell_monitor_started'] = True
            
            # Monitor and update every minute during market hours
            if self.is_market_hours():
                stats = self.sell_manager.monitor_and_update()
                logger.debug(f"Sell monitor: {stats['checked']} checked, {stats['updated']} updated, {stats['executed']} executed")
                
        except Exception as e:
            logger.error(f"❌ Sell monitor failed: {e}")
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
            
            # Monitor positions for signals
            summary = self.engine.monitor_positions()
            logger.info(f"Position monitor summary: {summary}")
            
            self.tasks_completed['position_monitor'][current_hour] = True
            logger.info("✅ Position monitoring completed")
            
        except Exception as e:
            logger.error(f"❌ Position monitor failed: {e}")
            import traceback
            traceback.print_exc()
    
    def run_analysis(self):
        """4:00 PM - Analyze stocks and generate recommendations"""
        try:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TASK: MARKET ANALYSIS (4:00 PM)")
            logger.info("=" * 80)
            
            # Run trade_agent.py --backtest
            import subprocess
            result = subprocess.run(
                [sys.executable, "trade_agent.py", "--backtest"],
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'  # Replace problematic Unicode chars instead of failing
            )
            
            if result.returncode == 0:
                logger.info("✅ Market analysis completed successfully")
            else:
                logger.error(f"❌ Market analysis failed: {result.stderr}")
            
            self.tasks_completed['analysis'] = True
            
        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            import traceback
            traceback.print_exc()
    
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
            logger.info("✅ Buy orders placement completed")
            
        except Exception as e:
            logger.error(f"❌ Buy orders failed: {e}")
            import traceback
            traceback.print_exc()
    
    def run_eod_cleanup(self):
        """6:00 PM - End-of-day cleanup"""
        try:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TASK: END-OF-DAY CLEANUP (6:00 PM)")
            logger.info("=" * 80)
            
            # Run EOD cleanup if available
            if hasattr(self.engine, 'eod_cleanup') and self.engine.eod_cleanup:
                self.engine.eod_cleanup.run()
                logger.info("✅ EOD cleanup completed")
            else:
                logger.info("EOD cleanup not configured")
            
            self.tasks_completed['eod_cleanup'] = True
            
            # Reset task completion flags for next day
            logger.info("📊 EOD cleanup completed - resetting for next trading day")
            self.tasks_completed['analysis'] = False
            self.tasks_completed['buy_orders'] = False
            self.tasks_completed['premarket_retry'] = False
            self.tasks_completed['sell_monitor_started'] = False
            self.tasks_completed['position_monitor'] = {}
            logger.info("✅ Service ready for next trading day")
            
        except Exception as e:
            logger.error(f"❌ EOD cleanup failed: {e}")
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
        
        last_minute = -1
        
        while not self.shutdown_requested:
            try:
                now = datetime.now()
                current_time = now.time()
                current_minute = now.minute
                
                # Run tasks only once per minute (on trading days only)
                if current_minute != last_minute:
                    last_minute = current_minute
                    
                    # Only run tasks on trading days (Mon-Fri)
                    if self.is_trading_day():
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
                
                # Sleep for 30 seconds between checks
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("⚠️ Keyboard interrupt received")
                self.shutdown_requested = True
                break
                
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)  # Wait a bit before retrying
    
    def shutdown(self):
        """Graceful shutdown"""
        try:
            logger.info("")
            logger.info("=" * 80)
            logger.info("TRADING SERVICE SHUTDOWN")
            logger.info("=" * 80)
            
            # Stop WebSocket price feed
            if self.price_cache:
                try:
                    logger.info("Stopping WebSocket price feed...")
                    self.price_cache.stop()
                    logger.info("✅ WebSocket stopped")
                except Exception as e:
                    logger.error(f"Error stopping WebSocket: {e}")
            
            # Logout from session
            if self.auth:
                self.auth.logout()
                logger.info("✅ Logged out successfully")
            
            logger.info("Service stopped gracefully")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def run(self):
        """Main entry point - Runs continuously"""
        self.setup_signal_handlers()
        
        # Initialize service (single login)
        if not self.initialize():
            logger.error("Failed to initialize service")
            return
        
        try:
            # Run scheduler continuously
            self.run_scheduler()
        finally:
            # Always cleanup on exit
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
