from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from organizations.models import BusinessHours, Organization, OrganizationMembership, Service
from queues.exceptions import OutsideBusinessHours, SlotUnavailable

from .models import Appointment
from .services import book, cancel

User = get_user_model()

# A Wednesday, safely in the future relative to any test run.
FUTURE_WEDNESDAY = timezone.now().astimezone(
    timezone.get_fixed_timezone(0)
).date() + timedelta(days=(2 - timezone.now().weekday()) % 7 or 7 + 7)


def _future_date(weekday=2, min_days_ahead=7):
    """Next local UTC date falling on `weekday` (0=Mon) at least min_days ahead."""
    today = timezone.now().date()
    offset = (weekday - today.weekday()) % 7
    if offset < min_days_ahead:
        offset += 7
    return today + timedelta(days=offset)


class BookingTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Clinic", slug="clinic")
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
            organization=self.org, name="Consult", duration_minutes=30
        )
        self.customer = User.objects.create_user(email="cust@test.io", password="Str0ngPass!x")
        self.client = APIClient()
        self.client.force_authenticate(user=self.customer)

    def _slot(self, hour=10, minute=0):
        day = _future_date(weekday=2)  # Wednesday
        tz = timezone.get_fixed_timezone(0)
        return timezone.make_aware(datetime.combine(day, datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").time()), tz)

    def test_successful_booking(self):
        slot = self._slot()
        response = self.client.post(
            "/api/appointments/", {"service": self.service.id, "slot_start": slot}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "CONFIRMED")

    def test_double_booking_rejected(self):
        slot = self._slot()
        first = book(customer=self.customer, service=self.service, slot_start=slot)
        other = User.objects.create_user(email="b@test.io", password="Str0ngPass!x")
        with self.assertRaises(SlotUnavailable):
            book(customer=other, service=self.service, slot_start=slot)
        self.assertEqual(
            Appointment.objects.filter(service=self.service).count(), 1
        )

    def test_past_slot_rejected(self):
        past = timezone.now() - timedelta(hours=1)
        with self.assertRaises(SlotUnavailable):
            book(customer=self.customer, service=self.service, slot_start=past)

    def test_closed_day_rejected(self):
        saturday = _future_date(weekday=5)
        tz = timezone.get_fixed_timezone(0)
        slot = timezone.make_aware(datetime.combine(saturday, datetime.strptime("10:00", "%H:%M").time()), tz)
        with self.assertRaises(OutsideBusinessHours):
            book(customer=self.customer, service=self.service, slot_start=slot)

    def test_outside_hours_rejected(self):
        day = _future_date(weekday=2)
        tz = timezone.get_fixed_timezone(0)
        slot = timezone.make_aware(datetime.combine(day, datetime.strptime("18:00", "%H:%M").time()), tz)
        with self.assertRaises(OutsideBusinessHours):
            book(customer=self.customer, service=self.service, slot_start=slot)

    def test_cancellation_by_customer(self):
        slot = self._slot()
        appt = book(customer=self.customer, service=self.service, slot_start=slot)
        response = self.client.post(f"/api/appointments/{appt.id}/cancel/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "CANCELLED")
        appt.refresh_from_db()
        self.assertEqual(appt.cancelled_by, self.customer)

    def test_cancelled_slot_can_be_rebooked(self):
        slot = self._slot()
        appt = book(customer=self.customer, service=self.service, slot_start=slot)
        cancel(appt, cancelled_by=self.customer)
        other = User.objects.create_user(email="c@test.io", password="Str0ngPass!x")
        rebooked = book(customer=other, service=self.service, slot_start=slot)
        self.assertEqual(rebooked.status, Appointment.Status.CONFIRMED)

    def test_availability_endpoint_marks_taken_slots(self):
        slot = self._slot()
        book(customer=self.customer, service=self.service, slot_start=slot)
        response = self.client.get(
            f"/api/organizations/{self.org.id}/availability/",
            {"service": self.service.id, "date": slot.date().isoformat()},
        )
        slots = response.data["slots"]
        self.assertTrue(slots)
        flags = [s["is_available"] for s in slots]
        self.assertIn(False, flags)  # the booked slot is marked taken
        self.assertEqual(flags.count(False), 1)


class ConcurrentBookingTests(TransactionTestCase):
    """Two simultaneous booking attempts on one slot: exactly one wins."""

    def setUp(self):
        self.org = Organization.objects.create(name="Clinic2", slug="clinic2")
        BusinessHours.objects.bulk_create(
            BusinessHours(
                organization=self.org,
                weekday=d,
                opens_at=datetime.strptime("09:00", "%H:%M").time(),
                closes_at=datetime.strptime("17:00", "%H:%M").time(),
            )
            for d in range(5)
        )
        self.service = Service.objects.create(
            organization=self.org, name="Consult", duration_minutes=30
        )
        self.users = [
            User.objects.create_user(email=f"cc{i}@test.io", password="Str0ngPass!x")
            for i in range(2)
        ]
        today = timezone.now().date()
        offset = (2 - today.weekday()) % 7
        if offset < 7:
            offset += 7
        day = today + timedelta(days=offset)
        tz = timezone.get_fixed_timezone(0)
        self.slot = timezone.make_aware(
            datetime.combine(day, datetime.strptime("10:00", "%H:%M").time()), tz
        )

    def test_concurrent_booking_single_winner(self):
        import threading

        results = []

        def attempt(user):
            try:
                appt = book(customer=user, service=self.service, slot_start=self.slot)
                results.append(("ok", appt.id))
            except SlotUnavailable as exc:
                results.append(("rejected", str(exc)))
            except Exception as exc:  # unexpected
                results.append(("error", str(exc)))
            finally:
                from django.db import connections

                connections.close_all()

        threads = [threading.Thread(target=attempt, args=(u,)) for u in self.users]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        outcomes = [r[0] for r in results]
        self.assertEqual(outcomes.count("ok"), 1, results)
        self.assertEqual(outcomes.count("rejected"), 1, results)
        self.assertEqual(
            Appointment.objects.filter(
                service=self.service, status=Appointment.Status.CONFIRMED
            ).count(),
            1,
        )
