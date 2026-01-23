from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.app.routers import notifications as notifications_router


class DummyNotification(SimpleNamespace):
    def __init__(self, **kwargs):
        defaults = {
            "id": 1,
            "user_id": 1,
            "type": "service",
            "level": "info",
            "title": "Test",
            "message": "payload",
            "read": False,
            "read_at": None,
            "created_at": datetime(2025, 1, 1, 12, 0),
            "telegram_sent": False,
            "email_sent": False,
            "in_app_delivered": True,
        }
        super().__init__(**{**defaults, **kwargs})


class _RepoFactory:
    def __init__(self, behavior):
        self.behavior = behavior

    def __call__(self, db):
        return self.behavior(db)


@pytest.fixture
def current_user():
    return SimpleNamespace(id=10)


def test_get_notifications_serializes(monkeypatch, current_user):
    notifications = [
        DummyNotification(id=i, user_id=current_user.id, read=(i % 2 == 0)) for i in range(1, 4)
    ]

    class FakeRepo:
        def __init__(self, db):
            self.db = db

        def list(self, **kwargs):
            assert kwargs["user_id"] == current_user.id
            assert kwargs["type"] == "service"
            assert kwargs["level"] == "info"
            assert kwargs["read"] is True
            assert kwargs["limit"] == 2
            return notifications

    monkeypatch.setattr(
        notifications_router,
        "NotificationRepository",
        _RepoFactory(lambda db: FakeRepo(db)),
    )

    result = notifications_router.get_notifications(
        type="service",
        level="info",
        read=True,
        limit=2,
        db=SimpleNamespace(),
        current_user=current_user,
    )

    assert len(result) == 3
    assert all(isinstance(item, dict) for item in result)
    assert result[0]["id"] == 1
    assert result[0]["read"] is False
    assert "created_at" in result[0]


def test_mark_notification_read_not_found(monkeypatch, current_user):
    class FakeRepo:
        def __init__(self, db):
            pass

        def get(self, notification_id):
            return None

    monkeypatch.setattr(
        notifications_router,
        "NotificationRepository",
        _RepoFactory(lambda db: FakeRepo(db)),
    )

    with pytest.raises(HTTPException) as excinfo:
        notifications_router.mark_notification_read(
            notification_id=123,
            db=SimpleNamespace(),
            current_user=current_user,
        )
    assert excinfo.value.status_code == 404


def test_mark_notification_read_forbidden(monkeypatch, current_user):
    class FakeRepo:
        def __init__(self, db):
            pass

        def get(self, notification_id):
            return DummyNotification(user_id=current_user.id + 1)

    monkeypatch.setattr(
        notifications_router,
        "NotificationRepository",
        _RepoFactory(lambda db: FakeRepo(db)),
    )

    with pytest.raises(HTTPException) as excinfo:
        notifications_router.mark_notification_read(
            notification_id=1,
            db=SimpleNamespace(),
            current_user=current_user,
        )
    assert excinfo.value.status_code == 403


def test_mark_all_notifications_read_returns_count(monkeypatch, current_user):
    class FakeRepo:
        def __init__(self, db):
            pass

        def mark_all_read(self, user_id):
            assert user_id == current_user.id
            return 5

    monkeypatch.setattr(
        notifications_router,
        "NotificationRepository",
        _RepoFactory(lambda db: FakeRepo(db)),
    )

    result = notifications_router.mark_all_notifications_read(
        db=SimpleNamespace(),
        current_user=current_user,
    )
    assert result == {"marked_read": 5}


def test_get_notification_count(monkeypatch, current_user):
    class FakeRepo:
        def __init__(self, db):
            pass

        def count_unread(self, user_id):
            return 7

    monkeypatch.setattr(
        notifications_router,
        "NotificationRepository",
        _RepoFactory(lambda db: FakeRepo(db)),
    )

    result = notifications_router.get_notification_count(
        db=SimpleNamespace(),
        current_user=current_user,
    )
    assert result == {"unread_count": 7}


def test_get_unread_notifications_serializes(monkeypatch, current_user):
    notifications = [
        DummyNotification(id=1, user_id=current_user.id, read=False, read_at=None),
        DummyNotification(id=2, user_id=current_user.id, read=False, read_at=datetime(2025, 1, 2, 12, 0)),
    ]

    class FakeRepo:
        def __init__(self, db):
            self.db = db

        def get_unread(self, *, user_id, limit):
            assert user_id == current_user.id
            assert limit == 2
            return notifications

    monkeypatch.setattr(
        notifications_router,
        "NotificationRepository",
        _RepoFactory(lambda db: FakeRepo(db)),
    )

    result = notifications_router.get_unread_notifications(
        limit=2,
        db=SimpleNamespace(),
        current_user=current_user,
    )

    assert result[0]["read_at"] is None
    assert result[1]["read_at"] == "2025-01-02T12:00:00"


def test_mark_notification_read_success(monkeypatch, current_user):
    updated = DummyNotification(
        id=1,
        user_id=current_user.id,
        read=True,
        read_at=datetime(2025, 1, 3, 9, 0),
    )

    class FakeRepo:
        def __init__(self, db):
            pass

        def get(self, notification_id):
            assert notification_id == 1
            return DummyNotification(id=1, user_id=current_user.id)

        def mark_read(self, notification_id):
            assert notification_id == 1
            return updated

    monkeypatch.setattr(
        notifications_router,
        "NotificationRepository",
        _RepoFactory(lambda db: FakeRepo(db)),
    )

    result = notifications_router.mark_notification_read(
        notification_id=1,
        db=SimpleNamespace(),
        current_user=current_user,
    )
    assert result == {"id": 1, "read": True, "read_at": "2025-01-03T09:00:00"}


@pytest.mark.parametrize(
    "callable_name, kwargs",
    [
        ("get_notifications", {"type": None, "level": None, "read": None, "limit": 1}),
        ("get_unread_notifications", {"limit": 1}),
        ("get_notification_count", {}),
        ("mark_notification_read", {"notification_id": 1}),
        ("mark_all_notifications_read", {}),
    ],
)
def test_notifications_router_500_paths(monkeypatch, current_user, callable_name: str, kwargs: dict):
    class FakeRepo:
        def __init__(self, db):
            pass

        def list(self, **_k):
            raise RuntimeError("boom")

        def get_unread(self, **_k):
            raise RuntimeError("boom")

        def count_unread(self, **_k):
            raise RuntimeError("boom")

        def get(self, _id):
            raise RuntimeError("boom")

        def mark_read(self, _id):
            raise RuntimeError("boom")

        def mark_all_read(self, **_k):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        notifications_router,
        "NotificationRepository",
        _RepoFactory(lambda db: FakeRepo(db)),
    )

    fn = getattr(notifications_router, callable_name)
    with pytest.raises(HTTPException) as excinfo:
        fn(db=SimpleNamespace(), current_user=current_user, **kwargs)
    assert excinfo.value.status_code == 500
