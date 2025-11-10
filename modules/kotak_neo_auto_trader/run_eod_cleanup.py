#!/usr/bin/env python3
"""
DEPRECATED - Use run_trading_service.py instead

This script is kept for manual fallback only.
The unified trading service (run_trading_service.py) handles EOD cleanup automatically at 6:00 PM.

End-of-Day Cleanup Runner
Executes the EOD cleanup workflow when called by scheduled task
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


def run_eod_cleanup(env_file: str = "kotak_neo.env"):
    """
    Run end-of-day cleanup workflow.
    
    Args:
        env_file: Path to environment file
    """
    logger.info("=" * 70)
    logger.info("STARTING EOD CLEANUP RUNNER")
    logger.info("=" * 70)
    
    try:
        # Initialize engine
        engine = AutoTradeEngine(
            env_file=env_file,
            enable_verifier=False,  # Don't need verifier for EOD
            enable_telegram=True,  # Keep Telegram for notifications
            enable_eod_cleanup=True
        )
        
        # Login
        if not engine.login():
            logger.error("Login failed - aborting EOD cleanup")
            return False
        
        logger.info("Login successful")
        
        # Run EOD cleanup
        if not engine.eod_cleanup:
            logger.error("EOD cleanup module not initialized")
            engine.logout()
            return False
        
        results = engine.eod_cleanup.run_eod_cleanup()
        
        # Log summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("EOD CLEANUP SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Success: {results['success']}")
        logger.info(f"Duration: {results['duration_seconds']:.2f}s")
        logger.info(f"Steps Completed: {len(results['steps_completed'])}/6")
        logger.info(f"Steps Failed: {len(results['steps_failed'])}/6")
        
        if results['steps_failed']:
            logger.warning(f"Failed steps: {', '.join(results['steps_failed'])}")
        
        logger.info("=" * 70)
        
        # Logout
        engine.logout()
        
        return results['success']
        
    except Exception as e:
        logger.error(f"EOD cleanup error: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run end-of-day cleanup workflow"
    )
    parser.add_argument(
        "--env",
        type=str,
        default="kotak_neo.env",
        help="Path to environment file"
    )
    
    args = parser.parse_args()
    
    success = run_eod_cleanup(env_file=args.env)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
