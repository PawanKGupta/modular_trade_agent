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
    from src.infrastructure.db.models import Users

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
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

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
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

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


class TestLoadTradesHistory:
    """Test _load_trades_history method"""

    def test_load_from_repository_with_open_positions(
        self, auto_trade_engine_with_db, db_session, sample_trade, test_user
    ):
        """Test loading trades from repository when positions exist"""
        from src.infrastructure.persistence.orders_repository import OrdersRepository
        from src.infrastructure.persistence.positions_repository import PositionsRepository

        # Create a position
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.upsert(
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
        from src.infrastructure.persistence.orders_repository import OrdersRepository
        from src.infrastructure.persistence.positions_repository import PositionsRepository

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
        from src.infrastructure.persistence.orders_repository import OrdersRepository

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
        from src.infrastructure.persistence.positions_repository import PositionsRepository

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

    def test_save_to_repository_closed_position(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test saving closed trade to repository"""
        from src.infrastructure.persistence.positions_repository import PositionsRepository

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

    def test_save_to_file_fallback(self, auto_trade_engine_file_mode, sample_trade):
        """Test saving trades to file when repository not available"""

        temp_path = tempfile.mktemp(suffix=".json")
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
        from src.infrastructure.persistence.positions_repository import PositionsRepository

        auto_trade_engine_with_db._append_trade(sample_trade)

        # Verify position was created
        positions_repo = PositionsRepository(db_session)
        position = positions_repo.get_by_symbol(test_user.id, "RELIANCE")
        assert position is not None
        assert position.quantity == 20

    def test_append_to_file_fallback(self, auto_trade_engine_file_mode, sample_trade):
        """Test appending trade to file when repository not available"""

        temp_path = tempfile.mktemp(suffix=".json")
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


class TestFailedOrders:
    """Test failed orders methods"""

    def test_get_failed_orders_from_repository(
        self, auto_trade_engine_with_db, db_session, sample_failed_order, test_user
    ):
        """Test getting failed orders from repository"""
        from src.infrastructure.persistence.orders_repository import OrdersRepository

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
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus
        from src.infrastructure.persistence.orders_repository import OrdersRepository

        auto_trade_engine_with_db._add_failed_order(sample_failed_order)

        # Verify failed order was stored (using status-based approach)
        orders_repo = OrdersRepository(db_session)
        orders = orders_repo.list(test_user.id)
        failed_orders = [
            o for o in orders if o.status == DbOrderStatus.FAILED  # RETRY_PENDING merged into FAILED
        ]
        assert len(failed_orders) == 1
        assert failed_orders[0].symbol == "TATASTEEL"

    def test_remove_failed_order_from_repository(
        self, auto_trade_engine_with_db, db_session, sample_failed_order, test_user
    ):
        """Test removing failed order from repository"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus
        from src.infrastructure.persistence.orders_repository import OrdersRepository

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

        temp_path = tempfile.mktemp(suffix=".json")
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
        from src.infrastructure.persistence.positions_repository import PositionsRepository

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

        temp_path = tempfile.mktemp(suffix=".json")
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
