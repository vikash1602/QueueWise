from django.conf import settings
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=300, blank=True)
    timezone = models.CharField(max_length=63, default="UTC")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "organization"
        verbose_name_plural = "organizations"

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    """Links a platform user to an organization with a role. All staff-level
    authorization flows through this table."""

    class Roles(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        STAFF = "STAFF", "Staff"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=10, choices=Roles.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="uniq_membership_per_org"
            )
        ]
        indexes = [models.Index(fields=["user", "is_active"])]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"


class Service(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="services"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(
        help_text="Configured nominal duration used for slotting and estimation fallback."
    )
    buffer_minutes = models.PositiveIntegerField(
        default=0, help_text="Cleanup/changeover buffer appended after each slot."
    )
    # Rolling estimate of actual duration, updated when services complete.
    # Falls back to duration_minutes when there is no history.
    avg_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_appointment_enabled = models.BooleanField(default=True)
    is_walkin_enabled = models.BooleanField(default=True)
    max_advance_days = models.PositiveIntegerField(default=14)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization", "name"]
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self):
        return f"{self.organization} / {self.name}"


class BusinessHours(models.Model):
    """Weekly opening hours per organization, in the organization's timezone.
    weekday follows Python convention: 0=Monday .. 6=Sunday."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="business_hours"
    )
    weekday = models.PositiveSmallIntegerField()
    opens_at = models.TimeField()
    closes_at = models.TimeField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "weekday"], name="uniq_hours_per_weekday"
            )
        ]
        ordering = ["organization", "weekday"]

    def __str__(self):
        return f"{self.organization} day {self.weekday}: {self.opens_at}-{self.closes_at}"


class ServiceCounter(models.Model):
    """A physical desk/counter serving a service; multiple counters reduce
    effective waiting time in the estimation algorithm."""

    service = models.ForeignKey(
        Service, on_delete=models.CASCADE, related_name="counters"
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["service", "name"]

    def __str__(self):
        return f"{self.service} counter {self.name}"
