"""
Integration tests for fix_missed_entry_type.py script

Tests verify that the script correctly updates orders that were incorrectly
marked as "manual" but were actually system initial entries.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.fix_missed_entry_type import fix_missed_entry_type  # noqa: E402
from src.infrastructure.db.base import Base  # noqa: E402
from src.infrastructure.db.models import Orders, OrderStatus, UserRole, Users  # noqa: E402


@pytest.fixture
def db_session():
    """Create in-memory test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test users
    user1 = Users(
        email="test1@example.com",
        name="Test User 1",
        password_hash="dummy_hash",
        role=UserRole.USER,
        is_active=True,
    )
    user2 = Users(
        email="test2@example.com",
        name="Test User 2",
        password_hash="dummy_hash",
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user1)
    session.add(user2)
    session.commit()
    session.refresh(user1)
    session.refresh(user2)

    yield session, user1.id, user2.id

    session.close()


class TestFixMissedEntryType:
    """Test fix_missed_entry_type script"""

    def test_fix_missed_entry_type_dry_run_identifies_orders(self, db_session):
        """Test that dry run identifies orders that need fixing"""
        session, user1_id, user2_id = db_session

        # Create orders that should be fixed (have "missed" in reason)
        order1 = Orders(
            user_id=user1_id,
            symbol="ASTERDM-EQ",
            side="buy",
            order_type="market",
            quantity=16,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="System entry (missed): Position added from broker account due to service downtime",
        )
        session.add(order1)

        # Create order that should NOT be fixed (no "missed" in reason)
        order2 = Orders(
            user_id=user1_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="Manual entry by user",
        )
        session.add(order2)

        # Create order that should NOT be fixed (already correct)
        order3 = Orders(
            user_id=user1_id,
            symbol="TCS-EQ",
            side="buy",
            order_type="market",
            quantity=5,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="initial",
            orig_source="signal",
            reason="System entry",
        )
        session.add(order3)

        session.commit()

        # Run dry run
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=True)

        # Verify no changes were made (dry run)
        session.refresh(order1)
        assert order1.entry_type == "manual"
        assert order1.orig_source == "manual"

        session.refresh(order2)
        assert order2.entry_type == "manual"
        assert order2.orig_source == "manual"

        session.refresh(order3)
        assert order3.entry_type == "initial"
        assert order3.orig_source == "signal"

    def test_fix_missed_entry_type_updates_orders_with_missed_reason(self, db_session):
        """Test that script updates orders with 'missed' in reason"""
        session, user1_id, _ = db_session

        # Create order with "missed" in reason
        order = Orders(
            user_id=user1_id,
            symbol="ASTERDM-EQ",
            side="buy",
            order_type="market",
            quantity=16,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="System entry (missed): Position added from broker account due to service downtime",
        )
        session.add(order)
        session.commit()

        # Run script with apply
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=False)

        # Verify order was updated
        session.refresh(order)
        assert order.entry_type == "initial"
        assert order.orig_source == "signal"
        assert "missed" in order.reason.lower()

    def test_fix_missed_entry_type_updates_orders_with_service_downtime_reason(self, db_session):
        """Test that script updates orders with 'service' or 'downtime' in reason"""
        session, user1_id, _ = db_session

        # Create order with "service" in reason
        order1 = Orders(
            user_id=user1_id,
            symbol="EMKAY-BE",
            side="buy",
            order_type="market",
            quantity=376,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="Position added due to service downtime",
        )
        session.add(order1)

        # Create order with "downtime" in reason
        order2 = Orders(
            user_id=user1_id,
            symbol="TEST-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="System entry missed during downtime",
        )
        session.add(order2)

        session.commit()

        # Run script with apply
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=False)

        # Verify orders were updated
        session.refresh(order1)
        assert order1.entry_type == "initial"
        assert order1.orig_source == "signal"
        assert "System entry (missed):" in order1.reason  # Reason should be updated

        session.refresh(order2)
        assert order2.entry_type == "initial"
        assert order2.orig_source == "signal"

    def test_fix_missed_entry_type_ignores_orders_without_keywords(self, db_session):
        """Test that script ignores orders without 'missed', 'service', or 'downtime' in reason"""
        session, user1_id, _ = db_session

        # Create order without keywords
        order = Orders(
            user_id=user1_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="Manual entry by user",
        )
        session.add(order)
        session.commit()

        # Run script with apply
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=False)

        # Verify order was NOT updated
        session.refresh(order)
        assert order.entry_type == "manual"
        assert order.orig_source == "manual"
        assert order.reason == "Manual entry by user"

    def test_fix_missed_entry_type_ignores_already_correct_orders(self, db_session):
        """Test that script ignores orders that are already correct"""
        session, user1_id, _ = db_session

        # Create order that's already correct
        order = Orders(
            user_id=user1_id,
            symbol="TCS-EQ",
            side="buy",
            order_type="market",
            quantity=5,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="initial",
            orig_source="signal",
            reason="System entry",
        )
        session.add(order)
        session.commit()

        # Run script with apply
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=False)

        # Verify order was NOT changed
        session.refresh(order)
        assert order.entry_type == "initial"
        assert order.orig_source == "signal"

    def test_fix_missed_entry_type_ignores_sell_orders(self, db_session):
        """Test that script only processes buy orders"""
        session, user1_id, _ = db_session

        # Create sell order with "missed" in reason
        order = Orders(
            user_id=user1_id,
            symbol="ASTERDM-EQ",
            side="sell",
            order_type="limit",
            quantity=16,
            price=600.0,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="System entry (missed): Position added from broker account",
        )
        session.add(order)
        session.commit()

        # Run script with apply
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=False)

        # Verify sell order was NOT updated
        session.refresh(order)
        assert order.entry_type == "manual"
        assert order.orig_source == "manual"

    def test_fix_missed_entry_type_filters_by_user_id(self, db_session):
        """Test that script can filter by user_id"""
        session, user1_id, user2_id = db_session

        # Create orders for both users
        order1 = Orders(
            user_id=user1_id,
            symbol="ASTERDM-EQ",
            side="buy",
            order_type="market",
            quantity=16,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="System entry (missed): Position added from broker account",
        )
        order2 = Orders(
            user_id=user2_id,
            symbol="EMKAY-BE",
            side="buy",
            order_type="market",
            quantity=376,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="System entry (missed): Position added from broker account",
        )
        session.add(order1)
        session.add(order2)
        session.commit()

        # Run script for user1 only
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=False)

        # Verify only user1's order was updated
        session.refresh(order1)
        assert order1.entry_type == "initial"
        assert order1.orig_source == "signal"

        session.refresh(order2)
        assert order2.entry_type == "manual"
        assert order2.orig_source == "manual"

    def test_fix_missed_entry_type_updates_all_users_when_user_id_none(self, db_session):
        """Test that script updates all users when user_id is None"""
        session, user1_id, user2_id = db_session

        # Create orders for both users
        order1 = Orders(
            user_id=user1_id,
            symbol="ASTERDM-EQ",
            side="buy",
            order_type="market",
            quantity=16,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="System entry (missed): Position added from broker account",
        )
        order2 = Orders(
            user_id=user2_id,
            symbol="EMKAY-BE",
            side="buy",
            order_type="market",
            quantity=376,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="System entry (missed): Position added from broker account",
        )
        session.add(order1)
        session.add(order2)
        session.commit()

        # Run script for all users
        fix_missed_entry_type(db=session, user_id=None, dry_run=False)

        # Verify both orders were updated
        session.refresh(order1)
        assert order1.entry_type == "initial"
        assert order1.orig_source == "signal"

        session.refresh(order2)
        assert order2.entry_type == "initial"
        assert order2.orig_source == "signal"

    def test_fix_missed_entry_type_updates_reason_when_missing_missed_keyword(self, db_session):
        """Test that script updates reason to include 'missed' if not present"""
        session, user1_id, _ = db_session

        # Create order with "service" but not "missed"
        order = Orders(
            user_id=user1_id,
            symbol="TEST-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="Position added due to service downtime",
        )
        session.add(order)
        session.commit()

        # Run script with apply
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=False)

        # Verify order was updated and reason includes "missed"
        session.refresh(order)
        assert order.entry_type == "initial"
        assert order.orig_source == "signal"
        assert "System entry (missed):" in order.reason
        assert "service downtime" in order.reason

    def test_fix_missed_entry_type_preserves_reason_when_missed_already_present(self, db_session):
        """Test that script preserves reason when 'missed' is already present"""
        session, user1_id, _ = db_session

        original_reason = (
            "System entry (missed): Position added from broker account due to service downtime"
        )

        # Create order with "missed" already in reason
        order = Orders(
            user_id=user1_id,
            symbol="ASTERDM-EQ",
            side="buy",
            order_type="market",
            quantity=16,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason=original_reason,
        )
        session.add(order)
        session.commit()

        # Run script with apply
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=False)

        # Verify order was updated but reason preserved (since "missed" already present)
        session.refresh(order)
        assert order.entry_type == "initial"
        assert order.orig_source == "signal"
        # Reason should be preserved as-is when "missed" is already present
        assert order.reason == original_reason

    def test_fix_missed_entry_type_handles_empty_reason(self, db_session):
        """Test that script handles orders with empty or None reason"""
        session, user1_id, _ = db_session

        # Create order with None reason
        order1 = Orders(
            user_id=user1_id,
            symbol="TEST1-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason=None,
        )
        session.add(order1)

        # Create order with empty reason
        order2 = Orders(
            user_id=user1_id,
            symbol="TEST2-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            status=OrderStatus.ONGOING,
            entry_type="manual",
            orig_source="manual",
            reason="",
        )
        session.add(order2)

        session.commit()

        # Run script with apply
        fix_missed_entry_type(db=session, user_id=user1_id, dry_run=False)

        # Verify orders were NOT updated (no keywords in reason)
        session.refresh(order1)
        assert order1.entry_type == "manual"
        assert order1.orig_source == "manual"

        session.refresh(order2)
        assert order2.entry_type == "manual"
        assert order2.orig_source == "manual"
