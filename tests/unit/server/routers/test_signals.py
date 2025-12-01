from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from server.app.routers import signals
from src.infrastructure.db.models import SignalStatus, UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummySignal(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            symbol=kwargs.get("symbol", "RELIANCE.NS"),
            status=kwargs.get("status", SignalStatus.ACTIVE),
            ts=kwargs.get("ts", datetime(2025, 1, 15, 10, 0, 0)),
            # Technical indicators
            rsi10=kwargs.get("rsi10", None),
            ema9=kwargs.get("ema9", None),
            ema200=kwargs.get("ema200", None),
            distance_to_ema9=kwargs.get("distance_to_ema9", None),
            clean_chart=kwargs.get("clean_chart", None),
            monthly_support_dist=kwargs.get("monthly_support_dist", None),
            confidence=kwargs.get("confidence", None),
            # Scoring fields
            backtest_score=kwargs.get("backtest_score", None),
            combined_score=kwargs.get("combined_score", None),
            strength_score=kwargs.get("strength_score", None),
            priority_score=kwargs.get("priority_score", None),
            # ML fields
            ml_verdict=kwargs.get("ml_verdict", None),
            ml_confidence=kwargs.get("ml_confidence", None),
            ml_probabilities=kwargs.get("ml_probabilities", None),
            # Trading parameters
            buy_range=kwargs.get("buy_range", None),
            target=kwargs.get("target", None),
            stop=kwargs.get("stop", None),
            last_close=kwargs.get("last_close", None),
            # Fundamental data
            pe=kwargs.get("pe", None),
            pb=kwargs.get("pb", None),
            fundamental_assessment=kwargs.get("fundamental_assessment", None),
            fundamental_ok=kwargs.get("fundamental_ok", None),
            # Volume data
            avg_vol=kwargs.get("avg_vol", None),
            today_vol=kwargs.get("today_vol", None),
            volume_analysis=kwargs.get("volume_analysis", None),
            volume_pattern=kwargs.get("volume_pattern", None),
            volume_description=kwargs.get("volume_description", None),
            vol_ok=kwargs.get("vol_ok", None),
            volume_ratio=kwargs.get("volume_ratio", None),
            # Analysis metadata
            verdict=kwargs.get("verdict", None),
            signals=kwargs.get("signals", None),
            justification=kwargs.get("justification", None),
            timeframe_analysis=kwargs.get("timeframe_analysis", None),
            news_sentiment=kwargs.get("news_sentiment", None),
            candle_analysis=kwargs.get("candle_analysis", None),
            chart_quality=kwargs.get("chart_quality", None),
            # Additional analysis fields
            final_verdict=kwargs.get("final_verdict", None),
            rule_verdict=kwargs.get("rule_verdict", None),
            verdict_source=kwargs.get("verdict_source", None),
            backtest_confidence=kwargs.get("backtest_confidence", None),
            vol_strong=kwargs.get("vol_strong", None),
            is_above_ema200=kwargs.get("is_above_ema200", None),
            # Dip buying features
            dip_depth_from_20d_high_pct=kwargs.get("dip_depth_from_20d_high_pct", None),
            consecutive_red_days=kwargs.get("consecutive_red_days", None),
            dip_speed_pct_per_day=kwargs.get("dip_speed_pct_per_day", None),
            decline_rate_slowing=kwargs.get("decline_rate_slowing", None),
            volume_green_vs_red_ratio=kwargs.get("volume_green_vs_red_ratio", None),
            support_hold_count=kwargs.get("support_hold_count", None),
            # Additional metadata
            liquidity_recommendation=kwargs.get("liquidity_recommendation", None),
            trading_params=kwargs.get("trading_params", None),
        )


class DummySignalsRepo:
    def __init__(self, db):
        self.db = db
        self.recent_items = []
        self.by_date_items = {}
        self.last_n_dates_items = []
        self.recent_called = []
        self.by_date_called = []
        self.last_n_dates_called = []
        self.mark_rejected_called = []
        self.mark_rejected_result = True

    def recent(self, limit=100, active_only=False):
        self.recent_called.append((limit, active_only))
        return self.recent_items

    def by_date(self, target_date, limit=100):
        self.by_date_called.append((target_date, limit))
        return self.by_date_items.get(target_date, [])

    def last_n_dates(self, n, limit=100):
        self.last_n_dates_called.append((n, limit))
        return self.last_n_dates_items

    def mark_as_rejected(self, symbol):
        self.mark_rejected_called.append(symbol)
        return self.mark_rejected_result


@pytest.fixture
def signals_repo(monkeypatch):
    repo = DummySignalsRepo(db=None)
    monkeypatch.setattr(signals, "SignalsRepository", lambda db: repo)
    return repo


@pytest.fixture
def current_user():
    return DummyUser(id=42, email="test@example.com")


@pytest.fixture
def mock_ist_now(monkeypatch):
    fixed_time = datetime(2025, 1, 20, 12, 0, 0)

    def ist_now():
        return fixed_time

    monkeypatch.setattr(signals, "ist_now", ist_now)
    return fixed_time


# GET /buying-zone tests
def test_buying_zone_default_recent(signals_repo, current_user, mock_ist_now):
    signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    signals_repo.recent_items = [signal]

    result = signals.buying_zone(limit=100, status_filter="active", db=None, user=current_user)

    assert len(result) == 1
    assert result[0]["symbol"] == "RELIANCE.NS"
    assert result[0]["status"] == "active"
    assert len(signals_repo.recent_called) == 1
    assert signals_repo.recent_called[0] == (100, False)


def test_buying_zone_today_filter(signals_repo, current_user, mock_ist_now):
    signal = DummySignal(id=1, symbol="TCS.NS", status=SignalStatus.ACTIVE)
    today = mock_ist_now.date()
    signals_repo.by_date_items[today] = [signal]

    result = signals.buying_zone(
        limit=100, date_filter="today", status_filter="active", db=None, user=current_user
    )

    assert len(result) == 1
    assert result[0]["symbol"] == "TCS.NS"
    assert len(signals_repo.by_date_called) == 1
    assert signals_repo.by_date_called[0][0] == today


def test_buying_zone_yesterday_filter(signals_repo, current_user, mock_ist_now):
    signal = DummySignal(id=1, symbol="INFY.NS", status=SignalStatus.ACTIVE)
    yesterday = (mock_ist_now - timedelta(days=1)).date()
    signals_repo.by_date_items[yesterday] = [signal]

    result = signals.buying_zone(
        limit=100, date_filter="yesterday", status_filter="active", db=None, user=current_user
    )

    assert len(result) == 1
    assert result[0]["symbol"] == "INFY.NS"
    assert len(signals_repo.by_date_called) == 1
    assert signals_repo.by_date_called[0][0] == yesterday


def test_buying_zone_last_10_days_filter(signals_repo, current_user, mock_ist_now):
    signal = DummySignal(id=1, symbol="WIPRO.NS", status=SignalStatus.ACTIVE)
    signals_repo.last_n_dates_items = [signal]

    result = signals.buying_zone(
        limit=100, date_filter="last_10_days", status_filter="active", db=None, user=current_user
    )

    assert len(result) == 1
    assert result[0]["symbol"] == "WIPRO.NS"
    assert len(signals_repo.last_n_dates_called) == 1
    assert signals_repo.last_n_dates_called[0] == (10, 100)


def test_buying_zone_status_filter_active(signals_repo, current_user):
    active_signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    expired_signal = DummySignal(id=2, symbol="TCS.NS", status=SignalStatus.EXPIRED)
    signals_repo.recent_items = [active_signal, expired_signal]

    result = signals.buying_zone(limit=100, status_filter="active", db=None, user=current_user)

    assert len(result) == 1
    assert result[0]["status"] == "active"
    assert result[0]["symbol"] == "RELIANCE.NS"


def test_buying_zone_status_filter_expired(signals_repo, current_user):
    active_signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    expired_signal = DummySignal(id=2, symbol="TCS.NS", status=SignalStatus.EXPIRED)
    signals_repo.recent_items = [active_signal, expired_signal]

    result = signals.buying_zone(limit=100, status_filter="expired", db=None, user=current_user)

    assert len(result) == 1
    assert result[0]["status"] == "expired"
    assert result[0]["symbol"] == "TCS.NS"


def test_buying_zone_status_filter_all(signals_repo, current_user):
    active_signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    expired_signal = DummySignal(id=2, symbol="TCS.NS", status=SignalStatus.EXPIRED)
    traded_signal = DummySignal(id=3, symbol="INFY.NS", status=SignalStatus.TRADED)
    signals_repo.recent_items = [active_signal, expired_signal, traded_signal]

    result = signals.buying_zone(limit=100, status_filter="all", db=None, user=current_user)

    assert len(result) == 3  # All signals returned


def test_buying_zone_status_filter_invalid_ignored(signals_repo, current_user):
    signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    signals_repo.recent_items = [signal]

    result = signals.buying_zone(
        limit=100, status_filter="invalid_status", db=None, user=current_user
    )

    # Invalid status filter is ignored, returns all
    assert len(result) == 1


def test_buying_zone_custom_limit(signals_repo, current_user):
    signals_repo.recent_items = [DummySignal(id=i) for i in range(50)]

    result = signals.buying_zone(limit=25, status_filter="active", db=None, user=current_user)

    assert len(result) == 50  # Returns all items from repo (limit applied at repo level)
    assert signals_repo.recent_called[0][0] == 25


def test_buying_zone_combined_filters(signals_repo, current_user, mock_ist_now):
    active_signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    expired_signal = DummySignal(id=2, symbol="TCS.NS", status=SignalStatus.EXPIRED)
    today = mock_ist_now.date()
    signals_repo.by_date_items[today] = [active_signal, expired_signal]

    result = signals.buying_zone(
        limit=100, date_filter="today", status_filter="active", db=None, user=current_user
    )

    assert len(result) == 1
    assert result[0]["status"] == "active"


def test_buying_zone_empty_result(signals_repo, current_user):
    signals_repo.recent_items = []

    result = signals.buying_zone(limit=100, status_filter="active", db=None, user=current_user)

    assert len(result) == 0
    assert result == []


def test_buying_zone_maps_all_fields(signals_repo, current_user):
    signal = DummySignal(
        id=1,
        symbol="RELIANCE.NS",
        status=SignalStatus.ACTIVE,
        ts=datetime(2025, 1, 15, 10, 30, 0),
        rsi10=25.5,
        ema9=2500.0,
        ema200=2400.0,
        distance_to_ema9=2.0,
        clean_chart=True,
        confidence=0.85,
        backtest_score=0.9,
        ml_verdict="buy",
        target=2600.0,
        pe=15.5,
        vol_ok=True,
        verdict="strong_buy",
    )
    signals_repo.recent_items = [signal]

    result = signals.buying_zone(limit=100, status_filter="active", db=None, user=current_user)

    assert len(result) == 1
    assert result[0]["id"] == 1
    assert result[0]["symbol"] == "RELIANCE.NS"
    assert result[0]["rsi10"] == 25.5
    assert result[0]["ema9"] == 2500.0
    assert result[0]["target"] == 2600.0
    assert result[0]["ts"] == "2025-01-15T10:30:00"


def test_buying_zone_handles_none_fields(signals_repo, current_user):
    signal = DummySignal(
        id=1,
        symbol="RELIANCE.NS",
        status=SignalStatus.ACTIVE,
        rsi10=None,
        ema9=None,
        target=None,
        ml_verdict=None,
    )
    signals_repo.recent_items = [signal]

    result = signals.buying_zone(limit=100, status_filter="active", db=None, user=current_user)

    assert len(result) == 1
    assert result[0]["rsi10"] is None
    assert result[0]["ema9"] is None
    assert result[0]["target"] is None
    assert result[0]["ml_verdict"] is None


# PATCH /signals/{symbol}/reject tests
def test_reject_signal_success(signals_repo, current_user):
    signals_repo.mark_rejected_result = True

    result = signals.reject_signal(symbol="RELIANCE.NS", db=None, user=current_user)

    assert result["message"] == "Signal for RELIANCE.NS marked as REJECTED"
    assert result["symbol"] == "RELIANCE.NS"
    assert result["status"] == "rejected"
    assert len(signals_repo.mark_rejected_called) == 1
    assert signals_repo.mark_rejected_called[0] == "RELIANCE.NS"


def test_reject_signal_not_found(signals_repo, current_user):
    signals_repo.mark_rejected_result = False

    with pytest.raises(HTTPException) as exc:
        signals.reject_signal(symbol="NONEXISTENT.NS", db=None, user=current_user)

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "No active signal found" in exc.value.detail
    assert "NONEXISTENT.NS" in exc.value.detail


# Additional edge case tests
def test_buying_zone_status_filter_traded(signals_repo, current_user):
    active_signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    traded_signal = DummySignal(id=2, symbol="TCS.NS", status=SignalStatus.TRADED)
    signals_repo.recent_items = [active_signal, traded_signal]

    result = signals.buying_zone(limit=100, status_filter="traded", db=None, user=current_user)

    assert len(result) == 1
    assert result[0]["status"] == "traded"


def test_buying_zone_status_filter_rejected(signals_repo, current_user):
    active_signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    rejected_signal = DummySignal(id=2, symbol="TCS.NS", status=SignalStatus.REJECTED)
    signals_repo.recent_items = [active_signal, rejected_signal]

    result = signals.buying_zone(limit=100, status_filter="rejected", db=None, user=current_user)

    assert len(result) == 1
    assert result[0]["status"] == "rejected"


def test_buying_zone_status_filter_case_insensitive(signals_repo, current_user):
    signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    signals_repo.recent_items = [signal]

    result = signals.buying_zone(limit=100, status_filter="ACTIVE", db=None, user=current_user)

    # Should work because status_filter.lower() is used
    assert len(result) == 1


def test_buying_zone_none_status_filter(signals_repo, current_user):
    signal = DummySignal(id=1, symbol="RELIANCE.NS", status=SignalStatus.ACTIVE)
    signals_repo.recent_items = [signal]

    result = signals.buying_zone(limit=100, status_filter=None, db=None, user=current_user)

    # None status filter means no filtering - all items returned
    assert len(result) == 1
