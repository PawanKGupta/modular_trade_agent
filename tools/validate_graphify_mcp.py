"""Sanity check for Graphify MCP bootstrap and graph artifacts.

Run before enabling Graphify MCP in Cursor or after rebuilding ``graphify-out/``.

Usage (repo root)::

    .\\.venv-graphify\\Scripts\\python.exe tools\\validate_graphify_mcp.py

Prints ``Result: PASS`` when the graph file exists and can be loaded.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Return the repository root (parent of ``tools/``)."""
    return Path(__file__).resolve().parent.parent


def main() -> int:
    """Validate graph artifacts and optional graphify import."""
    root = _repo_root()
    graph_path = root / "graphify-out" / "graph.json"
    report_path = root / "graphify-out" / "GRAPH_REPORT.md"
    errors: list[str] = []

    if not graph_path.is_file():
        errors.append(f"Missing graph: {graph_path}")
    if not report_path.is_file():
        errors.append(f"Missing report: {report_path}")

    if importlib.util.find_spec("graphify") is None:
        errors.append(
            "graphifyy not installed in this Python env. "
            'Use .venv-graphify: pip install "graphifyy[mcp]"'
        )

    if errors:
        for message in errors:
            print(f"FAIL: {message}", file=sys.stderr)
        print("Result: FAIL")
        return 1

    data = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    links = data.get("links", data.get("edges", []))
    print(f"graph_stats: nodes={len(nodes)} links={len(links)}")
    print(f"graph_path: {graph_path}")
    print("Result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
