"""Execution ``details`` must serialize to strict JSON (PostgreSQL rejects ``NaN``)."""

from __future__ import annotations

import json
import math

from src.application.services.individual_service_manager import _sanitize_for_postgres_json


def test_sanitize_for_postgres_json_replaces_non_finite_floats():
    raw = {
        "summary": {"price": float("nan")},
        "items": [{"x": float("inf")}, {"y": -0.0, "z": 1.25}],
        "nested": (float("-inf"),),
    }
    out = _sanitize_for_postgres_json(raw)
    assert out["summary"]["price"] is None
    assert out["items"][0]["x"] is None
    assert out["items"][1]["y"] == -0.0
    assert out["items"][1]["z"] == 1.25
    assert out["nested"][0] is None
    json.dumps(out, allow_nan=False)


def test_sanitize_for_postgres_json_passes_through_plain_types():
    assert _sanitize_for_postgres_json(None) is None
    assert _sanitize_for_postgres_json("ok") == "ok"
    assert _sanitize_for_postgres_json(3) == 3
    assert _sanitize_for_postgres_json(True) is True
    assert math.isclose(_sanitize_for_postgres_json(1.5), 1.5)
