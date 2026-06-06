#!/usr/bin/env python3
"""
Reopen a live (broker) position wrongly closed by stale holdings reconciliation.

Typical case: same-day buy shows broker_qty=0 (T+1 lag) or mid-session restart
ran reconcile/orphan cleanup and cancelled a valid pending sell.

Usage (repo root, prod DB):
  DB_URL=postgresql+psycopg2://trader:changeme@127.0.0.1:5432/tradeagent \\
    .venv/bin/python tools/repair_live_erroneous_position_close.py \\
      --user-id 2 --symbol PFC-EQ --position-id 13 --sell-order-id 108 --dry-run
  ... --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infrastructure.db.models import OrderStatus  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402
from src.infrastructure.persistence.orders_repository import OrdersRepository  # noqa: E402
from src.infrastructure.persistence.positions_repository import PositionsRepository  # noqa: E402

REVERSAL_REASON = (
    "Repair: erroneous MANUAL close / orphan cancel (holdings T+1 lag, 2026-06-03). "
    "Position reopened; place new sell via sell_monitor."
)


def _place_sell_for_user(user_id: int) -> int:
    """Run market-open sell placement (no reconcile) for open positions missing sells."""
    from src.application.services.broker_credentials import load_broker_credentials

    db = SessionLocal()
    try:
        broker_creds = load_broker_credentials(user_id, db)
        if not broker_creds:
            print(f"ERROR: broker credentials missing for user {user_id}")
            return 1

        from modules.kotak_neo_auto_trader.run_trading_service import TradingService

        service = TradingService(
            user_id=user_id,
            db_session=db,
            broker_creds=broker_creds,
            strategy_config=None,
            skip_execution_tracking=True,
            enable_live_price_cache=True,
        )
        if not service.initialize():
            print("ERROR: TradingService.initialize() failed")
            return 1
        placed = service.sell_manager.run_at_market_open(
            reconcile_holdings=False,
            cancel_orphans=False,
        )
        print(f"Placed or tracked {placed} sell order(s)")
        return 0
    finally:
        db.close()


def repair(
    *,
    user_id: int,
    symbol: str,
    position_id: int,
    sell_order_id: int,
    restore_quantity: float | None,
    apply: bool,
    place_sell: bool,
) -> int:
    db = SessionLocal()
    try:
        pos_repo = PositionsRepository(db)
        ord_repo = OrdersRepository(db)

        position = pos_repo.get_by_symbol_any(user_id, symbol, include_closed=True)
        if position is None or position.id != position_id:
            print(f"ERROR: position id={position_id} not found for user {user_id} / {symbol}")
            return 1
        if position.symbol.upper() != symbol.upper():
            print(f"ERROR: position symbol {position.symbol} != {symbol}")
            return 1

        sell_order = ord_repo.get(sell_order_id)
        if sell_order is None or sell_order.user_id != user_id:
            print(f"ERROR: sell order id={sell_order_id} not found")
            return 1
        if sell_order.side != "sell":
            print(f"ERROR: order {sell_order_id} is not a sell")
            return 1

        qty = restore_quantity
        if qty is None or qty <= 0:
            qty = float(sell_order.quantity or 0)
        if qty <= 0:
            print("ERROR: could not determine restore quantity")
            return 1

        print("=== Planned live broker repair ===")
        print(f"  Position {position.id} {position.symbol}:")
        print(f"    quantity {position.quantity} -> {qty}")
        print(f"    closed_at {position.closed_at} -> NULL")
        print(f"    exit_reason {position.exit_reason} -> NULL")
        print(f"    sell_order_id {position.sell_order_id} -> NULL")
        print(f"  Sell order {sell_order_id}: status={sell_order.status.value}")
        print(f"    reason -> {REVERSAL_REASON[:80]}...")

        if not apply:
            print("\nDry run only. Pass --apply to commit.")
            return 0

        position.quantity = qty
        position.closed_at = None
        position.exit_price = None
        position.exit_reason = None
        position.exit_rsi = None
        position.realized_pnl = None
        position.realized_pnl_pct = None
        position.sell_order_id = None

        if sell_order.status != OrderStatus.CANCELLED:
            ord_repo.mark_cancelled(sell_order, REVERSAL_REASON, auto_commit=False)
        else:
            sell_order.reason = REVERSAL_REASON

        db.commit()
        db.refresh(position)
        db.refresh(sell_order)

        print("\nApplied.")
        print(f"  Position {position.id}: qty={position.quantity}, closed_at={position.closed_at}")
        print(f"  Sell order {sell_order.id}: status={sell_order.status.value}")
        if place_sell:
            print("\nPlacing missing sell orders...")
            return _place_sell_for_user(user_id)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--symbol", required=True, help="e.g. PFC-EQ")
    parser.add_argument("--position-id", type=int, required=True)
    parser.add_argument("--sell-order-id", type=int, required=True)
    parser.add_argument("--quantity", type=float, default=None, help="Restore qty (default: sell order qty)")
    parser.add_argument("--apply", action="store_true", help="Commit changes (default: dry run)")
    parser.add_argument(
        "--place-sell",
        action="store_true",
        help="After repair, place missing live sell orders (requires --apply)",
    )
    args = parser.parse_args()
    if args.place_sell and not args.apply:
        print("ERROR: --place-sell requires --apply")
        return 1
    return repair(
        user_id=args.user_id,
        symbol=args.symbol,
        position_id=args.position_id,
        sell_order_id=args.sell_order_id,
        restore_quantity=args.quantity,
        apply=args.apply,
        place_sell=args.place_sell,
    )


if __name__ == "__main__":
    raise SystemExit(main())
