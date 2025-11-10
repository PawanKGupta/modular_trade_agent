import pandas as pd
import pytest

from src.infrastructure.indicators.pandas_ta_calculator import PandasTACalculator
from src.domain.interfaces.indicator_calculator import IndicatorCalculationError


def make_ohlcv(n=30):
    import numpy as np
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 110, n))
    high = close + 1
    low = close - 1
    vol = pd.Series(np.linspace(1000, 2000, n))
    return pd.DataFrame({
        'date': dates,
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': vol,
    })


def test_validate_data():
    calc = PandasTACalculator()
    assert not calc.validate_data(pd.DataFrame())
    assert not calc.validate_data(pd.DataFrame({'open':[1,2]}))
    df = make_ohlcv()
    assert calc.validate_data(df)


def test_calculate_rsi_and_ema():
    calc = PandasTACalculator()
    df = make_ohlcv(50)
    rsi = calc.calculate_rsi(df, period=10)
    ema = calc.calculate_ema(df, period=20)
    assert not rsi.empty and not ema.empty


def test_support_resistance_and_volume_ratio():
    calc = PandasTACalculator()
    df = make_ohlcv(40)
    support, resistance = calc.calculate_support_resistance(df, lookback=20)
    assert support is not None and resistance is not None
    vr = calc.calculate_volume_ratio(df, period=20)
    assert vr > 0


def test_calculate_all_indicators():
    calc = PandasTACalculator()
    df = make_ohlcv(60)
    indicators = calc.calculate_all_indicators(df, rsi_period=10, ema_period=20)
    assert indicators.rsi is not None
    assert indicators.ema is not None
    assert indicators.support is not None
    assert indicators.resistance is not None
    assert indicators.volume_ratio > 0
