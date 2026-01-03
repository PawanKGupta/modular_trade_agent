import importlib
import os

import pytest

from src.infrastructure.db import session as db_session


def _reload_session_with_url(monkeypatch, url):
    original_url = os.environ.get("DB_URL")
    if url is None:
        monkeypatch.delenv("DB_URL", raising=False)
    else:
        monkeypatch.setenv("DB_URL", url)
    importlib.reload(db_session)
    return original_url


def _restore_original_url(monkeypatch, original_url):
    if original_url is None:
        monkeypatch.delenv("DB_URL", raising=False)
    else:
        monkeypatch.setenv("DB_URL", original_url)
    importlib.reload(db_session)


def test_sqlite_flag_reflects_url(monkeypatch):
    original_url = _reload_session_with_url(monkeypatch, "sqlite:///tmp/test.db")
    try:
        assert db_session.is_sqlite
        assert not db_session.is_memory
    finally:
        _restore_original_url(monkeypatch, original_url)


def test_memory_flag_reflects_in_memory(monkeypatch):
    original_url = _reload_session_with_url(monkeypatch, "sqlite:///:memory:")
    try:
        assert db_session.is_sqlite
        assert db_session.is_memory
    finally:
        _restore_original_url(monkeypatch, original_url)


def test_production_paths_are_rejected(monkeypatch, tmp_path):
    project_root = tmp_path / "proj"
    (project_root / "data").mkdir(parents=True)
    fake_path = project_root / "data" / "app.db"
    fake_path.write_text("")

    original_url = os.environ.get("DB_URL")
    monkeypatch.chdir(project_root)
    monkeypatch.setenv("DB_URL", f"sqlite:///{fake_path.as_posix()}")

    with pytest.raises(RuntimeError):
        importlib.reload(db_session)

    _restore_original_url(monkeypatch, original_url)
