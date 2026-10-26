from .models import AuditLog


def record(*, actor=None, organization=None, action, object_type, object_id="", detail=None):
    """Append an audit record. Returns the AuditLog instance.

    Kept deliberately small and side-effect free so it can be called from any
    transaction; failures must not mask the business operation, so callers wrap
    it inside the same atomic block and let integrity errors surface in tests.
    """
    return AuditLog.objects.create(
        actor=actor,
        organization=organization,
        action=action,
        object_type=object_type,
        object_id=str(object_id or ""),
        detail=detail or {},
    )
