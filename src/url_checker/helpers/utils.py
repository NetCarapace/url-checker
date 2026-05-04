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


def str_to_bool(value, default=False):
    """
    Convert a string supposed to be a boolean to a real boolean type after some validation.
    Default to False if non recognised or missing.
    """
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default
