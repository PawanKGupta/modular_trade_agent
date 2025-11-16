"""
Integration tests for data migration scripts

Tests cover:
- trades_history.json migration
- pending_orders.json migration
- paper_trading data migration
- Validation
- Rollback
"""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts.migration.migrate_paper_trading import (
    migrate_paper_trading_holdings,
    migrate_paper_trading_orders,
)
from scripts.migration.migrate_pending_orders import migrate_pending_orders

# Import migration functions
from scripts.migration.migrate_trades_history import migrate_trades_history
from scripts.migration.rollback_migration import (
    rollback_trades_history,
)
from scripts.migration.validate_migration import (
    validate_trades_history,
)
from src.infrastructure.db.models import Fills, Orders, OrderStatus, Positions


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    from src.infrastructure.db.models import UserRole, Users

    user = Users(
        email="migration_test@example.com",
        name="Migration Test User",
        password_hash="hashed_password",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def temp_data_dir():
    """Create temporary directory for test data files"""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestTradesHistoryMigration:
    """Tests for trades_history.json migration"""

    def test_migrate_empty_trades_history(self, db_session, sample_user, temp_data_dir):
        """Test migrating empty trades_history.json"""
        trades_file = temp_data_dir / "trades_history.json"
        trades_file.write_text(json.dumps({"trades": [], "failed_orders": [], "last_run": None}))

        stats = migrate_trades_history(
            db=db_session,
            trades_history_path=str(trades_file),
            user_id=sample_user.id,
            dry_run=False,
        )

        assert stats["trades_processed"] == 0
        assert stats["orders_created"] == 0
        assert stats["fills_created"] == 0
        assert len(stats["errors"]) == 0

    def test_migrate_single_trade(self, db_session, sample_user, temp_data_dir):
        """Test migrating a single trade"""
        trade = {
            "symbol": "RELIANCE",
            "ticker": "RELIANCE.NS",
            "entry_price": 2450.0,
            "qty": 10,
            "entry_time": "2025-10-27T09:15:00",
            "status": "open",
        }
        trades_file = temp_data_dir / "trades_history.json"
        trades_file.write_text(
            json.dumps({"trades": [trade], "failed_orders": [], "last_run": None})
        )

        stats = migrate_trades_history(
            db=db_session,
            trades_history_path=str(trades_file),
            user_id=sample_user.id,
            dry_run=False,
        )

        assert stats["trades_processed"] == 1
        assert stats["orders_created"] == 1  # Buy order
        assert stats["fills_created"] == 1
        assert len(stats["errors"]) == 0

        # Verify order in DB
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        assert len(orders) == 1
        order = orders[0]
        assert order.symbol == "RELIANCE"
        assert order.side == "buy"
        assert order.quantity == 10
        assert order.avg_price == 2450.0
        assert order.status == OrderStatus.ONGOING

        # Verify fill
        fills = db_session.query(Fills).join(Orders).filter(Orders.id == order.id).all()
        assert len(fills) == 1
        assert fills[0].qty == 10
        assert fills[0].price == 2450.0

    def test_migrate_closed_trade(self, db_session, sample_user, temp_data_dir):
        """Test migrating a closed trade (buy + sell)"""
        trade = {
            "symbol": "TCS",
            "entry_price": 3850.0,
            "qty": 5,
            "entry_time": "2025-10-27T09:15:00",
            "status": "closed",
            "exit_price": 3900.0,
            "exit_time": "2025-10-27T15:30:00",
        }
        trades_file = temp_data_dir / "trades_history.json"
        trades_file.write_text(
            json.dumps({"trades": [trade], "failed_orders": [], "last_run": None})
        )

        stats = migrate_trades_history(
            db=db_session,
            trades_history_path=str(trades_file),
            user_id=sample_user.id,
            dry_run=False,
        )

        assert stats["trades_processed"] == 1
        assert stats["orders_created"] == 2  # Buy + Sell
        assert stats["fills_created"] == 2
        assert len(stats["errors"]) == 0

        # Verify orders
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        assert len(orders) == 2
        buy_order = next(o for o in orders if o.side == "buy")
        sell_order = next(o for o in orders if o.side == "sell")
        assert buy_order.avg_price == 3850.0
        assert sell_order.avg_price == 3900.0
        assert sell_order.status == OrderStatus.CLOSED

    def test_dry_run(self, db_session, sample_user, temp_data_dir):
        """Test dry run doesn't commit changes"""
        trade = {
            "symbol": "INFY",
            "entry_price": 1520.0,
            "qty": 15,
            "entry_time": "2025-10-27T09:15:00",
            "status": "open",
        }
        trades_file = temp_data_dir / "trades_history.json"
        trades_file.write_text(
            json.dumps({"trades": [trade], "failed_orders": [], "last_run": None})
        )

        stats = migrate_trades_history(
            db=db_session,
            trades_history_path=str(trades_file),
            user_id=sample_user.id,
            dry_run=True,
        )

        assert stats["orders_created"] == 1

        # Verify no data in DB (dry run rolled back)
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        assert len(orders) == 0


class TestPendingOrdersMigration:
    """Tests for pending_orders.json migration"""

    def test_migrate_pending_order(self, db_session, sample_user, temp_data_dir):
        """Test migrating a pending order"""
        order = {
            "order_id": "12345",
            "symbol": "RELIANCE-EQ",
            "ticker": "RELIANCE.NS",
            "qty": 10,
            "order_type": "MARKET",
            "variety": "AMO",
            "price": 0.0,
            "placed_at": "2025-10-27T09:15:00",
            "status": "PENDING",
        }
        orders_file = temp_data_dir / "pending_orders.json"
        orders_file.write_text(json.dumps({"orders": [order]}))

        stats = migrate_pending_orders(
            db=db_session,
            pending_orders_path=str(orders_file),
            user_id=sample_user.id,
            dry_run=False,
        )

        assert stats["orders_processed"] == 1
        assert stats["orders_created"] == 1
        assert len(stats["errors"]) == 0

        # Verify order in DB
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        assert len(orders) == 1
        db_order = orders[0]
        assert db_order.symbol == "RELIANCE"
        assert db_order.broker_order_id == "12345"
        assert db_order.status == OrderStatus.AMO

    def test_skip_duplicate_orders(self, db_session, sample_user, temp_data_dir):
        """Test that duplicate orders are skipped"""
        order = {
            "order_id": "12345",
            "symbol": "RELIANCE",
            "qty": 10,
            "placed_at": "2025-10-27T09:15:00",
            "status": "PENDING",
        }
        orders_file = temp_data_dir / "pending_orders.json"
        orders_file.write_text(json.dumps({"orders": [order, order]}))  # Duplicate

        stats = migrate_pending_orders(
            db=db_session,
            pending_orders_path=str(orders_file),
            user_id=sample_user.id,
            dry_run=False,
        )

        assert stats["orders_created"] == 1  # Only one created
        assert len(stats["skipped"]) == 1  # One skipped as duplicate


class TestPaperTradingMigration:
    """Tests for paper trading data migration"""

    def test_migrate_paper_trading_orders(self, db_session, sample_user, temp_data_dir):
        """Test migrating paper trading orders"""
        orders = [
            {
                "order_id": "paper_001",
                "symbol": "RELIANCE",
                "side": "buy",
                "quantity": 10,
                "price": 2450.0,
                "order_type": "MARKET",
                "status": "COMPLETE",
                "timestamp": "2025-10-27T09:15:00",
            }
        ]
        orders_file = temp_data_dir / "orders.json"
        orders_file.write_text(json.dumps(orders))

        stats = migrate_paper_trading_orders(
            db=db_session, orders_path=str(orders_file), user_id=sample_user.id, dry_run=False
        )

        assert stats["orders_processed"] == 1
        assert stats["orders_created"] == 1

        # Verify order
        db_orders = (
            db_session.query(Orders)
            .filter(Orders.user_id == sample_user.id, Orders.orig_source == "paper_trading")
            .all()
        )
        assert len(db_orders) == 1
        assert db_orders[0].order_id == "paper_001"

    def test_migrate_paper_trading_holdings(self, db_session, sample_user, temp_data_dir):
        """Test migrating paper trading holdings"""
        holdings = {"RELIANCE": {"quantity": 10, "avg_price": 2450.0, "unrealized_pnl": 500.0}}
        holdings_file = temp_data_dir / "holdings.json"
        holdings_file.write_text(json.dumps(holdings))

        stats = migrate_paper_trading_holdings(
            db=db_session, holdings_path=str(holdings_file), user_id=sample_user.id, dry_run=False
        )

        assert stats["holdings_processed"] == 1
        assert stats["positions_created"] == 1

        # Verify position
        positions = db_session.query(Positions).filter(Positions.user_id == sample_user.id).all()
        assert len(positions) == 1
        assert positions[0].symbol == "RELIANCE"
        assert positions[0].quantity == 10
        assert positions[0].avg_price == 2450.0


class TestValidation:
    """Tests for validation scripts"""

    def test_validate_trades_history(self, db_session, sample_user, temp_data_dir):
        """Test validating trades_history migration"""
        # Create a trade in DB
        order = Orders(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            quantity=10,
            status=OrderStatus.ONGOING,
            avg_price=2450.0,
            placed_at=datetime(2025, 10, 27, 9, 15, 0),
            filled_at=datetime(2025, 10, 27, 9, 15, 0),
            orig_source="signal",
        )
        db_session.add(order)
        db_session.commit()

        # Create matching trades_history.json
        trade = {
            "symbol": "RELIANCE",
            "entry_price": 2450.0,
            "qty": 10,
            "entry_time": "2025-10-27T09:15:00",
            "status": "open",
        }
        trades_file = temp_data_dir / "trades_history.json"
        trades_file.write_text(
            json.dumps({"trades": [trade], "failed_orders": [], "last_run": None})
        )

        results = validate_trades_history(
            db=db_session, trades_history_path=str(trades_file), user_id=sample_user.id
        )

        assert results["valid"] is True
        assert results["stats"]["source_trades"] == 1
        assert results["stats"]["db_orders"] == 1


class TestRollback:
    """Tests for rollback scripts"""

    def test_rollback_trades_history(self, db_session, sample_user):
        """Test rolling back trades_history migration"""
        # Create migrated order
        order = Orders(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            quantity=10,
            status=OrderStatus.ONGOING,
            orig_source="signal",
        )
        db_session.add(order)
        db_session.flush()

        fill = Fills(order_id=order.id, qty=10, price=2450.0, ts=datetime.utcnow())
        db_session.add(fill)
        db_session.commit()

        # Rollback
        stats = rollback_trades_history(db_session, sample_user.id, dry_run=False)

        assert stats["orders_deleted"] == 1
        assert stats["fills_deleted"] == 1

        # Verify deletion
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        assert len(orders) == 0
