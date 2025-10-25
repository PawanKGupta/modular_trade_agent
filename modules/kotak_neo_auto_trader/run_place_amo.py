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
    p.add_argument("--logout", action="store_true", help="Logout at end (default: keep session active)")
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
        # Hard cap: if we already have >= MAX_PORTFOLIO_SIZE, stop immediately
        try:
            from . import config as _cfg
        except ImportError:
            import modules.kotak_neo_auto_trader.config as _cfg
        try:
            # Prefer a raw holdings check for exact count and to catch 2FA gating strings
            raw = engine.portfolio.get_holdings() if engine.portfolio else {}
            if isinstance(raw, dict):
                # Safe-guard: if API says 2FA required, attempt force re-login once
                if 'Error Message' in raw and '2fa' in str(raw.get('Error Message','')).lower():
                    try:
                        if engine.auth and hasattr(engine.auth, 'force_relogin') and engine.auth.force_relogin():
                            raw = engine.portfolio.get_holdings()
                        else:
                            logger.info("Holdings gated by 2FA and re-login failed; skipping AMO placement")
                            return
                    except Exception:
                        logger.info("Holdings gated by 2FA; skipping AMO placement to avoid invalid state")
                        return
                data = raw.get('data') or []
                if isinstance(data, list) and len(data) >= getattr(_cfg, 'MAX_PORTFOLIO_SIZE', 6):
                    logger.info(f"Portfolio cap reached ({len(data)}/{getattr(_cfg, 'MAX_PORTFOLIO_SIZE', 6)}); skipping AMO placement")
                    return
            # Fallback to symbol-based helper
            current_syms = engine.current_symbols_in_portfolio()
            if len(current_syms) >= getattr(_cfg, 'MAX_PORTFOLIO_SIZE', 6):
                logger.info(f"Portfolio cap reached ({len(current_syms)}/{getattr(_cfg, 'MAX_PORTFOLIO_SIZE', 6)}); skipping AMO placement")
                return
        except Exception:
            pass
        recs = engine.load_latest_recommendations()
        if not recs:
            logger.warning("No BUY recommendations found in CSV")
            return
        summary = engine.place_new_entries(recs)
        logger.info(f"AMO placement summary: {summary}")
    finally:
        if args.logout:
            engine.logout()
        else:
            logger.info("Keeping session active (no logout)")


if __name__ == "__main__":
    main()
