from fastapi.testclient import TestClient

from server.app import main


def test_health_endpoint_returns_ok(monkeypatch):
    # Avoid running heavy startup/shutdown hooks during this smoke test
    startup_handlers = list(main.app.router.on_startup)
    shutdown_handlers = list(main.app.router.on_shutdown)
    main.app.router.on_startup.clear()
    main.app.router.on_shutdown.clear()

    try:
        with TestClient(main.app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            assert response.headers.get("X-Request-ID")
    finally:
        main.app.router.on_startup.extend(startup_handlers)
        main.app.router.on_shutdown.extend(shutdown_handlers)
