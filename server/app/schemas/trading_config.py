"""Schemas for trading configuration management"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TradingConfigResponse(BaseModel):
    """Response model for trading configuration"""

    # RSI Configuration
    rsi_period: int
    rsi_oversold: float
    rsi_extreme_oversold: float
    rsi_near_oversold: float

    # Capital & Position Management
    user_capital: float
    max_portfolio_size: int
    max_position_volume_ratio: float
    min_absolute_avg_volume: int

    # Chart Quality Filters
    chart_quality_enabled: bool
    chart_quality_min_score: float
    chart_quality_max_gap_frequency: float
    chart_quality_min_daily_range_pct: float
    chart_quality_max_extreme_candle_frequency: float

    # Risk Management
    default_stop_loss_pct: float | None = None
    tight_stop_loss_pct: float | None = None
    min_stop_loss_pct: float | None = None
    default_target_pct: float
    strong_buy_target_pct: float
    excellent_target_pct: float

    # Risk-Reward Ratios
    strong_buy_risk_reward: float
    buy_risk_reward: float
    excellent_risk_reward: float

    # Order Defaults
    default_exchange: str
    default_product: str
    default_order_type: str
    default_variety: str
    default_validity: str

    # Behavior Toggles
    allow_duplicate_recommendations_same_day: bool
    exit_on_ema9_or_rsi50: bool
    min_combined_score: int

    # News Sentiment
    news_sentiment_enabled: bool
    news_sentiment_lookback_days: int
    news_sentiment_min_articles: int
    news_sentiment_pos_threshold: float
    news_sentiment_neg_threshold: float

    # ML Configuration
    ml_enabled: bool
    ml_model_version: str | None = None
    ml_confidence_threshold: float
    ml_combine_with_rules: bool


class TradingConfigUpdateRequest(BaseModel):
    """Request model for updating trading configuration (all fields optional)"""

    # RSI Configuration
    rsi_period: int | None = Field(None, ge=1, le=50)
    rsi_oversold: float | None = Field(None, ge=0, le=50)
    rsi_extreme_oversold: float | None = Field(None, ge=0, le=30)
    rsi_near_oversold: float | None = Field(None, ge=30, le=50)

    # Capital & Position Management
    user_capital: float | None = Field(None, gt=0)
    max_portfolio_size: int | None = Field(None, ge=1, le=20)
    max_position_volume_ratio: float | None = Field(None, ge=0, le=1)
    min_absolute_avg_volume: int | None = Field(None, ge=0)

    # Chart Quality Filters
    chart_quality_enabled: bool | None = None
    chart_quality_min_score: float | None = Field(None, ge=0, le=100)
    chart_quality_max_gap_frequency: float | None = Field(None, ge=0, le=100)
    chart_quality_min_daily_range_pct: float | None = Field(None, ge=0, le=10)
    chart_quality_max_extreme_candle_frequency: float | None = Field(None, ge=0, le=100)

    # Risk Management
    default_stop_loss_pct: float | None = Field(None, ge=0, le=1)
    tight_stop_loss_pct: float | None = Field(None, ge=0, le=1)
    min_stop_loss_pct: float | None = Field(None, ge=0, le=1)
    default_target_pct: float | None = Field(None, ge=0, le=1)
    strong_buy_target_pct: float | None = Field(None, ge=0, le=1)
    excellent_target_pct: float | None = Field(None, ge=0, le=1)

    # Risk-Reward Ratios
    strong_buy_risk_reward: float | None = Field(None, ge=0)
    buy_risk_reward: float | None = Field(None, ge=0)
    excellent_risk_reward: float | None = Field(None, ge=0)

    # Order Defaults
    default_exchange: Literal["NSE", "BSE"] | None = None
    default_product: Literal["CNC", "MIS", "NRML"] | None = None
    default_order_type: Literal["MARKET", "LIMIT"] | None = None
    default_variety: Literal["AMO", "REGULAR"] | None = None
    default_validity: Literal["DAY", "IOC", "GTC"] | None = None

    # Behavior Toggles
    allow_duplicate_recommendations_same_day: bool | None = None
    exit_on_ema9_or_rsi50: bool | None = None
    min_combined_score: int | None = Field(None, ge=0, le=100)

    # News Sentiment
    news_sentiment_enabled: bool | None = None
    news_sentiment_lookback_days: int | None = Field(None, ge=1, le=365)
    news_sentiment_min_articles: int | None = Field(None, ge=0)
    news_sentiment_pos_threshold: float | None = Field(None, ge=-1, le=1)
    news_sentiment_neg_threshold: float | None = Field(None, ge=-1, le=1)

    # ML Configuration
    ml_enabled: bool | None = None
    ml_model_version: str | None = None
    ml_confidence_threshold: float | None = Field(None, ge=0, le=1)
    ml_combine_with_rules: bool | None = None

    @field_validator("rsi_extreme_oversold", "rsi_oversold", "rsi_near_oversold")
    @classmethod
    def validate_rsi_order(cls, v, info):
        """Validate RSI thresholds are in correct order"""
        if v is None:
            return v
        # This validation would need access to other fields, so we'll do it in the endpoint
        return v

    @field_validator("default_stop_loss_pct", "tight_stop_loss_pct", "min_stop_loss_pct")
    @classmethod
    def validate_stop_loss_order(cls, v, info):
        """Validate stop loss percentages are in correct order"""
        if v is None:
            return v
        # This validation would need access to other fields, so we'll do it in the endpoint
        return v
