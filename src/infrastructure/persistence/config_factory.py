"""Factory for creating UserTradingConfig from StrategyConfig defaults"""

from config.strategy_config import StrategyConfig
from src.infrastructure.db.models import UserTradingConfig


def create_default_user_config(user_id: int) -> UserTradingConfig:
    """
    Create a UserTradingConfig with default values from StrategyConfig.default()

    Args:
        user_id: User ID for the configuration

    Returns:
        UserTradingConfig instance with default values
    """
    strategy_config = StrategyConfig.default()

    return UserTradingConfig(
        user_id=user_id,
        # RSI Configuration
        rsi_period=strategy_config.rsi_period,
        rsi_oversold=strategy_config.rsi_oversold,
        rsi_extreme_oversold=strategy_config.rsi_extreme_oversold,
        rsi_near_oversold=strategy_config.rsi_near_oversold,
        # Capital & Position Management
        user_capital=strategy_config.user_capital,
        max_portfolio_size=6,  # From modules/kotak_neo_auto_trader/config.py
        max_position_volume_ratio=strategy_config.max_position_volume_ratio,
        min_absolute_avg_volume=strategy_config.min_absolute_avg_volume,
        # Chart Quality Filters
        chart_quality_enabled=strategy_config.chart_quality_enabled,
        chart_quality_min_score=strategy_config.chart_quality_min_score,
        chart_quality_max_gap_frequency=strategy_config.chart_quality_max_gap_frequency,
        chart_quality_min_daily_range_pct=strategy_config.chart_quality_min_daily_range_pct,
        chart_quality_max_extreme_candle_frequency=strategy_config.chart_quality_max_extreme_candle_frequency,
        # Risk Management (stop loss is optional)
        default_stop_loss_pct=None,  # Optional, not in StrategyConfig
        tight_stop_loss_pct=None,  # Optional
        min_stop_loss_pct=None,  # Optional
        default_target_pct=strategy_config.default_target_pct,
        strong_buy_target_pct=strategy_config.strong_buy_target_pct,
        excellent_target_pct=strategy_config.excellent_target_pct,
        # Risk-Reward Ratios
        strong_buy_risk_reward=strategy_config.strong_buy_risk_reward,
        buy_risk_reward=strategy_config.buy_risk_reward,
        excellent_risk_reward=strategy_config.excellent_risk_reward,
        # Order Defaults
        default_exchange="NSE",  # From modules/kotak_neo_auto_trader/config.py
        default_product="CNC",
        default_order_type="MARKET",
        default_variety="AMO",
        default_validity="DAY",
        # Behavior Toggles
        allow_duplicate_recommendations_same_day=False,  # From modules/kotak_neo_auto_trader/config.py
        exit_on_ema9_or_rsi50=True,
        min_combined_score=25,  # From modules/kotak_neo_auto_trader/config.py
        # News Sentiment
        news_sentiment_enabled=strategy_config.news_sentiment_enabled,
        news_sentiment_lookback_days=strategy_config.news_sentiment_lookback_days,
        news_sentiment_min_articles=strategy_config.news_sentiment_min_articles,
        news_sentiment_pos_threshold=strategy_config.news_sentiment_pos_threshold,
        news_sentiment_neg_threshold=strategy_config.news_sentiment_neg_threshold,
        # ML Configuration
        ml_enabled=strategy_config.ml_enabled,
        ml_model_version=None,  # Will be set when ML model is active
        ml_confidence_threshold=strategy_config.ml_confidence_threshold,
        ml_combine_with_rules=strategy_config.ml_combine_with_rules,
    )


def db_config_to_strategy_config(db_config: UserTradingConfig) -> StrategyConfig:
    """
    Convert UserTradingConfig to StrategyConfig object

    Args:
        db_config: UserTradingConfig from database

    Returns:
        StrategyConfig instance
    """
    return StrategyConfig(
        # RSI Configuration
        rsi_period=db_config.rsi_period,
        rsi_oversold=db_config.rsi_oversold,
        rsi_extreme_oversold=db_config.rsi_extreme_oversold,
        rsi_near_oversold=db_config.rsi_near_oversold,
        # Volume Configuration (using defaults for fields not in UserTradingConfig)
        min_volume_multiplier=1.0,
        volume_multiplier_for_strong=1.2,
        volume_lookback_days=50,
        min_absolute_avg_volume=db_config.min_absolute_avg_volume,
        # Capital Configuration
        user_capital=db_config.user_capital,
        max_position_volume_ratio=db_config.max_position_volume_ratio,
        # Chart Quality Configuration
        chart_quality_enabled=db_config.chart_quality_enabled,
        chart_quality_min_score=db_config.chart_quality_min_score,
        chart_quality_max_gap_frequency=db_config.chart_quality_max_gap_frequency,
        chart_quality_min_daily_range_pct=db_config.chart_quality_min_daily_range_pct,
        chart_quality_max_extreme_candle_frequency=db_config.chart_quality_max_extreme_candle_frequency,
        chart_quality_enabled_in_backtest=True,  # Default
        # Risk Management
        default_target_pct=db_config.default_target_pct,
        strong_buy_target_pct=db_config.strong_buy_target_pct,
        excellent_target_pct=db_config.excellent_target_pct,
        strong_buy_risk_reward=db_config.strong_buy_risk_reward,
        buy_risk_reward=db_config.buy_risk_reward,
        excellent_risk_reward=db_config.excellent_risk_reward,
        # News Sentiment
        news_sentiment_enabled=db_config.news_sentiment_enabled,
        news_sentiment_lookback_days=db_config.news_sentiment_lookback_days,
        news_sentiment_min_articles=db_config.news_sentiment_min_articles,
        news_sentiment_pos_threshold=db_config.news_sentiment_pos_threshold,
        news_sentiment_neg_threshold=db_config.news_sentiment_neg_threshold,
        # ML Configuration
        ml_enabled=db_config.ml_enabled,
        ml_confidence_threshold=db_config.ml_confidence_threshold,
        ml_combine_with_rules=db_config.ml_combine_with_rules,
    )
