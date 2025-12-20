#!/usr/bin/env python3
"""
Script to fix entry_type for positions that were incorrectly marked as "manual"
but were actually system initial entries missed due to service downtime.

This updates:
- Orders: entry_type from "manual" to "initial", orig_source from "manual" to "signal"
- Positions: No direct entry_type field, but related orders will be updated
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from src.infrastructure.db.models import Orders  # noqa: E402


def fix_missed_entry_type(db: Session, user_id: int | None = None, dry_run: bool = True):
    """
    Fix entry_type for orders that were incorrectly marked as manual.

    Args:
        db: Database session
        user_id: Optional user ID to filter by. If None, updates all users.
        dry_run: If True, only shows what would be updated without making changes.
    """
    print("=" * 80)
    print("Fix Missed Entry Type (manual -> initial)")
    print("=" * 80)
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    print()

    # Find orders marked as manual but should be initial
    # These are buy orders with entry_type="manual" and orig_source="manual"
    # that have reason containing "missed" or "service downtime"
    stmt = (
        select(Orders)
        .where(Orders.side == "buy")
        .where(Orders.entry_type == "manual")
        .where(Orders.orig_source == "manual")
    )

    if user_id:
        stmt = stmt.where(Orders.user_id == user_id)

    orders = list(db.execute(stmt).scalars().all())

    print(f"Found {len(orders)} order(s) to check")
    print()

    updated_count = 0

    for order in orders:
        # Check if reason indicates it was a missed system entry
        reason = order.reason or ""
        if (
            "missed" in reason.lower()
            or "service" in reason.lower()
            or "downtime" in reason.lower()
        ):
            print(f"  📝 Order ID {order.id}: {order.symbol}")
            print(
                f"     Current: entry_type='{order.entry_type}', orig_source='{order.orig_source}'"
            )
            print(f"     Reason: {reason[:80]}...")

            if not dry_run:
                order.entry_type = "initial"
                order.orig_source = "signal"
                # Update reason to clarify it was a system entry
                if "missed" not in reason.lower():
                    order.reason = f"System entry (missed): {reason}"
                updated_count += 1
                print("     ✅ Will update to: entry_type='initial', orig_source='signal'")
            else:
                print(
                    "     🔍 [DRY RUN] Would update to: entry_type='initial', orig_source='signal'"
                )
                updated_count += 1
            print()

    if not dry_run and updated_count > 0:
        db.commit()
        print("=" * 80)
        print("Summary")
        print("=" * 80)
        print(f"✅ Updated {updated_count} order(s)")
    elif dry_run:
        print("=" * 80)
        print("Summary")
        print("=" * 80)
        print(f"🔍 Would update {updated_count} order(s) (DRY RUN)")
    else:
        print("ℹ️  No orders needed updates")

    print()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Fix entry_type for missed system entries")
    parser.add_argument(
        "--user-id",
        type=int,
        help="User ID to update orders for (default: all users)",
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
        fix_missed_entry_type(
            db=db,
            user_id=args.user_id,
            dry_run=not args.apply,
        )
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
