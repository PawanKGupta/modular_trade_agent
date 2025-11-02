#!/usr/bin/env python3
"""
⚠️ DEPRECATED - Use run_trading_service.py instead

This script is kept for manual fallback only.
The unified trading service (run_trading_service.py) handles position monitoring automatically (hourly).

Position Monitor Runner
Executes live position monitoring for scheduled tasks
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from modules.kotak_neo_auto_trader.position_monitor import get_position_monitor


def is_market_hours() -> bool:
    """Check if current time is during market hours."""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()
    
    # Mon-Fri only
    if weekday > 4:
        return False
    
    # Market hours: 9:15 AM - 3:30 PM
    if hour < 9 or (hour == 9 and minute < 15):
        return False
    if hour > 15 or (hour == 15 and minute > 30):
        return False
    
    return True


def run_position_monitoring(
    history_path: str = "data/trades_history.json",
    enable_alerts: bool = True,
    force: bool = False
) -> bool:
    """
    Run position monitoring.
    
    Args:
        history_path: Path to trades history
        enable_alerts: Enable Telegram alerts
        force: Force run even outside market hours
    
    Returns:
        True if successful
    """
    logger.info("=" * 70)
    logger.info("POSITION MONITOR RUNNER")
    logger.info("=" * 70)
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # Check market hours
    if not force and not is_market_hours():
        logger.info("Outside market hours - skipping monitoring")
        logger.info("Market hours: Mon-Fri 9:15 AM - 3:30 PM")
        return True
    
    try:
        # Get monitor instance
        monitor = get_position_monitor(
            history_path=history_path,
            enable_alerts=enable_alerts
        )
        
        # Run monitoring
        results = monitor.monitor_all_positions()
        
        # Log results
        logger.info("")
        logger.info("=" * 70)
        logger.info("MONITORING COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Positions Monitored: {results['monitored']}")
        logger.info(f"Exit Imminent: {results['exit_imminent']}")
        logger.info(f"Averaging Opportunities: {results['averaging_opportunities']}")
        logger.info(f"Alerts Sent: {results['alerts_sent']}")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"Position monitoring error: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run live position monitoring during market hours"
    )
    parser.add_argument(
        "--history",
        type=str,
        default="data/trades_history.json",
        help="Path to trades history file"
    )
    parser.add_argument(
        "--no-alerts",
        action="store_true",
        help="Disable Telegram alerts"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force run even outside market hours"
    )
    
    args = parser.parse_args()
    
    success = run_position_monitoring(
        history_path=args.history,
        enable_alerts=not args.no_alerts,
        force=args.force
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
