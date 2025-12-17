"""
Test Price Provider
"""

import pandas as pd
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


class TestPriceProviderTickerConversion:
    """Test ticker conversion fix to prevent double-suffixing"""

    def test_ticker_already_has_ns_suffix(self, monkeypatch):
        """Test that symbols already ending with .NS are used as-is (no double-suffixing)"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_tickers = []

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_tickers.append(symbol)
                return 100.0

        monkeypatch.setattr(
            price_mod, "YFinanceProvider", lambda: MockYFinanceProvider(), raising=False
        )

        provider = price_mod.PriceProvider(mode="live")
        price = provider.get_price("AAREYDRUGS.NS")

        assert price == 100.0
        assert len(captured_tickers) == 1
        assert captured_tickers[0] == "AAREYDRUGS.NS"  # Should NOT be "AAREYDRUGS.NS.NS"

    def test_ticker_already_has_bo_suffix(self, monkeypatch):
        """Test that symbols already ending with .BO are used as-is"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_tickers = []

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_tickers.append(symbol)
                return 200.0

        monkeypatch.setattr(
            price_mod, "YFinanceProvider", lambda: MockYFinanceProvider(), raising=False
        )

        provider = price_mod.PriceProvider(mode="live")
        price = provider.get_price("RELIANCE.BO")

        assert price == 200.0
        assert len(captured_tickers) == 1
        assert captured_tickers[0] == "RELIANCE.BO"  # Should NOT be "RELIANCE.BO.NS"

    def test_full_symbol_converts_to_ticker(self, monkeypatch):
        """Test that full symbols like SALSTEEL-BE convert to SALSTEEL.NS"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_tickers = []

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_tickers.append(symbol)
                return 300.0

        monkeypatch.setattr(
            price_mod, "YFinanceProvider", lambda: MockYFinanceProvider(), raising=False
        )

        provider = price_mod.PriceProvider(mode="live")
        price = provider.get_price("SALSTEEL-BE")

        assert price == 300.0
        assert len(captured_tickers) == 1
        assert captured_tickers[0] == "SALSTEEL.NS"  # Should convert from SALSTEEL-BE

    def test_base_symbol_converts_to_ticker(self, monkeypatch):
        """Test that base symbols like AAREYDRUGS convert to AAREYDRUGS.NS"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_tickers = []

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_tickers.append(symbol)
                return 400.0

        monkeypatch.setattr(
            price_mod, "YFinanceProvider", lambda: MockYFinanceProvider(), raising=False
        )

        provider = price_mod.PriceProvider(mode="live")
        price = provider.get_price("AAREYDRUGS")

        assert price == 400.0
        assert len(captured_tickers) == 1
        assert captured_tickers[0] == "AAREYDRUGS.NS"  # Should convert from AAREYDRUGS

    def test_full_symbol_with_eq_suffix(self, monkeypatch):
        """Test that full symbols with -EQ suffix convert correctly"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_tickers = []

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_tickers.append(symbol)
                return 500.0

        monkeypatch.setattr(
            price_mod, "YFinanceProvider", lambda: MockYFinanceProvider(), raising=False
        )

        provider = price_mod.PriceProvider(mode="live")
        price = provider.get_price("ASTERDM-EQ")

        assert price == 500.0
        assert len(captured_tickers) == 1
        assert captured_tickers[0] == "ASTERDM.NS"  # Should extract base and add .NS

    def test_full_symbol_with_be_suffix(self, monkeypatch):
        """Test that full symbols with -BE suffix convert correctly"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_tickers = []

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_tickers.append(symbol)
                return 600.0

        monkeypatch.setattr(
            price_mod, "YFinanceProvider", lambda: MockYFinanceProvider(), raising=False
        )

        provider = price_mod.PriceProvider(mode="live")
        price = provider.get_price("EMKAY-BE")

        assert price == 600.0
        assert len(captured_tickers) == 1
        assert captured_tickers[0] == "EMKAY.NS"  # Should extract base and add .NS

    def test_case_insensitive_ticker_detection(self, monkeypatch):
        """Test that ticker detection is case-insensitive"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_tickers = []

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_tickers.append(symbol)
                return 700.0

        monkeypatch.setattr(
            price_mod, "YFinanceProvider", lambda: MockYFinanceProvider(), raising=False
        )

        provider = price_mod.PriceProvider(mode="live")
        # Test lowercase .ns
        price1 = provider.get_price("reliance.ns")
        # Test mixed case .NS
        price2 = provider.get_price("RELIANCE.Ns")

        assert price1 == 700.0
        assert price2 == 700.0
        # Both should be recognized as tickers (though actual conversion may normalize case)
        assert len(captured_tickers) >= 2

    def test_symbol_with_multiple_dashes(self, monkeypatch):
        """Test symbols with multiple dashes (edge case)"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_tickers = []

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_tickers.append(symbol)
                return 800.0

        monkeypatch.setattr(
            price_mod, "YFinanceProvider", lambda: MockYFinanceProvider(), raising=False
        )

        provider = price_mod.PriceProvider(mode="live")
        price = provider.get_price("TEST-SYMBOL-BE")

        assert price == 800.0
        assert len(captured_tickers) == 1
        # Should extract first part before first dash
        assert captured_tickers[0] == "TEST.NS"

    def test_data_fetcher_uses_converted_ticker(self, monkeypatch):
        """Test that DataFetcher also receives the converted ticker"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", True, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_data_fetcher_symbols = []
        captured_yfinance_symbols = []

        class MockDataFetcher:
            def fetch_data_yfinance(self, symbol, period, interval):
                captured_data_fetcher_symbols.append(symbol)
                # Return empty to force fallback to yfinance
                return pd.DataFrame()

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_yfinance_symbols.append(symbol)
                return 900.0

        # Create mock instances
        mock_data_fetcher = MockDataFetcher()
        mock_yfinance = MockYFinanceProvider()

        monkeypatch.setattr(price_mod, "DataFetcher", lambda: mock_data_fetcher, raising=False)
        monkeypatch.setattr(price_mod, "YFinanceProvider", lambda: mock_yfinance, raising=False)

        provider = price_mod.PriceProvider(mode="live")
        # Ensure yfinance provider is set (it should be from initialization)
        if provider.yfinance_provider is None:
            provider.yfinance_provider = mock_yfinance

        # Test with full symbol
        price = provider.get_price("THYROCARE-EQ")

        assert price == 900.0
        # DataFetcher should receive converted ticker
        assert len(captured_data_fetcher_symbols) == 1
        assert captured_data_fetcher_symbols[0] == "THYROCARE.NS"
        # YFinance should also receive converted ticker
        assert len(captured_yfinance_symbols) == 1
        assert captured_yfinance_symbols[0] == "THYROCARE.NS"

    def test_data_fetcher_with_already_ticker_format(self, monkeypatch):
        """Test that DataFetcher receives ticker as-is when already in ticker format"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", True, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_data_fetcher_symbols = []

        class MockDataFetcher:
            def fetch_data_yfinance(self, symbol, period, interval):
                captured_data_fetcher_symbols.append(symbol)
                # Return empty to force fallback to yfinance
                return pd.DataFrame()

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                return 1000.0

        # Create mock instances
        mock_data_fetcher = MockDataFetcher()
        mock_yfinance = MockYFinanceProvider()

        monkeypatch.setattr(price_mod, "DataFetcher", lambda: mock_data_fetcher, raising=False)
        monkeypatch.setattr(price_mod, "YFinanceProvider", lambda: mock_yfinance, raising=False)

        provider = price_mod.PriceProvider(mode="live")
        # Ensure yfinance provider is set (it should be from initialization)
        if provider.yfinance_provider is None:
            provider.yfinance_provider = mock_yfinance

        # Test with already-formatted ticker
        price = provider.get_price("TARAPUR.NS")

        assert price == 1000.0
        # DataFetcher should receive ticker as-is (no double-suffixing)
        assert len(captured_data_fetcher_symbols) == 1
        assert captured_data_fetcher_symbols[0] == "TARAPUR.NS"  # NOT "TARAPUR.NS.NS"

    def test_mock_mode_does_not_convert(self, monkeypatch):
        """Test that mock mode doesn't perform ticker conversion (uses symbol as-is)"""
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("SALSTEEL-BE", 50.0)
        provider.set_mock_price("SALSTEEL.NS", 50.0)

        # Mock mode should use symbol exactly as provided
        price1 = provider.get_price("SALSTEEL-BE")
        price2 = provider.get_price("SALSTEEL.NS")

        assert price1 == 50.0
        assert price2 == 50.0

    def test_multiple_symbols_mixed_formats(self, monkeypatch):
        """Test get_prices with mixed symbol formats"""
        monkeypatch.setattr(price_mod, "HAS_DATA_FETCHER", False, raising=False)
        monkeypatch.setattr(price_mod, "HAS_YFINANCE_PROVIDER", True, raising=False)

        captured_tickers = []

        class MockYFinanceProvider:
            def fetch_current_price(self, symbol):
                captured_tickers.append(symbol)
                # Return different prices for different symbols
                prices = {
                    "RELIANCE.NS": 2500.0,
                    "TCS.NS": 3500.0,
                    "INFY.NS": 1500.0,
                }
                return prices.get(symbol, 100.0)

        monkeypatch.setattr(
            price_mod, "YFinanceProvider", lambda: MockYFinanceProvider(), raising=False
        )

        provider = price_mod.PriceProvider(mode="live")
        # Mix of formats: ticker, full symbol, base symbol
        prices = provider.get_prices(["RELIANCE.NS", "TCS-EQ", "INFY"])

        assert len(prices) == 3
        assert prices["RELIANCE.NS"] == 2500.0
        assert prices["TCS-EQ"] == 3500.0
        assert prices["INFY"] == 1500.0
        # Verify all were converted correctly
        assert "RELIANCE.NS" in captured_tickers
        assert "TCS.NS" in captured_tickers
        assert "INFY.NS" in captured_tickers
        # Verify no double-suffixing
        assert "RELIANCE.NS.NS" not in captured_tickers
        assert "TCS.NS.NS" not in captured_tickers
        assert "INFY.NS.NS" not in captured_tickers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
