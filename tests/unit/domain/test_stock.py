import pytest
from datetime import datetime
from src.domain.entities.stock import Stock


def test_stock_validation_and_helpers():
    s = Stock(ticker="RELIANCE.NS", exchange="NSE", last_close=2450.5, last_updated=datetime.now())
    assert s.is_valid()
    assert s.get_display_symbol() == "RELIANCE.NS"

    with pytest.raises(ValueError):
        Stock(ticker="RELIANCE.NS", exchange="NSE", last_close=0, last_updated=datetime.now())
    with pytest.raises(ValueError):
        Stock(ticker="", exchange="NSE", last_close=1, last_updated=datetime.now())
