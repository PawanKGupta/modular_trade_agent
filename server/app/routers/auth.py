# ruff: noqa: B008
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.infrastructure.db.models import UserRole, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_repository import UserRepository

from ..core.deps import get_current_user, get_db
from ..core.security import create_access_token, verify_password
from ..schemas.auth import LoginRequest, MeResponse, SignupRequest, TokenResponse

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


@router.post("/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    try:
        logger.info(f"Signup request for {payload.email}")
        user_repo = UserRepository(db)
        existing = user_repo.get_by_email(payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            )
        logger.info("Creating user...")
        user = user_repo.create_user(
            email=payload.email, password=payload.password, name=payload.name, role=UserRole.USER
        )
        logger.info(f"User created id={user.id}, creating default settings...")
        SettingsRepository(db).ensure_default(user.id)
        logger.info("Default settings created, issuing token...")
        access_token = create_access_token(
            str(user.id), extra={"uid": user.id, "roles": [user.role.value]}
        )
        logger.info("Signup success")
        return TokenResponse(access_token=access_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Signup failed: {e}")
        raise HTTPException(status_code=500, detail="Signup failed") from e


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(payload.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        # Handle legacy plain-text passwords (from initial fallback) by detecting non-bcrypt hashes
        pwh = user.password_hash or ""
        is_bcrypt = pwh.startswith("$2a$") or pwh.startswith("$2b$") or pwh.startswith("$2y$")
        if not is_bcrypt:
            # If it matches exactly, rehash and save; otherwise invalid
            if payload.password == pwh:
                user_repo.set_password(user, payload.password)
                logger.info(f"Upgraded password hash for user id={user.id}")
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
                )
        elif not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        access_token = create_access_token(
            str(user.id), extra={"uid": user.id, "roles": [user.role.value]}
        )
        return TokenResponse(access_token=access_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login failed")
        raise HTTPException(status_code=500, detail="Login failed") from e


@router.get("/me", response_model=MeResponse)
def me(current: Users = Depends(get_current_user)):
    return MeResponse(
        id=current.id,
        email=current.email,
        name=current.name,
        roles=[current.role.value],
    )
