from __future__ import annotations

from sqlalchemy.orm import Session

from server.app.core.security import hash_password
from src.infrastructure.db.models import UserRole, Users


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Users | None:
        return self.db.get(Users, user_id)

    def get_by_email(self, email: str) -> Users | None:
        return self.db.query(Users).filter(Users.email == email).first()

    def list_users(self, active_only: bool = True) -> list[Users]:
        q = self.db.query(Users)
        if active_only:
            q = q.filter(Users.is_active.is_(True))
        return q.order_by(Users.created_at.desc()).all()

    def create_user(
        self, email: str, password: str, name: str | None = None, role: UserRole = UserRole.USER
    ) -> Users:
        hashed = hash_password(password)
        user = Users(
            email=email,
            name=name,
            role=role,
            is_active=True,
            password_hash=hashed,
        )
        self.db.add(user)
        try:
            self.db.commit()
        except Exception as e:
            # Print to stdout so it appears in simple logs
            print(f"[UserRepository] commit failed: {e}")
            raise
        self.db.refresh(user)
        return user

    def set_password(self, user: Users, new_password: str) -> None:
        user.password_hash = hash_password(new_password)
        self.db.commit()

    def update_user(
        self,
        user: Users,
        *,
        name: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> Users:
        if name is not None:
            user.name = name
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        self.db.commit()
        self.db.refresh(user)
        return user
