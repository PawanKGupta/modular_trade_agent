from typing import Literal

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    trade_mode: Literal["paper", "broker"]
    broker: str | None = None
    broker_status: str | None = None


class SettingsUpdateRequest(BaseModel):
    trade_mode: Literal["paper", "broker"] | None = None
    broker: str | None = None
    broker_status: str | None = None
    # credentials handled server-side; not exposed here


class BrokerCredsRequest(BaseModel):
    broker: Literal["kotak-neo"] = "kotak-neo"
    api_key: str = Field(min_length=1, description="Consumer Key (KOTAK_CONSUMER_KEY)")
    api_secret: str = Field(min_length=1, description="Consumer Secret (KOTAK_CONSUMER_SECRET)")
    # Optional fields for full Kotak Neo authentication test
    mobile_number: str | None = Field(None, description="Mobile number for login")
    password: str | None = Field(None, description="Password for login")
    mpin: str | None = Field(None, description="MPIN for 2FA (or use totp_secret)")
    totp_secret: str | None = Field(None, description="TOTP secret for 2FA (alternative to mpin)")
    environment: str | None = Field("prod", description="Environment: 'prod' or 'dev'")


class BrokerTestResponse(BaseModel):
    ok: bool
    message: str | None = None


class BrokerCredsInfo(BaseModel):
    """Information about stored broker credentials."""

    has_creds: bool
    api_key: str | None = None  # Full value when requested
    api_secret: str | None = None  # Full value when requested
    mobile_number: str | None = None
    password: str | None = None
    mpin: str | None = None
    totp_secret: str | None = None
    environment: str | None = None
    api_key_masked: str | None = None  # e.g., "****1234" (last 4 chars)
    api_secret_masked: str | None = None  # e.g., "****5678"
