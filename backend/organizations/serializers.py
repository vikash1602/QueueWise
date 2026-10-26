from rest_framework import serializers

from .models import BusinessHours, Organization, Service, ServiceCounter


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = [
            "id", "name", "description", "duration_minutes", "buffer_minutes",
            "is_appointment_enabled", "is_walkin_enabled", "max_advance_days",
            "is_active",
        ]


class AdminServiceSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Service
        fields = ServiceSerializer.Meta.fields + ["organization"]


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "description", "contact_email", "contact_phone",
            "address", "timezone", "is_active",
        ]
        read_only_fields = ["slug"]


class PublicOrganizationSerializer(serializers.ModelSerializer):
    services_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "description", "address", "contact_phone",
            "services_count",
        ]


class BusinessHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessHours
        fields = ["weekday", "opens_at", "closes_at", "is_closed"]


class ServiceCounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCounter
        fields = ["id", "service", "name", "is_active"]


class MembershipSerializer(serializers.Serializer):
    """Read representation of organization staff."""

    id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.CharField(source="user.name", read_only=True)
    role = serializers.CharField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField(read_only=True)
