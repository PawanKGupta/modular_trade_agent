from unittest.mock import Mock

import pytest

from src.infrastructure.db.transaction import transaction


class DummySession:
    def __init__(self) -> None:
        self.committed = 0
        self.rolled_back = 0
        self.closed = 0

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rolled_back += 1

    def close(self) -> None:
        self.closed += 1


def test_transaction_commits_and_closes(monkeypatch):
    session = DummySession()
    logger = Mock()
    monkeypatch.setattr("src.infrastructure.db.transaction.logger", logger)

    with transaction(session) as db_session:
        assert db_session is session

    assert session.committed == 1
    assert session.rolled_back == 0
    assert session.closed == 0
    logger.debug.assert_called_once()


def test_transaction_rolls_back_and_logs(monkeypatch):
    session = DummySession()
    logger = Mock()
    monkeypatch.setattr("src.infrastructure.db.transaction.logger", logger)

    with pytest.raises(RuntimeError):
        with transaction(session):
            raise RuntimeError("boom")

    assert session.committed == 0
    assert session.rolled_back == 1
    assert session.closed == 0
    logger.error.assert_called_once()
