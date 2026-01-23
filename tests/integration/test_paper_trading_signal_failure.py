"""
Integration tests for Phase 1: Paper trading order failure integration

Tests that paper trading order failures sync to database and trigger signal FAILED status.
"""

from unittest.mock import patch

import pytest

from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.domain import Money, Order, OrderType, TransactionType
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.paper_trading_adapter import (
    PaperTradingBrokerAdapter,
)
from src.infrastructure.db.models import Orders, OrderStatus, Signals, SignalStatus
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.signals_repository import SignalsRepository


@pytest.fixture
def orders_repo(db_session):
    return OrdersRepository(db_session)


@pytest.fixture
def signals_repo(db_session):
    return SignalsRepository(db_session)


@pytest.fixture
def test_user(db_session):
    from src.infrastructure.db.models import Users

    user = Users(email="paper_test@example.com", password_hash="test_hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def paper_broker_adapter(db_session, test_user):
    """Create paper trading broker adapter with db_session"""
    config = PaperTradingConfig.default()
    return PaperTradingBrokerAdapter(user_id=test_user.id, config=config, db_session=db_session)


@pytest.fixture
def test_signal(db_session, test_user):
    """Create a test signal"""
    signal = Signals(symbol="RELIANCE", status=SignalStatus.ACTIVE, ts=ist_now())
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    return signal


class TestPaperTradingOrderFailureSync:
    """Test that paper trading order failures sync to database"""

    def test_order_rejection_syncs_to_database(
        self, paper_broker_adapter, orders_repo, signals_repo, test_user, test_signal, db_session
    ):
        """Test that rejected order syncs to database"""
        # Mark signal as traded first (required for FAILED status)
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id, reason="order_placed")

        # Create database order
        db_order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="limit",
            quantity=10,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="PAPER_ORDER_123",
        )
        db_session.add(db_order)
        db_session.commit()
        db_session.refresh(db_order)

        # Create paper trading order
        paper_order = Order(
            order_id="PAPER_ORDER_123",
            symbol="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            price=Money(2500.0),
            order_type=OrderType.LIMIT,
        )
        # Add user_id as attribute (used by sync method)
        paper_order.user_id = test_user.id

        # Simulate order rejection
        with patch.object(paper_broker_adapter, "_save_order"):
            paper_broker_adapter._sync_order_failure_to_db(
                paper_order, "rejected", "Insufficient funds"
            )

        # Verify database order was updated
        db_session.refresh(db_order)
        assert db_order.status == OrderStatus.FAILED

        # Verify signal was marked as FAILED
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status is not None
        assert user_status == SignalStatus.FAILED

    def test_order_failure_syncs_to_database(
        self, paper_broker_adapter, orders_repo, signals_repo, test_user, test_signal, db_session
    ):
        """Test that failed order syncs to database"""
        # Mark signal as traded first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id, reason="order_placed")

        # Create database order
        db_order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="limit",
            quantity=10,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="PAPER_ORDER_456",
        )
        db_session.add(db_order)
        db_session.commit()
        db_session.refresh(db_order)

        # Create paper trading order
        paper_order = Order(
            order_id="PAPER_ORDER_456",
            symbol="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            price=Money(2500.0),
            order_type=OrderType.LIMIT,
        )
        paper_order.user_id = test_user.id

        # Simulate order failure
        with patch.object(paper_broker_adapter, "_save_order"):
            paper_broker_adapter._sync_order_failure_to_db(
                paper_order, "failed", "Execution failed"
            )

        # Verify database order was updated
        db_session.refresh(db_order)
        assert db_order.status == OrderStatus.FAILED

    def test_order_cancellation_syncs_to_database(
        self, paper_broker_adapter, orders_repo, signals_repo, test_user, test_signal, db_session
    ):
        """Test that cancelled order syncs to database"""
        # Mark signal as traded first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id, reason="order_placed")

        # Create database order
        db_order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="limit",
            quantity=10,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="PAPER_ORDER_789",
        )
        db_session.add(db_order)
        db_session.commit()
        db_session.refresh(db_order)

        # Create paper trading order
        paper_order = Order(
            order_id="PAPER_ORDER_789",
            symbol="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            price=Money(2500.0),
            order_type=OrderType.LIMIT,
        )
        paper_order.user_id = test_user.id

        # Simulate order cancellation
        with patch.object(paper_broker_adapter, "_save_order"):
            paper_broker_adapter._sync_order_failure_to_db(
                paper_order, "cancelled", "User cancelled"
            )

        # Verify database order was updated
        db_session.refresh(db_order)
        assert db_order.status == OrderStatus.CANCELLED

    def test_sync_graceful_degradation_no_db_session(self, test_user):
        """Test that sync works gracefully when db_session is None"""
        # Create adapter without db_session
        config = PaperTradingConfig.default()
        adapter = PaperTradingBrokerAdapter(user_id=test_user.id, config=config, db_session=None)

        # Create paper trading order
        paper_order = Order(
            order_id="PAPER_ORDER_999",
            symbol="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            price=Money(2500.0),
            order_type=OrderType.LIMIT,
        )
        paper_order.user_id = test_user.id

        # Should not raise exception
        adapter._sync_order_failure_to_db(paper_order, "rejected", "Test rejection")
        # If we get here, graceful degradation worked

    def test_sync_graceful_degradation_order_not_found(self, paper_broker_adapter, test_user):
        """Test that sync works gracefully when database order doesn't exist"""
        # Create paper trading order with non-existent broker_order_id
        paper_order = Order(
            order_id="NON_EXISTENT_ORDER",
            symbol="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            price=Money(2500.0),
            order_type=OrderType.LIMIT,
        )
        paper_order.user_id = test_user.id

        # Should not raise exception
        with patch.object(paper_broker_adapter, "_save_order"):
            paper_broker_adapter._sync_order_failure_to_db(
                paper_order, "rejected", "Test rejection"
            )
        # If we get here, graceful degradation worked

    def test_sync_handles_database_error_gracefully(
        self, paper_broker_adapter, test_user, db_session
    ):
        """Test that sync handles database errors gracefully"""
        # Create paper trading order
        paper_order = Order(
            order_id="ERROR_ORDER",
            symbol="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            price=Money(2500.0),
            order_type=OrderType.LIMIT,
        )
        paper_order.user_id = test_user.id

        # Mock database error
        with patch.object(
            OrdersRepository, "get_by_broker_order_id", side_effect=Exception("DB Error")
        ):
            # Should not raise exception
            paper_broker_adapter._sync_order_failure_to_db(
                paper_order, "rejected", "Test rejection"
            )
        # If we get here, error handling worked


class TestPaperTradingSignalFailedStatus:
    """Test that paper trading order failures trigger signal FAILED status"""

    def test_order_failure_triggers_signal_failed(
        self, paper_broker_adapter, orders_repo, signals_repo, test_user, test_signal, db_session
    ):
        """Test that order failure triggers signal FAILED status"""
        # Mark signal as traded first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id, reason="order_placed")

        # Verify signal is TRADED
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED

        # Create database order
        db_order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="limit",
            quantity=10,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="PAPER_FAIL_ORDER",
        )
        db_session.add(db_order)
        db_session.commit()
        db_session.refresh(db_order)

        # Create paper trading order
        paper_order = Order(
            order_id="PAPER_FAIL_ORDER",
            symbol="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=10,
            price=Money(2500.0),
            order_type=OrderType.LIMIT,
        )
        paper_order.user_id = test_user.id

        # Simulate order failure
        with patch.object(paper_broker_adapter, "_save_order"):
            paper_broker_adapter._sync_order_failure_to_db(
                paper_order, "failed", "Order execution failed"
            )

        # Verify signal is now FAILED
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED
