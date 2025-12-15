"""Database dialect detection utilities for cross-database compatibility."""

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session


def is_postgresql(db_session: Session) -> bool:
    """Check if the database session is using PostgreSQL.

    Args:
        db_session: SQLAlchemy session

    Returns:
        True if database is PostgreSQL, False otherwise
    """
    try:
        return isinstance(db_session.bind.dialect, postgresql.dialect)
    except AttributeError:
        # Fallback: check connection URL
        url = str(db_session.bind.url)
        return url.startswith("postgresql") or url.startswith("postgres")


def is_sqlite(db_session: Session) -> bool:
    """Check if the database session is using SQLite.

    Args:
        db_session: SQLAlchemy session

    Returns:
        True if database is SQLite, False otherwise
    """
    try:
        return isinstance(db_session.bind.dialect, sqlite.dialect)
    except AttributeError:
        # Fallback: check connection URL
        url = str(db_session.bind.url)
        return url.startswith("sqlite")
