"""
Database Connection Pool Monitoring

Utilities for monitoring SQLAlchemy connection pool health and usage.
"""

from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool


def get_pool_status(engine: Engine) -> dict[str, Any]:
    """
    Get current connection pool status.

    Args:
        engine: SQLAlchemy engine instance

    Returns:
        Dictionary with pool metrics:
        - size: Current pool size
        - checked_in: Available connections
        - checked_out: Active connections
        - overflow: Overflow connections in use
        - max_overflow: Maximum overflow allowed
        - pool_size: Configured pool size
        - total_connections: checked_out + checked_in + overflow
    """
    pool: Pool = engine.pool

    # StaticPool (used in tests) doesn't have these methods
    # Check if pool supports standard pool interface
    if not hasattr(pool, "size"):
        # StaticPool or other simple pool - return minimal status
        return {
            "pool_size": 0,
            "checked_in": 0,
            "checked_out": 0,
            "overflow": 0,
            "max_overflow": 0,
            "total_connections": 0,
            "utilization_percent": 0.0,
        }

    # Get pool statistics
    status = {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "max_overflow": getattr(pool, "_max_overflow", 0),
    }

    # Calculate total connections
    status["total_connections"] = status["checked_out"] + status["checked_in"] + status["overflow"]

    # Add pool utilization percentage
    max_total = status["pool_size"] + status["max_overflow"]
    if max_total > 0:
        status["utilization_percent"] = (status["total_connections"] / max_total) * 100
    else:
        status["utilization_percent"] = 0.0

    return status


def log_pool_status(engine: Engine, logger=None) -> None:
    """
    Log current connection pool status.

    Args:
        engine: SQLAlchemy engine instance
        logger: Optional logger instance (uses print if None)
    """
    status = get_pool_status(engine)

    message = (
        f"📊 DB Connection Pool Status: "
        f"{status['checked_out']} active, "
        f"{status['checked_in']} available, "
        f"{status['overflow']} overflow, "
        f"{status['total_connections']}/{status['pool_size'] + status['max_overflow']} total "
        f"({status['utilization_percent']:.1f}% utilized)"
    )

    if logger:
        logger.info(message)
    else:
        print(message)


def check_pool_health(engine: Engine) -> tuple[bool, str]:
    """
    Check if connection pool is healthy.

    Args:
        engine: SQLAlchemy engine instance

    Returns:
        (is_healthy: bool, message: str)
    """
    status = get_pool_status(engine)

    # Check for pool exhaustion
    max_total = status["pool_size"] + status["max_overflow"]
    if status["total_connections"] >= max_total:
        return False, f"Connection pool exhausted: {status['total_connections']}/{max_total}"

    # Warn if utilization is high (>80%)
    if status["utilization_percent"] > 80:
        return (
            True,
            f"High pool utilization: {status['utilization_percent']:.1f}% "
            f"({status['total_connections']}/{max_total})",
        )

    return True, "Pool healthy"


def get_active_connections_count(engine: Engine) -> int:
    """
    Get count of currently active database connections.

    Args:
        engine: SQLAlchemy engine instance

    Returns:
        Number of checked-out connections
    """
    pool = engine.pool
    if not hasattr(pool, "checkedout"):
        return 0
    return pool.checkedout()
