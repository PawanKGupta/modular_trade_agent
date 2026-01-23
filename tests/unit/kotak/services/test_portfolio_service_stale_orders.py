"""
Unit tests for PortfolioService stale PENDING order exclusion

Tests verify that stale PENDING orders are correctly excluded from portfolio count
using trading-day-aware logic (same as EOD cleanup).
"""

from datetime import datetime
from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.services.portfolio_service import PortfolioService
from src.infrastructure.db.models import OrderStatus
from src.infrastructure.db.timezone_utils import IST


class TestPortfolioServiceStalePendingOrderExclusion:
    """Test stale PENDING order exclusion using trading-day-aware logic"""

    def test_excludes_stale_pending_order_past_next_trading_day_close(self):
        """Test that PENDING orders past next trading day market close are excluded"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Create a stale PENDING order (placed Monday 2 PM, current time is Tuesday 4 PM)
        # Next trading day close would be Tuesday 3:30 PM, so order is stale
        monday_2pm = datetime(2025, 1, 6, 14, 0, 0, tzinfo=IST)  # Monday 2 PM IST
        tuesday_4pm = datetime(2025, 1, 7, 16, 0, 0, tzinfo=IST)  # Tuesday 4 PM IST

        mock_stale_order = Mock()
        mock_stale_order.side = "buy"
        mock_stale_order.status = OrderStatus.PENDING
        mock_stale_order.symbol = "WIPRO-EQ"
        mock_stale_order.placed_at = monday_2pm

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_stale_order], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=tuesday_4pm):
            positions = service.get_current_positions(include_pending=True)

        # Should only include RELIANCE (from holdings), not WIPRO (stale PENDING)
        # Holdings symbols may have suffixes, database orders are normalized
        assert any("RELIANCE" in pos for pos in positions)
        assert not any("WIPRO" in pos for pos in positions)
        assert len(positions) == 1

    def test_includes_recent_pending_order_before_next_trading_day_close(self):
        """Test that recent PENDING orders (before next trading day close) are included"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Create a recent PENDING order (placed Tuesday 2 PM, current time is Tuesday 3 PM)
        # Next trading day close would be Wednesday 3:30 PM, so order is NOT stale
        tuesday_2pm = datetime(2025, 1, 7, 14, 0, 0, tzinfo=IST)  # Tuesday 2 PM IST
        tuesday_3pm = datetime(2025, 1, 7, 15, 0, 0, tzinfo=IST)  # Tuesday 3 PM IST

        mock_recent_order = Mock()
        mock_recent_order.side = "buy"
        mock_recent_order.status = OrderStatus.PENDING
        mock_recent_order.symbol = "TCS-EQ"
        mock_recent_order.placed_at = tuesday_2pm

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_recent_order], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=tuesday_3pm):
            positions = service.get_current_positions(include_pending=True)

        # Should include both RELIANCE (from holdings) and TCS (recent PENDING)
        assert any("RELIANCE" in pos for pos in positions)
        assert "TCS" in positions  # Database orders are normalized
        assert len(positions) == 2

    def test_excludes_stale_pending_order_placed_on_friday(self):
        """Test that PENDING orders placed on Friday are correctly handled (skip weekend)"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Order placed Friday 4 PM, current time is Monday 4 PM
        # Next trading day close would be Monday 3:30 PM, so order is stale
        friday_4pm = datetime(2025, 1, 3, 16, 0, 0, tzinfo=IST)  # Friday 4 PM IST
        monday_4pm = datetime(2025, 1, 6, 16, 0, 0, tzinfo=IST)  # Monday 4 PM IST

        mock_stale_order = Mock()
        mock_stale_order.side = "buy"
        mock_stale_order.status = OrderStatus.PENDING
        mock_stale_order.symbol = "INFY-EQ"
        mock_stale_order.placed_at = friday_4pm

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_stale_order], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=monday_4pm):
            positions = service.get_current_positions(include_pending=True)

        # Should exclude INFY (stale, past Monday 3:30 PM)
        assert any("RELIANCE" in pos for pos in positions)
        assert "INFY" not in positions
        assert len(positions) == 1

    def test_includes_pending_order_at_exact_market_close_boundary(self):
        """Test that PENDING orders are included if current time is exactly at next trading day close"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Order placed Monday 2 PM, current time is Tuesday 3:30 PM (exactly at market close)
        # Order should still be included (not stale until after 3:30 PM)
        monday_2pm = datetime(2025, 1, 6, 14, 0, 0, tzinfo=IST)  # Monday 2 PM IST
        tuesday_330pm = datetime(2025, 1, 7, 15, 30, 0, tzinfo=IST)  # Tuesday 3:30 PM IST

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.status = OrderStatus.PENDING
        mock_order.symbol = "HDFC-EQ"
        mock_order.placed_at = monday_2pm

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_order], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=tuesday_330pm):
            positions = service.get_current_positions(include_pending=True)

        # Should include HDFC (not stale yet, exactly at boundary)
        assert any("RELIANCE" in pos for pos in positions)
        assert "HDFC" in positions
        assert len(positions) == 2

    def test_excludes_stale_pending_order_after_market_close(self):
        """Test that PENDING orders are excluded if current time is after next trading day close"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Order placed Monday 2 PM, current time is Tuesday 3:31 PM (1 minute after market close)
        monday_2pm = datetime(2025, 1, 6, 14, 0, 0, tzinfo=IST)  # Monday 2 PM IST
        tuesday_331pm = datetime(2025, 1, 7, 15, 31, 0, tzinfo=IST)  # Tuesday 3:31 PM IST

        mock_stale_order = Mock()
        mock_stale_order.side = "buy"
        mock_stale_order.status = OrderStatus.PENDING
        mock_stale_order.symbol = "ICICIBANK-EQ"
        mock_stale_order.placed_at = monday_2pm

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_stale_order], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=tuesday_331pm):
            positions = service.get_current_positions(include_pending=True)

        # Should exclude ICICIBANK (stale, past Tuesday 3:30 PM)
        assert any("RELIANCE" in pos for pos in positions)
        assert "ICICIBANK" not in positions
        assert len(positions) == 1

    def test_handles_mix_of_stale_and_recent_pending_orders(self):
        """Test that mix of stale and recent PENDING orders are handled correctly"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Stale order (placed Monday 2 PM, current time is Tuesday 4 PM)
        monday_2pm = datetime(2025, 1, 6, 14, 0, 0, tzinfo=IST)
        # Recent order (placed Tuesday 2 PM, current time is Tuesday 4 PM)
        tuesday_2pm = datetime(2025, 1, 7, 14, 0, 0, tzinfo=IST)
        tuesday_4pm = datetime(2025, 1, 7, 16, 0, 0, tzinfo=IST)

        mock_stale_order = Mock()
        mock_stale_order.side = "buy"
        mock_stale_order.status = OrderStatus.PENDING
        mock_stale_order.symbol = "WIPRO-EQ"
        mock_stale_order.placed_at = monday_2pm

        mock_recent_order = Mock()
        mock_recent_order.side = "buy"
        mock_recent_order.status = OrderStatus.PENDING
        mock_recent_order.symbol = "TCS-EQ"
        mock_recent_order.placed_at = tuesday_2pm

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_stale_order, mock_recent_order], 2))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=tuesday_4pm):
            positions = service.get_current_positions(include_pending=True)

        # Should include RELIANCE (holdings) and TCS (recent PENDING), exclude WIPRO (stale PENDING)
        assert any("RELIANCE" in pos for pos in positions)
        assert "TCS" in positions
        assert "WIPRO" not in positions
        assert len(positions) == 2

    def test_includes_ongoing_orders_regardless_of_age(self):
        """Test that ONGOING orders are always included, regardless of age"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Very old ONGOING order (should still be included)
        old_date = datetime(2025, 1, 1, 14, 0, 0, tzinfo=IST)
        current_time = datetime(2025, 1, 7, 16, 0, 0, tzinfo=IST)

        mock_ongoing_order = Mock()
        mock_ongoing_order.side = "buy"
        mock_ongoing_order.status = OrderStatus.ONGOING
        mock_ongoing_order.symbol = "SBIN-EQ"
        mock_ongoing_order.placed_at = old_date

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_ongoing_order], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=current_time):
            positions = service.get_current_positions(include_pending=True)

        # Should include both RELIANCE and SBIN (ONGOING orders are never excluded)
        assert any("RELIANCE" in pos for pos in positions)
        assert "SBIN" in positions
        assert len(positions) == 2

    def test_handles_pending_order_without_placed_at(self):
        """Test that PENDING orders without placed_at are included (safe default)"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        mock_order_no_date = Mock()
        mock_order_no_date.side = "buy"
        mock_order_no_date.status = OrderStatus.PENDING
        mock_order_no_date.symbol = "TCS-EQ"
        mock_order_no_date.placed_at = None  # No placed_at

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_order_no_date], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        positions = service.get_current_positions(include_pending=True)

        # Should include TCS (safe default when placed_at is None)
        assert any("RELIANCE" in pos for pos in positions)
        assert "TCS" in positions
        assert len(positions) == 2

    def test_handles_naive_datetime_placed_at(self):
        """Test that naive datetime placed_at is handled correctly (converted to IST)"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Naive datetime (no timezone)
        monday_2pm_naive = datetime(2025, 1, 6, 14, 0, 0)  # No tzinfo
        tuesday_4pm = datetime(2025, 1, 7, 16, 0, 0, tzinfo=IST)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.status = OrderStatus.PENDING
        mock_order.symbol = "WIPRO-EQ"
        mock_order.placed_at = monday_2pm_naive

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_order], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=tuesday_4pm):
            positions = service.get_current_positions(include_pending=True)

        # Should exclude WIPRO (stale, naive datetime should be treated as IST)
        assert any("RELIANCE" in pos for pos in positions)
        assert "WIPRO" not in positions
        assert len(positions) == 1

    def test_handles_exception_in_stale_check_gracefully(self):
        """Test that exceptions in stale check are handled gracefully (include order as safe default)"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.status = OrderStatus.PENDING
        mock_order.symbol = "TCS-EQ"
        mock_order.placed_at = datetime(2025, 1, 6, 14, 0, 0, tzinfo=IST)

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_order], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        # Mock get_next_trading_day_close to raise an exception by patching the import inside the try block
        # We need to patch it where it's used, not at module level
        with patch(
            "modules.kotak_neo_auto_trader.utils.trading_day_utils.get_next_trading_day_close",
            side_effect=Exception("Holiday calendar error"),
        ):
            with patch(
                "src.infrastructure.db.timezone_utils.ist_now",
                return_value=datetime(2025, 1, 7, 16, 0, 0, tzinfo=IST),
            ):
                positions = service.get_current_positions(include_pending=True)

        # Should include TCS (safe default when exception occurs)
        assert any("RELIANCE" in pos for pos in positions)
        assert "TCS" in positions
        assert len(positions) == 2

    def test_fallback_to_24_hour_check_when_trading_day_utils_unavailable(self):
        """Test fallback to 24-hour check when trading_day_utils is not available"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Order placed 25 hours ago (should be stale with 24-hour fallback)
        old_time = datetime(2025, 1, 6, 14, 0, 0, tzinfo=IST)
        current_time = datetime(2025, 1, 7, 15, 0, 0, tzinfo=IST)  # 25 hours later

        mock_stale_order = Mock()
        mock_stale_order.side = "buy"
        mock_stale_order.status = OrderStatus.PENDING
        mock_stale_order.symbol = "WIPRO-EQ"
        mock_stale_order.placed_at = old_time

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_stale_order], 1))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        # Simulate ImportError for trading_day_utils by patching the import to raise ImportError
        # Patch the import inside the try block to simulate ImportError
        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "modules.kotak_neo_auto_trader.utils.trading_day_utils":
                raise ImportError("trading_day_utils not available")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=current_time):
                positions = service.get_current_positions(include_pending=True)

        # Should exclude WIPRO (stale with 24-hour fallback)
        assert any("RELIANCE" in pos for pos in positions)
        assert "WIPRO" not in positions
        assert len(positions) == 1

    def test_portfolio_count_excludes_stale_pending_orders(self):
        """Test that get_portfolio_count() excludes stale PENDING orders"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": "RELIANCE-EQ"}]}
        )

        # Stale PENDING order
        monday_2pm = datetime(2025, 1, 6, 14, 0, 0, tzinfo=IST)
        tuesday_4pm = datetime(2025, 1, 7, 16, 0, 0, tzinfo=IST)

        mock_stale_order = Mock()
        mock_stale_order.side = "buy"
        mock_stale_order.status = OrderStatus.PENDING
        mock_stale_order.symbol = "WIPRO-EQ"
        mock_stale_order.placed_at = monday_2pm

        # Recent PENDING order
        tuesday_2pm = datetime(2025, 1, 7, 14, 0, 0, tzinfo=IST)
        mock_recent_order = Mock()
        mock_recent_order.side = "buy"
        mock_recent_order.status = OrderStatus.PENDING
        mock_recent_order.symbol = "TCS-EQ"
        mock_recent_order.placed_at = tuesday_2pm

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_stale_order, mock_recent_order], 2))

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=tuesday_4pm):
            count = service.get_portfolio_count(include_pending=True)

        # Should count: 1 holding + 1 recent PENDING = 2 (stale PENDING excluded)
        assert count == 2

    def test_check_portfolio_capacity_with_stale_pending_exclusion(self):
        """Test that check_portfolio_capacity() correctly excludes stale PENDING orders"""
        mock_portfolio = Mock()
        mock_portfolio.get_holdings = Mock(
            return_value={"data": [{"tradingSymbol": f"STOCK{i}"} for i in range(5)]}
        )

        # 1 stale PENDING order (should be excluded)
        monday_2pm = datetime(2025, 1, 6, 14, 0, 0, tzinfo=IST)
        tuesday_4pm = datetime(2025, 1, 7, 16, 0, 0, tzinfo=IST)

        mock_stale_order = Mock()
        mock_stale_order.side = "buy"
        mock_stale_order.status = OrderStatus.PENDING
        mock_stale_order.symbol = "STALE-EQ"
        mock_stale_order.placed_at = monday_2pm

        # 1 recent PENDING order (should be included)
        tuesday_2pm = datetime(2025, 1, 7, 14, 0, 0, tzinfo=IST)
        mock_recent_order = Mock()
        mock_recent_order.side = "buy"
        mock_recent_order.status = OrderStatus.PENDING
        mock_recent_order.symbol = "RECENT-EQ"
        mock_recent_order.placed_at = tuesday_2pm

        mock_orders_repo = Mock()
        mock_orders_repo.list = Mock(return_value=([mock_stale_order, mock_recent_order], 2))

        mock_config = Mock()
        mock_config.max_portfolio_size = 6

        service = PortfolioService(
            portfolio=mock_portfolio,
            orders_repo=mock_orders_repo,
            user_id=1,
            strategy_config=mock_config,
            enable_caching=False,
        )

        with patch("src.infrastructure.db.timezone_utils.ist_now", return_value=tuesday_4pm):
            has_capacity, current, max_size = service.check_portfolio_capacity()

        # Should have capacity: 5 holdings + 1 recent PENDING = 6 (stale excluded)
        # At limit (6/6), so has_capacity = False
        assert has_capacity is False
        assert current == 6  # 5 holdings + 1 recent PENDING (stale excluded)
        assert max_size == 6
