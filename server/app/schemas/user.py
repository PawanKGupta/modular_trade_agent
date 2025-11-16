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
    api_key: str = Field(min_length=1)
    api_secret: str = Field(min_length=1)


class BrokerTestResponse(BaseModel):
    ok: bool
    message: str | None = None
