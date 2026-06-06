"""Branch coverage for IPv4 broker connectivity helpers in ``server.app.main``."""

from __future__ import annotations

import socket

import pytest


def test_ipv4_getaddrinfo_passthrough_when_force_disabled(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    monkeypatch.setattr(main, "_FORCE_IPV4", False)
    sentinel = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.1", 443))]

    def _fake(host, port, family=0, type=0, proto=0, flags=0):
        assert host == "gw-napi.kotaksecurities.com"
        assert port == 443
        return list(sentinel)

    monkeypatch.setattr(main, "_original_getaddrinfo", _fake)
    out = main._ipv4_getaddrinfo("gw-napi.kotaksecurities.com", 443)
    assert out == sentinel


def test_check_broker_ipv4_connectivity_short_circuits_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app import main

    monkeypatch.setattr(main, "_FORCE_IPV4", False)
    assert main._check_broker_ipv4_connectivity() is True


def test_check_broker_ipv4_connectivity_failure_warns(monkeypatch: pytest.MonkeyPatch, caplog):
    from server.app import main

    monkeypatch.setattr(main, "_FORCE_IPV4", True)

    def _boom(*_a, **_k):
        raise OSError("unreachable")

    monkeypatch.setattr(main.socket, "create_connection", _boom)
    assert main._check_broker_ipv4_connectivity() is False
    assert any("IPv4 connectivity check" in r.getMessage() for r in caplog.records)


def test_ipv4_getaddrinfo_forces_inet_for_broker_host(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    monkeypatch.setattr(main, "_FORCE_IPV4", True)
    captured: dict = {}

    def _spy(host, port, family=0, type=0, proto=0, flags=0):
        captured["family"] = family
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(main, "_original_getaddrinfo", _spy)
    main._ipv4_getaddrinfo("gw-napi.kotaksecurities.com", 443)
    assert captured["family"] == socket.AF_INET
