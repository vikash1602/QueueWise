"""Create clearly-labeled demo data for local evaluation.

Everything created by this command is prefixed with "[DEMO]" in the UI-visible
name fields, and demo accounts use the demo.queuewise.local email domain so
they can never collide with real users.

Usage:  python manage.py seed_demo
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment
from audit.services import record as audit_record
from notifications.models import Notification
from organizations.models import (
    BusinessHours,
    Organization,
    OrganizationMembership,
    Service,
    ServiceCounter,
)
from queues.models import QueueEntry
from queues import workflow

DEMO_DOMAIN = "demo.queuewise.local"
PASSWORD = "Demo!Pass123"


class Command(BaseCommand):
    help = "Seed labeled demo organization, services, accounts, and sample history."

    def handle(self, *args, **options):
        if Organization.objects.filter(slug__startswith="demo-").exists():
            self.stdout.write(self.style.WARNING("Demo data already exists — nothing seeded."))
            return

        org = Organization.objects.create(
            name="[DEMO] City Care Clinic",
            slug="demo-city-care-clinic",
            description="Demo organization seeded by `manage.py seed_demo` for evaluation.",
            contact_email=f"contact@{DEMO_DOMAIN}",
            contact_phone="+1-555-0100",
            address="1 Demo Street, Springfield",
            timezone="UTC",
        )
        BusinessHours.objects.bulk_create(
            BusinessHours(
                organization=org,
                weekday=d,
                opens_at=datetime.strptime("09:00", "%H:%M").time(),
                closes_at=datetime.strptime("17:00", "%H:%M").time(),
                is_closed=d >= 5,
            )
            for d in range(7)
        )

        demo_admin = User.objects.create_user(
            email=f"admin@{DEMO_DOMAIN}", password=PASSWORD, name="Demo Admin"
        )
        demo_staff = User.objects.create_user(
            email=f"staff@{DEMO_DOMAIN}", password=PASSWORD, name="Demo Staff"
        )
        demo_customer = User.objects.create_user(
            email=f"customer@{DEMO_DOMAIN}", password=PASSWORD, name="Demo Customer"
        )
        OrganizationMembership.objects.create(
            organization=org, user=demo_admin, role=OrganizationMembership.Roles.ADMIN
        )
        OrganizationMembership.objects.create(
            organization=org, user=demo_staff, role=OrganizationMembership.Roles.STAFF
        )

        consultation = Service.objects.create(
            organization=org,
            name="General consultation",
            description="Routine doctor consultation.",
            duration_minutes=20,
            buffer_minutes=5,
        )
        ServiceCounter.objects.create(service=consultation, name="Counter A")
        ServiceCounter.objects.create(service=consultation, name="Counter B")
        vaccination = Service.objects.create(
            organization=org,
            name="Vaccination",
            description="Standard immunizations.",
            duration_minutes=10,
            buffer_minutes=2,
        )

        # Sample completed history so analytics and estimates have data.
        now = timezone.now()
        for i in range(6):
            joined = now - timedelta(days=1, hours=5 - i * 0.5)
            started = joined + timedelta(minutes=10 + i)
            completed = started + timedelta(minutes=15 + i * 3)
            entry = QueueEntry.objects.create(
                organization=org,
                service=consultation,
                customer=demo_customer,
                source=QueueEntry.Source.WALKIN,
                token_number=i + 1,
                business_date=(now - timedelta(days=1)).date(),
                status=QueueEntry.Status.WAITING,
            )
            # auto_now_add overrides create-time values, so backdate in one update.
            QueueEntry.objects.filter(pk=entry.pk).update(
                status=QueueEntry.Status.COMPLETED,
                joined_at=joined,
                called_at=started,
                started_at=started,
                completed_at=completed,
            )

        # A live walk-in and a future appointment.
        live_entry = workflow.join_queue(
            organization=org, service=consultation, customer=demo_customer
        )
        slot = now.replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
        if slot.weekday() >= 5:
            slot += timedelta(days=2)
        Appointment.objects.create(
            organization=org,
            service=vaccination,
            customer=demo_customer,
            slot_start=slot,
            slot_end=slot + timedelta(minutes=vaccination.duration_minutes),
        )

        Notification.objects.create(
            user=demo_customer,
            type=Notification.Types.BOOKING_CONFIRMED,
            title="Appointment confirmed",
            body=f"Vaccination on {slot:%Y-%m-%d %H:%M} (UTC).",
            payload={},
        )
        audit_record(
            organization=org,
            action="DEMO_SEEDED",
            object_type="organization",
            object_id=org.id,
        )

        self.stdout.write(self.style.SUCCESS("Demo data created. All names are prefixed [DEMO]."))
        self.stdout.write(f"  Admin:    admin@{DEMO_DOMAIN} / {PASSWORD}")
        self.stdout.write(f"  Staff:    staff@{DEMO_DOMAIN} / {PASSWORD}")
        self.stdout.write(f"  Customer: customer@{DEMO_DOMAIN} / {PASSWORD}")
        self.stdout.write(f"  Live queue token #{live_entry.token_number} for the demo customer.")
