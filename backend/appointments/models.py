from django.conf import settings
from django.db import models


class Appointment(models.Model):
    """A booked time slot for one customer at one service.

    Conflict prevention: a *partial* unique index on (service, slot_start)
    restricted to live statuses makes double-booking impossible at the
    database level, independent of application checks.
    """

    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        CHECKED_IN = "CHECKED_IN", "Checked in"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No-show"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="appointments"
    )
    service = models.ForeignKey(
        "organizations.Service", on_delete=models.CASCADE, related_name="appointments"
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments"
    )
    slot_start = models.DateTimeField(db_index=True)
    slot_end = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cancelled_appointments",
    )
    cancel_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slot_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["service", "slot_start"],
                condition=~models.Q(status__in=["CANCELLED", "NO_SHOW"]),
                name="uniq_live_booking_per_service_slot",
            ),
            models.CheckConstraint(
                check=models.Q(slot_end__gt=models.F("slot_start")),
                name="appointment_end_after_start",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "slot_start"], name="idx_appt_org_slot"
            ),
            models.Index(fields=["customer", "status"], name="idx_appt_customer"),
        ]

    def __str__(self):
        return f"{self.service_id} {self.slot_start:%Y-%m-%d %H:%M} {self.status}"
