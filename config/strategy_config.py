"""
Strategy Configuration Management

This module provides centralized configuration management for trading strategy parameters.
Replaces hardcoded magic numbers throughout the codebase.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class StrategyConfig:
    """Centralized strategy configuration parameters"""

    # RSI Configuration
    rsi_period: int = 10  # RSI calculation period (default: 10 for short-term strategy)
    rsi_oversold: float = 30.0
    rsi_extreme_oversold: float = 20.0
    rsi_near_oversold: float = 40.0

    # Volume Configuration
    min_volume_multiplier: float = 1.0
    volume_multiplier_for_strong: float = 1.2
    volume_lookback_days: int = 50
    min_absolute_avg_volume: int = (
        10000  # Lowered to 10000 (2025-11-09) to allow more stocks to pass liquidity filter
    )

    # Capital Configuration
    user_capital: float = 200000.0  # Default: 2L
    max_portfolio_size: int = 6  # Maximum number of positions in portfolio
    max_position_volume_ratio: float = 0.10  # 10% of daily volume max

    # Chart Quality Configuration
    # [WARN]? IMPORTANT: Chart quality is REQUIRED in production - DO NOT disable in live trading
    # Chart quality can be disabled ONLY for testing/data collection purposes
    # RELAXED THRESHOLDS (2025-11-09): Adjusted to allow more stocks while maintaining quality
    # - Increased gap frequency from 20% to 25% (allow more gaps for volatile stocks)
    # - Decreased min score from 60 to 50 (allow slightly lower scores)
    # - Decreased min daily range from 1.5% to 1.0% (allow lower volatility stocks)
    # - Increased extreme candle frequency from 15% to 20% (allow more extreme candles)
    chart_quality_enabled: bool = True  # REQUIRED in production - filters out bad charts
    chart_quality_min_score: float = (
        50.0  # Minimum score for acceptance (0-100) - Relaxed from 60.0
    )
    chart_quality_max_gap_frequency: float = 25.0  # Max gap frequency (%) - Relaxed from 20.0
    chart_quality_min_daily_range_pct: float = 1.0  # Min daily range (%) - Relaxed from 1.5
    chart_quality_max_extreme_candle_frequency: float = (
        20.0  # Max extreme candle frequency (%) - Relaxed from 15.0
    )
    chart_quality_enabled_in_backtest: bool = (
        True  # Default: enabled (can be disabled for data collection)
    )

    # Fundamental Filters
    pe_max_attractive: float = 15.0
    pe_max_decent: float = 25.0
    pb_max_attractive: float = 1.5
    pb_max_expensive: float = 10.0
    # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): PB threshold for growth stocks
    # Growth stocks (negative PE) are allowed "watch" verdict if PB < this threshold
    pb_max_for_growth_stock: float = 5.0  # Max PB ratio for growth stocks to allow "watch" verdict

    # Multi-Timeframe Analysis
    mtf_alignment_excellent: float = 8.0
    mtf_alignment_good: float = 6.0
    mtf_alignment_fair: float = 4.0

    # Risk Management
    default_stop_loss_pct: float = 0.08  # 8%
    tight_stop_loss_pct: float = 0.06  # 6%
    min_stop_loss_pct: float = 0.03  # 3%
    default_target_pct: float = 0.10  # 10%
    strong_buy_target_pct: float = 0.12  # 12%
    excellent_target_pct: float = 0.15  # 15%

    # Risk-Reward Ratios
    strong_buy_risk_reward: float = 3.0
    buy_risk_reward: float = 2.5
    excellent_risk_reward: float = 3.5

    # Buy Range Configuration
    buy_range_default_low: float = 0.995  # -0.5%
    buy_range_default_high: float = 1.01  # +1.0%
    buy_range_tight_low: float = 0.997  # -0.3%
    buy_range_tight_high: float = 1.007  # +0.7%
    buy_range_max_width_pct: float = 2.0  # Maximum buy range width

    # Support-based buy range
    support_buffer_strong: float = 0.003  # 0.3%
    support_buffer_moderate: float = 0.005  # 0.5%

    # Backtest Scoring Weights
    backtest_weight: float = 0.5  # 50% historical, 50% current analysis

    # Support/Resistance Lookback Configuration
    support_resistance_lookback_daily: int = 20  # Daily timeframe lookback periods
    support_resistance_lookback_weekly: int = 50  # Weekly timeframe lookback periods

    # Volume Exhaustion Lookback Configuration
    volume_exhaustion_lookback_daily: int = 10  # Daily timeframe volume exhaustion lookback
    volume_exhaustion_lookback_weekly: int = 20  # Weekly timeframe volume exhaustion lookback

    # Data Fetching Configuration
    data_fetch_daily_max_years: int = 5  # Maximum years to fetch for daily data
    data_fetch_weekly_max_years: int = 3  # Maximum years to fetch for weekly data

    # Adaptive Logic Configuration
    enable_adaptive_lookback: bool = True  # Enable adaptive lookback based on available data

    # News Sentiment
    news_sentiment_enabled: bool = True
    news_sentiment_lookback_days: int = 30
    news_sentiment_min_articles: int = 2
    news_sentiment_pos_threshold: float = 0.25
    news_sentiment_neg_threshold: float = -0.25

    # ML Configuration
    ml_enabled: bool = False
    ml_verdict_model_path: str = "models/verdict_model_random_forest.pkl"
    ml_price_model_path: str = "models/price_model_random_forest.pkl"
    ml_confidence_threshold: float = 0.5  # 50% confidence threshold
    ml_combine_with_rules: bool = True  # Combine ML with rule-based logic

    # Order Defaults
    default_exchange: str = "NSE"  # Default exchange
    default_product: str = "CNC"  # Default product type
    default_order_type: str = "MARKET"  # Default order type
    default_variety: str = "AMO"  # Default order variety
    default_validity: str = "DAY"  # Default order validity

    # Behavior Settings
    exit_on_ema9_or_rsi50: bool = True  # Exit when price >= EMA9 or RSI > 50
    allow_duplicate_recommendations_same_day: bool = False  # Allow duplicate recommendations
    min_combined_score: int = 25  # Minimum combined score for recommendations

    @classmethod
    def from_env(cls) -> "StrategyConfig":
        """Load configuration from environment variables with defaults"""
        return cls(
            # RSI configuration
            rsi_period=int(os.getenv("RSI_PERIOD", "10")),
            rsi_oversold=float(os.getenv("RSI_OVERSOLD", "30.0")),
            rsi_extreme_oversold=float(os.getenv("RSI_EXTREME_OVERSOLD", "20.0")),
            rsi_near_oversold=float(os.getenv("RSI_NEAR_OVERSOLD", "40.0")),
            # Volume
            min_volume_multiplier=float(os.getenv("MIN_VOLUME_MULTIPLIER", "1.0")),
            volume_multiplier_for_strong=float(os.getenv("VOLUME_MULTIPLIER_FOR_STRONG", "1.2")),
            volume_lookback_days=int(os.getenv("VOLUME_LOOKBACK_DAYS", "50")),
            min_absolute_avg_volume=int(
                os.getenv("MIN_ABSOLUTE_AVG_VOLUME", "10000")
            ),  # Lowered to 10000 (2025-11-09)
            # Capital
            user_capital=float(os.getenv("USER_CAPITAL", "200000.0")),
            max_portfolio_size=int(os.getenv("MAX_PORTFOLIO_SIZE", "6")),
            max_position_volume_ratio=float(os.getenv("MAX_POSITION_VOLUME_RATIO", "0.10")),
            # Chart Quality
            chart_quality_enabled=os.getenv("CHART_QUALITY_ENABLED", "true").lower()
            in ("1", "true", "yes", "on"),
            chart_quality_min_score=float(
                os.getenv("CHART_QUALITY_MIN_SCORE", "50.0")
            ),  # Relaxed from 60.0
            chart_quality_max_gap_frequency=float(
                os.getenv("CHART_QUALITY_MAX_GAP_FREQUENCY", "25.0")
            ),  # Relaxed from 20.0
            chart_quality_min_daily_range_pct=float(
                os.getenv("CHART_QUALITY_MIN_DAILY_RANGE_PCT", "1.0")
            ),  # Relaxed from 1.5
            chart_quality_max_extreme_candle_frequency=float(
                os.getenv("CHART_QUALITY_MAX_EXTREME_CANDLE_FREQUENCY", "20.0")
            ),  # Relaxed from 15.0
            chart_quality_enabled_in_backtest=os.getenv(
                "CHART_QUALITY_ENABLED_IN_BACKTEST", "true"
            ).lower()
            in ("1", "true", "yes", "on"),
            # Fundamentals
            pe_max_attractive=float(os.getenv("PE_MAX_ATTRACTIVE", "15.0")),
            pe_max_decent=float(os.getenv("PE_MAX_DECENT", "25.0")),
            pb_max_attractive=float(os.getenv("PB_MAX_ATTRACTIVE", "1.5")),
            pb_max_expensive=float(os.getenv("PB_MAX_EXPENSIVE", "10.0")),
            pb_max_for_growth_stock=float(
                os.getenv("PB_MAX_FOR_GROWTH_STOCK", "5.0")
            ),  # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09)
            # MTF
            mtf_alignment_excellent=float(os.getenv("MTF_ALIGNMENT_EXCELLENT", "8.0")),
            mtf_alignment_good=float(os.getenv("MTF_ALIGNMENT_GOOD", "6.0")),
            mtf_alignment_fair=float(os.getenv("MTF_ALIGNMENT_FAIR", "4.0")),
            # Risk Management
            default_stop_loss_pct=float(os.getenv("DEFAULT_STOP_LOSS_PCT", "0.08")),
            tight_stop_loss_pct=float(os.getenv("TIGHT_STOP_LOSS_PCT", "0.06")),
            min_stop_loss_pct=float(os.getenv("MIN_STOP_LOSS_PCT", "0.03")),
            default_target_pct=float(os.getenv("DEFAULT_TARGET_PCT", "0.10")),
            strong_buy_target_pct=float(os.getenv("STRONG_BUY_TARGET_PCT", "0.12")),
            excellent_target_pct=float(os.getenv("EXCELLENT_TARGET_PCT", "0.15")),
            # Risk-Reward
            strong_buy_risk_reward=float(os.getenv("STRONG_BUY_RISK_REWARD", "3.0")),
            buy_risk_reward=float(os.getenv("BUY_RISK_REWARD", "2.5")),
            excellent_risk_reward=float(os.getenv("EXCELLENT_RISK_REWARD", "3.5")),
            # Buy Range
            buy_range_default_low=float(os.getenv("BUY_RANGE_DEFAULT_LOW", "0.995")),
            buy_range_default_high=float(os.getenv("BUY_RANGE_DEFAULT_HIGH", "1.01")),
            buy_range_tight_low=float(os.getenv("BUY_RANGE_TIGHT_LOW", "0.997")),
            buy_range_tight_high=float(os.getenv("BUY_RANGE_TIGHT_HIGH", "1.007")),
            buy_range_max_width_pct=float(os.getenv("BUY_RANGE_MAX_WIDTH_PCT", "2.0")),
            # Support buffers
            support_buffer_strong=float(os.getenv("SUPPORT_BUFFER_STRONG", "0.003")),
            support_buffer_moderate=float(os.getenv("SUPPORT_BUFFER_MODERATE", "0.005")),
            # Backtest
            backtest_weight=float(os.getenv("BACKTEST_WEIGHT", "0.5")),
            # News Sentiment
            news_sentiment_enabled=os.getenv("NEWS_SENTIMENT_ENABLED", "true").lower()
            in ("1", "true", "yes", "on"),
            news_sentiment_lookback_days=int(os.getenv("NEWS_SENTIMENT_LOOKBACK_DAYS", "30")),
            news_sentiment_min_articles=int(os.getenv("NEWS_SENTIMENT_MIN_ARTICLES", "2")),
            news_sentiment_pos_threshold=float(os.getenv("NEWS_SENTIMENT_POS_THRESHOLD", "0.25")),
            news_sentiment_neg_threshold=float(os.getenv("NEWS_SENTIMENT_NEG_THRESHOLD", "-0.25")),
            # ML Configuration
            ml_enabled=os.getenv("ML_ENABLED", "false").lower() in ("1", "true", "yes", "on"),
            ml_verdict_model_path=os.getenv(
                "ML_VERDICT_MODEL_PATH", "models/verdict_model_random_forest.pkl"
            ),
            ml_price_model_path=os.getenv(
                "ML_PRICE_MODEL_PATH", "models/price_model_random_forest.pkl"
            ),
            ml_confidence_threshold=float(os.getenv("ML_CONFIDENCE_THRESHOLD", "0.5")),
            ml_combine_with_rules=os.getenv("ML_COMBINE_WITH_RULES", "true").lower()
            in ("1", "true", "yes", "on"),
            # Support/Resistance Lookback
            support_resistance_lookback_daily=int(
                os.getenv("SUPPORT_RESISTANCE_LOOKBACK_DAILY", "20")
            ),
            support_resistance_lookback_weekly=int(
                os.getenv("SUPPORT_RESISTANCE_LOOKBACK_WEEKLY", "50")
            ),
            # Volume Exhaustion Lookback
            volume_exhaustion_lookback_daily=int(
                os.getenv("VOLUME_EXHAUSTION_LOOKBACK_DAILY", "10")
            ),
            volume_exhaustion_lookback_weekly=int(
                os.getenv("VOLUME_EXHAUSTION_LOOKBACK_WEEKLY", "20")
            ),
            # Data Fetching
            data_fetch_daily_max_years=int(os.getenv("DATA_FETCH_DAILY_MAX_YEARS", "5")),
            data_fetch_weekly_max_years=int(os.getenv("DATA_FETCH_WEEKLY_MAX_YEARS", "3")),
            # Adaptive Logic
            enable_adaptive_lookback=os.getenv("ENABLE_ADAPTIVE_LOOKBACK", "true").lower()
            in ("1", "true", "yes", "on"),
            # Order Defaults
            default_exchange=os.getenv("DEFAULT_EXCHANGE", "NSE"),
            default_product=os.getenv("DEFAULT_PRODUCT", "CNC"),
            default_order_type=os.getenv("DEFAULT_ORDER_TYPE", "MARKET"),
            default_variety=os.getenv("DEFAULT_VARIETY", "AMO"),
            default_validity=os.getenv("DEFAULT_VALIDITY", "DAY"),
            # Behavior Settings
            exit_on_ema9_or_rsi50=os.getenv("EXIT_ON_EMA9_OR_RSI50", "true").lower()
            in ("1", "true", "yes", "on"),
            allow_duplicate_recommendations_same_day=os.getenv(
                "ALLOW_DUPLICATE_RECOMMENDATIONS_SAME_DAY", "false"
            ).lower()
            in ("1", "true", "yes", "on"),
            min_combined_score=int(os.getenv("MIN_COMBINED_SCORE", "25")),
        )

    @classmethod
    def default(cls) -> "StrategyConfig":
        """Return default configuration (same as instantiation defaults)"""
        return cls()

    def __repr__(self) -> str:
        return f"StrategyConfig(rsi_oversold={self.rsi_oversold}, volume_lookback={self.volume_lookback_days}, ...)"
