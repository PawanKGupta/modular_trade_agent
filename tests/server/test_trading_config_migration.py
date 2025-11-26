"""Test trading config API with missing fields (migration scenarios)"""

from unittest.mock import MagicMock

from server.app.routers.trading_config import _config_to_response


def test_config_to_response_handles_missing_paper_capital():
    """Test that _config_to_response handles configs without paper_trading_initial_capital

    This simulates the scenario where:
    1. A user's config was created before the migration
    2. The database column has a default value
    3. But the SQLAlchemy object doesn't have the attribute yet
    """
    # Create a config object WITHOUT paper_trading_initial_capital
    # This simulates an old DB row loaded before the migration

    # Simulate missing attribute by using spec
    # When we try to access paper_trading_initial_capital, it will raise AttributeError
    # But getattr() with default should handle it

    # Create a real object that doesn't have the attribute
    class OldConfig:
        def __init__(self):
            self.rsi_period = 10
            self.rsi_oversold = 30.0
            self.rsi_extreme_oversold = 20.0
            self.rsi_near_oversold = 40.0
            self.user_capital = 200000.0
            # paper_trading_initial_capital NOT defined
            self.max_portfolio_size = 6
            self.max_position_volume_ratio = 0.1
            self.min_absolute_avg_volume = 10000
            self.chart_quality_enabled = True
            self.chart_quality_min_score = 50.0
            self.chart_quality_max_gap_frequency = 25.0
            self.chart_quality_min_daily_range_pct = 1.0
            self.chart_quality_max_extreme_candle_frequency = 20.0
            self.default_stop_loss_pct = None
            self.tight_stop_loss_pct = None
            self.min_stop_loss_pct = None
            self.default_target_pct = 0.1
            self.strong_buy_target_pct = 0.12
            self.excellent_target_pct = 0.15
            self.strong_buy_risk_reward = 3.0
            self.buy_risk_reward = 2.5
            self.excellent_risk_reward = 3.5
            self.default_exchange = "NSE"
            self.default_product = "CNC"
            self.default_order_type = "MARKET"
            self.default_variety = "AMO"
            self.default_validity = "DAY"
            self.allow_duplicate_recommendations_same_day = False
            self.exit_on_ema9_or_rsi50 = True
            self.min_combined_score = 50
            self.news_sentiment_enabled = False
            self.news_sentiment_lookback_days = 7
            self.news_sentiment_min_articles = 3
            self.news_sentiment_pos_threshold = 0.6
            self.news_sentiment_neg_threshold = -0.6
            self.ml_enabled = False
            self.ml_model_version = None
            self.ml_confidence_threshold = 0.7
            self.ml_combine_with_rules = True

    old_config = OldConfig()

    # This should NOT raise ValidationError
    response = _config_to_response(old_config)

    # Should use default value
    assert response.paper_trading_initial_capital == 300000.0
    assert response.user_capital == 200000.0


def test_config_to_response_uses_existing_paper_capital():
    """Test that _config_to_response uses the value when it exists"""
    # Create a mock config object WITH paper_trading_initial_capital
    mock_config = MagicMock()
    mock_config.rsi_period = 10
    mock_config.rsi_oversold = 30.0
    mock_config.rsi_extreme_oversold = 20.0
    mock_config.rsi_near_oversold = 40.0
    mock_config.user_capital = 200000.0
    mock_config.paper_trading_initial_capital = 500000.0  # Custom value
    mock_config.max_portfolio_size = 6
    mock_config.max_position_volume_ratio = 0.1
    mock_config.min_absolute_avg_volume = 10000
    mock_config.chart_quality_enabled = True
    mock_config.chart_quality_min_score = 50.0
    mock_config.chart_quality_max_gap_frequency = 25.0
    mock_config.chart_quality_min_daily_range_pct = 1.0
    mock_config.chart_quality_max_extreme_candle_frequency = 20.0
    mock_config.default_stop_loss_pct = None
    mock_config.tight_stop_loss_pct = None
    mock_config.min_stop_loss_pct = None
    mock_config.default_target_pct = 0.1
    mock_config.strong_buy_target_pct = 0.12
    mock_config.excellent_target_pct = 0.15
    mock_config.strong_buy_risk_reward = 3.0
    mock_config.buy_risk_reward = 2.5
    mock_config.excellent_risk_reward = 3.5
    mock_config.default_exchange = "NSE"
    mock_config.default_product = "CNC"
    mock_config.default_order_type = "MARKET"
    mock_config.default_variety = "AMO"
    mock_config.default_validity = "DAY"
    mock_config.allow_duplicate_recommendations_same_day = False
    mock_config.exit_on_ema9_or_rsi50 = True
    mock_config.min_combined_score = 50
    mock_config.news_sentiment_enabled = False
    mock_config.news_sentiment_lookback_days = 7
    mock_config.news_sentiment_min_articles = 3
    mock_config.news_sentiment_pos_threshold = 0.6
    mock_config.news_sentiment_neg_threshold = -0.6
    mock_config.ml_enabled = False
    mock_config.ml_model_version = None
    mock_config.ml_confidence_threshold = 0.7
    mock_config.ml_combine_with_rules = True

    response = _config_to_response(mock_config)

    # Should use the actual value
    assert response.paper_trading_initial_capital == 500000.0
    assert response.user_capital == 200000.0
