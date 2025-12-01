"""
Integration tests for Phase 4.2 cache warming methods

Tests verify cache warming methods work correctly and can be integrated
into run_trading_service.py workflows.

Phase 4.2: Enhanced Caching Strategy - Integration
"""

from unittest.mock import Mock

import pytest

from modules.kotak_neo_auto_trader.services import (
    get_indicator_service,
    get_price_service,
)


class TestCacheWarmingIntegrationSellMonitor:
    """Test cache warming integration for sell monitor positions"""

    def test_cache_warming_services_available(self):
        """Test that cache warming services are available and have required methods"""
        # Verify services can be instantiated
        price_service = get_price_service(enable_caching=True)
        assert hasattr(price_service, "warm_cache_for_positions")
        assert hasattr(price_service, "warm_cache_for_recommendations")

        indicator_service = get_indicator_service(
            price_service=price_service, enable_caching=True
        )
        assert hasattr(indicator_service, "warm_cache_for_positions")

    def test_warm_cache_for_positions_list_format(self):
        """Test that warm_cache_for_positions accepts list format (used by sell monitor)"""
        price_service = get_price_service(enable_caching=True)
        indicator_service = get_indicator_service(
            price_service=price_service, enable_caching=True
        )

        # Test with list format (as returned by sell_manager.get_open_positions())
        positions_list = [
            {"symbol": "RELIANCE-EQ", "ticker": "RELIANCE.NS", "qty": 10},
            {"symbol": "TATA-EQ", "ticker": "TATA.NS", "qty": 20},
        ]

        # Should handle list format correctly
        price_stats = price_service.warm_cache_for_positions(positions_list)
        assert isinstance(price_stats, dict)
        assert "warmed" in price_stats
        assert "failed" in price_stats

        indicator_stats = indicator_service.warm_cache_for_positions(positions_list)
        assert isinstance(indicator_stats, dict)
        assert "warmed" in indicator_stats
        assert "failed" in indicator_stats

    def test_warm_cache_for_positions_dict_format(self):
        """Test that warm_cache_for_positions accepts dict format"""
        price_service = get_price_service(enable_caching=True)
        indicator_service = get_indicator_service(
            price_service=price_service, enable_caching=True
        )

        # Test with dict format (grouped by symbol)
        positions_dict = {
            "RELIANCE": [
                {"symbol": "RELIANCE-EQ", "ticker": "RELIANCE.NS", "qty": 10}
            ],
            "TATA": [{"symbol": "TATA-EQ", "ticker": "TATA.NS", "qty": 20}],
        }

        # Should handle dict format correctly
        price_stats = price_service.warm_cache_for_positions(positions_dict)
        assert isinstance(price_stats, dict)
        assert "warmed" in price_stats
        assert "failed" in price_stats

        indicator_stats = indicator_service.warm_cache_for_positions(positions_dict)
        assert isinstance(indicator_stats, dict)
        assert "warmed" in indicator_stats
        assert "failed" in indicator_stats

    def test_cache_warming_handles_exceptions(self):
        """Test that cache warming handles exceptions gracefully (non-critical)"""
        price_service = get_price_service(enable_caching=True)

        # Test with invalid positions (should handle gracefully)
        invalid_positions = [{"invalid": "data"}]
        stats = price_service.warm_cache_for_positions(invalid_positions)
        assert isinstance(stats, dict)
        assert "warmed" in stats
        assert "failed" in stats
        # Should not raise exception (failures are non-critical)


class TestCacheWarmingIntegrationBuyOrders:
    """Test cache warming integration for buy orders recommendations"""

    def test_warm_cache_for_recommendations_objects(self):
        """Test that warm_cache_for_recommendations accepts objects with ticker attribute"""
        price_service = get_price_service(enable_caching=True)

        # Test with recommendations as objects with ticker attribute (as used in run_buy_orders)
        mock_rec1 = Mock(ticker="RELIANCE.NS")
        mock_rec2 = Mock(ticker="TATA.NS")
        recommendations_objects = [mock_rec1, mock_rec2]

        stats = price_service.warm_cache_for_recommendations(recommendations_objects)
        assert isinstance(stats, dict)
        assert "warmed" in stats
        assert "failed" in stats

    def test_warm_cache_for_recommendations_dicts(self):
        """Test that warm_cache_for_recommendations accepts dicts with ticker key"""
        price_service = get_price_service(enable_caching=True)

        # Test with recommendations as dicts
        recommendations_dicts = [
            {"ticker": "RELIANCE.NS", "symbol": "RELIANCE"},
            {"ticker": "TATA.NS", "symbol": "TATA"},
        ]

        stats = price_service.warm_cache_for_recommendations(recommendations_dicts)
        assert isinstance(stats, dict)
        assert "warmed" in stats
        assert "failed" in stats

    def test_warm_cache_for_recommendations_handles_missing_ticker(self):
        """Test that cache warming handles recommendations without ticker gracefully"""
        price_service = get_price_service(enable_caching=True)

        # Test with recommendations missing ticker
        recommendations_no_ticker = [
            {"symbol": "RELIANCE"},  # No ticker - should be skipped
            {"ticker": "TATA.NS", "symbol": "TATA"},  # Has ticker - should be processed
        ]

        stats = price_service.warm_cache_for_recommendations(recommendations_no_ticker)
        assert isinstance(stats, dict)
        assert "warmed" in stats
        assert "failed" in stats
        # Should not raise exception (missing ticker is handled gracefully)

    def test_warm_cache_for_recommendations_empty_list(self):
        """Test that cache warming handles empty recommendations list (early return)"""
        price_service = get_price_service(enable_caching=True)

        stats = price_service.warm_cache_for_recommendations([])
        assert isinstance(stats, dict)
        assert stats["warmed"] == 0
        assert stats["failed"] == 0
        # Should return immediately without processing


class TestCacheWarmingIntegrationEdgeCases:
    """Test edge cases for cache warming integration"""

    def test_cache_warming_with_empty_positions(self):
        """Test cache warming behavior with empty positions list"""
        price_service = get_price_service(enable_caching=True)
        indicator_service = get_indicator_service(
            price_service=price_service, enable_caching=True
        )

        # Test with empty list
        stats = price_service.warm_cache_for_positions([])
        assert stats["warmed"] == 0
        assert stats["failed"] == 0

        stats = indicator_service.warm_cache_for_positions([])
        assert stats["warmed"] == 0
        assert stats["failed"] == 0

        # Test with empty dict
        stats = price_service.warm_cache_for_positions({})
        assert stats["warmed"] == 0
        assert stats["failed"] == 0

        stats = indicator_service.warm_cache_for_positions({})
        assert stats["warmed"] == 0
        assert stats["failed"] == 0

    def test_cache_warming_return_value_format(self):
        """Test that cache warming returns consistent dict format"""
        price_service = get_price_service(enable_caching=True)
        indicator_service = get_indicator_service(
            price_service=price_service, enable_caching=True
        )

        # Verify return format is consistent
        positions = [{"symbol": "RELIANCE-EQ", "ticker": "RELIANCE.NS", "qty": 10}]

        price_stats = price_service.warm_cache_for_positions(positions)
        assert isinstance(price_stats, dict)
        assert "warmed" in price_stats
        assert "failed" in price_stats
        assert isinstance(price_stats["warmed"], int)
        assert isinstance(price_stats["failed"], int)

        indicator_stats = indicator_service.warm_cache_for_positions(positions)
        assert isinstance(indicator_stats, dict)
        assert "warmed" in indicator_stats
        assert "failed" in indicator_stats
        assert isinstance(indicator_stats["warmed"], int)
        assert isinstance(indicator_stats["failed"], int)

    def test_cache_warming_idempotent(self):
        """Test that cache warming can be called multiple times safely"""
        price_service = get_price_service(enable_caching=True)

        positions = [{"symbol": "RELIANCE-EQ", "ticker": "RELIANCE.NS", "qty": 10}]

        # Call multiple times - should not raise exceptions
        stats1 = price_service.warm_cache_for_positions(positions)
        stats2 = price_service.warm_cache_for_positions(positions)
        stats3 = price_service.warm_cache_for_positions(positions)

        # All calls should return valid stats
        for stats in [stats1, stats2, stats3]:
            assert isinstance(stats, dict)
            assert "warmed" in stats
            assert "failed" in stats
