"""
Configuration Converter

Converts UserTradingConfig (database model) to StrategyConfig (trading engine config).
"""

from __future__ import annotations

from config.strategy_config import StrategyConfig
from src.infrastructure.db.models import UserTradingConfig


def user_config_to_strategy_config(user_config: UserTradingConfig) -> StrategyConfig:
    """
    Convert UserTradingConfig database model to StrategyConfig dataclass.
    
    Args:
        user_config: UserTradingConfig from database
        
    Returns:
        StrategyConfig instance with user-specific values
    """
    return StrategyConfig(
        # RSI Configuration
        rsi_period=user_config.rsi_period,
        rsi_oversold=user_config.rsi_oversold,
        rsi_extreme_oversold=user_config.rsi_extreme_oversold,
        rsi_near_oversold=user_config.rsi_near_oversold,
        # Volume Configuration (use defaults from StrategyConfig for now)
        min_volume_multiplier=1.0,  # Not in UserTradingConfig yet
        volume_multiplier_for_strong=1.2,  # Not in UserTradingConfig yet
        volume_lookback_days=50,  # Not in UserTradingConfig yet
        min_absolute_avg_volume=user_config.min_absolute_avg_volume,
        # Capital Configuration
        user_capital=user_config.user_capital,
        max_position_volume_ratio=user_config.max_position_volume_ratio,
        # Chart Quality Configuration
        chart_quality_enabled=user_config.chart_quality_enabled,
        chart_quality_min_score=user_config.chart_quality_min_score,
        chart_quality_max_gap_frequency=user_config.chart_quality_max_gap_frequency,
        chart_quality_min_daily_range_pct=user_config.chart_quality_min_daily_range_pct,
        chart_quality_max_extreme_candle_frequency=user_config.chart_quality_max_extreme_candle_frequency,
        chart_quality_enabled_in_backtest=True,  # Default
        # Fundamental Filters (use defaults - not in UserTradingConfig yet)
        pe_max_attractive=15.0,
        pe_max_decent=25.0,
        pb_max_attractive=1.5,
        pb_max_expensive=10.0,
        pb_max_for_growth_stock=5.0,
        # Multi-Timeframe Analysis (use defaults - not in UserTradingConfig yet)
        mtf_alignment_excellent=8.0,
        mtf_alignment_good=6.0,
        mtf_alignment_fair=4.0,
        # Risk Management
        default_stop_loss_pct=user_config.default_stop_loss_pct or 0.08,
        tight_stop_loss_pct=user_config.tight_stop_loss_pct or 0.06,
        min_stop_loss_pct=user_config.min_stop_loss_pct or 0.03,
        default_target_pct=user_config.default_target_pct,
        strong_buy_target_pct=user_config.strong_buy_target_pct,
        excellent_target_pct=user_config.excellent_target_pct,
        # Risk-Reward Ratios
        strong_buy_risk_reward=user_config.strong_buy_risk_reward,
        buy_risk_reward=user_config.buy_risk_reward,
        excellent_risk_reward=user_config.excellent_risk_reward,
        # Buy Range Configuration (use defaults - not in UserTradingConfig yet)
        buy_range_default_low=0.995,
        buy_range_default_high=1.01,
        buy_range_tight_low=0.997,
        buy_range_tight_high=1.007,
        buy_range_max_width_pct=2.0,
        # Support-based buy range (use defaults - not in UserTradingConfig yet)
        support_buffer_strong=0.003,
        support_buffer_moderate=0.005,
        # Backtest Scoring Weights (use defaults - not in UserTradingConfig yet)
        backtest_weight=0.5,
        # Support/Resistance Lookback (use defaults - not in UserTradingConfig yet)
        support_resistance_lookback_daily=20,
        support_resistance_lookback_weekly=50,
        # Volume Exhaustion Lookback (use defaults - not in UserTradingConfig yet)
        volume_exhaustion_lookback_daily=10,
        volume_exhaustion_lookback_weekly=20,
        # Data Fetching Configuration (use defaults - not in UserTradingConfig yet)
        data_fetch_daily_max_years=5,
        data_fetch_weekly_max_years=3,
        enable_adaptive_lookback=True,
        # News Sentiment
        news_sentiment_enabled=user_config.news_sentiment_enabled,
        news_sentiment_lookback_days=user_config.news_sentiment_lookback_days,
        news_sentiment_min_articles=user_config.news_sentiment_min_articles,
        news_sentiment_pos_threshold=user_config.news_sentiment_pos_threshold,
        news_sentiment_neg_threshold=user_config.news_sentiment_neg_threshold,
        # ML Configuration (use defaults - not fully in StrategyConfig yet)
        ml_enabled=False,  # User config has ml_enabled but StrategyConfig uses different structure
        ml_verdict_model_path="models/verdict_model_random_forest.pkl",
        ml_price_model_path="models/price_model_random_forest.pkl",
        ml_confidence_threshold=user_config.ml_confidence_threshold,
        ml_combine_with_rules=user_config.ml_combine_with_rules,
    )

