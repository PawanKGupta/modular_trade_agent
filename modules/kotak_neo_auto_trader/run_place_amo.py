#!/usr/bin/env python3
"""
Place AMO MARKET buy orders sized by capital for recommendations from CSV
with pre-checks: skip if in holdings, notify on insufficient balance, cancel-and-replace any pending BUY.
Usage:
  python -m modules.kotak_neo_auto_trader.run_place_amo --env modules/kotak_neo_auto_trader/kotak_neo.env --csv analysis_results/bulk_analysis_*.csv
"""

import argparse
from utils.logger import logger

try:
    from .auto_trade_engine import AutoTradeEngine
    from .orders import KotakNeoOrders
    from .portfolio import KotakNeoPortfolio
except ImportError:
    from auto_trade_engine import AutoTradeEngine
    from orders import KotakNeoOrders
    from portfolio import KotakNeoPortfolio


def main():
    p = argparse.ArgumentParser(description="Place AMO orders for recommendations with checks")
    p.add_argument("--env", default="modules/kotak_neo_auto_trader/kotak_neo.env")
    p.add_argument("--csv", default=None)
    args = p.parse_args()

    engine = AutoTradeEngine(env_file=args.env)
    if args.csv:
        engine._custom_csv_path = args.csv

    if not engine.login():
        logger.error("Login failed")
        return

    try:
        engine.orders = KotakNeoOrders(engine.auth)
        engine.portfolio = KotakNeoPortfolio(engine.auth)
        recs = engine.load_latest_recommendations()
        if not recs:
            logger.warning("No BUY recommendations found in CSV")
            return
        summary = engine.place_new_entries(recs)
        logger.info(f"AMO placement summary: {summary}")
    finally:
        engine.logout()


if __name__ == "__main__":
    main()
