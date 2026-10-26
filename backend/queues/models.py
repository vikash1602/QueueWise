from django.conf import settings
from django.db import models


class QueueEntry(models.Model):
    """A customer's place in a walk-in or appointment queue for one operating
    day. Token numbers are unique per (organization, service, business_date).

    State machine (enforced in queues.services.transition):
        WAITING -> CALLED -> IN_PROGRESS -> COMPLETED
        WAITING/CALLED -> NO_SHOW
        WAITING -> CANCELLED (customer or staff)
        CALLED -> WAITING (skip/requeue)
    """

    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        CALLED = "CALLED", "Called"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        NO_SHOW = "NO_SHOW", "No-show"
        CANCELLED = "CANCELLED", "Cancelled"

    class Source(models.TextChoices):
        WALKIN = "WALKIN", "Walk-in"
        APPOINTMENT = "APPOINTMENT", "Appointment"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="queue_entries"
    )
    service = models.ForeignKey(
        "organizations.Service", on_delete=models.CASCADE, related_name="queue_entries"
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="queue_entries",
    )
    guest_name = models.CharField(
        max_length=120, blank=True,
        help_text="Name for staff-registered walk-ins without an account.",
    )
    appointment = models.OneToOneField(
        "appointments.Appointment", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="queue_entry",
    )
    source = models.CharField(max_length=12, choices=Source.choices)
    token_number = models.PositiveIntegerField()
    business_date = models.DateField(db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WAITING)
    counter = models.ForeignKey(
        "organizations.ServiceCounter", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="served_entries",
    )
    estimated_wait_minutes = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["business_date", "token_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "service", "business_date", "token_number"],
                name="uniq_token_per_org_service_day",
            ),
            models.CheckConstraint(
                check=~models.Q(status="COMPLETED") | models.Q(completed_at__isnull=False),
                name="completed_requires_completed_at",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "service", "business_date", "status"],
                name="idx_queue_active_lookup",
            ),
            models.Index(fields=["customer", "status"], name="idx_customer_queue"),
        ]

    def __str__(self):
        return f"#{self.token_number} {self.service_id} {self.business_date} {self.status}"
