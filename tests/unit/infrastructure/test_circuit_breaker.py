import time
import types

from src.infrastructure.resilience.circuit_breaker import CircuitBreaker, CircuitState, api_circuit_breaker


def test_circuit_breaker_states_and_reset(monkeypatch):
    # Simulate time progression
    now = [1000.0]
    monkeypatch.setattr(time, 'time', lambda: now[0])

    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=5.0, expected_exception=ValueError, name='TEST')

    calls = {'count': 0}

    def flaky():
        calls['count'] += 1
        if calls['count'] <= 2:
            raise ValueError('fail')
        return 'ok'

    # First failure moves count to 1, still CLOSED
    try:
        cb._call(flaky)
    except ValueError:
        pass
    assert cb.get_state() == CircuitState.CLOSED

    # Second failure opens the circuit
    try:
        cb._call(flaky)
    except ValueError:
        pass
    assert cb.get_state() == CircuitState.OPEN

    # While OPEN and before timeout, should fail fast
    try:
        cb._call(flaky)
    except Exception as e:
        assert "OPEN" in str(e)

    # Advance time to trigger HALF_OPEN
    now[0] += 6.0
    # Next call transitions to HALF_OPEN and succeeds, should reset to CLOSED
    out = cb._call(flaky)
    assert out == 'ok'
    assert cb.get_state() == CircuitState.CLOSED

    # Test manual reset
    cb.reset()
    assert cb.get_state() == CircuitState.CLOSED


def test_api_circuit_breaker_decorator(monkeypatch):
    # Make a function that fails first then succeeds
    state = {'n': 0}

    breaker = api_circuit_breaker(name='API-TEST', failure_threshold=1, recovery_timeout=0.0)

    @breaker
    def sometimes():
        state['n'] += 1
        if state['n'] == 1:
            raise Exception('boom')
        return 42

    # First call fails and opens, but recovery_timeout=0 allows immediate HALF_OPEN next call
    try:
        sometimes()
    except Exception:
        pass
    val = sometimes()
    assert val == 42
