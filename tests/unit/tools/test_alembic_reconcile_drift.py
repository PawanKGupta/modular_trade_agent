"""Tests for tools/alembic_reconcile_drift.py"""

from unittest.mock import MagicMock, patch


def test_skips_when_no_db_url(monkeypatch):
    monkeypatch.delenv("DB_URL", raising=False)
    from tools import alembic_reconcile_drift as mod  # noqa: PLC0415

    assert mod.main() == 0


def test_skips_when_opt_out(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ALEMBIC_SKIP_DRIFT_RECONCILE", "1")
    from tools import alembic_reconcile_drift as mod  # noqa: PLC0415

    assert mod.main() == 0


def test_skips_when_users_missing(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite:///:memory:")
    monkeypatch.delenv("ALEMBIC_SKIP_DRIFT_RECONCILE", raising=False)

    engine = MagicMock()
    engine.dialect.name = "sqlite"
    engine.dispose = MagicMock()

    with (
        patch("tools.alembic_reconcile_drift.create_engine", return_value=engine),
        patch("tools.alembic_reconcile_drift.inspect") as insp_mock,
        patch.dict("os.environ", {"DB_URL": "sqlite:///:memory:"}, clear=False),
    ):
        insp_mock.return_value.get_table_names.return_value = []

        from tools import alembic_reconcile_drift as mod  # noqa: PLC0415

        assert mod.main() == 0
