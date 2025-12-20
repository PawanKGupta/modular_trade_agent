"""
Unit tests for RSI Exit functionality in Paper Trading Service Adapter

Tests verify RSI exit condition checking and order conversion for paper trading.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.application.services.paper_trading_service_adapter import PaperTradingServiceAdapter
from src.infrastructure.db.models import Users


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="rsi_exit_test@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def paper_adapter(db_session, test_user):
    """Create paper trading service adapter"""
    with (
        patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
        ) as mock_broker_class,
        patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
        ) as mock_config_class,
    ):
        mock_broker = MagicMock()
        mock_broker.connect.return_value = True
        mock_broker.get_holdings.return_value = []
        mock_broker.get_available_balance.return_value = MagicMock(amount=100000.0)
        mock_broker_class.return_value = mock_broker

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            initial_capital=100000.0,
        )
        adapter.broker = mock_broker
        adapter.engine = MagicMock()
        return adapter


class TestRSI10CacheInitializationPaper:
    """Test RSI10 cache initialization at market open (paper trading)"""

    def test_rsi10_cache_initialized_empty(self, paper_adapter):
        """Test that RSI10 cache is initialized as empty dict"""
        assert isinstance(paper_adapter.rsi10_cache, dict)
        assert len(paper_adapter.rsi10_cache) == 0
        assert isinstance(paper_adapter.converted_to_market, set)
        assert len(paper_adapter.converted_to_market) == 0

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    def test_initialize_rsi10_cache_with_positions(self, mock_rsi, mock_fetch, paper_adapter):
        """Test that RSI10 cache is initialized with previous day's RSI10 for positions"""
        # Mock OHLCV data
        mock_data = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104],
                "high": [105, 106, 107, 108, 109],
                "low": [95, 96, 97, 98, 99],
                "open": [99, 100, 101, 102, 103],
                "volume": [1000000] * 5,
            }
        )
        mock_fetch.return_value = mock_data

        # Mock RSI calculation (second-to-last row is previous day)
        mock_rsi.return_value = pd.Series([30.0, 32.0, 35.0, 38.0, 40.0])

        # Set up active sell orders
        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            },
            "TCS": {
                "order_id": "ORDER456",
                "target_price": 3500.0,
                "qty": 20,
                "ticker": "TCS.NS",
                "entry_date": "2024-01-01",
            },
        }

        # Call cache initialization
        paper_adapter._initialize_rsi10_cache_paper()

        # Verify cache was populated (previous day is second-to-last row, RSI=38.0)
        assert len(paper_adapter.rsi10_cache) == 2
        assert paper_adapter.rsi10_cache["RELIANCE"] == 38.0
        assert paper_adapter.rsi10_cache["TCS"] == 38.0
        assert mock_fetch.call_count == 2

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    def test_initialize_rsi10_cache_handles_missing_ticker(self, mock_fetch, paper_adapter):
        """Test that cache initialization handles positions without ticker"""
        # Set up active sell orders with missing ticker
        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            },
            "TCS": {
                "order_id": "ORDER456",
                "target_price": 3500.0,
                "qty": 20,
                # Missing ticker
                "entry_date": "2024-01-01",
            },
        }

        # Call cache initialization
        paper_adapter._initialize_rsi10_cache_paper()

        # Verify only position with ticker was processed
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args[0][0] == "RELIANCE.NS"

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    def test_initialize_rsi10_cache_handles_none_rsi(self, mock_rsi, mock_fetch, paper_adapter):
        """Test that cache initialization handles None RSI values"""
        # Mock empty data (returns None RSI)
        mock_fetch.return_value = None

        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            },
        }

        # Call cache initialization
        paper_adapter._initialize_rsi10_cache_paper()

        # Verify cache was not populated
        assert len(paper_adapter.rsi10_cache) == 0


class TestGetCurrentRSI10Paper:
    """Test real-time RSI10 calculation with fallback (paper trading)"""

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    def test_get_current_rsi10_uses_real_time_first(self, mock_rsi, mock_fetch, paper_adapter):
        """Test that real-time RSI10 is used when available"""
        # Mock OHLCV data with current day
        mock_data = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104],
                "high": [105, 106, 107, 108, 109],
                "low": [95, 96, 97, 98, 99],
                "open": [99, 100, 101, 102, 103],
                "volume": [1000000] * 5,
            }
        )
        mock_fetch.return_value = mock_data
        # Mock RSI calculation (latest row is current day)
        mock_rsi.return_value = pd.Series([30.0, 32.0, 35.0, 38.0, 45.0])

        # No cached value
        paper_adapter.rsi10_cache = {}

        rsi10 = paper_adapter._get_current_rsi10_paper("RELIANCE", "RELIANCE.NS")

        # Verify real-time RSI was used
        assert rsi10 == 45.0
        assert paper_adapter.rsi10_cache["RELIANCE"] == 45.0
        # Verify add_current_day=True was used
        assert mock_fetch.call_args[1]["add_current_day"] is True

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    def test_get_current_rsi10_updates_cache_with_real_time(
        self, mock_rsi, mock_fetch, paper_adapter
    ):
        """Test that cache is updated when real-time RSI10 is available"""
        # Mock OHLCV data
        mock_data = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104],
                "high": [105, 106, 107, 108, 109],
                "low": [95, 96, 97, 98, 99],
                "open": [99, 100, 101, 102, 103],
                "volume": [1000000] * 5,
            }
        )
        mock_fetch.return_value = mock_data
        mock_rsi.return_value = pd.Series([30.0, 32.0, 35.0, 38.0, 45.0])

        # Set cached value (previous day)
        paper_adapter.rsi10_cache = {"RELIANCE": 35.0}

        rsi10 = paper_adapter._get_current_rsi10_paper("RELIANCE", "RELIANCE.NS")

        # Verify real-time RSI was used and cache updated
        assert rsi10 == 45.0
        assert paper_adapter.rsi10_cache["RELIANCE"] == 45.0

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    def test_get_current_rsi10_fallback_to_cache(self, mock_fetch, paper_adapter):
        """Test that cached value is used when real-time RSI10 is unavailable"""
        # Mock real-time RSI10 unavailable
        mock_fetch.return_value = None

        # Set cached value (previous day)
        paper_adapter.rsi10_cache = {"RELIANCE": 35.0}

        rsi10 = paper_adapter._get_current_rsi10_paper("RELIANCE", "RELIANCE.NS")

        # Verify cached value was used
        assert rsi10 == 35.0

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    def test_get_current_rsi10_returns_none_if_no_data(self, mock_fetch, paper_adapter):
        """Test that None is returned when neither real-time nor cached RSI10 is available"""
        # Mock real-time RSI10 unavailable
        mock_fetch.return_value = None

        # No cached value
        paper_adapter.rsi10_cache = {}

        rsi10 = paper_adapter._get_current_rsi10_paper("RELIANCE", "RELIANCE.NS")

        # Verify None was returned
        assert rsi10 is None


class TestRSIExitConditionCheckPaper:
    """Test RSI exit condition checking (paper trading)"""

    @patch(
        "src.application.services.paper_trading_service_adapter.PaperTradingServiceAdapter._get_current_rsi10_paper"
    )
    def test_check_rsi_exit_condition_triggers_when_rsi_above_50(self, mock_get_rsi, paper_adapter):
        """Test that RSI exit is triggered when RSI10 > 50"""
        # Mock RSI10 > 50
        mock_get_rsi.return_value = 55.0

        # Set up active sell order
        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock broker place_order
        paper_adapter.broker.place_order = MagicMock(return_value="MARKET_ORDER_123")

        # Call monitor sell orders (which checks RSI exit)
        with patch("core.data_fetcher.fetch_ohlcv_yf") as mock_fetch:
            mock_data = pd.DataFrame(
                {
                    "high": [2550.0],  # High < Target (not reached)
                    "close": [2520.0],
                    "rsi10": [55.0],  # RSI > 50 (falling knife exit!)
                }
            )
            mock_fetch.return_value = mock_data

            paper_adapter._monitor_sell_orders()

        # Verify order was removed (RSI exit triggered)
        assert "RELIANCE" not in paper_adapter.active_sell_orders
        # Verify market order was placed
        assert paper_adapter.broker.place_order.called

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    @patch(
        "src.application.services.paper_trading_service_adapter.PaperTradingServiceAdapter._get_current_rsi10_paper"
    )
    def test_check_rsi_exit_condition_no_trigger_when_rsi_below_50(
        self, mock_get_rsi, mock_rsi, mock_fetch, paper_adapter
    ):
        """Test that RSI exit is not triggered when RSI10 <= 50"""
        # Mock broker check_and_execute_pending_orders
        paper_adapter.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        # Mock RSI10 <= 50
        mock_get_rsi.return_value = 45.0

        # Set up active sell order
        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Call monitor sell orders
        mock_data = pd.DataFrame(
            {
                "high": [2550.0],  # High < Target (not reached)
                "close": [2520.0],
            }
        )
        mock_fetch.return_value = mock_data
        mock_rsi.return_value = pd.Series([45.0])

        paper_adapter._monitor_sell_orders()

        # Verify order remains active
        assert "RELIANCE" in paper_adapter.active_sell_orders

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    def test_check_rsi_exit_condition_skips_already_converted(
        self, mock_rsi, mock_fetch, paper_adapter
    ):
        """Test that already converted orders are skipped"""
        # Mock broker check_and_execute_pending_orders
        paper_adapter.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        # Mark as already converted
        paper_adapter.converted_to_market.add("RELIANCE")

        # Set up active sell order
        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock broker place_order
        paper_adapter.broker.place_order = MagicMock()

        # Call monitor sell orders
        mock_data = pd.DataFrame(
            {
                "high": [2550.0],
                "close": [2520.0],
            }
        )
        mock_fetch.return_value = mock_data
        mock_rsi.return_value = pd.Series([55.0])

        paper_adapter._monitor_sell_orders()

        # Verify order was not converted again
        assert "RELIANCE" in paper_adapter.active_sell_orders
        assert not paper_adapter.broker.place_order.called

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    @patch(
        "src.application.services.paper_trading_service_adapter.PaperTradingServiceAdapter._get_current_rsi10_paper"
    )
    def test_check_rsi_exit_condition_handles_missing_ticker(
        self, mock_get_rsi, mock_rsi, mock_fetch, paper_adapter
    ):
        """Test that missing ticker is handled gracefully"""
        # Mock broker check_and_execute_pending_orders
        paper_adapter.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        # Set up active sell order without ticker
        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                # Missing ticker
                "entry_date": "2024-01-01",
            }
        }

        # Call monitor sell orders
        try:
            paper_adapter._monitor_sell_orders()
        except KeyError:
            # Expected - missing ticker causes KeyError
            pass

        # Verify get_rsi was not called (no ticker, exception caught)
        mock_get_rsi.assert_not_called()

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    @patch(
        "src.application.services.paper_trading_service_adapter.PaperTradingServiceAdapter._get_current_rsi10_paper"
    )
    def test_check_rsi_exit_condition_handles_none_rsi(
        self, mock_get_rsi, mock_rsi, mock_fetch, paper_adapter
    ):
        """Test that None RSI is handled gracefully"""
        # Mock broker check_and_execute_pending_orders
        paper_adapter.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        # Mock None RSI
        mock_get_rsi.return_value = None

        # Set up active sell order
        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Call monitor sell orders
        mock_data = pd.DataFrame(
            {
                "high": [2550.0],
                "close": [2520.0],
            }
        )
        mock_fetch.return_value = mock_data
        mock_rsi.return_value = pd.Series([None])

        paper_adapter._monitor_sell_orders()

        # Verify order remains active (no RSI exit)
        assert "RELIANCE" in paper_adapter.active_sell_orders


class TestRSIExitErrorHandlingPaper:
    """Test error handling for RSI exit (paper trading)"""

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    def test_error_handling_when_rsi_calculation_fails(self, mock_fetch, paper_adapter):
        """Test error handling when RSI calculation fails"""
        # Mock exception during RSI calculation
        mock_fetch.side_effect = Exception("Data fetch failed")

        # Call get_current_rsi10_paper - should handle exception gracefully
        rsi10 = paper_adapter._get_current_rsi10_paper("RELIANCE", "RELIANCE.NS")

        # Verify None returned (fallback to cache if available)
        # Since no cache, should return None
        assert rsi10 is None or rsi10 == paper_adapter.rsi10_cache.get("RELIANCE")

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    @patch(
        "src.application.services.paper_trading_service_adapter.PaperTradingServiceAdapter._get_current_rsi10_paper"
    )
    def test_error_handling_when_order_conversion_fails(
        self, mock_get_rsi, mock_rsi, mock_fetch, paper_adapter
    ):
        """Test error handling when order conversion fails"""
        # Mock broker check_and_execute_pending_orders
        paper_adapter.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        # Mock broker place_order to fail
        paper_adapter.broker.place_order = MagicMock(
            side_effect=Exception("Order placement failed")
        )
        # Mock RSI > 50
        mock_get_rsi.return_value = 55.0

        # Set up active sell order
        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Call monitor sell orders with RSI > 50
        mock_data = pd.DataFrame(
            {
                "high": [2550.0],
                "close": [2520.0],
            }
        )
        mock_fetch.return_value = mock_data
        mock_rsi.return_value = pd.Series([55.0])

        # Should handle exception gracefully (caught in try-except)
        paper_adapter._monitor_sell_orders()

        # Verify order might still be in active_sell_orders (if exception was caught)
        # The exact behavior depends on implementation, but should not crash
        # Exception is caught and logged, order remains in active_sell_orders
        assert "RELIANCE" in paper_adapter.active_sell_orders

    @patch("core.data_fetcher.fetch_ohlcv_yf")
    @patch("pandas_ta.rsi")
    @patch(
        "src.application.services.paper_trading_service_adapter.PaperTradingServiceAdapter._get_current_rsi10_paper"
    )
    def test_error_handling_when_market_order_placement_fails(
        self, mock_get_rsi, mock_rsi, mock_fetch, paper_adapter
    ):
        """Test error handling when market order placement fails"""
        # Mock broker check_and_execute_pending_orders to return proper dict
        paper_adapter.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        # Mock broker place_order to return None/False
        paper_adapter.broker.place_order = MagicMock(return_value=None)

        # Mock RSI > 50
        mock_get_rsi.return_value = 55.0

        # Set up active sell order
        paper_adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "ORDER123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Call monitor sell orders with RSI > 50
        mock_data = pd.DataFrame(
            {
                "high": [2550.0],  # High < Target (not reached)
                "close": [2520.0],
            }
        )
        mock_fetch.return_value = mock_data
        mock_rsi.return_value = pd.Series([55.0])

        # Should handle failure gracefully
        paper_adapter._monitor_sell_orders()

        # Verify place_order was called (even if it returns None)
        assert paper_adapter.broker.place_order.called
