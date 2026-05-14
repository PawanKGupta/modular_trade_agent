# ruff: noqa: E501, PLC0415
"""Direct-call coverage for user router (settings, UI prefs, unified portfolio)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.app.routers import user as user_router
from server.app.schemas.user import SettingsUpdateRequest
from src.infrastructure.db.models import TradeMode


def test_get_settings_returns_repo_payload(monkeypatch):
    settings = SimpleNamespace(trade_mode=TradeMode.PAPER, broker="k", broker_status="ok")

    class _Repo:
        def __init__(self, _db):
            pass

        def ensure_default(self, uid):
            assert uid == 5
            return settings

    monkeypatch.setattr(user_router, "SettingsRepository", _Repo)
    out = user_router.get_settings(db=object(), current=SimpleNamespace(id=5))
    assert out.trade_mode == "paper"
    assert out.broker == "k"


def test_update_settings_broker_requires_entitlement(monkeypatch):
    class _Repo:
        def __init__(self, _db):
            pass

        def ensure_default(self, uid):
            return SimpleNamespace(trade_mode=TradeMode.PAPER, broker=None, broker_status=None)

        def update(self, settings, **kwargs):
            return SimpleNamespace(
                trade_mode=kwargs.get("trade_mode") or TradeMode.BROKER,
                broker=kwargs.get("broker"),
                broker_status=kwargs.get("broker_status"),
            )

    monkeypatch.setattr(user_router, "SettingsRepository", _Repo)

    class _Ent:
        def __init__(self, _db):
            pass

        def user_has_feature(self, user, feature):
            assert feature == "broker_execution"
            return False

    monkeypatch.setattr(user_router, "SubscriptionEntitlementService", _Ent)
    payload = SettingsUpdateRequest(trade_mode="broker", broker="x", broker_status="y")
    with pytest.raises(HTTPException) as ei:
        user_router.update_settings(payload=payload, db=object(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 403


def test_update_settings_broker_allowed(monkeypatch):
    updated = SimpleNamespace(trade_mode=TradeMode.BROKER, broker="neo", broker_status="Connected")

    class _Repo:
        def __init__(self, _db):
            pass

        def ensure_default(self, uid):
            return SimpleNamespace(trade_mode=TradeMode.PAPER, broker=None, broker_status=None)

        def update(self, settings, **kwargs):
            return updated

    monkeypatch.setattr(user_router, "SettingsRepository", _Repo)
    monkeypatch.setattr(
        user_router,
        "SubscriptionEntitlementService",
        lambda db: SimpleNamespace(user_has_feature=lambda u, f: True),
    )
    payload = SettingsUpdateRequest(trade_mode="broker", broker="neo", broker_status="Connected")
    out = user_router.update_settings(payload=payload, db=object(), current=SimpleNamespace(id=2))
    assert out.trade_mode == "broker"


def test_update_buying_zone_columns_propagates_errors(monkeypatch):
    class _Repo:
        def __init__(self, _db):
            pass

        def update_ui_preferences(self, *_a, **_k):
            raise ValueError("prefs")

    monkeypatch.setattr(user_router, "SettingsRepository", _Repo)
    payload = user_router.BuyingZoneColumnsRequest(columns=["a"])
    with pytest.raises(ValueError, match="prefs"):
        user_router.update_buying_zone_columns(
            payload=payload, db=object(), current=SimpleNamespace(id=3)
        )


def test_save_filter_preset_success(monkeypatch):
    stored = {"filter_presets": {}}

    class _Repo:
        def __init__(self, _db):
            pass

        def get_ui_preferences(self, uid):
            return dict(stored)

        def update_ui_preferences(self, uid, prefs):
            stored.clear()
            stored.update(prefs)
            return prefs

    monkeypatch.setattr(user_router, "SettingsRepository", _Repo)
    payload = user_router.FilterPresetRequest(page="signals", preset_name="p1", filters={"x": 1})
    out = user_router.save_filter_preset(
        payload=payload, db=object(), current=SimpleNamespace(id=4)
    )
    assert "p1" in out.presets


def test_delete_filter_preset_removes_entry(monkeypatch):
    prefs_state = {"filter_presets": {"signals": {"old": {}}}}

    class _Repo:
        def __init__(self, _db):
            pass

        def get_ui_preferences(self, uid):
            return dict(prefs_state)

        def update_ui_preferences(self, uid, prefs):
            prefs_state.clear()
            prefs_state.update(prefs)
            return prefs

    monkeypatch.setattr(user_router, "SettingsRepository", _Repo)
    out = user_router.delete_filter_preset(
        page="signals", preset_name="old", db=object(), current=SimpleNamespace(id=6)
    )
    assert "deleted" in out["message"].lower()


def test_get_portfolio_paper_delegates(monkeypatch):
    sentinel = object()

    def _paper(*, page, page_size, db, current):
        assert page == 2
        assert page_size == 20
        return sentinel

    class _SR:
        def __init__(self, _db):
            pass

        def get_by_user_id(self, uid):
            return SimpleNamespace(trade_mode=TradeMode.PAPER)

    monkeypatch.setattr(user_router, "SettingsRepository", _SR)
    monkeypatch.setattr(user_router, "get_paper_trading_portfolio", _paper)
    out = user_router.get_portfolio(
        page=2, page_size=20, db=object(), current=SimpleNamespace(id=8)
    )
    assert out is sentinel


def test_get_portfolio_broker_wraps_get_broker_portfolio(monkeypatch):
    from server.app.routers import paper_trading as pt

    bp = pt.PaperTradingPortfolio(
        account=pt.PaperTradingAccount(
            initial_capital=100000.0,
            available_cash=50000.0,
            total_pnl=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            portfolio_value=50000.0,
            total_value=100000.0,
            return_percentage=0.0,
        ),
        holdings=[],
        recent_orders=[],
        order_statistics={"n": 1},
    )

    def _gb(db, current):
        return bp

    class _SR:
        def __init__(self, _db):
            pass

        def get_by_user_id(self, uid):
            return SimpleNamespace(trade_mode=TradeMode.BROKER)

    monkeypatch.setattr(user_router, "SettingsRepository", _SR)
    monkeypatch.setattr(user_router, "get_broker_portfolio", _gb)
    out = user_router.get_portfolio(
        page=1, page_size=10, db=object(), current=SimpleNamespace(id=9)
    )
    assert out.account.initial_capital == 100000.0
    assert out.recent_orders.total == 0


def test_get_portfolio_missing_settings_uses_default(monkeypatch):
    sentinel = object()

    def _paper(*, page, page_size, db, current):
        return sentinel

    class _SR:
        def __init__(self, _db):
            pass

        def get_by_user_id(self, uid):
            return None

        def ensure_default(self, uid):
            return SimpleNamespace(trade_mode=TradeMode.PAPER)

    monkeypatch.setattr(user_router, "SettingsRepository", _SR)
    monkeypatch.setattr(user_router, "get_paper_trading_portfolio", _paper)
    out = user_router.get_portfolio(
        page=1, page_size=5, db=object(), current=SimpleNamespace(id=10)
    )
    assert out is sentinel


def test_get_portfolio_propagates_errors(monkeypatch):
    class _SR:
        def __init__(self, _db):
            pass

        def get_by_user_id(self, uid):
            return SimpleNamespace(trade_mode=TradeMode.PAPER)

    monkeypatch.setattr(user_router, "SettingsRepository", _SR)
    monkeypatch.setattr(
        user_router,
        "get_paper_trading_portfolio",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError, match="boom"):
        user_router.get_portfolio(page=1, page_size=5, db=object(), current=SimpleNamespace(id=11))
