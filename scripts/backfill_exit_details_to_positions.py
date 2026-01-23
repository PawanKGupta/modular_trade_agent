#!/usr/bin/env python3
"""
Phase 0.2: Backfill exit details for existing closed positions

This script populates exit detail columns for existing closed positions in the database
by inferring from Orders table (sell orders) and calculating realized P&L.

Run with: python scripts/backfill_exit_details_to_positions.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.infrastructure.db.session import SessionLocal


def backfill_exit_details():
    """Backfill exit details for existing closed positions"""
    db: Session = SessionLocal()
    try:
        # Get all closed positions with NULL exit details
        result = db.execute(
            text("""
                SELECT p.id, p.user_id, p.symbol, p.avg_price, p.quantity, p.closed_at
                FROM positions p
                WHERE p.closed_at IS NOT NULL
                  AND (p.exit_price IS NULL OR p.exit_reason IS NULL)
                ORDER BY p.closed_at DESC
            """)
        ).fetchall()

        if not result:
            print("No closed positions with missing exit details found. Nothing to backfill.")
            return

        print(f"Found {len(result)} closed positions with missing exit details. Starting backfill...")

        updated_count = 0
        skipped_count = 0

        for pos_id, user_id, symbol, avg_price, quantity, closed_at in result:
            try:
                # Try to find matching sell order
                # Look for sell orders executed around the same time as position closed
                sell_order = db.execute(
                    text("""
                        SELECT o.id, o.execution_price, o.execution_time, o.order_metadata
                        FROM orders o
                        WHERE o.user_id = :user_id
                          AND o.side = 'sell'
                          AND o.symbol = :symbol
                          AND o.status IN ('ongoing', 'closed')
                          AND o.execution_time IS NOT NULL
                          AND ABS(JULIANDAY(o.execution_time) - JULIANDAY(:closed_at)) < 0.01
                        ORDER BY ABS(JULIANDAY(o.execution_time) - JULIANDAY(:closed_at))
                        LIMIT 1
                    """),
                    {"user_id": user_id, "symbol": symbol, "closed_at": closed_at},
                ).fetchone()

                exit_price = None
                exit_reason = None
                exit_rsi = None
                sell_order_id = None

                if sell_order:
                    sell_order_id, execution_price, execution_time, order_metadata = sell_order
                    exit_price = execution_price
                    sell_order_id = sell_order_id

                    # Extract exit_reason and exit_rsi from order_metadata
                    if order_metadata:
                        import json

                        try:
                            if isinstance(order_metadata, str):
                                metadata = json.loads(order_metadata)
                            else:
                                metadata = order_metadata

                            exit_reason = metadata.get("exit_note", "EMA9_TARGET")
                            exit_rsi = metadata.get("exit_rsi")
                        except Exception:
                            exit_reason = "EMA9_TARGET"  # Default
                else:
                    # No sell order found - likely manual sell
                    exit_reason = "MANUAL"

                # Calculate realized P&L if exit_price is available
                realized_pnl = None
                realized_pnl_pct = None
                if exit_price and avg_price and quantity:
                    realized_pnl = (exit_price - avg_price) * quantity
                    cost_basis = avg_price * quantity
                    realized_pnl_pct = (
                        (realized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0
                    )

                # Update position
                update_params = {}
                if exit_price is not None:
                    update_params["exit_price"] = exit_price
                if exit_reason is not None:
                    update_params["exit_reason"] = exit_reason
                if exit_rsi is not None:
                    update_params["exit_rsi"] = exit_rsi
                if realized_pnl is not None:
                    update_params["realized_pnl"] = realized_pnl
                if realized_pnl_pct is not None:
                    update_params["realized_pnl_pct"] = realized_pnl_pct
                if sell_order_id is not None:
                    update_params["sell_order_id"] = sell_order_id

                if update_params:
                    set_clause = ", ".join([f"{k} = :{k}" for k in update_params.keys()])
                    db.execute(
                        text(f"""
                            UPDATE positions
                            SET {set_clause}
                            WHERE id = :pos_id
                        """),
                        {**update_params, "pos_id": pos_id},
                    )
                    updated_count += 1

                    if updated_count % 100 == 0:
                        print(f"Progress: Updated {updated_count} positions...")
                        db.commit()  # Commit in batches

            except Exception as e:
                print(f"Error processing position {pos_id} ({symbol}): {e}")
                skipped_count += 1
                continue

        # Final commit
        db.commit()
        print(f"\nBackfill complete!")
        print(f"  - Updated: {updated_count} positions")
        print(f"  - Skipped: {skipped_count} positions (errors)")

        # Verify backfill
        remaining = db.execute(
            text("""
                SELECT COUNT(*)
                FROM positions
                WHERE closed_at IS NOT NULL
                  AND (exit_price IS NULL AND exit_reason IS NULL)
            """)
        ).scalar()
        if remaining > 0:
            print(f"\nWarning: {remaining} closed positions still have NULL exit details")
        else:
            print("\n✓ All closed positions now have exit details set")

    except Exception as e:
        db.rollback()
        print(f"Error during backfill: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 80)
    print("Phase 0.2: Backfill exit details for existing closed positions")
    print("=" * 80)
    print()
    backfill_exit_details()

