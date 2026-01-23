from types import SimpleNamespace

from sqlalchemy.dialects import postgresql, sqlite

from src.infrastructure.db import dialect as db_dialect


class _BindWithoutDialect:
    def __init__(self, url: str) -> None:
        self.url = url


class _FakeSession:
    def __init__(self, bind: object) -> None:
        self.bind = bind


def test_is_postgresql_detects_postgres_dialect():
    session = _FakeSession(bind=SimpleNamespace(dialect=postgresql.dialect()))

    assert db_dialect.is_postgresql(session) is True


def test_is_postgresql_fallbacks_to_url_when_dialect_missing():
    bind = _BindWithoutDialect("postgresql://user:pass@localhost/db")
    session = _FakeSession(bind=bind)

    assert db_dialect.is_postgresql(session) is True


def test_is_postgresql_returns_false_for_other_schemes():
    bind = _BindWithoutDialect("mysql://user@localhost/db")
    session = _FakeSession(bind=bind)

    assert db_dialect.is_postgresql(session) is False


def test_is_sqlite_detects_sqlite_dialect():
    session = _FakeSession(bind=SimpleNamespace(dialect=sqlite.dialect()))

    assert db_dialect.is_sqlite(session) is True


def test_is_sqlite_fallbacks_to_url_when_dialect_missing():
    bind = _BindWithoutDialect("sqlite:///tmp/sample.db")
    session = _FakeSession(bind=bind)

    assert db_dialect.is_sqlite(session) is True


def test_is_sqlite_returns_false_for_non_sqlite_urls():
    bind = _BindWithoutDialect("postgresql://user@localhost/db")
    session = _FakeSession(bind=bind)

    assert db_dialect.is_sqlite(session) is False
