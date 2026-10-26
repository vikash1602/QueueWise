from rest_framework import serializers

from .models import QueueEntry


class QueueEntrySerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = QueueEntry
        fields = [
            "id", "organization", "organization_name", "service", "service_name",
            "source", "token_number", "business_date", "status", "counter",
            "estimated_wait_minutes", "joined_at", "called_at", "started_at",
            "completed_at", "display_name",
        ]
        read_only_fields = fields

    def get_display_name(self, obj):
        if obj.customer_id:
            return obj.customer.get_full_name() or obj.customer.email
        return obj.guest_name or "Guest"


class CustomerQueueStatusSerializer(serializers.Serializer):
    """Customer-facing live status: no other customers' personal data."""

    id = serializers.IntegerField()
    token_number = serializers.IntegerField()
    status = serializers.CharField()
    position = serializers.IntegerField()
    people_ahead = serializers.SerializerMethodField()
    estimated_wait_minutes = serializers.IntegerField()
    now_serving = serializers.SerializerMethodField()

    def get_people_ahead(self, obj):
        return max(obj.position - 1, 0)

    def get_now_serving(self, obj):
        return list(
            QueueEntry.objects.filter(
                organization=obj.organization,
                service=obj.service,
                business_date=obj.business_date,
                status__in=[QueueEntry.Status.CALLED, QueueEntry.Status.IN_PROGRESS],
            )
            .order_by("token_number")
            .values_list("token_number", flat=True)
        )


class StaffWalkInSerializer(serializers.Serializer):
    service = serializers.IntegerField()
    guest_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
