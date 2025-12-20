#!/usr/bin/env python3
"""
Script to add missing broker positions to orders and positions tables.

This script creates:
1. Buy orders with status ONGOING (executed orders)
2. Positions with correct quantity and price

Use this when you have positions in your broker account that weren't tracked
by the system (e.g., system entries missed due to service downtime, or positions
from before system tracking).
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session  # noqa: E402

from src.infrastructure.db.models import Orders, OrderStatus  # noqa: E402
from src.infrastructure.db.timezone_utils import ist_now  # noqa: E402
from src.infrastructure.persistence.orders_repository import OrdersRepository  # noqa: E402
from src.infrastructure.persistence.positions_repository import PositionsRepository  # noqa: E402

# Import symbol utilities for ticker creation
try:
    from modules.kotak_neo_auto_trader.utils.symbol_utils import (
        extract_base_symbol,
        get_ticker_from_full_symbol,
    )
except ImportError:
    # Fallback if not available
    def extract_base_symbol(symbol: str) -> str:
        return symbol.upper().split("-")[0]

    def get_ticker_from_full_symbol(full_symbol: str, exchange: str = "NS") -> str:
        base = extract_base_symbol(full_symbol)
        return f"{base}.{exchange}"


def add_missing_position(
    db: Session,
    user_id: int,
    symbol: str,
    quantity: float,
    buy_price: float,
    trade_date: str,
    dry_run: bool = True,
):
    """
    Add a missing position by creating order and position records.

    Args:
        db: Database session
        user_id: User ID
        symbol: Full symbol (e.g., "ASTERDM-EQ", "EMKAY-BE")
        quantity: Quantity of shares
        buy_price: Buy price per share
        trade_date: Trade date in format "DD MMM YYYY" (e.g., "11 Dec 2025")
        dry_run: If True, only shows what would be created without making changes.

    Returns:
        Tuple of (order, position) or (None, None) if dry_run
    """
    print(f"\n{'=' * 80}")
    print(f"Processing: {symbol}")
    print(f"{'=' * 80}")

    # Parse trade date
    try:
        # Parse "11 Dec 2025" format
        trade_datetime = datetime.strptime(trade_date, "%d %b %Y")
        # Set to market open time (9:15 AM IST)
        trade_datetime = trade_datetime.replace(hour=9, minute=15, second=0, microsecond=0)
    except ValueError:
        try:
            # Try ISO format
            trade_datetime = datetime.fromisoformat(trade_date)
        except ValueError:
            print(f"  ❌ ERROR: Invalid date format: {trade_date}")
            print("     Expected format: 'DD MMM YYYY' (e.g., '11 Dec 2025')")
            return None, None

    orders_repo = OrdersRepository(db)
    positions_repo = PositionsRepository(db)

    # Check if order already exists
    existing_orders = orders_repo.list(user_id)
    for order in existing_orders:
        if (
            order.symbol.upper() == symbol.upper()
            and order.side == "buy"
            and order.status in [OrderStatus.ONGOING, OrderStatus.CLOSED]
        ):
            print(f"  ⚠️  WARNING: Buy order already exists for {symbol}")
            print(f"     Order ID: {order.id}, Status: {order.status.value}")
            print("     Skipping order creation...")
            order_obj = order
            break
    else:
        # Create new order
        print("  📝 Creating buy order:")
        print(f"     Symbol: {symbol}")
        print(f"     Quantity: {quantity}")
        print(f"     Price: Rs {buy_price:.2f}")
        print(f"     Trade Date: {trade_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

        if not dry_run:
            # Determine exchange from symbol suffix
            # -EQ = NSE Equity, -BE = BSE Equity, -BL = BSE Limited, etc.
            symbol_upper = symbol.upper()
            if "-BE" in symbol_upper or "-BL" in symbol_upper or "-BZ" in symbol_upper:
                exchange = "BO"  # BSE
            else:
                exchange = "NS"  # NSE (default, includes -EQ, -XX, etc.)

            # Create ticker for order metadata
            ticker = get_ticker_from_full_symbol(symbol_upper, exchange=exchange)

            # Create order metadata with ticker information
            order_metadata = {
                "ticker": ticker,
                "exchange": "BSE" if exchange == "BO" else "NSE",
                "base_symbol": extract_base_symbol(symbol_upper),
                "full_symbol": symbol_upper,
            }

            # Create order with ONGOING status (already executed)
            order_obj = Orders(
                user_id=user_id,
                symbol=symbol.upper(),
                side="buy",
                order_type="market",  # Assume market order
                quantity=quantity,
                price=buy_price,  # Limit price (if limit order)
                status=OrderStatus.ONGOING,  # Already executed
                placed_at=trade_datetime,
                updated_at=trade_datetime,
                filled_at=trade_datetime,
                execution_price=buy_price,
                execution_qty=quantity,
                execution_time=trade_datetime,
                avg_price=buy_price,
                last_status_check=ist_now(),
                entry_type="initial",  # System initial entry that was missed due to service downtime
                orig_source="signal",  # System-generated entry (missed due to service downtime)
                order_metadata=order_metadata,  # Include ticker and exchange info
                reason=f"System entry (missed): Position added from broker account due to service downtime (traded {trade_date})",
            )
            db.add(order_obj)
            db.flush()  # Flush to get order ID
            print(f"  ✅ Order created: ID {order_obj.id}")
        else:
            print("  🔍 [DRY RUN] Would create order")
            order_obj = None

    # Check if position already exists
    existing_position = positions_repo.get_by_symbol(user_id, symbol.upper())
    if existing_position:
        print(f"  ⚠️  WARNING: Position already exists for {symbol}")
        print(f"     Position ID: {existing_position.id}")
        print(f"     Current Quantity: {existing_position.quantity}")
        print(f"     Current Avg Price: Rs {existing_position.avg_price:.2f}")

        # Update if different
        if (
            abs(existing_position.quantity - quantity) > 0.01
            or abs(existing_position.avg_price - buy_price) > 0.01
        ):
            print("  📝 Updating position to match broker data:")
            print(f"     Quantity: {existing_position.quantity} -> {quantity}")
            print(f"     Avg Price: Rs {existing_position.avg_price:.2f} -> Rs {buy_price:.2f}")

            if not dry_run:
                existing_position.quantity = quantity
                existing_position.avg_price = buy_price
                existing_position.initial_entry_price = (
                    existing_position.initial_entry_price or buy_price
                )
                db.commit()
                print("  ✅ Position updated")
            else:
                print("  🔍 [DRY RUN] Would update position")
        else:
            print("  ✓ Position data matches, no update needed")

        position_obj = existing_position
    else:
        # Create new position
        print("  📝 Creating position:")
        print(f"     Symbol: {symbol}")
        print(f"     Quantity: {quantity}")
        print(f"     Avg Price: Rs {buy_price:.2f}")
        print(f"     Opened At: {trade_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

        if not dry_run:
            position_obj = positions_repo.upsert(
                user_id=user_id,
                symbol=symbol.upper(),
                quantity=quantity,
                avg_price=buy_price,
                opened_at=trade_datetime,
                initial_entry_price=buy_price,
                entry_rsi=None,  # Not available for missed entries (service was down)
                auto_commit=False,  # We'll commit after order
            )
            print(f"  ✅ Position created: ID {position_obj.id}")
        else:
            print("  🔍 [DRY RUN] Would create position")
            position_obj = None

    return order_obj, position_obj


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Add missing broker positions to orders and positions tables"
    )
    parser.add_argument(
        "--user-id",
        type=int,
        required=True,
        help="User ID to add positions for",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default: dry run)",
    )

    args = parser.parse_args()

    # Import SessionLocal here to avoid triggering engine creation during test imports
    from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        print("=" * 80)
        print("Add Missing Broker Positions")
        print("=" * 80)
        if not args.apply:
            print("🔍 DRY RUN MODE - No changes will be made")
        print()

        # Add the two positions
        positions_to_add = [
            {
                "symbol": "ASTERDM-EQ",
                "quantity": 16,
                "buy_price": 633.05,
                "trade_date": "11 Dec 2025",
            },
            {
                "symbol": "EMKAY-BE",
                "quantity": 376,
                "buy_price": 267.95,
                "trade_date": "16 Dec 2025",
            },
        ]

        created_orders = []
        created_positions = []

        for pos_data in positions_to_add:
            order, position = add_missing_position(
                db=db,
                user_id=args.user_id,
                symbol=pos_data["symbol"],
                quantity=pos_data["quantity"],
                buy_price=pos_data["buy_price"],
                trade_date=pos_data["trade_date"],
                dry_run=not args.apply,
            )
            if order:
                created_orders.append(order)
            if position:
                created_positions.append(position)

        if args.apply and (created_orders or created_positions):
            db.commit()
            print()
            print("=" * 80)
            print("Summary")
            print("=" * 80)
            print(f"✅ Orders created/updated: {len(created_orders)}")
            print(f"✅ Positions created/updated: {len(created_positions)}")
            print()
            print("These positions will now be tracked by sell order monitoring.")
        elif not args.apply:
            print()
            print("=" * 80)
            print("Summary")
            print("=" * 80)
            print(f"🔍 Would create/update orders: {len([o for o in created_orders if o])}")
            print(f"🔍 Would create/update positions: {len([p for p in created_positions if p])}")
            print()
            print("Run with --apply to make changes.")

    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
