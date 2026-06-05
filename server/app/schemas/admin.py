from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from .auth import PasswordStr, validate_password_strength


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: PasswordStr
    name: str = Field(min_length=1, max_length=255)
    role: Literal["admin", "user"] = "user"

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Name is required")
        return trimmed

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password_strength(value)


class AdminUserUpdate(BaseModel):
    name: str | None = None
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None


class AdminUserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str | None
    role: Literal["admin", "user"]
    is_active: bool
