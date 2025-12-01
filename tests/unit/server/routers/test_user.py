from types import SimpleNamespace

import pytest

from server.app.routers import user
from src.infrastructure.db.models import TradeMode, UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummySettings(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            trade_mode=kwargs.get("trade_mode", TradeMode.PAPER),
            broker=kwargs.get("broker", None),
            broker_status=kwargs.get("broker_status", None),
            ui_preferences=kwargs.get("ui_preferences", None),
        )


class DummySettingsRepo:
    def __init__(self, db):
        self.db = db
        self.settings_by_user_id = {}
        self.ensure_default_called = []
        self.update_called = []
        self.get_ui_prefs_called = []
        self.update_ui_prefs_called = []

    def get_by_user_id(self, user_id):
        return self.settings_by_user_id.get(user_id)

    def ensure_default(self, user_id):
        self.ensure_default_called.append(user_id)
        if user_id in self.settings_by_user_id:
            return self.settings_by_user_id[user_id]
        # Create default if not exists
        settings = DummySettings(trade_mode=TradeMode.PAPER)
        self.settings_by_user_id[user_id] = settings
        return settings

    def update(
        self, settings, *, trade_mode=None, broker=None, broker_status=None, ui_preferences=None
    ):
        self.update_called.append((settings, trade_mode, broker, broker_status, ui_preferences))
        if trade_mode is not None:
            settings.trade_mode = trade_mode
        if broker is not None:
            settings.broker = broker
        if broker_status is not None:
            settings.broker_status = broker_status
        if ui_preferences is not None:
            settings.ui_preferences = ui_preferences
        return settings

    def get_ui_preferences(self, user_id):
        self.get_ui_prefs_called.append(user_id)
        settings = self.settings_by_user_id.get(user_id)
        if settings and settings.ui_preferences:
            return settings.ui_preferences
        return {}

    def update_ui_preferences(self, user_id, preferences):
        self.update_ui_prefs_called.append((user_id, preferences))
        settings = self.ensure_default(user_id)
        current_prefs = settings.ui_preferences or {}
        merged_prefs = {**current_prefs, **preferences}
        settings.ui_preferences = merged_prefs
        return merged_prefs


@pytest.fixture
def settings_repo(monkeypatch):
    repo = DummySettingsRepo(db=None)
    monkeypatch.setattr(user, "SettingsRepository", lambda db: repo)
    return repo


@pytest.fixture
def current_user():
    return DummyUser(id=42, email="test@example.com")


# GET /settings tests
def test_get_settings_existing(settings_repo, current_user):
    settings = DummySettings(
        trade_mode=TradeMode.BROKER, broker="kotak-neo", broker_status="connected"
    )
    settings_repo.settings_by_user_id[42] = settings

    result = user.get_settings(db=None, current=current_user)

    assert result.trade_mode == "broker"
    assert result.broker == "kotak-neo"
    assert result.broker_status == "connected"
    assert 42 in settings_repo.ensure_default_called


def test_get_settings_default_creation(settings_repo, current_user):
    # No existing settings, should create default
    result = user.get_settings(db=None, current=current_user)

    assert result.trade_mode == "paper"
    assert result.broker is None
    assert result.broker_status is None
    assert 42 in settings_repo.ensure_default_called
    assert 42 in settings_repo.settings_by_user_id


def test_get_settings_with_none_values(settings_repo, current_user):
    settings = DummySettings(trade_mode=TradeMode.PAPER, broker=None, broker_status=None)
    settings_repo.settings_by_user_id[42] = settings

    result = user.get_settings(db=None, current=current_user)

    assert result.trade_mode == "paper"
    assert result.broker is None
    assert result.broker_status is None


# PUT /settings tests
def test_update_settings_trade_mode(settings_repo, current_user):
    settings = DummySettings(trade_mode=TradeMode.PAPER)
    settings_repo.settings_by_user_id[42] = settings

    payload = user.SettingsUpdateRequest(trade_mode="broker")
    result = user.update_settings(payload, db=None, current=current_user)

    assert result.trade_mode == "broker"
    assert len(settings_repo.update_called) == 1
    call_args = settings_repo.update_called[0]
    assert call_args[1] == TradeMode.BROKER


def test_update_settings_broker(settings_repo, current_user):
    settings = DummySettings(trade_mode=TradeMode.BROKER)
    settings_repo.settings_by_user_id[42] = settings

    payload = user.SettingsUpdateRequest(broker="kotak-neo")
    result = user.update_settings(payload, db=None, current=current_user)

    assert result.broker == "kotak-neo"
    call_args = settings_repo.update_called[0]
    assert call_args[2] == "kotak-neo"


def test_update_settings_broker_status(settings_repo, current_user):
    settings = DummySettings(trade_mode=TradeMode.BROKER)
    settings_repo.settings_by_user_id[42] = settings

    payload = user.SettingsUpdateRequest(broker_status="connected")
    result = user.update_settings(payload, db=None, current=current_user)

    assert result.broker_status == "connected"
    call_args = settings_repo.update_called[0]
    assert call_args[3] == "connected"


def test_update_settings_all_fields(settings_repo, current_user):
    settings = DummySettings(trade_mode=TradeMode.PAPER)
    settings_repo.settings_by_user_id[42] = settings

    payload = user.SettingsUpdateRequest(
        trade_mode="broker", broker="kotak-neo", broker_status="connected"
    )
    result = user.update_settings(payload, db=None, current=current_user)

    assert result.trade_mode == "broker"
    assert result.broker == "kotak-neo"
    assert result.broker_status == "connected"


def test_update_settings_partial_update(settings_repo, current_user):
    settings = DummySettings(
        trade_mode=TradeMode.BROKER, broker="kotak-neo", broker_status="disconnected"
    )
    settings_repo.settings_by_user_id[42] = settings

    payload = user.SettingsUpdateRequest(broker_status="connected")  # Only update status
    result = user.update_settings(payload, db=None, current=current_user)

    assert result.trade_mode == "broker"  # Unchanged
    assert result.broker == "kotak-neo"  # Unchanged
    assert result.broker_status == "connected"  # Updated


def test_update_settings_none_trade_mode(settings_repo, current_user):
    settings = DummySettings(trade_mode=TradeMode.PAPER)
    settings_repo.settings_by_user_id[42] = settings

    payload = user.SettingsUpdateRequest(trade_mode=None, broker="kotak-neo")
    result = user.update_settings(payload, db=None, current=current_user)

    # Trade mode should remain unchanged when None
    call_args = settings_repo.update_called[0]
    assert call_args[1] is None  # trade_mode is None
    assert call_args[2] == "kotak-neo"  # broker is updated


def test_update_settings_creates_default_if_missing(settings_repo, current_user):
    # No existing settings
    payload = user.SettingsUpdateRequest(trade_mode="broker")
    result = user.update_settings(payload, db=None, current=current_user)

    assert result.trade_mode == "broker"
    assert 42 in settings_repo.ensure_default_called


def test_update_settings_paper_mode(settings_repo, current_user):
    settings = DummySettings(trade_mode=TradeMode.BROKER)
    settings_repo.settings_by_user_id[42] = settings

    payload = user.SettingsUpdateRequest(trade_mode="paper")
    result = user.update_settings(payload, db=None, current=current_user)

    assert result.trade_mode == "paper"
    call_args = settings_repo.update_called[0]
    assert call_args[1] == TradeMode.PAPER


# GET /buying-zone-columns tests
def test_get_buying_zone_columns_existing(settings_repo, current_user):
    settings = DummySettings(ui_preferences={"buying_zone_columns": ["symbol", "price", "rsi"]})
    settings_repo.settings_by_user_id[42] = settings

    result = user.get_buying_zone_columns(db=None, current=current_user)

    assert result.columns == ["symbol", "price", "rsi"]
    assert 42 in settings_repo.get_ui_prefs_called


def test_get_buying_zone_columns_default(settings_repo, current_user):
    # No UI preferences set
    settings = DummySettings(ui_preferences=None)
    settings_repo.settings_by_user_id[42] = settings

    result = user.get_buying_zone_columns(db=None, current=current_user)

    assert result.columns == []


def test_get_buying_zone_columns_missing_key(settings_repo, current_user):
    # UI preferences exist but no buying_zone_columns key
    settings = DummySettings(ui_preferences={"other_pref": "value"})
    settings_repo.settings_by_user_id[42] = settings

    result = user.get_buying_zone_columns(db=None, current=current_user)

    assert result.columns == []


def test_get_buying_zone_columns_empty_list(settings_repo, current_user):
    settings = DummySettings(ui_preferences={"buying_zone_columns": []})
    settings_repo.settings_by_user_id[42] = settings

    result = user.get_buying_zone_columns(db=None, current=current_user)

    assert result.columns == []


# PUT /buying-zone-columns tests
def test_update_buying_zone_columns_success(settings_repo, current_user):
    settings = DummySettings(ui_preferences={})
    settings_repo.settings_by_user_id[42] = settings

    payload = user.BuyingZoneColumnsRequest(columns=["symbol", "price", "rsi", "volume"])
    result = user.update_buying_zone_columns(payload, db=None, current=current_user)

    assert result.columns == ["symbol", "price", "rsi", "volume"]
    assert len(settings_repo.update_ui_prefs_called) == 1
    assert settings_repo.update_ui_prefs_called[0][0] == 42
    assert settings_repo.update_ui_prefs_called[0][1] == {
        "buying_zone_columns": ["symbol", "price", "rsi", "volume"]
    }


def test_update_buying_zone_columns_merges_existing(settings_repo, current_user):
    settings = DummySettings(
        ui_preferences={"buying_zone_columns": ["symbol"], "other_pref": "value"}
    )
    settings_repo.settings_by_user_id[42] = settings

    payload = user.BuyingZoneColumnsRequest(columns=["symbol", "price"])
    result = user.update_buying_zone_columns(payload, db=None, current=current_user)

    assert result.columns == ["symbol", "price"]
    # Verify existing preferences are preserved
    call_args = settings_repo.update_ui_prefs_called[0]
    merged = call_args[1]
    assert merged["buying_zone_columns"] == ["symbol", "price"]


def test_update_buying_zone_columns_empty_list(settings_repo, current_user):
    settings = DummySettings(ui_preferences={"buying_zone_columns": ["symbol", "price"]})
    settings_repo.settings_by_user_id[42] = settings

    payload = user.BuyingZoneColumnsRequest(columns=[])
    result = user.update_buying_zone_columns(payload, db=None, current=current_user)

    assert result.columns == []


def test_update_buying_zone_columns_creates_default_if_missing(settings_repo, current_user):
    # No existing settings
    payload = user.BuyingZoneColumnsRequest(columns=["symbol"])
    result = user.update_buying_zone_columns(payload, db=None, current=current_user)

    assert result.columns == ["symbol"]
    assert 42 in settings_repo.ensure_default_called


def test_update_buying_zone_columns_exception_handling(settings_repo, current_user, monkeypatch):
    def boom(user_id, preferences):
        raise RuntimeError("Database error")

    settings_repo.update_ui_preferences = boom
    payload = user.BuyingZoneColumnsRequest(columns=["symbol"])

    with pytest.raises(RuntimeError):
        user.update_buying_zone_columns(payload, db=None, current=current_user)


def test_update_buying_zone_columns_single_column(settings_repo, current_user):
    settings = DummySettings(ui_preferences={})
    settings_repo.settings_by_user_id[42] = settings

    payload = user.BuyingZoneColumnsRequest(columns=["symbol"])
    result = user.update_buying_zone_columns(payload, db=None, current=current_user)

    assert result.columns == ["symbol"]


def test_update_buying_zone_columns_overwrites_existing(settings_repo, current_user):
    settings = DummySettings(ui_preferences={"buying_zone_columns": ["old1", "old2"]})
    settings_repo.settings_by_user_id[42] = settings

    payload = user.BuyingZoneColumnsRequest(columns=["new1", "new2", "new3"])
    result = user.update_buying_zone_columns(payload, db=None, current=current_user)

    assert result.columns == ["new1", "new2", "new3"]
    # Verify old columns are replaced, not merged
    assert "old1" not in result.columns
