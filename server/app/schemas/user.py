from typing import Literal

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    trade_mode: Literal["paper", "broker"]
    broker: str | None = None
    broker_status: str | None = None


class SettingsUpdateRequest(BaseModel):
    trade_mode: Literal["paper", "broker"] | None = None
    broker: str | None = None
    broker_status: str | None = None
    # credentials handled server-side; not exposed here
