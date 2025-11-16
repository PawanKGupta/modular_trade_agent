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
