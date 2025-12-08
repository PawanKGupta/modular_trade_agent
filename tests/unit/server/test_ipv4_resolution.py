"""
Tests for IPv4-only DNS resolution override in FastAPI server bootstrap.
"""

import logging
import socket

from server.app import main


def test_main_ipv4_getaddrinfo_forces_af_inet(monkeypatch):
    """Ensure server-level getaddrinfo override forces IPv4 resolution."""
    calls = []

    def fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        calls.append(family)
        return [("addr", socket.AF_INET)]

    # Replace the stored original with our fake and call the wrapper directly
    monkeypatch.setattr(main, "_original_getaddrinfo", fake_getaddrinfo)
    monkeypatch.setenv("FORCE_IPV4", "1")

    result = main._ipv4_getaddrinfo("gw-napi.kotaksecurities.com", 80)

    assert calls == [socket.AF_INET]
    assert result[0][1] == socket.AF_INET


def test_broker_ipv4_health_check_warns_on_failure(monkeypatch, caplog):
    """Health check should log a warning and return False on failure."""
    caplog.set_level(logging.WARNING)

    def fake_create_connection(*args, **kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(main.socket, "create_connection", fake_create_connection)
    monkeypatch.setenv("FORCE_IPV4", "1")

    ok = main._check_broker_ipv4_connectivity()

    assert ok is False
    assert any(
        "IPv4 connectivity check to broker host failed" in rec.message for rec in caplog.records
    )
