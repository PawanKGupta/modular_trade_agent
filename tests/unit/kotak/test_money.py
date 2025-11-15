import pytest
from modules.kotak_neo_auto_trader.domain.value_objects.money import Money


def test_money_basic_ops_and_validation():
    m1 = Money.from_float(100.0)
    m2 = Money.from_int(50)
    assert (m1 + m2).to_float() == 150.0
    assert (m1 - m2).to_float() == 50.0
    assert (m2 * 2).to_float() == 100.0
    assert (m1 / 2).to_float() == 50.0

    # Negative amounts are now allowed (for P&L, losses, etc.)
    # This was changed to support paper trading P&L calculations
    negative_money = Money.from_float(-1.0)
    assert negative_money.to_float() == -1.0
    
    with pytest.raises(ValueError):
        _ = m1 / 0

    # Currency mismatch comparisons/errors
    inr = Money.from_int(10, "INR")
    usd = Money.from_int(10, "USD")
    with pytest.raises(ValueError):
        _ = inr < usd
