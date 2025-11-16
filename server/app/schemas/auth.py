from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None
    roles: list[Literal["admin", "user"]]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
