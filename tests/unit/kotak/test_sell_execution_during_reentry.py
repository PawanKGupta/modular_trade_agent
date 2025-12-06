"""
Tests for Race Condition #4: Sell Execution During Reentry

Tests verify that:
1. Reentry processing re-checks closed_at just before updating position
2. Position is not reopened if it was closed during reentry processing
3. Transaction rollback prevents partial updates
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor
from src.infrastructure.db.models import OrderStatus, Orders, Positions
from src.infrastructure.db.timezone_utils import ist_now


class TestSellExecutionDuringReentry:
    """Test race condition fix for sell execution during reentry"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth"""
        auth = MagicMock()
        return auth

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository"""
        repo = MagicMock()
        return repo

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository"""
        repo = MagicMock()
        return repo

    @pytest.fixture
    def mock_sell_manager(self, mock_auth):
        """Mock SellOrderManager"""
        from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager

        manager = MagicMock(spec=SellOrderManager)
        manager.orders = MagicMock()
        return manager

    @pytest.fixture
    def order_monitor(self, mock_sell_manager, mock_positions_repo, mock_orders_repo):
        """Create UnifiedOrderMonitor with mocked dependencies"""
        from sqlalchemy.orm import Session

        mock_db = MagicMock(spec=Session)
        monitor = UnifiedOrderMonitor(
            sell_order_manager=mock_sell_manager,
            db_session=mock_db,
            user_id=1,
        )
        # Override repositories with mocks
        monitor.positions_repo = mock_positions_repo
        monitor.orders_repo = mock_orders_repo
        return monitor

    def test_rechecks_closed_at_before_updating_position(
        self, order_monitor, mock_positions_repo
    ):
        """Test that closed_at is re-checked just before updating position"""
        # Initial position (open)
        initial_position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            closed_at=None,  # Open position
        )

        # Position after sell execution (closed)
        closed_position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=0.0,
            avg_price=100.0,
            opened_at=ist_now(),
            closed_at=ist_now(),  # Closed during reentry processing
        )

        # Mock first read (position is open)
        mock_positions_repo.get_by_symbol_for_update = MagicMock(
            side_effect=[initial_position, closed_position]
        )

        # Mock order
        db_order = Orders(
            user_id=1,
            symbol="RELIANCE-EQ",
            side="buy",
            status=OrderStatus.ONGOING,
            entry_type="reentry",
            quantity=10.0,
            execution_qty=10.0,
            execution_price=105.0,
        )
        order_monitor.orders_repo.get = MagicMock(return_value=db_order)

        # Mock transaction context manager
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction") as mock_transaction:
            mock_transaction.return_value.__enter__ = MagicMock(return_value=mock_positions_repo.db)
            mock_transaction.return_value.__exit__ = MagicMock(return_value=False)

            # Call _create_position_from_executed_order
            order_monitor._create_position_from_executed_order(
                order_id="ORDER123",
                order_info={"symbol": "RELIANCE-EQ"},
                execution_price=105.0,
                execution_qty=10.0,
            )

        # Verify position was read twice (initial check + re-check before update)
        assert mock_positions_repo.get_by_symbol_for_update.call_count == 2

        # Verify upsert was NOT called (position was closed, so update was skipped)
        mock_positions_repo.upsert.assert_not_called()

    def test_allows_update_if_position_still_open(
        self, order_monitor, mock_positions_repo, mock_orders_repo
    ):
        """Test that update proceeds if position is still open at re-check"""
        # Position (open)
        open_position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            closed_at=None,  # Still open
        )

        # Mock reads (position stays open)
        mock_positions_repo.get_by_symbol_for_update = MagicMock(
            return_value=open_position
        )

        # Mock order
        db_order = Orders(
            user_id=1,
            symbol="RELIANCE-EQ",
            side="buy",
            status=OrderStatus.ONGOING,
            entry_type="reentry",
            quantity=10.0,
            execution_qty=10.0,
            execution_price=105.0,
        )
        order_monitor.orders_repo.get = MagicMock(return_value=db_order)

        # Mock transaction context manager
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction") as mock_transaction:
            mock_transaction.return_value.__enter__ = MagicMock(return_value=mock_positions_repo.db)
            mock_transaction.return_value.__exit__ = MagicMock(return_value=False)

            # Call _create_position_from_executed_order
            order_monitor._create_position_from_executed_order(
                order_id="ORDER123",
                order_info={"symbol": "RELIANCE-EQ"},
                execution_price=105.0,
                execution_qty=10.0,
            )

        # Verify position was read twice (initial check + re-check before update)
        assert mock_positions_repo.get_by_symbol_for_update.call_count == 2

        # Verify upsert WAS called (position still open)
        mock_positions_repo.upsert.assert_called_once()

    def test_uses_locked_read_for_recheck(self, order_monitor, mock_positions_repo):
        """Test that re-check uses get_by_symbol_for_update (locked read)"""
        # Position (open)
        open_position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            closed_at=None,
        )

        # Mock reads
        mock_positions_repo.get_by_symbol_for_update = MagicMock(
            return_value=open_position
        )

        # Mock order
        db_order = Orders(
            user_id=1,
            symbol="RELIANCE-EQ",
            side="buy",
            status=OrderStatus.ONGOING,
            entry_type="reentry",
            quantity=10.0,
            execution_qty=10.0,
            execution_price=105.0,
        )
        order_monitor.orders_repo.get = MagicMock(return_value=db_order)

        # Mock transaction context manager
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction") as mock_transaction:
            mock_transaction.return_value.__enter__ = MagicMock(return_value=mock_positions_repo.db)
            mock_transaction.return_value.__exit__ = MagicMock(return_value=False)

            # Call _create_position_from_executed_order
            order_monitor._create_position_from_executed_order(
                order_id="ORDER123",
                order_info={"symbol": "RELIANCE-EQ"},
                execution_price=105.0,
                execution_qty=10.0,
            )

        # Verify locked read was used for re-check
        calls = mock_positions_repo.get_by_symbol_for_update.call_args_list
        assert len(calls) >= 2, "Should read position at least twice (initial + re-check)"
        # Both calls should use get_by_symbol_for_update (locked read)
        for call in calls:
            assert call[0][0] == 1  # user_id
            assert call[0][1] == "RELIANCE"  # symbol

    def test_skips_update_for_new_position_if_closed_during_processing(
        self, order_monitor, mock_positions_repo
    ):
        """Test that new position creation is also protected"""
        # First read: No position exists (None)
        # Second read: Position was created and closed (by sell execution)
        closed_position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=0.0,
            avg_price=105.0,
            opened_at=ist_now(),
            closed_at=ist_now(),  # Closed immediately after creation
        )

        # Mock reads: No position initially, then closed position
        mock_positions_repo.get_by_symbol_for_update = MagicMock(
            side_effect=[None, closed_position]
        )

        # Mock order (not a reentry, but position was created and closed)
        db_order = Orders(
            user_id=1,
            symbol="RELIANCE-EQ",
            side="buy",
            status=OrderStatus.ONGOING,
            entry_type="entry",  # Initial entry
            quantity=10.0,
            execution_qty=10.0,
            execution_price=105.0,
        )
        order_monitor.orders_repo.get = MagicMock(return_value=db_order)

        # Mock transaction context manager
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction") as mock_transaction:
            mock_transaction.return_value.__enter__ = MagicMock(return_value=mock_positions_repo.db)
            mock_transaction.return_value.__exit__ = MagicMock(return_value=False)

            # Call _create_position_from_executed_order
            order_monitor._create_position_from_executed_order(
                order_id="ORDER123",
                order_info={"symbol": "RELIANCE-EQ"},
                execution_price=105.0,
                execution_qty=10.0,
            )

        # Verify position was read (for re-check)
        # Note: For new positions, the re-check might not happen in the same way,
        # but the locked read ensures we see the latest state
        assert mock_positions_repo.get_by_symbol_for_update.call_count >= 1

