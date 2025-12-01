"""
Unit tests for PortfolioService

Tests verify the centralized holdings/positions check service
maintains backward compatibility with existing methods.
"""

from unittest.mock import Mock

from modules.kotak_neo_auto_trader.services.portfolio_service import (
    PortfolioCache,
    PortfolioService,
    get_portfolio_service,
)


class TestPortfolioCache:
    """Test PortfolioCache functionality"""

    def test_cache_get_set(self):
        """Test basic cache get/set operations"""
        cache = PortfolioCache(ttl_seconds=60)
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

    def test_cache_expiration(self):
        """Test cache expiration"""
        cache = PortfolioCache(ttl_seconds=0)  # Immediate expiration
        cache.set("test_key", "test_value")
        assert cache.get("test_key") is None  # Should be expired

    def test_cache_clear(self):
        """Test cache clearing"""
        cache = PortfolioCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_invalidate(self):
        """Test cache invalidation for specific key"""
        cache = PortfolioCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.invalidate("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"


class TestPortfolioServiceInitialization:
    """Test PortfolioService initialization"""

    def test_init_with_all_params(self):
        """Test initialization with all parameters"""
        mock_portfolio = Mock()
        mock_orders = Mock()
        mock_auth = Mock()
        mock_config = Mock()

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders=mock_orders,
            auth=mock_auth,
            strategy_config=mock_config,
            enable_caching=True,
            cache_ttl=120,
        )

        assert service.portfolio == mock_portfolio
        assert service.orders == mock_orders
        assert service.auth == mock_auth
        assert service.strategy_config == mock_config
        assert service.enable_caching is True
        assert service._cache is not None

    def test_init_without_caching(self):
        """Test initialization without caching"""
        service = PortfolioService(enable_caching=False)
        assert service.enable_caching is False
        assert service._cache is None

    def test_singleton_pattern(self):
        """Test that get_portfolio_service returns singleton"""
        service1 = get_portfolio_service()
        service2 = get_portfolio_service()
        assert service1 is service2

    def test_singleton_update_dependencies(self):
        """Test that singleton updates dependencies when provided"""
        mock_portfolio = Mock()
        mock_orders = Mock()

        service = get_portfolio_service(portfolio=mock_portfolio, orders=mock_orders)
        assert service.portfolio == mock_portfolio
        assert service.orders == mock_orders


class TestPortfolioServiceSymbolVariants:
    """Test symbol variants generation"""

    def test_symbol_variants(self):
        """Test that symbol variants are generated correctly"""
        variants = PortfolioService._symbol_variants("RELIANCE")
        expected = ["RELIANCE", "RELIANCE-EQ", "RELIANCE-BE", "RELIANCE-BL", "RELIANCE-BZ"]
        assert variants == expected

    def test_symbol_variants_uppercase(self):
        """Test that symbol is converted to uppercase"""
        variants = PortfolioService._symbol_variants("reliance")
        assert all(v.isupper() for v in variants)


class TestPortfolioServiceHasPosition:
    """Test has_position() method"""

    def test_has_position_with_holding(self):
        """Test has_position() returns True when symbol is in holdings"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={
                "data": [
                    {"tradingSymbol": "RELIANCE-EQ"},
                    {"tradingSymbol": "TCS"},
                ]
            }
        )

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=False)
        assert service.has_position("RELIANCE") is True

    def test_has_position_without_holding(self):
        """Test has_position() returns False when symbol is not in holdings"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(return_value={"data": [{"tradingSymbol": "TCS"}]})

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=False)
        assert service.has_position("RELIANCE") is False

    def test_has_position_no_portfolio(self):
        """Test has_position() returns False when portfolio is None"""
        service = PortfolioService(portfolio=None, enable_caching=False)
        assert service.has_position("RELIANCE") is False

    def test_has_position_with_variants(self):
        """Test has_position() checks all symbol variants"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-BE"}]}
        )

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=False)
        assert service.has_position("RELIANCE") is True  # Should match variant

    def test_has_position_with_2fa_handling(self):
        """Test has_position() handles 2FA gate"""
        mock_portfolio = Mock()
        mock_auth = Mock()
        mock_auth.force_relogin = Mock(return_value=True)

        # First call returns 2FA error, second returns holdings
        mock_portfolio.get_holdings = Mock(
            side_effect=[
                {"error": "2FA authentication required"},
                {"data": [{"tradingSymbol": "RELIANCE-EQ"}]},
            ]
        )

        service = PortfolioService(portfolio=mock_portfolio, auth=mock_auth, enable_caching=False)
        assert service.has_position("RELIANCE") is True
        assert mock_auth.force_relogin.called


class TestPortfolioServiceGetCurrentPositions:
    """Test get_current_positions() method"""

    def test_get_current_positions_from_holdings(self):
        """Test get_current_positions() returns symbols from holdings"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={
                "data": [
                    {"tradingSymbol": "RELIANCE-EQ"},
                    {"tradingSymbol": "TCS"},
                ]
            }
        )

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=False)
        positions = service.get_current_positions(include_pending=False)
        assert "RELIANCE-EQ" in positions
        assert "TCS" in positions
        assert positions == sorted(positions)  # Should be sorted

    def test_get_current_positions_with_pending(self):
        """Test get_current_positions() includes pending orders"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(
            return_value=[
                {"transactionType": "BUY", "tradingSymbol": "TCS"},
                {"transactionType": "SELL", "tradingSymbol": "INFY"},  # Should be excluded
            ]
        )

        service = PortfolioService(
            portfolio=mock_portfolio, orders=mock_orders, enable_caching=False
        )
        positions = service.get_current_positions(include_pending=True)
        assert "RELIANCE-EQ" in positions
        assert "TCS" in positions
        assert "INFY" not in positions  # SELL orders excluded

    def test_get_current_positions_without_pending(self):
        """Test get_current_positions() excludes pending when requested"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(
            return_value=[{"transactionType": "BUY", "tradingSymbol": "TCS"}]
        )

        service = PortfolioService(
            portfolio=mock_portfolio, orders=mock_orders, enable_caching=False
        )
        positions = service.get_current_positions(include_pending=False)
        assert "RELIANCE-EQ" in positions
        assert "TCS" not in positions  # Pending excluded

    def test_get_current_positions_handles_orders_error(self):
        """Test get_current_positions() handles orders API error gracefully"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(side_effect=Exception("API Error"))

        service = PortfolioService(
            portfolio=mock_portfolio, orders=mock_orders, enable_caching=False
        )
        positions = service.get_current_positions(include_pending=True)
        assert "RELIANCE-EQ" in positions  # Should still return holdings


class TestPortfolioServicePortfolioCount:
    """Test get_portfolio_count() method"""

    def test_get_portfolio_count(self):
        """Test get_portfolio_count() returns correct count"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={
                "data": [
                    {"tradingSymbol": "RELIANCE-EQ"},
                    {"tradingSymbol": "TCS"},
                ]
            }
        )

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=False)
        count = service.get_portfolio_count(include_pending=False)
        assert count == 2

    def test_get_portfolio_count_with_pending(self):
        """Test get_portfolio_count() includes pending orders"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        mock_orders = Mock()
        mock_orders.get_pending_orders = Mock(
            return_value=[{"transactionType": "BUY", "tradingSymbol": "TCS"}]
        )

        service = PortfolioService(
            portfolio=mock_portfolio, orders=mock_orders, enable_caching=False
        )
        count = service.get_portfolio_count(include_pending=True)
        assert count == 2  # 1 holding + 1 pending


class TestPortfolioServiceCheckCapacity:
    """Test check_portfolio_capacity() method"""

    def test_check_portfolio_capacity_with_capacity(self):
        """Test check_portfolio_capacity() when capacity available"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        mock_config = Mock()
        mock_config.max_portfolio_size = 10

        service = PortfolioService(
            portfolio=mock_portfolio, strategy_config=mock_config, enable_caching=False
        )
        has_capacity, current, max_size = service.check_portfolio_capacity()
        assert has_capacity is True
        assert current == 1
        assert max_size == 10

    def test_check_portfolio_capacity_at_limit(self):
        """Test check_portfolio_capacity() when at limit"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": f"STOCK{i}"} for i in range(10)]}
        )

        mock_config = Mock()
        mock_config.max_portfolio_size = 10

        service = PortfolioService(
            portfolio=mock_portfolio, strategy_config=mock_config, enable_caching=False
        )
        has_capacity, current, max_size = service.check_portfolio_capacity()
        assert has_capacity is False
        assert current == 10
        assert max_size == 10

    def test_check_portfolio_capacity_with_custom_max(self):
        """Test check_portfolio_capacity() with custom max_size"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=False)
        has_capacity, current, max_size = service.check_portfolio_capacity(max_size=5)
        assert has_capacity is True
        assert current == 1
        assert max_size == 5


class TestPortfolioServiceCaching:
    """Test caching functionality"""

    def test_caching_enabled(self):
        """Test that caching works when enabled"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=True)
        # First call
        service.has_position("RELIANCE")
        # Second call should use cache
        service.has_position("RELIANCE")
        # Should only be called once due to caching
        assert mock_portfolio.get_holdings.call_count == 1

    def test_caching_disabled(self):
        """Test that caching doesn't work when disabled"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=False)
        # First call
        service.has_position("RELIANCE")
        # Second call
        service.has_position("RELIANCE")
        # Should be called twice (no caching)
        assert mock_portfolio.get_holdings.call_count == 2

    def test_clear_cache(self):
        """Test clear_cache() method"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=True)
        service.has_position("RELIANCE")  # Populate cache
        service.clear_cache()
        service.has_position("RELIANCE")  # Should fetch again
        assert mock_portfolio.get_holdings.call_count == 2

    def test_invalidate_holdings_cache(self):
        """Test invalidate_holdings_cache() method"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        service = PortfolioService(portfolio=mock_portfolio, enable_caching=True)
        service.has_position("RELIANCE")  # Populate cache
        service.invalidate_holdings_cache()
        service.has_position("RELIANCE")  # Should fetch again
        assert mock_portfolio.get_holdings.call_count == 2
