from django.shortcuts import get_object_or_404
from django.utils import timezone as dj_timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment
from audit.services import record as audit_record
from organizations.models import Organization, OrganizationMembership, Service
from organizations.services import local_business_date

from .exceptions import QueueWiseError
from .models import QueueEntry
from .serializers import (
    CustomerQueueStatusSerializer,
    QueueEntrySerializer,
    StaffWalkInSerializer,
)
from . import services as queue_services
from . import workflow


def _require_membership(request, org=None):
    """Return (membership, error_response) for the requester, optionally
    scoped to one organization."""
    org_id = request.query_params.get("org") if org is None else org
    qs = OrganizationMembership.objects.filter(user=request.user, is_active=True)
    if org_id:
        membership = qs.filter(organization_id=org_id).first()
    else:
        membership = qs.order_by("id").first()
    if membership is None:
        return None, Response(
            {"detail": "Active organization membership required."}, status=403
        )
    return membership, None


class MyQueueEntriesView(APIView):
    """Customer: list own queue entries (active and past)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = QueueEntry.objects.filter(customer=request.user).select_related(
            "service", "organization"
        )
        scope = request.query_params.get("scope")
        if scope == "active":
            qs = qs.filter(status__in=[QueueEntry.Status.WAITING, QueueEntry.Status.CALLED])
        return Response(QueueEntrySerializer(qs.order_by("-joined_at"), many=True).data)

    def post(self, request):
        """Customer joins a walk-in queue for a service."""
        service_id = request.data.get("service")
        service = get_object_or_404(Service, pk=service_id, is_active=True)
        if not service.is_walkin_enabled:
            return Response({"detail": "Walk-in is not enabled for this service."}, status=400)
        try:
            entry = workflow.join_queue(
                organization=service.organization, service=service, customer=request.user
            )
        except QueueWiseError as exc:
            return Response({"detail": str(exc)}, status=409)
        audit_record(
            actor=request.user,
            organization=entry.organization,
            action="QUEUE_JOINED",
            object_type="queue_entry",
            object_id=entry.id,
            detail={"token": entry.token_number, "service_id": service.id},
        )
        return Response(QueueEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class MyQueueEntryStatusView(APIView):
    """Customer: live status for one of their entries (polling endpoint)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, entry_id):
        entry = get_object_or_404(
            QueueEntry.objects.select_related("service", "organization"),
            pk=entry_id,
        )
        if entry.customer_id != request.user.id:
            return Response({"detail": "Not found."}, status=404)
        entry.position = queue_services.position_of(entry)
        data = CustomerQueueStatusSerializer(entry).data
        data["service_name"] = entry.service.name
        data["organization_name"] = entry.organization.name
        data["business_date"] = entry.business_date.isoformat()
        data["updated_at"] = dj_timezone.now()
        return Response(data)


class MyQueueEntryCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, entry_id):
        entry = get_object_or_404(QueueEntry, pk=entry_id)
        if entry.customer_id != request.user.id:
            return Response({"detail": "Not found."}, status=404)
        try:
            entry = workflow.cancel_by_customer(entry, actor=request.user)
        except QueueWiseError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(QueueEntrySerializer(entry).data)


class StaffQueueTodayView(APIView):
    """Staff: today's queue for their organization, filterable by service."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership, err = _require_membership(request)
        if err:
            return err
        org = membership.organization
        business_date = local_business_date(org)
        qs = QueueEntry.objects.filter(
            organization=org, business_date=business_date
        ).select_related("service", "customer", "counter")
        service_id = request.query_params.get("service")
        if service_id:
            qs = qs.filter(service_id=service_id)
        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        search = request.query_params.get("search")
        if search:
            from django.db.models import Q

            qs = qs.filter(
                Q(guest_name__icontains=search)
                | Q(customer__email__icontains=search)
                | Q(customer__name__icontains=search)
            )
        return Response(
            {
                "business_date": business_date.isoformat(),
                "results": QueueEntrySerializer(qs.order_by("service", "token_number"), many=True).data,
            }
        )


class StaffWalkInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        membership, err = _require_membership(request)
        if err:
            return err
        serializer = StaffWalkInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = get_object_or_404(
            Service,
            pk=serializer.validated_data["service"],
            organization=membership.organization,
            is_active=True,
        )
        try:
            entry = workflow.join_queue(
                organization=membership.organization,
                service=service,
                customer=None,
                guest_name=serializer.validated_data.get("guest_name", ""),
            )
        except QueueWiseError as exc:
            return Response({"detail": str(exc)}, status=409)
        audit_record(
            actor=request.user,
            organization=membership.organization,
            action="WALKIN_REGISTERED",
            object_type="queue_entry",
            object_id=entry.id,
            detail={"token": entry.token_number, "service_id": service.id},
        )
        return Response(QueueEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class StaffCheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appointment_id):
        membership, err = _require_membership(request)
        if err:
            return err
        appointment = get_object_or_404(
            Appointment, pk=appointment_id, organization=membership.organization
        )
        try:
            entry = workflow.check_in_appointment(appointment, actor=request.user)
        except QueueWiseError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(QueueEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class StaffCallNextView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        membership, err = _require_membership(request)
        if err:
            return err
        service = get_object_or_404(
            Service, pk=request.data.get("service"), organization=membership.organization
        )
        try:
            entry = workflow.call_next(
                organization=membership.organization,
                service=service,
                actor=request.user,
            )
        except QueueWiseError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(QueueEntrySerializer(entry).data)


class StaffEntryActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, entry_id, action):
        membership, err = _require_membership(request)
        if err:
            return err
        entry = get_object_or_404(
            QueueEntry, pk=entry_id, organization=membership.organization
        )
        try:
            entry = workflow.perform_staff_action(
                entry=entry, action=action, actor=request.user
            )
        except QueueWiseError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(QueueEntrySerializer(entry).data)


class StaffHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership, err = _require_membership(request)
        if err:
            return err
        org = membership.organization
        business_date = local_business_date(org)
        qs = QueueEntry.objects.filter(organization=org).select_related(
            "service", "customer"
        )
        day = request.query_params.get("date")
        if day:
            from datetime import date as date_cls

            try:
                qs = qs.filter(business_date=date_cls.fromisoformat(day))
            except ValueError:
                return Response({"detail": "Invalid date."}, status=400)
        else:
            qs = qs.filter(business_date=business_date)
        closed = qs.exclude(
            status__in=[QueueEntry.Status.WAITING, QueueEntry.Status.CALLED]
        )
        return Response(
            QueueEntrySerializer(
                closed.order_by("-completed_at", "-token_number")[:100], many=True
            ).data
        )


class PublicNowServingView(APIView):
    """Public display: current token per service. Exposes no personal data."""

    permission_classes = []

    def get(self, request, org_id):
        org = get_object_or_404(Organization, pk=org_id, is_active=True)
        business_date = local_business_date(org)
        qs = QueueEntry.objects.filter(
            organization=org,
            business_date=business_date,
            status__in=[QueueEntry.Status.CALLED, QueueEntry.Status.IN_PROGRESS],
        ).select_related("service")
        services = Service.objects.filter(organization=org, is_active=True)
        result = []
        for service in services:
            entries = [e for e in qs if e.service_id == service.id]
            result.append(
                {
                    "service_id": service.id,
                    "service_name": service.name,
                    "now_serving": [e.token_number for e in entries],
                    "waiting_count": QueueEntry.objects.filter(
                        organization=org,
                        service=service,
                        business_date=business_date,
                        status=QueueEntry.Status.WAITING,
                    ).count(),
                }
            )
        return Response({"business_date": business_date.isoformat(), "services": result})
