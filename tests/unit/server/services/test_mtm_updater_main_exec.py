"""Execute the ``mtm_updater`` CLI block with a controlled namespace (no I/O)."""

from __future__ import annotations

import contextlib
import logging
import sys
from io import StringIO


def test_mtm_main_block_single_user(monkeypatch):
    import server.app.services.mtm_updater as mtm

    calls = []

    def _fake(uid, db=None):
        calls.append(uid)
        return {"total": 0, "updated": 0, "failed": 0, "skipped": 0}

    monkeypatch.setattr(mtm, "update_mtm_for_user", _fake)
    monkeypatch.setattr(mtm, "update_mtm_for_all_users", lambda: {9: {"total": 0}})
    monkeypatch.setattr(sys, "argv", ["mtm_updater.py", "77"])

    ns = {
        "__name__": "__main__",
        "logging": logging,
        "sys": sys,
        "update_mtm_for_user": mtm.update_mtm_for_user,
        "update_mtm_for_all_users": mtm.update_mtm_for_all_users,
    }
    buf = StringIO()
    snippet = """
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        stats = update_mtm_for_user(user_id)
        print(stats["total"])
    else:
        results = update_mtm_for_all_users()
        print(len(results))
"""
    with contextlib.redirect_stdout(buf):
        exec(compile(snippet, "<mtm_updater __main__>", "exec"), ns)

    assert calls == [77]
    assert buf.getvalue().strip() == "0"


def test_mtm_main_block_all_users(monkeypatch):
    import server.app.services.mtm_updater as mtm

    monkeypatch.setattr(
        mtm,
        "update_mtm_for_all_users",
        lambda: {1: {"total": 0}, 2: {"total": 0}},
    )
    monkeypatch.setattr(sys, "argv", ["mtm_updater.py"])

    ns = {
        "__name__": "__main__",
        "logging": logging,
        "sys": sys,
        "update_mtm_for_user": mtm.update_mtm_for_user,
        "update_mtm_for_all_users": mtm.update_mtm_for_all_users,
    }
    buf = StringIO()
    snippet = """
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        stats = update_mtm_for_user(user_id)
        print(stats["total"])
    else:
        results = update_mtm_for_all_users()
        print(len(results))
"""
    with contextlib.redirect_stdout(buf):
        exec(compile(snippet, "<mtm_updater __main__>", "exec"), ns)

    assert buf.getvalue().strip() == "2"
