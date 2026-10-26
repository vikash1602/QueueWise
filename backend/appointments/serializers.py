from rest_framework import serializers

from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    queue_token = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id", "organization", "organization_name", "service", "service_name",
            "customer", "customer_email", "slot_start", "slot_end", "status",
            "queue_token", "cancel_reason", "created_at",
        ]
        read_only_fields = fields

    def get_queue_token(self, obj):
        qe = getattr(obj, "queue_entry", None)
        return qe.token_number if qe else None


class CreateAppointmentSerializer(serializers.Serializer):
    service = serializers.IntegerField()
    slot_start = serializers.DateTimeField()
