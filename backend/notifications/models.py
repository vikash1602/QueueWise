from django.conf import settings
from django.db import models


class Notification(models.Model):
    """In-app notification for one user."""

    class Types(models.TextChoices):
        BOOKING_CONFIRMED = "BOOKING_CONFIRMED", "Booking confirmed"
        BOOKING_CANCELLED = "BOOKING_CANCELLED", "Booking cancelled"
        QUEUE_CALLED = "QUEUE_CALLED", "You are being called"
        QUEUE_COMPLETED = "QUEUE_COMPLETED", "Service completed"
        QUEUE_CANCELLED = "QUEUE_CANCELLED", "Queue entry cancelled"
        APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER", "Appointment reminder"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=30, choices=Types.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"], name="idx_notif_unread"),
            models.Index(fields=["user", "-created_at"], name="idx_notif_recent"),
        ]

    def __str__(self):
        return f"{self.type} for user {self.user_id}"
