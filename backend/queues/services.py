"""Queue business logic: token allocation, state transitions, positions,
and waiting-time estimation. All mutations happen inside caller-provided
transactions; the caller (API layer) is responsible for atomicity."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone as dj_timezone

from .models import QueueEntry
from .exceptions import InvalidQueueTransition

ALLOWED_TRANSITIONS = {
    QueueEntry.Status.WAITING: {
        QueueEntry.Status.CALLED,
        QueueEntry.Status.CANCELLED,
        QueueEntry.Status.NO_SHOW,
    },
    QueueEntry.Status.CALLED: {
        QueueEntry.Status.IN_PROGRESS,
        QueueEntry.Status.WAITING,  # skipped back into the queue
        QueueEntry.Status.NO_SHOW,
        QueueEntry.Status.CANCELLED,
    },
    QueueEntry.Status.IN_PROGRESS: {QueueEntry.Status.COMPLETED, QueueEntry.Status.CANCELLED},
    QueueEntry.Status.COMPLETED: set(),
    QueueEntry.Status.NO_SHOW: set(),
    QueueEntry.Status.CANCELLED: set(),
}


def assert_can_transition(entry, new_status):
    if new_status not in ALLOWED_TRANSITIONS.get(entry.status, set()):
        raise InvalidQueueTransition(
            f"Cannot move entry from {entry.status} to {new_status}."
        )


def allocate_token(organization, service, business_date):
    """Return the next token number for the org+service+day scope.

    Caller must hold a lock (select_for_update) on the Service row and be
    inside a transaction so concurrent walk-ins serialize on that lock and
    receive gapless unique tokens (enforced additionally by the unique
    constraint as a last resort).
    """
    last = (
        QueueEntry.objects.filter(
            organization=organization, service=service, business_date=business_date
        )
        .select_for_update()
        .order_by("-token_number")
        .first()
    )
    return (last.token_number + 1) if last else 1


def transition(entry, new_status, *, when=None, counter=None):
    """Apply a state transition with timestamp bookkeeping."""
    assert_can_transition(entry, new_status)
    when = when or dj_timezone.now()
    entry.status = new_status
    if new_status == QueueEntry.Status.CALLED:
        entry.called_at = when
    elif new_status == QueueEntry.Status.IN_PROGRESS:
        entry.started_at = when
        if counter is not None:
            entry.counter = counter
    elif new_status == QueueEntry.Status.COMPLETED:
        entry.completed_at = when
    entry.save()
    return entry


def active_entries(organization, service, business_date, exclude_status=None):
    qs = QueueEntry.objects.filter(
        organization=organization, service=service, business_date=business_date
    )
    if exclude_status:
        qs = qs.exclude(status__in=exclude_status)
    return qs


def position_of(entry) -> int:
    """People still waiting ahead of this entry (1 = next to be called)."""
    if entry.status != QueueEntry.Status.WAITING:
        return 0
    ahead = QueueEntry.objects.filter(
        organization=entry.organization,
        service=entry.service,
        business_date=entry.business_date,
        status__in=[QueueEntry.Status.WAITING, QueueEntry.Status.CALLED],
        token_number__lt=entry.token_number,
    ).count()
    return ahead + 1


def estimated_service_minutes(service) -> int:
    """Best available per-customer service duration estimate."""
    return service.avg_duration_minutes or service.duration_minutes


def _recent_completed_minutes(service, limit=None):
    """Durations (minutes) of the last N completed services, outliers dropped."""
    limit = limit or settings.ESTIMATION_HISTORY_SIZE
    durations = (
        QueueEntry.objects.filter(
            service=service,
            status=QueueEntry.Status.COMPLETED,
            started_at__isnull=False,
            completed_at__isnull=False,
        )
        .order_by("-completed_at")
        .values_list("started_at", "completed_at")[:limit]
    )
    minutes = []
    for started, completed in durations:
        delta = (completed - started).total_seconds() / 60
        # Ignore absurd outliers (clock issues, left-open counters).
        if 0 < delta <= 8 * 60:
            minutes.append(delta)
    return minutes


def _median(values):
    values = sorted(values)
    n = len(values)
    if n == 0:
        return None
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def update_rolling_estimate(service):
    """Recompute the service's rolling median from recent completions and
    persist it. Called whenever a service completes."""
    median = _median(_recent_completed_minutes(service))
    if median is not None:
        service.avg_duration_minutes = max(1, round(median))
        service.save(update_fields=["avg_duration_minutes", "updated_at"])
    return service.avg_duration_minutes


def service_duration_estimate(service) -> int:
    """Per-customer duration: persisted rolling median, or the configured
    duration when no history exists yet."""
    return service.avg_duration_minutes or service.duration_minutes


def estimate_wait_minutes(entry_or_service, *, position=None, counters_active=None) -> int:
    """Estimated wait for a customer at `position` (1 = next).

    Method (documented in docs/waiting-time.md):
      - per-customer duration = rolling median of the last N completed
        durations for the service (fallback: configured duration);
      - with C active counters the waiting load is served in parallel, so
        wait = ceil((position - 1) / C) * duration;
      - CALLED entries still occupy their counter and count as load.
    """
    entry = entry_or_service if isinstance(entry_or_service, QueueEntry) else None
    service = entry.service if entry else entry_or_service
    if position is None:
        position = position_of(entry) if entry else 1
    if position <= 0:
        return 0
    duration = service_duration_estimate(service)
    if counters_active is None:
        counters_active = max(service.counters.filter(is_active=True).count(), 1)
    batches = -(-(position - 1) // max(counters_active, 1))  # ceil
    return int(batches * duration)


def refresh_estimates(organization, service, business_date):
    """Recalculate estimates for everyone still waiting. Called after any
    meaningful queue change (join, call, complete, no-show, cancel)."""
    waiting = active_entries(organization, service, business_date).filter(
        status=QueueEntry.Status.WAITING
    )
    updates = []
    for entry in waiting:
        entry.estimated_wait_minutes = estimate_wait_minutes(entry)
        updates.append(entry)
    if updates:
        QueueEntry.objects.bulk_update(updates, ["estimated_wait_minutes"])
    return updates
