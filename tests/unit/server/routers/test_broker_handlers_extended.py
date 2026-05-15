# ruff: noqa: E501, PLC0415
"""Direct-call coverage for large broker router handlers (portfolio, holdings, orders, history)."""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from server.app.routers import broker as br
from src.infrastructure.db.models import OrderStatus, TradeMode


def _money(amount: float):
    return SimpleNamespace(amount=amount)


class _FakeSettingsRepo:
    def __init__(self, settings):
        self._settings = settings

    def get_by_user_id(self, _uid):
        return self._settings


class _FakeBroker:
    def __init__(self, *, connect_ok: bool = True, holdings=None, orders=None):
        self._connect_ok = connect_ok
        self._holdings = holdings or []
        self._orders = orders or []
        self._client = object()
        self._connected = False

    def connect(self):
        if not self._connect_ok:
            return False
        self._connected = True
        return True

    def get_holdings(self):
        return list(self._holdings)

    def get_account_limits(self):
        return {"net": _money(500.0)}

    def get_all_orders(self):
        return list(self._orders)


class _FakeAuth:
    def __init__(self, *, authenticated: bool = True, client: object | None = object()):
        self._authenticated = authenticated
        self._client = client

    def is_authenticated(self):
        return self._authenticated

    def get_client(self):
        return self._client


class _FakeSessionMgr:
    def __init__(self):
        self.cleared = []

    def clear_session(self, user_id: int):
        self.cleared.append(user_id)


@pytest.fixture
def broker_settings_broker_mode():
    return SimpleNamespace(
        trade_mode=TradeMode.BROKER,
        broker="kotak-neo",
        broker_status="Connected",
        broker_creds_encrypted=b"enc",
    )


def test_get_broker_portfolio_http_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(br, "SettingsRepository", lambda _db: _FakeSettingsRepo(None))
    with pytest.raises(HTTPException) as ei:
        br.get_broker_portfolio(db=object(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 404

    monkeypatch.setattr(
        br,
        "SettingsRepository",
        lambda _db: _FakeSettingsRepo(
            SimpleNamespace(trade_mode=TradeMode.PAPER, broker_creds_encrypted=None)
        ),
    )
    with pytest.raises(HTTPException) as ei:
        br.get_broker_portfolio(db=object(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 400

    monkeypatch.setattr(
        br,
        "SettingsRepository",
        lambda _db: _FakeSettingsRepo(
            SimpleNamespace(trade_mode=TradeMode.BROKER, broker_creds_encrypted=None)
        ),
    )
    with pytest.raises(HTTPException) as ei:
        br.get_broker_portfolio(db=object(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 400

    monkeypatch.setattr(
        br,
        "SettingsRepository",
        lambda _db: _FakeSettingsRepo(
            SimpleNamespace(trade_mode=TradeMode.BROKER, broker_creds_encrypted=b"x")
        ),
    )
    monkeypatch.setattr(br, "decrypt_broker_credentials", lambda _b: None)
    with pytest.raises(HTTPException) as ei:
        br.get_broker_portfolio(db=object(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 400


def test_get_broker_portfolio_success_and_service_unavailable(
    monkeypatch, tmp_path, broker_settings_broker_mode
):
    env_file = str(tmp_path / "kotak.env")
    monkeypatch.setattr(
        br, "SettingsRepository", lambda _db: _FakeSettingsRepo(broker_settings_broker_mode)
    )
    monkeypatch.setattr(br, "decrypt_broker_credentials", lambda _b: {"api_key": "k"})
    monkeypatch.setattr(br, "create_temp_env_file", lambda _creds: env_file)
    tmp_path.joinpath("kotak.env").write_text("x", encoding="utf-8")

    holding = SimpleNamespace(
        quantity=10,
        symbol="RELIANCE-EQ",
        current_price=_money(100.0),
        average_price=_money(90.0),
    )
    broker = _FakeBroker(holdings=[holding])

    monkeypatch.setattr(br, "_get_or_create_auth_session", lambda *a, **k: _FakeAuth())

    class _BF:
        @staticmethod
        def create_broker(name, auth_handler=None):
            assert name == "kotak_neo"
            return broker

    mod_bf = types.ModuleType("broker_factory_mod")
    mod_bf.BrokerFactory = _BF
    mod_ad = types.ModuleType("broker_adapter_mod")

    class _BSE(Exception):
        def __init__(self):
            super().__init__("down")
            self.message = "maintenance"

    mod_ad.BrokerServiceUnavailableError = _BSE
    monkeypatch.setitem(
        sys.modules,
        "modules.kotak_neo_auto_trader.infrastructure.broker_factory",
        mod_bf,
    )
    monkeypatch.setitem(
        sys.modules,
        "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter",
        mod_ad,
    )

    class _PR:
        def __init__(self, _db):
            pass

        def get_by_symbol(self, *_a, **_k):
            return None

        def list(self, *_a, **_k):
            return []

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository", _PR
    )

    out = br.get_broker_portfolio(db=object(), current=SimpleNamespace(id=7))
    assert out.account.available_cash == 500.0
    assert len(out.holdings) == 1
    assert out.holdings[0].symbol == "RELIANCE-EQ"

    def _raise_holdings():
        raise _BSE()

    broker.get_holdings = _raise_holdings
    with pytest.raises(HTTPException) as ei:
        br.get_broker_portfolio(db=object(), current=SimpleNamespace(id=7))
    assert ei.value.status_code == 503


def test_get_broker_portfolio_stale_session_recovers(
    monkeypatch, tmp_path, broker_settings_broker_mode
):
    env_file = str(tmp_path / "kotak2.env")
    tmp_path.joinpath("kotak2.env").write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        br, "SettingsRepository", lambda _db: _FakeSettingsRepo(broker_settings_broker_mode)
    )
    monkeypatch.setattr(br, "decrypt_broker_credentials", lambda _b: {"api_key": "k"})
    monkeypatch.setattr(br, "create_temp_env_file", lambda _creds: env_file)

    holding = SimpleNamespace(
        quantity=1,
        symbol="TCS-EQ",
        current_price=_money(200.0),
        average_price=_money(190.0),
    )
    good_broker = _FakeBroker(holdings=[holding])

    class _StaleAuth(_FakeAuth):
        def __init__(self):
            super().__init__(authenticated=True, client=None)

    class _GoodAuth(_FakeAuth):
        def __init__(self):
            super().__init__(authenticated=True, client=object())

    auths = [_StaleAuth(), _GoodAuth()]

    def _get_sess(*_a, **_k):
        return auths.pop(0) if auths else _GoodAuth()

    mgr = _FakeSessionMgr()

    class _SM:
        @staticmethod
        def get_shared_session_manager():
            return mgr

    monkeypatch.setattr(br, "_get_or_create_auth_session", _get_sess)

    class _BF:
        @staticmethod
        def create_broker(name, auth_handler=None):
            return good_broker

    mod_bf = types.ModuleType("broker_factory_mod2")
    mod_bf.BrokerFactory = _BF
    mod_ad = types.ModuleType("broker_adapter_mod2")

    class _BSE(Exception):
        pass

    mod_ad.BrokerServiceUnavailableError = _BSE
    monkeypatch.setitem(
        sys.modules,
        "modules.kotak_neo_auto_trader.infrastructure.broker_factory",
        mod_bf,
    )
    monkeypatch.setitem(
        sys.modules,
        "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter",
        mod_ad,
    )
    monkeypatch.setitem(
        sys.modules,
        "modules.kotak_neo_auto_trader.shared_session_manager",
        types.SimpleNamespace(get_shared_session_manager=_SM.get_shared_session_manager),
    )

    class _PR:
        def __init__(self, _db):
            pass

        def get_by_symbol(self, *_a, **_k):
            return None

        def list(self, *_a, **_k):
            return []

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository", _PR
    )

    out = br.get_broker_portfolio(db=object(), current=SimpleNamespace(id=8))
    assert len(out.holdings) == 1
    assert mgr.cleared == [8]


def test_get_broker_system_holdings_paths(monkeypatch, broker_settings_broker_mode):
    monkeypatch.setattr(br, "SettingsRepository", lambda _db: _FakeSettingsRepo(None))
    with pytest.raises(HTTPException):
        br.get_broker_system_holdings(db=object(), current=SimpleNamespace(id=1))

    monkeypatch.setattr(
        br,
        "SettingsRepository",
        lambda _db: _FakeSettingsRepo(
            SimpleNamespace(trade_mode=TradeMode.PAPER, broker_creds_encrypted=None)
        ),
    )
    with pytest.raises(HTTPException):
        br.get_broker_system_holdings(db=object(), current=SimpleNamespace(id=1))

    pos = SimpleNamespace(
        symbol="INFY-EQ",
        quantity=5.0,
        avg_price=10.0,
        closed_at=None,
        reentry_count=1,
        reentries={"reentries": [{"x": 1}]},
        entry_rsi=40.0,
        initial_entry_price=9.0,
    )
    broker_settings_broker_mode.broker_creds_encrypted = None

    class _PR:
        def __init__(self, _db):
            pass

        def list(self, _uid):
            return [pos]

    monkeypatch.setattr(
        br,
        "SettingsRepository",
        lambda _db: _FakeSettingsRepo(broker_settings_broker_mode),
    )
    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository", _PR
    )

    out = br.get_broker_system_holdings(db=object(), current=SimpleNamespace(id=3))
    assert len(out.holdings) == 1
    assert out.holdings[0].reentries == [{"x": 1}]


def test_get_broker_orders_success(monkeypatch, tmp_path, broker_settings_broker_mode):
    env_file = str(tmp_path / "k3.env")
    tmp_path.joinpath("k3.env").write_text("z", encoding="utf-8")
    monkeypatch.setattr(
        br, "SettingsRepository", lambda _db: _FakeSettingsRepo(broker_settings_broker_mode)
    )
    monkeypatch.setattr(br, "decrypt_broker_credentials", lambda _b: {"k": "v"})
    monkeypatch.setattr(br, "create_temp_env_file", lambda _c: env_file)

    ord_obj = SimpleNamespace(
        status=SimpleNamespace(value="COMPLETE"),
        transaction_type=SimpleNamespace(value="BUY"),
        symbol="ACC-EQ",
        quantity=2,
        price=_money(11.0),
        executed_price=_money(11.0),
        executed_quantity=2,
        order_id="O1",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    gw = _FakeBroker(orders=[ord_obj])
    monkeypatch.setattr(br, "_get_or_create_auth_session", lambda *a, **k: _FakeAuth())

    class _BF:
        @staticmethod
        def create_broker(name, auth_handler=None):
            return gw

    mod_bf = types.ModuleType("broker_factory_mod3")
    mod_bf.BrokerFactory = _BF
    mod_ad = types.ModuleType("broker_adapter_mod3")

    class _BSE(Exception):
        pass

    mod_ad.BrokerServiceUnavailableError = _BSE
    monkeypatch.setitem(
        sys.modules,
        "modules.kotak_neo_auto_trader.infrastructure.broker_factory",
        mod_bf,
    )
    monkeypatch.setitem(
        sys.modules,
        "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter",
        mod_ad,
    )

    rows = br.get_broker_orders(db=object(), current=SimpleNamespace(id=4))
    assert len(rows) == 1
    assert rows[0]["side"] == "buy"


def test_clear_broker_session(monkeypatch):
    mgr = MagicMock()

    class _SM:
        @staticmethod
        def get_shared_session_manager():
            return mgr

    monkeypatch.setitem(
        sys.modules,
        "modules.kotak_neo_auto_trader.shared_session_manager",
        types.SimpleNamespace(get_shared_session_manager=_SM.get_shared_session_manager),
    )
    out = br.clear_broker_session(db=object(), current=SimpleNamespace(id=99))
    assert out["status"] == "success"
    mgr.clear_session.assert_called_once_with(99)


class _HistQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a):
        return self

    def limit(self, *_n):
        return self

    def all(self):
        return list(self._rows)


class _HistDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, _model):
        return _HistQuery(self._rows)


def test_get_broker_trading_history(monkeypatch, broker_settings_broker_mode):
    monkeypatch.setattr(
        br, "SettingsRepository", lambda _db: _FakeSettingsRepo(broker_settings_broker_mode)
    )
    monkeypatch.setattr(br, "_upsert_pnl_from_closed_positions", lambda *a, **k: None)

    o = SimpleNamespace(
        id=1,
        user_id=1,
        symbol="X",
        side="buy",
        quantity=1.0,
        status=OrderStatus.CLOSED,
        placed_at=datetime(2026, 1, 2, tzinfo=UTC),
        order_id=None,
        broker_order_id="B1",
        execution_price=10.0,
        avg_price=None,
    )
    db = _HistDB([o])
    hist = br.get_broker_trading_history(
        from_date="not-a-date",
        to_date="also-bad",
        raw=True,
        limit=10,
        db=db,
        current=SimpleNamespace(id=1),
    )
    assert hist.transactions
    hist2 = br.get_broker_trading_history(
        from_date="2026-01-01T00:00:00+00:00",
        to_date="2026-12-31T00:00:00+00:00",
        raw=False,
        limit=50,
        db=db,
        current=SimpleNamespace(id=1),
    )
    assert hist2.statistics["total_trades"] >= 0


def test_test_kotak_neo_connection_short_circuit(monkeypatch):
    ok, msg = br._test_kotak_neo_connection(
        br.KotakNeoCreds(consumer_key="", consumer_secret="x", mobile_number=None, password=None)
    )
    assert ok is False

    ok2, msg2 = br._test_kotak_neo_connection(
        br.KotakNeoCreds(
            consumer_key="k",
            consumer_secret="u",
            mobile_number=None,
            password=None,
        )
    )
    assert ok2 is True


def test_extract_error_message():
    assert br._extract_error_message([{"message": "hi"}]) == "hi"


def test_kotak_rest_login_happy_path(monkeypatch):
    """Exercise REST tradeApiLogin + tradeApiValidate + optional script-details GET."""

    creds = br.KotakNeoCreds(
        consumer_key="api-key",
        consumer_secret="UCC123",
        mobile_number="9999999999",
        password="pw",
        mpin="1234",
        totp_secret="JBSWY3DPEHPK3PXP",
    )

    class _Resp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def _post(url, **_kwargs):
        if "tradeApiLogin" in url:
            return _Resp(200, {"data": {"sid": "sid1", "token": "tok1"}})
        if "tradeApiValidate" in url:
            return _Resp(200, {"data": {"baseUrl": "https://gw.example/", "token": "tradeTok"}})
        return _Resp(500, {})

    monkeypatch.setattr(br.requests, "post", _post)
    monkeypatch.setattr(br.requests, "get", lambda **_kwargs: _Resp(200, {}))

    ok, msg = br._test_kotak_neo_connection(creds)
    assert ok is True
    assert "successful" in msg.lower()


def test_kotak_rest_login_script_details_non_200_is_warning_only(monkeypatch):
    creds = br.KotakNeoCreds(
        consumer_key="api-key",
        consumer_secret="UCC123",
        mobile_number="9999999999",
        password="pw",
        mpin="1234",
        totp_secret="JBSWY3DPEHPK3PXP",
    )

    class _Resp:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def json(self):
            return self._payload

    def _post(url, **_kwargs):
        if "tradeApiLogin" in url:
            return _Resp(200, {"data": {"sid": "sid1", "token": "tok1"}})
        if "tradeApiValidate" in url:
            return _Resp(200, {"data": {"baseUrl": "https://gw.example/", "token": "tradeTok"}})
        return _Resp(500, {})

    monkeypatch.setattr(br.requests, "post", _post)
    monkeypatch.setattr(br.requests, "get", lambda **_kwargs: _Resp(503, {}))

    ok, msg = br._test_kotak_neo_connection(creds)
    assert ok is True


def test_kotak_rest_login_step1_http_error(monkeypatch):
    creds = br.KotakNeoCreds(
        consumer_key="api-key",
        consumer_secret="UCC123",
        mobile_number="9999999999",
        password="pw",
        mpin="1234",
        totp_secret="JBSWY3DPEHPK3PXP",
    )

    class _Resp:
        def __init__(self, code, body):
            self.status_code = code
            self._body = body

        def json(self):
            return self._body

    monkeypatch.setattr(
        br.requests,
        "post",
        lambda url, **_kwargs: _Resp(401, {"message": "nope"}),
    )
    ok, msg = br._test_kotak_neo_connection(creds)
    assert ok is False
    assert "Login failed" in msg


def test_kotak_rest_login_step1_missing_sid(monkeypatch):
    creds = br.KotakNeoCreds(
        consumer_key="api-key",
        consumer_secret="UCC123",
        mobile_number="9999999999",
        password="pw",
        mpin="1234",
        totp_secret="JBSWY3DPEHPK3PXP",
    )

    class _Resp:
        status_code = 200

        def json(self):
            return {"data": {}}

    monkeypatch.setattr(br.requests, "post", lambda *a, **k: _Resp())
    ok, msg = br._test_kotak_neo_connection(creds)
    assert ok is False
    assert "missing sid" in msg.lower()


def test_kotak_rest_login_requires_mpin_for_step2(monkeypatch):
    creds = br.KotakNeoCreds(
        consumer_key="api-key",
        consumer_secret="UCC123",
        mobile_number="9999999999",
        password="pw",
        mpin=None,
        totp_secret="JBSWY3DPEHPK3PXP",
    )

    class _Resp:
        status_code = 200

        def json(self):
            return {"data": {"sid": "s", "token": "t"}}

    monkeypatch.setattr(br.requests, "post", lambda *a, **k: _Resp())
    ok, msg = br._test_kotak_neo_connection(creds)
    assert ok is False
    assert "MPIN is required" in msg


def test_kotak_rest_totp_secret_invalid_format():
    creds = br.KotakNeoCreds(
        consumer_key="api-key",
        consumer_secret="UCC123",
        mobile_number="9999999999",
        password="pw",
        mpin="1234",
        totp_secret="not-valid-base32-!!!",
    )
    ok, msg = br._test_kotak_neo_connection(creds)
    assert ok is False
    assert "TOTP" in msg or "secret" in msg.lower()


def test_kotak_rest_pyotp_import_error(monkeypatch):
    import builtins

    creds = br.KotakNeoCreds(
        consumer_key="api-key",
        consumer_secret="UCC123",
        mobile_number="9999999999",
        password="pw",
        mpin="1234",
        totp_secret="JBSWY3DPEHPK3PXP",
    )

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pyotp":
            raise ImportError("blocked")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, msg = br._test_kotak_neo_connection(creds)
    assert ok is False
    assert "pyotp" in msg.lower()
