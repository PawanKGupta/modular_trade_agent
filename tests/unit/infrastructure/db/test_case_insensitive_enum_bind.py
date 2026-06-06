"""Bind-param branches for `CaseInsensitiveEnum` (name fallback)."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy.dialects import sqlite

from src.infrastructure.db.case_insensitive_enum import CaseInsensitiveEnum


class _Sample(StrEnum):
    """Name differs from stored value to exercise name-based bind matching."""

    ALPHA_CODE = "alpha"


def test_process_bind_param_matches_member_name_not_value():
    col = CaseInsensitiveEnum(_Sample)
    dialect = sqlite.dialect()
    # String "ALPHA_CODE" does not equal value "alpha" case-insensitively as value match,
    # but matches enum member name and returns the canonical DB value.
    assert col.process_bind_param("ALPHA_CODE", dialect) == "alpha"


def test_find_enum_member_by_name():
    col = CaseInsensitiveEnum(_Sample)
    assert col._find_enum_member("ALPHA_CODE") == _Sample.ALPHA_CODE
