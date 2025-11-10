import pytest

from src.domain.value_objects.indicators import (
    RSIIndicator, EMAIndicator, SupportResistanceLevel, IndicatorSet
)


def test_rsi_indicator_validation_and_helpers():
    with pytest.raises(ValueError):
        RSIIndicator(-1)
    with pytest.raises(ValueError):
        RSIIndicator(50, period=0)

    rsi = RSIIndicator(25, period=10)
    assert rsi.is_oversold()
    assert not rsi.is_overbought()
    assert rsi.is_extremely_oversold() is False
    assert rsi.get_severity() == 'moderate'
    assert str(rsi).startswith('RSI(10)=')


def test_ema_indicator_validation_and_calcs():
    with pytest.raises(ValueError):
        EMAIndicator(-1)
    with pytest.raises(ValueError):
        EMAIndicator(10, period=0)

    ema = EMAIndicator(100, period=200)
    assert ema.is_price_above(110)
    assert ema.get_distance_percentage(110) == pytest.approx(10.0)


def test_support_resistance_level_and_indicator_set():
    with pytest.raises(ValueError):
        SupportResistanceLevel(-1)
    with pytest.raises(ValueError):
        SupportResistanceLevel(100, strength='invalid')

    supp = SupportResistanceLevel(100, strength='strong')
    assert supp.is_near(101.5, threshold_pct=2.0)
    assert supp.is_strong()

    rsi = RSIIndicator(25)
    ema = EMAIndicator(100)
    ind = IndicatorSet(rsi=rsi, ema=ema, support=supp, volume_ratio=1.6)
    assert ind.is_complete()
    assert ind.meets_reversal_criteria()
    assert ind.get_signal_strength() > 0
    assert 'RSI' in str(ind)
