import re
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from server.app.core.email_policy import validate_email_domain_allowed

_PASSWORD_MIN_LENGTH = 8


def validate_password_strength(value: str) -> str:
    if len(value) < _PASSWORD_MIN_LENGTH:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Za-z]", value):
        raise ValueError("Password must include at least one letter")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must include at least one capital letter")
    if not re.search(r"\d", value):
        raise ValueError("Password must include at least one number")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise ValueError("Password must include at least one special character")
    return value


PasswordStr = Annotated[str, Field(min_length=_PASSWORD_MIN_LENGTH)]

_INDIAN_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


def normalize_optional_mobile(value: str | None) -> str | None:
    """Normalize optional Indian mobile: empty -> None, else 10 digits starting 6-9."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    digits = re.sub(r"\D", "", trimmed)
    if not _INDIAN_MOBILE_RE.match(digits):
        raise ValueError("Enter a valid 10-digit Indian mobile number")
    return digits


class SignupRequest(BaseModel):
    email: EmailStr
    password: PasswordStr
    name: str = Field(min_length=1, max_length=255)
    mobile_number: str | None = None

    @field_validator("email")
    @classmethod
    def email_domain_allowed(cls, value: str) -> str:
        return validate_email_domain_allowed(value)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Name is required")
        return trimmed

    @field_validator("mobile_number", mode="before")
    @classmethod
    def mobile_optional(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator("mobile_number")
    @classmethod
    def mobile_valid(cls, value: str | None) -> str | None:
        return normalize_optional_mobile(value)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password_strength(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: PasswordStr

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password_strength(value)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: PasswordStr

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password_strength(value)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1)


class MessageResponse(BaseModel):
    message: str


class SignupResponse(BaseModel):
    message: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"  # noqa: S105
    csrf_token: str | None = None
    mfa_required: bool = False
    mfa_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    backup_codes: list[str]


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class MfaLoginRequest(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=16)


class MfaDisableRequest(BaseModel):
    current_password: str
    code: str = Field(min_length=6, max_length=16)


class DeleteAccountRequest(BaseModel):
    current_password: str
    code: str | None = None


class MeResponse(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None
    mobile_number: str | None = None
    roles: list[Literal["admin", "user"]]
    email_verified: bool = True
    must_change_password: bool = False
    mfa_enabled: bool = False


class UpdateProfileRequest(BaseModel):
    email: EmailStr | None = None
    mobile_number: str | None = None
    current_password: str | None = None

    @field_validator("email")
    @classmethod
    def email_domain_allowed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_email_domain_allowed(value)

    @field_validator("mobile_number", mode="before")
    @classmethod
    def mobile_optional(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator("mobile_number")
    @classmethod
    def mobile_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_optional_mobile(value)


class ProfileUpdateResponse(BaseModel):
    message: str
    email: EmailStr
    mobile_number: str | None = None
    email_verified: bool
    verification_required: bool = False
