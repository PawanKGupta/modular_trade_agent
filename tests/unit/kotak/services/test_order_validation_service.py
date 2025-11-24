"""
Unit tests for OrderValidationService

Tests verify the consolidated order validation service
maintains backward compatibility with existing validation logic.
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.services.order_validation_service import (
    OrderValidationService,
    ValidationResult,
    get_order_validation_service,
)


class TestValidationResult:
    """Test ValidationResult dataclass"""

    def test_initialization(self):
        """Test ValidationResult initialization"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.data == {}

    def test_initialization_with_data(self):
        """Test ValidationResult initialization with data"""
        data = {"test": "value"}
        result = ValidationResult(
            is_valid=False, errors=["error1"], warnings=["warning1"], data=data
        )

        assert result.is_valid is False
        assert result.errors == ["error1"]
        assert result.warnings == ["warning1"]
        assert result.data == data

    def test_add_error(self):
        """Test add_error() method"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        result.add_error("Test error")

        assert result.is_valid is False
        assert "Test error" in result.errors

    def test_add_warning(self):
        """Test add_warning() method"""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        result.add_warning("Test warning")

        assert result.is_valid is True  # Warnings don't invalidate
        assert "Test warning" in result.warnings

    def test_get_error_summary(self):
        """Test get_error_summary() method"""
        result = ValidationResult(is_valid=False, errors=["Error 1", "Error 2"], warnings=[])

        summary = result.get_error_summary()
        assert "Error 1" in summary
        assert "Error 2" in summary

    def test_get_warning_summary(self):
        """Test get_warning_summary() method"""
        result = ValidationResult(
            is_valid=True, errors=[], warnings=["Warning 1", "Warning 2"]
        )

        summary = result.get_warning_summary()
        assert "Warning 1" in summary
        assert "Warning 2" in summary


class TestOrderValidationServiceInitialization:
    """Test OrderValidationService initialization"""

    def test_init_with_dependencies(self):
        """Test initialization with all dependencies"""
        mock_portfolio_service = Mock()
        mock_portfolio = Mock()
        mock_orders = Mock()
        mock_orders_repo = Mock()
        user_id = 1

        service = OrderValidationService(
            portfolio_service=mock_portfolio_service,
            portfolio=mock_portfolio,
            orders=mock_orders,
            orders_repo=mock_orders_repo,
            user_id=user_id,
        )

        assert service.portfolio_service == mock_portfolio_service
        assert service.portfolio == mock_portfolio
        assert service.orders == mock_orders
        assert service.orders_repo == mock_orders_repo
        assert service.user_id == user_id

    def test_init_without_dependencies(self):
        """Test initialization without dependencies"""
        service = OrderValidationService()

        assert service.portfolio_service is None
        assert service.portfolio is None
        assert service.orders is None

    def test_singleton_pattern(self):
        """Test that get_order_validation_service returns singleton"""
        service1 = get_order_validation_service()
        service2 = get_order_validation_service()

        assert service1 is service2

    def test_singleton_updates_dependencies(self):
        """Test that singleton updates dependencies when provided"""
        mock_portfolio = Mock()
        service1 = get_order_validation_service(portfolio=mock_portfolio)
        assert service1.portfolio == mock_portfolio

        mock_portfolio2 = Mock()
        service2 = get_order_validation_service(portfolio=mock_portfolio2)
        assert service2.portfolio == mock_portfolio2
        assert service1 is service2  # Same instance


class TestOrderValidationServiceCheckBalance:
    """Test check_balance() method"""

    def test_check_balance_sufficient_funds(self):
        """Test balance check with sufficient funds"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 100000.0, "availableCash": 100000.0}}
        )

        service = OrderValidationService(portfolio=mock_portfolio)

        has_sufficient, available_cash, affordable_qty = service.check_balance(2500.0, 10)

        assert has_sufficient is True
        assert available_cash > 0
        assert affordable_qty >= 10

    def test_check_balance_insufficient_funds(self):
        """Test balance check with insufficient funds"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 10000.0, "availableCash": 10000.0}}
        )

        service = OrderValidationService(portfolio=mock_portfolio)

        # Try to buy 10 shares at Rs 2500 = Rs 25000 (more than available)
        has_sufficient, available_cash, affordable_qty = service.check_balance(2500.0, 10)

        assert has_sufficient is False
        assert available_cash == 10000.0
        assert affordable_qty < 10

    def test_check_balance_no_required_qty(self):
        """Test balance check without required quantity"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 100000.0}}
        )

        service = OrderValidationService(portfolio=mock_portfolio)

        has_sufficient, available_cash, affordable_qty = service.check_balance(2500.0, None)

        assert has_sufficient is True  # No requirement, so always sufficient
        assert available_cash > 0
        assert affordable_qty > 0

    def test_check_balance_no_portfolio(self):
        """Test balance check without portfolio"""
        service = OrderValidationService()

        has_sufficient, available_cash, affordable_qty = service.check_balance(2500.0, 10)

        assert has_sufficient is False
        assert available_cash == 0.0
        assert affordable_qty == 0

    def test_check_balance_zero_price(self):
        """Test balance check with zero price"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(return_value={"data": {"cash": 100000.0}})

        service = OrderValidationService(portfolio=mock_portfolio)

        has_sufficient, available_cash, affordable_qty = service.check_balance(0.0, 10)

        assert affordable_qty == 0


class TestOrderValidationServiceGetAvailableCash:
    """Test get_available_cash() method"""

    def test_get_available_cash_with_cash_field(self):
        """Test getting available cash with cash field"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 50000.0, "availableCash": 50000.0}}
        )

        service = OrderValidationService(portfolio=mock_portfolio)

        cash = service.get_available_cash()

        assert cash == 50000.0

    def test_get_available_cash_with_available_cash_field(self):
        """Test getting available cash with availableCash field"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"availableCash": 75000.0, "Net": 80000.0}}
        )

        service = OrderValidationService(portfolio=mock_portfolio)

        cash = service.get_available_cash()

        assert cash == 75000.0  # Should prefer availableCash over Net

    def test_get_available_cash_with_fallback(self):
        """Test getting available cash with fallback to max numeric"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"field1": 30000.0, "field2": 40000.0, "field3": "text"}}
        )

        service = OrderValidationService(portfolio=mock_portfolio)

        cash = service.get_available_cash()

        assert cash == 40000.0  # Should use max numeric value

    def test_get_available_cash_no_portfolio(self):
        """Test getting available cash without portfolio"""
        service = OrderValidationService()

        cash = service.get_available_cash()

        assert cash == 0.0

    def test_get_available_cash_invalid_limits(self):
        """Test getting available cash with invalid limits response"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(return_value=None)

        service = OrderValidationService(portfolio=mock_portfolio)

        cash = service.get_available_cash()

        assert cash == 0.0


class TestOrderValidationServiceGetAffordableQty:
    """Test get_affordable_qty() method"""

    def test_get_affordable_qty_sufficient_cash(self):
        """Test getting affordable quantity with sufficient cash"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 100000.0}}
        )

        service = OrderValidationService(portfolio=mock_portfolio)

        qty = service.get_affordable_qty(2500.0)

        assert qty == 40  # 100000 / 2500 = 40

    def test_get_affordable_qty_insufficient_cash(self):
        """Test getting affordable quantity with insufficient cash"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(return_value={"data": {"cash": 1000.0}})

        service = OrderValidationService(portfolio=mock_portfolio)

        qty = service.get_affordable_qty(2500.0)

        assert qty == 0  # 1000 / 2500 = 0

    def test_get_affordable_qty_zero_price(self):
        """Test getting affordable quantity with zero price"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(return_value={"data": {"cash": 100000.0}})

        service = OrderValidationService(portfolio=mock_portfolio)

        qty = service.get_affordable_qty(0.0)

        assert qty == 0

    def test_get_affordable_qty_no_portfolio(self):
        """Test getting affordable quantity without portfolio"""
        service = OrderValidationService()

        qty = service.get_affordable_qty(2500.0)

        assert qty == 0


class TestOrderValidationServiceCheckPortfolioCapacity:
    """Test check_portfolio_capacity() method"""

    def test_check_portfolio_capacity_with_service(self):
        """Test portfolio capacity check with PortfolioService"""
        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 5, 10)
        )

        service = OrderValidationService(portfolio_service=mock_portfolio_service)

        has_capacity, current_count, max_size = service.check_portfolio_capacity()

        assert has_capacity is True
        assert current_count == 5
        assert max_size == 10
        mock_portfolio_service.check_portfolio_capacity.assert_called_once_with(
            include_pending=True
        )

    def test_check_portfolio_capacity_at_limit(self):
        """Test portfolio capacity check at limit"""
        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(False, 10, 10)
        )

        service = OrderValidationService(portfolio_service=mock_portfolio_service)

        has_capacity, current_count, max_size = service.check_portfolio_capacity()

        assert has_capacity is False
        assert current_count == 10
        assert max_size == 10

    def test_check_portfolio_capacity_without_service(self):
        """Test portfolio capacity check without PortfolioService"""
        service = OrderValidationService()

        has_capacity, current_count, max_size = service.check_portfolio_capacity()

        # Should fallback to assuming capacity available
        assert has_capacity is True
        assert current_count == 0
        assert max_size == 999


class TestOrderValidationServiceCheckDuplicateOrder:
    """Test check_duplicate_order() method"""

    def test_check_duplicate_order_active_buy_order_broker(self):
        """Test duplicate check with active buy order in broker API"""
        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(
            return_value=[
                {"transactionType": "BUY", "tradingSymbol": "RELIANCE-EQ"},
                {"transactionType": "SELL", "tradingSymbol": "TCS-EQ"},
            ]
        )

        service = OrderValidationService(orders=mock_orders)

        is_duplicate, reason = service.check_duplicate_order("RELIANCE")

        assert is_duplicate is True
        assert "Active buy order" in reason

    def test_check_duplicate_order_no_active_order(self):
        """Test duplicate check with no active order"""
        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(
            return_value=[
                {"transactionType": "SELL", "tradingSymbol": "TCS-EQ"},
            ]
        )

        service = OrderValidationService(orders=mock_orders)

        is_duplicate, reason = service.check_duplicate_order("RELIANCE")

        assert is_duplicate is False
        assert reason is None

    def test_check_duplicate_order_in_holdings(self):
        """Test duplicate check when symbol is in holdings"""
        mock_portfolio_service = Mock()
        mock_portfolio_service.has_position = Mock(return_value=True)

        service = OrderValidationService(portfolio_service=mock_portfolio_service)

        is_duplicate, reason = service.check_duplicate_order("RELIANCE")

        assert is_duplicate is True
        assert "Already in holdings" in reason

    @patch("src.infrastructure.db.models.OrderStatus")
    def test_check_duplicate_order_database_fallback(self, mock_db_order_status):
        """Test duplicate check with database fallback"""
        # Set up mock enum values
        mock_db_order_status.PENDING = "PENDING"
        mock_db_order_status.ONGOING = "ONGOING"

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(return_value=[])  # No broker orders

        mock_orders_repo = Mock()
        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.status = "PENDING"  # Match PENDING value

        mock_orders_repo.list = Mock(return_value=[mock_order])

        service = OrderValidationService(
            orders=mock_orders, orders_repo=mock_orders_repo, user_id=1
        )

        is_duplicate, reason = service.check_duplicate_order("RELIANCE")

        assert is_duplicate is True
        assert "database" in reason.lower() or "Active buy order" in reason

    def test_check_duplicate_order_no_checks(self):
        """Test duplicate check with checks disabled"""
        service = OrderValidationService()

        is_duplicate, reason = service.check_duplicate_order(
            "RELIANCE", check_active_buy_order=False, check_holdings=False
        )

        assert is_duplicate is False
        assert reason is None

    def test_check_duplicate_order_symbol_variants(self):
        """Test duplicate check with symbol variants"""
        mock_orders = Mock()
        # Include both variants in pending orders
        mock_orders.get_pending_orders = Mock(
            return_value=[
                {"transactionType": "BUY", "tradingSymbol": "RELIANCE"},
                {"transactionType": "BUY", "tradingSymbol": "RELIANCE-EQ"},
            ]
        )

        service = OrderValidationService(orders=mock_orders)

        # Should match RELIANCE-EQ to RELIANCE (variants match)
        is_duplicate, reason = service.check_duplicate_order("RELIANCE")

        assert is_duplicate is True
        assert "Active buy order" in reason


class TestOrderValidationServiceCheckVolumeRatio:
    """Test check_volume_ratio() method"""

    @patch("modules.kotak_neo_auto_trader.services.order_validation_service.POSITION_VOLUME_RATIO_TIERS")
    def test_check_volume_ratio_valid(self, mock_tiers):
        """Test volume ratio check with valid ratio"""
        mock_tiers.return_value = [
            (5000, 0.02),
            (1000, 0.05),
            (500, 0.10),
            (0, 0.20),
        ]

        service = OrderValidationService()

        # 100 shares, 1M volume = 0.01% (well below 2% limit for Rs 2500)
        is_valid, ratio, tier_info = service.check_volume_ratio(
            100, 1000000.0, "RELIANCE", 2500.0
        )

        assert is_valid is True
        assert ratio is not None
        assert tier_info is not None

    @patch("modules.kotak_neo_auto_trader.services.order_validation_service.POSITION_VOLUME_RATIO_TIERS")
    def test_check_volume_ratio_invalid(self, mock_tiers):
        """Test volume ratio check with invalid ratio"""
        mock_tiers.return_value = [
            (5000, 0.02),
            (1000, 0.05),
            (500, 0.10),
            (0, 0.20),
        ]

        service = OrderValidationService()

        # 1000 shares, 1000 volume = 100% (exceeds 20% limit)
        is_valid, ratio, tier_info = service.check_volume_ratio(
            1000, 1000.0, "STOCK", 100.0
        )

        assert is_valid is False
        assert ratio == 1.0  # 100%
        assert tier_info is not None

    def test_check_volume_ratio_zero_volume(self):
        """Test volume ratio check with zero volume"""
        service = OrderValidationService()

        is_valid, ratio, tier_info = service.check_volume_ratio(
            100, 0.0, "STOCK", 100.0
        )

        assert is_valid is False
        assert ratio is None
        assert tier_info is None

    def test_check_volume_ratio_price_tiers(self):
        """Test volume ratio check with different price tiers"""
        # Mock POSITION_VOLUME_RATIO_TIERS at the module level
        with patch(
            "modules.kotak_neo_auto_trader.services.order_validation_service.POSITION_VOLUME_RATIO_TIERS",
            [
                (5000, 0.02),  # > Rs 5000: 2%
                (1000, 0.05),  # Rs 1000-5000: 5%
                (500, 0.10),  # Rs 500-1000: 10%
                (0, 0.20),  # < Rs 500: 20%
            ],
        ):
            service = OrderValidationService()

            # Test Rs 6000 stock (should use 2% limit)
            is_valid, ratio, tier_info = service.check_volume_ratio(
                10000, 500000.0, "STOCK", 6000.0  # 2% ratio, at limit
            )

            assert is_valid is True  # 2% is within 2% limit
            assert "5000" in tier_info or "Rs" in tier_info

            # Test Rs 300 stock (should use 20% limit)
            is_valid2, ratio2, tier_info2 = service.check_volume_ratio(
                1000, 10000.0, "STOCK2", 300.0  # 10% ratio, within 20% limit
            )

            assert is_valid2 is True
            # Check for tier info indicating < Rs 500 tier
            assert "500" in tier_info2 or "20" in tier_info2 or "Rs" in tier_info2


class TestOrderValidationServiceValidateOrderPlacement:
    """Test validate_order_placement() comprehensive method"""

    def test_validate_order_placement_all_valid(self):
        """Test comprehensive validation with all checks passing"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 100000.0}}
        )

        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 3, 10)
        )
        mock_portfolio_service.has_position = Mock(return_value=False)

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(return_value=[])

        service = OrderValidationService(
            portfolio=mock_portfolio,
            portfolio_service=mock_portfolio_service,
            orders=mock_orders,
        )

        result = service.validate_order_placement(
            symbol="RELIANCE",
            price=2500.0,
            qty=10,
            avg_volume=1000000.0,
        )

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_order_placement_insufficient_balance(self):
        """Test validation with insufficient balance"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(return_value={"data": {"cash": 1000.0}})

        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 3, 10)
        )
        mock_portfolio_service.has_position = Mock(return_value=False)

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(return_value=[])

        service = OrderValidationService(
            portfolio=mock_portfolio,
            portfolio_service=mock_portfolio_service,
            orders=mock_orders,
        )

        result = service.validate_order_placement(
            symbol="RELIANCE",
            price=2500.0,
            qty=10,  # Requires Rs 25000, but only Rs 1000 available
            avg_volume=1000000.0,
        )

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Insufficient balance" in result.get_error_summary()

    def test_validate_order_placement_portfolio_at_capacity(self):
        """Test validation with portfolio at capacity"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 100000.0}}
        )

        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(False, 10, 10)
        )
        mock_portfolio_service.has_position = Mock(return_value=False)

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(return_value=[])

        service = OrderValidationService(
            portfolio=mock_portfolio,
            portfolio_service=mock_portfolio_service,
            orders=mock_orders,
        )

        result = service.validate_order_placement(
            symbol="RELIANCE",
            price=2500.0,
            qty=10,
            avg_volume=1000000.0,
        )

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Portfolio at capacity" in result.get_error_summary()

    def test_validate_order_placement_duplicate_order(self):
        """Test validation with duplicate order"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 100000.0}}
        )

        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 3, 10)
        )
        mock_portfolio_service.has_position = Mock(return_value=True)  # Already in holdings

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(return_value=[])

        service = OrderValidationService(
            portfolio=mock_portfolio,
            portfolio_service=mock_portfolio_service,
            orders=mock_orders,
        )

        result = service.validate_order_placement(
            symbol="RELIANCE",
            price=2500.0,
            qty=10,
            avg_volume=1000000.0,
        )

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Duplicate order" in result.get_error_summary()

    @patch("modules.kotak_neo_auto_trader.services.order_validation_service.POSITION_VOLUME_RATIO_TIERS")
    def test_validate_order_placement_invalid_volume_ratio(self, mock_tiers):
        """Test validation with invalid volume ratio"""
        mock_tiers.return_value = [
            (5000, 0.02),
            (1000, 0.05),
            (500, 0.10),
            (0, 0.20),
        ]

        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 100000.0}}
        )

        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 3, 10)
        )
        mock_portfolio_service.has_position = Mock(return_value=False)

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(return_value=[])

        service = OrderValidationService(
            portfolio=mock_portfolio,
            portfolio_service=mock_portfolio_service,
            orders=mock_orders,
        )

        result = service.validate_order_placement(
            symbol="STOCK",
            price=100.0,
            qty=1000,  # 1000 shares
            avg_volume=1000.0,  # 1000 volume = 100% ratio (exceeds 20% limit)
        )

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "volume" in result.get_error_summary().lower()

    def test_validate_order_placement_selective_checks(self):
        """Test validation with selective checks enabled/disabled"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 1000.0}}  # Insufficient for qty=10
        )

        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(False, 10, 10)  # At capacity
        )

        service = OrderValidationService(
            portfolio=mock_portfolio, portfolio_service=mock_portfolio_service
        )

        # Disable balance and capacity checks - should pass
        result = service.validate_order_placement(
            symbol="RELIANCE",
            price=2500.0,
            qty=10,
            check_balance=False,
            check_capacity=False,
            check_duplicate=False,
            check_volume=False,
        )

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_order_placement_data_included(self):
        """Test that validation result includes data"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 100000.0}}
        )

        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 5, 10)
        )
        mock_portfolio_service.has_position = Mock(return_value=False)

        service = OrderValidationService(
            portfolio=mock_portfolio, portfolio_service=mock_portfolio_service
        )

        result = service.validate_order_placement(
            symbol="RELIANCE",
            price=2500.0,
            qty=10,
            avg_volume=1000000.0,
        )

        assert result.data is not None
        assert "available_cash" in result.data
        assert "affordable_qty" in result.data
        assert "required_cash" in result.data
        assert "current_portfolio_count" in result.data
        assert "max_portfolio_size" in result.data


class TestOrderValidationServiceBackwardCompatibility:
    """Test backward compatibility with existing validation logic"""

    def test_check_balance_backward_compatibility(self):
        """Test that check_balance() maintains backward compatibility"""
        mock_portfolio = Mock()
        mock_portfolio.get_limits = Mock(
            return_value={"data": {"cash": 100000.0}}
        )

        service = OrderValidationService(portfolio=mock_portfolio)

        has_sufficient, available_cash, affordable_qty = service.check_balance(2500.0, 10)

        assert isinstance(has_sufficient, bool)
        assert isinstance(available_cash, (int, float))
        assert isinstance(affordable_qty, int)

    def test_validate_order_placement_result_structure(self):
        """Test that ValidationResult structure is consistent"""
        service = OrderValidationService()

        result = service.validate_order_placement(
            symbol="RELIANCE",
            price=2500.0,
            qty=10,
            avg_volume=1000000.0,
            check_balance=False,
            check_capacity=False,
            check_duplicate=False,
            check_volume=False,
        )

        assert isinstance(result, ValidationResult)
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.data, dict)

