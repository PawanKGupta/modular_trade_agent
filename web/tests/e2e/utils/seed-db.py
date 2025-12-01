#!/usr/bin/env python3
"""
Test Data Seeding Script for E2E Tests
Seeds the e2e database with test data for comprehensive testing

Usage:
    python seed-db.py [--signals N] [--orders N] [--notifications N] [--user-id ID]
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Set database URL for e2e tests
# IMPORTANT: E2E tests MUST use e2e.db, not app.db (which is used by Docker/production)
e2e_db_url = os.environ.get("E2E_DB_URL", "sqlite:///./data/e2e.db")
os.environ["DB_URL"] = e2e_db_url

# Warn if trying to use production database
if "app.db" in e2e_db_url:
    print("\n" + "=" * 70)
    print("⚠ WARNING: E2E tests should use e2e.db, not app.db!")
    print("  Your data will be seeded into the production database.")
    print("  This could cause issues if the Docker app is using app.db.")
    print("=" * 70 + "\n")
    response = input("Continue anyway? (yes/no): ")
    if response.lower() not in ["yes", "y"]:
        sys.exit(1)

# Imports must come after path setup - noqa comments suppress lint warnings
from src.infrastructure.db.base import Base  # noqa: E402
from src.infrastructure.db.models import (  # noqa: E402
    Notification,
    Orders,
    OrderStatus,
    Signals,
    SignalStatus,
    Users,
)
from src.infrastructure.db.session import SessionLocal, engine  # noqa: E402
from src.infrastructure.db.timezone_utils import ist_now  # noqa: E402


def ensure_schema(recreate: bool = False):
    """Ensure database schema is up to date"""
    from sqlalchemy import inspect  # noqa: PLC0415

    print("Ensuring database schema is up to date...")

    inspector = inspect(engine)

    # Check if signals table exists and has status column
    if inspector.has_table("signals"):
        columns = [col["name"] for col in inspector.get_columns("signals")]
        if "status" not in columns:
            if recreate:
                print("⚠ Signals table exists but missing 'status' column - recreating schema...")
                Base.metadata.drop_all(bind=engine)
                Base.metadata.create_all(bind=engine)
                print("✓ Database schema recreated")
            else:
                print("⚠ Warning: Signals table exists but is missing 'status' column.")
                print("  The database schema appears to be outdated.")
                print(
                    "  Please run Alembic migrations or use --recreate-db flag to recreate schema."
                )
                raise RuntimeError(
                    "Database schema is outdated. Run migrations or use --recreate-db to recreate."
                )
        else:
            print("✓ Database schema is up to date")
    else:
        # Create all tables if they don't exist
        Base.metadata.create_all(bind=engine)
        print("✓ Created database schema")


def get_or_create_test_user(db) -> Users:
    """Get or create the test admin user"""
    from src.infrastructure.db.models import UserRole  # noqa: PLC0415
    from src.infrastructure.persistence.user_repository import UserRepository  # noqa: PLC0415

    # First, try to find any admin user
    user = db.query(Users).filter(Users.role == UserRole.ADMIN).first()

    if user:
        return user

    # Try common admin emails
    common_emails = [
        os.environ.get("ADMIN_EMAIL"),
        os.environ.get("TEST_ADMIN_EMAIL"),
        "admin@example.com",
        "testadmin@rebound.com",
    ]

    # Filter out None values and try each email
    for email in [e for e in common_emails if e]:
        user = db.query(Users).filter(Users.email == email).first()
        if user:
            return user

    # If no user found, try to find ANY user
    user = db.query(Users).first()
    if user:
        print(f"⚠ Using existing user: {user.email} (ID: {user.id})")
        return user

    # Create admin user if none exists
    admin_email = (
        os.environ.get("ADMIN_EMAIL") or os.environ.get("TEST_ADMIN_EMAIL") or "admin@example.com"
    )
    admin_password = (
        os.environ.get("ADMIN_PASSWORD") or os.environ.get("TEST_ADMIN_PASSWORD") or "Admin@123"
    )
    admin_name = os.environ.get("ADMIN_NAME") or "Admin User"

    print(f"Creating admin user: {admin_email}")
    repo = UserRepository(db)
    user = repo.create_user(
        email=admin_email,
        password=admin_password,
        name=admin_name,
        role=UserRole.ADMIN,
    )

    # Also create default settings for the user (required for services)
    try:
        # noqa: PLC0415
        from src.infrastructure.persistence.settings_repository import SettingsRepository

        SettingsRepository(db).ensure_default(user.id)
        print(f"✓ Created default settings for admin user {user.id}")
    except Exception as e:
        print(f"⚠ Warning: Could not create default settings: {e}")

    return user


def create_test_signals(db, count: int, user_id: int):
    """Create test signals"""
    signals = []
    symbols = [
        "TCS",
        "INFY",
        "RELIANCE",
        "HDFCBANK",
        "ICICIBANK",
        "SBIN",
        "BHARTIARTL",
        "LT",
        "HCLTECH",
        "AXISBANK",
    ]

    now = ist_now()
    today = now.date()

    for i in range(count):
        symbol = symbols[i % len(symbols)]

        # Create signals with different statuses and dates
        status = SignalStatus.ACTIVE if i < count * 0.7 else SignalStatus.REJECTED
        signal_date = today if i < count * 0.5 else today - timedelta(days=i % 5)

        signal = Signals(
            symbol=symbol,
            status=status,
            rsi10=25.0 + (i * 2.5),  # Vary RSI between 25-50
            ema9=100.0 + (i * 10),
            ema200=90.0 + (i * 10),
            distance_to_ema9=2.0 + (i * 0.5),
            clean_chart=i % 2 == 0,
            monthly_support_dist=0.5 + (i * 0.2),
            confidence=0.6 + (i * 0.05),
            backtest_score=60.0 + (i * 5),
            combined_score=65.0 + (i * 5),
            ml_verdict="buy" if i % 2 == 0 else "avoid",
            ml_confidence=0.7 + (i * 0.02),
            buy_range={"low": 95.0 + (i * 5), "high": 100.0 + (i * 5)},
            target=110.0 + (i * 5),
            stop=90.0 + (i * 5),
            last_close=98.0 + (i * 5),
            verdict="buy" if i % 2 == 0 else "avoid",
            ts=datetime.combine(signal_date, now.time()).replace(tzinfo=now.tzinfo),
        )
        signals.append(signal)

    db.add_all(signals)
    db.commit()
    print(f"✓ Created {len(signals)} test signals")
    return signals


def create_test_orders(db, count: int, user_id: int):
    """Create test orders"""
    orders = []
    symbols = ["TCS", "INFY", "RELIANCE"]
    statuses = [OrderStatus.PENDING, OrderStatus.ONGOING, OrderStatus.CLOSED, OrderStatus.FAILED]

    now = ist_now()

    for i in range(count):
        symbol = symbols[i % len(symbols)]
        status = statuses[i % len(statuses)]
        side = "buy" if i % 2 == 0 else "sell"

        order = Orders(
            user_id=user_id,
            symbol=symbol,
            side=side,
            order_type="limit" if i % 2 == 0 else "market",
            quantity=10.0 + (i * 5),
            price=100.0 + (i * 10) if status != OrderStatus.PENDING else None,
            status=status,
            avg_price=100.0 + (i * 10) if status == OrderStatus.ONGOING else None,
            placed_at=now - timedelta(hours=i),
            filled_at=now - timedelta(hours=i - 1) if status == OrderStatus.ONGOING else None,
            closed_at=now - timedelta(minutes=30) if status == OrderStatus.CLOSED else None,
            orig_source="signal",
        )
        orders.append(order)

    db.add_all(orders)
    db.commit()
    print(f"✓ Created {len(orders)} test orders")
    return orders


def create_test_notifications(db, count: int, user_id: int):
    """Create test notifications"""
    notifications = []
    types = ["service", "trading", "system", "error"]
    levels = ["info", "warning", "error"]

    now = ist_now()

    for i in range(count):
        notif_type = types[i % len(types)]
        level = levels[i % len(levels)]
        read = i % 3 == 0  # Mix of read and unread

        notification = Notification(
            user_id=user_id,
            type=notif_type,
            level=level,
            title=f"Test {notif_type} notification {i + 1}",
            message=f"This is a test {notif_type} notification for E2E testing. Level: {level}",
            read=read,
            read_at=now - timedelta(hours=i) if read else None,
            created_at=now - timedelta(hours=i),
            telegram_sent=False,
            email_sent=False,
            in_app_delivered=True,
        )
        notifications.append(notification)

    db.add_all(notifications)
    db.commit()
    print(f"✓ Created {len(notifications)} test notifications")
    return notifications


def clear_test_data(db, user_id: int):
    """Clear existing test data (optional cleanup before seeding)"""
    try:
        # Clear signals
        db.query(Signals).delete()

        # Clear orders for test user
        db.query(Orders).filter(Orders.user_id == user_id).delete()

        # Clear notifications for test user
        db.query(Notification).filter(Notification.user_id == user_id).delete()

        db.commit()
        print("✓ Cleared existing test data")
    except Exception as e:
        print(f"⚠ Warning: Could not clear some test data: {e}")
        db.rollback()


def main():
    parser = argparse.ArgumentParser(
        description="Seed E2E test database with test data",
        epilog="""
IMPORTANT: This script seeds the E2E test database (e2e.db), not the production database (app.db).
The Docker app uses app.db, while E2E tests use e2e.db. These are separate databases.

For more information, see: web/tests/e2e/DATABASE.md
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--signals", type=int, default=5, help="Number of signals to create (default: 5)"
    )
    parser.add_argument(
        "--orders", type=int, default=3, help="Number of orders to create (default: 3)"
    )
    parser.add_argument(
        "--notifications",
        type=int,
        default=5,
        help="Number of notifications to create (default: 5)",
    )
    parser.add_argument(
        "--user-id", type=int, help="User ID to associate data with (default: admin user)"
    )
    parser.add_argument(
        "--clear", action="store_true", help="Clear existing test data before seeding"
    )
    parser.add_argument(
        "--recreate-schema",
        action="store_true",
        help="Recreate database schema if outdated (WARNING: drops all tables)",
    )
    parser.add_argument("--db-url", type=str, help="Database URL (overrides E2E_DB_URL env var)")

    args = parser.parse_args()

    if args.db_url:
        os.environ["DB_URL"] = args.db_url

    # Ensure schema is up to date before proceeding
    ensure_schema(recreate=args.recreate_schema)

    db = SessionLocal()

    try:
        # Get or create test user
        user = get_or_create_test_user(db)

        if not user:
            print("✗ Error: Could not find or create test user.")
            sys.exit(1)

        user_id = args.user_id or user.id
        print(f"✓ Using user ID: {user_id} ({user.email}, role: {user.role.value})")

        # Clear existing data if requested
        if args.clear:
            clear_test_data(db, user_id)

        # Create test data
        print("\nSeeding test data...")
        signals = create_test_signals(db, args.signals, user_id)
        orders = create_test_orders(db, args.orders, user_id)
        notifications = create_test_notifications(db, args.notifications, user_id)

        print("\n✓ Successfully seeded test data:")
        print(f"  - {len(signals)} signals")
        print(f"  - {len(orders)} orders")
        print(f"  - {len(notifications)} notifications")

    except Exception as e:
        print(f"✗ Error seeding test data: {e}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
