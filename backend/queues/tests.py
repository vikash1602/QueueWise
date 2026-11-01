from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import Appointment
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
            for d in range(7)
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
            for d in range(7)
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


class CheckInTestBase(TestCase):
    """Shared fixtures for appointment check-in tests."""

    def setUp(self):
        self.org = Organization.objects.create(name="CheckOrg", slug="checkorg")
        BusinessHours.objects.bulk_create(
            BusinessHours(
                organization=self.org, weekday=d,
                opens_at=datetime.strptime("09:00", "%H:%M").time(),
                closes_at=datetime.strptime("17:00", "%H:%M").time(),
            )
            for d in range(7)
        )
        self.service = Service.objects.create(
            organization=self.org, name="Follow-up", duration_minutes=10,
        )
        self.staff = User.objects.create_user(email="ci@staff.io", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.staff, role=OrganizationMembership.Roles.STAFF
        )
        self.customer = User.objects.create_user(email="ci@cust.io", password="Str0ngPass!x")
        self.other_org = Organization.objects.create(name="OtherCheck", slug="othercheck")
        self.other_staff = User.objects.create_user(email="ci2@staff.io", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=self.other_org, user=self.other_staff, role=OrganizationMembership.Roles.STAFF
        )

    def make_appointment(self, *, status=Appointment.Status.CONFIRMED, customer=None, service=None):
        from appointments.models import Appointment

        slot = timezone.localtime().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        if slot.weekday() >= 5 or slot.hour < 9 or slot.hour >= 17:
            slot = slot.replace(hour=10) + timedelta(days=1)
            if slot.weekday() >= 5:
                slot += timedelta(days=2)
        return Appointment.objects.create(
            organization=self.org,
            service=service or self.service,
            customer=customer or self.customer,
            slot_start=slot,
            slot_end=slot + timedelta(minutes=(service or self.service).duration_minutes),
            status=status,
        )


class StaffCheckInListTests(CheckInTestBase):
    def test_staff_sees_own_org_confirmed_appointments(self):
        from organizations.services import local_business_date
        from organizations.models import BusinessHours

        appt = self.make_appointment()
        # Query the appointment's own org-local slot date (fixtures push
        # weekend-created appointments to the next weekday).
        from zoneinfo import ZoneInfo

        appt_date = timezone.localtime(appt.slot_start, ZoneInfo(self.org.timezone)).date()
        self.assertTrue(
            BusinessHours.objects.filter(organization=self.org, weekday=appt_date.weekday(), is_closed=False).exists()
        )
        client = APIClient()
        client.force_authenticate(user=self.staff)
        response = client.get("/api/staff/queue/check-ins/", {"date": appt_date.isoformat()})
        self.assertEqual(response.status_code, 200)
        ids = [r["id"] for r in response.data["results"]]
        self.assertIn(appt.id, ids)
        row = response.data["results"][0]
        self.assertEqual(row["customer_email"], "ci@cust.io")
        self.assertEqual(row["service_name"], "Follow-up")
        # The listed slot date matches the org's operating day.
        self.assertEqual(response.data["business_date"], appt_date.isoformat())
        _ = local_business_date  # referenced to document the org-local contract

    def test_cancelled_appointments_excluded(self):
        self.make_appointment(status=Appointment.Status.CANCELLED)
        client = APIClient()
        client.force_authenticate(user=self.staff)
        response = client.get("/api/staff/queue/check-ins/")
        self.assertEqual(response.data["results"], [])

    def test_other_org_staff_sees_nothing(self):
        self.make_appointment()
        client = APIClient()
        client.force_authenticate(user=self.other_staff)
        response = client.get("/api/staff/queue/check-ins/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_customer_cannot_list_checkins(self):
        self.make_appointment()
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.get("/api/staff/queue/check-ins/")
        self.assertEqual(response.status_code, 403)


class CheckInWorkflowTests(CheckInTestBase):
    def test_checkin_creates_linked_waiting_entry(self):
        appt = self.make_appointment()
        entry = workflow.check_in_appointment(appt, actor=self.staff)
        self.assertEqual(entry.status, QueueEntry.Status.WAITING)
        self.assertEqual(entry.appointment_id, appt.id)
        self.assertEqual(entry.customer_id, appt.customer_id)
        self.assertEqual(entry.organization_id, self.org.id)
        self.assertEqual(entry.source, QueueEntry.Source.APPOINTMENT)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.CHECKED_IN)
        self.assertTrue(entry.token_number >= 1)

    def test_repeat_checkin_is_idempotent(self):
        appt = self.make_appointment()
        first = workflow.check_in_appointment(appt, actor=self.staff)
        second = workflow.check_in_appointment(appt, actor=self.staff)
        self.assertEqual(first.id, second.id)
        self.assertEqual(QueueEntry.objects.filter(appointment_id=appt.id).count(), 1)

    def test_ineligible_status_rejected(self):
        appt = self.make_appointment(status=Appointment.Status.CANCELLED)
        with self.assertRaises(QueueWiseError):
            workflow.check_in_appointment(appt, actor=self.staff)
        self.assertEqual(QueueEntry.objects.count(), 0)

    def test_appointment_only_service_can_be_checked_in(self):
        # Regression: a service with walk-ins disabled must still accept
        # appointment check-ins.
        appt_only = Service.objects.create(
            organization=self.org, name="Appointment-only", duration_minutes=15,
            is_walkin_enabled=False, is_appointment_enabled=True,
        )
        appt = self.make_appointment(service=appt_only)
        entry = workflow.check_in_appointment(appt, actor=self.staff)
        self.assertEqual(entry.status, QueueEntry.Status.WAITING)

    def test_customer_serializer_exposes_token_after_checkin(self):
        from django.test import Client as DjClient

        appt = self.make_appointment()
        entry = workflow.check_in_appointment(appt, actor=self.staff)
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.get(f"/api/appointments/{appt.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["queue_token"], entry.token_number)

    def test_other_customer_cannot_access_entry(self):
        appt = self.make_appointment()
        entry = workflow.check_in_appointment(appt, actor=self.staff)
        stranger = User.objects.create_user(email="stranger@ci.io", password="Str0ngPass!x")
        client = APIClient()
        client.force_authenticate(user=stranger)
        response = client.get(f"/api/queue/entries/{entry.id}/")
        self.assertEqual(response.status_code, 404)


class ConcurrentCheckInTests(TransactionTestCase):
    """Standalone TransactionTestCase: it cannot share the TestCase-based
    CheckInTestBase (the MRO would re-introduce the wrapping transaction),
    so it builds its own committed fixtures that worker threads can see."""

    def setUp(self):
        self.org = Organization.objects.create(name="CIOrg", slug="ciorg")
        BusinessHours.objects.bulk_create(
            BusinessHours(
                organization=self.org, weekday=d,
                opens_at=datetime.strptime("09:00", "%H:%M").time(),
                closes_at=datetime.strptime("17:00", "%H:%M").time(),
            )
            for d in range(7)
        )
        self.service = Service.objects.create(
            organization=self.org, name="Follow-up", duration_minutes=10,
        )
        self.staff = User.objects.create_user(email="cc@staff.io", password="Str0ngPass!x")
        OrganizationMembership.objects.create(
            organization=self.org, user=self.staff, role=OrganizationMembership.Roles.STAFF
        )
        self.customer = User.objects.create_user(email="cc@cust.io", password="Str0ngPass!x")
        slot = timezone.localtime().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        if slot.weekday() >= 5 or slot.hour < 9 or slot.hour >= 17:
            slot = slot.replace(hour=10) + timedelta(days=1)
            if slot.weekday() >= 5:
                slot += timedelta(days=2)
        self.appt = Appointment.objects.create(
            organization=self.org,
            service=self.service,
            customer=self.customer,
            slot_start=slot,
            slot_end=slot + timedelta(minutes=10),
            status=Appointment.Status.CONFIRMED,
        )

    def test_concurrent_checkin_single_entry(self):
        import threading

        results = []

        def attempt():
            try:
                entry = workflow.check_in_appointment(self.appt, actor=self.staff)
                results.append(("ok", entry.id))
            except Exception as exc:
                results.append(("error", str(exc)))
            finally:
                from django.db import connections

                connections.close_all()

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Exactly one queue entry exists, and both concurrent requests
        # converge on it (the second is served the existing entry instead of
        # creating a duplicate).
        self.assertEqual(QueueEntry.objects.filter(appointment_id=self.appt.id).count(), 1)
        ok_ids = [r[1] for r in results if r[0] == "ok"]
        self.assertEqual(len(ok_ids), 2, results)
        self.assertEqual(len(set(ok_ids)), 1, results)

