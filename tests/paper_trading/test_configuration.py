"""
Test Paper Trading Configuration
"""

import pytest
from pathlib import Path
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig


class TestPaperTradingConfig:
    """Test configuration management"""

    def test_default_config(self):
        """Test default configuration values"""
        config = PaperTradingConfig()

        assert config.initial_capital == 100000.0
        assert config.enable_slippage is True
        assert config.enable_fees is True
        assert config.enforce_market_hours is True

    def test_custom_config(self):
        """Test custom configuration"""
        config = PaperTradingConfig(
            initial_capital=50000.0,
            enable_slippage=False,
            enable_fees=False
        )

        assert config.initial_capital == 50000.0
        assert config.enable_slippage is False
        assert config.enable_fees is False

    def test_config_validation_negative_capital(self):
        """Test that negative capital raises error"""
        with pytest.raises(ValueError):
            PaperTradingConfig(initial_capital=-1000.0)

    def test_config_validation_negative_slippage(self):
        """Test that negative slippage raises error"""
        with pytest.raises(ValueError):
            PaperTradingConfig(slippage_percentage=-0.5)

    def test_config_presets(self):
        """Test configuration presets"""
        minimal = PaperTradingConfig.minimal_fees()
        assert minimal.enable_fees is False
        assert minimal.enable_slippage is False

        realistic = PaperTradingConfig.realistic()
        assert realistic.enable_fees is True
        assert realistic.enable_slippage is True

    def test_total_charges_calculation_buy(self):
        """Test total charges calculation for buy orders"""
        config = PaperTradingConfig(enable_fees=True)
        charges_pct = config.get_total_charges_percentage(is_buy=True)

        assert charges_pct > 0
        assert charges_pct < 1.0  # Should be less than 1%

    def test_total_charges_calculation_sell(self):
        """Test total charges calculation for sell orders"""
        config = PaperTradingConfig(enable_fees=True)
        charges_pct = config.get_total_charges_percentage(is_buy=False)

        assert charges_pct > 0
        assert charges_pct < 1.0

    def test_calculate_charges(self):
        """Test charges calculation on order value"""
        config = PaperTradingConfig(enable_fees=True)
        order_value = 10000.0

        buy_charges = config.calculate_charges(order_value, is_buy=True)
        sell_charges = config.calculate_charges(order_value, is_buy=False)

        assert buy_charges > 0
        assert sell_charges > 0
        assert buy_charges != sell_charges  # Different due to STT vs stamp duty

    def test_config_to_dict(self):
        """Test configuration serialization"""
        config = PaperTradingConfig(initial_capital=75000.0)
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["initial_capital"] == 75000.0

    def test_config_from_dict(self):
        """Test configuration deserialization"""
        data = {
            "initial_capital": 75000.0,
            "enable_slippage": False,
            "enable_fees": False,
        }

        config = PaperTradingConfig.from_dict(data)
        assert config.initial_capital == 75000.0
        assert config.enable_slippage is False


class TestConfigPersistence:
    """Test configuration file operations"""

    def test_save_and_load_config(self, tmp_path):
        """Test saving and loading configuration"""
        config = PaperTradingConfig(initial_capital=60000.0)
        filepath = tmp_path / "config.json"

        config.save_to_file(filepath)
        assert filepath.exists()

        loaded_config = PaperTradingConfig.load_from_file(filepath)
        assert loaded_config.initial_capital == 60000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

