"""Unit tests for EOD cancellation of unexecuted DAY/REGULAR pending buys."""

from unittest.mock import MagicMock, patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


@pytest.fixture
def mock_engine_for_eod_cancel():
    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth") as mock_auth:
        mock_auth_instance = MagicMock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        engine = AutoTradeEngine(auth=mock_auth_instance, user_id=1, db_session=MagicMock())
        engine.orders = MagicMock()
        engine.orders_repo = MagicMock()
        engine.login = MagicMock(return_value=True)
        return engine


class TestCancelUnexecutedDayBuyOrdersAtEod:
    def test_cancels_day_buy_at_broker_skips_amo(self, mock_engine_for_eod_cancel):
        engine = mock_engine_for_eod_cancel
        engine.orders.get_pending_orders.return_value = [
            {
                "nOrdNo": "DAY_BUY_1",
                "trdSym": "GALLANTT-EQ",
                "transactionType": "BUY",
                "orderStatus": "open",
                "orderValidity": "DAY",
            },
            {
                "nOrdNo": "AMO_BUY_1",
                "trdSym": "RELIANCE-EQ",
                "transactionType": "BUY",
                "orderStatus": "open",
                "orderValidity": "DAY",
                "am": "YES",
            },
        ]
        engine.orders.cancel_order.return_value = True
        engine.orders_repo.list.return_value = ([], 0)

        summary = engine.cancel_unexecuted_day_buy_orders_at_eod()

        engine.orders.cancel_order.assert_called_once_with("DAY_BUY_1")
        assert summary["cancelled"] == 1
        assert summary["skipped_amo"] == 1

    def test_db_sweep_marks_orphan_pending_day_buy(self, mock_engine_for_eod_cancel):
        engine = mock_engine_for_eod_cancel
        engine.orders.get_pending_orders.return_value = []

        db_order = MagicMock()
        db_order.side = "buy"
        db_order.status = MagicMock(value="PENDING")
        db_order.reason = "limit order placed"
        db_order.order_metadata = {}
        db_order.symbol = "GALLANTT-EQ"
        db_order.broker_order_id = "GHOST_BUY"
        db_order.order_id = None
        db_order.id = 99

        engine.orders_repo.list.return_value = ([db_order], 1)

        summary = engine.cancel_unexecuted_day_buy_orders_at_eod()

        engine.orders_repo.mark_cancelled.assert_called_once()
        assert summary["db_only_cancelled"] == 1
