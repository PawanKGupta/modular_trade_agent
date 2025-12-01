"""
Tests for reentry tracking in Orders table.

Tests the new entry_type field and order_metadata for tracking reentry orders.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.models import Orders, OrderStatus
from src.infrastructure.persistence.orders_repository import OrdersRepository


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    from src.infrastructure.db.models import Base
    
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def orders_repo(db_session):
    """Create OrdersRepository instance"""
    return OrdersRepository(db_session)


@pytest.fixture
def user_id():
    return 1


class TestReentryTrackingInOrders:
    """Test reentry tracking in Orders table"""

    def test_create_amo_with_entry_type_initial(self, orders_repo, user_id):
        """Test creating AMO order with entry_type='initial'"""
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            order_id="ORDER123",
            broker_order_id="BROKER123",
            entry_type="initial",
            order_metadata={"rsi10": 28.5, "ema9": 2500.0},
        )
        
        assert order.entry_type == "initial"
        assert order.order_metadata == {"rsi10": 28.5, "ema9": 2500.0}
        assert order.symbol == "RELIANCE"
        assert order.quantity == 10

    def test_create_amo_with_entry_type_reentry(self, orders_repo, user_id):
        """Test creating AMO order with entry_type='reentry'"""
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=5,
            price=None,
            order_id="ORDER456",
            broker_order_id="BROKER456",
            entry_type="reentry",
            order_metadata={
                "rsi_level": 20,
                "rsi": 19.5,
                "price": 2480.0,
                "reentry_index": 1,
            },
        )
        
        assert order.entry_type == "reentry"
        assert order.order_metadata["rsi_level"] == 20
        assert order.order_metadata["rsi"] == 19.5
        assert order.order_metadata["reentry_index"] == 1

    def test_create_amo_without_entry_type(self, orders_repo, user_id):
        """Test creating AMO order without entry_type (backward compatibility)"""
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            order_id="ORDER789",
            broker_order_id="BROKER789",
        )
        
        assert order.entry_type is None
        assert order.order_metadata is None

    def test_query_reentry_orders(self, orders_repo, user_id):
        """Test querying orders by entry_type='reentry'"""
        # Create initial order
        orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            entry_type="initial",
        )
        
        # Create reentry orders
        for i in range(3):
            orders_repo.create_amo(
                user_id=user_id,
                symbol="RELIANCE",
                side="buy",
                order_type="market",
                quantity=5,
                price=None,
                entry_type="reentry",
                order_metadata={"reentry_index": i + 1},
            )
        
        # Query all orders
        all_orders = orders_repo.list(user_id)
        assert len(all_orders) == 4
        
        # Query reentry orders only
        reentry_orders = [o for o in all_orders if o.entry_type == "reentry"]
        assert len(reentry_orders) == 3
        
        # Verify reentry orders have correct metadata
        # Sort by placed_at to ensure consistent order
        reentry_orders_sorted = sorted(reentry_orders, key=lambda o: o.placed_at)
        for i, order in enumerate(reentry_orders_sorted, 1):
            assert order.entry_type == "reentry"
            assert order.order_metadata["reentry_index"] == i

    def test_reentry_order_metadata_structure(self, orders_repo, user_id):
        """Test that reentry order metadata has all required fields"""
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=5,
            price=None,
            entry_type="reentry",
            order_metadata={
                "rsi_level": 30,
                "rsi": 29.5,
                "price": 2500.0,
                "reentry_index": 1,
            },
        )
        
        metadata = order.order_metadata
        assert "rsi_level" in metadata
        assert "rsi" in metadata
        assert "price" in metadata
        assert "reentry_index" in metadata
        assert metadata["rsi_level"] == 30
        assert metadata["rsi"] == 29.5

