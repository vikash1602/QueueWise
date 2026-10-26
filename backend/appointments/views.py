from django.shortcuts import get_object_or_404
from django.utils import timezone as dj_timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record as audit_record
from notifications import services as notification_service
from organizations.models import Service
from organizations.permissions import membership_for
from queues.exceptions import QueueWiseError

from .models import Appointment
from .serializers import AppointmentSerializer, CreateAppointmentSerializer
from . import services as booking

LIVE_STATUSES = [Appointment.Status.CONFIRMED, Appointment.Status.CHECKED_IN]


class AppointmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Appointment.objects.filter(customer=request.user)
            .select_related("service", "organization", "customer")
            .order_by("-slot_start")
        )
        scope = request.query_params.get("scope")
        if scope == "upcoming":
            qs = qs.filter(status__in=LIVE_STATUSES, slot_start__gte=dj_timezone.now())
        elif scope == "past":
            qs = qs.exclude(status__in=LIVE_STATUSES)
        return Response(AppointmentSerializer(qs, many=True).data)

    def post(self, request):
        serializer = CreateAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = get_object_or_404(
            Service, pk=serializer.validated_data["service"], is_active=True
        )
        if not service.is_appointment_enabled:
            return Response(
                {"detail": "This service does not accept appointments."}, status=400
            )
        try:
            appointment = booking.book(
                customer=request.user,
                service=service,
                slot_start=serializer.validated_data["slot_start"],
            )
        except QueueWiseError as exc:
            return Response({"detail": str(exc)}, status=409)
        audit_record(
            actor=request.user,
            organization=appointment.organization,
            action="APPOINTMENT_CREATED",
            object_type="appointment",
            object_id=appointment.id,
            detail={"service_id": service.id, "slot_start": appointment.slot_start.isoformat()},
        )
        notification_service.create(
            user=request.user,
            type=notification_service.Notification.Types.BOOKING_CONFIRMED,
            title="Appointment confirmed",
            body=f"{service.name} on {appointment.slot_start:%Y-%m-%d %H:%M} (UTC).",
            payload={"appointment_id": appointment.id},
        )
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)


class AppointmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, pk=appointment_id)
        if not (
            appointment.customer_id == request.user.id
            or membership_for(request.user, appointment.organization)
        ):
            return Response({"detail": "Not found."}, status=404)
        return Response(AppointmentSerializer(appointment).data)


class AppointmentCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, pk=appointment_id)
        is_owner = appointment.customer_id == request.user.id
        is_staff = bool(membership_for(request.user, appointment.organization))
        if not (is_owner or is_staff):
            return Response({"detail": "Not found."}, status=404)
        try:
            appointment = booking.cancel(
                appointment,
                cancelled_by=request.user,
                reason=request.data.get("reason", ""),
            )
        except QueueWiseError as exc:
            return Response({"detail": str(exc)}, status=409)
        audit_record(
            actor=request.user,
            organization=appointment.organization,
            action="APPOINTMENT_CANCELLED",
            object_type="appointment",
            object_id=appointment.id,
            detail={"by": "customer" if is_owner else "staff"},
        )
        notification_service.create(
            user=appointment.customer,
            type=notification_service.Notification.Types.BOOKING_CANCELLED,
            title="Appointment cancelled",
            body=f"Your {appointment.service.name} appointment on "
            f"{appointment.slot_start:%Y-%m-%d %H:%M} (UTC) was cancelled.",
            payload={"appointment_id": appointment.id},
        )
        return Response(AppointmentSerializer(appointment).data)
