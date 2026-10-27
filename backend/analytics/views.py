from datetime import datetime, timedelta

from django.db import models
from django.db.models import Avg, Count, F
from django.db.models.functions import TruncHour
from django.utils import timezone as dj_timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment
from organizations.models import OrganizationMembership
from queues.models import QueueEntry
from organizations.services import local_business_date


def _membership_or_none(request):
    org_id = request.query_params.get("org")
    qs = OrganizationMembership.objects.filter(user=request.user, is_active=True)
    membership = qs.filter(organization_id=org_id).first() if org_id else qs.order_by("id").first()
    return membership


def _parse_range(request):
    to = dj_timezone.now()
    try:
        from_days = int(request.query_params.get("days", "7"))
    except ValueError:
        from_days = 7
    from_dt = to - timedelta(days=max(1, min(from_days, 90)))
    return from_dt, to


class AnalyticsSummaryView(APIView):
    """Organization analytics computed from persisted records only."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = _membership_or_none(request)
        if membership is None:
            return Response({"detail": "No organization membership."}, status=403)
        if membership.role != OrganizationMembership.Roles.ADMIN:
            return Response({"detail": "Administrator role required."}, status=403)
        org = membership.organization
        from_dt, to_dt = _parse_range(request)

        service_id = request.query_params.get("service")
        appointment_qs = Appointment.objects.filter(
            organization=org, created_at__range=(from_dt, to_dt)
        )
        queue_qs = QueueEntry.objects.filter(
            organization=org, joined_at__range=(from_dt, to_dt)
        )
        if service_id:
            appointment_qs = appointment_qs.filter(service_id=service_id)
            queue_qs = queue_qs.filter(service_id=service_id)

        total_appointments = appointment_qs.count()
        cancelled_appointments = appointment_qs.filter(
            status=Appointment.Status.CANCELLED
        ).count()
        completed = queue_qs.filter(status=QueueEntry.Status.COMPLETED)
        completed_count = completed.count()
        no_show_count = queue_qs.filter(status=QueueEntry.Status.NO_SHOW).count()
        cancelled_queue = queue_qs.filter(status=QueueEntry.Status.CANCELLED).count()

        # Waiting time: joined_at -> called_at. Service duration: started -> completed.
        # Inverted intervals (backdated records, clock drift) are excluded so
        # averages stay meaningful.
        wait_avg = completed.filter(
            called_at__isnull=False, called_at__gte=F("joined_at")
        ).aggregate(v=Avg(F("called_at") - F("joined_at")))["v"]
        service_avg = completed.filter(
            completed_at__isnull=False, completed_at__gte=F("started_at")
        ).aggregate(v=Avg(F("completed_at") - F("started_at")))["v"]

        business_date = local_business_date(org)
        active_size = QueueEntry.objects.filter(
            organization=org,
            business_date=business_date,
            status__in=[QueueEntry.Status.WAITING, QueueEntry.Status.CALLED],
        ).count()

        def minutes(delta):
            return round(delta.total_seconds() / 60, 1) if delta else None

        return Response(
            {
                "range": {"from": from_dt.date().isoformat(), "to": to_dt.date().isoformat()},
                "total_appointments": total_appointments,
                "cancelled_appointments": cancelled_appointments,
                "cancellation_rate": round(cancelled_appointments / total_appointments, 3)
                if total_appointments
                else None,
                "customers_served": completed_count,
                "no_show_count": no_show_count,
                "no_show_rate": round(no_show_count / (completed_count + no_show_count), 3)
                if (completed_count + no_show_count)
                else None,
                "cancelled_queue_entries": cancelled_queue,
                "active_queue_size": active_size,
                "avg_wait_minutes": minutes(wait_avg),
                "avg_service_minutes": minutes(service_avg),
            }
        )


class AnalyticsTrendsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = _membership_or_none(request)
        if membership is None:
            return Response({"detail": "No organization membership."}, status=403)
        if membership.role != OrganizationMembership.Roles.ADMIN:
            return Response({"detail": "Administrator role required."}, status=403)
        org = membership.organization
        from_dt, to_dt = _parse_range(request)

        days = []
        cursor = from_dt.date()
        end = to_dt.date()
        while cursor <= end:
            day_start = dj_timezone.make_aware(datetime.combine(cursor, datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            joined = QueueEntry.objects.filter(
                organization=org, joined_at__range=(day_start, day_end)
            )
            served = joined.filter(status=QueueEntry.Status.COMPLETED).count()
            days.append(
                {
                    "date": cursor.isoformat(),
                    "queue_joined": joined.count(),
                    "customers_served": served,
                    "appointments": Appointment.objects.filter(
                        organization=org, created_at__range=(day_start, day_end)
                    ).count(),
                }
            )
            cursor += timedelta(days=1)
        return Response({"trends": days})


class AnalyticsPeakHoursView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = _membership_or_none(request)
        if membership is None:
            return Response({"detail": "No organization membership."}, status=403)
        if membership.role != OrganizationMembership.Roles.ADMIN:
            return Response({"detail": "Administrator role required."}, status=403)
        org = membership.organization
        from_dt, to_dt = _parse_range(request)
        hours = (
            QueueEntry.objects.filter(
                organization=org, joined_at__range=(from_dt, to_dt)
            )
            .annotate(hour=TruncHour("joined_at"))
            .values("hour")
            .annotate(joins=Count("id"))
            .order_by("hour")
        )
        return Response(
            {
                "peak_hours": [
                    {"hour": row["hour"], "joins": row["joins"]} for row in hours
                ]
            }
        )


class AdminOverviewView(APIView):
    """Organization-wide totals for the admin dashboard. Every number is
    computed from persisted records; each metric states its period."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from audit.models import AuditLog

        membership = _membership_or_none(request)
        if membership is None:
            return Response({"detail": "No organization membership."}, status=403)
        if membership.role != OrganizationMembership.Roles.ADMIN:
            return Response({"detail": "Administrator role required."}, status=403)
        org = membership.organization

        from accounts.models import User

        appointment_customers = Appointment.objects.filter(organization=org).values("customer")
        queue_customers = QueueEntry.objects.filter(organization=org).values("customer")
        total_customers = (
            User.objects.filter(
                models.Q(id__in=appointment_customers) | models.Q(id__in=queue_customers)
            )
            .filter(is_active=True)
            .count()
        )

        now = dj_timezone.now()
        business_date = local_business_date(org)
        today_entries = QueueEntry.objects.filter(organization=org, business_date=business_date)
        week_ago = now - timedelta(days=7)

        service_stats = []
        for service in org.services.filter(is_active=True):
            completed = QueueEntry.objects.filter(
                service=service, status=QueueEntry.Status.COMPLETED
            )
            avg_minutes = completed.filter(completed_at__isnull=False, completed_at__gte=F("started_at")).aggregate(
                v=Avg(F("completed_at") - F("started_at"))
            )["v"]
            service_stats.append(
                {
                    "service_id": service.id,
                    "service_name": service.name,
                    "completed_total": completed.count(),
                    "avg_service_minutes": round(avg_minutes.total_seconds() / 60, 1) if avg_minutes else None,
                    "waiting_now": QueueEntry.objects.filter(
                        service=service, status=QueueEntry.Status.WAITING
                    ).count(),
                }
            )

        recent_activity = AuditLog.objects.filter(organization=org).select_related("actor")[:8]

        return Response(
            {
                "total_customers": total_customers,
                "total_staff": org.memberships.filter(is_active=True).count(),
                "total_appointments": Appointment.objects.filter(organization=org).count(),
                "queue_volume_total": QueueEntry.objects.filter(organization=org).count(),
                "appointments_last_7_days": Appointment.objects.filter(
                    organization=org, created_at__gte=week_ago
                ).count(),
                "queue_joins_last_7_days": QueueEntry.objects.filter(
                    organization=org, joined_at__gte=week_ago
                ).count(),
                "today": {
                    "business_date": business_date.isoformat(),
                    "waiting": today_entries.filter(status=QueueEntry.Status.WAITING).count(),
                    "called": today_entries.filter(status=QueueEntry.Status.CALLED).count(),
                    "in_progress": today_entries.filter(status=QueueEntry.Status.IN_PROGRESS).count(),
                    "completed": today_entries.filter(status=QueueEntry.Status.COMPLETED).count(),
                    "no_show": today_entries.filter(status=QueueEntry.Status.NO_SHOW).count(),
                },
                "service_stats": service_stats,
                "recent_activity": [
                    {
                        "id": log.id,
                        "action": log.action,
                        "object_type": log.object_type,
                        "object_id": log.object_id,
                        "actor": log.actor.name or log.actor.email if log.actor else "system",
                        "created_at": log.created_at,
                    }
                    for log in recent_activity
                ],
            }
        )
