from types import SimpleNamespace

from server.app.routers import targets
from src.infrastructure.db.models import UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


def test_list_targets_returns_empty_list():
    """Test that list_targets returns empty list (placeholder implementation)"""
    db_marker = object()
    user = DummyUser(id=42, email="test@example.com")

    result = targets.list_targets(db=db_marker, current=user)

    assert result == []
    assert isinstance(result, list)


def test_list_targets_handles_different_users():
    """Test that list_targets works with different user objects"""
    db_marker = object()
    user1 = DummyUser(id=1, email="user1@example.com")
    user2 = DummyUser(id=2, email="user2@example.com", role=UserRole.ADMIN)

    result1 = targets.list_targets(db=db_marker, current=user1)
    result2 = targets.list_targets(db=db_marker, current=user2)

    assert result1 == []
    assert result2 == []
