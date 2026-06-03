# ruff: noqa: PLC0415, E501
"""Cover SafeRotatingFileHandler and module-level Docker/rotation helpers in main."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest


def test_safe_rotating_file_handler_skips_rollover_when_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    from server.app.main import SafeRotatingFileHandler

    log_file = tmp_path / "app.log"
    h = SafeRotatingFileHandler(str(log_file), maxBytes=10, backupCount=2)
    SafeRotatingFileHandler._rotation_disabled = True
    try:
        h.emit(logging.makeLogRecord({"msg": "hello", "level": logging.INFO}))
        h.doRollover()
    finally:
        SafeRotatingFileHandler._rotation_disabled = False
        SafeRotatingFileHandler._rotation_warning_printed = False
        h.close()


def test_safe_rotating_file_handler_rollover_permission_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    from server.app.main import SafeRotatingFileHandler

    log_file = tmp_path / "roll.log"
    h = SafeRotatingFileHandler(str(log_file), maxBytes=5, backupCount=1)
    SafeRotatingFileHandler._rotation_disabled = False
    SafeRotatingFileHandler._rotation_warning_printed = False
    monkeypatch.setattr(SafeRotatingFileHandler, "_can_rotate", lambda self: True)

    def _boom(*_a, **_k):
        raise OSError("permission denied")

    monkeypatch.setattr(logging.handlers.RotatingFileHandler, "doRollover", _boom)
    try:
        h.doRollover()
        assert SafeRotatingFileHandler._rotation_disabled is True
    finally:
        SafeRotatingFileHandler._rotation_disabled = False
        SafeRotatingFileHandler._rotation_warning_printed = False
        h.close()


def test_main_module_is_docker_and_can_rotate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from server.app import main

    monkeypatch.delenv("DOCKER_CONTAINER", raising=False)
    monkeypatch.setattr(os.path, "exists", lambda p: str(p) == "/.dockerenv")
    assert main._is_docker_environment() is True

    monkeypatch.setattr(os.path, "exists", lambda p: False)
    monkeypatch.setattr(main, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(main, "_is_docker_environment", lambda: False)
    assert main._can_rotate_logs() is True


def test_main_module_detects_docker_via_cgroup(monkeypatch: pytest.MonkeyPatch):
    """``/.dockerenv`` absent but cgroup mentions docker (``main._is_docker_environment``)."""
    from server.app import main

    monkeypatch.delenv("DOCKER_CONTAINER", raising=False)

    def _exists(p):
        return str(p) == "/proc/self/cgroup"

    def _open(path, *a, **k):
        from io import StringIO

        assert str(path) == "/proc/self/cgroup"
        return StringIO("0::/docker/buildkit\n")

    monkeypatch.setattr(os.path, "exists", _exists)
    monkeypatch.setattr("builtins.open", _open)
    assert main._is_docker_environment() is True


def test_safe_rotating_handler_detects_docker_via_cgroup(monkeypatch: pytest.MonkeyPatch):
    from server.app.main import SafeRotatingFileHandler

    monkeypatch.delenv("DOCKER_CONTAINER", raising=False)

    def _exists(p):
        return str(p) == "/proc/self/cgroup"

    def _open(path, *a, **k):
        from io import StringIO

        return StringIO("1:name=systemd:/docker.slice\n")

    monkeypatch.setattr(os.path, "exists", _exists)
    monkeypatch.setattr("builtins.open", _open)
    assert SafeRotatingFileHandler._is_docker_environment() is True


def test_main_module_can_rotate_logs_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from server.app import main

    monkeypatch.setattr(main, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(main, "_is_docker_environment", lambda: False)

    def _fail_open(*_a, **_k):
        raise OSError("nope")

    monkeypatch.setattr("builtins.open", _fail_open)
    assert main._can_rotate_logs() is False


def test_configure_root_file_logging_skips_on_permission_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    """API must start when logs/ is not writable (bind mount UID mismatch)."""
    from server.app import main

    log_path = str(tmp_path / "server_api.log")
    monkeypatch.setattr(main, "log_path", log_path)
    monkeypatch.setattr(main, "_can_rotate_logs", lambda: False)

    def _deny_handler(*_a, **_k):
        raise PermissionError("Permission denied")

    monkeypatch.setattr(logging, "FileHandler", _deny_handler)
    before = len(logging.getLogger().handlers)
    main._configure_root_file_logging()
    assert len(logging.getLogger().handlers) == before
