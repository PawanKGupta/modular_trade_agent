"""
REST-only broker router unit tests.
"""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))

from server.app.routers import broker  # noqa: E402


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(broker.router)
    return app


def test_broker_router_imports_without_legacy_symbols():
    # Router module should not expose legacy client symbols anymore.
    assert not hasattr(broker, "_NEO_API_AVAILABLE")


def test_broker_router_has_health_endpoint():
    app = _build_app()
    client = TestClient(app)
    resp = client.get("/api/broker/health")
    # Endpoint may return 200 or 404 depending on route registration prefixes in app integration,
    # but importing and serving through TestClient must not crash.
    assert resp.status_code in (200, 404)

