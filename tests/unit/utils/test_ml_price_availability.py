"""Tests for ML price model path discovery."""

from __future__ import annotations

from utils.ml_price_availability import (
    discover_ml_price_target_path,
    ml_price_target_model_available,
    resolve_ml_price_target_path_str,
)


def test_discover_canonical_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    models = tmp_path / "models"
    models.mkdir()
    target = models / "price_model_random_forest.pkl"
    target.write_bytes(b"x")

    found = discover_ml_price_target_path()
    assert found == target.resolve()
    assert ml_price_target_model_available()


def test_discover_glob_when_canonical_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    models = tmp_path / "models"
    models.mkdir()
    alt = models / "price_model_random_forest_actual_pnl_pct.pkl"
    alt.write_bytes(b"x")

    found = discover_ml_price_target_path()
    assert found == alt.resolve()
    assert resolve_ml_price_target_path_str() == str(alt.resolve())


def test_unavailable_returns_default_path_string(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    (tmp_path / "models").mkdir()
    assert discover_ml_price_target_path() is None
    assert not ml_price_target_model_available()
    assert "price_model_random_forest.pkl" in resolve_ml_price_target_path_str()
