"""
Tests for OrderValidationService.allow_reentry parameter

Tests verify that allow_reentry=True skips holdings check,
allowing reentries to buy more of existing positions.
"""

from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.services.order_validation_service import (
    OrderValidationService,
)


class TestOrderValidationServiceAllowReentry:
    """Test allow_reentry parameter in check_duplicate_order()"""

    def test_allow_reentry_skips_holdings_check(self):
        """Test that allow_reentry=True skips holdings check"""
        mock_portfolio_service = Mock()
        mock_portfolio_service.has_position = Mock(return_value=True)

        service = OrderValidationService(portfolio_service=mock_portfolio_service)

        # With allow_reentry=False, should detect duplicate
        is_duplicate, reason = service.check_duplicate_order(
            "RELIANCE", check_holdings=True, allow_reentry=False
        )
        assert is_duplicate is True
        assert "holdings" in reason.lower()
        mock_portfolio_service.has_position.assert_called()

        # Reset mock
        mock_portfolio_service.reset_mock()

        # With allow_reentry=True, should skip holdings check
        is_duplicate, reason = service.check_duplicate_order(
            "RELIANCE", check_holdings=True, allow_reentry=True
        )
        assert is_duplicate is False
        assert reason is None
        # Holdings check should not be called
        mock_portfolio_service.has_position.assert_not_called()

    def test_allow_reentry_skips_positions_table_check(self):
        """Test that allow_reentry=True skips positions table check"""
        mock_orders_repo = Mock()
        mock_position = Mock()
        mock_position.closed_at = None
        mock_position.quantity = 10.0

        mock_orders_repo.db = Mock()  # Mock db session
        mock_orders_repo.list = Mock(return_value=[])

        # Mock PositionsRepository
        mock_positions_repo = Mock()
        mock_positions_repo.get_by_symbol = Mock(return_value=mock_position)

        service = OrderValidationService(orders_repo=mock_orders_repo, user_id=1)

        # Mock the PositionsRepository import where it's used (inside the method)
        with patch(
            "src.infrastructure.persistence.positions_repository.PositionsRepository",
            return_value=mock_positions_repo,
        ):
            # With allow_reentry=False, should detect duplicate in positions table
            is_duplicate, reason = service.check_duplicate_order(
                "RELIANCE", check_holdings=True, allow_reentry=False
            )
            assert is_duplicate is True
            assert "positions table" in reason.lower()

            # Reset mock
            mock_positions_repo.reset_mock()

            # With allow_reentry=True, should skip positions table check
            is_duplicate, reason = service.check_duplicate_order(
                "RELIANCE", check_holdings=True, allow_reentry=True
            )
            assert is_duplicate is False
            assert reason is None
            # Positions table check should not be called
            mock_positions_repo.get_by_symbol.assert_not_called()

    def test_allow_reentry_still_checks_active_buy_orders(self):
        """Test that allow_reentry=True still checks for active buy orders"""
        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(
            return_value=[
                {"transactionType": "BUY", "tradingSymbol": "RELIANCE-EQ"},
            ]
        )

        service = OrderValidationService(orders=mock_orders)

        # With allow_reentry=True, should still detect active buy order
        is_duplicate, reason = service.check_duplicate_order(
            "RELIANCE", check_active_buy_order=True, allow_reentry=True
        )
        assert is_duplicate is True
        assert "Active buy order" in reason

    def test_allow_reentry_with_database_active_orders(self):
        """Test that allow_reentry=True still checks database for active buy orders"""
        mock_orders_repo = Mock()
        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.status = "PENDING"

        mock_orders_repo.list = Mock(return_value=[mock_order])

        service = OrderValidationService(orders_repo=mock_orders_repo, user_id=1)

        with patch("src.infrastructure.db.models.OrderStatus") as mock_status:
            mock_status.PENDING = "PENDING"
            mock_status.ONGOING = "ONGOING"

            # With allow_reentry=True, should still detect active buy order in DB
            is_duplicate, reason = service.check_duplicate_order(
                "RELIANCE",
                check_active_buy_order=True,
                check_holdings=True,
                allow_reentry=True,
            )
            assert is_duplicate is True
            assert "database" in reason.lower() or "Active buy order" in reason

    def test_allow_reentry_allows_buying_more_of_existing_position(self):
        """Test that allow_reentry=True allows buying more of existing position"""
        mock_portfolio_service = Mock()
        mock_portfolio_service.has_position = Mock(return_value=True)

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(return_value=[])  # No active orders

        service = OrderValidationService(
            orders=mock_orders, portfolio_service=mock_portfolio_service
        )

        # With allow_reentry=True and no active orders, should allow reentry
        is_duplicate, reason = service.check_duplicate_order(
            "RELIANCE",
            check_active_buy_order=True,
            check_holdings=True,
            allow_reentry=True,
        )
        assert is_duplicate is False
        assert reason is None

    def test_allow_reentry_defaults_to_false(self):
        """Test that allow_reentry defaults to False (backward compatibility)"""
        mock_portfolio_service = Mock()
        mock_portfolio_service.has_position = Mock(return_value=True)

        service = OrderValidationService(portfolio_service=mock_portfolio_service)

        # Default behavior (allow_reentry=False) should detect duplicate
        is_duplicate, reason = service.check_duplicate_order("RELIANCE", check_holdings=True)
        assert is_duplicate is True
        assert "holdings" in reason.lower()
