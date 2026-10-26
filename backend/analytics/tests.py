from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from organizations.models import BusinessHours, Organization, OrganizationMembership, Service
from queues.models import QueueEntry

User = get_user_model()


class AnalyticsBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="AnOrg", slug="anorg")
        BusinessHours.objects.bulk_create(
            BusinessHours(
                organization=self.org, weekday=d,
                opens_at=datetime.strptime("09:00", "%H:%M").time(),
                closes_at=datetime.strptime("17:00", "%H:%M").time(),
            )
            for d in range(5)
        )
        self.service = Service.objects.create(
            organization=self.org, name="Consult", duration_minutes=15
        )
        self.admin = User.objects.create_user(email="an@admin.io", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.Roles.ADMIN
        )
        self.staff = User.objects.create_user(email="an@staff.io", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.staff, role=OrganizationMembership.Roles.STAFF
        )
        self.customer = User.objects.create_user(email="an@cust.io", password="Str0ngPass!x")

    def add_completed(self, token, wait_minutes, service_minutes, joined_hours_ago=2):
        now = timezone.now()
        joined = now - timedelta(hours=joined_hours_ago)
        called = joined + timedelta(minutes=wait_minutes)
        started = called
        completed = started + timedelta(minutes=service_minutes)
        entry = QueueEntry.objects.create(
            organization=self.org,
            service=self.service,
            customer=self.customer,
            source=QueueEntry.Source.WALKIN,
            token_number=token,
            business_date=timezone.localdate(),
            status=QueueEntry.Status.WAITING,
        )
        # Backdate the record into a completed state in one update so the
        # completed_requires_completed_at check holds.
        QueueEntry.objects.filter(pk=entry.pk).update(
            status=QueueEntry.Status.COMPLETED,
            joined_at=joined, called_at=called, started_at=started, completed_at=completed
        )
        entry.refresh_from_db()
        return entry


class AnalyticsTests(AnalyticsBase):
    def test_summary_metrics_from_real_records(self):
        self.add_completed(1, wait_minutes=10, service_minutes=15)
        self.add_completed(2, wait_minutes=20, service_minutes=25)
        QueueEntry.objects.create(
            organization=self.org, service=self.service, customer=self.customer,
            source=QueueEntry.Source.WALKIN, token_number=3,
            business_date=timezone.localdate(), status=QueueEntry.Status.NO_SHOW,
            joined_at=timezone.now() - timedelta(hours=1),
        )
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get("/api/my/analytics/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["customers_served"], 2)
        self.assertEqual(response.data["no_show_count"], 1)
        self.assertEqual(response.data["avg_wait_minutes"], 15.0)
        self.assertEqual(response.data["avg_service_minutes"], 20.0)

    def test_summary_admin_only(self):
        client = APIClient()
        client.force_authenticate(user=self.staff)
        response = client.get("/api/my/analytics/summary/")
        self.assertEqual(response.status_code, 403)

    def test_summary_requires_membership(self):
        outsider = User.objects.create_user(email="an@out.io", password="Str0ngPass!x")
        client = APIClient()
        client.force_authenticate(user=outsider)
        response = client.get("/api/my/analytics/summary/")
        self.assertEqual(response.status_code, 403)

    def test_trends_cover_range(self):
        self.add_completed(1, wait_minutes=5, service_minutes=10)
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get("/api/my/analytics/trends/", {"days": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["trends"]), 4)  # inclusive of both ends
        self.assertEqual(sum(d["customers_served"] for d in response.data["trends"]), 1)


class AuditLogTests(AnalyticsBase):
    def test_queue_actions_recorded(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.post("/api/queue/entries/", {"service": self.service.id}, format="json")
        self.assertEqual(response.status_code, 201)
        client.force_authenticate(user=self.admin)
        logs = client.get("/api/my/audit-logs/").data["results"]
        self.assertTrue(any(log["action"] == "QUEUE_JOINED" for log in logs))

    def test_audit_admin_only(self):
        client = APIClient()
        client.force_authenticate(user=self.staff)
        response = client.get("/api/my/audit-logs/")
        self.assertEqual(response.status_code, 403)

    def test_isolated_per_organization(self):
        # Another org's admin must not see this org's logs.
        other = Organization.objects.create(name="OtherAn", slug="otheran")
        other_admin = User.objects.create_user(email="an@other.io", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=other, user=other_admin, role=OrganizationMembership.Roles.ADMIN
        )
        client = APIClient()
        client.force_authenticate(user=other_admin)
        response = client.get("/api/my/audit-logs/", {"org": self.org.id})
        self.assertEqual(response.status_code, 403)
