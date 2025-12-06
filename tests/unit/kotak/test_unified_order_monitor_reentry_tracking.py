"""
Tests for reentry tracking in database when reentry order executes.

Tests that when a reentry order executes, the positions table is updated with:
- reentry_count
- reentries array
- last_reentry_price
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.models import Orders, Positions  # noqa: E402
from src.infrastructure.persistence.orders_repository import OrdersRepository  # noqa: E402
from src.infrastructure.persistence.positions_repository import PositionsRepository  # noqa: E402


class TestReentryTrackingInDatabase:
    """Test that reentry tracking fields are updated in database when reentry executes"""

    @pytest.fixture
    def db_session(self):
        """Create a mock database session"""
        from unittest.mock import MagicMock

        session = MagicMock()
        session.query = MagicMock()
        session.add = MagicMock()
        session.commit = MagicMock()
        session.refresh = MagicMock()
        return session

    @pytest.fixture
    def positions_repo(self, db_session):
        """Create PositionsRepository instance"""
        return PositionsRepository(db_session)

    @pytest.fixture
    def orders_repo(self, db_session):
        """Create OrdersRepository instance"""
        return OrdersRepository(db_session)

    @pytest.fixture
    def sell_manager(self):
        """Create a mock SellOrderManager"""
        manager = Mock()
        manager.get_existing_sell_orders = Mock(return_value={})
        manager.update_sell_order = Mock(return_value=True)
        return manager

    @pytest.fixture
    def unified_monitor(self, db_session, sell_manager, positions_repo, orders_repo):
        """Create UnifiedOrderMonitor instance with mocked dependencies"""
        from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor

        monitor = UnifiedOrderMonitor(
            sell_order_manager=sell_manager,
            db_session=db_session,
            user_id=1,
        )
        monitor.positions_repo = positions_repo
        monitor.orders_repo = orders_repo
        return monitor

    def test_reentry_updates_reentry_count(self, unified_monitor, positions_repo, orders_repo):
        """Test that reentry_count is incremented when reentry executes"""
        # Create initial position
        initial_position = Positions(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            reentry_count=0,
            reentries=None,
            initial_entry_price=2500.0,
            last_reentry_price=None,
            opened_at=datetime.now(),
        )

        # Mock get_by_symbol to return existing position
        positions_repo.get_by_symbol = Mock(return_value=initial_position)

        # Create reentry order with entry_type="reentry"
        reentry_order = Orders(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=5,
            entry_type="reentry",
            order_metadata={
                "rsi_level": 20,
                "rsi": 19.5,
                "price": 2480.0,
                "reentry_index": 1,
            },
        )

        # Mock orders_repo methods
        orders_repo.get = Mock(return_value=reentry_order)
        orders_repo.get = Mock(return_value=reentry_order)
        orders_repo.get_by_broker_order_id = Mock(return_value=reentry_order)

        # Mock upsert to capture the call
        upsert_call_args = {}

        def capture_upsert(**kwargs):
            upsert_call_args.update(kwargs)
            # Return updated position
            updated_pos = Positions(
                id=1,
                user_id=1,
                symbol="RELIANCE",
                quantity=15,  # 10 + 5
                avg_price=2490.0,  # Weighted average
                reentry_count=kwargs.get("reentry_count", 0),
                reentries=kwargs.get("reentries"),
                initial_entry_price=2500.0,
                last_reentry_price=kwargs.get("last_reentry_price"),
                opened_at=initial_position.opened_at,
            )
            return updated_pos

        positions_repo.upsert = Mock(side_effect=capture_upsert)

        # Execute reentry order
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info={"symbol": "RELIANCE-EQ", "db_order_id": 1},
            execution_price=2480.0,
            execution_qty=5.0,
        )

        # Verify reentry_count was updated
        assert upsert_call_args.get("reentry_count") == 1
        assert upsert_call_args.get("last_reentry_price") == 2480.0
        assert upsert_call_args.get("reentries") is not None
        assert len(upsert_call_args.get("reentries", [])) == 1

        # Verify reentry data structure
        reentries = upsert_call_args.get("reentries", [])
        assert len(reentries) == 1
        reentry = reentries[0]
        assert reentry["qty"] == 5
        assert reentry["level"] == 20
        assert reentry["rsi"] == 19.5
        assert reentry["price"] == 2480.0
        assert "time" in reentry

    def test_reentry_detected_by_existing_position(
        self, unified_monitor, positions_repo, orders_repo
    ):
        """Test that reentry is detected even if entry_type is not set, when position exists"""
        # Create initial position
        initial_position = Positions(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            reentry_count=0,
            reentries=None,
            initial_entry_price=2500.0,
            last_reentry_price=None,
            opened_at=datetime.now(),
        )

        positions_repo.get_by_symbol = Mock(return_value=initial_position)

        # Create order without entry_type (but position exists, so it's a reentry)
        order = Orders(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=5,
            entry_type=None,  # Not explicitly marked as reentry
            order_metadata={},
        )

        orders_repo.get = Mock(return_value=order)
        orders_repo.get_by_broker_order_id = Mock(return_value=order)

        upsert_call_args = {}

        def capture_upsert(**kwargs):
            upsert_call_args.update(kwargs)
            return initial_position

        positions_repo.upsert = Mock(side_effect=capture_upsert)

        # Execute order
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info={"symbol": "RELIANCE-EQ"},
            execution_price=2480.0,
            execution_qty=5.0,
        )

        # Verify reentry was detected and tracked
        assert upsert_call_args.get("reentry_count") == 1
        assert upsert_call_args.get("last_reentry_price") == 2480.0
        assert upsert_call_args.get("reentries") is not None

    def test_multiple_reentries_accumulate(self, unified_monitor, positions_repo, orders_repo):
        """Test that multiple reentries accumulate correctly"""
        # Create position with one existing reentry
        existing_reentries = [
            {
                "qty": 5,
                "level": 30,
                "rsi": 29.5,
                "price": 2490.0,
                "time": "2024-01-01T10:00:00",
            }
        ]

        initial_position = Positions(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            quantity=15,  # 10 + 5
            avg_price=2495.0,
            reentry_count=1,
            reentries=existing_reentries,
            initial_entry_price=2500.0,
            last_reentry_price=2490.0,
            opened_at=datetime.now(),
        )

        positions_repo.get_by_symbol = Mock(return_value=initial_position)

        # Create second reentry order
        reentry_order = Orders(
            id=2,
            user_id=1,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=3,
            entry_type="reentry",
            order_metadata={
                "rsi_level": 20,
                "rsi": 19.5,
                "price": 2480.0,
                "reentry_index": 2,
            },
        )

        orders_repo.get = Mock(return_value=reentry_order)
        orders_repo.get_by_broker_order_id = Mock(return_value=reentry_order)

        upsert_call_args = {}

        def capture_upsert(**kwargs):
            upsert_call_args.update(kwargs)
            return initial_position

        positions_repo.upsert = Mock(side_effect=capture_upsert)

        # Execute second reentry
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER456",
            order_info={"symbol": "RELIANCE-EQ"},
            execution_price=2480.0,
            execution_qty=3.0,
        )

        # Verify reentry_count increased
        assert upsert_call_args.get("reentry_count") == 2

        # Verify reentries array has both entries
        reentries = upsert_call_args.get("reentries", [])
        assert len(reentries) == 2
        assert reentries[0]["qty"] == 5  # First reentry
        assert reentries[1]["qty"] == 3  # Second reentry
        assert reentries[1]["level"] == 20
        assert reentries[1]["price"] == 2480.0

        # Verify last_reentry_price updated
        assert upsert_call_args.get("last_reentry_price") == 2480.0

    def test_new_position_not_tracked_as_reentry(
        self, unified_monitor, positions_repo, orders_repo
    ):
        """Test that new positions are not tracked as reentries"""
        # No existing position
        positions_repo.get_by_symbol = Mock(return_value=None)

        # Create initial entry order
        initial_order = Orders(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10,
            entry_type="initial",
            order_metadata={"rsi10": 28.5},
        )

        orders_repo.get = Mock(return_value=initial_order)
        orders_repo.get_by_broker_order_id = Mock(return_value=initial_order)

        upsert_call_args = {}

        def capture_upsert(**kwargs):
            upsert_call_args.update(kwargs)
            return Positions(
                id=1,
                user_id=1,
                symbol="RELIANCE",
                quantity=10,
                avg_price=2500.0,
                opened_at=datetime.now(),
            )

        positions_repo.upsert = Mock(side_effect=capture_upsert)

        # Execute initial order
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info={"symbol": "RELIANCE-EQ"},
            execution_price=2500.0,
            execution_qty=10.0,
        )

        # Verify reentry fields are NOT set for new position
        assert upsert_call_args.get("reentry_count") is None
        assert upsert_call_args.get("reentries") is None
        assert upsert_call_args.get("last_reentry_price") is None

    def test_reentry_without_metadata_uses_execution_data(
        self, unified_monitor, positions_repo, orders_repo
    ):
        """Test that reentry data is constructed from execution data when metadata is missing"""
        # Create initial position
        initial_position = Positions(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            reentry_count=0,
            reentries=None,
            initial_entry_price=2500.0,
            last_reentry_price=None,
            opened_at=datetime.now(),
        )

        positions_repo.get_by_symbol = Mock(return_value=initial_position)

        # Create order without metadata
        order = Orders(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=5,
            entry_type="reentry",
            order_metadata=None,  # No metadata
        )

        orders_repo.get = Mock(return_value=order)
        orders_repo.get_by_broker_order_id = Mock(return_value=order)

        upsert_call_args = {}

        def capture_upsert(**kwargs):
            upsert_call_args.update(kwargs)
            return initial_position

        positions_repo.upsert = Mock(side_effect=capture_upsert)

        # Execute reentry
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info={"symbol": "RELIANCE-EQ"},
            execution_price=2480.0,
            execution_qty=5.0,
        )

        # Verify reentry was tracked with fallback data
        assert upsert_call_args.get("reentry_count") == 1
        assert upsert_call_args.get("last_reentry_price") == 2480.0

        reentries = upsert_call_args.get("reentries", [])
        assert len(reentries) == 1
        reentry = reentries[0]
        assert reentry["qty"] == 5
        assert reentry["price"] == 2480.0
        assert reentry["level"] is None  # Not in metadata
        assert "time" in reentry  # Should have timestamp

    def test_initial_entry_price_preserved_on_reentry(
        self, unified_monitor, positions_repo, orders_repo
    ):
        """Test that initial_entry_price is preserved when reentry executes"""
        # Create position with initial_entry_price
        initial_position = Positions(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            reentry_count=0,
            reentries=None,
            initial_entry_price=2500.0,  # Original entry price
            last_reentry_price=None,
            opened_at=datetime.now(),
        )

        positions_repo.get_by_symbol = Mock(return_value=initial_position)

        reentry_order = Orders(
            id=1,
            user_id=1,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=5,
            entry_type="reentry",
            order_metadata={"rsi_level": 20, "rsi": 19.5, "price": 2480.0},
        )

        orders_repo.get = Mock(return_value=reentry_order)
        orders_repo.get_by_broker_order_id = Mock(return_value=reentry_order)

        upsert_call_args = {}

        def capture_upsert(**kwargs):
            upsert_call_args.update(kwargs)
            return initial_position

        positions_repo.upsert = Mock(side_effect=capture_upsert)

        # Execute reentry
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info={"symbol": "RELIANCE-EQ"},
            execution_price=2480.0,
            execution_qty=5.0,
        )

        # Verify initial_entry_price is NOT in upsert call (should be preserved from existing position)
        # The upsert method should not update initial_entry_price for existing positions
        assert (
            "initial_entry_price" not in upsert_call_args
            or upsert_call_args.get("initial_entry_price") is None
        )
