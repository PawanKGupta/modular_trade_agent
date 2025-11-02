from datetime import datetime, timedelta
import pytest

from src.domain.entities.trade import Trade, TradeDirection, TradeStatus


def test_trade_lifecycle_and_pnl_long():
    t = Trade(
        ticker='AAA.NS',
        entry_date=datetime(2024,1,1),
        entry_price=100.0,
        quantity=10,
        capital=1000.0,
        direction=TradeDirection.LONG
    )
    assert t.is_open()
    t.close(exit_date=datetime(2024,1,10), exit_price=110.0)
    assert t.is_closed()
    assert t.get_pnl() == 10*10.0
    assert t.get_pnl_percentage() == pytest.approx((100.0/1000.0)*100)
    assert t.get_holding_days() == 9
    assert t.is_winner()
    assert 'CLOSED' in str(t).upper()


def test_trade_short_and_cancel_and_validation():
    t = Trade(
        ticker='BBB.NS',
        entry_date=datetime(2024,2,1),
        entry_price=200.0,
        quantity=5,
        capital=1000.0,
        direction=TradeDirection.SHORT
    )
    t.close(exit_date=datetime(2024,2,5), exit_price=180.0)
    assert t.get_pnl() == (200.0-180.0)*5

    t2 = Trade(
        ticker='CCC.NS',
        entry_date=datetime(2024,3,1),
        entry_price=150.0,
        quantity=2,
        capital=300.0,
    )
    t2.cancel()
    assert t2.status == TradeStatus.CANCELLED

    with pytest.raises(ValueError):
        Trade(ticker='X', entry_date=datetime.now(), entry_price=0, quantity=1, capital=1)
    with pytest.raises(ValueError):
        Trade(ticker='X', entry_date=datetime.now(), entry_price=1, quantity=0, capital=1)
    with pytest.raises(ValueError):
        Trade(ticker='X', entry_date=datetime.now(), entry_price=1, quantity=1, capital=0)
