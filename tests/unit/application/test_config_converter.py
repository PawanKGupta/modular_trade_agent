"""
Unit tests for Config Converter

Tests for converting UserTradingConfig to StrategyConfig.
"""

import pytest

from config.strategy_config import StrategyConfig
from src.application.services.config_converter import user_config_to_strategy_config
from src.infrastructure.db.models import UserTradingConfig
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def sample_user_config(db_session):
    """Create a sample UserTradingConfig"""
    from src.infrastructure.db.models import Users

    user = Users(
        email="test@example.com",
        password_hash="hash",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()

    config = UserTradingConfig(
        user_id=user.id,
        rsi_period=14,
        rsi_oversold=25.0,
        rsi_extreme_oversold=15.0,
        rsi_near_oversold=35.0,
        user_capital=300000.0,
        max_portfolio_size=8,
        max_position_volume_ratio=0.12,
        min_absolute_avg_volume=15000,
        chart_quality_enabled=True,
        chart_quality_min_score=55.0,
        chart_quality_max_gap_frequency=30.0,
        chart_quality_min_daily_range_pct=1.2,
        chart_quality_max_extreme_candle_frequency=25.0,
        default_stop_loss_pct=0.10,
        tight_stop_loss_pct=0.07,
        min_stop_loss_pct=0.04,
        default_target_pct=0.12,
        strong_buy_target_pct=0.14,
        excellent_target_pct=0.18,
        strong_buy_risk_reward=3.5,
        buy_risk_reward=2.8,
        excellent_risk_reward=4.0,
        news_sentiment_enabled=True,
        news_sentiment_lookback_days=45,
        news_sentiment_min_articles=3,
        news_sentiment_pos_threshold=0.30,
        news_sentiment_neg_threshold=-0.30,
    )
    db_session.add(config)
    db_session.commit()
    return config


class TestConfigConverter:
    """Tests for config converter"""

    def test_basic_conversion(self, sample_user_config):
        """Test basic config conversion"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert isinstance(strategy_config, StrategyConfig)
        assert strategy_config.rsi_period == 14
        assert strategy_config.rsi_oversold == 25.0
        assert strategy_config.user_capital == 300000.0

    def test_rsi_configuration(self, sample_user_config):
        """Test RSI configuration conversion"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.rsi_period == sample_user_config.rsi_period
        assert strategy_config.rsi_oversold == sample_user_config.rsi_oversold
        assert strategy_config.rsi_extreme_oversold == sample_user_config.rsi_extreme_oversold
        assert strategy_config.rsi_near_oversold == sample_user_config.rsi_near_oversold

    def test_capital_configuration(self, sample_user_config):
        """Test capital configuration conversion"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.user_capital == sample_user_config.user_capital
        assert strategy_config.max_position_volume_ratio == sample_user_config.max_position_volume_ratio
        assert strategy_config.min_absolute_avg_volume == sample_user_config.min_absolute_avg_volume

    def test_chart_quality_configuration(self, sample_user_config):
        """Test chart quality configuration conversion"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.chart_quality_enabled == sample_user_config.chart_quality_enabled
        assert strategy_config.chart_quality_min_score == sample_user_config.chart_quality_min_score
        assert strategy_config.chart_quality_max_gap_frequency == sample_user_config.chart_quality_max_gap_frequency
        assert (
            strategy_config.chart_quality_min_daily_range_pct
            == sample_user_config.chart_quality_min_daily_range_pct
        )
        assert (
            strategy_config.chart_quality_max_extreme_candle_frequency
            == sample_user_config.chart_quality_max_extreme_candle_frequency
        )

    def test_risk_management_configuration(self, sample_user_config):
        """Test risk management configuration conversion"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.default_stop_loss_pct == sample_user_config.default_stop_loss_pct
        assert strategy_config.tight_stop_loss_pct == sample_user_config.tight_stop_loss_pct
        assert strategy_config.min_stop_loss_pct == sample_user_config.min_stop_loss_pct
        assert strategy_config.default_target_pct == sample_user_config.default_target_pct
        assert strategy_config.strong_buy_target_pct == sample_user_config.strong_buy_target_pct
        assert strategy_config.excellent_target_pct == sample_user_config.excellent_target_pct

    def test_risk_reward_ratios(self, sample_user_config):
        """Test risk-reward ratios conversion"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.strong_buy_risk_reward == sample_user_config.strong_buy_risk_reward
        assert strategy_config.buy_risk_reward == sample_user_config.buy_risk_reward
        assert strategy_config.excellent_risk_reward == sample_user_config.excellent_risk_reward

    def test_news_sentiment_configuration(self, sample_user_config):
        """Test news sentiment configuration conversion"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.news_sentiment_enabled == sample_user_config.news_sentiment_enabled
        assert strategy_config.news_sentiment_lookback_days == sample_user_config.news_sentiment_lookback_days
        assert strategy_config.news_sentiment_min_articles == sample_user_config.news_sentiment_min_articles
        assert strategy_config.news_sentiment_pos_threshold == sample_user_config.news_sentiment_pos_threshold
        assert strategy_config.news_sentiment_neg_threshold == sample_user_config.news_sentiment_neg_threshold

    def test_default_values_for_missing_fields(self, sample_user_config):
        """Test that defaults are used for fields not in UserTradingConfig"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        # These should use defaults from StrategyConfig
        assert strategy_config.min_volume_multiplier == 1.0
        assert strategy_config.volume_multiplier_for_strong == 1.2
        assert strategy_config.volume_lookback_days == 50
        assert strategy_config.pe_max_attractive == 15.0
        assert strategy_config.backtest_weight == 0.5

    def test_nullable_stop_loss_handling(self, db_session):
        """Test handling of nullable stop loss fields"""
        from src.infrastructure.db.models import Users

        user = Users(
            email="test2@example.com",
            password_hash="hash",
            created_at=ist_now(),
        )
        db_session.add(user)
        db_session.commit()

        # Config with None stop loss values
        config = UserTradingConfig(
            user_id=user.id,
            default_stop_loss_pct=None,
            tight_stop_loss_pct=None,
            min_stop_loss_pct=None,
        )
        db_session.add(config)
        db_session.commit()

        strategy_config = user_config_to_strategy_config(config)

        # Should use defaults when None
        assert strategy_config.default_stop_loss_pct == 0.08
        assert strategy_config.tight_stop_loss_pct == 0.06
        assert strategy_config.min_stop_loss_pct == 0.03

