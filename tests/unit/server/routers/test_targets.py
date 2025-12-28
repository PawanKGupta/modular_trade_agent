from types import SimpleNamespace
from unittest.mock import MagicMock

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
    """Test that list_targets returns empty list when no targets exist"""
    # Create a mock database session
    mock_db = MagicMock()
    # Mock the execute method to return an empty result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    user = DummyUser(id=42, email="test@example.com")

    result = targets.list_targets(db=mock_db, current=user)

    assert result == []
    assert isinstance(result, list)


def test_list_targets_handles_different_users():
    """Test that list_targets works with different user objects"""
    # Create a mock database session
    mock_db = MagicMock()
    # Mock the execute method to return an empty result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    user1 = DummyUser(id=1, email="user1@example.com")
    user2 = DummyUser(id=2, email="user2@example.com", role=UserRole.ADMIN)

    result1 = targets.list_targets(db=mock_db, current=user1)
    result2 = targets.list_targets(db=mock_db, current=user2)

    assert result1 == []
    assert result2 == []
