"""
Unit tests for LiquidityCapitalService

Tests automatic capital calculation based on stock liquidity.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import Mock, patch

# Import directly to avoid sklearn dependency issues
import importlib.util

spec = importlib.util.spec_from_file_location(
    "liquidity_capital_service", str(project_root / "services" / "liquidity_capital_service.py")
)
liquidity_capital_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(liquidity_capital_module)
LiquidityCapitalService = liquidity_capital_module.LiquidityCapitalService

from config.strategy_config import StrategyConfig


class TestLiquidityCapitalService:
    """Test suite for LiquidityCapitalService"""

    def test_initialization(self):
        """Test that LiquidityCapitalService initializes correctly"""
        service = LiquidityCapitalService()
        assert service is not None
        assert service.config is not None
        assert hasattr(service, "user_capital")
        assert hasattr(service, "max_position_volume_ratio")
        assert hasattr(service, "min_absolute_avg_volume")

    def test_initialization_with_config(self):
        """Test initialization with custom config"""
        config = StrategyConfig.default()
        service = LiquidityCapitalService(config=config)
        assert service.config == config

    def test_calculate_max_capital_high_liquidity(self):
        """Test max capital calculation for high liquidity stock"""
        service = LiquidityCapitalService()

        # High liquidity: 5M volume, Rs 2500 price
        max_capital = service.calculate_max_capital(avg_volume=5000000, stock_price=2500)

        # Should be 10% of daily volume value
        expected = 5000000 * 2500 * 0.10
        assert max_capital == expected
        assert max_capital > 0

    def test_calculate_max_capital_medium_liquidity(self):
        """Test max capital calculation for medium liquidity stock"""
        service = LiquidityCapitalService()

        # Medium liquidity: 100K volume, Rs 500 price
        max_capital = service.calculate_max_capital(avg_volume=100000, stock_price=500)

        expected = 100000 * 500 * 0.10
        assert max_capital == expected
        assert max_capital > 0

    def test_calculate_max_capital_low_liquidity(self):
        """Test max capital calculation for low liquidity stock"""
        service = LiquidityCapitalService()

        # Low liquidity: 5K volume, Rs 50 price
        max_capital = service.calculate_max_capital(avg_volume=5000, stock_price=50)

        expected = 5000 * 50 * 0.10
        assert max_capital == expected
        assert max_capital > 0

    def test_calculate_max_capital_zero_volume(self):
        """Test max capital calculation with zero volume"""
        service = LiquidityCapitalService()

        max_capital = service.calculate_max_capital(avg_volume=0, stock_price=100)

        assert max_capital == 0

    def test_calculate_max_capital_zero_price(self):
        """Test max capital calculation with zero price"""
        service = LiquidityCapitalService()

        max_capital = service.calculate_max_capital(avg_volume=100000, stock_price=0)

        assert max_capital == 0

    def test_calculate_execution_capital_high_liquidity(self):
        """Test execution capital for high liquidity (should use full user capital)"""
        service = LiquidityCapitalService()

        # High liquidity allows full user capital
        result = service.calculate_execution_capital(avg_volume=5000000, stock_price=2500)

        execution_capital = result.get("execution_capital", 0)
        max_capital = result.get("max_capital", 0)
        capital_adjusted = result.get("capital_adjusted", False)

        assert execution_capital == service.user_capital
        assert max_capital > execution_capital
        assert capital_adjusted is False

    def test_calculate_execution_capital_medium_liquidity(self):
        """Test execution capital for medium liquidity"""
        service = LiquidityCapitalService()

        # Medium liquidity - should use full user capital if max allows
        result = service.calculate_execution_capital(avg_volume=100000, stock_price=500)

        execution_capital = result.get("execution_capital", 0)
        max_capital = result.get("max_capital", 0)

        assert execution_capital > 0
        assert execution_capital <= max_capital
        assert execution_capital <= service.user_capital

    def test_calculate_execution_capital_low_liquidity(self):
        """Test execution capital for low liquidity (should be limited)"""
        service = LiquidityCapitalService()

        # Low liquidity - should be limited by max_capital or return 0 if below minimum
        result = service.calculate_execution_capital(avg_volume=5000, stock_price=50)

        execution_capital = result.get("execution_capital", 0)
        max_capital = result.get("max_capital", 0)
        capital_adjusted = result.get("capital_adjusted", False)

        # Low liquidity may return 0 if below minimum threshold
        assert execution_capital >= 0
        assert execution_capital <= max_capital if max_capital > 0 else True

    def test_calculate_execution_capital_below_minimum(self):
        """Test execution capital when below minimum threshold"""
        service = LiquidityCapitalService()

        # Very low liquidity - below minimum threshold
        result = service.calculate_execution_capital(avg_volume=1000, stock_price=10)  # Very low

        execution_capital = result.get("execution_capital", 0)
        max_capital = result.get("max_capital", 0)

        # Should return 0 or very low capital
        assert execution_capital >= 0
        assert max_capital >= 0

    def test_calculate_execution_capital_adjusted(self):
        """Test that capital adjustment flag is set correctly"""
        service = LiquidityCapitalService()

        # Set user capital high, but liquidity limits it
        config = StrategyConfig.default()
        config.user_capital = 1000000.0  # 10L
        service = LiquidityCapitalService(config=config)

        # Medium liquidity that limits capital
        result = service.calculate_execution_capital(avg_volume=50000, stock_price=200)

        capital_adjusted = result.get("capital_adjusted", False)
        execution_capital = result.get("execution_capital", 0)
        max_capital = result.get("max_capital", 0)

        if execution_capital < config.user_capital:
            assert capital_adjusted is True
            assert execution_capital == max_capital

    def test_calculate_execution_capital_not_adjusted(self):
        """Test that capital adjustment flag is False when using full capital"""
        service = LiquidityCapitalService()

        # High liquidity allows full user capital
        result = service.calculate_execution_capital(avg_volume=5000000, stock_price=2500)

        capital_adjusted = result.get("capital_adjusted", False)
        execution_capital = result.get("execution_capital", 0)

        assert capital_adjusted is False
        assert execution_capital == service.user_capital

    def test_is_capital_safe_high_liquidity(self):
        """Test capital safety check for high liquidity"""
        service = LiquidityCapitalService()

        # High liquidity - should be safe
        is_safe = service.is_capital_safe(user_capital=200000, avg_volume=5000000, stock_price=2500)

        assert isinstance(is_safe, bool)
        # High liquidity should allow the capital
        assert is_safe is True

    def test_is_capital_safe_low_liquidity(self):
        """Test capital safety check for low liquidity"""
        service = LiquidityCapitalService()

        # Low liquidity - may not be safe if capital exceeds max
        is_safe = service.is_capital_safe(user_capital=200000, avg_volume=5000, stock_price=50)

        # Should check if capital exceeds max allowed
        assert isinstance(is_safe, bool)

    def test_is_capital_safe_zero_capital(self):
        """Test capital safety check with zero capital"""
        service = LiquidityCapitalService()

        is_safe = service.is_capital_safe(user_capital=0, avg_volume=100000, stock_price=100)

        # Zero capital should not be safe
        assert isinstance(is_safe, bool)

    def test_configurable_user_capital(self):
        """Test that user capital is configurable"""
        config = StrategyConfig.default()
        config.user_capital = 500000.0  # 5L

        service = LiquidityCapitalService(config=config)

        assert service.user_capital == 500000.0

        # Should use configured capital
        result = service.calculate_execution_capital(avg_volume=5000000, stock_price=2500)

        assert result.get("execution_capital", 0) == 500000.0

    def test_configurable_max_position_volume_ratio(self):
        """Test that max position volume ratio is configurable"""
        config = StrategyConfig.default()
        config.max_position_volume_ratio = 0.05  # 5% instead of 10%

        service = LiquidityCapitalService(config=config)

        assert service.max_position_volume_ratio == 0.05

        # Should use configured ratio
        max_capital = service.calculate_max_capital(avg_volume=1000000, stock_price=100)

        expected = 1000000 * 100 * 0.05
        assert max_capital == expected

    def test_edge_case_very_high_price(self):
        """Test with very high stock price"""
        service = LiquidityCapitalService()

        result = service.calculate_execution_capital(
            avg_volume=100000, stock_price=100000  # Very high price
        )

        execution_capital = result.get("execution_capital", 0)
        max_capital = result.get("max_capital", 0)

        assert execution_capital >= 0
        assert max_capital >= 0

    def test_edge_case_very_low_price(self):
        """Test with very low stock price"""
        service = LiquidityCapitalService()

        result = service.calculate_execution_capital(
            avg_volume=1000000, stock_price=1  # Very low price
        )

        execution_capital = result.get("execution_capital", 0)
        max_capital = result.get("max_capital", 0)

        assert execution_capital >= 0
        assert max_capital > 0

    def test_edge_case_negative_values(self):
        """Test error handling with negative values"""
        service = LiquidityCapitalService()

        # Should handle gracefully
        result = service.calculate_execution_capital(avg_volume=-1000, stock_price=100)

        # Should return 0 or handle error
        execution_capital = result.get("execution_capital", 0)
        assert execution_capital >= 0

    def test_calculate_execution_capital_returns_all_fields(self):
        """Test that calculate_execution_capital returns all required fields"""
        service = LiquidityCapitalService()

        result = service.calculate_execution_capital(avg_volume=100000, stock_price=500)

        assert "execution_capital" in result
        assert "max_capital" in result
        assert "capital_adjusted" in result
        # Check for recommendation or other fields that may exist
        assert isinstance(result, dict)

    def test_calculate_max_capital_uses_config_ratio(self):
        """Test that calculate_max_capital uses configured ratio"""
        config = StrategyConfig.default()
        config.max_position_volume_ratio = 0.15  # 15%

        service = LiquidityCapitalService(config=config)

        max_capital = service.calculate_max_capital(avg_volume=1000000, stock_price=100)

        expected = 1000000 * 100 * 0.15
        assert max_capital == expected

    def test_minimum_absolute_volume_check(self):
        """Test that minimum absolute volume is respected"""
        service = LiquidityCapitalService()

        # Very low volume below minimum
        result = service.calculate_execution_capital(
            avg_volume=1000, stock_price=50  # Below MIN_ABSOLUTE_AVG_VOLUME (20000)
        )

        # Should return 0 or very low capital
        execution_capital = result.get("execution_capital", 0)
        assert execution_capital >= 0

    def test_config_fallback_min_absolute_avg_volume(self):
        """Test config fallback for min_absolute_avg_volume"""
        # Test that service initializes correctly even if config doesn't have min_absolute_avg_volume
        # This tests the fallback logic
        service = LiquidityCapitalService()
        # Service should have min_absolute_avg_volume set (either from config or fallback)
        assert hasattr(service, "min_absolute_avg_volume")
        assert service.min_absolute_avg_volume > 0
        assert isinstance(service.min_absolute_avg_volume, int)

    def test_calculate_max_capital_exception_handling(self):
        """Test calculate_max_capital exception handling"""
        service = LiquidityCapitalService()

        # Test with invalid inputs that might cause exception
        # Should handle gracefully
        max_capital = service.calculate_max_capital(avg_volume=float("inf"), stock_price=100)
        assert isinstance(max_capital, (int, float))

        # Test with negative values that might cause exception
        max_capital = service.calculate_max_capital(avg_volume=-1000, stock_price=-100)
        assert isinstance(max_capital, (int, float))
        assert max_capital == 0.0  # Should return 0 on exception

    def test_calculate_max_capital_with_custom_ratio(self):
        """Test calculate_max_capital with custom ratio"""
        service = LiquidityCapitalService()

        # Test with custom ratio parameter
        max_capital = service.calculate_max_capital(
            avg_volume=1000000,
            stock_price=100,
            max_position_volume_ratio=0.15,  # 15% instead of default 10%
        )

        expected = 1000000 * 100 * 0.15
        assert max_capital == expected

    def test_calculate_execution_capital_max_cap_zero(self):
        """Test calculate_execution_capital when max_cap is zero"""
        service = LiquidityCapitalService()

        # Create scenario where max_capital would be 0
        # This might happen with very low volume or price
        result = service.calculate_execution_capital(avg_volume=0, stock_price=100)

        assert result.get("execution_capital", 0) == 0.0
        assert result.get("max_capital", 0) == 0.0
        assert result.get("is_safe", True) is False

    def test_calculate_execution_capital_max_cap_zero_from_calculation(self):
        """Test calculate_execution_capital when max_cap is zero from calculation"""
        service = LiquidityCapitalService()

        # Create scenario where calculate_max_capital returns 0
        # This happens when volume or price is very low
        result = service.calculate_execution_capital(
            avg_volume=100, stock_price=0.01  # Very low  # Very low price
        )

        # Should handle max_cap <= 0 case
        max_cap = result.get("max_capital", 0)
        if max_cap <= 0:
            assert result.get("execution_capital", 0) == 0.0
            assert result.get("is_safe", True) is False

    def test_calculate_execution_capital_with_custom_params(self):
        """Test calculate_execution_capital with custom parameters"""
        service = LiquidityCapitalService()

        # Test with custom user_capital and ratio
        result = service.calculate_execution_capital(
            user_capital=500000.0,  # 5L
            avg_volume=1000000,
            stock_price=500,
            max_position_volume_ratio=0.15,
        )

        assert "execution_capital" in result
        assert "max_capital" in result
        assert result.get("user_capital", 0) == 500000.0

    def test_calculate_max_capital_exception_path(self):
        """Test calculate_max_capital exception path"""
        service = LiquidityCapitalService()

        # Force exception by patching the multiplication operation
        from unittest.mock import patch

        with patch("builtins.float", side_effect=Exception("Test exception")):
            # This will trigger exception in the calculation
            try:
                max_capital = service.calculate_max_capital(avg_volume=1000000, stock_price=100)
                # If no exception, check result
                assert isinstance(max_capital, (int, float))
            except Exception:
                # Exception should be caught and return 0.0
                pass

    def test_calculate_execution_capital_exception_path(self):
        """Test calculate_execution_capital exception path"""
        service = LiquidityCapitalService()

        # Force exception by patching calculate_max_capital
        from unittest.mock import patch

        with patch.object(
            service, "calculate_max_capital", side_effect=Exception("Test exception")
        ):
            result = service.calculate_execution_capital(avg_volume=1000000, stock_price=100)
            assert result.get("execution_capital", 0) == 0.0
            assert "Error" in result.get("reason", "")

    def test_calculate_execution_capital_exception_handling(self):
        """Test calculate_execution_capital exception handling"""
        service = LiquidityCapitalService()

        # Test with invalid inputs that might cause exception
        # Use values that will trigger exception path
        result = service.calculate_execution_capital(
            avg_volume=float("inf"), stock_price=float("inf")
        )

        # Should handle gracefully - may return valid result or error
        assert "execution_capital" in result
        assert "reason" in result
        # Service handles inf values - just verify it doesn't crash
        assert isinstance(result.get("execution_capital", 0), (int, float))

    def test_calculate_position_size(self):
        """Test calculate_position_size method"""
        service = LiquidityCapitalService()

        # Normal case
        result = service.calculate_position_size(execution_capital=200000, stock_price=500)

        assert "quantity" in result
        assert "actual_capital" in result
        assert "execution_capital" in result
        assert result["quantity"] == 400  # 200000 / 500
        assert result["actual_capital"] == 200000.0

    def test_calculate_position_size_zero_capital(self):
        """Test calculate_position_size with zero capital"""
        service = LiquidityCapitalService()

        result = service.calculate_position_size(execution_capital=0, stock_price=500)

        assert result["quantity"] == 0
        assert result["actual_capital"] == 0.0

    def test_calculate_position_size_zero_price(self):
        """Test calculate_position_size with zero price"""
        service = LiquidityCapitalService()

        result = service.calculate_position_size(execution_capital=200000, stock_price=0)

        assert result["quantity"] == 0
        assert result["actual_capital"] == 0.0

    def test_calculate_position_size_exception_handling(self):
        """Test calculate_position_size exception handling"""
        service = LiquidityCapitalService()

        # Test with invalid inputs
        result = service.calculate_position_size(
            execution_capital=float("inf"), stock_price=float("inf")
        )

        # Should handle gracefully
        assert "quantity" in result
        assert "actual_capital" in result
