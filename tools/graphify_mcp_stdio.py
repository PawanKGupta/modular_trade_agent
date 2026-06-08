"""Bootstrap Graphify MCP stdio server with a repo-root graph path.

Resolves ``graphify-out/graph.json`` from this file's location so Cursor MCP
works reliably on Windows without depending on the process cwd.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from graphify.serve import serve
except ImportError:
    serve = None  # type: ignore[misc, assignment]


def _repo_root() -> Path:
    """Return the repository root (parent of ``tools/``)."""
    return Path(__file__).resolve().parent.parent


def _graph_json_path() -> Path:
    """Return the expected Graphify graph artifact path."""
    return _repo_root() / "graphify-out" / "graph.json"


def main() -> None:
    """Start the Graphify MCP stdio server for the local knowledge graph."""
    graph_path = _graph_json_path()
    if serve is None:
        print(
            'graphifyy not installed. Use .venv-graphify: pip install "graphifyy[mcp]"',
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not graph_path.is_file():
        print(
            f"graphify-out/graph.json not found at {graph_path}.\n"
            "Run from repo root: .\\.venv-graphify\\Scripts\\graphify update .",
            file=sys.stderr,
        )
        raise SystemExit(1)

    serve(str(graph_path))


if __name__ == "__main__":
    main()
