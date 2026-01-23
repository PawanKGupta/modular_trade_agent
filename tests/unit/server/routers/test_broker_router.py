import sys
import types
from types import SimpleNamespace

from server.app.routers import broker as broker_router
from src.infrastructure.db.models import TradeMode


class FakeSettingsRepo:
    def __init__(self):
        self.settings = SimpleNamespace(
            trade_mode=None,
            broker=None,
            broker_status=None,
            broker_creds_encrypted=None,
        )

    def ensure_default(self, user_id):
        return self.settings

    def update(self, settings, trade_mode=None, broker=None, broker_status=None):
        if trade_mode is not None:
            settings.trade_mode = trade_mode
        if broker is not None:
            settings.broker = broker
        if broker_status is not None:
            settings.broker_status = broker_status
        return settings

    def get_by_user_id(self, user_id):
        return self.settings


class FakeSessionManager:
    def __init__(self, auth):
        self._auth = auth

    def get_session(self, user_id):
        return self._auth


class FakeAuth:
    def __init__(self, authenticated: bool = True):
        self._authenticated = authenticated

    def is_authenticated(self):
        return self._authenticated

    def get_client(self):
        return object()


def test_save_broker_creds_encrypts_payload(monkeypatch):
    repo = FakeSettingsRepo()
    monkeypatch.setattr(broker_router, "SettingsRepository", lambda db: repo)
    monkeypatch.setattr(broker_router, "encrypt_blob", lambda payload: b"encrypted")

    payload = SimpleNamespace(
        api_key="key",
        api_secret="secret",
        broker="kotak-neo",
        mobile_number=None,
        password=None,
        mpin=None,
        totp_secret=None,
        environment=None,
    )

    class FakeDB:
        def commit(self):
            pass

    response = broker_router.save_broker_creds(
        payload=payload,
        db=FakeDB(),
        current=SimpleNamespace(id=11),
    )

    assert response["status"] == "ok"
    assert repo.settings.broker == "kotak-neo"
    assert repo.settings.trade_mode == TradeMode.BROKER
    assert repo.settings.broker_creds_encrypted == b"encrypted"


class FakeCommitDB:
    def commit(self):
        pass


def test_broker_status_returns_connected(monkeypatch):
    repo = FakeSettingsRepo()
    repo.settings.trade_mode = TradeMode.BROKER
    repo.settings.broker = "kotak-neo"
    repo.settings.broker_status = "Stored"
    repo.settings.broker_creds_encrypted = b"data"

    auth = FakeAuth(authenticated=True)
    monkeypatch.setattr(broker_router, "SettingsRepository", lambda db: repo)
    fake_module = types.ModuleType("modules.kotak_neo_auto_trader.shared_session_manager")
    fake_module.get_shared_session_manager = lambda: FakeSessionManager(auth)
    monkeypatch.setitem(
        sys.modules,
        "modules.kotak_neo_auto_trader.shared_session_manager",
        fake_module,
    )

    result = broker_router.broker_status(
        db=FakeCommitDB(),
        current=SimpleNamespace(id=22),
    )

    assert result["status"] == "Connected"
    assert repo.settings.broker_status == "Connected"


def test_get_broker_creds_info_masks_values(monkeypatch):
    repo = FakeSettingsRepo()
    repo.settings.broker_creds_encrypted = b"secret"
    monkeypatch.setattr(broker_router, "SettingsRepository", lambda db: repo)
    monkeypatch.setattr(
        broker_router,
        "decrypt_blob",
        lambda blob: b'{"api_key":"abcd1234","api_secret":"secret5678"}',
    )

    info = broker_router.get_broker_creds_info(
        show_full=False,
        db=SimpleNamespace(),
        current=SimpleNamespace(id=33),
    )

    assert info.has_creds is True
    assert info.api_key_masked.startswith("****")
    assert info.api_secret_masked.startswith("****")


def test_test_broker_connection_handles_variants(monkeypatch):
    monkeypatch.setattr(
        broker_router,
        "_test_kotak_neo_connection",
        lambda creds: (True, "ok"),
    )

    payload = SimpleNamespace(
        api_key="key",
        api_secret="secret",
        broker="kotak-neo",
        mobile_number=None,
        password=None,
        mpin=None,
        totp_secret=None,
        environment="prod",
    )

    response = broker_router.test_broker_connection(
        payload=payload,
        db=SimpleNamespace(),
        current=SimpleNamespace(id=44),
    )

    assert response.ok is True
    assert "ok" in response.message

    missing = SimpleNamespace(
        api_key="",
        api_secret="",
        broker="kotak-neo",
        mobile_number=None,
        password=None,
        mpin=None,
        totp_secret=None,
        environment=None,
    )

    response = broker_router.test_broker_connection(
        payload=missing,
        db=SimpleNamespace(),
        current=SimpleNamespace(id=44),
    )

    assert response.ok is False
    assert "required" in response.message.lower()

    response = broker_router.test_broker_connection(
        payload=SimpleNamespace(
            broker="unknown",
            api_key="any",
            api_secret="any",
            mobile_number=None,
            password=None,
            mpin=None,
            totp_secret=None,
            environment=None,
        ),
        db=SimpleNamespace(),
        current=SimpleNamespace(id=44),
    )

    assert response.ok is False
    assert "unsupported" in response.message.lower()
