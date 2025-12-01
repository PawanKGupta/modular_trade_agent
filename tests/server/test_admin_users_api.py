import os

from fastapi.testclient import TestClient

os.environ["DB_URL"] = os.getenv("DB_URL", "sqlite:///./data/test_api_admin_users.db")

from server.app.main import app  # noqa: E402
from src.infrastructure.db.models import UserRole, Users  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402


def _signup(email: str, password: str = "secret123") -> tuple[TestClient, dict]:
    client = TestClient(app)
    s = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert s.status_code == 200, s.text
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def _promote_to_admin(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(Users).filter(Users.email == email).first()
        assert user is not None
        user.role = UserRole.ADMIN
        user.is_active = True
        db.commit()


def test_admin_create_and_update_user():
    client, admin_headers = _signup("admin_update@example.com")
    _promote_to_admin("admin_update@example.com")

    # create a normal user
    r = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={"email": "target@example.com", "password": "secret123", "name": "Target"},
    )
    assert r.status_code == 200, r.text
    user_id = r.json()["id"]

    # update with PATCH (role and is_active)
    u = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=admin_headers,
        json={"role": "admin", "is_active": True},
    )
    assert u.status_code == 200, u.text
    assert u.json()["role"] == "admin"
    assert u.json()["is_active"] is True

    # list should include both users
    lst = client.get("/api/v1/admin/users", headers=admin_headers)
    assert lst.status_code == 200
    emails = [x["email"] for x in lst.json()]
    assert "admin_update@example.com" in emails and "target@example.com" in emails
