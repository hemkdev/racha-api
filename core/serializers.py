from datetime import timedelta

from django.db import IntegrityError, transaction
from rest_framework import serializers

from core.models import (
    CLOSES_AT,
    OPENS_AT,
    Booking,
    BookingKind,
    BookingStatus,
    Court,
    Order,
    Role,
)


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
            "order",
            "price_charged",
        ]
        read_only_fields = [
            "id",
            "ends_at",
            "status",
            "created_by",
            "order",
            "price_charged",
        ]

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
        kind = attrs.get("kind", BookingKind.CUSTOMER)
        reason = attrs.get("reason", "")
        if kind == BookingKind.CUSTOMER:
            raise serializers.ValidationError(
                {"kind": "Customer bookings must be created through orders."}
            )
        elif not reason:
            raise serializers.ValidationError(
                {"reason": "Reason must be provided for maintenance bookings."}
            )
        elif attrs.get("user"):
            raise serializers.ValidationError(
                {"user": "User must be empty for maintenance bookings."}
            )
        return attrs


class ItemSerializer(BookingSerializer):
    class Meta(BookingSerializer.Meta):
        fields = ["court", "price_charged", "starts_at", "ends_at"]
        read_only_fields = ["ends_at", "price_charged"]
        extra_kwargs = {
            "court": {"queryset": Court.objects.filter(is_active=True)},
        }

    def validate(self, attrs):
        attrs["ends_at"] = attrs["starts_at"] + timedelta(hours=1)
        exists = Booking.objects.filter(
            court=attrs["court"],
            starts_at=attrs["starts_at"],
            status=BookingStatus.ACTIVE,
        ).exists()
        if exists:
            raise serializers.ValidationError(
                {
                    "starts_at": "This court is already booked for the selected time slot."
                }
            )
        return attrs


class OrderSerializer(serializers.ModelSerializer):
    bookings = ItemSerializer(many=True, allow_empty=False)

    class Meta:
        model = Order
        fields = ["id", "user", "bookings", "status", "created_by"]
        read_only_fields = ["id", "status", "created_by"]
        extra_kwargs = {"user": {"required": False}}

    def validate(self, attrs):
        requester = self.context["request"].user
        if requester.role == Role.STAFF and (
            ("user" not in attrs) or (attrs["user"].role != Role.CUSTOMER)
        ):
            raise serializers.ValidationError(
                {"user": "Staff must specify a customer for the order."}
            )
        elif requester.role == Role.CUSTOMER and "user" in attrs:
            raise serializers.ValidationError(
                {"user": "Customers can only create orders for themselves."}
            )
        attrs["user"] = attrs.get("user", requester)
        return attrs

    def validate_bookings(self, value):
        slots = []
        for booking in value:
            slots.append((booking["court"], booking["starts_at"]))
        if len(slots) != len(set(slots)):
            raise serializers.ValidationError(
                "Duplicate bookings for the same court and time slot are not allowed."
            )
        return value

    def create(self, validated_data):
        bookings_data = validated_data.pop("bookings")
        with transaction.atomic():
            order = Order.objects.create(**validated_data)
            for index, booking_data in enumerate(bookings_data):
                price_charged = booking_data["court"].price_at(
                    booking_data["starts_at"]
                )
                try:
                    with transaction.atomic():
                        Booking.objects.create(
                            **booking_data,
                            order=order,
                            user=order.user,
                            created_by=order.created_by,
                            kind=BookingKind.CUSTOMER,
                            price_charged=price_charged,
                        )
                except IntegrityError:
                    raise serializers.ValidationError(
                        {
                            "bookings": {
                                index: {
                                    "starts_at": "This court is already booked for the selected time slot."
                                }
                            }
                        }
                    )
        return order
