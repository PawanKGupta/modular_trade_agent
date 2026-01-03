"""
Tests for ExecuteTradesUseCase quantity calculation fix.

Tests verify that:
1. Each stock gets correct quantity based on execution capital and price
2. User config capital is used when available
3. Falls back to 1.0 capital (minimum 1 qty) when no config
4. Stock's execution_capital takes precedence over user config
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.mock_broker_adapter import (
    MockBrokerAdapter,
)
from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse
from src.application.use_cases.execute_trades import ExecuteTradesUseCase


def make_resp(ticker, verdict="buy", combined=50.0, last_close=100.0, execution_capital=None):
    """Helper to create AnalysisResponse with optional execution_capital"""
    resp = AnalysisResponse(
        ticker=ticker,
        status="success",
        timestamp=datetime.now(),
        verdict=verdict,
        last_close=last_close,
        combined_score=combined,
    )
    if execution_capital is not None:
        resp.execution_capital = execution_capital
    return resp


class TestQuantityCalculationWithUserConfig:
    """Test quantity calculation when user config is provided"""

    def test_uses_user_capital_from_config(self):
        """Test that user_capital from UserTradingConfig is used"""
        broker = MockBrokerAdapter()
        mock_db = MagicMock()
        mock_config = MagicMock()
        mock_config.user_capital = 50000.0  # Rs 50,000

        # Mock UserTradingConfigRepository (patch where it's imported in execute_trades.py)
        mock_repo_instance = MagicMock()
        mock_repo_instance.get_or_create_default.return_value = mock_config

        with patch(
            "src.application.use_cases.execute_trades.UserTradingConfigRepository",
            return_value=mock_repo_instance,
        ):
            # Stock at Rs 100, should get qty = floor(50000/100) = 500
            r1 = make_resp("STOCK1.NS", verdict="buy", last_close=100.0)

            bulk = BulkAnalysisResponse(
                results=[r1],
                total_analyzed=1,
                successful=1,
                failed=0,
                buyable_count=1,
                timestamp=datetime.now(),
                execution_time_seconds=0.1,
            )

            uc = ExecuteTradesUseCase(
                broker_gateway=broker,
                trade_history_repo=None,
                user_id=1,
                db_session=mock_db,
            )
            summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=False)

            assert summary.success
            assert len(summary.orders_placed) == 1
            order = summary.orders_placed[0]
            assert order["ticker"] == "STOCK1.NS"
            assert order["quantity"] == 500  # floor(50000/100) = 500

    def test_different_quantities_for_different_prices(self):
        """Test that different stocks get different quantities based on their prices"""
        broker = MockBrokerAdapter()
        mock_db = MagicMock()
        mock_config = MagicMock()
        mock_config.user_capital = 100000.0  # Rs 1,00,000

        mock_repo_instance = MagicMock()
        mock_repo_instance.get_or_create_default.return_value = mock_config

        with patch(
            "src.application.use_cases.execute_trades.UserTradingConfigRepository",
            return_value=mock_repo_instance,
        ):
            # Stock 1: Rs 100 -> qty = floor(100000/100) = 1000
            # Stock 2: Rs 500 -> qty = floor(100000/500) = 200
            # Stock 3: Rs 50 -> qty = floor(100000/50) = 2000
            r1 = make_resp("STOCK1.NS", verdict="buy", last_close=100.0)
            r2 = make_resp("STOCK2.NS", verdict="buy", last_close=500.0)
            r3 = make_resp("STOCK3.NS", verdict="buy", last_close=50.0)

            bulk = BulkAnalysisResponse(
                results=[r1, r2, r3],
                total_analyzed=3,
                successful=3,
                failed=0,
                buyable_count=3,
                timestamp=datetime.now(),
                execution_time_seconds=0.1,
            )

            uc = ExecuteTradesUseCase(
                broker_gateway=broker,
                trade_history_repo=None,
                user_id=1,
                db_session=mock_db,
            )
            summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=False)

            assert summary.success
            assert len(summary.orders_placed) == 3

            # Verify each stock got correct quantity
            orders_by_ticker = {o["ticker"]: o["quantity"] for o in summary.orders_placed}
            assert orders_by_ticker["STOCK1.NS"] == 1000  # floor(100000/100)
            assert orders_by_ticker["STOCK2.NS"] == 200  # floor(100000/500)
            assert orders_by_ticker["STOCK3.NS"] == 2000  # floor(100000/50)

            # Verify quantities are different (not all same)
            quantities = list(orders_by_ticker.values())
            assert len(set(quantities)) == 3, "All stocks should have different quantities"

    def test_stock_execution_capital_takes_precedence(self):
        """Test that stock's execution_capital overrides user config"""
        broker = MockBrokerAdapter()
        mock_db = MagicMock()
        mock_config = MagicMock()
        mock_config.user_capital = 50000.0  # User config: Rs 50,000

        mock_repo_instance = MagicMock()
        mock_repo_instance.get_or_create_default.return_value = mock_config

        with patch(
            "src.application.use_cases.execute_trades.UserTradingConfigRepository",
            return_value=mock_repo_instance,
        ):
            # Stock has its own execution_capital: Rs 25,000
            # Should use stock's capital (25000) instead of user config (50000)
            r1 = make_resp("STOCK1.NS", verdict="buy", last_close=100.0, execution_capital=25000.0)

            bulk = BulkAnalysisResponse(
                results=[r1],
                total_analyzed=1,
                successful=1,
                failed=0,
                buyable_count=1,
                timestamp=datetime.now(),
                execution_time_seconds=0.1,
            )

            uc = ExecuteTradesUseCase(
                broker_gateway=broker,
                trade_history_repo=None,
                user_id=1,
                db_session=mock_db,
            )
            summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=False)

            assert summary.success
            assert len(summary.orders_placed) == 1
            order = summary.orders_placed[0]
            # Should use stock's capital: floor(25000/100) = 250,
            # not user config: floor(50000/100) = 500
            assert order["quantity"] == 250


class TestQuantityCalculationWithoutUserConfig:
    """Test quantity calculation when user config is NOT provided"""

    def test_falls_back_to_minimum_1_qty(self):
        """Test that falls back to 1.0 capital, ensuring minimum 1 qty"""
        broker = MockBrokerAdapter()

        # No user_id or db_session provided
        r1 = make_resp("STOCK1.NS", verdict="buy", last_close=100.0)

        bulk = BulkAnalysisResponse(
            results=[r1],
            total_analyzed=1,
            successful=1,
            failed=0,
            buyable_count=1,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=broker,
            trade_history_repo=None,
            # No user_id or db_session
        )
        summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=False)

        assert summary.success
        assert len(summary.orders_placed) == 1
        order = summary.orders_placed[0]
        # With capital=1.0 and price=100: qty = max(1, floor(1/100)) = max(1, 0) = 1
        assert order["quantity"] == 1

    def test_minimum_1_qty_for_high_price_stocks(self):
        """Test that high price stocks still get minimum 1 qty"""
        broker = MockBrokerAdapter()

        # Stock with very high price
        r1 = make_resp("EXPENSIVE.NS", verdict="buy", last_close=10000.0)

        bulk = BulkAnalysisResponse(
            results=[r1],
            total_analyzed=1,
            successful=1,
            failed=0,
            buyable_count=1,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=broker,
            trade_history_repo=None,
        )
        summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=False)

        assert summary.success
        assert len(summary.orders_placed) == 1
        order = summary.orders_placed[0]
        # With capital=1.0 and price=10000: qty = max(1, floor(1/10000)) = max(1, 0) = 1
        assert order["quantity"] == 1

    def test_multiple_stocks_all_get_1_qty_when_no_config(self):
        """Test that multiple stocks all get 1 qty when no user config"""
        broker = MockBrokerAdapter()

        r1 = make_resp("STOCK1.NS", verdict="buy", last_close=100.0)
        r2 = make_resp("STOCK2.NS", verdict="buy", last_close=500.0)
        r3 = make_resp("STOCK3.NS", verdict="buy", last_close=50.0)

        bulk = BulkAnalysisResponse(
            results=[r1, r2, r3],
            total_analyzed=3,
            successful=3,
            failed=0,
            buyable_count=3,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=broker,
            trade_history_repo=None,
        )
        summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=False)

        assert summary.success
        assert len(summary.orders_placed) == 3

        # All should get 1 qty (minimum) when capital=1.0
        for order in summary.orders_placed:
            assert order["quantity"] == 1


class TestQuantityCalculationEdgeCases:
    """Test edge cases for quantity calculation"""

    def test_fractional_shares_truncated(self):
        """Test that fractional shares are truncated correctly"""
        broker = MockBrokerAdapter()
        mock_db = MagicMock()
        mock_config = MagicMock()
        mock_config.user_capital = 33333.0  # Rs 33,333

        mock_repo_instance = MagicMock()
        mock_repo_instance.get_or_create_default.return_value = mock_config

        with patch(
            "src.application.use_cases.execute_trades.UserTradingConfigRepository",
            return_value=mock_repo_instance,
        ):
            # Price that gives fractional result: 33333/100 = 333.33 -> should be 333
            r1 = make_resp("STOCK1.NS", verdict="buy", last_close=100.0)

            bulk = BulkAnalysisResponse(
                results=[r1],
                total_analyzed=1,
                successful=1,
                failed=0,
                buyable_count=1,
                timestamp=datetime.now(),
                execution_time_seconds=0.1,
            )

            uc = ExecuteTradesUseCase(
                broker_gateway=broker,
                trade_history_repo=None,
                user_id=1,
                db_session=mock_db,
            )
            summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=False)

            assert summary.success
            order = summary.orders_placed[0]
            # floor(33333/100) = 333 (truncated, not rounded)
            assert order["quantity"] == 333
            assert isinstance(order["quantity"], int)

    def test_config_fetch_error_falls_back_to_1(self):
        """Test that if config fetch fails, falls back to 1.0 capital"""
        broker = MockBrokerAdapter()
        mock_db = MagicMock()

        with patch(
            "src.infrastructure.persistence.user_trading_config_repository.UserTradingConfigRepository"
        ) as mock_repo_class:
            # Simulate error when fetching config
            mock_repo_class.side_effect = Exception("Database error")

            r1 = make_resp("STOCK1.NS", verdict="buy", last_close=100.0)

            bulk = BulkAnalysisResponse(
                results=[r1],
                total_analyzed=1,
                successful=1,
                failed=0,
                buyable_count=1,
                timestamp=datetime.now(),
                execution_time_seconds=0.1,
            )

            uc = ExecuteTradesUseCase(
                broker_gateway=broker,
                trade_history_repo=None,
                user_id=1,
                db_session=mock_db,
            )
            summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=False)

            assert summary.success
            order = summary.orders_placed[0]
            # Should fall back to 1 qty when config fetch fails
            assert order["quantity"] == 1

    def test_zero_or_negative_execution_capital_uses_default(self):
        """Test that zero or negative execution_capital uses user config or default"""
        broker = MockBrokerAdapter()
        mock_db = MagicMock()
        mock_config = MagicMock()
        mock_config.user_capital = 50000.0

        mock_repo_instance = MagicMock()
        mock_repo_instance.get_or_create_default.return_value = mock_config

        with patch(
            "src.application.use_cases.execute_trades.UserTradingConfigRepository",
            return_value=mock_repo_instance,
        ):
            # Stock with zero execution_capital should use user config
            r1 = make_resp("STOCK1.NS", verdict="buy", last_close=100.0, execution_capital=0.0)
            # Stock with negative execution_capital should use user config
            r2 = make_resp("STOCK2.NS", verdict="buy", last_close=100.0, execution_capital=-1000.0)

            bulk = BulkAnalysisResponse(
                results=[r1, r2],
                total_analyzed=2,
                successful=2,
                failed=0,
                buyable_count=2,
                timestamp=datetime.now(),
                execution_time_seconds=0.1,
            )

            uc = ExecuteTradesUseCase(
                broker_gateway=broker,
                trade_history_repo=None,
                user_id=1,
                db_session=mock_db,
            )
            summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=False)

            assert summary.success
            assert len(summary.orders_placed) == 2

            # Both should use user config capital: floor(50000/100) = 500
            for order in summary.orders_placed:
                assert order["quantity"] == 500
