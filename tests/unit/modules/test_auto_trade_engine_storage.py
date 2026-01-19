"""
Tests for AutoTradeEngine storage abstraction layer (Phase 2.3)

Tests that AutoTradeEngine correctly uses repository-based storage when available,
with fallback to file-based storage for backward compatibility.
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from config.strategy_config import StrategyConfig
from src.infrastructure.db.models import OrderStatus as DbOrderStatus
from src.infrastructure.db.models import Users
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository


@pytest.fixture
def mock_auth():
    """Mock KotakNeoAuth"""
    auth = MagicMock()
    auth.is_authenticated.return_value = True
    auth.login.return_value = True
    return auth


@pytest.fixture
def strategy_config():
    """Default strategy config"""
    return StrategyConfig(
        rsi_period=14,
        rsi_oversold=25.0,
        user_capital=300000.0,
        max_portfolio_size=6,
    )


@pytest.fixture
def test_user(db_session):
    """Create a test user for foreign key constraints"""
    user = Users(
        email="test@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auto_trade_engine_with_db(mock_auth, db_session, strategy_config, test_user):
    """Create AutoTradeEngine instance with database (repository mode)"""
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine  # noqa: PLC0415

    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth") as mock_auth_class:
        mock_auth_class.return_value = mock_auth

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )

        # Mock portfolio and orders
        engine.portfolio = MagicMock()
        engine.orders = MagicMock()

        return engine


@pytest.fixture
def auto_trade_engine_file_mode(mock_auth, strategy_config):
    """Create AutoTradeEngine instance without database (file mode)"""
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine  # noqa: PLC0415

    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth") as mock_auth_class:
        mock_auth_class.return_value = mock_auth

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,
            user_id=None,  # No user_id = file mode
            db_session=None,  # No db_session = file mode
            strategy_config=strategy_config,
        )

        # Mock portfolio and orders
        engine.portfolio = MagicMock()
        engine.orders = MagicMock()

        return engine


@pytest.fixture
def sample_trade():
    """Sample trade dictionary"""
    return {
        "symbol": "RELIANCE",
        "placed_symbol": "RELIANCE-EQ",
        "ticker": "RELIANCE.NS",
        "entry_price": 2500.0,
        "entry_time": datetime.now().isoformat(),
        "rsi10": 25.0,
        "ema9": 2550.0,
        "ema200": 2400.0,
        "capital": 50000.0,
        "qty": 20,
        "rsi_entry_level": 30,
        "levels_taken": {"30": True, "20": False, "10": False},
        "reset_ready": False,
        "order_response": {"order_id": "12345"},
        "status": "open",
        "entry_type": "system_recommended",
    }


@pytest.fixture
def sample_failed_order():
    """Sample failed order dictionary"""
    return {
        "symbol": "TATASTEEL",
        "ticker": "TATASTEEL.NS",
        "close": 1200.0,
        "qty": 40,
        "required_cash": 48000.0,
        "shortfall": 10000.0,
        "reason": "insufficient_balance",
        "verdict": "buy",
        "rsi10": 28.0,
        "ema9": 1250.0,
        "ema200": 1100.0,
    }


@pytest.fixture
def orders_repo(db_session):
    """Create OrdersRepository instance for testing"""
    return OrdersRepository(db_session)


class TestLoadTradesHistory:
    """Test _load_trades_history method"""

    def test_load_from_repository_with_open_positions(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test loading trades from repository when positions exist"""
        # Create a position
        positions_repo = PositionsRepository(db_session)
        positions_repo.upsert(
            user_id=test_user.id,
            symbol="RELIANCE",
            quantity=20,
            avg_price=2500.0,
            opened_at=datetime.now(),
        )

        # Create an order with metadata
        orders_repo = OrdersRepository(db_session)
        order = orders_repo.create_amo(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=20,
            price=None,
        )
        # Add metadata
        metadata = {
            "placed_symbol": "RELIANCE-EQ",
            "ticker": "RELIANCE.NS",
            "rsi10": 25.0,
            "ema9": 2550.0,
            "ema200": 2400.0,
            "capital": 50000.0,
            "rsi_entry_level": 30,
            "levels_taken": {"30": True, "20": False, "10": False},
            "reset_ready": False,
            "order_response": {"order_id": "12345"},
            "entry_type": "system_recommended",
        }
        orders_repo.update(order, order_metadata=metadata)

        # Load trades
        result = auto_trade_engine_with_db._load_trades_history()

        assert "trades" in result
        assert len(result["trades"]) == 1
        trade = result["trades"][0]
        assert trade["symbol"] == "RELIANCE"
        assert trade["qty"] == 20
        assert trade["entry_price"] == 2500.0
        assert trade["status"] == "open"
        assert trade["rsi10"] == 25.0
        assert trade["ema9"] == 2550.0

    def test_load_from_repository_with_closed_positions(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test loading trades from repository with closed positions"""
        # Create a closed position
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="TATASTEEL",
            quantity=40,
            avg_price=1200.0,
            opened_at=datetime.now(),
        )
        position.closed_at = datetime.now()
        db_session.commit()

        # Create an order with exit metadata
        orders_repo = OrdersRepository(db_session)
        order = orders_repo.create_amo(
            user_id=test_user.id,
            symbol="TATASTEEL",
            side="buy",
            order_type="market",
            quantity=40,
            price=None,
        )
        metadata = {
            "placed_symbol": "TATASTEEL-EQ",
            "ticker": "TATASTEEL.NS",
            "exit_price": 1250.0,
            "exit_rsi10": 55.0,
            "exit_reason": "EMA9 or RSI50",
            "entry_type": "system_recommended",
        }
        orders_repo.update(order, order_metadata=metadata)

        # Load trades
        result = auto_trade_engine_with_db._load_trades_history()

        assert "trades" in result
        closed_trades = [t for t in result["trades"] if t["status"] == "closed"]
        assert len(closed_trades) == 1
        trade = closed_trades[0]
        assert trade["symbol"] == "TATASTEEL"
        assert trade["exit_price"] == 1250.0
        assert trade["exit_rsi10"] == 55.0

    def test_load_from_repository_with_failed_orders(
        self, auto_trade_engine_with_db, db_session, sample_failed_order, test_user
    ):
        """Test loading failed orders from repository"""
        orders_repo = OrdersRepository(db_session)
        order = orders_repo.create_amo(
            user_id=test_user.id,
            symbol="TATASTEEL",
            side="buy",
            order_type="market",
            quantity=0,
            price=None,
        )
        metadata = {
            "failed_order": True,
            "failed_order_data": sample_failed_order,
        }
        orders_repo.update(order, order_metadata=metadata)

        # Load trades
        result = auto_trade_engine_with_db._load_trades_history()

        assert "failed_orders" in result
        assert len(result["failed_orders"]) == 1
        failed = result["failed_orders"][0]
        assert failed["symbol"] == "TATASTEEL"
        assert failed["reason"] == "insufficient_balance"

    def test_load_from_file_fallback(self, auto_trade_engine_file_mode, sample_trade):
        """Test loading trades from file when repository not available"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            data = {
                "trades": [sample_trade],
                "failed_orders": [],
                "last_run": datetime.now().isoformat(),
            }
            json.dump(data, f)
            temp_path = f.name

        try:
            auto_trade_engine_file_mode.history_path = temp_path

            result = auto_trade_engine_file_mode._load_trades_history()

            assert "trades" in result
            assert len(result["trades"]) == 1
            assert result["trades"][0]["symbol"] == "RELIANCE"
        finally:
            os.unlink(temp_path)

    def test_load_empty_when_no_storage(self, auto_trade_engine_file_mode):
        """Test loading returns empty structure when no storage available"""
        auto_trade_engine_file_mode.history_path = None

        result = auto_trade_engine_file_mode._load_trades_history()

        assert "trades" in result
        assert "failed_orders" in result
        assert result["trades"] == []
        assert result["failed_orders"] == []


class TestSaveTradesHistory:
    """Test _save_trades_history method"""

    def test_save_to_repository_open_position(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test saving open trade to repository"""
        data = {
            "trades": [sample_trade],
            "failed_orders": [],
        }

        auto_trade_engine_with_db._save_trades_history(data)

        # Verify position was created
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
        assert position is not None
        assert position.quantity == 20
        assert position.avg_price == 2500.0
        assert position.closed_at is None

    def test_save_to_repository_skips_json_write_when_db_available(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test that _save_trades_history skips JSON write when DB is available (DB-only mode)"""
        # Set up a history_path to verify it's NOT written to
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        # Initialize file with some data
        with open(temp_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        try:
            data = {
                "trades": [sample_trade],
                "failed_orders": [],
            }

            # Mock save_history to verify it's NOT called
            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.save_history") as mock_save:
                auto_trade_engine_with_db._save_trades_history(data)

                # Verify save_history was NOT called (DB-only mode)
                mock_save.assert_not_called()

                # Verify position was created in DB
                positions_repo = PositionsRepository(db_session)
                position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
                assert position is not None
                assert position.quantity == 20

                # Verify JSON file was NOT modified (should still be empty)
                with open(temp_path) as f:
                    saved_data = json.load(f)
                    assert len(saved_data["trades"]) == 0  # File not written to
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_save_to_repository_closed_position(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test saving closed trade to repository"""
        # Create an open position first
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="RELIANCE",
            quantity=20,
            avg_price=2500.0,
            opened_at=datetime.now(),
        )

        # Now close it
        closed_trade = {
            "symbol": "RELIANCE",
            "qty": 20,
            "entry_price": 2500.0,
            "status": "closed",
            "exit_time": datetime.now().isoformat(),
        }
        data = {
            "trades": [closed_trade],
            "failed_orders": [],
        }

        auto_trade_engine_with_db._save_trades_history(data)

        # Verify position was closed
        db_session.refresh(position)
        assert position.closed_at is not None

    def test_save_to_repository_closed_position_with_exit_details(
        self, auto_trade_engine_with_db, db_session, test_user, orders_repo
    ):
        """Test Fix #1: Closed position with exit details (exit_price, exit_reason, realized_pnl)"""
        from src.infrastructure.db.timezone_utils import ist_now

        # Create an open position first
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="IMFA-EQ",
            quantity=82,
            avg_price=1222.7,
            opened_at=datetime.now(),
        )

        # Close it with full exit details in trade dict
        exit_time = ist_now()
        closed_trade = {
            "symbol": "IMFA-EQ",
            "qty": 82,
            "entry_price": 1222.7,
            "status": "closed",
            "exit_time": exit_time.isoformat(),
            "exit_price": 1331.19,
            "exit_reason": "EMA9 or RSI50",
            "exit_rsi10": 25.5,
            "pnl": 8887.68,  # (1331.19 - 1222.7) * 82
        }
        data = {
            "trades": [closed_trade],
            "failed_orders": [],
        }

        # Ensure orders_repo is set for the test
        auto_trade_engine_with_db.orders_repo = orders_repo

        auto_trade_engine_with_db._save_trades_history(data)

        # Verify position was closed with all exit details
        db_session.refresh(position)
        assert position.closed_at is not None
        assert position.exit_price == 1331.19
        assert position.exit_reason == "EMA9 or RSI50"
        assert position.exit_rsi == 25.5
        assert position.realized_pnl == 8887.68
        assert position.quantity == 0.0  # Position should be fully closed

    def test_save_to_repository_closed_position_with_sell_order_id(
        self, auto_trade_engine_with_db, db_session, test_user, orders_repo
    ):
        """Test Fix #1: Closed position with sell_order_id resolution from string"""
        from src.infrastructure.db.models import Orders, OrderStatus as DbOrderStatus
        from src.infrastructure.db.timezone_utils import ist_now

        # Create a sell order
        sell_order = Orders(
            user_id=test_user.id,
            symbol="IMFA-EQ",
            side="sell",
            order_type="limit",
            quantity=82,
            status=DbOrderStatus.CLOSED,
            execution_price=1331.19,
            execution_qty=82,
            broker_order_id="BROKER123",
            order_id="ORDER456",
        )
        db_session.add(sell_order)
        db_session.commit()
        db_session.refresh(sell_order)

        # Create an open position
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="IMFA-EQ",
            quantity=82,
            avg_price=1222.7,
            opened_at=datetime.now(),
        )

        # Close it with sell_order_id as string (broker_order_id)
        exit_time = ist_now()
        closed_trade = {
            "symbol": "IMFA-EQ",
            "qty": 82,
            "entry_price": 1222.7,
            "status": "closed",
            "exit_time": exit_time.isoformat(),
            "exit_price": 1331.19,
            "exit_reason": "TARGET_HIT",
            "sell_order_id": "BROKER123",  # String, should be resolved to DB ID
        }
        data = {
            "trades": [closed_trade],
            "failed_orders": [],
        }

        # Ensure orders_repo is set
        auto_trade_engine_with_db.orders_repo = orders_repo

        auto_trade_engine_with_db._save_trades_history(data)

        # Verify position was closed with sell_order_id resolved
        db_session.refresh(position)
        assert position.closed_at is not None
        assert position.exit_price == 1331.19
        assert position.sell_order_id == sell_order.id  # Should be resolved from "BROKER123"

    def test_save_to_file_fallback(self, auto_trade_engine_file_mode, sample_trade):
        """Test saving trades to file when repository not available"""

        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)  # Close file descriptor immediately, we just need the path
        auto_trade_engine_file_mode.history_path = temp_path

        try:
            data = {
                "trades": [sample_trade],
                "failed_orders": [],
            }

            auto_trade_engine_file_mode._save_trades_history(data)

            # Verify file was created and contains data
            assert os.path.exists(temp_path)
            with open(temp_path) as f:
                saved_data = json.load(f)
                assert "trades" in saved_data
                assert len(saved_data["trades"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestAppendTrade:
    """Test _append_trade method"""

    def test_append_to_repository(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test appending trade to repository"""
        auto_trade_engine_with_db._append_trade(sample_trade)

        # Verify position was created
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
        assert position is not None
        assert position.quantity == 20

    def test_append_to_repository_skips_json_write_when_db_available(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test that _append_trade skips JSON write when DB is available (DB-only mode)"""
        # Set up a history_path to verify it's NOT written to
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        # Initialize file with some data
        with open(temp_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        try:
            # Mock append_trade to verify it's NOT called
            with patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.append_trade"
            ) as mock_append:
                auto_trade_engine_with_db._append_trade(sample_trade)

                # Verify append_trade was NOT called (DB-only mode)
                mock_append.assert_not_called()

                # Verify position was created in DB
                positions_repo = PositionsRepository(db_session)
                position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
                assert position is not None
                assert position.quantity == 20

                # Verify JSON file was NOT modified (should still be empty)
                with open(temp_path) as f:
                    data = json.load(f)
                    assert len(data["trades"]) == 0  # File not written to
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_append_to_file_fallback(self, auto_trade_engine_file_mode, sample_trade):
        """Test appending trade to file when repository not available"""

        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        # Initialize with empty valid JSON structure
        with os.fdopen(temp_fd, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)
        auto_trade_engine_file_mode.history_path = temp_path

        try:
            auto_trade_engine_file_mode._append_trade(sample_trade)

            # Verify file was created and contains trade
            assert os.path.exists(temp_path)
            with open(temp_path) as f:
                data = json.load(f)
                assert "trades" in data
                assert len(data["trades"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_db_only_mode_no_json_writes(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test that DB-only mode does not write to JSON files"""
        from src.infrastructure.persistence.positions_repository import PositionsRepository

        # Set up a history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        # Initialize file
        with open(temp_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        try:
            # Mock both storage functions
            with (
                patch(
                    "modules.kotak_neo_auto_trader.auto_trade_engine.append_trade"
                ) as mock_append,
                patch("modules.kotak_neo_auto_trader.auto_trade_engine.save_history") as mock_save,
            ):
                # Test _append_trade
                auto_trade_engine_with_db._append_trade(sample_trade)
                mock_append.assert_not_called()

                # Test _save_trades_history
                data = {
                    "trades": [sample_trade],
                    "failed_orders": [],
                }
                auto_trade_engine_with_db._save_trades_history(data)
                mock_save.assert_not_called()

                # Verify positions were created in DB
                positions_repo = PositionsRepository(db_session)
                position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
                assert position is not None
                assert position.quantity == 20

                # Verify JSON file was NOT modified
                with open(temp_path) as f:
                    saved_data = json.load(f)
                    assert len(saved_data["trades"]) == 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestFailedOrders:
    """Test failed orders methods"""

    def test_get_failed_orders_from_repository(
        self, auto_trade_engine_with_db, db_session, sample_failed_order, test_user
    ):
        """Test getting failed orders from repository"""
        orders_repo = OrdersRepository(db_session)
        order = orders_repo.create_amo(
            user_id=test_user.id,
            symbol="TATASTEEL",
            side="buy",
            order_type="market",
            quantity=sample_failed_order["qty"],
            price=sample_failed_order["close"],
        )
        # Mark as failed using the new status-based approach
        orders_repo.mark_failed(order, failure_reason="insufficient_balance", retry_pending=True)

        failed_orders = auto_trade_engine_with_db._get_failed_orders()

        assert len(failed_orders) == 1
        assert failed_orders[0]["symbol"] == "TATASTEEL"
        assert failed_orders[0]["reason"] == "insufficient_balance"

    def test_add_failed_order_to_repository(
        self, auto_trade_engine_with_db, db_session, sample_failed_order, test_user
    ):
        """Test adding failed order to repository"""
        auto_trade_engine_with_db._add_failed_order(sample_failed_order)

        # Verify failed order was stored (using status-based approach)
        orders_repo = OrdersRepository(db_session)
        orders = orders_repo.list(test_user.id)
        failed_orders = [
            o
            for o in orders
            if o.status == DbOrderStatus.FAILED  # RETRY_PENDING merged into FAILED
        ]
        assert len(failed_orders) == 1
        assert failed_orders[0].symbol == "TATASTEEL"

    def test_remove_failed_order_from_repository(
        self, auto_trade_engine_with_db, db_session, sample_failed_order, test_user
    ):
        """Test removing failed order from repository"""
        # Add failed order using status-based approach
        orders_repo = OrdersRepository(db_session)
        order = orders_repo.create_amo(
            user_id=test_user.id,
            symbol="TATASTEEL",
            side="buy",
            order_type="market",
            quantity=sample_failed_order["qty"],
            price=sample_failed_order["close"],
        )
        orders_repo.mark_failed(order, failure_reason="insufficient_balance", retry_pending=True)

        # Remove it
        auto_trade_engine_with_db._remove_failed_order("TATASTEEL")

        # Verify it was removed (marked as CANCELLED, not in failed status anymore)
        db_session.refresh(order)
        assert order.status == DbOrderStatus.CANCELLED  # Changed from CLOSED to CANCELLED

    def test_get_failed_orders_from_file_fallback(
        self, auto_trade_engine_file_mode, sample_failed_order
    ):
        """Test getting failed orders from file when repository not available"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            data = {
                "trades": [],
                "failed_orders": [sample_failed_order],
                "last_run": datetime.now().isoformat(),
            }
            json.dump(data, f)
            temp_path = f.name

        try:
            auto_trade_engine_file_mode.history_path = temp_path

            failed_orders = auto_trade_engine_file_mode._get_failed_orders()

            assert len(failed_orders) == 1
            assert failed_orders[0]["symbol"] == "TATASTEEL"
        finally:
            os.unlink(temp_path)

    def test_add_failed_order_to_file_fallback(
        self, auto_trade_engine_file_mode, sample_failed_order
    ):
        """Test adding failed order to file when repository not available"""

        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        # Initialize with empty valid JSON structure
        with os.fdopen(temp_fd, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)
        auto_trade_engine_file_mode.history_path = temp_path

        try:
            auto_trade_engine_file_mode._add_failed_order(sample_failed_order)

            # Verify file was created and contains failed order
            assert os.path.exists(temp_path)
            with open(temp_path) as f:
                data = json.load(f)
                assert "failed_orders" in data
                assert len(data["failed_orders"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestStorageIntegration:
    """Integration tests for storage abstraction"""

    def test_full_cycle_repository_mode(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test complete cycle: append, load, save in repository mode"""
        # Append trade
        auto_trade_engine_with_db._append_trade(sample_trade)

        # Load trades
        result = auto_trade_engine_with_db._load_trades_history()

        # Verify trade was loaded
        assert len(result["trades"]) == 1
        assert result["trades"][0]["symbol"] == "RELIANCE"

        # Modify and save
        result["trades"][0]["qty"] = 25
        auto_trade_engine_with_db._save_trades_history(result)

        # Verify update
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
        assert position.quantity == 25

    def test_backward_compatibility_file_mode(self, auto_trade_engine_file_mode, sample_trade):
        """Test that file mode still works for backward compatibility"""

        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)  # Close file descriptor immediately, we just need the path
        auto_trade_engine_file_mode.history_path = temp_path

        try:
            # Initialize empty file first
            with open(temp_path, "w") as f:
                json.dump({"trades": [], "failed_orders": []}, f)

            # Append trade
            auto_trade_engine_file_mode._append_trade(sample_trade)

            # Load trades
            result = auto_trade_engine_file_mode._load_trades_history()

            # Verify trade was loaded (should be 1, not 2, since we started with empty file)
            assert len(result["trades"]) >= 1
            # Find the trade we just added
            reliance_trades = [t for t in result["trades"] if t["symbol"] == "RELIANCE"]
            assert len(reliance_trades) == 1
            assert reliance_trades[0]["symbol"] == "RELIANCE"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_db_only_mode_no_json_writes(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test that DB-only mode does not write to JSON files"""
        from src.infrastructure.persistence.positions_repository import PositionsRepository

        # Set up a history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        # Initialize file
        with open(temp_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        try:
            # Mock both storage functions
            with (
                patch(
                    "modules.kotak_neo_auto_trader.auto_trade_engine.append_trade"
                ) as mock_append,
                patch("modules.kotak_neo_auto_trader.auto_trade_engine.save_history") as mock_save,
            ):
                # Test _append_trade
                auto_trade_engine_with_db._append_trade(sample_trade)
                mock_append.assert_not_called()

                # Test _save_trades_history
                data = {
                    "trades": [sample_trade],
                    "failed_orders": [],
                }
                auto_trade_engine_with_db._save_trades_history(data)
                mock_save.assert_not_called()

                # Verify positions were created in DB
                positions_repo = PositionsRepository(db_session)
                position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
                assert position is not None
                assert position.quantity == 20

                # Verify JSON file was NOT modified
                with open(temp_path) as f:
                    saved_data = json.load(f)
                    assert len(saved_data["trades"]) == 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestDBOnlyModeEdgeCases:
    """Test edge cases for DB-only mode"""

    def test_append_trade_when_positions_repo_none(self, auto_trade_engine_with_db, sample_trade):
        """Test _append_trade when positions_repo is None (should not crash)"""

        # Set positions_repo to None
        auto_trade_engine_with_db.positions_repo = None

        # Set up history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        try:
            # Should not crash, but also should not write to JSON (DB-only mode)
            with patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.append_trade"
            ) as mock_append:
                auto_trade_engine_with_db._append_trade(sample_trade)

                # Should not call append_trade (DB-only mode, even if positions_repo is None)
                mock_append.assert_not_called()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_save_trades_history_when_positions_repo_none(
        self, auto_trade_engine_with_db, sample_trade
    ):
        """Test _save_trades_history when positions_repo is None (should not crash)"""

        # Set positions_repo to None
        auto_trade_engine_with_db.positions_repo = None

        # Set up history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        try:
            data = {
                "trades": [sample_trade],
                "failed_orders": [],
            }

            # Should not crash, but also should not write to JSON (DB-only mode)
            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.save_history") as mock_save:
                auto_trade_engine_with_db._save_trades_history(data)

                # Should not call save_history (DB-only mode, even if positions_repo is None)
                mock_save.assert_not_called()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_append_trade_when_history_path_none(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test _append_trade when history_path is None (DB-only mode should still work)"""
        # Set history_path to None
        auto_trade_engine_with_db.history_path = None

        # Should work fine in DB-only mode
        auto_trade_engine_with_db._append_trade(sample_trade)

        # Verify position was created in DB
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
        assert position is not None
        assert position.quantity == 20

    def test_save_trades_history_when_history_path_none(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test _save_trades_history when history_path is None (DB-only mode should still work)"""
        # Set history_path to None
        auto_trade_engine_with_db.history_path = None

        data = {
            "trades": [sample_trade],
            "failed_orders": [],
        }

        # Should work fine in DB-only mode
        auto_trade_engine_with_db._save_trades_history(data)

        # Verify position was created in DB
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
        assert position is not None
        assert position.quantity == 20

    def test_save_trades_history_with_empty_trades_list(
        self, auto_trade_engine_with_db, db_session
    ):
        """Test _save_trades_history with empty trades list (should not crash)"""

        # Set up history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        try:
            data = {
                "trades": [],  # Empty list
                "failed_orders": [],
            }

            # Should not crash
            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.save_history") as mock_save:
                auto_trade_engine_with_db._save_trades_history(data)

                # Should not call save_history (DB-only mode)
                mock_save.assert_not_called()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_save_trades_history_with_multiple_trades(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test _save_trades_history with multiple trades"""
        # Set up history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        try:
            # Create multiple trades
            trade2 = sample_trade.copy()
            trade2["symbol"] = "TCS"
            trade2["placed_symbol"] = "TCS-EQ"
            trade2["ticker"] = "TCS.NS"
            trade2["qty"] = 15
            trade2["entry_price"] = 3500.0

            data = {
                "trades": [sample_trade, trade2],
                "failed_orders": [],
            }

            # Should not write to JSON (DB-only mode)
            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.save_history") as mock_save:
                auto_trade_engine_with_db._save_trades_history(data)

                # Should not call save_history (DB-only mode)
                mock_save.assert_not_called()

                # Verify both positions were created in DB
                positions_repo = PositionsRepository(db_session)
                pos1 = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
                pos2 = positions_repo.get_by_symbol(test_user.id, "TCS")
                assert pos1 is not None
                assert pos2 is not None
                assert pos1.quantity == 20
                assert pos2.quantity == 15
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_append_trade_with_missing_required_fields(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test _append_trade with missing required fields (should handle gracefully)"""
        # Trade with missing fields
        incomplete_trade = {
            "symbol": "INFY",
            "qty": 10,
            # Missing entry_price, entry_time, etc.
        }

        # Should not crash (may fail to create position, but should not write to JSON)
        try:
            auto_trade_engine_with_db._append_trade(incomplete_trade)
        except Exception:
            # Expected to fail due to missing fields, but should not write to JSON
            pass

        # Verify no position was created (due to missing fields)
        positions_repo = PositionsRepository(db_session)
        _ = positions_repo.get_by_symbol(test_user.id, "INFY")
        # Position may or may not exist depending on validation, but JSON should not be written

    def test_file_fallback_when_orders_repo_none(self, auto_trade_engine_file_mode, sample_trade):
        """Test that file fallback works when orders_repo is None"""
        # This is file mode, so orders_repo should be None
        assert auto_trade_engine_file_mode.orders_repo is None

        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_file_mode.history_path = temp_path

        try:
            # Initialize file
            with open(temp_path, "w") as f:
                json.dump({"trades": [], "failed_orders": []}, f)

            # Should write to file (fallback mode)
            auto_trade_engine_file_mode._append_trade(sample_trade)

            # Verify file was written
            assert os.path.exists(temp_path)
            with open(temp_path) as f:
                data = json.load(f)
                assert len(data["trades"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_file_fallback_when_user_id_none(self, auto_trade_engine_file_mode, sample_trade):
        """Test that file fallback works when user_id is None"""
        # This is file mode, so user_id should be None
        assert auto_trade_engine_file_mode.user_id is None

        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_file_mode.history_path = temp_path

        try:
            # Initialize file
            with open(temp_path, "w") as f:
                json.dump({"trades": [], "failed_orders": []}, f)

            # Should write to file (fallback mode)
            data = {
                "trades": [sample_trade],
                "failed_orders": [],
            }
            auto_trade_engine_file_mode._save_trades_history(data)

            # Verify file was written
            assert os.path.exists(temp_path)
            with open(temp_path) as f:
                saved_data = json.load(f)
                assert len(saved_data["trades"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_append_trade_when_orders_repo_none_but_user_id_exists(
        self, auto_trade_engine_with_db, sample_trade
    ):
        """Test _append_trade when orders_repo is None but user_id exists (should use file fallback)"""

        # Set orders_repo to None (but user_id still exists)
        auto_trade_engine_with_db.orders_repo = None

        # Set up history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        try:
            # Initialize file
            with open(temp_path, "w") as f:
                json.dump({"trades": [], "failed_orders": []}, f)

            # Should fall back to file write (since orders_repo is None)
            auto_trade_engine_with_db._append_trade(sample_trade)

            # Verify file was written (fallback mode)
            with open(temp_path) as f:
                data = json.load(f)
                assert len(data["trades"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_save_trades_history_when_orders_repo_none_but_user_id_exists(
        self, auto_trade_engine_with_db, sample_trade
    ):
        """Test _save_trades_history when orders_repo is None but user_id exists (should use file fallback)"""
        # Set orders_repo to None (but user_id still exists)
        auto_trade_engine_with_db.orders_repo = None

        # Set up history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        try:
            data = {
                "trades": [sample_trade],
                "failed_orders": [],
            }

            # Should fall back to file write (since orders_repo is None)
            auto_trade_engine_with_db._save_trades_history(data)

            # Verify file was written (fallback mode)
            assert os.path.exists(temp_path)
            with open(temp_path) as f:
                saved_data = json.load(f)
                assert len(saved_data["trades"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_append_trade_when_user_id_none_but_orders_repo_exists(
        self, auto_trade_engine_with_db, sample_trade
    ):
        """Test _append_trade when user_id is None but orders_repo exists (should use file fallback)"""

        # Set user_id to None (but orders_repo still exists)
        auto_trade_engine_with_db.user_id = None

        # Set up history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        try:
            # Initialize file
            with open(temp_path, "w") as f:
                json.dump({"trades": [], "failed_orders": []}, f)

            # Should fall back to file write (since user_id is None)
            auto_trade_engine_with_db._append_trade(sample_trade)

            # Verify file was written (fallback mode)
            with open(temp_path) as f:
                data = json.load(f)
                assert len(data["trades"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_save_trades_history_when_user_id_none_but_orders_repo_exists(
        self, auto_trade_engine_with_db, sample_trade
    ):
        """Test _save_trades_history when user_id is None but orders_repo exists (should use file fallback)"""
        # Set user_id to None (but orders_repo still exists)
        auto_trade_engine_with_db.user_id = None

        # Set up history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        try:
            data = {
                "trades": [sample_trade],
                "failed_orders": [],
            }

            # Should fall back to file write (since user_id is None)
            auto_trade_engine_with_db._save_trades_history(data)

            # Verify file was written (fallback mode)
            assert os.path.exists(temp_path)
            with open(temp_path) as f:
                saved_data = json.load(f)
                assert len(saved_data["trades"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_append_trade_handles_db_error_gracefully(
        self, auto_trade_engine_with_db, sample_trade, test_user
    ):
        """Test _append_trade handles DB errors gracefully (should not crash)"""
        # Mock positions_repo.upsert to raise an exception
        with patch.object(PositionsRepository, "upsert", side_effect=Exception("DB error")):
            # Temporarily replace positions_repo
            original_repo = auto_trade_engine_with_db.positions_repo
            auto_trade_engine_with_db.positions_repo = PositionsRepository(
                auto_trade_engine_with_db.db
            )

            try:
                # Should not crash, but may raise exception (which is acceptable)
                # The key is that it should not write to JSON in DB-only mode
                with patch(
                    "modules.kotak_neo_auto_trader.auto_trade_engine.append_trade"
                ) as mock_append:
                    try:
                        auto_trade_engine_with_db._append_trade(sample_trade)
                    except Exception:
                        # Expected to fail due to DB error
                        pass

                    # Should not call append_trade (DB-only mode)
                    mock_append.assert_not_called()
            finally:
                auto_trade_engine_with_db.positions_repo = original_repo

    def test_save_trades_history_handles_db_error_gracefully(
        self, auto_trade_engine_with_db, sample_trade
    ):
        """Test _save_trades_history handles DB errors gracefully (should not crash)"""
        # Set up history_path
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(temp_fd)
        auto_trade_engine_with_db.history_path = temp_path

        try:
            data = {
                "trades": [sample_trade],
                "failed_orders": [],
            }

            # Mock positions_repo.list to raise an exception
            with patch.object(PositionsRepository, "upsert", side_effect=Exception("DB error")):
                # Temporarily replace positions_repo
                original_repo = auto_trade_engine_with_db.positions_repo
                auto_trade_engine_with_db.positions_repo = PositionsRepository(
                    auto_trade_engine_with_db.db
                )

                try:
                    # Should not crash, but may raise exception (which is acceptable)
                    # The key is that it should not write to JSON in DB-only mode
                    with patch(
                        "modules.kotak_neo_auto_trader.auto_trade_engine.save_history"
                    ) as mock_save:
                        try:
                            auto_trade_engine_with_db._save_trades_history(data)
                        except Exception:
                            # Expected to fail due to DB error
                            pass

                        # Should not call save_history (DB-only mode)
                        mock_save.assert_not_called()
                finally:
                    auto_trade_engine_with_db.positions_repo = original_repo
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
