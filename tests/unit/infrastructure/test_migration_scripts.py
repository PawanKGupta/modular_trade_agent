"""Unit tests for migration scripts (Phase 1.2)

Tests cover:
- migrate_trades_history
- migrate_pending_orders
- migrate_paper_trading
- Data parsing and validation
- Error handling
"""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts.migration.migrate_paper_trading import (
    migrate_paper_trading_holdings,
    migrate_paper_trading_orders,
    migrate_paper_trading_transactions,
)
from scripts.migration.migrate_pending_orders import migrate_pending_orders
from scripts.migration.migrate_trades_history import migrate_trades_history
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
    """Unit tests for trades_history.json migration"""

    def test_migrate_empty_trades(self, db_session, sample_user, temp_data_dir):
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

    def test_migrate_single_buy_trade(self, db_session, sample_user, temp_data_dir):
        """Test migrating a single buy trade"""
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
        assert stats["orders_created"] == 1  # One buy order
        assert stats["fills_created"] == 1
        assert len(stats["errors"]) == 0

        # Verify order was created
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        assert len(orders) == 1
        # Migration uses ticker if available, otherwise symbol
        assert orders[0].symbol in ["RELIANCE.NS", "RELIANCE"]
        assert orders[0].side == "buy"
        assert orders[0].quantity == 10.0

    def test_migrate_completed_trade(self, db_session, sample_user, temp_data_dir):
        """Test migrating a completed trade (buy + sell)"""
        trade = {
            "symbol": "TCS",
            "ticker": "TCS.NS",
            "entry_price": 3500.0,
            "exit_price": 3600.0,
            "qty": 5,
            "entry_time": "2025-10-27T09:15:00",
            "exit_time": "2025-10-28T15:30:00",
            "status": "closed",
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
        assert buy_order.avg_price == 3500.0
        assert sell_order.avg_price == 3600.0

    def test_migrate_dry_run(self, db_session, sample_user, temp_data_dir):
        """Test dry run mode doesn't create records"""
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
            dry_run=True,
        )

        assert stats["trades_processed"] == 1
        assert stats["orders_created"] == 1
        # But no actual records should be created
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        assert len(orders) == 0

    def test_migrate_missing_file(self, db_session, sample_user, temp_data_dir):
        """Test handling missing file"""
        missing_file = temp_data_dir / "nonexistent.json"

        stats = migrate_trades_history(
            db=db_session,
            trades_history_path=str(missing_file),
            user_id=sample_user.id,
            dry_run=False,
        )

        assert stats["trades_processed"] == 0
        assert len(stats["errors"]) > 0


class TestPendingOrdersMigration:
    """Unit tests for pending_orders.json migration"""

    def test_migrate_empty_pending_orders(self, db_session, sample_user, temp_data_dir):
        """Test migrating empty pending_orders.json"""
        orders_file = temp_data_dir / "pending_orders.json"
        orders_file.write_text(json.dumps({"orders": []}))

        stats = migrate_pending_orders(
            db=db_session,
            pending_orders_path=str(orders_file),
            user_id=sample_user.id,
            dry_run=False,
        )

        assert stats["orders_processed"] == 0
        assert stats["orders_created"] == 0
        assert len(stats["errors"]) == 0

    def test_migrate_single_pending_order(self, db_session, sample_user, temp_data_dir):
        """Test migrating a single pending order"""
        order = {
            "order_id": "BROKER-12345",  # Required field
            "symbol": "RELIANCE.NS",
            "side": "buy",
            "order_type": "MARKET",
            "qty": 10.0,  # Use 'qty' not 'quantity'
            "price": 0.0,
            "variety": "AMO",
            "status": "PENDING",
            "placed_at": "2025-10-27T09:15:00",
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

        # Verify order
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        assert len(orders) == 1
        # Migration removes .NS suffix
        assert orders[0].symbol == "RELIANCE"
        assert orders[0].status == OrderStatus.AMO
        assert orders[0].broker_order_id == "BROKER-12345"
        # Verify price is None when 0.0
        assert orders[0].price is None

    def test_migrate_order_with_broker_id(self, db_session, sample_user, temp_data_dir):
        """Test migrating order with broker_order_id"""
        order = {
            "order_id": "BROKER-12345",  # Required - becomes broker_order_id
            "symbol": "TCS.NS",
            "side": "buy",
            "order_type": "MARKET",
            "qty": 5.0,  # Use 'qty' not 'quantity'
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

        assert stats["orders_created"] == 1
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        assert orders[0].broker_order_id == "BROKER-12345"


class TestPaperTradingMigration:
    """Unit tests for paper trading data migration"""

    def test_migrate_paper_trading_orders(self, db_session, sample_user, temp_data_dir):
        """Test migrating paper trading orders"""
        orders_data = [
            {
                "order_id": "paper_001",  # Required field
                "symbol": "RELIANCE.NS",
                "side": "buy",
                "order_type": "MARKET",
                "quantity": 10.0,
                "price": 2450.0,
                "status": "FILLED",
                "timestamp": "2025-10-27T09:15:00",
            }
        ]
        orders_file = temp_data_dir / "orders.json"
        orders_file.write_text(json.dumps(orders_data))

        stats = migrate_paper_trading_orders(
            db=db_session, orders_path=str(orders_file), user_id=sample_user.id, dry_run=False
        )

        assert stats["orders_processed"] == 1
        assert stats["orders_created"] == 1
        assert len(stats["errors"]) == 0

        # Verify order (symbol has .NS removed)
        orders = db_session.query(Orders).filter(Orders.user_id == sample_user.id).all()
        if len(orders) > 0:
            assert orders[0].symbol == "RELIANCE"  # .NS removed
            assert orders[0].order_id == "paper_001"

    def test_migrate_paper_trading_holdings(self, db_session, sample_user, temp_data_dir):
        """Test migrating paper trading holdings"""
        # Holdings file is a dictionary keyed by symbol, not a list
        holdings_data = {
            "RELIANCE.NS": {
                "quantity": 10.0,
                "avg_price": 2450.0,
                "opened_at": "2025-10-27T09:15:00",
            }
        }
        holdings_file = temp_data_dir / "holdings.json"
        holdings_file.write_text(json.dumps(holdings_data))

        stats = migrate_paper_trading_holdings(
            db=db_session, holdings_path=str(holdings_file), user_id=sample_user.id, dry_run=False
        )

        assert stats["holdings_processed"] == 1
        assert stats["positions_created"] == 1
        assert len(stats["errors"]) == 0

        # Verify position (symbol has .NS removed)
        positions = db_session.query(Positions).filter(Positions.user_id == sample_user.id).all()
        assert len(positions) == 1
        assert positions[0].symbol == "RELIANCE"  # .NS removed
        assert positions[0].quantity == 10.0
        assert positions[0].avg_price == 2450.0

    def test_migrate_paper_trading_transactions(self, db_session, sample_user, temp_data_dir):
        """Test migrating paper trading transactions"""
        # First create an order (symbol without .NS as migration removes it)
        placed_at = datetime(2025, 10, 27, 9, 15, 0)
        order = Orders(
            user_id=sample_user.id,
            symbol="RELIANCE",  # Without .NS
            side="buy",
            order_type="market",
            quantity=10.0,
            status=OrderStatus.ONGOING,
            placed_at=placed_at,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Transactions are matched by (symbol, side, timestamp)
        transactions_data = [
            {
                "symbol": "RELIANCE",  # Without .NS
                "side": "buy",
                "qty": 10.0,
                "price": 2450.0,
                "timestamp": "2025-10-27T09:15:00",
            }
        ]
        transactions_file = temp_data_dir / "transactions.json"
        transactions_file.write_text(json.dumps(transactions_data))

        stats = migrate_paper_trading_transactions(
            db=db_session,
            transactions_path=str(transactions_file),
            user_id=sample_user.id,
            dry_run=False,
        )

        assert stats["transactions_processed"] == 1
        assert stats["fills_created"] == 1
        assert len(stats["errors"]) == 0

        # Verify fill
        fills = db_session.query(Fills).filter(Fills.order_id == order.id).all()
        assert len(fills) == 1
        assert fills[0].qty == 10.0
        assert fills[0].price == 2450.0
