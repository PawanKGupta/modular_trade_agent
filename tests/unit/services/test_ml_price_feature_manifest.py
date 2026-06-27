"""
Unit tests for versioned price feature manifest train/serve pairing.
"""

# ruff: noqa: E402 -- project root on path before services imports

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from services.ml_price_feature_manifest import (  # noqa: E402
    ARTIFACT_KIND,
    PRICE_FEATURE_SCHEMA_VERSION,
    load_price_feature_manifest,
    price_feature_manifest_path,
    write_price_feature_manifest,
)


class TestPriceFeatureManifest:
    @pytest.fixture
    def tmp(self):
        d = Path(tempfile.mkdtemp())
        yield d
        shutil.rmtree(d, ignore_errors=True)

    def test_roundtrip_manifest(self, tmp):
        model_path = tmp / "price_model_random_forest.pkl"
        model_path.write_bytes(b"dummy")

        out = write_price_feature_manifest(model_path, ["rsi_10", "volume_ratio", "day_of_week"])
        assert out == price_feature_manifest_path(model_path)

        loaded = load_price_feature_manifest(model_path)
        assert loaded is not None
        assert loaded["feature_schema_version"] == PRICE_FEATURE_SCHEMA_VERSION
        assert loaded["feature_names"] == ["rsi_10", "volume_ratio", "day_of_week"]

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["artifact"] == ARTIFACT_KIND
        # price manifest must NOT contain label_classes (it's a regressor)
        assert "label_classes" not in data

    def test_load_missing_returns_none(self, tmp):
        assert load_price_feature_manifest(tmp / "missing.pkl") is None

    def test_load_rejects_wrong_artifact_kind(self, tmp):
        model_path = tmp / "x.pkl"
        model_path.touch()
        path = price_feature_manifest_path(model_path)
        path.write_text(
            json.dumps(
                {
                    "artifact": "modular_trade_agent.verdict_features",
                    "feature_schema_version": PRICE_FEATURE_SCHEMA_VERSION,
                    "feature_names": ["a"],
                }
            ),
            encoding="utf-8",
        )
        assert load_price_feature_manifest(model_path) is None

    def test_load_rejects_unknown_schema_version(self, tmp):
        model_path = tmp / "x.pkl"
        model_path.touch()
        path = price_feature_manifest_path(model_path)
        path.write_text(
            json.dumps(
                {
                    "artifact": ARTIFACT_KIND,
                    "feature_schema_version": 999,
                    "feature_names": ["a"],
                }
            ),
            encoding="utf-8",
        )
        assert load_price_feature_manifest(model_path) is None

    def test_load_rejects_empty_feature_names(self, tmp):
        model_path = tmp / "x.pkl"
        model_path.touch()
        path = price_feature_manifest_path(model_path)
        path.write_text(
            json.dumps(
                {
                    "artifact": ARTIFACT_KIND,
                    "feature_schema_version": PRICE_FEATURE_SCHEMA_VERSION,
                    "feature_names": [],
                }
            ),
            encoding="utf-8",
        )
        assert load_price_feature_manifest(model_path) is None

    def test_write_raises_on_empty_names(self, tmp):
        model_path = tmp / "m.pkl"
        model_path.touch()
        with pytest.raises(ValueError, match="non-empty"):
            write_price_feature_manifest(model_path, [])

    def test_manifest_path_naming(self, tmp):
        model_path = tmp / "price_model_random_forest.pkl"
        assert (
            price_feature_manifest_path(model_path).name
            == "price_model_random_forest.price_features.json"
        )
