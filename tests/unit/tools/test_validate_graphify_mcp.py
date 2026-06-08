"""Tests for tools/validate_graphify_mcp.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools import validate_graphify_mcp as mod


@pytest.mark.unit
def test_repo_root_is_parent_of_tools():
    root = mod._repo_root()
    assert (root / "tools" / "validate_graphify_mcp.py").is_file()


@pytest.mark.unit
def test_main_fails_when_graph_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(mod, "_repo_root", lambda: tmp_path)
    with patch.object(mod.importlib.util, "find_spec", return_value=object()):
        assert mod.main() == 1


@pytest.mark.unit
def test_main_fails_when_graphify_missing(tmp_path: Path, monkeypatch):
    graph_dir = tmp_path / "graphify-out"
    graph_dir.mkdir()
    (graph_dir / "graph.json").write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
    (graph_dir / "GRAPH_REPORT.md").write_text("# report", encoding="utf-8")
    monkeypatch.setattr(mod, "_repo_root", lambda: tmp_path)
    with patch.object(mod.importlib.util, "find_spec", return_value=None):
        assert mod.main() == 1


@pytest.mark.unit
def test_main_passes_with_valid_artifacts(tmp_path: Path, monkeypatch, capsys):
    graph_dir = tmp_path / "graphify-out"
    graph_dir.mkdir()
    (graph_dir / "graph.json").write_text(
        json.dumps({"nodes": [{"id": "a"}], "links": [{"source": "a", "target": "b"}]}),
        encoding="utf-8",
    )
    (graph_dir / "GRAPH_REPORT.md").write_text("# report", encoding="utf-8")
    monkeypatch.setattr(mod, "_repo_root", lambda: tmp_path)
    with patch.object(mod.importlib.util, "find_spec", return_value=object()):
        assert mod.main() == 0
    out = capsys.readouterr().out
    assert "graph_stats: nodes=1 links=1" in out
    assert "Result: PASS" in out
