from datetime import date

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.services import availability as slot_availability

from .models import BusinessHours, Organization, OrganizationMembership, Service
from .serializers import (
    AdminServiceSerializer,
    BusinessHoursSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    PublicOrganizationSerializer,
    ServiceSerializer,
)


class PublicOrganizationListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = Organization.objects.filter(is_active=True).prefetch_related("services")
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(
                services__name__icontains=search
            ).distinct()
        orgs = [PublicOrganizationSerializer(o).data for o in qs]
        return Response({"results": orgs})


class PublicOrganizationDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, org_id):
        org = get_object_or_404(Organization, pk=org_id, is_active=True)
        hours = BusinessHoursSerializer(org.business_hours.all(), many=True).data
        profile_incomplete = (
            org.name == "My Organization"
            or not org.address.strip()
            or not org.contact_phone.strip()
        )
        return Response(
            {
                **PublicOrganizationSerializer(org).data,
                "profile_incomplete": profile_incomplete,
                "business_hours": hours,
                "services": ServiceSerializer(
                    org.services.filter(is_active=True), many=True
                ).data,
            }
        )


class PublicAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, org_id):
        org = get_object_or_404(Organization, pk=org_id, is_active=True)
        service = get_object_or_404(
            Service, pk=request.query_params.get("service"), organization=org, is_active=True
        )
        day_param = request.query_params.get("date")
        try:
            day = date.fromisoformat(day_param) if day_param else date.today()
        except ValueError:
            return Response({"detail": "Invalid date; use YYYY-MM-DD."}, status=400)
        slots = slot_availability(org, service, day)
        return Response(
            {
                "service_id": service.id,
                "date": day.isoformat(),
                "slots": [
                    {
                        "slot_start": s["slot_start"],
                        "slot_end": s["slot_end"],
                        "is_available": s["is_available"],
                    }
                    for s in slots
                ],
            }
        )


class MyOrgMixin:
    """Resolves the organization the member is operating on. A user with
    several memberships passes ?org=<id>; otherwise their first membership
    is used."""

    required_role = None  # None => any active member

    def resolve_membership(self, request):
        memberships = OrganizationMembership.objects.filter(
            user=request.user, is_active=True
        ).select_related("organization")
        org_id = request.query_params.get("org")
        if org_id:
            membership = memberships.filter(organization_id=org_id).first()
        else:
            membership = memberships.order_by("id").first()
        if membership is None:
            return None
        if self.required_role and membership.role != self.required_role:
            return None
        return membership


class MyOrganizationView(MyOrgMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = self.resolve_membership(request)
        if membership is None:
            return Response({"detail": "No organization membership."}, status=403)
        org = membership.organization
        return Response(
            {
                **OrganizationSerializer(org).data,
                "role": membership.role,
                "business_hours": BusinessHoursSerializer(
                    org.business_hours.all(), many=True
                ).data,
            }
        )

    def put(self, request):
        membership = self.resolve_membership(request)
        if membership is None or membership.role != OrganizationMembership.Roles.ADMIN:
            return Response({"detail": "Administrator role required."}, status=403)
        serializer = OrganizationSerializer(
            membership.organization, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MyServicesViewSet(MyOrgMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = self.resolve_membership(request)
        if membership is None:
            return Response({"detail": "No organization membership."}, status=403)
        qs = Service.objects.filter(organization=membership.organization).prefetch_related(
            "counters"
        )
        return Response(AdminServiceSerializer(qs, many=True).data)

    def _require_admin(self, request):
        membership = self.resolve_membership(request)
        if membership is None or membership.role != OrganizationMembership.Roles.ADMIN:
            return None
        return membership

    def post(self, request):
        membership = self._require_admin(request)
        if membership is None:
            return Response({"detail": "Administrator role required."}, status=403)
        serializer = AdminServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=membership.organization)
        return Response(serializer.data, status=201)

    def patch(self, request, service_id=None):
        membership = self._require_admin(request)
        if membership is None:
            return Response({"detail": "Administrator role required."}, status=403)
        service = get_object_or_404(
            Service, pk=service_id, organization=membership.organization
        )
        serializer = AdminServiceSerializer(service, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, service_id=None):
        membership = self._require_admin(request)
        if membership is None:
            return Response({"detail": "Administrator role required."}, status=403)
        service = get_object_or_404(
            Service, pk=service_id, organization=membership.organization
        )
        service.is_active = False
        service.save(update_fields=["is_active", "updated_at"])
        return Response(status=204)


class MyBusinessHoursView(MyOrgMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = self.resolve_membership(request)
        if membership is None:
            return Response({"detail": "No organization membership."}, status=403)
        return Response(
            BusinessHoursSerializer(membership.organization.business_hours.all(), many=True).data
        )

    def put(self, request):
        """Replace the whole weekly schedule (one entry per weekday 0-6)."""
        membership = self.resolve_membership(request)
        if membership is None or membership.role != OrganizationMembership.Roles.ADMIN:
            return Response({"detail": "Administrator role required."}, status=403)
        data = request.data if isinstance(request.data, list) else request.data.get("hours")
        serializer = BusinessHoursSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=True)
        weekdays = {item["weekday"] for item in serializer.validated_data}
        if weekdays != set(range(7)):
            return Response(
                {"detail": "Provide exactly one entry per weekday (0-6)."}, status=400
            )
        org = membership.organization
        try:
            with transaction.atomic():
                org.business_hours.all().delete()
                BusinessHours.objects.bulk_create(
                    BusinessHours(organization=org, **item)
                    for item in serializer.validated_data
                )
        except IntegrityError:
            return Response({"detail": "Invalid schedule."}, status=400)
        return Response(BusinessHoursSerializer(org.business_hours.all(), many=True).data)


class MyStaffView(MyOrgMixin, APIView):
    """Staff membership management for organization administrators."""

    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        membership = self.resolve_membership(request)
        if membership is None or membership.role != OrganizationMembership.Roles.ADMIN:
            return None
        return membership

    def get(self, request):
        membership = self.resolve_membership(request)
        if membership is None:
            return Response({"detail": "No organization membership."}, status=403)
        qs = OrganizationMembership.objects.filter(
            organization=membership.organization
        ).select_related("user")
        return Response(MembershipSerializer(qs, many=True).data)

    def post(self, request):
        membership = self._require_admin(request)
        if membership is None:
            return Response({"detail": "Administrator role required."}, status=403)
        email = (request.data.get("email") or "").strip().lower()
        role = request.data.get("role")
        if role not in OrganizationMembership.Roles.values:
            return Response({"detail": "role must be ADMIN or STAFF."}, status=400)
        from accounts.models import User

        target = User.objects.filter(email=email).first()
        if target is None:
            return Response({"detail": "No platform user with that email."}, status=400)
        if OrganizationMembership.objects.filter(
            organization=membership.organization, user=target
        ).exists():
            return Response({"detail": "User is already a member."}, status=409)
        m = OrganizationMembership.objects.create(
            organization=membership.organization, user=target, role=role
        )
        return Response(MembershipSerializer(m).data, status=201)

    def patch(self, request, member_id=None):
        membership = self._require_admin(request)
        if membership is None:
            return Response({"detail": "Administrator role required."}, status=403)
        target = get_object_or_404(
            OrganizationMembership, pk=member_id, organization=membership.organization
        )
        role = request.data.get("role")
        is_active = request.data.get("is_active")
        if role is not None:
            if role not in OrganizationMembership.Roles.values:
                return Response({"detail": "Invalid role."}, status=400)
            target.role = role
        if is_active is not None:
            target.is_active = bool(is_active)
        target.save()
        return Response(MembershipSerializer(target).data)


class MyCustomersView(MyOrgMixin, APIView):
    """Admin-only, read-only customer directory: platform users who have
    appointments or queue entries at this organization. Passwords and other
    sensitive fields are never exposed."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = self.resolve_membership(request)
        if membership is None:
            return Response({"detail": "No organization membership."}, status=403)
        if membership.role != OrganizationMembership.Roles.ADMIN:
            return Response({"detail": "Administrator role required."}, status=403)
        org = membership.organization

        from accounts.models import User
        from appointments.models import Appointment
        from django.db.models import Count, Max, Q
        from queues.models import QueueEntry

        appt = Appointment.objects.filter(organization=org)
        queue = QueueEntry.objects.filter(organization=org)
        users = (
            User.objects.filter(
                Q(id__in=appt.values("customer")) | Q(id__in=queue.values("customer")),
                is_active=True,
            )
            .annotate(
                appointment_count=Count("appointments", filter=Q(appointments__organization=org), distinct=True),
                queue_count=Count("queue_entries", filter=Q(queue_entries__organization=org), distinct=True),
                last_visit=Max("queue_entries__joined_at", filter=Q(queue_entries__organization=org)),
            )
            .order_by("name", "email")
        )

        search = request.query_params.get("search")
        if search:
            users = users.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )

        try:
            page = max(1, int(request.query_params.get("page", "1")))
        except ValueError:
            page = 1
        page_size = 20
        total = users.count()
        rows = users[(page - 1) * page_size : page * page_size]
        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": [
                    {
                        "id": u.id,
                        "name": u.name,
                        "email": u.email,
                        "phone": u.phone,
                        "appointment_count": u.appointment_count,
                        "queue_count": u.queue_count,
                        "last_visit": u.last_visit,
                    }
                    for u in rows
                ],
            }
        )
