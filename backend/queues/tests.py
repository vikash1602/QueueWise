from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from organizations.models import BusinessHours, Organization, OrganizationMembership, Service, ServiceCounter

from .exceptions import InvalidQueueTransition, QueueWiseError
from .models import QueueEntry
from .services import (
    estimate_wait_minutes,
    position_of,
    update_rolling_estimate,
)
from . import workflow

User = get_user_model()


class QueueTestBase(TestCase):
    """Shared fixtures: an org open Mon-Fri 09:00-17:00 with two services."""

    def setUp(self):
        self.org = Organization.objects.create(name="QueueOrg", slug="queueorg")
        BusinessHours.objects.bulk_create(
            BusinessHours(
                organization=self.org,
                weekday=d,
                opens_at=datetime.strptime("09:00", "%H:%M").time(),
                closes_at=datetime.strptime("17:00", "%H:%M").time(),
                is_closed=False,
            )
            for d in range(5)
        )
        self.service = Service.objects.create(
            organization=self.org, name="Consult", duration_minutes=15
        )
        self.customer = User.objects.create_user(email="qcust@test.io", password="Str0ngPass!x")
        self.staff = User.objects.create_user(email="qstaff@test.io", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.staff, role=OrganizationMembership.Roles.STAFF
        )
        self.admin = User.objects.create_user(email="qadmin@test.io", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin, role=OrganizationMembership.Roles.ADMIN
        )


class TokenGenerationTests(QueueTestBase):
    def test_tokens_increase_per_join(self):
        tokens = [
            workflow.join_queue(organization=self.org, service=self.service, customer=self.customer).token_number
            for _ in range(3)
        ]
        self.assertEqual(tokens, [1, 2, 3])

    def test_token_scope_is_per_service_per_day(self):
        other_service = Service.objects.create(
            organization=self.org, name="Vaccination", duration_minutes=10
        )
        e1 = workflow.join_queue(organization=self.org, service=self.service, customer=self.customer)
        e2 = workflow.join_queue(organization=self.org, service=other_service, customer=self.customer)
        self.assertEqual(e1.token_number, 1)
        self.assertEqual(e2.token_number, 1)

    def test_walkin_disabled_rejected(self):
        self.service.is_walkin_enabled = False
        self.service.save()
        with self.assertRaises(QueueWiseError):
            workflow.join_queue(organization=self.org, service=self.service, customer=self.customer)

    def test_guest_walkin_requires_name(self):
        with self.assertRaises(QueueWiseError):
            workflow.join_queue(organization=self.org, service=self.service, customer=None, guest_name="  ")


class StateTransitionTests(QueueTestBase):
    def _entry(self):
        return workflow.join_queue(
            organization=self.org, service=self.service, customer=self.customer
        )

    def test_full_happy_path(self):
        entry = self._entry()
        self.assertEqual(entry.status, QueueEntry.Status.WAITING)
        entry = workflow.perform_staff_action(entry=entry, action="call", actor=self.staff)
        self.assertEqual(entry.status, QueueEntry.Status.CALLED)
        entry = workflow.perform_staff_action(entry=entry, action="start", actor=self.staff)
        self.assertEqual(entry.status, QueueEntry.Status.IN_PROGRESS)
        entry = workflow.perform_staff_action(entry=entry, action="complete", actor=self.staff)
        self.assertEqual(entry.status, QueueEntry.Status.COMPLETED)
        self.assertIsNotNone(entry.completed_at)

    def test_complete_without_start_rejected(self):
        entry = self._entry()
        with self.assertRaises(InvalidQueueTransition):
            workflow.perform_staff_action(entry=entry, action="complete", actor=self.staff)

    def test_call_without_waiting_rejected(self):
        entry = self._entry()
        workflow.perform_staff_action(entry=entry, action="call", actor=self.staff)
        with self.assertRaises(InvalidQueueTransition):
            workflow.perform_staff_action(entry=entry, action="call", actor=self.staff)

    def test_no_show_from_called(self):
        entry = self._entry()
        workflow.perform_staff_action(entry=entry, action="call", actor=self.staff)
        entry = workflow.perform_staff_action(entry=entry, action="no-show", actor=self.staff)
        self.assertEqual(entry.status, QueueEntry.Status.NO_SHOW)

    def test_invalid_action_name(self):
        entry = self._entry()
        with self.assertRaises(QueueWiseError):
            workflow.perform_staff_action(entry=entry, action="teleport", actor=self.staff)

    def test_completed_entry_fed_back_into_rolling_estimate(self):
        first = self._entry()
        self._entry()  # will be at position 1 after `first` completes
        follower = self._entry()  # position 2 after completion
        workflow.perform_staff_action(entry=first, action="call", actor=self.staff)
        workflow.perform_staff_action(entry=first, action="start", actor=self.staff)
        # Simulate a 20-minute service.
        QueueEntry.objects.filter(pk=first.pk).update(
            started_at=timezone.now() - timedelta(minutes=20)
        )
        first = QueueEntry.objects.get(pk=first.pk)  # pick up the backdated start
        workflow.perform_staff_action(entry=first, action="complete", actor=self.staff)
        self.service.refresh_from_db()
        self.assertEqual(self.service.avg_duration_minutes, 20)
        # The entry at position 2 waits one learned duration.
        follower.refresh_from_db()
        self.assertEqual(follower.estimated_wait_minutes, 20)

    def test_customer_cancels_waiting_entry(self):
        entry = self._entry()
        entry = workflow.cancel_by_customer(entry, actor=self.customer)
        self.assertEqual(entry.status, QueueEntry.Status.CANCELLED)

    def test_customer_cannot_cancel_other_entry(self):
        entry = self._entry()
        stranger = User.objects.create_user(email="s@test.io", password="Str0ngPass!x")
        with self.assertRaises(PermissionError):
            workflow.cancel_by_customer(entry, actor=stranger)


class CallNextTests(QueueTestBase):
    def test_call_next_picks_lowest_token(self):
        e1 = workflow.join_queue(organization=self.org, service=self.service, customer=self.customer)
        e2 = workflow.join_queue(organization=self.org, service=self.service, guest_name="B")
        workflow.join_queue(organization=self.org, service=self.service, guest_name="C")
        called = workflow.call_next(organization=self.org, service=self.service, actor=self.staff)
        self.assertEqual(called.token_number, e1.token_number)

    def test_call_next_empty_queue(self):
        with self.assertRaises(QueueWiseError):
            workflow.call_next(organization=self.org, service=self.service, actor=self.staff)

    def test_skipped_entry_returns_to_waiting(self):
        e1 = workflow.join_queue(organization=self.org, service=self.service, customer=self.customer)
        e2 = workflow.join_queue(organization=self.org, service=self.service, guest_name="B")
        workflow.perform_staff_action(entry=e1, action="call", actor=self.staff)
        workflow.perform_staff_action(entry=e1, action="no-show", actor=self.staff)
        called = workflow.call_next(organization=self.org, service=self.service, actor=self.staff)
        self.assertEqual(called.id, e2.id)


class PositionTests(QueueTestBase):
    def test_position_counts_only_waiting_ahead(self):
        e1 = workflow.join_queue(organization=self.org, service=self.service, customer=self.customer)
        e2 = workflow.join_queue(organization=self.org, service=self.service, guest_name="B")
        e3 = workflow.join_queue(organization=self.org, service=self.service, guest_name="C")
        self.assertEqual(position_of(e1), 1)
        self.assertEqual(position_of(e2), 2)
        self.assertEqual(position_of(e3), 3)
        workflow.perform_staff_action(entry=e1, action="call", actor=self.staff)
        # e1 is CALLED (still occupies a counter), e2 is next waiting.
        self.assertEqual(position_of(e2), 2)
        self.assertEqual(position_of(e3), 3)
        workflow.perform_staff_action(entry=e1, action="start", actor=self.staff)
        workflow.perform_staff_action(entry=e1, action="complete", actor=self.staff)
        self.assertEqual(position_of(e2), 1)
        self.assertEqual(position_of(e3), 2)

    def test_done_entries_have_no_position(self):
        entry = workflow.join_queue(organization=self.org, service=self.service, customer=self.customer)
        workflow.cancel_by_customer(entry, actor=self.customer)
        self.assertEqual(position_of(entry), 0)


class EstimationTests(QueueTestBase):
    def test_empty_history_uses_configured_duration(self):
        self.assertEqual(estimate_wait_minutes(self.service, position=2), 15)

    def test_median_of_history_ignores_outliers(self):
        base = timezone.now() - timedelta(hours=6)
        for i, minutes in enumerate([10, 20, 10, 20, 600]):
            entry = QueueEntry.objects.create(
                organization=self.org,
                service=self.service,
                customer=self.customer,
                source=QueueEntry.Source.WALKIN,
                token_number=i + 1,
                business_date=timezone.localdate(),
                status=QueueEntry.Status.COMPLETED,
                joined_at=base,
                called_at=base,
                started_at=base,
                completed_at=base + timedelta(minutes=minutes),
            )
        update_rolling_estimate(self.service)
        self.service.refresh_from_db()
        # Median of [10, 10, 20, 20] (600 dropped as outlier) = 15.
        self.assertEqual(self.service.avg_duration_minutes, 15)

    def test_multiple_counters_halve_wait(self):
        ServiceCounter.objects.create(service=self.service, name="Counter 1")
        ServiceCounter.objects.create(service=self.service, name="Counter 2")
        # position 5 with 2 counters: ceil(4/2)=2 batches of 15 minutes.
        self.assertEqual(estimate_wait_minutes(self.service, position=5), 30)

    def test_zero_position_zero_wait(self):
        self.assertEqual(estimate_wait_minutes(self.service, position=0), 0)


class StaffApiTests(QueueTestBase):
    def test_staff_dashboard_lists_today(self):
        workflow.join_queue(organization=self.org, service=self.service, customer=self.customer)
        client = APIClient()
        client.force_authenticate(user=self.staff)
        response = client.get("/api/staff/queue/today/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_customer_cannot_call_staff_endpoints(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.post(
            "/api/staff/queue/call-next/", {"service": self.service.id}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_of_other_org_cannot_operate(self):
        other = Organization.objects.create(name="Other", slug="other")
        other_staff = User.objects.create_user(email="o@test.io", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=other, user=other_staff, role=OrganizationMembership.Roles.STAFF
        )
        client = APIClient()
        client.force_authenticate(user=other_staff)
        response = client.post(
            "/api/staff/queue/call-next/", {"service": self.service.id}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_walkin_registration_by_staff(self):
        client = APIClient()
        client.force_authenticate(user=self.staff)
        response = client.post(
            "/api/staff/queue/walk-in/",
            {"service": self.service.id, "guest_name": "Walkin Guest"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["source"], "WALKIN")

    def test_customer_join_and_status_polling(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.post("/api/queue/entries/", {"service": self.service.id}, format="json")
        self.assertEqual(response.status_code, 201)
        entry_id = response.data["id"]
        status_response = client.get(f"/api/queue/entries/{entry_id}/")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.data["position"], 1)
        self.assertEqual(status_response.data["people_ahead"], 0)
        # Staff of the org cannot see the customer's private endpoint; strangers get 404.
        stranger = User.objects.create_user(email="x@test.io", password="Str0ngPass!x")
        other_client = APIClient()
        other_client.force_authenticate(user=stranger)
        self.assertEqual(other_client.get(f"/api/queue/entries/{entry_id}/").status_code, 404)


class ConcurrentTokenTests(TransactionTestCase):
    """Concurrent walk-ins must receive unique, gapless tokens."""

    def setUp(self):
        self.org = Organization.objects.create(name="TokOrg", slug="tokorg")
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

    def test_concurrent_walkins_unique_tokens(self):
        import threading

        created = []

        def join(i):
            try:
                entry = workflow.join_queue(
                    organization=self.org,
                    service=self.service,
                    guest_name=f"Guest {i}",
                )
                created.append(entry.token_number)
            except Exception as exc:
                created.append(str(exc))
            finally:
                from django.db import connections

                connections.close_all()

        threads = [threading.Thread(target=join, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(created), 5, created)
        self.assertEqual(sorted(created), [1, 2, 3, 4, 5])
