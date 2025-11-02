import pytest
from datetime import datetime
from src.domain.entities.signal import Signal, SignalType


def test_signal_basic_and_justifications():
    s = Signal(
        ticker="RELIANCE.NS",
        signal_type=SignalType.BUY,
        timestamp=datetime.now(),
        strength_score=50.0,
    )
    assert s.is_buyable() is True
    assert s.is_strong() is False
    s.add_justification("rsi:25")
    s.add_justification("rsi:25")
    assert s.justifications.count("rsi:25") == 1


def test_signal_validation():
    with pytest.raises(ValueError):
        Signal(ticker="", signal_type=SignalType.BUY, timestamp=datetime.now(), strength_score=10)
    with pytest.raises(ValueError):
        Signal(ticker="X", signal_type=SignalType.BUY, timestamp=datetime.now(), strength_score=101)
