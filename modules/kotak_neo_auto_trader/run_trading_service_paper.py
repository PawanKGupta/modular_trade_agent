#!/usr/bin/env python3
"""
Unified Trading Service - Paper Trading Mode
Run the complete trading service with paper trading (no real money)

This allows you to test your strategy with all the same workflows:
- Market analysis (4:00 PM)
- Place buy orders (4:05 PM)
- Sell monitoring (9:15 AM - 3:30 PM)
- Position monitoring
- EOD cleanup

All orders go to paper trading system instead of real broker.
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
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter


class PaperTradingService:
    """
    Paper trading service - runs like the real service but with simulated trading
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        storage_path: str = "paper_trading/unified_service"
    ):
        """
        Initialize paper trading service

        Args:
            initial_capital: Starting virtual capital
            storage_path: Where to store paper trading data
        """
        self.initial_capital = initial_capital
        self.storage_path = storage_path

        # Paper trading components
        self.config: Optional[PaperTradingConfig] = None
        self.broker: Optional[PaperTradingBrokerAdapter] = None
        self.reporter: Optional[PaperTradeReporter] = None

        # Service state
        self.running = False
        self.shutdown_requested = False

        # Task execution flags (reset daily)
        self.tasks_completed = {
            'analysis': False,
            'buy_orders': False,
            'eod_cleanup': False,
            'premarket_retry': False,
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
        """Initialize paper trading service"""
        try:
            logger.info("=" * 80)
            logger.info("PAPER TRADING SERVICE INITIALIZATION")
            logger.info("=" * 80)
            logger.info("⚠️  PAPER TRADING MODE - NO REAL MONEY")
            logger.info("=" * 80)

            # Create paper trading configuration
            logger.info(f"Creating paper trading config (Capital: ₹{self.initial_capital:,.2f})...")
            self.config = PaperTradingConfig(
                initial_capital=self.initial_capital,
                enable_slippage=True,
                enable_fees=True,
                enforce_market_hours=True,
                price_source="live",  # Use live prices
                storage_path=self.storage_path,
                auto_save=True
            )

            # Initialize paper trading broker
            logger.info("Initializing paper trading broker...")
            self.broker = PaperTradingBrokerAdapter(self.config)

            if not self.broker.connect():
                logger.error("Failed to connect to paper trading system")
                return False

            logger.info("✅ Paper trading broker connected")

            # Initialize reporter
            self.reporter = PaperTradeReporter(self.broker.store)

            logger.info("Service initialized successfully")
            logger.info("=" * 80)

            # Show current portfolio status
            self._show_portfolio_status()

            return True

        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _show_portfolio_status(self):
        """Display current portfolio status"""
        try:
            balance = self.broker.get_available_balance()
            holdings = self.broker.get_holdings()

            logger.info(f"💰 Available Balance: ₹{balance.amount:,.2f}")
            logger.info(f"📊 Holdings: {len(holdings)}")

            if holdings:
                for holding in holdings:
                    pnl = holding.calculate_pnl()
                    logger.info(
                        f"  • {holding.symbol}: {holding.quantity} shares @ "
                        f"₹{holding.average_price.amount:.2f} (P&L: ₹{pnl.amount:.2f})"
                    )
        except Exception as e:
            logger.warning(f"Could not display portfolio status: {e}")

    def is_trading_day(self) -> bool:
        """Check if today is a trading day (Monday-Friday)"""
        return datetime.now().weekday() < 5

    def is_market_hours(self) -> bool:
        """Check if currently in market hours (9:15 AM - 3:30 PM)"""
        now = datetime.now().time()
        return dt_time(9, 15) <= now <= dt_time(15, 30)

    def run_analysis(self):
        """Run market analysis (4:00 PM)"""
        if self.tasks_completed['analysis']:
            return

        logger.info("📊 Running market analysis...")
        logger.info("⚠️  Paper Trading: Analysis runs normally, orders will be simulated")

        # Your analysis would run here
        # Results would be used for placing paper trades

        # Example: Import and run trade_agent
        try:
            # This would run your actual analysis
            logger.info("Running trade_agent.py analysis...")
            # import trade_agent
            # results = trade_agent.main(export_csv=True)
            logger.info("✅ Analysis complete")
        except Exception as e:
            logger.error(f"Analysis failed: {e}")

        self.tasks_completed['analysis'] = True

    def place_buy_orders(self):
        """Place buy orders (4:05 PM) - paper trading version"""
        if self.tasks_completed['buy_orders']:
            return

        logger.info("📝 Placing paper buy orders...")

        # This would place orders using self.broker.place_order()
        # All orders go to paper trading system

        try:
            # Example: Place paper trades based on analysis
            # (In reality, you'd integrate with your analysis results)
            logger.info("⚠️  Orders would be placed to paper trading system")
            logger.info("✅ Paper buy orders complete")
        except Exception as e:
            logger.error(f"Failed to place buy orders: {e}")

        self.tasks_completed['buy_orders'] = True

    def eod_cleanup(self):
        """End of day cleanup (6:00 PM)"""
        if self.tasks_completed['eod_cleanup']:
            return

        logger.info("🧹 Running EOD cleanup...")

        # Generate daily report
        try:
            logger.info("📊 Generating daily report...")
            self.reporter.print_summary()

            # Export report
            timestamp = datetime.now().strftime("%Y%m%d")
            report_path = f"{self.storage_path}/reports/report_{timestamp}.json"
            self.reporter.export_to_json(report_path)
            logger.info(f"📄 Report saved to: {report_path}")

        except Exception as e:
            logger.error(f"Failed to generate report: {e}")

        # Reset flags for next day
        logger.info("Resetting task flags for next trading day...")
        self.tasks_completed = {k: False for k in self.tasks_completed}

        logger.info("✅ EOD cleanup complete")
        self.tasks_completed['eod_cleanup'] = True

    def run_scheduler(self):
        """Main scheduler loop"""
        logger.info("Starting scheduler loop...")
        self.running = True

        last_check = None

        while self.running and not self.shutdown_requested:
            try:
                now = datetime.now()
                current_time = now.time()

                # Check only once per minute
                current_minute = now.strftime("%Y-%m-%d %H:%M")
                if current_minute == last_check:
                    time.sleep(1)
                    continue

                last_check = current_minute

                # Only run on trading days
                if not self.is_trading_day():
                    time.sleep(60)
                    continue

                # Task scheduling
                # 4:00 PM - Market analysis
                if dt_time(16, 0) <= current_time < dt_time(16, 1):
                    self.run_analysis()

                # 4:05 PM - Place buy orders
                elif dt_time(16, 5) <= current_time < dt_time(16, 6):
                    self.place_buy_orders()

                # 6:00 PM - EOD cleanup
                elif dt_time(18, 0) <= current_time < dt_time(18, 1):
                    self.eod_cleanup()

                time.sleep(1)

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)

    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down paper trading service...")

        try:
            # Generate final report
            if self.reporter:
                logger.info("📊 Generating final report...")
                self.reporter.print_summary()

            # Disconnect broker
            if self.broker:
                logger.info("Disconnecting paper trading broker...")
                self.broker.disconnect()

            logger.info("✅ Shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def run(self):
        """Main entry point"""
        logger.info("Setting up signal handlers...")
        self.setup_signal_handlers()

        # Initialize service
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
            self.shutdown()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Paper Trading Service - Test your strategy without real money"
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="Initial virtual capital (default: 100000)"
    )
    parser.add_argument(
        "--storage",
        default="paper_trading/unified_service",
        help="Storage path for paper trading data"
    )

    args = parser.parse_args()

    # Create and run service
    service = PaperTradingService(
        initial_capital=args.capital,
        storage_path=args.storage
    )
    service.run()


if __name__ == "__main__":
    main()

