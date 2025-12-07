"""Transaction utilities for database operations."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


@contextmanager
def transaction(db_session: Session) -> Generator[Session, None, None]:
    """
    Context manager for database transactions.

    Ensures all operations within the context are atomic - either all succeed
    or all are rolled back on any exception.

    Usage:
        with transaction(db_session):
            positions_repo.upsert(..., auto_commit=False)
            orders_repo.update(..., auto_commit=False)
            # All changes committed here if no exception
            # All changes rolled back if any exception occurs

    Args:
        db_session: SQLAlchemy database session

    Yields:
        The same database session for use within the transaction

    Raises:
        Any exception that occurs during the transaction will trigger a rollback
    """
    try:
        yield db_session
        db_session.commit()
        logger.debug("Transaction committed successfully")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Transaction rolled back due to error: {e}")
        raise
