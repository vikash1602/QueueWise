"""Higher-level queue workflows used by the API layer: joining the queue,
staff call-next, and status operations. Each public function is atomic and
records audit history + notifications + real-time broadcasts."""
from django.db import transaction
from django.utils import timezone as dj_timezone

from audit.services import record as audit_record
from notifications import services as notification_service
from organizations.models import BusinessHours, Service
from organizations.services import local_business_date

from .exceptions import InvalidQueueTransition, QueueWiseError
from .events import broadcast_entry_update
from .models import QueueEntry
from . import services as queue_services


def _entry_display_name(entry):
    if entry.customer_id:
        return entry.customer.get_full_name() or entry.customer.email
    return entry.guest_name or "Guest"


@transaction.atomic
def join_queue(*, organization, service, customer=None, guest_name="", source=None):
    """Add a customer (or guest walk-in registered by staff) to today's queue."""
    if not service.is_walkin_enabled:
        raise QueueWiseError("Walk-in queue is not enabled for this service.")
    business_date = local_business_date(organization)
    hours = BusinessHours.objects.filter(
        organization=organization, weekday=business_date.weekday()
    ).first()
    if hours is None or hours.is_closed:
        raise QueueWiseError("The organization is closed today.")
    if customer is None and not guest_name.strip():
        raise QueueWiseError("A guest name is required for staff-registered walk-ins.")

    # Lock the service row: serializes token allocation for this scope.
    locked_service = Service.objects.select_for_update().get(pk=service.pk)
    token = queue_services.allocate_token(organization, locked_service, business_date)
    waiting_count = QueueEntry.objects.filter(
        organization=organization,
        service=locked_service,
        business_date=business_date,
        status=QueueEntry.Status.WAITING,
    ).count()
    entry = QueueEntry.objects.create(
        organization=organization,
        service=locked_service,
        customer=customer,
        guest_name=guest_name.strip()[:120],
        source=source or QueueEntry.Source.WALKIN,
        token_number=token,
        business_date=business_date,
        status=QueueEntry.Status.WAITING,
        estimated_wait_minutes=queue_services.estimate_wait_minutes(
            locked_service, position=waiting_count + 1
        ),
    )
    queue_services.refresh_estimates(organization, locked_service, business_date)
    entry.refresh_from_db()
    return entry


@transaction.atomic
def check_in_appointment(appointment, *, actor):
    """Convert a confirmed appointment into a queue entry (customer arrives)."""
    from appointments.models import Appointment

    if appointment.status != Appointment.Status.CONFIRMED:
        raise QueueWiseError(
            f"Only confirmed appointments can be checked in (status: {appointment.status})."
        )
    appointment.status = Appointment.Status.CHECKED_IN
    appointment.save(update_fields=["status", "updated_at"])
    entry = join_queue(
        organization=appointment.organization,
        service=appointment.service,
        customer=appointment.customer,
        source=QueueEntry.Source.APPOINTMENT,
    )
    entry.appointment = appointment
    entry.save(update_fields=["appointment"])
    audit_record(
        actor=actor,
        organization=appointment.organization,
        action="APPOINTMENT_CHECKED_IN",
        object_type="queue_entry",
        object_id=entry.id,
        detail={"appointment_id": appointment.id, "token": entry.token_number},
    )
    return entry


@transaction.atomic
def call_next(*, organization, service, actor, counter=None):
    """Call the lowest-token waiting entry for a service."""
    entry = (
        QueueEntry.objects.select_for_update()
        .filter(
            organization=organization,
            service=service,
            business_date=local_business_date(organization),
            status=QueueEntry.Status.WAITING,
        )
        .order_by("token_number")
        .first()
    )
    if entry is None:
        raise QueueWiseError("No customers are waiting for this service.")
    return _call(entry, actor=actor, counter=counter)


@transaction.atomic
def _call(entry, *, actor, counter=None):
    queue_services.transition(entry, QueueEntry.Status.CALLED, counter=counter)
    audit_record(
        actor=actor,
        organization=entry.organization,
        action="QUEUE_CALLED",
        object_type="queue_entry",
        object_id=entry.id,
        detail={"token": entry.token_number},
    )
    if entry.customer_id:
        notification_service.create(
            user=entry.customer,
            type=notification_service.Notification.Types.QUEUE_CALLED,
            title="It's your turn",
            body=f"Token {entry.token_number} at {entry.service.name} — please approach the counter.",
            payload={"queue_entry_id": entry.id},
        )
    queue_services.refresh_estimates(
        entry.organization, entry.service, entry.business_date
    )
    broadcast_entry_update(entry)
    return entry


ACTIONS = {
    "call": QueueEntry.Status.CALLED,
    "start": QueueEntry.Status.IN_PROGRESS,
    "complete": QueueEntry.Status.COMPLETED,
    "no-show": QueueEntry.Status.NO_SHOW,
    "cancel": QueueEntry.Status.CANCELLED,
}


@transaction.atomic
def perform_staff_action(*, entry, action, actor, counter=None):
    """Apply a staff queue action with transition validation and bookkeeping."""
    try:
        new_status = ACTIONS[action]
    except KeyError:
        raise QueueWiseError(f"Unknown queue action '{action}'.")

    previous_status = entry.status
    if action == "call" and previous_status == QueueEntry.Status.WAITING:
        return _call(entry, actor=actor, counter=counter)

    queue_services.transition(entry, new_status, counter=counter)
    audit_record(
        actor=actor,
        organization=entry.organization,
        action=f"QUEUE_{new_status}",
        object_type="queue_entry",
        object_id=entry.id,
        detail={"token": entry.token_number, "from": previous_status},
    )
    if entry.customer_id:
        titles = {
            QueueEntry.Status.COMPLETED: "Service completed",
            QueueEntry.Status.CANCELLED: "Queue entry cancelled",
        }
        if new_status in titles:
            notification_service.create(
                user=entry.customer,
                type=notification_service.Notification.Types.QUEUE_COMPLETED
                if new_status == QueueEntry.Status.COMPLETED
                else notification_service.Notification.Types.QUEUE_CANCELLED,
                title=titles[new_status],
                body=f"Token {entry.token_number} at {entry.service.name}.",
                payload={"queue_entry_id": entry.id},
            )

    if new_status == QueueEntry.Status.COMPLETED:
        # Maintain the rolling median used for waiting-time estimation.
        queue_services.update_rolling_estimate(entry.service)

    queue_services.refresh_estimates(entry.organization, entry.service, entry.business_date)
    broadcast_entry_update(entry)
    return entry


@transaction.atomic
def cancel_by_customer(entry, *, actor):
    if entry.customer_id != actor.id:
        raise PermissionError("You can only cancel your own queue entries.")
    if entry.status not in {QueueEntry.Status.WAITING}:
        raise InvalidQueueTransition(
            f"Entries with status {entry.status} can no longer be cancelled."
        )
    queue_services.transition(entry, QueueEntry.Status.CANCELLED)
    audit_record(
        actor=actor,
        organization=entry.organization,
        action="QUEUE_CANCELLED",
        object_type="queue_entry",
        object_id=entry.id,
        detail={"token": entry.token_number, "by": "customer"},
    )
    queue_services.refresh_estimates(entry.organization, entry.service, entry.business_date)
    broadcast_entry_update(entry)
    return entry
