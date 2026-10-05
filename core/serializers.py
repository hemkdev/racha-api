from datetime import timedelta

from rest_framework import serializers

from core.models import CLOSES_AT, OPENS_AT, Booking, BookingKind, Court, Role


class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ["id", "name", "sport", "tier", "hour_price", "is_active"]
        read_only_fields = ["id"]


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            "id",
            "court",
            "starts_at",
            "ends_at",
            "created_by",
            "user",
            "status",
            "kind",
            "reason",
        ]
        read_only_fields = ["id", "ends_at", "status", "created_by"]

    def validate_starts_at(self, value):
        if value.hour < OPENS_AT.hour or value.hour >= CLOSES_AT.hour:
            raise serializers.ValidationError(
                f"Booking must be in working hours ({OPENS_AT.hour}:00-{CLOSES_AT.hour}:00)."
            )
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
            elif "kind" in attrs:
                raise serializers.ValidationError(
                    {"kind": "You cannot set the kind for this booking."}
                )
            elif "reason" in attrs:
                raise serializers.ValidationError(
                    {"reason": "You cannot set the reason for this booking."}
                )
            attrs["user"] = request.user
        kind = attrs.get("kind", BookingKind.CUSTOMER)
        reason = attrs.get("reason", "")
        if kind == BookingKind.CUSTOMER and reason:
            raise serializers.ValidationError(
                {"reason": "Reason must be empty for customer bookings."}
            )
        elif kind == BookingKind.MAINTENANCE and not reason:
            raise serializers.ValidationError(
                {"reason": "Reason must be provided for maintenance bookings."}
            )
        elif kind == BookingKind.MAINTENANCE and attrs.get("user"):
            raise serializers.ValidationError(
                {"user": "User must be empty for maintenance bookings."}
            )
        elif kind == BookingKind.CUSTOMER and not attrs.get("user"):
            raise serializers.ValidationError(
                {"user": "User must be provided for customer bookings."}
            )
        return attrs
