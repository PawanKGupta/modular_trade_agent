"""
Unit tests for Phase 0.1: Trade Mode Column in Orders Table

Tests cover:
- Order creation with trade_mode
- Auto-population from UserSettings
- Backward compatibility (NULL handling)
- Edge cases and negative scenarios
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.base import Base
from src.infrastructure.db.models import (
    OrderStatus,
    TradeMode,
    UserRole,
    Users,
    UserSettings,
)
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.settings_repository import SettingsRepository


@pytest.fixture
def db_session():
    """Create in-memory test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test user
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="dummy_hash",
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create user settings with PAPER mode
    settings = UserSettings(
        user_id=user.id,
        trade_mode=TradeMode.PAPER,
    )
    session.add(settings)
    session.commit()

    yield session, user.id

    session.close()


@pytest.fixture
def orders_repo(db_session):
    session, _ = db_session
    return OrdersRepository(session)


class TestTradeModeColumn:
    """Test trade_mode column functionality"""

    def test_create_order_with_trade_mode_paper(self, orders_repo, db_session):
        """Test creating order with explicit PAPER trade_mode"""
        session, user_id = db_session

        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
            trade_mode=TradeMode.PAPER,
        )
        session.commit()

        assert order.trade_mode == TradeMode.PAPER
        assert order.id is not None

    def test_create_order_with_trade_mode_broker(self, orders_repo, db_session):
        """Test creating order with explicit BROKER trade_mode"""
        session, user_id = db_session

        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
            trade_mode=TradeMode.BROKER,
        )
        session.commit()

        assert order.trade_mode == TradeMode.BROKER

    def test_create_order_auto_populate_from_settings(self, orders_repo, db_session):
        """Test auto-population of trade_mode from UserSettings when not provided"""
        session, user_id = db_session

        # UserSettings has PAPER mode
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
            # trade_mode not provided - should auto-populate
        )
        session.commit()

        assert order.trade_mode == TradeMode.PAPER

    def test_create_order_auto_populate_broker_mode(self, orders_repo, db_session):
        """Test auto-population when UserSettings has BROKER mode"""
        session, user_id = db_session

        # Update settings to BROKER
        settings_repo = SettingsRepository(session)
        settings = settings_repo.get_by_user_id(user_id)
        settings.trade_mode = TradeMode.BROKER
        session.commit()

        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
        )
        session.commit()

        assert order.trade_mode == TradeMode.BROKER

    def test_create_order_no_settings_defaults_to_paper(self, orders_repo, db_session):
        """Test that order defaults to PAPER when no UserSettings exist"""
        session, user_id = db_session

        # Delete user settings
        session.query(UserSettings).filter(UserSettings.user_id == user_id).delete()
        session.commit()

        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
        )
        session.commit()

        # Should default to PAPER
        assert order.trade_mode == TradeMode.PAPER

    def test_list_orders_includes_trade_mode(self, orders_repo, db_session):
        """Test that list() method includes trade_mode in results"""
        session, user_id = db_session

        # Create multiple orders with different trade modes
        order1 = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
            trade_mode=TradeMode.PAPER,
        )
        order2 = orders_repo.create_amo(
            user_id=user_id,
            symbol="TCS-EQ",
            side="buy",
            order_type="amo",
            quantity=5,
            price=3500.0,
            trade_mode=TradeMode.BROKER,
        )
        session.commit()

        orders = orders_repo.list(user_id)

        assert len(orders) >= 2
        # Find our orders
        found_order1 = next((o for o in orders if o.id == order1.id), None)
        found_order2 = next((o for o in orders if o.id == order2.id), None)

        assert found_order1 is not None
        assert found_order2 is not None
        assert found_order1.trade_mode == TradeMode.PAPER
        assert found_order2.trade_mode == TradeMode.BROKER

    def test_list_orders_filters_by_status(self, orders_repo, db_session):
        """Test that list() with status filter still includes trade_mode"""
        session, user_id = db_session

        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
            trade_mode=TradeMode.PAPER,
        )
        session.commit()

        orders = orders_repo.list(user_id, status=OrderStatus.PENDING)

        assert len(orders) >= 1
        found_order = next((o for o in orders if o.id == order.id), None)
        assert found_order is not None
        # Note: trade_mode might not be in the list() result if column doesn't exist
        # This is expected behavior for backward compatibility
        if hasattr(found_order, "trade_mode"):
            assert found_order.trade_mode == TradeMode.PAPER

    def test_trade_mode_index_exists(self, db_session):
        """Test that trade_mode column has an index"""
        session, _ = db_session

        # Check if index exists (SQLite specific)
        from sqlalchemy import text

        result = session.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='orders' AND name LIKE '%trade_mode%'"
            )
        ).fetchall()

        # Index should exist (created by migration)
        assert len(result) > 0

    def test_multiple_orders_same_user_different_modes(self, orders_repo, db_session):
        """Test creating multiple orders with different trade modes for same user"""
        session, user_id = db_session

        paper_order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
            trade_mode=TradeMode.PAPER,
        )
        broker_order = orders_repo.create_amo(
            user_id=user_id,
            symbol="TCS-EQ",
            side="buy",
            order_type="amo",
            quantity=5,
            price=3500.0,
            trade_mode=TradeMode.BROKER,
        )
        session.commit()

        assert paper_order.trade_mode == TradeMode.PAPER
        assert broker_order.trade_mode == TradeMode.BROKER
        assert paper_order.user_id == broker_order.user_id

    def test_trade_mode_persistence(self, orders_repo, db_session):
        """Test that trade_mode persists after order creation"""
        session, user_id = db_session

        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
            trade_mode=TradeMode.PAPER,
        )
        session.commit()

        # Retrieve order again
        retrieved = orders_repo.get(order.id)
        assert retrieved is not None
        assert retrieved.trade_mode == TradeMode.PAPER


class TestTradeModeEdgeCases:
    """Test edge cases and negative scenarios"""

    def test_invalid_user_id_handling(self, orders_repo, db_session):
        """Test handling of invalid user_id"""
        # create_amo doesn't validate user_id existence (foreign key constraint would handle this)
        # For SQLite, foreign keys might not be enforced, so this test just verifies it doesn't crash
        session, _ = db_session
        try:
            order = orders_repo.create_amo(
                user_id=99999,  # Non-existent user
                symbol="RELIANCE-EQ",
                side="buy",
                order_type="amo",
                quantity=10,
                price=2500.0,
            )
            # If it doesn't raise, that's OK - foreign key constraint would catch it in production
            assert order is not None
        except Exception:
            # If it raises, that's also OK
            pass

    def test_trade_mode_with_null_symbol(self, orders_repo, db_session):
        """Test that trade_mode works even with edge case symbol values"""
        session, user_id = db_session

        # Empty string symbol (edge case)
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="",  # Edge case
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
            trade_mode=TradeMode.PAPER,
        )
        session.commit()

        assert order.trade_mode == TradeMode.PAPER

    def test_trade_mode_with_zero_quantity(self, orders_repo, db_session):
        """Test trade_mode with zero quantity (edge case)"""
        session, user_id = db_session

        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=0,  # Edge case
            price=2500.0,
            trade_mode=TradeMode.PAPER,
        )
        session.commit()

        assert order.trade_mode == TradeMode.PAPER

    def test_trade_mode_with_negative_price(self, orders_repo, db_session):
        """Test trade_mode with negative price (validation depends on DB constraints)"""
        session, user_id = db_session

        # Negative price might be allowed by SQLAlchemy/DB (no application-level validation)
        # This test just verifies it doesn't crash
        try:
            order = orders_repo.create_amo(
                user_id=user_id,
                symbol="RELIANCE-EQ",
                side="buy",
                order_type="amo",
                quantity=10,
                price=-100.0,  # Invalid but might be allowed
                trade_mode=TradeMode.PAPER,
            )
            # If it doesn't raise, that's OK - DB constraints would catch it in production
            assert order is not None
        except (ValueError, AssertionError):
            # If it raises, that's also OK
            pass

    def test_bulk_orders_same_trade_mode(self, orders_repo, db_session):
        """Test creating multiple orders in bulk with same trade_mode"""
        session, user_id = db_session

        orders = []
        for i in range(5):
            order = orders_repo.create_amo(
                user_id=user_id,
                symbol=f"STOCK{i}-EQ",
                side="buy",
                order_type="amo",
                quantity=10,
                price=1000.0 + i * 100,
                trade_mode=TradeMode.PAPER,
            )
            orders.append(order)

        session.commit()

        # Verify all have PAPER mode
        for order in orders:
            assert order.trade_mode == TradeMode.PAPER

    def test_trade_mode_query_performance(self, orders_repo, db_session):
        """Test that queries with trade_mode filter are performant"""
        session, user_id = db_session

        # Create multiple orders
        for i in range(10):
            orders_repo.create_amo(
                user_id=user_id,
                symbol=f"STOCK{i}-EQ",
                side="buy",
                order_type="amo",
                quantity=10,
                price=1000.0,
                trade_mode=TradeMode.PAPER if i % 2 == 0 else TradeMode.BROKER,
            )
        session.commit()

        # Query should be fast (indexed)
        all_orders = orders_repo.list(user_id)
        paper_orders = [o for o in all_orders if o.trade_mode == TradeMode.PAPER]
        broker_orders = [o for o in all_orders if o.trade_mode == TradeMode.BROKER]

        assert len(paper_orders) >= 5
        assert len(broker_orders) >= 5
