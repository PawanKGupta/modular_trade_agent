# ruff: noqa: B008
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.application.services.subscription_entitlement_service import SubscriptionEntitlementService
from src.infrastructure.db.models import TradeMode, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.deps import get_current_user, get_db
from ..routers.broker import get_broker_portfolio
from ..routers.paper_trading import (
    PaginatedPaperTradingOrders,
    PaginatedPaperTradingPortfolio,
    get_paper_trading_portfolio,
)
from ..schemas.user import SettingsResponse, SettingsUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter()


class BuyingZoneColumnsRequest(BaseModel):
    columns: list[str]


class BuyingZoneColumnsResponse(BaseModel):
    columns: list[str]


class FilterPresetRequest(BaseModel):
    page: str  # e.g., "signals", "orders", "trades"
    preset_name: str
    filters: dict  # Filter values


class FilterPresetsResponse(BaseModel):
    presets: dict[str, dict]  # preset_name -> filters


@router.get("/settings", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db), current: Users = Depends(get_current_user)):
    settings = SettingsRepository(db).ensure_default(current.id)
    return SettingsResponse(
        trade_mode=settings.trade_mode.value,
        broker=settings.broker,
        broker_status=settings.broker_status,
    )


@router.put("/settings", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    repo = SettingsRepository(db)
    settings = repo.ensure_default(current.id)
    # CRITICAL: Normalize to lowercase before creating enum to handle "BROKER"/"PAPER"
    # This prevents validation errors when uppercase values are sent
    trade_mode = TradeMode(payload.trade_mode.lower()) if payload.trade_mode else None
    if trade_mode == TradeMode.BROKER and not SubscriptionEntitlementService(db).user_has_feature(
        current, "broker_execution"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active Auto Trade subscription required for broker mode",
        )
    settings = repo.update(
        settings,
        trade_mode=trade_mode,
        broker=payload.broker,
        broker_status=payload.broker_status,
    )
    return SettingsResponse(
        trade_mode=settings.trade_mode.value,
        broker=settings.broker,
        broker_status=settings.broker_status,
    )


@router.get("/buying-zone-columns", response_model=BuyingZoneColumnsResponse)
def get_buying_zone_columns(
    db: Session = Depends(get_db), current: Users = Depends(get_current_user)
):
    """Get saved buying zone column preferences for the current user."""
    repo = SettingsRepository(db)
    prefs = repo.get_ui_preferences(current.id)
    columns = prefs.get("buying_zone_columns", [])
    return BuyingZoneColumnsResponse(columns=columns)


@router.put("/buying-zone-columns", response_model=BuyingZoneColumnsResponse)
def update_buying_zone_columns(
    payload: BuyingZoneColumnsRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Save buying zone column preferences for the current user."""
    try:
        repo = SettingsRepository(db)
        prefs = repo.update_ui_preferences(current.id, {"buying_zone_columns": payload.columns})
        columns = prefs.get("buying_zone_columns", [])
        return BuyingZoneColumnsResponse(columns=columns)
    except Exception as e:
        logger.exception(f"Error saving buying zone columns for user {current.id}: {e}")
        raise


@router.get("/filter-presets/{page}", response_model=FilterPresetsResponse)
def get_filter_presets(
    page: str,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Get saved filter presets for a specific page."""
    repo = SettingsRepository(db)
    prefs = repo.get_ui_preferences(current.id)
    filter_presets = prefs.get("filter_presets", {})
    page_presets = filter_presets.get(page, {})
    return FilterPresetsResponse(presets=page_presets)


@router.post("/filter-presets", response_model=FilterPresetsResponse)
def save_filter_preset(
    payload: FilterPresetRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Save a filter preset for a specific page."""
    try:
        repo = SettingsRepository(db)
        prefs = repo.get_ui_preferences(current.id)
        filter_presets = prefs.get("filter_presets", {})

        # Ensure page exists in filter_presets
        if payload.page not in filter_presets:
            filter_presets[payload.page] = {}

        # Save the preset
        filter_presets[payload.page][payload.preset_name] = payload.filters

        # Update preferences
        prefs = repo.update_ui_preferences(current.id, {"filter_presets": filter_presets})
        page_presets = prefs.get("filter_presets", {}).get(payload.page, {})
        return FilterPresetsResponse(presets=page_presets)
    except Exception as e:
        logger.exception(f"Error saving filter preset for user {current.id}: {e}")
        raise


@router.delete("/filter-presets/{page}/{preset_name}")
def delete_filter_preset(
    page: str,
    preset_name: str,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Delete a filter preset."""
    try:
        repo = SettingsRepository(db)
        prefs = repo.get_ui_preferences(current.id)
        filter_presets = prefs.get("filter_presets", {})

        if page in filter_presets and preset_name in filter_presets[page]:
            del filter_presets[page][preset_name]
            repo.update_ui_preferences(current.id, {"filter_presets": filter_presets})

        return {"message": "Preset deleted successfully"}
    except Exception as e:
        logger.exception(f"Error deleting filter preset for user {current.id}: {e}")
        raise


@router.get("/portfolio", response_model=PaginatedPaperTradingPortfolio)
def get_portfolio(
    page: Annotated[
        int,
        Query(ge=1, description="Page number for recent orders (1-based)"),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=500, description="Number of recent orders per page"),
    ] = 10,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Unified portfolio endpoint that returns either paper trading or broker portfolio
    based on user's trade mode setting.

    This endpoint automatically routes to the appropriate portfolio source:
    - Paper mode: Returns paper trading portfolio
    - Broker mode: Returns broker portfolio (if credentials are configured)
    """
    try:
        # Get user settings to determine trade mode
        settings_repo = SettingsRepository(db)
        settings = settings_repo.get_by_user_id(current.id)
        if not settings:
            # Default to paper mode if settings don't exist
            settings = settings_repo.ensure_default(current.id)

        # Route to appropriate portfolio based on trade mode
        if settings.trade_mode == TradeMode.BROKER:
            # Use broker portfolio endpoint (still returns non-paginated for now)
            broker_portfolio = get_broker_portfolio(db=db, current=current)
            # Convert to paginated format for consistency
            return PaginatedPaperTradingPortfolio(
                account=broker_portfolio.account,
                holdings=broker_portfolio.holdings,
                recent_orders=PaginatedPaperTradingOrders(
                    items=broker_portfolio.recent_orders,
                    total=len(broker_portfolio.recent_orders),
                    page=1,
                    page_size=len(broker_portfolio.recent_orders) or 1,
                    total_pages=1,
                ),
                order_statistics=broker_portfolio.order_statistics,
            )
        else:
            # Use paper trading portfolio endpoint (now paginated)
            return get_paper_trading_portfolio(
                page=page, page_size=page_size, db=db, current=current
            )

    except Exception as e:
        logger.exception(f"Error fetching unified portfolio for user {current.id}: {e}")
        raise
