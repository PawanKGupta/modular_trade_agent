"""Tests for pending buy detection in OrderFieldExtractor."""

from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor


def test_is_pending_open_buy_order_kotak_fields():
    assert OrderFieldExtractor.is_pending_open_buy_order(
        {
            "trdSym": "POWERGRID-EQ",
            "trnsTp": "B",
            "ordSt": "open",
            "rt": "DAY",
        }
    )


def test_is_pending_open_buy_order_rejects_sell_and_ioc():
    assert not OrderFieldExtractor.is_pending_open_buy_order(
        {"transactionType": "SELL", "orderStatus": "PENDING", "orderValidity": "DAY"}
    )
    assert not OrderFieldExtractor.is_pending_open_buy_order(
        {"transactionType": "BUY", "orderStatus": "PENDING", "orderValidity": "IOC"}
    )
