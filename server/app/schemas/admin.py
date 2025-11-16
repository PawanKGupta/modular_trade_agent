from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str | None = None
    role: Literal["admin", "user"] = "user"


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
