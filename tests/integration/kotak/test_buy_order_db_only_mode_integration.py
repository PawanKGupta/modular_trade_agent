"""
Integration tests for buy order DB-only mode workflow.

Tests the complete workflow from buy order placement to execution,
verifying that all operations use DB-only mode (no JSON writes).
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.order_tracker import configure_order_tracker, get_order_tracker
from src.infrastructure.db.base import Base
from src.infrastructure.db.models import OrderStatus, UserRole, Users
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository


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

    yield session, user.id

    session.close()


@pytest.fixture
def temp_history_path(tmp_path):
    """Create temporary history file path"""
    return str(tmp_path / "trades_history.json")


@pytest.fixture
def mock_broker():
    """Mock broker that simulates order placement"""
    broker = Mock()
    broker.place_market_buy = Mock(
        return_value={"stat": "Ok", "nOrdNo": "ORDER12345", "data": {"orderId": "ORDER12345"}}
    )
    broker.place_limit_buy = Mock(
        return_value={"stat": "Ok", "nOrdNo": "ORDER12346", "data": {"orderId": "ORDER12346"}}
    )
    return broker


class TestBuyOrderDBOnlyModeIntegration:
    """Integration tests for buy order DB-only mode workflow"""

    def test_buy_order_placement_to_execution_workflow_db_only(
        self, db_session, temp_history_path, mock_broker
    ):
        """Test complete workflow: buy order placement -> execution -> position creation (DB-only)"""
        session, user_id = db_session

        # Configure OrderTracker with DB-only mode
        configure_order_tracker(
            data_dir=str(Path(temp_history_path).parent),
            db_session=session,
            user_id=user_id,
            use_db=True,
            db_only_mode=True,
        )

        # Initialize file to verify it's NOT written to
        with open(temp_history_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)
        tracker = get_order_tracker()

        # Step 1: Place buy order (simulated)
        order_id = "ORDER12345"
        symbol = "RELIANCE-EQ"
        ticker = "RELIANCE.NS"
        qty = 10
        price = 2500.0

        # Get initial file state
        initial_file_mtime = (
            os.path.getmtime(temp_history_path) if os.path.exists(temp_history_path) else 0
        )

        # Add pending order (should write to DB only, not JSON)
        tracker.add_pending_order(
            order_id=order_id,
            symbol=symbol,
            ticker=ticker,
            qty=qty,
            order_type="MARKET",
            variety="AMO",
            price=0.0,
            entry_type="initial",
        )

        # Verify JSON file was NOT modified (DB-only mode)
        # Check pending_orders.json (OrderTracker's file)
        pending_orders_path = Path(temp_history_path).parent / "pending_orders.json"
        if pending_orders_path.exists():
            # File exists but should be empty or unchanged
            with open(pending_orders_path) as f:
                data = json.load(f)
                # In DB-only mode, orders should not be in JSON
                assert len(data.get("orders", [])) == 0

        # Verify order was created in DB
        db_order = orders_repo.get_by_broker_order_id(user_id, order_id)
        assert db_order is not None
        assert db_order.symbol == symbol
        assert db_order.quantity == qty
        assert db_order.status == OrderStatus.PENDING

        # Verify JSON file was NOT modified
        with open(temp_history_path) as f:
            data = json.load(f)
            assert len(data.get("trades", [])) == 0

        # Step 2: Simulate order execution
        execution_price = 2505.0
        execution_qty = 10.0

        # Mark order as executed
        orders_repo.mark_executed(
            db_order,
            execution_price=execution_price,
            execution_qty=execution_qty,
        )

        # Step 3: Create position from executed order (simulating _create_position_from_executed_order)
        # This is what happens in unified_order_monitor when order executes
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine  # noqa: PLC0415

        # Create trade dict (what would be passed to _append_trade)
        trade = {
            "symbol": "RELIANCE",
            "placed_symbol": symbol,
            "ticker": ticker,
            "entry_price": execution_price,
            "entry_time": "2025-12-18T09:15:00",
            "qty": execution_qty,
            "status": "open",
            "buy_order_id": order_id,
        }

        # Mock auth to avoid credential requirements
        from unittest.mock import MagicMock  # noqa: PLC0415

        mock_auth = MagicMock()
        mock_auth.is_authenticated.return_value = True
        mock_auth.login.return_value = True

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
        ) as mock_auth_class:
            mock_auth_class.return_value = mock_auth

            engine = AutoTradeEngine(
                env_file="test.env",
                auth=mock_auth,
                user_id=user_id,
                db_session=session,
            )
            engine.positions_repo = positions_repo
            engine.orders_repo = orders_repo
            engine.history_path = temp_history_path

            # Mock append_trade to verify it's NOT called
            with patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.append_trade"
            ) as mock_append_trade:
                # Simulate _append_trade call (DB-only mode should skip JSON write)
                engine._append_trade(trade)

                # Verify append_trade was NOT called (DB-only mode)
                mock_append_trade.assert_not_called()

        # Verify position was created in DB
        # _update_position_from_trade uses trade["symbol"] (base symbol), not placed_symbol
        base_symbol = trade.get("symbol", "").upper()
        position = positions_repo.get_by_symbol(user_id, base_symbol)
        # If not found by base symbol, try full symbol
        if position is None:
            position = positions_repo.get_by_symbol(user_id, symbol)
        assert position is not None, f"Position not found for {base_symbol} or {symbol}"
        assert position.quantity == execution_qty
        assert position.avg_price == execution_price
        assert position.closed_at is None

        # Verify JSON file was NOT modified
        with open(temp_history_path) as f:
            data = json.load(f)
            assert len(data.get("trades", [])) == 0

        # Verify order status updated in DB (filled orders are CLOSED)
        session.refresh(db_order)
        assert db_order.status == OrderStatus.CLOSED
        assert db_order.execution_price == execution_price
        assert db_order.execution_qty == execution_qty

    def test_multiple_buy_orders_workflow_db_only(self, db_session, temp_history_path, mock_broker):
        """Test multiple buy orders placed and executed (DB-only mode)"""
        session, user_id = db_session

        # Configure OrderTracker with DB-only mode
        configure_order_tracker(
            data_dir=str(Path(temp_history_path).parent),
            db_session=session,
            user_id=user_id,
            use_db=True,
            db_only_mode=True,
        )

        # Initialize file
        with open(temp_history_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)
        tracker = get_order_tracker()

        # Place multiple buy orders
        orders_data = [
            {"order_id": "ORDER1", "symbol": "RELIANCE-EQ", "ticker": "RELIANCE.NS", "qty": 10},
            {"order_id": "ORDER2", "symbol": "TCS-EQ", "ticker": "TCS.NS", "qty": 5},
            {"order_id": "ORDER3", "symbol": "INFY-EQ", "ticker": "INFY.NS", "qty": 8},
        ]

        for order_data in orders_data:
            tracker.add_pending_order(
                order_id=order_data["order_id"],
                symbol=order_data["symbol"],
                ticker=order_data["ticker"],
                qty=order_data["qty"],
                order_type="MARKET",
                variety="AMO",
                price=0.0,
            )

        # Verify JSON file was NOT modified (DB-only mode)
        pending_orders_path = Path(temp_history_path).parent / "pending_orders.json"
        if pending_orders_path.exists():
            with open(pending_orders_path) as f:
                data = json.load(f)
                # In DB-only mode, orders should not be in JSON
                assert len(data.get("orders", [])) == 0

        # Verify all orders in DB
        for order_data in orders_data:
            db_order = orders_repo.get_by_broker_order_id(user_id, order_data["order_id"])
            assert db_order is not None
            assert db_order.symbol == order_data["symbol"]

        # Execute all orders and create positions
        from unittest.mock import MagicMock  # noqa: PLC0415

        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine  # noqa: PLC0415

        mock_auth = MagicMock()
        mock_auth.is_authenticated.return_value = True
        mock_auth.login.return_value = True

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
        ) as mock_auth_class:
            mock_auth_class.return_value = mock_auth

            engine = AutoTradeEngine(
                env_file="test.env",
                auth=mock_auth,
                user_id=user_id,
                db_session=session,
            )
            engine.positions_repo = positions_repo
            engine.orders_repo = orders_repo
            engine.history_path = temp_history_path

        execution_prices = [2500.0, 3500.0, 1500.0]

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.append_trade"
        ) as mock_append_trade:
            for i, order_data in enumerate(orders_data):
                db_order = orders_repo.get_by_broker_order_id(user_id, order_data["order_id"])
                orders_repo.mark_executed(
                    db_order,
                    execution_price=execution_prices[i],
                    execution_qty=order_data["qty"],
                )

                # Create position via _append_trade (DB-only mode)
                trade = {
                    "symbol": order_data["symbol"].split("-")[0],
                    "placed_symbol": order_data["symbol"],
                    "ticker": order_data["ticker"],
                    "entry_price": execution_prices[i],
                    "entry_time": "2025-12-18T09:15:00",
                    "qty": order_data["qty"],
                    "status": "open",
                    "buy_order_id": order_data["order_id"],
                }
                engine._append_trade(trade)

            # Verify append_trade was NOT called (DB-only mode)
            mock_append_trade.assert_not_called()

        # Verify all positions created in DB
        # _update_position_from_trade uses trade["symbol"] (base symbol)
        for order_data in orders_data:
            base_symbol = order_data["symbol"].split("-")[0]  # Extract base symbol
            position = positions_repo.get_by_symbol(user_id, base_symbol)
            # If not found by base symbol, try full symbol
            if position is None:
                position = positions_repo.get_by_symbol(user_id, order_data["symbol"])
            assert (
                position is not None
            ), f"Position not found for {base_symbol} or {order_data['symbol']}"
            assert position.quantity == order_data["qty"]

        # Verify JSON file was NOT modified
        with open(temp_history_path) as f:
            data = json.load(f)
            assert len(data.get("trades", [])) == 0

    def test_buy_order_workflow_with_file_fallback_when_db_unavailable(
        self, temp_history_path, mock_broker
    ):
        """Test that file fallback works when DB is not available"""
        # Configure OrderTracker without DB (file mode)
        configure_order_tracker(
            data_dir=str(Path(temp_history_path).parent),
            db_session=None,
            user_id=None,
            use_db=False,
            db_only_mode=False,
        )

        # Initialize file
        with open(temp_history_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        tracker = get_order_tracker()

        # Add pending order (should write to JSON file)
        tracker.add_pending_order(
            order_id="ORDER123",
            symbol="RELIANCE-EQ",
            ticker="RELIANCE.NS",
            qty=10,
            order_type="MARKET",
            variety="AMO",
            price=0.0,
        )

        # Verify order was written to JSON file (fallback mode)
        pending_orders = tracker.get_pending_orders()
        assert len(pending_orders) == 1
        assert pending_orders[0]["order_id"] == "ORDER123"

    def test_buy_order_execution_creates_position_via_append_trade_db_only(
        self, db_session, temp_history_path
    ):
        """Test that buy order execution creates position via _append_trade in DB-only mode"""
        session, user_id = db_session

        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)

        # Create executed order in DB
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
        )
        orders_repo.mark_executed(order, execution_price=2500.0, execution_qty=10.0)

        # Create engine with DB (mock auth to avoid credential requirements)
        from unittest.mock import MagicMock  # noqa: PLC0415

        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine  # noqa: PLC0415

        mock_auth = MagicMock()
        mock_auth.is_authenticated.return_value = True
        mock_auth.login.return_value = True

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
        ) as mock_auth_class:
            mock_auth_class.return_value = mock_auth

            engine = AutoTradeEngine(
                env_file="test.env",
                auth=mock_auth,
                user_id=user_id,
                db_session=session,
            )
            engine.positions_repo = positions_repo
            engine.orders_repo = orders_repo
            engine.history_path = temp_history_path

        # Initialize file
        with open(temp_history_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        # Create trade dict
        trade = {
            "symbol": "RELIANCE",
            "placed_symbol": "RELIANCE-EQ",
            "ticker": "RELIANCE.NS",
            "entry_price": 2500.0,
            "entry_time": "2025-12-18T09:15:00",
            "qty": 10.0,
            "status": "open",
            "buy_order_id": str(order.id),
        }

        # Mock append_trade to verify it's NOT called
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.append_trade") as mock_append:
            engine._append_trade(trade)

            # Verify append_trade was NOT called (DB-only mode)
            mock_append.assert_not_called()

        # Verify position was created in DB
        # _update_position_from_trade uses trade["symbol"] (base symbol)
        base_symbol = trade.get("symbol", "").upper()
        position = positions_repo.get_by_symbol(user_id, base_symbol)
        # If not found by base symbol, try full symbol
        if position is None:
            position = positions_repo.get_by_symbol(user_id, "RELIANCE-EQ")
        assert position is not None, f"Position not found for {base_symbol} or RELIANCE-EQ"
        assert position.quantity == 10.0
        assert position.avg_price == 2500.0

        # Verify JSON file was NOT modified
        with open(temp_history_path) as f:
            data = json.load(f)
            assert len(data.get("trades", [])) == 0

    def test_buy_order_workflow_with_save_trades_history_db_only(
        self, db_session, temp_history_path
    ):
        """Test _save_trades_history in DB-only mode (bulk sync)"""
        session, user_id = db_session

        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)

        # Create engine with DB (mock auth to avoid credential requirements)
        from unittest.mock import MagicMock  # noqa: PLC0415

        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine  # noqa: PLC0415

        mock_auth = MagicMock()
        mock_auth.is_authenticated.return_value = True
        mock_auth.login.return_value = True

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
        ) as mock_auth_class:
            mock_auth_class.return_value = mock_auth

            engine = AutoTradeEngine(
                env_file="test.env",
                auth=mock_auth,
                user_id=user_id,
                db_session=session,
            )
            engine.positions_repo = positions_repo
            engine.orders_repo = orders_repo
            engine.history_path = temp_history_path

        # Initialize file
        with open(temp_history_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        # Create multiple trades data
        trades_data = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "placed_symbol": "RELIANCE-EQ",
                    "ticker": "RELIANCE.NS",
                    "entry_price": 2500.0,
                    "entry_time": "2025-12-18T09:15:00",
                    "qty": 10.0,
                    "status": "open",
                },
                {
                    "symbol": "TCS",
                    "placed_symbol": "TCS-EQ",
                    "ticker": "TCS.NS",
                    "entry_price": 3500.0,
                    "entry_time": "2025-12-18T09:16:00",
                    "qty": 5.0,
                    "status": "open",
                },
            ],
            "failed_orders": [],
        }

        # Mock save_history to verify it's NOT called
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.save_history") as mock_save:
            engine._save_trades_history(trades_data)

            # Verify save_history was NOT called (DB-only mode)
            mock_save.assert_not_called()

        # Verify positions were created in DB
        # _update_position_from_trade uses trade["symbol"] (base symbol)
        pos1 = positions_repo.get_by_symbol(user_id, "RELIANCE")
        if pos1 is None:
            pos1 = positions_repo.get_by_symbol(user_id, "RELIANCE-EQ")
        pos2 = positions_repo.get_by_symbol(user_id, "TCS")
        if pos2 is None:
            pos2 = positions_repo.get_by_symbol(user_id, "TCS-EQ")
        assert pos1 is not None, "Position not found for RELIANCE"
        assert pos2 is not None, "Position not found for TCS"
        assert pos1.quantity == 10.0
        assert pos2.quantity == 5.0

        # Verify JSON file was NOT modified
        with open(temp_history_path) as f:
            data = json.load(f)
            assert len(data.get("trades", [])) == 0

    def test_order_tracker_db_only_mode_defaults_to_true_when_db_available(
        self, db_session, temp_history_path
    ):
        """Test that OrderTracker defaults to DB-only mode when DB is available"""
        session, user_id = db_session

        # Configure without explicitly setting db_only_mode (should default to True)
        configure_order_tracker(
            data_dir=str(Path(temp_history_path).parent),
            db_session=session,
            user_id=user_id,
            use_db=True,
            # db_only_mode not specified - should default to True
        )

        tracker = get_order_tracker()

        # Verify DB-only mode is enabled
        assert tracker.db_only_mode is True
        assert tracker.use_db is True

        # Initialize file
        with open(temp_history_path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)

        # Add pending order (DB-only mode should skip JSON write)
        tracker.add_pending_order(
            order_id="ORDER123",
            symbol="RELIANCE-EQ",
            ticker="RELIANCE.NS",
            qty=10,
            order_type="MARKET",
            variety="AMO",
            price=0.0,
        )

        # Verify JSON file was NOT modified (DB-only mode)
        pending_orders_path = Path(temp_history_path).parent / "pending_orders.json"
        if pending_orders_path.exists():
            with open(pending_orders_path) as f:
                data = json.load(f)
                # In DB-only mode, orders should not be in JSON
                assert len(data.get("orders", [])) == 0

        # Verify order in DB
        orders_repo = OrdersRepository(session)
        db_order = orders_repo.get_by_broker_order_id(user_id, "ORDER123")
        assert db_order is not None

        # Verify JSON file was NOT modified
        with open(temp_history_path) as f:
            data = json.load(f)
            # Check pending_orders.json equivalent - should be empty or not exist
            # (OrderTracker uses pending_orders.json, not trades_history.json)
            # But we can verify no trades were written
            assert len(data.get("trades", [])) == 0
