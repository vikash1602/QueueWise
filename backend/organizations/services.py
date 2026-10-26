"""Organization-scoped helpers: business dates and opening-hours logic."""
from datetime import date, datetime, time, timedelta

from django.utils import timezone as dj_timezone

from .models import BusinessHours


def local_business_date(organization, at=None):
    """The organization-local operating day for a moment in time."""
    at = at or dj_timezone.now()
    return at.astimezone(_tz(organization.timezone)).date()


def _tz(name):
    from zoneinfo import ZoneInfo

    return ZoneInfo(name)


def slots_for_service(organization, service, day):
    """Generate bookable slot datetimes (UTC) for a service on a date.

    Slots are aligned from opening time and repeat every
    duration+buffer minutes; the last slot must end before closing.
    Returns [] when the organization is closed that weekday.
    """
    hours = BusinessHours.objects.filter(organization=organization, weekday=day.weekday()).first()
    if hours is None or hours.is_closed:
        return []
    tz = _tz(organization.timezone)
    step = timedelta(minutes=service.duration_minutes + service.buffer_minutes)
    start = datetime.combine(day, hours.opens_at, tzinfo=tz)
    end_of_day = datetime.combine(day, hours.closes_at, tzinfo=tz)
    if start >= end_of_day:
        return []
    slots = []
    now = dj_timezone.now()
    while start + timedelta(minutes=service.duration_minutes) <= end_of_day:
        slot_end = start + timedelta(minutes=service.duration_minutes)
        if start > now:
            slots.append((start, slot_end))
        start += step
    return slots
