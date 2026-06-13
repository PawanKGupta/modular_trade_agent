"""Reusable FastAPI Request mocks for router unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock


def mock_request(*, path: str = "/api/v1/test", csrf_token: str | None = None) -> MagicMock:
    """Build a minimal Request stand-in for direct handler calls in tests."""
    request = MagicMock()
    request.headers = {"X-Forwarded-For": "127.0.0.1"}
    if csrf_token:
        request.headers["X-CSRF-Token"] = csrf_token
    request.cookies = {"ta_csrf": csrf_token} if csrf_token else {}
    request.client = MagicMock(host="127.0.0.1")
    request.url = MagicMock(path=path)
    return request
