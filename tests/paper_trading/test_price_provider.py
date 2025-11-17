"""
Test Price Provider
"""

import pytest

import modules.kotak_neo_auto_trader.infrastructure.simulation.price_provider as price_mod
from modules.kotak_neo_auto_trader.infrastructure.simulation import PriceProvider


class TestPriceProvider:
    """Test price provider functionality"""

    def test_mock_price_provider(self):
        """Test mock price provider"""
        provider = PriceProvider(mode="mock")

        price = provider.get_price("INFY")
        assert price is not None
        assert price > 0

    def test_set_mock_price(self):
        """Test setting mock prices"""
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("INFY", 1450.00)

        price = provider.get_price("INFY")
        assert price == 1450.00

    def test_get_prices_multiple(self):
        """Test getting multiple prices"""
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("INFY", 1450.00)
        provider.set_mock_price("TCS", 3500.00)

        prices = provider.get_prices(["INFY", "TCS"])

        assert len(prices) == 2
        assert prices["INFY"] == 1450.00
        assert prices["TCS"] == 3500.00

    def test_price_caching(self):
        """Test price caching"""
        provider = PriceProvider(mode="mock", cache_duration_seconds=10)
        provider.set_mock_price("INFY", 1450.00)

        # First call
        price1 = provider.get_price("INFY")

        # Second call (should be from cache)
        price2 = provider.get_price("INFY")

        assert price1 == price2

    def test_clear_cache(self):
        """Test clearing price cache"""
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("INFY", 1450.00)

        provider.clear_cache()
        cache_info = provider.get_cache_info()

        assert cache_info["total_cached"] == 0

    def test_get_cache_info(self):
        """Test getting cache information"""
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("INFY", 1450.00)
        provider.set_mock_price("TCS", 3500.00)

        cache_info = provider.get_cache_info()

        assert cache_info["total_cached"] >= 2
        assert cache_info["mode"] == "mock"

    def test_deterministic_mock_prices(self):
        """Test that mock prices are deterministic for same symbol"""
        provider1 = PriceProvider(mode="mock")
        provider2 = PriceProvider(mode="mock")

        # Without setting, mock prices should be deterministic based on symbol
        price1 = provider1.get_price("TESTSTOCK")
        price2 = provider2.get_price("TESTSTOCK")

        # Should be close (within reasonable range due to randomness)
        assert abs(price1 - price2) < price1 * 0.1  # Within 10%

    def test_live_mode_falls_back_to_yfinance(self, monkeypatch):
        """Ensure live mode uses YFinance fallback instead of mock."""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        class DummyYF:
            def fetch_current_price(self, symbol):
                return 123.45

        monkeypatch.setattr(price_mod, "YFinanceProvider", lambda: DummyYF(), raising=False)

        provider = price_mod.PriceProvider(mode="live")
        assert provider.mode == "live"

        price = provider.get_price("ANY")
        assert price == 123.45


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
