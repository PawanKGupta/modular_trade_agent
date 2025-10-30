import time
import numpy as np
import pandas as pd
import pytest

from src.infrastructure.indicators.pandas_ta_calculator import PandasTACalculator


@pytest.mark.performance
def test_pandas_ta_calculator_rsi_ema_speed():
    # Generate synthetic OHLCV data
    n = 20000
    idx = pd.date_range("2024-01-01", periods=n, freq="T")
    close = np.cumsum(np.random.randn(n)).astype(float)
    # Shift the series so prices are strictly positive and realistic
    close = close - close.min() + 100.0
    high = close + np.random.rand(n)
    low = close - np.random.rand(n)
    open_ = close + np.random.randn(n) * 0.1
    volume = np.random.randint(1000, 100000, size=n)

    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=idx)

    calc = PandasTACalculator()

    t0 = time.time()
    indicators = calc.calculate_all_indicators(df, rsi_period=10, ema_period=200)
    dt = time.time() - t0

    assert dt < 3.5
    # Sanity: result should have rsi and ema set
    assert indicators.rsi is not None
    assert indicators.ema is not None