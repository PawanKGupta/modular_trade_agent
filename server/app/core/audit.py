"""Audit trail helper — never log plaintext secrets."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Users
from src.infrastructure.persistence.audit_log_repository import AuditLogRepository

from .rate_limit import get_client_ip

logger = logging.getLogger(__name__)

_SENSITIVE_SUBSTRINGS = (
    "password",
    "token",
    "secret",
    "mpin",
    "api_key",
    "api_secret",
    "totp",
    "authorization",
    "credential",
)


def _sanitize_value(key: str, value: Any) -> Any:
    key_lower = key.lower()
    if any(s in key_lower for s in _SENSITIVE_SUBSTRINGS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(str(i), v) for i, v in enumerate(value)]
    return value


def sanitize_changes(changes: dict | None) -> dict | None:
    """Remove sensitive fields from audit change payloads."""
    if not changes:
        return changes
    return {k: _sanitize_value(k, v) for k, v in changes.items()}


def record_audit(
    db: Session,
    *,
    user_id: int,
    action: str,
    resource_type: str,
    request: Request | None = None,
    resource_id: int | None = None,
    changes: dict | None = None,
) -> None:
    """Persist an audit log entry; failures are logged but do not break the request."""
    try:
        ip_address = get_client_ip(request) if request else None
        user_agent = request.headers.get("User-Agent") if request else None
        AuditLogRepository(db).create(
            user_id=user_id,
            action=action,  # type: ignore[arg-type]
            resource_type=resource_type,
            resource_id=resource_id,
            changes=sanitize_changes(changes),
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else None,
        )
    except Exception:
        logger.exception("Failed to record audit log action=%s resource=%s", action, resource_type)


def record_audit_user(
    db: Session,
    user: Users,
    *,
    action: str,
    resource_type: str,
    request: Request | None = None,
    resource_id: int | None = None,
    changes: dict | None = None,
) -> None:
    """Record audit for the acting user."""
    record_audit(
        db,
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        request=request,
        resource_id=resource_id,
        changes=changes,
    )
