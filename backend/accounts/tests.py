from django.test import TestCase

from accounts.models import User
from rest_framework.test import APIClient

from organizations.models import Organization, OrganizationMembership, Service


def make_org(name="Test Clinic", slug=None):
    return Organization.objects.create(name=name, slug=slug or name.lower().replace(" ", "-"))


def make_service(org, **kw):
    defaults = dict(name="Consultation", duration_minutes=20, buffer_minutes=0)
    defaults.update(kw)
    return Service.objects.create(organization=org, **defaults)


def register(client, email, password="Str0ngPass!x"):
    return client.post(
        "/api/auth/register/",
        {"email": email, "name": "Test User", "password": password, "password2": password},
        format="json",
    )


class RegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_and_login_flow(self):
        response = register(self.client, "alice@example.com")
        self.assertEqual(response.status_code, 201)
        self.assertIn("memberships", response.data)

        logout = self.client.post("/api/auth/logout/")
        self.assertEqual(logout.status_code, 204)

        login = self.client.post(
            "/api/auth/login/",
            {"email": "alice@example.com", "password": "Str0ngPass!x"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.data["email"], "alice@example.com")

    def test_duplicate_email_rejected(self):
        self.assertEqual(register(self.client, "bob@example.com").status_code, 201)
        self.client = APIClient()
        response = register(self.client, "BOB@example.com")
        self.assertEqual(response.status_code, 400)

    def test_weak_password_rejected(self):
        response = register(self.client, "carol@example.com", password="12345678")
        self.assertEqual(response.status_code, 400)

    def test_password_mismatch_rejected(self):
        response = self.client.post(
            "/api/auth/register/",
            {"email": "dave@example.com", "password": "Str0ngPass!x", "password2": "Other1!x"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_login_with_wrong_password(self):
        register(self.client, "erin@example.com")
        self.client = APIClient()
        response = self.client.post(
            "/api/auth/login/", {"email": "erin@example.com", "password": "nope-nope"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_protected_endpoint_requires_auth(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 403)


class AccessControlTests(TestCase):
    """Cross-role authorization boundaries."""

    def setUp(self):
        self.client = APIClient()

    def test_customer_cannot_use_staff_endpoints(self):
        register(self.client, "cust@example.com")
        response = self.client.get("/api/staff/queue/today/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/api/my/organization/")
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/api/my/audit-logs/")
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_read_other_org_data(self):
        register(self.client, "staff@example.com")
        staff = User.objects.get(email="staff@example.com")
        other_org = make_org("Other Org")
        OrganizationMembership.objects.create(
            organization=other_org, user=staff, role=OrganizationMembership.Roles.STAFF
        )

        response = self.client.get("/api/staff/queue/today/")
        self.assertEqual(response.status_code, 200)
        # Scoped to their org only — an unrelated org id returns 403.
        foreign_org = make_org("Foreign Org")
        response = self.client.get("/api/staff/queue/today/", {"org": foreign_org.id})
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_cancel_others_entry(self):
        register(self.client, "owner@example.com")
        owner = User.objects.get(email="owner@example.com")
        org = make_org()
        service = make_service(org, is_walkin_enabled=True)
        from queues.models import QueueEntry
        from django.utils import timezone

        entry = QueueEntry.objects.create(
            organization=org,
            service=service,
            customer=owner,
            source=QueueEntry.Source.WALKIN,
            token_number=1,
            business_date=timezone.localdate(),
        )
        self.client.post("/api/auth/logout/")
        register(self.client, "attacker@example.com")
        response = self.client.post(f"/api/queue/entries/{entry.id}/cancel/")
        self.assertEqual(response.status_code, 404)

    def test_customer_cannot_view_others_appointment(self):
        register(self.client, "realowner@example.com")
        owner = User.objects.get(email="realowner@example.com")
        org = make_org()
        service = make_service(org)
        from appointments.models import Appointment
        from django.utils import timezone

        appt = Appointment.objects.create(
            organization=org,
            service=service,
            customer=owner,
            slot_start=timezone.now() + timezone.timedelta(days=1),
            slot_end=timezone.now() + timezone.timedelta(days=1, minutes=20),
        )
        self.client.post("/api/auth/logout/")
        register(self.client, "stranger@example.com")
        response = self.client.get(f"/api/appointments/{appt.id}/")
        self.assertEqual(response.status_code, 404)
