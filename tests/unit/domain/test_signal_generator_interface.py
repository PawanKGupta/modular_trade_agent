import pytest

from src.domain.interfaces.signal_generator import SignalGenerator
from src.domain.entities.signal import Signal, SignalType
from src.domain.value_objects.indicators import IndicatorSet, RSIIndicator, EMAIndicator
from datetime import datetime


def test_signal_generator_abstract_enforcement():
    # Cannot instantiate abstract base
    with pytest.raises(TypeError):
        SignalGenerator()

    class SimpleGen(SignalGenerator):
        def generate_signal(self, ticker, indicators, current_price, **kwargs):
            sig_type = SignalType.BUY if indicators and indicators.rsi and indicators.rsi.is_oversold() else SignalType.WATCH
            return Signal(ticker=ticker, signal_type=sig_type, timestamp=datetime.now(), strength_score=50.0)
        def evaluate_signal_strength(self, signal: Signal) -> float:
            return signal.strength_score
        def should_generate_alert(self, signal: Signal) -> bool:
            return signal.is_buyable()
        def get_signal_justifications(self, signal: Signal):
            return ["rsi:oversold"] if signal.is_buyable() else []

    gen = SimpleGen()
    ind = IndicatorSet(rsi=RSIIndicator(25), ema=EMAIndicator(100))
    sig = gen.generate_signal('AAA.NS', ind, current_price=105)
    assert gen.should_generate_alert(sig)
    assert gen.evaluate_signal_strength(sig) == 50.0
    assert gen.get_signal_justifications(sig)
