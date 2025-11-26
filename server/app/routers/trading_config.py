"""API endpoints for trading configuration management"""

# ruff: noqa: B008
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Users
from src.infrastructure.persistence import UserTradingConfigRepository

from ..core.deps import get_current_user, get_db
from ..schemas.trading_config import TradingConfigResponse, TradingConfigUpdateRequest

router = APIRouter()


def _config_to_response(config) -> TradingConfigResponse:
    """Convert UserTradingConfig to response model"""
    return TradingConfigResponse(
        # RSI Configuration
        rsi_period=config.rsi_period,
        rsi_oversold=config.rsi_oversold,
        rsi_extreme_oversold=config.rsi_extreme_oversold,
        rsi_near_oversold=config.rsi_near_oversold,
        # Capital & Position Management
        user_capital=config.user_capital,
        paper_trading_initial_capital=getattr(config, "paper_trading_initial_capital", 300000.0),
        max_portfolio_size=config.max_portfolio_size,
        max_position_volume_ratio=config.max_position_volume_ratio,
        min_absolute_avg_volume=config.min_absolute_avg_volume,
        # Chart Quality Filters
        chart_quality_enabled=config.chart_quality_enabled,
        chart_quality_min_score=config.chart_quality_min_score,
        chart_quality_max_gap_frequency=config.chart_quality_max_gap_frequency,
        chart_quality_min_daily_range_pct=config.chart_quality_min_daily_range_pct,
        chart_quality_max_extreme_candle_frequency=config.chart_quality_max_extreme_candle_frequency,
        # Risk Management
        default_stop_loss_pct=config.default_stop_loss_pct,
        tight_stop_loss_pct=config.tight_stop_loss_pct,
        min_stop_loss_pct=config.min_stop_loss_pct,
        default_target_pct=config.default_target_pct,
        strong_buy_target_pct=config.strong_buy_target_pct,
        excellent_target_pct=config.excellent_target_pct,
        # Risk-Reward Ratios
        strong_buy_risk_reward=config.strong_buy_risk_reward,
        buy_risk_reward=config.buy_risk_reward,
        excellent_risk_reward=config.excellent_risk_reward,
        # Order Defaults
        default_exchange=config.default_exchange,
        default_product=config.default_product,
        default_order_type=config.default_order_type,
        default_variety=config.default_variety,
        default_validity=config.default_validity,
        # Behavior Toggles
        allow_duplicate_recommendations_same_day=config.allow_duplicate_recommendations_same_day,
        exit_on_ema9_or_rsi50=config.exit_on_ema9_or_rsi50,
        min_combined_score=config.min_combined_score,
        # News Sentiment
        news_sentiment_enabled=config.news_sentiment_enabled,
        news_sentiment_lookback_days=config.news_sentiment_lookback_days,
        news_sentiment_min_articles=config.news_sentiment_min_articles,
        news_sentiment_pos_threshold=config.news_sentiment_pos_threshold,
        news_sentiment_neg_threshold=config.news_sentiment_neg_threshold,
        # ML Configuration
        ml_enabled=config.ml_enabled,
        ml_model_version=config.ml_model_version,
        ml_confidence_threshold=config.ml_confidence_threshold,
        ml_combine_with_rules=config.ml_combine_with_rules,
    )


def _validate_config_update(update: TradingConfigUpdateRequest, current_config) -> None:
    """Validate configuration update values"""
    # Get current values for comparison
    extreme = (
        update.rsi_extreme_oversold
        if update.rsi_extreme_oversold is not None
        else current_config.rsi_extreme_oversold
    )
    oversold = (
        update.rsi_oversold if update.rsi_oversold is not None else current_config.rsi_oversold
    )
    near = (
        update.rsi_near_oversold
        if update.rsi_near_oversold is not None
        else current_config.rsi_near_oversold
    )

    # Validate RSI thresholds are in correct order
    if not (extreme < oversold < near):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RSI thresholds must be in order: extreme_oversold < oversold < near_oversold",
        )

    # Validate stop loss percentages are in correct order (if all are provided)
    if (
        update.min_stop_loss_pct is not None
        and update.tight_stop_loss_pct is not None
        and update.default_stop_loss_pct is not None
    ):
        if not (
            update.min_stop_loss_pct < update.tight_stop_loss_pct < update.default_stop_loss_pct
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stop loss percentages must be in order: min < tight < default",
            )


@router.get("/trading-config", response_model=TradingConfigResponse)
def get_trading_config(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Get user's trading configuration"""
    repo = UserTradingConfigRepository(db)
    config = repo.get_or_create_default(current.id)
    return _config_to_response(config)


@router.put("/trading-config", response_model=TradingConfigResponse)
def update_trading_config(
    payload: TradingConfigUpdateRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Update user's trading configuration"""
    # Get current config for validation
    repo = UserTradingConfigRepository(db)
    current_config = repo.get_or_create_default(current.id)

    # Validate the update
    _validate_config_update(payload, current_config)

    # Convert payload to dict, excluding None values
    update_dict = payload.model_dump(exclude_none=True)

    # Update configuration
    config = repo.update(current.id, **update_dict)

    return _config_to_response(config)


@router.post("/trading-config/reset", response_model=TradingConfigResponse)
def reset_trading_config(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Reset user's trading configuration to defaults"""
    repo = UserTradingConfigRepository(db)
    config = repo.reset_to_defaults(current.id)
    return _config_to_response(config)
