from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Users
from src.infrastructure.persistence.activity_repository import ActivityRepository

from ..core.deps import get_current_user, get_db
from ..schemas.activity import ActivityItem

router = APIRouter()


@router.get("", response_model=list[ActivityItem])
def list_activity(
    level: Annotated[Literal["info", "warn", "error", "all"] | None, Query()] = "all",
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> list[ActivityItem]:
    repo = ActivityRepository(db)
    items = repo.recent(current.id, limit=200, level=None if level in (None, "all") else level)
    return [
        ActivityItem(
            id=i.id,
            ts=i.ts,
            event=i.type,
            detail=(i.details_json or {}).get("detail") if i.details_json else None,
            level=(
                i.type if i.type in ("info", "warn", "error") else "info"  # type: ignore[arg-type]
            ),
        )
        for i in items
    ]
