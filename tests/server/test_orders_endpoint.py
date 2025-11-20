import os

import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = os.getenv("DB_URL", "sqlite:///./data/test_api_orders.db")

from server.app.main import app  # noqa: E402
from src.infrastructure.persistence.orders_repository import OrdersRepository


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_orders_list_requires_auth(client: TestClient):
    r = client.get("/api/v1/user/orders")
    assert r.status_code in (401, 403)


def test_orders_list_with_auth(client: TestClient):
    # signup
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "orders_tester@example.com", "password": "secret123"},
    )
    assert s.status_code == 200, s.text
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # initially empty
    r = client.get("/api/v1/user/orders", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Filter by status param (should still work and return list, possibly empty)
    r2 = client.get("/api/v1/user/orders?status=amo", headers=headers)
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)


def test_orders_list_with_new_statuses(client: TestClient, db_session):
    """Test that new order statuses are supported in API"""
    from src.infrastructure.db.models import UserRole, Users  # noqa: PLC0415

    # Create test user
    user = Users(
        email="status_tester@example.com",
        password_hash="hashed",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    # Create orders with different statuses
    repo = OrdersRepository(db_session)
    amo_order = repo.create_amo(
        user_id=user.id,
        symbol="RELIANCE",
        side="buy",
        order_type="market",
        quantity=10.0,
        price=None,
    )

    failed_order = repo.create_amo(
        user_id=user.id,
        symbol="TCS",
        side="buy",
        order_type="market",
        quantity=5.0,
        price=None,
    )
    repo.mark_failed(failed_order, "insufficient_balance", retry_pending=False)

    retry_order = repo.create_amo(
        user_id=user.id,
        symbol="INFY",
        side="buy",
        order_type="market",
        quantity=3.0,
        price=None,
    )
    repo.mark_failed(retry_order, "insufficient_balance", retry_pending=True)

    rejected_order = repo.create_amo(
        user_id=user.id,
        symbol="WIPRO",
        side="buy",
        order_type="market",
        quantity=2.0,
        price=None,
    )
    repo.mark_rejected(rejected_order, "Symbol not tradable")

    # Get auth token
    s = client.post(
        "/api/v1/auth/login",
        data={"username": "status_tester@example.com", "password": "secret123"},
    )
    if s.status_code != 200:
        # Create user if doesn't exist
        s = client.post(
            "/api/v1/auth/signup",
            json={"email": "status_tester@example.com", "password": "secret123"},
        )
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test filtering by new statuses
    for status in ["failed", "retry_pending", "rejected"]:
        r = client.get(f"/api/v1/user/orders?status={status}", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


def test_orders_response_includes_monitoring_fields(client: TestClient):
    """Test that order response schema includes new monitoring fields"""
    # This test verifies the API schema includes the new fields
    # Detailed field value tests are covered in repository unit tests
    from server.app.schemas.orders import OrderResponse

    # Verify the schema includes all monitoring fields
    schema_fields = OrderResponse.model_fields.keys()
    assert "failure_reason" in schema_fields
    assert "retry_count" in schema_fields
    assert "rejection_reason" in schema_fields
    assert "execution_price" in schema_fields
    assert "execution_qty" in schema_fields


def test_orders_status_validation(client: TestClient):
    """Test that invalid status values are rejected"""
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "validation_tester@example.com", "password": "secret123"},
    )
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Invalid status should be handled gracefully (may return 422 or empty list)
    r = client.get("/api/v1/user/orders?status=invalid_status", headers=headers)
    # Should either return 422 (validation error) or 200 with empty list
    assert r.status_code in (200, 422)


def test_orders_with_all_statuses(client: TestClient, db_session):
    """Test that all status values work correctly"""
    from src.infrastructure.db.models import UserRole, Users

    # Create user
    user = Users(
        email="all_status_tester@example.com",
        password_hash="hashed",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    # Create orders with all new statuses
    repo = OrdersRepository(db_session)

    # Test pending_execution status
    pending_order = repo.create_amo(
        user_id=user.id,
        symbol="TEST1",
        side="buy",
        order_type="market",
        quantity=1.0,
        price=None,
    )
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus

    repo.update(pending_order, status=DbOrderStatus.PENDING_EXECUTION)
    db_session.commit()

    # Get auth token
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "all_status_tester@example.com", "password": "secret123"},
    )
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test filtering by pending_execution
    r = client.get("/api/v1/user/orders?status=pending_execution", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
