# ruff: noqa: B008
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.infrastructure.db.models import TradeMode, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.crypto import encrypt_blob
from ..core.deps import get_current_user, get_db
from ..schemas.user import BrokerCredsRequest, BrokerTestResponse

router = APIRouter()


@router.post("/creds", response_model=dict)
def save_broker_creds(
    payload: BrokerCredsRequest,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> dict[str, str]:
    repo = SettingsRepository(db)
    settings = repo.ensure_default(current.id)
    creds_blob = {
        "api_key": payload.api_key,
        "api_secret": payload.api_secret,
    }
    settings = repo.update(
        settings,
        broker=payload.broker,
        broker_status="Stored",
    )
    # store encrypted creds
    settings.broker_creds_encrypted = encrypt_blob(str(creds_blob).encode("utf-8"))
    db.commit()
    return {"status": "ok"}


@router.post("/test", response_model=BrokerTestResponse)
def test_broker_connection(
    payload: BrokerCredsRequest,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> BrokerTestResponse:
    # Placeholder: simulate success if keys are non-empty
    ok = bool(payload.api_key and payload.api_secret)
    if ok:
        repo = SettingsRepository(db)
        settings = repo.ensure_default(current.id)
        settings = repo.update(
            settings,
            trade_mode=TradeMode.BROKER,
            broker=payload.broker,
            broker_status="Connected",
        )
        return BrokerTestResponse(ok=True, message="Broker connection successful")
    return BrokerTestResponse(ok=False, message="Invalid credentials")


@router.get("/status", response_model=dict)
def broker_status(
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> dict[str, str | None]:
    repo = SettingsRepository(db)
    settings = repo.ensure_default(current.id)
    return {"broker": settings.broker, "status": settings.broker_status}
