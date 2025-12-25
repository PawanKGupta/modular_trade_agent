"""Targets API router (Phase 0.4)"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Users
from src.infrastructure.persistence.targets_repository import TargetsRepository

from ..core.deps import get_current_user, get_db
from ..schemas.targets import TargetItem

router = APIRouter()


@router.get("/targets", response_model=list[TargetItem])
def list_targets(
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    List all active targets for the current user.

    Returns targets from database (Phase 0.4).
    """
    try:
        targets_repo = TargetsRepository(db)
        active_targets = targets_repo.get_active_by_user(current.id)

        # Convert to TargetItem schema
        return [
            TargetItem(
                id=target.id,
                symbol=target.symbol,
                target_price=target.target_price,
                entry_price=target.entry_price,
                current_price=target.current_price,
                quantity=target.quantity,
                distance_to_target=target.distance_to_target,
                distance_to_target_absolute=target.distance_to_target_absolute,
                target_type=target.target_type,
                is_active=target.is_active,
                achieved_at=target.achieved_at,
                note=None,  # Can be added to model later if needed
                created_at=target.created_at,
                updated_at=target.updated_at,
            )
            for target in active_targets
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch targets: {str(e)}") from e
