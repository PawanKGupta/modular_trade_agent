import types
import builtins
from datetime import datetime

from src.infrastructure.notifications.telegram_notifier import TelegramNotifier
from src.domain.entities.analysis_result import AnalysisResult
from src.domain.entities.signal import Signal, SignalType


def make_result(ticker='AAA.NS', buy=True):
    sig_type = SignalType.BUY if buy else SignalType.WATCH
    sig = Signal(ticker=ticker, signal_type=sig_type, timestamp=datetime.now(), strength_score=50.0)
    return AnalysisResult(
        ticker=ticker,
        status='success',
        timestamp=datetime.now(),
        signal=sig,
        metadata={'last_close': 100.0},
    )


def test_send_alert_success_and_failure(monkeypatch):
    sent = {'msg': None}

    import src.infrastructure.notifications.telegram_notifier as mod

    def fake_send_telegram(msg):
        sent['msg'] = msg

    monkeypatch.setattr(mod, 'send_telegram', fake_send_telegram)

    notifier = TelegramNotifier()
    assert notifier.send_alert('hello world') is True
    assert sent['msg'] == 'hello world'

    def boom(msg):
        raise RuntimeError('fail')

    monkeypatch.setattr(mod, 'send_telegram', boom)
    assert notifier.send_alert('x') is False


def test_send_analysis_results_and_format(monkeypatch):
    sent = {'msg': None}
    import src.infrastructure.notifications.telegram_notifier as mod
    monkeypatch.setattr(mod, 'send_telegram', lambda m: sent.__setitem__('msg', m))

    notifier = TelegramNotifier()
    a = make_result('AAA.NS', buy=True)
    b = make_result('BBB.NS', buy=False)
    ok = notifier.send_analysis_results([a, b])
    assert ok is True
    assert 'AAA.NS' in sent['msg'] and 'BBB.NS' not in sent['msg']


def test_is_available_and_test_connection(monkeypatch):
    # Make settings have tokens
    import config.settings as settings
    monkeypatch.setattr(settings, 'TELEGRAM_BOT_TOKEN', 'token', raising=False)
    monkeypatch.setattr(settings, 'TELEGRAM_CHAT_ID', 'chat', raising=False)

    notifier = TelegramNotifier()
    assert notifier.is_available() is True

    # Connection test should call send_alert
    called = {'n': 0}
    monkeypatch.setattr(TelegramNotifier, 'send_alert', lambda self, m: called.__setitem__('n', called['n'] + 1) or True)
    assert notifier.test_connection() is True
    assert called['n'] == 1

    # Without tokens
    monkeypatch.setattr(settings, 'TELEGRAM_BOT_TOKEN', '', raising=False)
    monkeypatch.setattr(settings, 'TELEGRAM_CHAT_ID', '', raising=False)
    assert notifier.is_available() is False
