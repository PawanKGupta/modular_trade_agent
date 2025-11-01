#!/usr/bin/env python3
"""
⚠️ DEPRECATED - Use run_trading_service.py instead

This script is kept for manual fallback only.
The unified trading service (run_trading_service.py) runs all tasks automatically.

Run Auto Trade after trade_agent analysis.
Usage:
  python -m modules.kotak_neo_auto_trader.run_auto_trade [--env kotak_neo.env]
"""

import argparse
from utils.logger import logger

try:
    from .auto_trade_engine import AutoTradeEngine
except ImportError:
    from auto_trade_engine import AutoTradeEngine


def main():
    parser = argparse.ArgumentParser(description="Kotak Neo Auto Trader Runner")
    parser.add_argument("--env", default="modules/kotak_neo_auto_trader/kotak_neo.env", help="Path to env file for Kotak Neo credentials")
    parser.add_argument("--csv", default=None, help="Path to the recommendations CSV to use")
    parser.add_argument("--logout", action="store_true", help="Logout at end (by default session is kept)")
    args = parser.parse_args()

    engine = AutoTradeEngine(env_file=args.env)
    # Stash custom CSV path on engine for this run
    engine._custom_csv_path = args.csv
    engine.run(keep_session=not args.logout)
    logger.info("Auto trade run complete")


if __name__ == "__main__":
    main()
