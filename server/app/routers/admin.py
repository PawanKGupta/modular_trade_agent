from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.user_repository import UserRepository

from ..core.deps import get_db, require_admin
from ..schemas.admin import AdminUserCreate, AdminUserResponse, AdminUserUpdate

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(db: Session = Depends(get_db)):
    users = UserRepository(db).list_users(active_only=False)
    return [
        AdminUserResponse(
            id=u.id, email=u.email, name=u.name, role=u.role.value, is_active=u.is_active
        )
        for u in users
    ]


@router.post("/users", response_model=AdminUserResponse)
def create_user(payload: AdminUserCreate, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    role = UserRole(payload.role)
    u = repo.create_user(
        email=payload.email, password=payload.password, name=payload.name, role=role
    )
    return AdminUserResponse(
        id=u.id, email=u.email, name=u.name, role=u.role.value, is_active=u.is_active
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(user_id: int, payload: AdminUserUpdate, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    role = UserRole(payload.role) if payload.role else None
    u = repo.update_user(user, name=payload.name, role=role, is_active=payload.is_active)
    return AdminUserResponse(
        id=u.id, email=u.email, name=u.name, role=u.role.value, is_active=u.is_active
    )


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent deleting last admin
    def is_admin(u) -> bool:
        try:
            return getattr(u.role, "value", str(u.role)).lower() == "admin"
        except Exception:
            return False

    if is_admin(user):
        admins = [u for u in repo.list_users(active_only=False) if is_admin(u) and u.is_active]
        if len(admins) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete last admin"
            )
    repo.update_user(user, is_active=False)
    return {"status": "ok"}
