# ruff: noqa: I001, PLC0415, PLR0913, E501

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import ModuleType, SimpleNamespace

import pytest


# This test module uses local imports and inline lambdas extensively to
# isolate FastAPI startup behavior without importing heavy dependencies
# at collection time.


def test_check_broker_ipv4_connectivity_success(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    monkeypatch.setattr(main, "_FORCE_IPV4", True)

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(main.socket, "create_connection", lambda *_a, **_k: _Conn())

    assert main._check_broker_ipv4_connectivity() is True


def test_check_broker_ipv4_connectivity_failure(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    monkeypatch.setattr(main, "_FORCE_IPV4", True)

    def _raise(*_a, **_k):
        raise OSError("no route")

    monkeypatch.setattr(main.socket, "create_connection", _raise)

    assert main._check_broker_ipv4_connectivity() is False


def test_ipv4_getaddrinfo_forced_and_passthrough(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    calls = []

    def _orig(host, port, family=0, type=0, proto=0, flags=0):
        calls.append((host, family))
        return [(family, host, port)]

    monkeypatch.setattr(main, "_original_getaddrinfo", _orig)

    monkeypatch.setattr(main, "_FORCE_IPV4", False)
    main._ipv4_getaddrinfo("example.com", 443)

    monkeypatch.setattr(main, "_FORCE_IPV4", True)
    monkeypatch.setattr(main, "_BROKER_HOSTS_IPV4_ONLY", {"h"})
    main._ipv4_getaddrinfo("h", 443)
    main._ipv4_getaddrinfo("other", 443)

    assert calls[0][0] == "example.com"
    assert calls[1][0] == "h"
    assert calls[2][0] == "other"


def test_start_unified_services_skips_when_disabled(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    monkeypatch.setattr(main, "RUN_UNIFIED_IN_API", False)
    monkeypatch.setattr(main, "UNIFIED_USER_IDS", [1])

    asyncio.run(main.start_unified_services())


def test_start_unified_services_skips_when_no_users(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    monkeypatch.setattr(main, "RUN_UNIFIED_IN_API", True)
    monkeypatch.setattr(main, "UNIFIED_USER_IDS", [])

    asyncio.run(main.start_unified_services())


def test_start_unified_services_starts_tasks(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    monkeypatch.setattr(main, "RUN_UNIFIED_IN_API", True)
    monkeypatch.setattr(main, "UNIFIED_USER_IDS", [10])

    class _Auth:
        def is_authenticated(self):
            return True

    class _Mgr:
        def get_or_create_session(self, user_id: int, env_file: str):
            assert user_id == 10
            return _Auth()

    class _Svc:
        def __init__(self, user_id: int, env_file: str):
            self.user_id = user_id
            self.env_file = env_file
            self.auth = None

        async def run_async(self):
            return None

    # Provide lazy imports used inside start_unified_services
    import sys
    import types

    mod_run = types.ModuleType("modules.kotak_neo_auto_trader.run_trading_service")
    mod_run.TradingService = _Svc

    mod_mgr = types.ModuleType("modules.kotak_neo_auto_trader.shared_session_manager")
    mod_mgr.get_shared_session_manager = lambda: _Mgr()

    monkeypatch.setitem(sys.modules, "modules.kotak_neo_auto_trader.run_trading_service", mod_run)
    monkeypatch.setitem(
        sys.modules, "modules.kotak_neo_auto_trader.shared_session_manager", mod_mgr
    )

    created = []
    loop = asyncio.new_event_loop()
    old_create_task = loop.create_task

    def _create_task(coro):
        t = old_create_task(coro)
        created.append(t)
        return t

    monkeypatch.setattr(asyncio, "get_event_loop", lambda: loop)
    monkeypatch.setattr(loop, "create_task", _create_task)
    main._unified_tasks.clear()
    loop.run_until_complete(main.start_unified_services())
    loop.close()

    assert len(main._unified_tasks) == 1
    assert len(created) >= 2
    assert main._unified_tasks[0] in created


def test_start_and_stop_background_scheduler(monkeypatch: pytest.MonkeyPatch):
    import sys
    import types

    from server.app import main

    jobs_mod = types.ModuleType("server.app.jobs")
    jobs_mod.start_scheduler = lambda: None
    jobs_mod.stop_scheduler = lambda: None
    monkeypatch.setitem(sys.modules, "server.app.jobs", jobs_mod)

    asyncio.run(main.start_background_scheduler())
    asyncio.run(main.stop_background_scheduler())


def test_log_exceptions_middleware_handles_error(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    req = SimpleNamespace(state=SimpleNamespace())

    async def _boom(_request):
        raise RuntimeError("x")

    resp = asyncio.run(main.log_exceptions(req, _boom))
    assert resp.status_code == 500


def test_ensure_db_schema_creates_tables_and_bootstraps_admin(monkeypatch: pytest.MonkeyPatch):
    from server.app import main

    created = {"create_all": 0, "create_user": 0, "ensure_default": 0}

    class _Inspector:
        def has_table(self, name: str) -> bool:
            assert name == "users"
            return False

    monkeypatch.setattr(main, "inspect", lambda _engine: _Inspector())
    monkeypatch.setattr(
        main.Base.metadata,
        "create_all",
        lambda **_k: created.__setitem__("create_all", created["create_all"] + 1),
    )

    monkeypatch.setattr(main.settings, "admin_email", "admin@example.com", raising=False)
    monkeypatch.setattr(main.settings, "admin_password", "secret", raising=False)
    monkeypatch.setattr(main.settings, "admin_name", "Admin", raising=False)

    class _Query:
        def __init__(self, count_value=0):
            self._count_value = count_value

        def count(self):
            return self._count_value

        def filter(self, *_a, **_k):
            return self

        def all(self):
            return []

        def first(self):
            return None

    class _Db:
        def __init__(self):
            self.commits = 0

        def query(self, model):
            # users_count == 0 triggers admin bootstrap
            return _Query(count_value=0)

        def commit(self):
            self.commits += 1

    @contextmanager
    def _session_ctx():
        yield _Db()

    monkeypatch.setattr(main, "SessionLocal", lambda: _session_ctx())

    class _UserRepo:
        def __init__(self, db):
            self.db = db

        def create_user(self, **_kwargs):
            created["create_user"] += 1
            return SimpleNamespace(id=123)

    class _SettingsRepo:
        def __init__(self, db):
            self.db = db

        def ensure_default(self, _user_id: int):
            created["ensure_default"] += 1

    monkeypatch.setattr(main, "UserRepository", _UserRepo)
    monkeypatch.setattr(main, "SettingsRepository", _SettingsRepo)

    asyncio.run(main.ensure_db_schema())

    assert created["create_all"] == 1
    assert created["create_user"] == 1
    assert created["ensure_default"] == 1


def test_ensure_db_schema_cleans_orphans_and_auto_restores(monkeypatch: pytest.MonkeyPatch):
    from server.app import main
    from src.infrastructure.db.models import IndividualServiceStatus, ServiceStatus, Users

    class _Inspector:
        def has_table(self, name: str) -> bool:
            assert name == "users"
            return True

    monkeypatch.setattr(main, "inspect", lambda _engine: _Inspector())
    monkeypatch.setattr(
        main.Base.metadata, "create_all", lambda **_k: pytest.fail("should not create schema")
    )
    monkeypatch.setattr(main.settings, "admin_email", None, raising=False)
    monkeypatch.setattr(main.settings, "admin_password", None, raising=False)

    # First DB session: cleanup orphaned statuses
    running_unified = [SimpleNamespace(user_id=1, service_running=True)]
    running_individual = [
        SimpleNamespace(user_id=1, task_name="svc", is_running=True, process_id=999)
    ]

    class _Query:
        def __init__(self, *, model, count_value=1, all_value=None, first_value=None):
            self._model = model
            self._count_value = count_value
            self._all_value = all_value
            self._first_value = first_value

        def count(self):
            return self._count_value

        def filter(self, *_a, **_k):
            return self

        def all(self):
            return list(self._all_value or [])

        def first(self):
            return self._first_value

    class _Db:
        def __init__(self, phase: str):
            self.phase = phase
            self.commits = 0

        def query(self, model):
            if self.phase == "cleanup":
                if model is Users:
                    return _Query(model=model, count_value=1)
                if model is ServiceStatus:
                    return _Query(model=model, all_value=running_unified)
                if model is IndividualServiceStatus:
                    return _Query(model=model, all_value=running_individual)
                return _Query(model=model)
            # restore phase
            if model is Users:
                return _Query(model=model, first_value=SimpleNamespace(id=1))
            return _Query(model=model)

        def commit(self):
            self.commits += 1

    cleanup_db = _Db("cleanup")
    restore_db = _Db("restore")

    # Provide two sessions in order: cleanup then restore
    sessions = [cleanup_db, restore_db]

    @contextmanager
    def _session_ctx():
        yield sessions.pop(0)

    monkeypatch.setattr(main, "SessionLocal", lambda: _session_ctx())
    monkeypatch.setattr(main.traceback, "print_exc", lambda: None)

    # Stub service managers imported inside ensure_db_schema
    mod_ism = ModuleType("src.application.services.individual_service_manager")

    class _IndividualServiceManager:
        def __init__(self, db):
            self.db = db

        def start_service(self, user_id: int, task_name: str):
            assert user_id == 1
            assert task_name == "svc"
            return (False, "Unified service is running")

    mod_ism.IndividualServiceManager = _IndividualServiceManager

    mod_muts = ModuleType("src.application.services.multi_user_trading_service")

    class _MultiUserTradingService:
        def __init__(self, db):
            self.db = db

        def start_service(self, user_id: int):
            assert user_id == 1
            return True

    mod_muts.MultiUserTradingService = _MultiUserTradingService

    import sys

    # Ensure these module substitutions are reverted after the test.
    monkeypatch.setitem(sys.modules, "src.application.services.individual_service_manager", mod_ism)
    monkeypatch.setitem(
        sys.modules, "src.application.services.multi_user_trading_service", mod_muts
    )

    asyncio.run(main.ensure_db_schema())

    # Orphan cleanup should have happened
    assert running_unified[0].service_running is False
    assert running_individual[0].is_running is False
    assert running_individual[0].process_id is None
    assert cleanup_db.commits >= 1
