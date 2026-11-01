"""Appointment booking logic. All correctness is enforced server-side:
availability grid, past-date rejection, and DB-level conflict prevention."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone as dj_timezone

from organizations.models import BusinessHours
from organizations.services import slots_for_service, _tz

from queues.exceptions import SlotUnavailable, OutsideBusinessHours
from .models import Appointment


def availability(organization, service, day):
    """Return bookable slots with their taken status for a date.

    A slot is taken when any live appointment overlaps it (not merely one
    with an identical start), so off-grid bookings still block the grid."""
    slots = slots_for_service(organization, service, day)
    now = dj_timezone.now()
    live = Appointment.objects.filter(
        service=service,
        slot_start__lt=max((end for _, end in slots), default=now),
        slot_end__gt=min((start for start, _ in slots), default=now),
    ).exclude(status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW])
    booked_ranges = [(a.slot_start, a.slot_end) for a in live]
    return [
        {
            "slot_start": start,
            "slot_end": end,
            "is_available": start > now
            and not any(b_start < end and b_end > start for b_start, b_end in booked_ranges),
        }
        for start, end in slots
    ]


@transaction.atomic
def book(*, customer, service, slot_start, organization=None):
    """Book an appointment for a validated slot. Raises SlotUnavailable /
    OutsideBusinessHours with a safe message when the slot cannot be taken.

    The service row is locked for the duration of validation + insert so that
    concurrent bookings for overlapping ranges serialize; the partial unique
    index on (service, slot_start) remains the final guarantee.
    """
    organization = organization or service.organization
    tz = _tz(organization.timezone)
    local_start = slot_start.astimezone(tz)

    if slot_start <= dj_timezone.now():
        raise SlotUnavailable("Appointment slots must be in the future.")
    today_local = dj_timezone.now().astimezone(tz).date()
    if local_start.date() > today_local + timedelta(days=service.max_advance_days):
        raise SlotUnavailable(
            f"Cannot book more than {service.max_advance_days} days ahead."
        )

    hours = BusinessHours.objects.filter(
        organization=organization, weekday=local_start.weekday()
    ).first()
    if hours is None or hours.is_closed:
        raise OutsideBusinessHours("The organization is closed on that day.")
    slot_end = slot_start + timedelta(minutes=service.duration_minutes)
    # The service plus its cleanup buffer must both fit inside operating
    # hours — backend-enforced so the frontend can never book past closing.
    buffer_end = slot_end + timedelta(minutes=service.buffer_minutes)
    local_end_t = buffer_end.astimezone(tz).time()
    if not (hours.opens_at <= local_start.time() and local_end_t <= hours.closes_at):
        raise OutsideBusinessHours(
            "The selected time is outside the organization's operating hours."
        )

    # Serialize concurrent bookings touching this service's grid.
    service = type(service).objects.select_for_update().get(pk=service.pk)

    overlapping = Appointment.objects.filter(
        service=service,
        slot_start__lt=slot_end,
        slot_end__gt=slot_start,
    ).exclude(status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW])
    if overlapping.exists():
        raise SlotUnavailable("That slot has just been taken. Please pick another.")

    return Appointment.objects.create(
        organization=organization,
        service=service,
        customer=customer,
        slot_start=slot_start,
        slot_end=slot_end,
        status=Appointment.Status.CONFIRMED,
    )


@transaction.atomic
def cancel(appointment, *, cancelled_by, reason=""):
    if appointment.status not in {
        Appointment.Status.CONFIRMED,
        Appointment.Status.CHECKED_IN,
    }:
        raise SlotUnavailable(
            f"An appointment with status {appointment.status} cannot be cancelled."
        )
    appointment.status = Appointment.Status.CANCELLED
    appointment.cancelled_by = cancelled_by
    appointment.cancel_reason = reason[:200]
    appointment.save(update_fields=["status", "cancelled_by", "cancel_reason", "updated_at"])
    return appointment
