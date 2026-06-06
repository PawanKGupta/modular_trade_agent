"""Coverage for `get_session` generator lifecycle (commit/rollback/close paths)."""

from __future__ import annotations

import pytest

from src.infrastructure.db import session as db_session


def test_get_session_commit_failure_after_yield(monkeypatch):
    """Second phase commit raises; outer handler re-raises after rollback attempt."""

    class _Sess:
        def __init__(self):
            self.commits = 0

        def execute(self, *a, **k):
            return None

        def rollback(self):
            return None

        def commit(self):
            self.commits += 1
            if self.commits == 1:
                raise RuntimeError("commit failed")

        def close(self):
            return None

    monkeypatch.setattr(db_session, "SessionLocal", _Sess)
    gen = db_session.get_session()
    next(gen)
    with pytest.raises(RuntimeError, match="commit failed"):
        next(gen)


def test_get_session_consumer_exception_triggers_rollback(monkeypatch):
    class _Sess:
        def execute(self, *a, **k):
            return None

        def rollback(self):
            return None

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(db_session, "SessionLocal", _Sess)
    gen = db_session.get_session()
    next(gen)
    with pytest.raises(ValueError, match="user"):
        gen.throw(ValueError("user"))


def test_get_session_initial_execute_raises_then_yield(monkeypatch):
    class _Sess:
        def execute(self, *a, **k):
            raise ConnectionError("bad conn")

        def rollback(self):
            return None

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(db_session, "SessionLocal", _Sess)
    gen = db_session.get_session()
    db = next(gen)
    assert isinstance(db, _Sess)
    gen.close()


def test_get_session_commit_rollback_also_raises(monkeypatch):
    class _Sess:
        def execute(self, *a, **k):
            return None

        def rollback(self):
            raise RuntimeError("rollback1")

        def commit(self):
            raise RuntimeError("commit bad")

        def close(self):
            return None

    monkeypatch.setattr(db_session, "SessionLocal", _Sess)
    gen = db_session.get_session()
    next(gen)
    with pytest.raises(RuntimeError, match="commit bad"):
        next(gen)


def test_get_session_outer_rollback_raises(monkeypatch):
    class _Sess:
        def execute(self, *a, **k):
            return None

        def rollback(self):
            if not getattr(self, "_second", False):
                self._second = True
                raise RuntimeError("rb1")

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(db_session, "SessionLocal", _Sess)
    gen = db_session.get_session()
    next(gen)
    with pytest.raises(ValueError):
        gen.throw(ValueError("x"))


def test_get_session_close_raises_swallowed(monkeypatch):
    class _Sess:
        def execute(self, *a, **k):
            return None

        def rollback(self):
            return None

        def commit(self):
            return None

        def close(self):
            raise RuntimeError("close broken")

    monkeypatch.setattr(db_session, "SessionLocal", _Sess)
    gen = db_session.get_session()
    next(gen)
    try:
        next(gen)
    except StopIteration:
        pass
