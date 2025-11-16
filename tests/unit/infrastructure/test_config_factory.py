"""Unit tests for configuration factory (Phase 1.4)

Tests cover:
- create_default_user_config
- db_config_to_strategy_config
- Configuration conversion accuracy
"""

import pytest

from config.strategy_config import StrategyConfig
from src.infrastructure.db.models import UserRole, Users, UserTradingConfig
from src.infrastructure.persistence.config_factory import (
    create_default_user_config,
    db_config_to_strategy_config,
)


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="hashed_password",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestConfigFactory:
    """Tests for configuration factory functions"""

    def test_create_default_user_config(self, sample_user):
        """Test creating default user config from StrategyConfig"""
        config = create_default_user_config(sample_user.id)

        assert config.user_id == sample_user.id
        # Verify RSI defaults
        assert config.rsi_period == 10
        assert config.rsi_oversold == 30.0
        assert config.rsi_extreme_oversold == 20.0
        assert config.rsi_near_oversold == 40.0
        # Verify capital defaults
        assert config.user_capital == 200000.0
        assert config.max_portfolio_size == 6
        # Verify chart quality defaults
        assert config.chart_quality_enabled is True
        assert config.chart_quality_min_score == 50.0
        # Verify order defaults
        assert config.default_exchange == "NSE"
        assert config.default_product == "CNC"
        assert config.default_order_type == "MARKET"
        assert config.default_variety == "AMO"
        # Verify ML defaults
        assert config.ml_enabled is False
        assert config.ml_confidence_threshold == 0.5

    def test_create_default_config_matches_strategy_config(self, sample_user):
        """Test that default config matches StrategyConfig.default()"""
        strategy_config = StrategyConfig.default()
        db_config = create_default_user_config(sample_user.id)

        # Compare matching fields
        assert db_config.rsi_period == strategy_config.rsi_period
        assert db_config.rsi_oversold == strategy_config.rsi_oversold
        assert db_config.rsi_extreme_oversold == strategy_config.rsi_extreme_oversold
        assert db_config.rsi_near_oversold == strategy_config.rsi_near_oversold
        assert db_config.user_capital == strategy_config.user_capital
        assert db_config.max_position_volume_ratio == strategy_config.max_position_volume_ratio
        assert db_config.min_absolute_avg_volume == strategy_config.min_absolute_avg_volume
        assert db_config.chart_quality_enabled == strategy_config.chart_quality_enabled
        assert db_config.chart_quality_min_score == strategy_config.chart_quality_min_score
        assert db_config.default_target_pct == strategy_config.default_target_pct
        assert db_config.strong_buy_target_pct == strategy_config.strong_buy_target_pct
        assert db_config.excellent_target_pct == strategy_config.excellent_target_pct

    def test_db_config_to_strategy_config(self, db_session, sample_user):
        """Test converting UserTradingConfig to StrategyConfig"""
        # Create a config with custom values
        db_config = UserTradingConfig(
            user_id=sample_user.id,
            rsi_period=14,
            rsi_oversold=35.0,
            user_capital=300000.0,
            chart_quality_min_score=60.0,
        )
        db_session.add(db_config)
        db_session.commit()
        db_session.refresh(db_config)

        strategy_config = db_config_to_strategy_config(db_config)

        assert strategy_config.rsi_period == 14
        assert strategy_config.rsi_oversold == 35.0
        assert strategy_config.user_capital == 300000.0
        assert strategy_config.chart_quality_min_score == 60.0
        # Verify defaults for fields not in UserTradingConfig
        assert strategy_config.min_volume_multiplier == 1.0
        assert strategy_config.volume_multiplier_for_strong == 1.2
        assert strategy_config.volume_lookback_days == 50

    def test_round_trip_conversion(self, db_session, sample_user):
        """Test that config can be converted back and forth"""
        # Create default config
        original_db_config = create_default_user_config(sample_user.id)
        db_session.add(original_db_config)
        db_session.commit()
        db_session.refresh(original_db_config)

        # Convert to StrategyConfig
        strategy_config = db_config_to_strategy_config(original_db_config)

        # Verify key fields match
        assert strategy_config.rsi_period == original_db_config.rsi_period
        assert strategy_config.rsi_oversold == original_db_config.rsi_oversold
        assert strategy_config.user_capital == original_db_config.user_capital
        assert strategy_config.chart_quality_enabled == original_db_config.chart_quality_enabled

    def test_config_with_custom_values(self, db_session, sample_user):
        """Test creating config with custom values"""
        db_config = UserTradingConfig(
            user_id=sample_user.id,
            rsi_period=20,
            rsi_oversold=25.0,
            rsi_extreme_oversold=15.0,
            rsi_near_oversold=35.0,
            user_capital=500000.0,
            max_portfolio_size=10,
            chart_quality_enabled=False,
            default_stop_loss_pct=0.05,
            ml_enabled=True,
            ml_confidence_threshold=0.7,
        )
        db_session.add(db_config)
        db_session.commit()
        db_session.refresh(db_config)

        strategy_config = db_config_to_strategy_config(db_config)

        assert strategy_config.rsi_period == 20
        assert strategy_config.rsi_oversold == 25.0
        assert strategy_config.user_capital == 500000.0
        assert strategy_config.chart_quality_enabled is False
        assert strategy_config.ml_enabled is True
        assert strategy_config.ml_confidence_threshold == 0.7
