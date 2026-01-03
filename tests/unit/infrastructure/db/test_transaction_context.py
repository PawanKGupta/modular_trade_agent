import pytest

from src.infrastructure.db.transaction import transaction


class _DummySession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_transaction_commits_on_success():
    session = _DummySession()

    with transaction(session) as context_session:
        assert context_session is session

    assert session.commits == 1
    assert session.rollbacks == 0


def test_transaction_rolls_back_on_exception():
    session = _DummySession()

    with pytest.raises(RuntimeError):
        with transaction(session):
            raise RuntimeError("boom")

    assert session.commits == 0
    assert session.rollbacks == 1
