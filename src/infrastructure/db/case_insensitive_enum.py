"""
Case-insensitive enum type for SQLAlchemy.

Handles conversion between database values (which may be lowercase)
and Python enum values (which are uppercase names).
"""

from enum import Enum
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import TypeDecorator


class CaseInsensitiveEnum(TypeDecorator):
    """
    SQLAlchemy type that handles case-insensitive enum conversion.

    This is useful when the database has lowercase values but SQLAlchemy
    expects uppercase enum names, or vice versa.
    """

    impl = SAEnum
    cache_ok = True

    def __init__(self, enum_class: type[Enum], *args: Any, **kwargs: Any):
        """
        Initialize with enum class.

        Args:
            enum_class: The Enum class to use
            *args: Additional arguments for SAEnum
            **kwargs: Additional keyword arguments for SAEnum
        """
        # Use values_callable to store enum values (lowercase) instead of names (uppercase)
        # Also use native_enum=False for SQLite to avoid enum type validation issues
        if "values_callable" not in kwargs:
            kwargs["values_callable"] = lambda x: [e.value for e in x]
        if "native_enum" not in kwargs:
            kwargs["native_enum"] = False  # Use string storage for SQLite compatibility
        super().__init__(enum_class, *args, **kwargs)
        self.enum_class = enum_class

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        """Convert Python enum to database value"""
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value  # Store the enum value (lowercase)
        if isinstance(value, str):
            # Try to match by value first (case-insensitive)
            value_lower = value.lower()
            for enum_member in self.enum_class:
                if enum_member.value.lower() == value_lower:
                    return enum_member.value
            # Fallback: try to match by name (case-insensitive)
            value_upper = value.upper()
            for enum_member in self.enum_class:
                if enum_member.name.upper() == value_upper:
                    return enum_member.value
        return value

    def _find_enum_member(self, value: str) -> Any:
        """Helper to find enum member by value or name (case-insensitive)"""
        value_lower = value.lower()
        value_upper = value.upper()

        # Try to match by value first (case-insensitive)
        for enum_member in self.enum_class:
            if enum_member.value.lower() == value_lower:
                return enum_member

        # Fallback: try to match by name (case-insensitive)
        for enum_member in self.enum_class:
            if enum_member.name.upper() == value_upper:
                return enum_member

        return None

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """Convert database value to Python enum"""
        if value is None or isinstance(value, self.enum_class):
            return value
        if not isinstance(value, str):
            return value

        # Try to find enum member using helper
        enum_member = self._find_enum_member(value)
        if enum_member is not None:
            return enum_member

        # If no match, try direct lookup
        try:
            return self.enum_class(value)
        except ValueError:
            # If still no match, return the value as-is (will cause error downstream)
            return value
