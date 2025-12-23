#!/usr/bin/env python3
"""
Phase 0.1: Backfill trade_mode for existing orders

This script populates the trade_mode column for existing orders in the database
by inferring from user_settings.trade_mode.

Run with: python scripts/backfill_trade_mode_to_orders.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.infrastructure.db.models import TradeMode
from src.infrastructure.db.session import SessionLocal


def backfill_trade_mode():
    """Backfill trade_mode for existing orders"""
    db: Session = SessionLocal()
    try:
        # Get all orders with NULL trade_mode
        result = db.execute(
            text("""
                SELECT o.id, o.user_id, u.id as user_exists
                FROM orders o
                LEFT JOIN users u ON o.user_id = u.id
                WHERE o.trade_mode IS NULL
            """)
        ).fetchall()

        if not result:
            print("No orders with NULL trade_mode found. Nothing to backfill.")
            return

        print(f"Found {len(result)} orders with NULL trade_mode. Starting backfill...")

        updated_count = 0
        skipped_count = 0

        for order_id, user_id, user_exists in result:
            if not user_exists:
                print(f"Warning: Order {order_id} has invalid user_id {user_id}, skipping...")
                skipped_count += 1
                continue

            # Get user's trade_mode from user_settings
            settings_result = db.execute(
                text("""
                    SELECT trade_mode
                    FROM user_settings
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id},
            ).fetchone()

            if not settings_result:
                # No settings found - default to PAPER for backward compatibility
                trade_mode = TradeMode.PAPER.value
                print(
                    f"Order {order_id}: No user_settings found for user {user_id}, "
                    f"defaulting to {trade_mode}"
                )
            else:
                trade_mode = settings_result[0]

            # Update order
            db.execute(
                text("""
                    UPDATE orders
                    SET trade_mode = :trade_mode
                    WHERE id = :order_id
                """),
                {"trade_mode": trade_mode, "order_id": order_id},
            )
            updated_count += 1

            if updated_count % 100 == 0:
                print(f"Progress: Updated {updated_count} orders...")
                db.commit()  # Commit in batches

        # Final commit
        db.commit()
        print(f"\nBackfill complete!")
        print(f"  - Updated: {updated_count} orders")
        print(f"  - Skipped: {skipped_count} orders (invalid user_id)")

        # Verify backfill
        remaining = db.execute(
            text("SELECT COUNT(*) FROM orders WHERE trade_mode IS NULL")
        ).scalar()
        if remaining > 0:
            print(f"\nWarning: {remaining} orders still have NULL trade_mode")
        else:
            print("\n✓ All orders now have trade_mode set")

    except Exception as e:
        db.rollback()
        print(f"Error during backfill: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 80)
    print("Phase 0.1: Backfill trade_mode for existing orders")
    print("=" * 80)
    print()
    backfill_trade_mode()

