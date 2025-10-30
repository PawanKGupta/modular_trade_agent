import time
import random
import pytest

from src.infrastructure.resilience.retry_handler import exponential_backoff_retry, api_retry


def test_exponential_backoff_retry_success_after_retries(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, 'sleep', lambda s: sleeps.append(s))
    monkeypatch.setattr(random, 'random', lambda: 0.5)

    state = {'n': 0}

    @exponential_backoff_retry(max_retries=3, base_delay=0.1, max_delay=1.0, backoff_multiplier=2.0, jitter=True)
    def flaky():
        state['n'] += 1
        if state['n'] < 3:
            raise Exception('temp')
        return 'ok'

    out = flaky()
    assert out == 'ok'
    # Should have slept twice (between two failures)
    assert len(sleeps) == 2
    assert all(s >= 0 for s in sleeps)


def test_exponential_backoff_retry_exhaust(monkeypatch):
    monkeypatch.setattr(time, 'sleep', lambda s: None)
    monkeypatch.setattr(random, 'random', lambda: 0.5)

    @exponential_backoff_retry(max_retries=2, base_delay=0.01)
    def always_fail():
        raise ValueError('nope')

    with pytest.raises(ValueError):
        always_fail()


def test_api_retry_defaults(monkeypatch):
    monkeypatch.setattr(time, 'sleep', lambda s: None)

    calls = {'n': 0}

    @api_retry
    def maybe():
        calls['n'] += 1
        if calls['n'] < 2:
            raise Exception('boom')
        return 1

    assert maybe() == 1
