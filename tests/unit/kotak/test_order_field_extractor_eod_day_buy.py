"""Tests for EOD cancellable DAY buy detection helpers."""

from unittest.mock import MagicMock

import pytest

from modules.kotak_neo_auto_trader.domain import (
    Exchange,
    Order,
    OrderType,
    OrderVariety,
    TransactionType,
)
from modules.kotak_neo_auto_trader.domain.value_objects.money import Money
from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import OrderStatus
from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor


class TestEodCancellableDayBuyBrokerOrder:
    def test_regular_pending_day_buy_is_cancellable(self):
        order = {
            "nOrdNo": "123",
            "trdSym": "RELIANCE-EQ",
            "transactionType": "BUY",
            "orderStatus": "open",
            "orderValidity": "DAY",
        }
        assert OrderFieldExtractor.is_eod_cancellable_day_buy_broker_order(order) is True

    def test_amo_pending_buy_is_not_cancellable(self):
        order = {
            "nOrdNo": "124",
            "trdSym": "RELIANCE-EQ",
            "transactionType": "BUY",
            "orderStatus": "open",
            "orderValidity": "DAY",
            "am": "YES",
        }
        assert OrderFieldExtractor.is_eod_cancellable_day_buy_broker_order(order) is False
        assert OrderFieldExtractor.is_amo_broker_order(order) is True

    def test_ioc_buy_is_not_cancellable(self):
        order = {
            "nOrdNo": "125",
            "trdSym": "RELIANCE-EQ",
            "transactionType": "BUY",
            "orderStatus": "open",
            "orderValidity": "IOC",
        }
        assert OrderFieldExtractor.is_eod_cancellable_day_buy_broker_order(order) is False


class TestEodCancellableDayBuyDbOrder:
    def test_pending_regular_db_buy_is_cancellable(self):
        db_order = MagicMock()
        db_order.side = "buy"
        db_order.status = MagicMock(value="PENDING")
        db_order.reason = "limit order placed"
        db_order.order_metadata = {"entry_type": "reentry"}
        assert OrderFieldExtractor.is_eod_cancellable_day_buy_db_order(db_order) is True

    def test_pending_amo_db_buy_is_not_cancellable(self):
        db_order = MagicMock()
        db_order.side = "buy"
        db_order.status = MagicMock(value="PENDING")
        db_order.reason = "AMO order placed"
        db_order.order_metadata = None
        assert OrderFieldExtractor.is_eod_cancellable_day_buy_db_order(db_order) is False


class TestPaperOrderEntityEodCancellable:
    def test_regular_limit_buy_is_cancellable(self):
        order = Order(
            symbol="GALLANTT.NS",
            quantity=100,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.REGULAR,
            exchange=Exchange.NSE,
            validity="DAY",
            price=Money(100.0),
            order_id="PT1",
            status=OrderStatus.OPEN,
        )
        assert order.is_eod_cancellable_day_buy() is True

    def test_amo_buy_is_not_cancellable(self):
        order = Order(
            symbol="GALLANTT.NS",
            quantity=100,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            exchange=Exchange.NSE,
            validity="DAY",
            price=Money(100.0),
            order_id="PT2",
            status=OrderStatus.OPEN,
        )
        assert order.is_eod_cancellable_day_buy() is False
