from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from server.app.routers import admin
from src.infrastructure.db.models import UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
            is_active=kwargs.get("is_active", True),
        )


class DummyUserRepo:
    def __init__(self, db):
        self.db = db
        self.listed_active_only = None
        self._users = []
        self.created = None
        self.updated = None
        self.delete_called = False
        self.by_email = None
        self.by_id = None

    def list_users(self, active_only):
        self.listed_active_only = active_only
        return self._users

    def get_by_email(self, email):
        return self.by_email

    def create_user(self, **kwargs):
        self.created = kwargs
        return DummyUser(**kwargs)

    def get_by_id(self, user_id):
        return self.by_id

    def update_user(self, user, **kwargs):
        self.updated = (user, kwargs)
        for key, value in kwargs.items():
            if value is not None:
                setattr(user, key, value)
        return user


@pytest.fixture
def user_repo(monkeypatch):
    repo = DummyUserRepo(db=None)
    monkeypatch.setattr(admin, "UserRepository", lambda db: repo)
    return repo


@pytest.fixture
def settings_repo(monkeypatch):
    called = SimpleNamespace(ids=[])

    class DummySettingsRepo:
        def __init__(self, db):
            pass

        def ensure_default(self, user_id):
            called.ids.append(user_id)

    monkeypatch.setattr(admin, "SettingsRepository", DummySettingsRepo)
    return called


def test_list_users_transforms_response(user_repo):
    user_repo._users = [
        DummyUser(id=1, email="a@x.com", name="A", role=UserRole.ADMIN),
        DummyUser(id=2, email="b@x.com", name="B", role=UserRole.USER),
    ]
    result = admin.list_users(db=None)
    assert user_repo.listed_active_only is False
    assert result[0].role == "admin"
    assert result[1].email == "b@x.com"


def test_create_user_conflict(user_repo):
    user_repo.by_email = DummyUser()
    payload = admin.AdminUserCreate(email="dup@x.com", password="secret1", name="Dup", role="admin")
    with pytest.raises(HTTPException) as exc:
        admin.create_user(payload, db=None)
    assert exc.value.status_code == status.HTTP_409_CONFLICT


def test_create_user_success(user_repo, settings_repo):
    user_repo.by_email = None
    payload = admin.AdminUserCreate(email="new@x.com", password="secret1", name="New", role="user")
    resp = admin.create_user(payload, db=None)
    assert resp.email == "new@x.com"
    assert settings_repo.ids == [resp.id]


def test_update_user_not_found(user_repo):
    user_repo.by_id = None
    payload = admin.AdminUserUpdate(name=None, role=None, is_active=None)
    with pytest.raises(HTTPException) as exc:
        admin.update_user(1, payload, db=None)
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_update_user_success(user_repo):
    user_repo.by_id = DummyUser(name="Old")
    payload = admin.AdminUserUpdate(name="New", role="admin", is_active=False)
    resp = admin.update_user(1, payload, db=None)
    assert resp.name == "New"
    assert resp.role == "admin"
    assert user_repo.updated[1]["is_active"] is False


def test_delete_user_not_found(user_repo):
    user_repo.by_id = None
    with pytest.raises(HTTPException) as exc:
        admin.delete_user(1, db=None)
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_delete_last_admin_fails(user_repo):
    admin_user = DummyUser(role=UserRole.ADMIN)
    user_repo.by_id = admin_user
    user_repo._users = [admin_user]
    with pytest.raises(HTTPException) as exc:
        admin.delete_user(1, db=None)
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_delete_user_success(user_repo):
    target = DummyUser(role=UserRole.USER)
    user_repo.by_id = target
    user_repo._users = [DummyUser(role=UserRole.ADMIN, is_active=True), target]
    resp = admin.delete_user(1, db=None)
    assert resp == {"status": "ok"}
    assert user_repo.updated[1]["is_active"] is False


# Schedule manager helpers
class DummyScheduleManager:
    def __init__(self):
        self.schedules = []
        self.next = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)

    def get_all_schedules(self):
        return self.schedules

    def get_schedule(self, task_name):
        for s in self.schedules:
            if s.task_name == task_name:
                return s
        return None

    def calculate_next_execution(self, task_name):
        return self.next

    def validate_schedule(self, **kwargs):
        return True, ""


@pytest.fixture
def schedule_manager(monkeypatch):
    manager = DummyScheduleManager()

    def factory(*_, **__):
        return manager

    monkeypatch.setattr(admin, "ScheduleManager", factory)
    return manager


@pytest.fixture
def schedule_repo(monkeypatch):
    class DummyScheduleRepo:
        def __init__(self, db):
            self.created = None
            self.enabled = {}

        def create_or_update(self, **kwargs):
            self.created = kwargs
            return SimpleNamespace(
                id=1,
                task_name=kwargs["task_name"],
                schedule_time=SimpleNamespace(strftime=lambda _: "10:00"),
                enabled=kwargs["enabled"],
                is_hourly=kwargs["is_hourly"],
                is_continuous=kwargs["is_continuous"],
                end_time=None,
                schedule_type=kwargs["schedule_type"],
                description=kwargs["description"],
                updated_by=kwargs["updated_by"],
                updated_at=datetime.now(tz=UTC),
            )

        def update_enabled(self, task_name, enabled, updated_by):
            self.enabled[task_name] = (enabled, updated_by)
            return SimpleNamespace(
                id=1,
                task_name=task_name,
                schedule_time=SimpleNamespace(strftime=lambda _: "10:00"),
                enabled=enabled,
                is_hourly=False,
                is_continuous=False,
                end_time=None,
                schedule_type="daily",
                description="desc",
                updated_by=updated_by,
                updated_at=datetime.now(tz=UTC),
            )

    repo = DummyScheduleRepo(db=None)
    monkeypatch.setattr(admin, "ServiceScheduleRepository", lambda db: repo)
    return repo


def _schedule_item(task="task1", enabled=True):
    return SimpleNamespace(
        id=1,
        task_name=task,
        schedule_time=SimpleNamespace(strftime=lambda _: "09:00"),
        enabled=enabled,
        is_hourly=False,
        is_continuous=False,
        end_time=None,
        schedule_type="daily",
        description="desc",
        updated_by=1,
        updated_at=datetime.now(tz=UTC),
    )


def test_delete_user_handles_role_exception(user_repo):
    class WeirdRole:
        def __getattr__(self, item):
            raise AttributeError("boom")

        def __str__(self):
            return "ADMIN"

    target = DummyUser(role=WeirdRole())
    user_repo.by_id = target
    user_repo._users = [target, DummyUser(role=UserRole.ADMIN)]
    resp = admin.delete_user(1, db=None)
    assert resp == {"status": "ok"}


def test_list_service_schedules_success(schedule_manager):
    schedule_manager.schedules = [_schedule_item()]
    resp = admin.list_service_schedules(db=None, schedule_manager=schedule_manager)
    assert resp.schedules[0].task_name == "task1"


def test_list_service_schedules_error(schedule_manager, monkeypatch):
    def boom(*_, **__):
        raise RuntimeError("fail")

    schedule_manager.get_all_schedules = boom
    with pytest.raises(HTTPException) as exc:
        admin.list_service_schedules(db=None, schedule_manager=schedule_manager)
    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_get_service_schedule_not_found(schedule_manager):
    with pytest.raises(HTTPException) as exc:
        admin.get_service_schedule("missing", db=None, schedule_manager=schedule_manager)
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_get_service_schedule_success(schedule_manager):
    schedule_manager.schedules = [_schedule_item()]
    resp = admin.get_service_schedule("task1", db=None, schedule_manager=schedule_manager)
    assert resp.task_name == "task1"


def test_get_service_schedule_internal_error(schedule_manager):
    def boom(task_name):
        raise RuntimeError("db down")

    schedule_manager.schedules = [_schedule_item()]
    schedule_manager.get_schedule = boom
    with pytest.raises(HTTPException) as exc:
        admin.get_service_schedule("task1", db=None, schedule_manager=schedule_manager)
    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_update_schedule_invalid_time(schedule_manager):
    payload = admin.UpdateServiceScheduleRequest(
        schedule_time="bad",
        end_time=None,
        enabled=True,
        is_hourly=False,
        is_continuous=False,
        schedule_type="daily",
        description=None,
    )
    with pytest.raises(HTTPException) as exc:
        admin.update_service_schedule(
            "task",
            payload,
            db=None,
            current=DummyUser(),
            schedule_manager=schedule_manager,
        )
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_update_schedule_invalid_end_time(schedule_manager):
    payload = admin.UpdateServiceScheduleRequest(
        schedule_time="10:00",
        end_time="bad",
        enabled=True,
        is_hourly=False,
        is_continuous=False,
        schedule_type="daily",
        description=None,
    )
    with pytest.raises(HTTPException):
        admin.update_service_schedule(
            "task",
            payload,
            db=None,
            current=DummyUser(),
            schedule_manager=schedule_manager,
        )


def test_update_schedule_validation_failure(schedule_manager):
    def invalid(**kwargs):
        return False, "conflict"

    schedule_manager.validate_schedule = invalid
    payload = admin.UpdateServiceScheduleRequest(
        schedule_time="10:00",
        end_time=None,
        enabled=True,
        is_hourly=False,
        is_continuous=False,
        schedule_type="daily",
        description=None,
    )
    with pytest.raises(HTTPException) as exc:
        admin.update_service_schedule(
            "task",
            payload,
            db=None,
            current=DummyUser(),
            schedule_manager=schedule_manager,
        )
    assert exc.value.detail == "conflict"


def test_update_schedule_success(schedule_manager, schedule_repo):
    payload = admin.UpdateServiceScheduleRequest(
        schedule_time="10:00",
        end_time="11:00",
        enabled=True,
        is_hourly=False,
        is_continuous=False,
        schedule_type="daily",
        description="desc",
    )
    resp = admin.update_service_schedule(
        "task",
        payload,
        db=None,
        current=DummyUser(id=7),
        schedule_manager=schedule_manager,
    )
    assert resp.success is True
    assert schedule_repo.created["updated_by"] == 7


def test_update_schedule_internal_error(schedule_manager, schedule_repo):
    def boom(**kwargs):
        raise RuntimeError("fail")

    schedule_repo.create_or_update = boom
    payload = admin.UpdateServiceScheduleRequest(
        schedule_time="10:00",
        end_time=None,
        enabled=True,
        is_hourly=False,
        is_continuous=False,
        schedule_type="daily",
        description=None,
    )
    with pytest.raises(HTTPException) as exc:
        admin.update_service_schedule(
            "task",
            payload,
            db=None,
            current=DummyUser(),
            schedule_manager=schedule_manager,
        )
    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_enable_schedule_not_found(schedule_repo):
    def none(*_, **__):
        return None

    schedule_repo.update_enabled = none
    with pytest.raises(HTTPException) as exc:
        admin.enable_service_schedule(
            "task",
            db=None,
            current=DummyUser(),
            schedule_manager=DummyScheduleManager(),
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_enable_schedule_success(schedule_repo):
    resp = admin.enable_service_schedule(
        "task",
        db=None,
        current=DummyUser(id=3),
        schedule_manager=DummyScheduleManager(),
    )
    assert resp.success
    assert schedule_repo.enabled["task"] == (True, 3)


def test_enable_schedule_error(schedule_repo):
    def boom(*_, **__):
        raise RuntimeError("fail")

    schedule_repo.update_enabled = boom
    with pytest.raises(HTTPException) as exc:
        admin.enable_service_schedule(
            "task",
            db=None,
            current=DummyUser(),
            schedule_manager=DummyScheduleManager(),
        )
    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_disable_schedule_success(schedule_repo):
    resp = admin.disable_service_schedule(
        "task",
        db=None,
        current=DummyUser(id=2),
        schedule_manager=DummyScheduleManager(),
    )
    assert resp.success
    assert schedule_repo.enabled["task"] == (False, 2)


def test_disable_schedule_error(schedule_repo):
    def boom(*_, **__):
        raise RuntimeError("fail")

    schedule_repo.update_enabled = boom
    with pytest.raises(HTTPException) as exc:
        admin.disable_service_schedule(
            "task",
            db=None,
            current=DummyUser(),
            schedule_manager=DummyScheduleManager(),
        )
    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_get_schedule_manager_returns_instance(monkeypatch):
    class StubManager:
        pass

    created = SimpleNamespace(count=0)

    def factory(db):
        created.count += 1
        return StubManager()

    monkeypatch.setattr(admin, "ScheduleManager", factory)
    mgr = admin.get_schedule_manager(db="db")
    assert isinstance(mgr, StubManager)
    assert created.count == 1
