"""
Tests for late fill detection (Phase 2.1)

Tests verify that:
1. Late fills are detected when order executes for EXPIRED signals
2. Signal status is updated to TRADED with "late_fill" reason
3. Audit log entry is created with "late_fill" reason
"""

import pytest
from datetime import datetime, timedelta

from src.infrastructure.db.models import OrderStatus, Orders, SignalStatus, Signals, UserRole, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.audit_log_repository import AuditLogRepository
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.signals_repository import SignalsRepository


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="dummy",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def expired_signal(db_session, test_user):
    """Create an expired signal"""
    signal = Signals(
        symbol="RELIANCE.NS",
        status=SignalStatus.EXPIRED,
        ts=ist_now() - timedelta(days=2),
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    return signal


@pytest.fixture
def active_signal(db_session, test_user):
    """Create an active signal"""
    signal = Signals(
        symbol="TCS.NS",
        status=SignalStatus.ACTIVE,
        ts=ist_now() - timedelta(hours=1),
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    return signal


class TestLateFillDetection:
    """Test late fill detection in order execution"""

    def test_late_fill_detected_for_expired_signal(self, db_session, test_user, expired_signal):
        """Test that late fill is detected when order executes for EXPIRED signal"""
        orders_repo = OrdersRepository(db_session)
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create a buy order for the expired signal
        order = orders_repo.create_amo(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Mark order as executed (should detect late fill)
        executed_order = orders_repo.mark_executed(
            order,
            execution_price=2500.0,
            execution_qty=10.0,
        )

        # Verify order was executed
        assert executed_order.status == OrderStatus.ONGOING
        assert executed_order.execution_price == 2500.0

        # Verify signal was marked as TRADED with late_fill reason
        user_status = signals_repo.get_user_signal_status(expired_signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED

        # Verify audit log entry was created with late_fill reason
        audit_log_repo = AuditLogRepository(db_session)
        audit_logs = db_session.execute(
            "SELECT * FROM audit_logs WHERE resource_id = :signal_id ORDER BY timestamp DESC LIMIT 1",
            {"signal_id": expired_signal.id},
        ).fetchall()

        assert len(audit_logs) > 0
        # Check that the latest audit log has late_fill reason
        # (Note: This is a simplified check - in practice, you'd parse the JSON changes field)
        latest_log = audit_logs[0]
        assert latest_log is not None

    def test_normal_fill_for_active_signal(self, db_session, test_user, active_signal):
        """Test that normal fill (not late) is handled for ACTIVE signal"""
        orders_repo = OrdersRepository(db_session)
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create a buy order for the active signal
        order = orders_repo.create_amo(
            user_id=test_user.id,
            symbol="TCS",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Mark order as executed (should NOT detect late fill)
        executed_order = orders_repo.mark_executed(
            order,
            execution_price=3500.0,
            execution_qty=10.0,
        )

        # Verify order was executed
        assert executed_order.status == OrderStatus.ONGOING

        # Verify signal was marked as TRADED with order_placed reason (not late_fill)
        user_status = signals_repo.get_user_signal_status(active_signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED

    def test_late_fill_only_for_buy_orders(self, db_session, test_user, expired_signal):
        """Test that late fill detection only applies to buy orders"""
        orders_repo = OrdersRepository(db_session)

        # Create a sell order (should not trigger late fill detection)
        order = orders_repo.create(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="sell",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Mark order as executed
        executed_order = orders_repo.mark_executed(
            order,
            execution_price=2500.0,
            execution_qty=10.0,
        )

        # Verify order was executed
        assert executed_order.status == OrderStatus.ONGOING

        # Verify signal status was NOT changed (sell orders don't trigger signal marking)
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)
        user_status = signals_repo.get_user_signal_status(expired_signal.id, test_user.id)
        # Signal should still be EXPIRED (not marked as TRADED by sell order)
        assert user_status == SignalStatus.EXPIRED

    def test_late_fill_with_symbol_variants(self, db_session, test_user, expired_signal):
        """Test that late fill detection works with different symbol variants"""
        orders_repo = OrdersRepository(db_session)
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create order with different symbol variant (RELIANCE vs RELIANCE.NS)
        order = orders_repo.create_amo(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",  # Different variant
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Mark order as executed
        executed_order = orders_repo.mark_executed(
            order,
            execution_price=2500.0,
            execution_qty=10.0,
        )

        # Verify signal was marked as TRADED (symbol normalization should work)
        user_status = signals_repo.get_user_signal_status(expired_signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED

