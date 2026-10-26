"""Reusable DRF permission classes. Organization authorization always flows
through OrganizationMembership — client-supplied state is never trusted."""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import OrganizationMembership


def membership_for(user, organization):
    if not user or not user.is_authenticated:
        return None
    return OrganizationMembership.objects.filter(
        organization=organization, user=user, is_active=True
    ).first()


class IsAuthenticatedCustomer(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsOrgAdmin(BasePermission):
    """Object must expose `organization`; allows only its active admins."""

    def has_object_permission(self, request, view, obj):
        org = getattr(obj, "organization", obj)
        m = membership_for(request.user, org)
        return bool(m and m.role == OrganizationMembership.Roles.ADMIN)


class IsOrgStaff(BasePermission):
    """Allows active admins or staff of the object's organization."""

    def has_object_permission(self, request, view, obj):
        org = getattr(obj, "organization", obj)
        m = membership_for(request.user, org)
        return bool(m)


class IsOwnerOrOrgStaff(BasePermission):
    """Customers may act on their own objects; org staff on any object of
    their organization (e.g. staff-registered guest walk-ins)."""

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_authenticated:
            if getattr(obj, "customer_id", None) == request.user.id:
                return True
        org = getattr(obj, "organization", obj)
        return bool(membership_for(request.user, org))
