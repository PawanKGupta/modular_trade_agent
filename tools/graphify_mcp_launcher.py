#!/usr/bin/env python3
"""Launch Graphify MCP stdio server using the repo-local .venv-graphify interpreter.

Cursor MCP config can use any system ``python3`` with this script as the sole
argument; it re-execs ``graphify_mcp_stdio.py`` under ``.venv-graphify`` so
Windows (``Scripts/python.exe``) and Linux (``bin/python``) both work.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _venv_python(repo_root: Path) -> Path | None:
    """Return the Graphify venv Python executable if present."""
    if sys.platform == "win32":
        candidates = [
            repo_root / ".venv-graphify" / "Scripts" / "python.exe",
            repo_root / ".venv-graphify" / "Scripts" / "python",
        ]
    else:
        candidates = [
            repo_root / ".venv-graphify" / "bin" / "python",
            repo_root / ".venv-graphify" / "bin" / "python3",
        ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def main() -> None:
    repo = _repo_root()
    venv_python = _venv_python(repo)
    target = repo / "tools" / "graphify_mcp_stdio.py"

    if venv_python is None:
        print(
            "Graphify venv not found. From repo root:\n"
            '  python3 -m venv .venv-graphify\n'
            '  .venv-graphify/bin/pip install "graphifyy[mcp]"\n'
            "  .venv-graphify/bin/graphify update .",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not target.is_file():
        print(f"Missing MCP bootstrap script: {target}", file=sys.stderr)
        raise SystemExit(1)

    os.execv(str(venv_python), [str(venv_python), str(target)])


if __name__ == "__main__":
    main()
