# ruff: noqa: B008
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.infrastructure.db.models import TradeMode, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.deps import get_current_user, get_db
from ..schemas.user import SettingsResponse, SettingsUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter()


class BuyingZoneColumnsRequest(BaseModel):
    columns: list[str]


class BuyingZoneColumnsResponse(BaseModel):
    columns: list[str]


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
    trade_mode = TradeMode(payload.trade_mode) if payload.trade_mode else None
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
