"""
Timezone utilities for database models

All datetime fields use IST (Indian Standard Time, UTC+5:30)
"""

from datetime import UTC, datetime, timedelta, timezone

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# NSE market-open window (IST). Used to source the day's opening price for
# AMO fills at market open instead of the previous session's close.
MARKET_OPEN_HOUR = 9
MARKET_OPEN_START_MIN = 15
MARKET_OPEN_END_MIN = 20

# Plausible-age bounds for disambiguating IST-naive vs UTC-naive DB timestamps.
_MIN_PLAUSIBLE_AGE_MINUTES = -5
_MAX_PLAUSIBLE_AGE_MINUTES = 24 * 60
_MIN_PLAUSIBLE_AGE_SECONDS = -60
_MAX_PLAUSIBLE_AGE_SECONDS = 7 * 86400


def is_market_open_window(now: datetime) -> bool:
    """Return True if ``now`` falls within the NSE market-open window (09:15-09:20 IST)."""
    return (
        now.hour == MARKET_OPEN_HOUR and MARKET_OPEN_START_MIN <= now.minute <= MARKET_OPEN_END_MIN
    )


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


def coerce_db_timestamp_to_ist(dt: datetime, *, reference: datetime | None = None) -> datetime:
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
    if _MIN_PLAUSIBLE_AGE_MINUTES <= age_min <= _MAX_PLAUSIBLE_AGE_MINUTES:
        return as_ist
    return dt.replace(tzinfo=UTC).astimezone(IST)


def service_status_heartbeat_age_seconds(
    last_heartbeat: datetime | None,
    *,
    reference: datetime | None = None,
) -> float | None:
    """
    Compute heartbeat age in seconds for ``service_status.last_heartbeat``.

    Naive DB values may be IST wall-clock (``ist_now_naive()``) or UTC wall-clock
    (legacy writes via timezone-aware ``ist_now()`` through psycopg2). Both
    interpretations are evaluated; the smallest non-negative plausible age wins.
    """
    if last_heartbeat is None:
        return None

    ref = reference or ist_now()
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=IST)

    if last_heartbeat.tzinfo is not None:
        return (ref - last_heartbeat.astimezone(IST)).total_seconds()

    age_as_ist_naive = (ref - last_heartbeat.replace(tzinfo=IST)).total_seconds()
    age_as_utc_stored = (ref - utc_to_ist(last_heartbeat.replace(tzinfo=UTC))).total_seconds()
    candidates = [age_as_ist_naive, age_as_utc_stored]
    plausible = [
        age for age in candidates if _MIN_PLAUSIBLE_AGE_SECONDS <= age <= _MAX_PLAUSIBLE_AGE_SECONDS
    ]
    if plausible:
        return min(plausible)
    return min(candidates)


def service_status_heartbeat_to_utc_for_api(
    last_heartbeat: datetime | None,
    *,
    reference: datetime | None = None,
) -> datetime | None:
    """
    Serialize ``service_status.last_heartbeat`` to UTC for API JSON.

    Uses the same IST-vs-UTC-naive disambiguation as
    ``service_status_heartbeat_age_seconds`` so the UI absolute time and
    relative age stay consistent.
    """
    if last_heartbeat is None:
        return None
    if last_heartbeat.tzinfo is not None:
        return last_heartbeat.astimezone(UTC)

    ref = reference or ist_now()
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=IST)

    instant_as_ist_write = ist_to_utc(last_heartbeat.replace(tzinfo=IST))
    instant_as_utc_write = last_heartbeat.replace(tzinfo=UTC)
    age_as_ist = (ref - last_heartbeat.replace(tzinfo=IST)).total_seconds()
    age_as_utc = (ref - utc_to_ist(instant_as_utc_write)).total_seconds()
    candidates = [(age_as_ist, instant_as_ist_write), (age_as_utc, instant_as_utc_write)]
    plausible = [
        (age, instant)
        for age, instant in candidates
        if _MIN_PLAUSIBLE_AGE_SECONDS <= age <= _MAX_PLAUSIBLE_AGE_SECONDS
    ]
    if plausible:
        return min(plausible, key=lambda pair: pair[0])[1]
    return min(candidates, key=lambda pair: pair[0])[1]


def db_timestamp_to_utc_for_api(
    dt: datetime | None,
    *,
    reference: datetime | None = None,
) -> datetime | None:
    """
    Normalize a DB datetime to UTC for API JSON serialization.

    Naive values are treated as IST wall-clock when plausible (``ist_now_naive()``),
    with legacy UTC-naive fallback via ``coerce_db_timestamp_to_ist``.
    """
    if dt is None:
        return None
    return ist_to_utc(coerce_db_timestamp_to_ist(dt, reference=reference))


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
