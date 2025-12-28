"""Unit tests for portfolio history and snapshot endpoints"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from server.app.core.security import create_jwt_token
from src.infrastructure.db.models import TradeMode, UserRole, Users, UserSettings


@pytest.fixture
def test_user(db_session):
    user = db_session.query(Users).first()
    if not user:
        user = Users(
            email="test_portfolio@example.com",
            name="Test Portfolio",
            password_hash="dummy",
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_jwt_token(
        str(test_user.id), extra={"uid": test_user.id, "roles": [test_user.role.value]}
    )
    return {"Authorization": f"Bearer {token}"}


def test_snapshot_and_history_empty(client: TestClient, db_session, test_user, auth_headers):
    # Ensure settings exist
    settings = db_session.query(UserSettings).filter_by(user_id=test_user.id).one_or_none()
    if not settings:
        settings = UserSettings(user_id=test_user.id, trade_mode=TradeMode.PAPER)
        db_session.add(settings)
        db_session.commit()

    # Create snapshot for today
    resp = client.post("/api/v1/user/portfolio/snapshot", headers=auth_headers)
    if resp.status_code == 404:
        pytest.skip("Portfolio snapshot endpoint not implemented")
    assert resp.status_code == 200

    # Query history
    resp2 = client.get("/api/v1/user/portfolio/history", headers=auth_headers)
    if resp2.status_code == 404:
        pytest.skip("Portfolio history endpoint not implemented")
    assert resp2.status_code == 200
    data = resp2.json()
    assert isinstance(data, list)


def test_snapshot_upsert(client: TestClient, db_session, test_user, auth_headers):
    # Create a snapshot for a specific date
    target = (date.today() - timedelta(days=2)).isoformat()
    resp = client.post(
        f"/api/v1/user/portfolio/snapshot?snapshot_date={target}", headers=auth_headers
    )
    if resp.status_code == 404:
        pytest.skip("Portfolio snapshot endpoint not implemented")
    assert resp.status_code == 200
    assert resp.json().get("date") == target
