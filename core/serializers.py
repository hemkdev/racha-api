from datetime import timedelta

from rest_framework import serializers

from core.models import Booking, Court, Role


class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ["id", "name", "sport", "tier", "hour_price", "is_active"]
        read_only_fields = ["id", "is_active"]


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ["id", "court", "starts_at", "ends_at", "created_by", "user", "status"]
        read_only_fields = ["id", "ends_at", "status", "created_by"]

    def validate_starts_at(self, value):
        if value.minute != 0 or value.second != 0 or value.microsecond != 0:
            raise serializers.ValidationError(
                "Booking must start at the beginning of an hour."
            )
        return value

    def validate(self, attrs):
        if "starts_at" in attrs:
            attrs["ends_at"] = attrs["starts_at"] + timedelta(hours=1)
        request = self.context["request"]
        if request.user.role != Role.STAFF:
            if "user" in attrs:
                raise serializers.ValidationError(
                    {"user": "You cannot set the user for this booking."}
                )
            attrs["user"] = request.user
        return attrs
