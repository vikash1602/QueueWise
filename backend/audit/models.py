from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Append-only record of important organization and queue actions.
    Never stores credentials or tokens."""

    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_logs",
    )
    action = models.CharField(max_length=60, db_index=True)
    object_type = models.CharField(max_length=60)
    object_id = models.CharField(max_length=60, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "-created_at"], name="idx_audit_org_recent")]

    def __str__(self):
        return f"{self.action} {self.object_type}#{self.object_id}"
