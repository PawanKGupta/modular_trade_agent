"""
Unit tests for versioned verdict feature manifest train/serve pairing.
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

from services.ml_verdict_feature_manifest import (  # noqa: E402
    ARTIFACT_KIND,
    VERDICT_FEATURE_SCHEMA_VERSION,
    load_verdict_feature_manifest,
    verdict_feature_manifest_path,
    write_verdict_feature_manifest,
)


class TestVerdictFeatureManifest:
    """Manifest write/load and validation."""

    @pytest.fixture
    def tmp(self):
        d = Path(tempfile.mkdtemp())
        yield d
        shutil.rmtree(d, ignore_errors=True)

    def test_roundtrip_manifest(self, tmp):
        model_path = tmp / "verdict_model_random_forest.pkl"
        model_path.write_bytes(b"dummy")

        out = write_verdict_feature_manifest(model_path, ["a", "rsi_10", "z"])
        assert out == verdict_feature_manifest_path(model_path)

        loaded = load_verdict_feature_manifest(model_path)
        assert loaded is not None
        assert loaded["feature_schema_version"] == VERDICT_FEATURE_SCHEMA_VERSION
        assert loaded["feature_names"] == ["a", "rsi_10", "z"]

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["artifact"] == ARTIFACT_KIND

    def test_load_missing_returns_none(self, tmp):
        assert load_verdict_feature_manifest(tmp / "missing.pkl") is None

    def test_load_rejects_unknown_schema(self, tmp):
        model_path = tmp / "x.pkl"
        model_path.touch()
        path = verdict_feature_manifest_path(model_path)
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
        assert load_verdict_feature_manifest(model_path) is None
