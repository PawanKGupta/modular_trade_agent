from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Users

from ..core.deps import get_current_user, get_db
from ..schemas.targets import TargetItem

router = APIRouter()


@router.get("/", response_model=list[TargetItem])
def list_targets(
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    # Placeholder until Targets persistence is implemented
    _ = (db, current)  # silence unused for now
    return []  # return empty list rather than 404
