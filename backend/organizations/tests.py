from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import BusinessHours, Organization, OrganizationMembership, ServiceCounter

User = get_user_model()

DEFAULT_HOURS = [
    {"weekday": d, "opens_at": "09:00", "closes_at": "17:00", "is_closed": d >= 5}
    for d in range(7)
]


def seed_org_admin(email="admin@clinic.test", org_name="Alpha Clinic"):
    org = Organization.objects.create(name=org_name, slug=org_name.lower().replace(" ", "-"))
    user = User.objects.create_user(email=email, password="Str0ngPass!x", name="Admin")
    OrganizationMembership.objects.create(
        organization=org, user=user, role=OrganizationMembership.Roles.ADMIN
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return org, user, client


class OrganizationManagementTests(TestCase):
    def setUp(self):
        self.org, self.admin, self.client = seed_org_admin()

    def test_admin_views_own_organization(self):
        response = self.client.get("/api/my/organization/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], self.org.name)
        self.assertEqual(response.data["role"], "ADMIN")

    def test_admin_updates_organization(self):
        response = self.client.put(
            "/api/my/organization/", {"description": "Primary care"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.description, "Primary care")

    def test_admin_creates_service(self):
        response = self.client.post(
            "/api/my/services/",
            {"name": "Haircut", "duration_minutes": 30, "buffer_minutes": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            self.org.services.filter(name="Haircut").count(), 1
        )

    def test_staff_cannot_manage_services(self):
        staff_user = User.objects.create_user(email="staff@clinic.test", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=self.org, user=staff_user, role=OrganizationMembership.Roles.STAFF
        )
        client = APIClient()
        client.force_authenticate(user=staff_user)
        response = client.post(
            "/api/my/services/", {"name": "X", "duration_minutes": 10}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_business_hours_roundtrip(self):
        response = self.client.put(
            "/api/my/business-hours/", DEFAULT_HOURS, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BusinessHours.objects.filter(organization=self.org).count(), 7)
        # Sunday closed
        sunday = BusinessHours.objects.get(organization=self.org, weekday=6)
        self.assertTrue(sunday.is_closed)

    def test_business_hours_requires_all_days(self):
        response = self.client.put(
            "/api/my/business-hours/", DEFAULT_HOURS[:5], format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_add_staff_member_by_email(self):
        User.objects.create_user(email="newstaff@clinic.test", password="Str0ngPass!x")
        response = self.client.post(
            "/api/my/staff/", {"email": "newstaff@clinic.test", "role": "STAFF"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.org, user__email="newstaff@clinic.test"
            ).exists()
        )

    def test_add_unknown_staff_email_rejected(self):
        response = self.client.post(
            "/api/my/staff/", {"email": "ghost@nowhere.test", "role": "STAFF"}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class PublicDiscoveryTests(TestCase):
    def setUp(self):
        self.org, self.admin, _ = seed_org_admin()
        BusinessHours.objects.bulk_create(
            BusinessHours(organization=self.org, **h) for h in DEFAULT_HOURS
        )
        self.client = APIClient()

    def test_public_organization_list(self):
        response = self.client.get("/api/organizations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["name"], "Alpha Clinic")

    def test_public_organization_detail_includes_services(self):
        self.org.services.create(name="Consult", duration_minutes=20)
        response = self.client.get(f"/api/organizations/{self.org.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["services"]), 1)

    def test_public_availability_closed_day(self):
        service = self.org.services.create(name="Consult", duration_minutes=60)
        # 2026-11-01 is a Sunday in this seed (closed)
        response = self.client.get(
            f"/api/organizations/{self.org.id}/availability/",
            {"service": service.id, "date": "2026-11-01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slots"], [])

    def test_inactive_org_hidden(self):
        self.org.is_active = False
        self.org.save()
        response = self.client.get(f"/api/organizations/{self.org.id}/")
        self.assertEqual(response.status_code, 404)
