"""Tests for `src.infrastructure.db.transaction.transaction`."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.infrastructure.db.transaction import transaction


def test_transaction_commits_on_success():
    db = MagicMock()
    with transaction(db):
        pass
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_transaction_rollbacks_on_error():
    db = MagicMock()

    with pytest.raises(RuntimeError, match="boom"), transaction(db):
        raise RuntimeError("boom")

    db.rollback.assert_called_once()
