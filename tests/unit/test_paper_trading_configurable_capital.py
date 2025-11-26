"""Tests for configurable paper trading initial capital feature"""

from unittest.mock import MagicMock, Mock, patch

from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from server.app.routers.trading_config import _config_to_response
from src.infrastructure.db.models import UserTradingConfig


def test_user_trading_config_has_paper_capital_field():
    """Test that UserTradingConfig model has paper_trading_initial_capital field"""
    config = UserTradingConfig(
        user_id=1,
        user_capital=200000.0,
        paper_trading_initial_capital=500000.0,
    )
    assert hasattr(config, "paper_trading_initial_capital")
    assert config.paper_trading_initial_capital == 500000.0


def test_paper_trading_config_to_dict_includes_max_position_size():
    """Test that PaperTradingConfig.to_dict() includes max_position_size"""
    config = PaperTradingConfig(
        initial_capital=1000000.0,
        max_position_size=800000.0,
    )

    config_dict = config.to_dict()

    assert "initial_capital" in config_dict
    assert "max_position_size" in config_dict
    assert config_dict["initial_capital"] == 1000000.0
    assert config_dict["max_position_size"] == 800000.0


def test_paper_trading_config_from_dict_restores_max_position_size():
    """Test that PaperTradingConfig.from_dict() restores max_position_size"""
    config_dict = {
        "initial_capital": 1000000.0,
        "max_position_size": 800000.0,
        "enable_slippage": True,
        "enable_fees": True,
        "storage_path": "test_path",
        "price_source": "live",
    }

    config = PaperTradingConfig.from_dict(config_dict)

    assert config.initial_capital == 1000000.0
    assert config.max_position_size == 800000.0


def test_config_to_response_uses_paper_capital_when_present():
    """Test that _config_to_response uses paper_trading_initial_capital when present"""
    mock_config = MagicMock()
    mock_config.rsi_period = 10
    mock_config.rsi_oversold = 30.0
    mock_config.rsi_extreme_oversold = 20.0
    mock_config.rsi_near_oversold = 40.0
    mock_config.user_capital = 200000.0
    mock_config.paper_trading_initial_capital = 500000.0
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

    assert response.user_capital == 200000.0
    assert response.paper_trading_initial_capital == 500000.0


def test_config_to_response_handles_missing_paper_capital():
    """Test that _config_to_response handles missing paper_trading_initial_capital (old DB rows)"""

    class OldConfig:
        def __init__(self):
            self.rsi_period = 10
            self.rsi_oversold = 30.0
            self.rsi_extreme_oversold = 20.0
            self.rsi_near_oversold = 40.0
            self.user_capital = 200000.0
            # paper_trading_initial_capital NOT defined (old DB row)
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

    # Should NOT raise ValidationError, should use default Rs 3,00,000
    response = _config_to_response(old_config)

    assert response.user_capital == 200000.0
    assert response.paper_trading_initial_capital == 300000.0  # Default fallback


@patch("src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter")
@patch("src.application.services.paper_trading_service_adapter.PaperTradeReporter")
@patch("src.application.services.paper_trading_service_adapter.PaperTradingEngineAdapter")
def test_paper_service_uses_initial_capital_for_max_position_size(
    mock_engine, mock_reporter, mock_broker
):
    """Test that PaperTradingServiceAdapter uses initial_capital for max_position_size"""
    from src.application.services.paper_trading_service_adapter import PaperTradingServiceAdapter
    from src.infrastructure.db.session import SessionLocal

    db = SessionLocal()
    try:
        # Create service with Rs 10,00,000
        service = PaperTradingServiceAdapter(
            user_id=999,
            db_session=db,
            strategy_config=None,
            initial_capital=1000000.0,
            storage_path="paper_trading/test",
            skip_execution_tracking=True,
        )

        # Mock broker connect
        mock_broker_instance = Mock()
        mock_broker_instance.connect.return_value = True
        mock_broker_instance.get_pending_orders.return_value = []
        mock_broker_instance.get_all_holdings.return_value = []
        mock_broker_instance.get_available_balance.return_value = Mock(amount=1000000.0)
        mock_broker_instance.config = Mock(max_position_size=1000000.0)
        mock_broker_instance.store = Mock()
        mock_broker_instance.store.storage_path = "paper_trading/test"
        mock_broker.return_value = mock_broker_instance

        # Initialize
        service.initialize()

        # Verify config was created with correct max_position_size
        assert service.config.initial_capital == 1000000.0
        assert service.config.max_position_size == 1000000.0

    finally:
        db.close()


def test_individual_service_manager_uses_user_config_for_run_once():
    """Test that individual_service_manager uses user_config.paper_trading_initial_capital for run-once"""
    from src.application.services.individual_service_manager import IndividualServiceManager
    from src.infrastructure.db.session import SessionLocal
    from src.infrastructure.persistence.user_trading_config_repository import (
        UserTradingConfigRepository,
    )

    db = SessionLocal()
    try:
        # Set up a user config with custom paper trading capital
        config_repo = UserTradingConfigRepository(db)
        config = config_repo.get_or_create_default(user_id=999)
        config.paper_trading_initial_capital = 750000.0
        db.commit()

        manager = IndividualServiceManager(db)

        # Mock settings
        mock_settings = Mock()
        mock_settings.trade_mode.value = "paper"

        # Mock strategy config
        mock_strategy_config = Mock()

        with patch.object(manager._settings_repo, "get_by_user_id", return_value=mock_settings):
            with patch.object(manager._config_repo, "get_or_create_default", return_value=config):
                # Patch where it's imported (inside the function)
                with patch(
                    "src.application.services.paper_trading_service_adapter.PaperTradingServiceAdapter"
                ) as mock_adapter:
                    mock_service = Mock()
                    mock_service.initialize.return_value = True
                    mock_service.run_buy_orders.return_value = {"placed": 0}
                    mock_adapter.return_value = mock_service

                    # Execute task logic
                    manager._execute_task_logic(
                        user_id=999,
                        task_name="buy_orders",
                        broker_creds=None,
                        strategy_config=mock_strategy_config,
                        settings=mock_settings,
                    )

                    # Verify PaperTradingServiceAdapter was called with correct initial_capital
                    mock_adapter.assert_called_once()
                    call_kwargs = mock_adapter.call_args[1]
                    assert call_kwargs["initial_capital"] == 750000.0
    finally:
        db.close()
