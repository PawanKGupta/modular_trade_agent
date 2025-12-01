from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from server.app.routers import trading_config
from server.app.schemas.trading_config import TradingConfigUpdateRequest
from src.infrastructure.db.models import UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummyTradingConfig(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            user_id=kwargs.get("user_id", 1),
            # RSI Configuration
            rsi_period=kwargs.get("rsi_period", 10),
            rsi_oversold=kwargs.get("rsi_oversold", 30.0),
            rsi_extreme_oversold=kwargs.get("rsi_extreme_oversold", 20.0),
            rsi_near_oversold=kwargs.get("rsi_near_oversold", 40.0),
            # Capital & Position Management
            user_capital=kwargs.get("user_capital", 100000.0),
            paper_trading_initial_capital=kwargs.get("paper_trading_initial_capital", 1000000.0),
            max_portfolio_size=kwargs.get("max_portfolio_size", 6),
            max_position_volume_ratio=kwargs.get("max_position_volume_ratio", 0.10),
            min_absolute_avg_volume=kwargs.get("min_absolute_avg_volume", 10000),
            # Chart Quality Filters
            chart_quality_enabled=kwargs.get("chart_quality_enabled", True),
            chart_quality_min_score=kwargs.get("chart_quality_min_score", 50.0),
            chart_quality_max_gap_frequency=kwargs.get("chart_quality_max_gap_frequency", 25.0),
            chart_quality_min_daily_range_pct=kwargs.get("chart_quality_min_daily_range_pct", 1.0),
            chart_quality_max_extreme_candle_frequency=kwargs.get(
                "chart_quality_max_extreme_candle_frequency", 20.0
            ),
            # Risk Management
            default_stop_loss_pct=kwargs.get("default_stop_loss_pct", None),
            tight_stop_loss_pct=kwargs.get("tight_stop_loss_pct", None),
            min_stop_loss_pct=kwargs.get("min_stop_loss_pct", None),
            default_target_pct=kwargs.get("default_target_pct", 0.10),
            strong_buy_target_pct=kwargs.get("strong_buy_target_pct", 0.12),
            excellent_target_pct=kwargs.get("excellent_target_pct", 0.15),
            # Risk-Reward Ratios
            strong_buy_risk_reward=kwargs.get("strong_buy_risk_reward", 3.0),
            buy_risk_reward=kwargs.get("buy_risk_reward", 2.5),
            excellent_risk_reward=kwargs.get("excellent_risk_reward", 3.5),
            # Order Defaults
            default_exchange=kwargs.get("default_exchange", "NSE"),
            default_product=kwargs.get("default_product", "CNC"),
            default_order_type=kwargs.get("default_order_type", "MARKET"),
            default_variety=kwargs.get("default_variety", "AMO"),
            default_validity=kwargs.get("default_validity", "DAY"),
            # Behavior Toggles
            allow_duplicate_recommendations_same_day=kwargs.get(
                "allow_duplicate_recommendations_same_day", False
            ),
            exit_on_ema9_or_rsi50=kwargs.get("exit_on_ema9_or_rsi50", True),
            min_combined_score=kwargs.get("min_combined_score", 25),
            enable_premarket_amo_adjustment=kwargs.get("enable_premarket_amo_adjustment", True),
            # News Sentiment
            news_sentiment_enabled=kwargs.get("news_sentiment_enabled", True),
            news_sentiment_lookback_days=kwargs.get("news_sentiment_lookback_days", 30),
            news_sentiment_min_articles=kwargs.get("news_sentiment_min_articles", 2),
            news_sentiment_pos_threshold=kwargs.get("news_sentiment_pos_threshold", 0.25),
            news_sentiment_neg_threshold=kwargs.get("news_sentiment_neg_threshold", -0.25),
            # ML Configuration
            ml_enabled=kwargs.get("ml_enabled", False),
            ml_model_version=kwargs.get("ml_model_version", None),
            ml_confidence_threshold=kwargs.get("ml_confidence_threshold", 0.5),
            ml_combine_with_rules=kwargs.get("ml_combine_with_rules", True),
        )


class DummyTradingConfigRepo:
    def __init__(self, db):
        self.db = db
        self.configs_by_user = {}
        self.get_or_create_called = []
        self.update_called = []
        self.reset_called = []

    def get_or_create_default(self, user_id):
        self.get_or_create_called.append(user_id)
        if user_id in self.configs_by_user:
            return self.configs_by_user[user_id]
        # Create default config
        config = DummyTradingConfig(user_id=user_id)
        self.configs_by_user[user_id] = config
        return config

    def update(self, user_id, **kwargs):
        self.update_called.append((user_id, kwargs))
        config = self.configs_by_user.get(user_id)
        if not config:
            config = DummyTradingConfig(user_id=user_id)
            self.configs_by_user[user_id] = config
        # Update fields
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config

    def reset_to_defaults(self, user_id):
        self.reset_called.append(user_id)
        # Delete existing and create new
        if user_id in self.configs_by_user:
            del self.configs_by_user[user_id]
        return self.get_or_create_default(user_id)


@pytest.fixture
def trading_config_repo(monkeypatch):
    repo = DummyTradingConfigRepo(db=None)
    monkeypatch.setattr(trading_config, "UserTradingConfigRepository", lambda db: repo)
    return repo


@pytest.fixture
def current_user():
    return DummyUser(id=42, email="test@example.com")


# GET /trading-config tests
def test_get_trading_config_existing(trading_config_repo, current_user):
    """Test get_trading_config with existing config"""
    config = DummyTradingConfig(user_id=42, rsi_period=14, user_capital=200000.0, ml_enabled=True)
    trading_config_repo.configs_by_user[42] = config

    result = trading_config.get_trading_config(db=None, current=current_user)

    assert result.rsi_period == 14
    assert result.user_capital == 200000.0
    assert result.ml_enabled is True
    assert len(trading_config_repo.get_or_create_called) == 1
    assert trading_config_repo.get_or_create_called[0] == 42


def test_get_trading_config_creates_default(trading_config_repo, current_user):
    """Test get_trading_config creates default config if not exists"""
    result = trading_config.get_trading_config(db=None, current=current_user)

    assert result.rsi_period == 10  # Default value
    assert result.user_capital == 100000.0  # Default value
    assert len(trading_config_repo.get_or_create_called) == 1
    assert 42 in trading_config_repo.configs_by_user


def test_get_trading_config_maps_all_fields(trading_config_repo, current_user):
    """Test that all config fields are mapped correctly"""
    config = DummyTradingConfig(
        user_id=42,
        rsi_period=14,
        rsi_oversold=25.0,
        rsi_extreme_oversold=15.0,
        rsi_near_oversold=35.0,
        user_capital=500000.0,
        paper_trading_initial_capital=2000000.0,
        max_portfolio_size=10,
        ml_model_version="v2.0",
    )
    trading_config_repo.configs_by_user[42] = config

    result = trading_config.get_trading_config(db=None, current=current_user)

    assert result.rsi_period == 14
    assert result.rsi_oversold == 25.0
    assert result.user_capital == 500000.0
    assert result.ml_model_version == "v2.0"


def test_get_trading_config_handles_default_paper_trading_capital(
    trading_config_repo, current_user
):
    """Test that paper_trading_initial_capital defaults correctly"""
    config = DummyTradingConfig(user_id=42)
    # Remove paper_trading_initial_capital to test default
    delattr(config, "paper_trading_initial_capital")
    trading_config_repo.configs_by_user[42] = config

    result = trading_config.get_trading_config(db=None, current=current_user)

    assert result.paper_trading_initial_capital == 1000000.0


def test_get_trading_config_handles_default_premarket_amo(trading_config_repo, current_user):
    """Test that enable_premarket_amo_adjustment defaults correctly"""
    config = DummyTradingConfig(user_id=42)
    # Remove enable_premarket_amo_adjustment to test default
    delattr(config, "enable_premarket_amo_adjustment")
    trading_config_repo.configs_by_user[42] = config

    result = trading_config.get_trading_config(db=None, current=current_user)

    assert result.enable_premarket_amo_adjustment is True


# PUT /trading-config tests
def test_update_trading_config_success(trading_config_repo, current_user):
    """Test update_trading_config with valid values"""
    config = DummyTradingConfig(user_id=42)
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(rsi_period=14, user_capital=200000.0)

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.rsi_period == 14
    assert result.user_capital == 200000.0
    assert len(trading_config_repo.update_called) == 1
    assert trading_config_repo.update_called[0][0] == 42
    assert trading_config_repo.update_called[0][1]["rsi_period"] == 14


def test_update_trading_config_partial_update(trading_config_repo, current_user):
    """Test update_trading_config with partial update"""
    config = DummyTradingConfig(user_id=42, rsi_period=10, user_capital=100000.0)
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(rsi_period=14)

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.rsi_period == 14
    assert result.user_capital == 100000.0  # Unchanged
    assert len(trading_config_repo.update_called) == 1


def test_update_trading_config_creates_if_missing(trading_config_repo, current_user):
    """Test update_trading_config creates config if not exists"""
    payload = TradingConfigUpdateRequest(rsi_period=14)

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.rsi_period == 14
    assert len(trading_config_repo.get_or_create_called) == 1
    assert len(trading_config_repo.update_called) == 1


def test_update_trading_config_rsi_validation_pass(trading_config_repo, current_user):
    """Test RSI threshold validation passes with correct order"""
    config = DummyTradingConfig(
        user_id=42,
        rsi_extreme_oversold=20.0,
        rsi_oversold=30.0,
        rsi_near_oversold=40.0,
    )
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(
        rsi_extreme_oversold=15.0,
        rsi_oversold=25.0,
        rsi_near_oversold=35.0,
    )

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.rsi_extreme_oversold == 15.0
    assert result.rsi_oversold == 25.0
    assert result.rsi_near_oversold == 35.0


def test_update_trading_config_rsi_validation_fail_wrong_order(trading_config_repo, current_user):
    """Test RSI threshold validation fails with wrong order"""
    config = DummyTradingConfig(
        user_id=42,
        rsi_extreme_oversold=20.0,
        rsi_oversold=30.0,
        rsi_near_oversold=40.0,
    )
    trading_config_repo.configs_by_user[42] = config

    # Use values within Pydantic constraints but wrong order
    # rsi_extreme_oversold max is 30, rsi_oversold max is 50, but extreme < oversold < near
    # Current: extreme=20, oversold=30, near=40
    # Try to set oversold < extreme (wrong order)
    payload = TradingConfigUpdateRequest(
        rsi_extreme_oversold=25.0,  # Valid: 0-30
        rsi_oversold=20.0,  # Valid: 0-50, but < extreme (wrong order!)
    )

    with pytest.raises(HTTPException) as exc:
        trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "RSI thresholds must be in order" in exc.value.detail


def test_update_trading_config_rsi_validation_fail_equal_values(trading_config_repo, current_user):
    """Test RSI threshold validation fails with equal values"""
    config = DummyTradingConfig(
        user_id=42,
        rsi_extreme_oversold=20.0,
        rsi_oversold=30.0,
        rsi_near_oversold=40.0,
    )
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(
        rsi_extreme_oversold=25.0,
        rsi_oversold=25.0,  # Equal to extreme
        rsi_near_oversold=35.0,
    )

    with pytest.raises(HTTPException) as exc:
        trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "RSI thresholds must be in order" in exc.value.detail


def test_update_trading_config_rsi_validation_partial_update(trading_config_repo, current_user):
    """Test RSI threshold validation with partial update (uses current values)"""
    config = DummyTradingConfig(
        user_id=42,
        rsi_extreme_oversold=20.0,
        rsi_oversold=30.0,
        rsi_near_oversold=40.0,
    )
    trading_config_repo.configs_by_user[42] = config

    # Only update oversold, should validate against existing extreme and near
    payload = TradingConfigUpdateRequest(rsi_oversold=25.0)

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.rsi_oversold == 25.0
    assert result.rsi_extreme_oversold == 20.0  # Unchanged
    assert result.rsi_near_oversold == 40.0  # Unchanged


def test_update_trading_config_rsi_validation_partial_invalid(trading_config_repo, current_user):
    """Test RSI threshold validation fails with partial update creating invalid order"""
    config = DummyTradingConfig(
        user_id=42,
        rsi_extreme_oversold=20.0,
        rsi_oversold=30.0,
        rsi_near_oversold=40.0,
    )
    trading_config_repo.configs_by_user[42] = config

    # Try to set oversold to be greater than near_oversold
    payload = TradingConfigUpdateRequest(rsi_oversold=50.0)

    with pytest.raises(HTTPException) as exc:
        trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "RSI thresholds must be in order" in exc.value.detail


def test_update_trading_config_stop_loss_validation_pass(trading_config_repo, current_user):
    """Test stop loss validation passes with correct order"""
    config = DummyTradingConfig(
        user_id=42,
        min_stop_loss_pct=0.02,
        tight_stop_loss_pct=0.03,
        default_stop_loss_pct=0.05,
    )
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(
        min_stop_loss_pct=0.01,
        tight_stop_loss_pct=0.02,
        default_stop_loss_pct=0.04,
    )

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.min_stop_loss_pct == 0.01
    assert result.tight_stop_loss_pct == 0.02
    assert result.default_stop_loss_pct == 0.04


def test_update_trading_config_stop_loss_validation_fail(trading_config_repo, current_user):
    """Test stop loss validation fails with wrong order"""
    config = DummyTradingConfig(
        user_id=42,
        min_stop_loss_pct=0.02,
        tight_stop_loss_pct=0.03,
        default_stop_loss_pct=0.05,
    )
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(
        min_stop_loss_pct=0.05,  # Wrong: should be < tight
        tight_stop_loss_pct=0.03,
        default_stop_loss_pct=0.02,  # Wrong: should be > tight
    )

    with pytest.raises(HTTPException) as exc:
        trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Stop loss percentages must be in order" in exc.value.detail


def test_update_trading_config_stop_loss_partial_update_no_validation(
    trading_config_repo, current_user
):
    """Test stop loss validation only runs when all three are provided"""
    config = DummyTradingConfig(
        user_id=42,
        min_stop_loss_pct=0.02,
        tight_stop_loss_pct=0.03,
        default_stop_loss_pct=0.05,
    )
    trading_config_repo.configs_by_user[42] = config

    # Only update one stop loss - validation should not run
    payload = TradingConfigUpdateRequest(default_stop_loss_pct=0.10)

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.default_stop_loss_pct == 0.10
    # Validation should not have run since not all three were provided


def test_update_trading_config_excludes_none_values(trading_config_repo, current_user):
    """Test that None values are excluded from update"""
    config = DummyTradingConfig(user_id=42, rsi_period=10)
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(
        rsi_period=14,
        user_capital=None,  # Should be excluded
        ml_enabled=None,  # Should be excluded
    )

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.rsi_period == 14
    update_kwargs = trading_config_repo.update_called[0][1]
    assert "user_capital" not in update_kwargs
    assert "ml_enabled" not in update_kwargs


def test_update_trading_config_multiple_fields(trading_config_repo, current_user):
    """Test update_trading_config with multiple fields"""
    config = DummyTradingConfig(user_id=42)
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(
        rsi_period=14,
        user_capital=500000.0,
        max_portfolio_size=10,
        ml_enabled=True,
        chart_quality_enabled=False,
    )

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.rsi_period == 14
    assert result.user_capital == 500000.0
    assert result.max_portfolio_size == 10
    assert result.ml_enabled is True
    assert result.chart_quality_enabled is False


# POST /trading-config/reset tests
def test_reset_trading_config_existing(trading_config_repo, current_user):
    """Test reset_trading_config with existing config"""
    config = DummyTradingConfig(user_id=42, rsi_period=14, user_capital=200000.0)
    trading_config_repo.configs_by_user[42] = config

    result = trading_config.reset_trading_config(db=None, current=current_user)

    assert result.rsi_period == 10  # Default value
    assert result.user_capital == 100000.0  # Default value
    assert len(trading_config_repo.reset_called) == 1
    assert trading_config_repo.reset_called[0] == 42


def test_reset_trading_config_no_existing(trading_config_repo, current_user):
    """Test reset_trading_config creates default if no existing config"""
    result = trading_config.reset_trading_config(db=None, current=current_user)

    assert result.rsi_period == 10  # Default value
    assert result.user_capital == 100000.0  # Default value
    assert len(trading_config_repo.reset_called) == 1


def test_reset_trading_config_creates_new_instance(trading_config_repo, current_user):
    """Test reset_trading_config creates a new config instance"""
    old_config = DummyTradingConfig(user_id=42, id=1, rsi_period=14)
    trading_config_repo.configs_by_user[42] = old_config

    result = trading_config.reset_trading_config(db=None, current=current_user)

    # Config should be reset to defaults
    assert result.rsi_period == 10
    assert len(trading_config_repo.reset_called) == 1


# Edge cases
def test_update_trading_config_empty_payload(trading_config_repo, current_user):
    """Test update_trading_config with empty payload"""
    config = DummyTradingConfig(user_id=42, rsi_period=10)
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest()

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    # Should return unchanged config
    assert result.rsi_period == 10
    assert len(trading_config_repo.update_called) == 1
    # Update dict should be empty or only contain None values (excluded)
    update_kwargs = trading_config_repo.update_called[0][1]
    assert len(update_kwargs) == 0 or all(v is None for v in update_kwargs.values())


def test_update_trading_config_rsi_all_none_uses_current(trading_config_repo, current_user):
    """Test RSI validation when all RSI fields are None (uses current values)"""
    config = DummyTradingConfig(
        user_id=42,
        rsi_extreme_oversold=20.0,
        rsi_oversold=30.0,
        rsi_near_oversold=40.0,
    )
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(user_capital=200000.0)

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.user_capital == 200000.0
    # RSI values should remain unchanged
    assert result.rsi_extreme_oversold == 20.0
    assert result.rsi_oversold == 30.0
    assert result.rsi_near_oversold == 40.0


def test_config_to_response_handles_all_fields(trading_config_repo, current_user):
    """Test that _config_to_response handles all config fields"""
    config = DummyTradingConfig(
        user_id=42,
        rsi_period=14,
        default_stop_loss_pct=0.05,
        ml_model_version="v1.0",
        enable_premarket_amo_adjustment=True,
    )
    trading_config_repo.configs_by_user[42] = config

    result = trading_config.get_trading_config(db=None, current=current_user)

    # Verify all major field categories are present
    assert hasattr(result, "rsi_period")
    assert hasattr(result, "user_capital")
    assert hasattr(result, "chart_quality_enabled")
    assert hasattr(result, "default_stop_loss_pct")
    assert hasattr(result, "default_exchange")
    assert hasattr(result, "ml_enabled")
    assert hasattr(result, "news_sentiment_enabled")


def test_update_trading_config_stop_loss_all_none_no_validation(trading_config_repo, current_user):
    """Test stop loss validation doesn't run when all are None"""
    config = DummyTradingConfig(
        user_id=42,
        default_stop_loss_pct=None,
        tight_stop_loss_pct=None,
        min_stop_loss_pct=None,
    )
    trading_config_repo.configs_by_user[42] = config

    payload = TradingConfigUpdateRequest(user_capital=200000.0)

    result = trading_config.update_trading_config(payload=payload, db=None, current=current_user)

    assert result.user_capital == 200000.0
    # Should not raise validation error since not all stop loss fields are provided
