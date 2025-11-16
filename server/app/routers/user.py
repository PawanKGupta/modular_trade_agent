from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.infrastructure.db.models import TradeMode, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.deps import get_current_user, get_db
from ..schemas.user import SettingsResponse, SettingsUpdateRequest

router = APIRouter()


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
