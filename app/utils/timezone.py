from datetime import datetime, date
from zoneinfo import ZoneInfo
from app.config import settings

IST_ZONE = ZoneInfo(settings.TIMEZONE)


def get_ist_now() -> datetime:
    """
    Returns current datetime in Asia/Kolkata timezone.
    Returns naive datetime for clean cross-platform SQLite storage.
    """
    return datetime.now(IST_ZONE).replace(tzinfo=None)


def get_ist_today() -> date:
    """Returns current calendar date in Asia/Kolkata timezone."""
    return datetime.now(IST_ZONE).date()


def format_datetime_ist(dt: datetime) -> str:
    """Formats datetime nicely with AM/PM for UI display."""
    if not dt:
        return ""
    return dt.strftime("%d %b %Y, %I:%M:%S %p")


def format_time_ist(dt: datetime) -> str:
    """Formats time with AM/PM."""
    if not dt:
        return ""
    return dt.strftime("%I:%M:%S %p")
