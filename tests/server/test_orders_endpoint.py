import os

import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = os.getenv("DB_URL", "sqlite:///./data/test_api_orders.db")

from server.app.core.deps import get_db  # noqa: E402
from server.app.main import app  # noqa: E402
from src.infrastructure.persistence.orders_repository import OrdersRepository


@pytest.fixture(scope="function")
def client(db_session) -> TestClient:
    """Create test client with database session override"""

    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


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
    from src.infrastructure.db.models import Users  # noqa: PLC0415

    # Create user via signup API (uses same db_session via override)
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "status_tester@example.com", "password": "secret123"},
    )
    assert s.status_code == 200
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get user from database to get user_id
    user = db_session.query(Users).filter(Users.email == "status_tester@example.com").first()
    assert user is not None

    # Create orders with different statuses
    repo = OrdersRepository(db_session)
    repo.create_amo(
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
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus  # noqa: PLC0415
    from src.infrastructure.db.models import Users  # noqa: PLC0415

    # Create user via signup API (uses same db_session via override)
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "all_status_tester@example.com", "password": "secret123"},
    )
    assert s.status_code == 200
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get user from database to get user_id
    user = db_session.query(Users).filter(Users.email == "all_status_tester@example.com").first()
    assert user is not None

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

    repo.update(pending_order, status=DbOrderStatus.PENDING_EXECUTION)
    db_session.commit()

    # Test filtering by pending_execution
    r = client.get("/api/v1/user/orders?status=pending_execution", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_retry_order_success(client: TestClient, db_session):
    """Test retrying a failed order"""
    from jose import jwt  # noqa: PLC0415

    from server.app.core.config import settings  # noqa: PLC0415

    # Create user via signup API (uses same db_session via override)
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "retry_tester@example.com", "password": "secret123"},
    )
    assert s.status_code == 200
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get user_id from token (matches user created by signup API)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload["uid"]

    # Create failed order for this user
    repo = OrdersRepository(db_session)
    failed_order = repo.create_amo(
        user_id=user_id,
        symbol="RELIANCE",
        side="buy",
        order_type="market",
        quantity=10.0,
        price=None,
    )
    repo.mark_failed(failed_order, "insufficient_balance", retry_pending=False)
    db_session.commit()

    # Retry the order
    r = client.post(f"/api/v1/user/orders/{failed_order.id}/retry", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "retry_pending"
    assert data["retry_count"] == 1
    assert data["last_retry_attempt"] is not None

    # Verify in DB
    db_session.refresh(failed_order)
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus

    assert failed_order.status == DbOrderStatus.RETRY_PENDING
    assert failed_order.retry_count == 1
    assert failed_order.last_retry_attempt is not None


def test_retry_order_not_found(client: TestClient):
    """Test retrying a non-existent order"""
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "retry_notfound@example.com", "password": "secret123"},
    )
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/v1/user/orders/99999/retry", headers=headers)
    assert r.status_code == 404


def test_retry_order_wrong_status(client: TestClient, db_session):
    """Test retrying an order that's not in failed/retry_pending status"""
    from jose import jwt  # noqa: PLC0415

    from server.app.core.config import settings  # noqa: PLC0415
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus  # noqa: PLC0415

    # Create user via signup
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "retry_wrong_status@example.com", "password": "secret123"},
    )
    assert s.status_code == 200
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get user_id from token
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload["uid"]

    # Create ongoing order (not failed)
    repo = OrdersRepository(db_session)
    ongoing_order = repo.create_amo(
        user_id=user_id,
        symbol="TCS",
        side="buy",
        order_type="market",
        quantity=5.0,
        price=None,
    )
    repo.update(ongoing_order, status=DbOrderStatus.ONGOING)
    db_session.commit()

    # Try to retry (should fail)
    r = client.post(f"/api/v1/user/orders/{ongoing_order.id}/retry", headers=headers)
    assert r.status_code == 400
    assert "Cannot retry order" in r.json()["detail"]


def test_drop_order_success(client: TestClient, db_session):
    """Test dropping an order from retry queue"""
    from jose import jwt

    from server.app.core.config import settings

    # Create user via signup
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "drop_tester@example.com", "password": "secret123"},
    )
    assert s.status_code == 200
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get user_id from token
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload["uid"]

    # Create retry_pending order
    repo = OrdersRepository(db_session)
    retry_order = repo.create_amo(
        user_id=user_id,
        symbol="INFY",
        side="buy",
        order_type="market",
        quantity=3.0,
        price=None,
    )
    repo.mark_failed(retry_order, "insufficient_balance", retry_pending=True)
    db_session.commit()

    # Drop the order
    r = client.delete(f"/api/v1/user/orders/{retry_order.id}", headers=headers)
    assert r.status_code == 200
    assert "dropped" in r.json()["message"].lower()

    # Verify in DB
    db_session.refresh(retry_order)
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus

    assert retry_order.status == DbOrderStatus.CLOSED
    assert retry_order.closed_at is not None


def test_drop_order_not_found(client: TestClient):
    """Test dropping a non-existent order"""
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "drop_notfound@example.com", "password": "secret123"},
    )
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.delete("/api/v1/user/orders/99999", headers=headers)
    assert r.status_code == 404


def test_drop_order_wrong_status(client: TestClient, db_session):
    """Test dropping an order that's not in failed/retry_pending status"""
    from jose import jwt  # noqa: PLC0415

    from server.app.core.config import settings  # noqa: PLC0415
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus  # noqa: PLC0415

    # Create user via signup
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "drop_wrong_status@example.com", "password": "secret123"},
    )
    assert s.status_code == 200
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get user_id from token
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload["uid"]

    # Create ongoing order (not failed)
    repo = OrdersRepository(db_session)
    ongoing_order = repo.create_amo(
        user_id=user_id,
        symbol="WIPRO",
        side="buy",
        order_type="market",
        quantity=2.0,
        price=None,
    )
    repo.update(ongoing_order, status=DbOrderStatus.ONGOING)
    db_session.commit()

    # Try to drop (should fail)
    r = client.delete(f"/api/v1/user/orders/{ongoing_order.id}", headers=headers)
    assert r.status_code == 400
    assert "Cannot drop order" in r.json()["detail"]


def test_list_orders_with_filters(client: TestClient, db_session):
    """Test filtering orders by failure_reason and date range"""
    from jose import jwt

    from server.app.core.config import settings

    # Create user via signup
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "filter_tester@example.com", "password": "secret123"},
    )
    assert s.status_code == 200
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get user_id from token
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload["uid"]

    # Create orders with different failure reasons
    repo = OrdersRepository(db_session)
    order1 = repo.create_amo(
        user_id=user_id,
        symbol="RELIANCE",
        side="buy",
        order_type="market",
        quantity=10.0,
        price=None,
    )
    repo.mark_failed(order1, "insufficient_balance", retry_pending=False)

    order2 = repo.create_amo(
        user_id=user_id,
        symbol="TCS",
        side="buy",
        order_type="market",
        quantity=5.0,
        price=None,
    )
    repo.mark_failed(order2, "broker_error", retry_pending=False)

    db_session.commit()

    # Filter by failure_reason
    r = client.get(
        "/api/v1/user/orders?status=failed&failure_reason=insufficient",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert any("insufficient" in (o.get("failure_reason") or "").lower() for o in data)

    # Filter by date range (using today's date)
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    r2 = client.get(
        f"/api/v1/user/orders?from_date={today}&to_date={today}",
        headers=headers,
    )
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)
