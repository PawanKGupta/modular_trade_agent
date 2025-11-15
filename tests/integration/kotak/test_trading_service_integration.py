#!/usr/bin/env python3
"""
Test Script for Trading Service - Runs tasks outside market hours and holidays
Allows testing all trading tasks without waiting for actual trading times
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, time as dt_time

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

try:
    from modules.kotak_neo_auto_trader.run_trading_service import TradingService
except ImportError:
    from modules.kotak_neo_auto_trader.run_trading_service import TradingService


class TestTradingService(TradingService):
    """
    Test version of TradingService that bypasses time/day checks
    """
    
    def __init__(self, env_file: str = "modules/kotak_neo_auto_trader/kotak_neo.env", force_trading_day: bool = True):
        """Initialize test service with forced trading day mode"""
        super().__init__(env_file)
        self.force_trading_day = force_trading_day
    
    def is_trading_day(self) -> bool:
        """Override to always return True in test mode"""
        if self.force_trading_day:
            return True
        return super().is_trading_day()
    
    def is_market_hours(self) -> bool:
        """Override to always return True in test mode"""
        if self.force_trading_day:
            return True
        return super().is_market_hours()
    
    def should_run_task(self, task_name: str, scheduled_time: dt_time) -> bool:
        """Override to always allow tasks to run in test mode"""
        if self.force_trading_day:
            return True
        return super().should_run_task(task_name, scheduled_time)
    
    def run_test_task(self, task_name: str):
        """Run a specific task for testing"""
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"TEST: Running {task_name}")
        logger.info("=" * 80)
        
        try:
            if task_name == "premarket_retry":
                self.run_premarket_retry()
            elif task_name == "sell_monitor":
                self.run_sell_monitor()
            elif task_name == "position_monitor":
                self.run_position_monitor()
            elif task_name == "analysis":
                self.run_analysis()
            elif task_name == "buy_orders":
                self.run_buy_orders()
            elif task_name == "eod_cleanup":
                self.run_eod_cleanup()
            else:
                logger.error(f"Unknown task: {task_name}")
                return False
            
            logger.info(f"✅ Test task '{task_name}' completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Test task '{task_name}' failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_all_tasks(self):
        """Run all tasks sequentially for testing"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST: Running ALL Tasks")
        logger.info("=" * 80)
        logger.info(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("Force trading day mode: ENABLED")
        logger.info("")
        
        tasks = [
            ("premarket_retry", "Pre-market Retry"),
            ("sell_monitor", "Sell Monitor"),
            ("position_monitor", "Position Monitor"),
            ("analysis", "Market Analysis"),
            ("buy_orders", "Buy Orders"),
            ("eod_cleanup", "EOD Cleanup"),
        ]
        
        results = []
        for task_name, task_display in tasks:
            logger.info(f"\n{'='*80}")
            logger.info(f"Testing: {task_display}")
            logger.info(f"{'='*80}")
            result = self.run_test_task(task_name)
            results.append((task_name, result))
        
        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        for task_name, success in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            logger.info(f"{status}: {task_name}")
        
        passed = sum(1 for _, success in results if success)
        logger.info(f"\nTotal: {passed}/{len(results)} tasks passed")
        logger.info("=" * 80)
        
        return all(success for _, success in results)


def main():
    """Main entry point for test script"""
    parser = argparse.ArgumentParser(
        description="Test Trading Service - Run tasks outside market hours and holidays"
    )
    parser.add_argument(
        "--env",
        default="modules/kotak_neo_auto_trader/kotak_neo.env",
        help="Path to Kotak Neo credentials env file"
    )
    parser.add_argument(
        "--task",
        choices=["premarket_retry", "sell_monitor", "position_monitor", "analysis", "buy_orders", "eod_cleanup", "all"],
        default="all",
        help="Which task to run (default: all)"
    )
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="Skip initialization (use existing session)"
    )
    parser.add_argument(
        "--no-force-trading-day",
        action="store_true",
        help="Don't force trading day mode (respect actual time/day)"
    )
    
    args = parser.parse_args()
    
    # Create test service
    logger.info("=" * 80)
    logger.info("TEST TRADING SERVICE")
    logger.info("=" * 80)
    logger.info(f"Task: {args.task}")
    logger.info(f"Force trading day: {not args.no_force_trading_day}")
    logger.info(f"Skip init: {args.skip_init}")
    logger.info("")
    
    service = TestTradingService(
        env_file=args.env,
        force_trading_day=not args.no_force_trading_day
    )
    
    # Initialize unless skipped
    if not args.skip_init:
        logger.info("Initializing service...")
        if not service.initialize():
            logger.error("Initialization failed - cannot run tests")
            return 1
        logger.info("Initialization successful")
    else:
        logger.info("Skipping initialization - using existing session")
    
    # Run requested task(s)
    try:
        if args.task == "all":
            success = service.run_all_tasks()
        else:
            success = service.run_test_task(args.task)
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup
        logger.info("\nCleaning up...")
        service.shutdown()


if __name__ == "__main__":
    sys.exit(main())
