from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, constr


class ServiceLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    level: str
    module: str
    message: str
    context: dict | None = None
    timestamp: datetime


class ServiceLogsResponse(BaseModel):
    logs: list[ServiceLogEntry]


class ErrorLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    error_type: str
    error_message: str
    traceback: str | None = None
    context: dict | None = None
    resolved: bool
    resolved_at: datetime | None = None
    resolved_by: int | None = None
    resolution_notes: str | None = None
    occurred_at: datetime


class ErrorLogsResponse(BaseModel):
    errors: list[ErrorLogEntry]


class ErrorResolutionRequest(BaseModel):
    notes: constr(max_length=512) | None = None


class ErrorResolutionResponse(BaseModel):
    message: str
    error: ErrorLogEntry
