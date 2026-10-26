from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import OrganizationMembership
from organizations.services import local_business_date


def _admin_membership(request):
    org_id = request.query_params.get("org")
    qs = OrganizationMembership.objects.filter(user=request.user, is_active=True)
    membership = qs.filter(organization_id=org_id).first() if org_id else qs.order_by("id").first()
    if membership is None or membership.role != OrganizationMembership.Roles.ADMIN:
        return None
    return membership


class AuditLogListView(APIView):
    """Organization administrators can review their own organization's audit
    history. Platform administrators use the Django admin instead."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = _admin_membership(request)
        if membership is None:
            return Response(
                {"detail": "Administrator role required."}, status=403
            )
        from audit.models import AuditLog

        qs = AuditLog.objects.filter(organization=membership.organization).select_related(
            "actor"
        )
        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)
        try:
            limit = min(int(request.query_params.get("limit", "100")), 500)
        except ValueError:
            limit = 100
        return Response(
            {
                "results": [
                    {
                        "id": log.id,
                        "action": log.action,
                        "object_type": log.object_type,
                        "object_id": log.object_id,
                        "detail": log.detail,
                        "actor_email": log.actor.email if log.actor else None,
                        "created_at": log.created_at,
                    }
                    for log in qs[:limit]
                ]
            }
        )
