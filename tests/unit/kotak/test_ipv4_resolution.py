"""
Tests for IPv4-only DNS resolution overrides in Kotak auth.
"""

import socket

from modules.kotak_neo_auto_trader import auth


def test_auth_ipv4_getaddrinfo_forces_af_inet(monkeypatch):
    """Ensure auth-level getaddrinfo override forces IPv4 resolution."""
    calls = []

    def fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        calls.append(family)
        return [("addr", socket.AF_INET)]

    # Replace the stored original with our fake and call the wrapper directly
    monkeypatch.setattr(auth, "_original_getaddrinfo", fake_getaddrinfo)
    monkeypatch.setenv("FORCE_IPV4", "1")

    result = auth._ipv4_getaddrinfo("gw-napi.kotaksecurities.com", 443)

    assert calls == [socket.AF_INET]
    assert result[0][1] == socket.AF_INET
    assert auth.socket.getaddrinfo == auth._ipv4_getaddrinfo
