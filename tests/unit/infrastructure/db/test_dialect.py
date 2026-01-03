from types import SimpleNamespace

from sqlalchemy.dialects import postgresql, sqlite

from src.infrastructure.db import dialect as db_dialect


def _session_with_dialect(dialect=None, url=""):
    bind = SimpleNamespace(url=url)
    if dialect is not None:
        bind = SimpleNamespace(dialect=dialect, url=url)
    return SimpleNamespace(bind=bind)


def test_is_postgresql_detects_postgresql_dialect():
    session = _session_with_dialect(dialect=postgresql.dialect(), url="postgresql://example")

    assert db_dialect.is_postgresql(session) is True


def test_is_postgresql_ignores_other_dialect():
    session = _session_with_dialect(dialect=sqlite.dialect(), url="postgresql://example")

    assert db_dialect.is_postgresql(session) is False


def test_is_postgresql_falls_back_to_url_when_dialect_missing():
    session = _session_with_dialect(dialect=None, url="postgresql://legacy")

    assert db_dialect.is_postgresql(session) is True


def test_is_postgresql_returns_false_for_non_postgres_url():
    session = _session_with_dialect(dialect=None, url="mysql://example")

    assert db_dialect.is_postgresql(session) is False


def test_is_sqlite_detects_sqlite_dialect():
    session = _session_with_dialect(dialect=sqlite.dialect(), url="sqlite:///memory")

    assert db_dialect.is_sqlite(session) is True


def test_is_sqlite_returns_false_for_other_dialect():
    session = _session_with_dialect(dialect=postgresql.dialect(), url="sqlite:///memory")

    assert db_dialect.is_sqlite(session) is False


def test_is_sqlite_falls_back_to_url_when_dialect_missing():
    session = _session_with_dialect(dialect=None, url="sqlite:///tmp/test.db")

    assert db_dialect.is_sqlite(session) is True


def test_is_sqlite_returns_false_for_non_sqlite_url():
    session = _session_with_dialect(dialect=None, url="postgresql://example")

    assert db_dialect.is_sqlite(session) is False
