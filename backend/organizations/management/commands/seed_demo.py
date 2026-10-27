"""Create clearly-labeled demo data for local evaluation.

All demo records are prefixed with "[DEMO]" in UI-visible names and demo
accounts use the demo.queuewise.local email domain, so they can never collide
with real users or be mistaken for production data. The command is idempotent
and never touches existing accounts' passwords or non-demo records.

Phone fields hold clearly synthetic values ("+91-DEMO-xxxx") — the application
has no SMS/WhatsApp/OTP integrations, so no message can ever be sent to them.

Usage:  python manage.py seed_demo
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

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
NEW_ORG_NAME = "[DEMO] Kaveri Multispeciality Clinic"
LEGACY_ORG_NAME = "[DEMO] City Care Clinic"

# Fictional sample identities (see docs/README — not real people).
DEMO_CUSTOMERS = [
    ("Ananya Krishnamurthy", "ananya.krishnamurthy"),
    ("Arjun Narayanan", "arjun.narayanan"),
    ("Meera Subramanian", "meera.subramanian"),
    ("Karthik Raman", "karthik.raman"),
    ("Priya Balasubramaniam", "priya.balasubramaniam"),
    ("Nithya Srinivasan", "nithya.srinivasan"),
    ("Sanjay Raghavan", "sanjay.raghavan"),
    ("Divya Venkatesan", "divya.venkatesan"),
    ("Rahul Chandrasekar", "rahul.chandrasekar"),
    ("Keerthana Mahendran", "keerthana.mahendran"),
    ("Naveen Rajendran", "naveen.rajendran"),
    ("Swetha Narayanan", "swetha.narayanan"),
]

NEW_SERVICES = [
    # name, duration, buffer, description
    ("Follow-up Consultation", 10, 2, "Review visits for ongoing treatment plans."),
    ("Diagnostic Consultation", 25, 5, "Discussion of lab and imaging results."),
    ("Preventive Health Check", 35, 10, "Annual wellness screening and counselling."),
]


def _backdate_completed(entry, joined, called, started, completed):
    """Turn a freshly created entry into a backdated completed record.

    auto_now_add ignores create-time values, and the DB check constraint
    requires completed_at on completed rows, so create as WAITING and update.
    """
    QueueEntry.objects.filter(pk=entry.pk).update(
        status=QueueEntry.Status.COMPLETED,
        joined_at=joined,
        called_at=called,
        started_at=started,
        completed_at=completed,
    )
    entry.refresh_from_db()
    return entry


class Command(BaseCommand):
    help = "Seed labeled demo organization, services, accounts, and sample history."

    def handle(self, *args, **options):
        from audit.models import AuditLog

        org = Organization.objects.filter(name__in=[NEW_ORG_NAME, LEGACY_ORG_NAME]).first()
        if org and AuditLog.objects.filter(
            organization=org, action="DEMO_SEEDED", detail__version=2
        ).exists():
            self.stdout.write(self.style.WARNING("Demo data already exists — nothing seeded."))
            return

        if org is None:
            org = self._create_org()
        elif org.name == LEGACY_ORG_NAME:
            self._upgrade_legacy_org(org)

        self._create_services(org)
        admin, staff = self._ensure_demo_accounts(org)
        self._create_customers(org)
        self._create_queue_activity(org, staff)
        self._create_appointments(org)

        demo_customer = User.objects.get(email=f"customer@{DEMO_DOMAIN}")
        if not Notification.objects.filter(
            user=demo_customer, type=Notification.Types.BOOKING_CONFIRMED
        ).exists():
            Notification.objects.create(
                user=demo_customer,
                type=Notification.Types.BOOKING_CONFIRMED,
                title="Appointment confirmed",
                body="Your upcoming appointment at [DEMO] Kaveri Multispeciality Clinic is confirmed.",
            )
        audit_record(
            organization=org,
            action="DEMO_SEEDED",
            object_type="organization",
            object_id=org.id,
            detail={"version": 2},
        )

        self.stdout.write(self.style.SUCCESS("Demo data ready. All names are prefixed [DEMO]."))
        self.stdout.write(f"  Admin:    admin@{DEMO_DOMAIN} / {PASSWORD}")
        self.stdout.write(f"  Staff:    staff@{DEMO_DOMAIN} / {PASSWORD}")
        self.stdout.write(f"  Customer: customer@{DEMO_DOMAIN} / {PASSWORD}")
        self.stdout.write(f"  Demo customers: 12 fictional accounts @ {DEMO_DOMAIN}")

    # -- pieces ------------------------------------------------------------

    def _create_org(self):
        org = Organization.objects.create(
            name=NEW_ORG_NAME,
            slug="demo-kaveri-multispeciality-clinic",
            description=(
                "Demo organization seeded by `manage.py seed_demo` — a fictional "
                "multispeciality clinic in Coimbatore for evaluation only."
            ),
            contact_email=f"contact@{DEMO_DOMAIN}",
            contact_phone="+91-DEMO-41100",
            address="42, Avinashi Road, Peelamedu, Coimbatore, Tamil Nadu 641004",
            timezone="Asia/Kolkata",
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
        return org

    def _upgrade_legacy_org(self, org):
        """Rename the v1 demo org in place (record preserved, no deletion)."""
        org.name = NEW_ORG_NAME
        org.slug = "demo-kaveri-multispeciality-clinic"
        org.description = (
            "Demo organization seeded by `manage.py seed_demo` — a fictional "
            "multispeciality clinic in Coimbatore for evaluation only."
        )
        org.contact_email = f"contact@{DEMO_DOMAIN}"
        org.contact_phone = "+91-DEMO-41100"
        org.address = "42, Avinashi Road, Peelamedu, Coimbatore, Tamil Nadu 641004"
        org.timezone = "Asia/Kolkata"
        org.save()

    def _create_services(self, org):
        consultation = org.services.filter(name__iexact="general consultation").first()
        if consultation is None:
            consultation, _ = Service.objects.get_or_create(
                organization=org,
                name="General Consultation",
                defaults={
                    "description": "Routine doctor consultation.",
                    "duration_minutes": 20,
                    "buffer_minutes": 5,
                },
            )
        consultation.name = "General Consultation"
        consultation.description = "Routine doctor consultation."
        consultation.duration_minutes = 20
        consultation.buffer_minutes = 5
        consultation.save()

        for name, duration, buffer_, description in NEW_SERVICES:
            Service.objects.get_or_create(
                organization=org,
                name=name,
                defaults={
                    "description": description,
                    "duration_minutes": duration,
                    "buffer_minutes": buffer_,
                },
            )

        # Keep the pre-existing Vaccination service and its records.
        vaccination = org.services.filter(name="Vaccination").first()
        if vaccination is None:
            vaccination = Service.objects.create(
                organization=org,
                name="Vaccination",
                description="Standard immunizations.",
                duration_minutes=10,
                buffer_minutes=2,
            )

        # Counters for the estimation algorithm.
        if not consultation.counters.exists():
            ServiceCounter.objects.create(service=consultation, name="Counter 1")
            ServiceCounter.objects.create(service=consultation, name="Counter 2")
        return consultation

    def _ensure_demo_accounts(self, org):
        admin = User.objects.filter(email=f"admin@{DEMO_DOMAIN}").first()
        if admin:
            admin.name = "Priya Raghunathan"
            admin.phone = "+91-DEMO-41101"
            admin.save(update_fields=["name", "phone"])
        else:
            admin = User.objects.create_user(
                email=f"admin@{DEMO_DOMAIN}", password=PASSWORD, name="Priya Raghunathan",
                phone="+91-DEMO-41101",
            )
            OrganizationMembership.objects.create(
                organization=org, user=admin, role=OrganizationMembership.Roles.ADMIN
            )

        staff = User.objects.filter(email=f"staff@{DEMO_DOMAIN}").first()
        if staff:
            staff.name = "Suresh Iyer"
            staff.phone = "+91-DEMO-41102"
            staff.save(update_fields=["name", "phone"])
        else:
            staff = User.objects.create_user(
                email=f"staff@{DEMO_DOMAIN}", password=PASSWORD, name="Suresh Iyer",
                phone="+91-DEMO-41102",
            )
            OrganizationMembership.objects.create(
                organization=org, user=staff, role=OrganizationMembership.Roles.STAFF
            )

        customer = User.objects.filter(email=f"customer@{DEMO_DOMAIN}").first()
        if customer:
            customer.name = "Meera Subramanian"
            customer.phone = "+91-DEMO-41103"
            customer.save(update_fields=["name", "phone"])
        else:
            customer = User.objects.create_user(
                email=f"customer@{DEMO_DOMAIN}", password=PASSWORD, name="Meera Subramanian",
                phone="+91-DEMO-41103",
            )
        return admin, staff

    def _create_customers(self, org):
        for i, (name, slug) in enumerate(DEMO_CUSTOMERS, start=1):
            user, created = User.objects.get_or_create(
                email=f"{slug}@{DEMO_DOMAIN}",
                defaults={
                    "name": name,
                    "phone": f"+91-DEMO-{1000 + i:05d}"[:20],
                },
            )
            if created and not user.name:
                user.name = name
                user.save(update_fields=["name"])
        self.stdout.write(f"  ensured {len(DEMO_CUSTOMERS)} demo customer accounts")

    def _create_queue_activity(self, org, staff):
        """Varied, natural-looking queue activity for one past day and today."""
        now = timezone.localtime()
        services = {s.name: s for s in org.services.filter(is_active=True)}
        general = services["General Consultation"]
        followup = services["Follow-up Consultation"]

        # Historical completed entries on the most recent day with no existing
        # entries for this service (preserves the token uniqueness scope).
        history_date = None
        for offset in range(1, 11):
            candidate = (now - timedelta(days=offset)).date()
            if not QueueEntry.objects.filter(
                organization=org, service=general, business_date=candidate
            ).exists():
                history_date = candidate
                break
        if history_date is None:
            history_date = (now - timedelta(days=1)).date()
        history_start = timezone.make_aware(
            datetime.combine(history_date, datetime.strptime("10:00", "%H:%M").time())
        )
        durations = [14, 22, 18, 31, 12, 25, 19, 16]
        for i, minutes in enumerate(durations):
            joined = history_start + timedelta(minutes=i * 23)
            started = joined + timedelta(minutes=6 + (i % 4))
            completed = started + timedelta(minutes=minutes)
            entry = QueueEntry.objects.create(
                organization=org,
                service=general,
                customer=User.objects.filter(
                    email=DEMO_CUSTOMERS[i][1] + "@" + DEMO_DOMAIN
                ).first(),
                source=QueueEntry.Source.WALKIN,
                token_number=i + 1,
                business_date=history_date,
            )
            _backdate_completed(entry, joined, started, started, completed)

        # Live queue today: two completed, one no-show, one in progress,
        # one called, three waiting — created through the real workflow so
        # tokens and estimates are computed by the actual business rules.
        today_users = [
            User.objects.get(email=slug + "@" + DEMO_DOMAIN)
            for _, slug in DEMO_CUSTOMERS[6:]
        ] + [User.objects.get(email=f"customer@{DEMO_DOMAIN}")]
        entries = []
        for user in today_users:
            entry = workflow.join_queue(
                organization=org, service=general, customer=user
            )
            entries.append(entry)
        workflow.join_queue(
            organization=org, service=followup, customer=today_users[0]
        )

        # 1: completed (walked through quickly), 2: completed, 3: no-show.
        workflow.perform_staff_action(entry=entries[0], action="call", actor=staff)
        workflow.perform_staff_action(entry=entries[0], action="start", actor=staff)
        workflow.perform_staff_action(entry=entries[0], action="complete", actor=staff)
        workflow.perform_staff_action(entry=entries[1], action="call", actor=staff)
        workflow.perform_staff_action(entry=entries[1], action="start", actor=staff)
        workflow.perform_staff_action(entry=entries[1], action="complete", actor=staff)
        workflow.perform_staff_action(entry=entries[2], action="call", actor=staff)
        workflow.perform_staff_action(entry=entries[2], action="no-show", actor=staff)
        workflow.perform_staff_action(entry=entries[3], action="call", actor=staff)
        workflow.perform_staff_action(entry=entries[3], action="start", actor=staff)
        # entries[4..6] remain WAITING.

    def _create_appointments(self, org):
        services = {s.name: s for s in org.services.filter(is_active=True)}
        diagnostic = services["Diagnostic Consultation"]
        preventive = services["Preventive Health Check"]
        meera = User.objects.get(email=f"customer@{DEMO_DOMAIN}")
        karthik = User.objects.get(email="karthik.raman@" + DEMO_DOMAIN)
        divya = User.objects.get(email="divya.venkatesan@" + DEMO_DOMAIN)

        # Explicit IST slots on the next weekdays, inside 09:00-17:00 hours.
        ist = ZoneInfo("Asia/Kolkata")
        today = timezone.now().astimezone(ist).date()
        slot_hours = (10, 11, 16)
        slots_ist = []
        day_offset = 0
        while len(slots_ist) < 3 and day_offset < 14:
            day_offset += 1
            day = today + timedelta(days=day_offset)
            if day.weekday() >= 5:
                continue
            slots_ist.append(
                datetime.combine(
                    day,
                    datetime.strptime(
                        f"{slot_hours[len(slots_ist)]:02d}:00", "%H:%M"
                    ).time(),
                    tzinfo=ist,
                )
            )

        for service, customer, slot in (
            (diagnostic, meera, slots_ist[0]),
            (preventive, karthik, slots_ist[1]),
            (diagnostic, divya, slots_ist[2]),
        ):
            Appointment.objects.get_or_create(
                organization=org,
                service=service,
                customer=customer,
                slot_start=slot.astimezone(dt_timezone.utc),
                defaults={
                    "slot_end": slot.astimezone(dt_timezone.utc)
                    + timedelta(minutes=service.duration_minutes),
                    "status": Appointment.Status.CONFIRMED,
                },
            )
