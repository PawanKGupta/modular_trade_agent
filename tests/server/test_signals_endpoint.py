import os
import sys

import pytest
from fastapi.testclient import TestClient


def setup_app():
    os.environ["DB_URL"] = "sqlite:///:memory:"
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.append(root)
    import src.infrastructure.db.models  # noqa
    from src.infrastructure.db.base import Base
    from src.infrastructure.db.models import Signals
    from src.infrastructure.db.session import SessionLocal, engine

    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)
    # seed signals
    db = SessionLocal()
    db.add_all(
        [
            Signals(symbol="TCS", rsi10=25.1, ema9=100.0, ema200=90.0, distance_to_ema9=5.0),
            Signals(symbol="INFY", rsi10=28.3, ema9=210.0, ema200=205.0, distance_to_ema9=3.0),
        ]
    )
    db.commit()
    db.close()
    from server.app.main import app

    return TestClient(app)


@pytest.mark.unit
def test_buying_zone_returns_seeded_rows():
    client = setup_app()
    # need auth token: create user and login
    import random

    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": f"s{random.randint(1, 1_000_000)}@example.com", "password": "Secret123"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/signals/buying-zone?limit=10", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list) and len(items) >= 2
    syms = {i["symbol"] for i in items}
    assert {"TCS", "INFY"} <= syms
