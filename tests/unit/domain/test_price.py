import pytest
from src.domain.value_objects.price import Price


def test_price_validation_negative():
    with pytest.raises(ValueError):
        Price(-1.0)


def test_price_equality_and_comparison():
    p1 = Price(100.0)
    p2 = Price(100.0)
    p3 = Price(120.0)

    assert p1 == p2
    assert p1 == 100.0
    assert p3 > p1
    assert p1 < p3

    # Different currency comparison should raise when comparing Price to Price
    with pytest.raises(ValueError):
        _ = Price(100.0, "USD") < Price(90.0, "INR")


def test_price_math_operations():
    p = Price(100.0)
    assert p.add(20.0) == Price(120.0)
    assert p.subtract(30.0) == Price(70.0)
    assert p.multiply(1.5) == Price(150.0)


def test_percentage_change_and_between():
    old = Price(80.0)
    new = Price(100.0)
    assert round(new.percentage_change(old), 2) == 25.0
    assert new.is_between(Price(90.0), Price(110.0))
