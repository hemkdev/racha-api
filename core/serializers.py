from rest_framework import serializers

from core.models import Booking, Court


class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ["id", "name", "sport", "tier", "hour_price", "is_active"]
        read_only_fields = ["id", "is_active"]


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ["id", "court", "starts_at", "ends_at", "created_by", "status"]
        read_only_fields = ["id", "status"]
