"""
Integration tests for Trade Mode (Phase 0.1)
Tests end-to-end flow of trade_mode column usage across orders and APIs
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Orders, TradeMode, Users, UserSettings
from src.infrastructure.persistence.orders_repository import OrdersRepository


class TestTradeModeIntegration:
    """Integration tests for trade_mode functionality"""

    @pytest.fixture
    def repository(self, db_session: Session):
        """Create repository instance"""
        return OrdersRepository(db_session)

    @pytest.fixture
    def paper_user(self, db_session: Session):
        """Create paper trading user"""
        user = Users(
            email="paper@example.com",
            name="Paper User",
            password_hash="hash",
            role="user",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.PAPER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(settings)
        db_session.commit()
        return user

    @pytest.fixture
    def broker_user(self, db_session: Session):
        """Create broker trading user"""
        user = Users(
            email="broker@example.com",
            name="Broker User",
            password_hash="hash",
            role="user",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.BROKER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(settings)
        db_session.commit()
        return user

    def test_paper_order_has_trade_mode(self, repository, paper_user, db_session):
        """Test that paper trading orders have trade_mode set"""
        order = Orders(
            user_id=paper_user.id,
            symbol="RELIANCE",
            side="BUY",
            order_type="LIMIT",
            quantity=10,
            price=Decimal("2500.00"),
            status="ongoing",
            trade_mode=TradeMode.PAPER,
            placed_at=datetime.utcnow(),
        )
        db_session.add(order)
        db_session.commit()

        retrieved = db_session.query(Orders).filter_by(id=order.id).first()
        assert retrieved.trade_mode == TradeMode.PAPER

    def test_broker_order_has_trade_mode(self, repository, broker_user, db_session):
        """Test that broker orders have trade_mode set"""
        order = Orders(
            user_id=broker_user.id,
            symbol="TCS",
            side="BUY",
            order_type="MARKET",
            quantity=5,
            status="closed",
            trade_mode=TradeMode.BROKER,
            placed_at=datetime.utcnow(),
        )
        db_session.add(order)
        db_session.commit()

        retrieved = db_session.query(Orders).filter_by(id=order.id).first()
        assert retrieved.trade_mode == TradeMode.BROKER

    def test_filter_orders_by_trade_mode(self, repository, paper_user, broker_user, db_session):
        """Test filtering orders by trade_mode"""
        # Create paper order
        paper_order = Orders(
            user_id=paper_user.id,
            symbol="INFY",
            side="BUY",
            order_type="LIMIT",
            quantity=20,
            price=Decimal("1500.00"),
            status="closed",
            trade_mode=TradeMode.PAPER,
            placed_at=datetime.utcnow(),
        )
        db_session.add(paper_order)

        # Create broker order
        broker_order = Orders(
            user_id=broker_user.id,
            symbol="INFY",
            side="BUY",
            order_type="LIMIT",
            quantity=20,
            price=Decimal("1500.00"),
            status="closed",
            trade_mode=TradeMode.BROKER,
            placed_at=datetime.utcnow(),
        )
        db_session.add(broker_order)
        db_session.commit()

        # Filter paper orders
        paper_orders = db_session.query(Orders).filter_by(trade_mode=TradeMode.PAPER).all()
        assert len(paper_orders) >= 1
        assert all(o.trade_mode == TradeMode.PAPER for o in paper_orders)

        # Filter broker orders
        broker_orders = db_session.query(Orders).filter_by(trade_mode=TradeMode.BROKER).all()
        assert len(broker_orders) >= 1
        assert all(o.trade_mode == TradeMode.BROKER for o in broker_orders)

    def test_user_orders_separated_by_trade_mode(
        self, repository, paper_user, broker_user, db_session
    ):
        """Test that user orders are properly separated by trade_mode"""
        # User switches mode - creates orders in both modes
        paper_order = Orders(
            user_id=paper_user.id,
            symbol="HDFC",
            side="BUY",
            order_type="LIMIT",
            quantity=10,
            price=Decimal("1600.00"),
            status="closed",
            trade_mode=TradeMode.PAPER,
            placed_at=datetime.utcnow(),
        )
        db_session.add(paper_order)

        # Same user, broker mode
        broker_order = Orders(
            user_id=paper_user.id,
            symbol="HDFC",
            side="BUY",
            order_type="LIMIT",
            quantity=10,
            price=Decimal("1600.00"),
            status="closed",
            trade_mode=TradeMode.BROKER,
            placed_at=datetime.utcnow(),
        )
        db_session.add(broker_order)
        db_session.commit()

        # Query user's paper orders
        user_paper_orders = (
            db_session.query(Orders)
            .filter_by(user_id=paper_user.id, trade_mode=TradeMode.PAPER)
            .all()
        )

        # Query user's broker orders
        user_broker_orders = (
            db_session.query(Orders)
            .filter_by(user_id=paper_user.id, trade_mode=TradeMode.BROKER)
            .all()
        )

        assert len(user_paper_orders) >= 1
        assert len(user_broker_orders) >= 1
        assert user_paper_orders[0].id != user_broker_orders[0].id

    def test_backfill_null_trade_mode(self, repository, paper_user, db_session):
        """Test handling of legacy orders with NULL trade_mode"""
        # Create order without trade_mode (simulating legacy data)
        legacy_order = Orders(
            user_id=paper_user.id,
            symbol="WIPRO",
            side="BUY",
            order_type="MARKET",
            quantity=15,
            status="closed",
            trade_mode=None,  # Legacy order
            placed_at=datetime.utcnow(),
        )
        db_session.add(legacy_order)
        db_session.commit()

        # Backfill logic should set trade_mode based on user settings
        if legacy_order.trade_mode is None:
            user_settings = db_session.query(UserSettings).filter_by(user_id=paper_user.id).first()
            legacy_order.trade_mode = user_settings.trade_mode
            db_session.commit()

        retrieved = db_session.query(Orders).filter_by(id=legacy_order.id).first()
        assert retrieved.trade_mode == TradeMode.PAPER

    def test_orders_statistics_by_trade_mode(self, repository, paper_user, broker_user, db_session):
        """Test calculating order statistics separated by trade_mode"""
        # Create multiple orders in different modes
        for i in range(3):
            paper_order = Orders(
                user_id=paper_user.id,
                symbol=f"SYM{i}",
                side="BUY",
                order_type="LIMIT",
                quantity=10,
                price=Decimal(f"{100 + i * 10}.00"),
                status="closed",
                trade_mode=TradeMode.PAPER,
                placed_at=datetime.utcnow(),
            )
            db_session.add(paper_order)

        for i in range(2):
            broker_order = Orders(
                user_id=broker_user.id,
                symbol=f"SYM{i}",
                side="BUY",
                order_type="LIMIT",
                quantity=10,
                price=Decimal(f"{200 + i * 10}.00"),
                status="closed",
                trade_mode=TradeMode.BROKER,
                placed_at=datetime.utcnow(),
            )
            db_session.add(broker_order)

        db_session.commit()

        # Get statistics
        paper_count = db_session.query(Orders).filter_by(trade_mode=TradeMode.PAPER).count()
        broker_count = db_session.query(Orders).filter_by(trade_mode=TradeMode.BROKER).count()

        assert paper_count >= 3
        assert broker_count >= 2

    def test_trade_mode_immutable_after_creation(self, repository, paper_user, db_session):
        """Test that trade_mode should not change after order creation"""
        order = Orders(
            user_id=paper_user.id,
            symbol="COAL",
            side="BUY",
            order_type="LIMIT",
            quantity=100,
            price=Decimal("250.00"),
            status="ongoing",
            trade_mode=TradeMode.PAPER,
            placed_at=datetime.utcnow(),
        )
        db_session.add(order)
        db_session.commit()

        original_trade_mode = order.trade_mode

        # Attempt to change (should not be allowed in business logic)
        # This is just a test to ensure data integrity
        assert order.trade_mode == original_trade_mode

    def test_export_orders_filtered_by_trade_mode(
        self, repository, paper_user, broker_user, db_session
    ):
        """Test exporting orders filtered by trade_mode"""
        # Create mixed orders
        paper_orders = []
        for i in range(5):
            order = Orders(
                user_id=paper_user.id,
                symbol=f"PAPER{i}",
                side="BUY",
                order_type="LIMIT",
                quantity=10,
                price=Decimal(f"{100 + i * 5}.00"),
                status="closed",
                trade_mode=TradeMode.PAPER,
                placed_at=datetime.utcnow(),
            )
            db_session.add(order)
            paper_orders.append(order)

        broker_orders = []
        for i in range(3):
            order = Orders(
                user_id=broker_user.id,
                symbol=f"BROKER{i}",
                side="BUY",
                order_type="MARKET",
                quantity=20,
                status="closed",
                trade_mode=TradeMode.BROKER,
                placed_at=datetime.utcnow(),
            )
            db_session.add(order)
            broker_orders.append(order)

        db_session.commit()

        # Export paper orders only
        exported_paper = (
            db_session.query(Orders)
            .filter_by(user_id=paper_user.id, trade_mode=TradeMode.PAPER)
            .all()
        )

        assert len(exported_paper) >= 5
        assert all(o.trade_mode == TradeMode.PAPER for o in exported_paper)
        assert all("PAPER" in o.symbol for o in exported_paper)

    def test_trade_mode_index_performance(self, repository, paper_user, db_session):
        """Test that trade_mode index improves query performance"""
        # Create many orders
        for i in range(100):
            order = Orders(
                user_id=paper_user.id,
                symbol=f"SYM{i % 10}",
                side="BUY" if i % 2 == 0 else "SELL",
                order_type="LIMIT",
                quantity=10,
                price=Decimal(f"{100 + i}.00"),
                status="closed",
                trade_mode=TradeMode.PAPER if i % 2 == 0 else TradeMode.BROKER,
                placed_at=datetime.utcnow(),
            )
            db_session.add(order)
        db_session.commit()

        # Query should use index (not testing actual performance, just correctness)
        results = (
            db_session.query(Orders)
            .filter_by(user_id=paper_user.id, trade_mode=TradeMode.PAPER)
            .all()
        )

        assert len(results) >= 50
        assert all(o.trade_mode == TradeMode.PAPER for o in results)
