from datetime import timezone

from sqlalchemy import DateTime, TypeDecorator


class UTCDateTime(TypeDecorator):
    """DateTime type that enforces UTC timezone"""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Ensure UTC when writing to DB"""
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        """Ensure UTC when reading from DB"""
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value
