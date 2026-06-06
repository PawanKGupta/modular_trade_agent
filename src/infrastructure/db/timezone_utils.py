"""
Timezone utilities for database models

All datetime fields use IST (Indian Standard Time, UTC+5:30)
"""

from datetime import UTC, datetime, timedelta, timezone

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def ist_now() -> datetime:
    """
    Get current datetime in IST timezone

    Returns:
        datetime: Current datetime in IST timezone
    """
    return datetime.now(IST)


def ist_now_naive() -> datetime:
    """
    Get current datetime in IST as a naive datetime (no tzinfo).

    Use when writing to TIMESTAMP WITHOUT TIME ZONE columns so the stored
    value is the IST clock time (e.g. 16:00 for 4 PM IST). If you pass
    timezone-aware IST, psycopg2 converts to UTC before storing.
    """
    return datetime.now(IST).replace(tzinfo=None)


def utc_to_ist(utc_dt: datetime) -> datetime:
    """
    Convert UTC datetime to IST

    Args:
        utc_dt: UTC datetime (naive or timezone-aware)

    Returns:
        datetime: IST datetime (timezone-aware)
    """
    if utc_dt.tzinfo is None:
        # Assume naive datetime is UTC
        utc_dt = utc_dt.replace(tzinfo=UTC)
    return utc_dt.astimezone(IST)


def as_ist_aware(dt: datetime) -> datetime:
    """
    Coerce a DB/API timestamp to timezone-aware IST.

    Naive values are treated as IST wall-clock (orders/positions convention).
    """
    if dt.tzinfo is not None:
        return dt.astimezone(IST)
    return dt.replace(tzinfo=IST)


def coerce_db_timestamp_to_ist(
    dt: datetime, *, reference: datetime | None = None
) -> datetime:
    """
    Normalize naive DB timestamps to aware IST.

    Most columns store IST naive via ``ist_now_naive()``. Legacy rows written
    with timezone-aware ``ist_now()`` were persisted as UTC naive by psycopg2;
    when interpreting as IST would imply an implausible age (>24h in the past
    while reference is "now"), fall back to UTC→IST conversion.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(IST)
    ref = reference or ist_now()
    as_ist = dt.replace(tzinfo=IST)
    age_min = (ref - as_ist).total_seconds() / 60
    if -5 <= age_min <= 24 * 60:
        return as_ist
    return dt.replace(tzinfo=UTC).astimezone(IST)


def ist_to_utc(ist_dt: datetime) -> datetime:
    """
    Convert IST datetime to UTC

    Args:
        ist_dt: IST datetime (naive or timezone-aware)

    Returns:
        datetime: UTC datetime (timezone-aware)
    """
    if ist_dt.tzinfo is None:
        # Assume naive datetime is IST
        ist_dt = ist_dt.replace(tzinfo=IST)
    return ist_dt.astimezone(UTC)
