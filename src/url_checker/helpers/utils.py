# utils.py
from datetime import datetime, timezone


def to_utc_isoformat(dt: datetime | None) -> str | None:
    """
    Convert datetime to UTC ISO 8601 string.
    Defensive: handles naive datetimes just in case.
    """
    if dt is None:
        return None

    # If somehow still naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.isoformat()
