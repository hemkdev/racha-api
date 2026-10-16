from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from core.models import (
    CLOSES_AT,
    OPENS_AT,
    Booking,
    BookingStatus,
    Court,
    Order,
    OrderStatus,
    Role,
    Sport,
    Tier,
)
from core.permissions import IsStaffRoleOrReadOnly
from core.serializers import BookingSerializer, CourtSerializer, OrderSerializer


def parse_date_param(value, param):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({param: "Expected date format: YYYY-MM-DD."})


def parse_period(start_str, end_str):
    start = parse_date_param(start_str, "from")
    end = parse_date_param(end_str, "to")
    if start and end and start > end:
        raise ValidationError({"to": "End date must not be before start date."})
    return start, end


PERIOD_PARAMETERS = [
    OpenApiParameter("from", OpenApiTypes.DATE),
    OpenApiParameter("to", OpenApiTypes.DATE),
]


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict"
    default_code = "conflict"


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("sport", str, enum=Sport.values),
            OpenApiParameter("tier", str, enum=Tier.values),
            OpenApiParameter("is_active", OpenApiTypes.BOOL),
        ]
    )
)
class CourtViewSet(viewsets.ModelViewSet):
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "hour_price"]
    ordering = ["name"]
    queryset = Court.objects.all()
    serializer_class = CourtSerializer
    permission_classes = [IsStaffRoleOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != "list":
            return queryset
        sport = self.request.query_params.get("sport")
        tier = self.request.query_params.get("tier")
        is_active = self.request.query_params.get("is_active")
        if sport:
            if sport not in Sport.values:
                raise ValidationError({"sport": "Invalid sport value."})
            queryset = queryset.filter(sports__contains=[sport])
        if tier:
            if tier not in Tier.values:
                raise ValidationError({"tier": "Invalid tier value."})
            queryset = queryset.filter(tier=tier)
        if is_active:
            if is_active.lower() not in ["true", "false"]:
                raise ValidationError({"is_active": "Invalid is_active value."})
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        return queryset

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "detail": "Cannot delete this court because it has associated bookings, deactivate it instead."
                },
                status=status.HTTP_409_CONFLICT,
            )

    def perform_update(self, serializer):
        if (
            serializer.validated_data.get("is_active") is False
            and serializer.instance.bookings.filter(
                status=BookingStatus.ACTIVE, starts_at__gt=timezone.now()
            ).exists()
        ):
            raise Conflict("Cannot deactivate a court with future bookings.")
        serializer.save()

    @extend_schema(
        parameters=[OpenApiParameter("date", OpenApiTypes.DATE, required=True)],
        responses=inline_serializer(
            "CourtSlots",
            {
                "court": serializers.IntegerField(),
                "date": serializers.DateField(),
                "slots": inline_serializer(
                    "Slot",
                    {
                        "starts_at": serializers.DateTimeField(),
                        "ends_at": serializers.DateTimeField(),
                        "available": serializers.BooleanField(),
                        "price": serializers.DecimalField(
                            max_digits=8, decimal_places=2
                        ),
                    },
                    many=True,
                ),
            },
        ),
    )
    @action(detail=True, methods=["get"])
    def slots(self, request, pk=None):
        court = self.get_object()
        if not court.is_active:
            return Response(
                {"detail": "No courts match the given query."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            value = request.query_params.get("date", "")
            value = date.fromisoformat(value)
        except ValueError:
            return Response(
                {"date": "Expected date format: YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tz = timezone.get_current_timezone()
        starts = [
            datetime.combine(value, time(hour), tzinfo=tz)
            for hour in range(OPENS_AT.hour, CLOSES_AT.hour)
        ]
        slot_duration = timedelta(hours=1)
        booked = set(
            Booking.objects.filter(
                court=court,
                status=BookingStatus.ACTIVE,
                starts_at__gte=starts[0],
                starts_at__lt=starts[-1] + slot_duration,
            ).values_list("starts_at", flat=True)
        )
        now = timezone.now()
        slots = [
            {
                "starts_at": start,
                "ends_at": start + slot_duration,
                "available": start not in booked and start > now,
                "price": str(court.price_at(start)),
            }
            for start in starts
        ]
        return Response({"court": court.id, "date": value.isoformat(), "slots": slots})


@extend_schema_view(list=extend_schema(parameters=PERIOD_PARAMETERS))
class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    filter_backends = [OrderingFilter]
    ordering_fields = [
        "court__name",
        "starts_at",
        "order__user__username",
        "created_by__username",
    ]
    ordering = ["starts_at", "-id"]
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsStaffRoleOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("order")
        user = self.request.user
        if user.role != Role.STAFF:
            queryset = queryset.filter(order__user=user)
        if self.action != "list":
            return queryset
        parsed_start, parsed_end = parse_period(
            self.request.query_params.get("from"), self.request.query_params.get("to")
        )
        if parsed_start:
            queryset = queryset.filter(starts_at__date__gte=parsed_start)
        if parsed_end:
            queryset = queryset.filter(starts_at__date__lte=parsed_end)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(request=None)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    @transaction.atomic
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.order:
            booking.order = Order.objects.select_for_update().get(pk=booking.order.pk)
            booking.refresh_from_db(fields=["status"])
        if booking.status != BookingStatus.ACTIVE:
            return Response(
                {"detail": "Only active bookings can be cancelled."},
                status=status.HTTP_409_CONFLICT,
            )
        if booking.order and booking.order.status != OrderStatus.PENDING:
            return Response(
                {
                    "detail": "Cannot cancel this booking because its associated order is not pending."
                },
                status=status.HTTP_409_CONFLICT,
            )
        if booking.starts_at <= timezone.now():
            return Response(
                {
                    "detail": "Cannot cancel this booking because it has already started."
                },
                status=status.HTTP_409_CONFLICT,
            )

        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=["status"])
        if (
            booking.order
            and not booking.order.bookings.filter(status=BookingStatus.ACTIVE).exists()
        ):
            booking.order.status = OrderStatus.CANCELLED
            booking.order.save(update_fields=["status"])
        booking = self.get_object()
        serializer = self.get_serializer(booking)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            *PERIOD_PARAMETERS,
            OpenApiParameter("status", str, enum=OrderStatus.values),
        ]
    )
)
class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    filter_backends = [OrderingFilter]
    ordering_fields = [
        "user__username",
        "status",
        "created_by__username",
        "created_at",
        "total",
    ]
    ordering = ["-created_at", "-id"]
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Order.objects.with_total().prefetch_related("bookings")
        user = self.request.user
        if user.role != Role.STAFF:
            queryset = queryset.filter(user=user)
        if self.action != "list":
            return queryset
        status_param = self.request.query_params.get("status")
        parsed_start, parsed_end = parse_period(
            self.request.query_params.get("from"), self.request.query_params.get("to")
        )
        if parsed_start:
            queryset = queryset.filter(created_at__date__gte=parsed_start)
        if parsed_end:
            queryset = queryset.filter(created_at__date__lte=parsed_end)
        if status_param:
            if status_param not in OrderStatus.values:
                raise ValidationError({"status": "Invalid status value."})
            queryset = queryset.filter(status=status_param)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(request=None)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRoleOrReadOnly])
    @transaction.atomic
    def confirm(self, request, pk=None):
        order = self.get_object()
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != OrderStatus.PENDING:
            return Response(
                {"detail": "Only pending orders can be confirmed."},
                status=status.HTTP_409_CONFLICT,
            )

        order.status = OrderStatus.PAID
        order.save(update_fields=["status"])
        order = self.get_object()
        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancel(self, request, pk=None):
        order = self.get_object()
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != OrderStatus.PENDING:
            return Response(
                {"detail": "Only pending orders can be cancelled."},
                status=status.HTTP_409_CONFLICT,
            )
        if (
            order.bookings.filter(status=BookingStatus.ACTIVE)
            .filter(starts_at__lte=timezone.now())
            .exists()
        ):
            return Response(
                {
                    "detail": "Cannot cancel this order because it has active bookings that have already started."
                },
                status=status.HTTP_409_CONFLICT,
            )
        order.status = OrderStatus.CANCELLED
        order.save(update_fields=["status"])
        order.bookings.filter(status=BookingStatus.ACTIVE).update(
            status=BookingStatus.CANCELLED
        )
        order = self.get_object()
        serializer = self.get_serializer(order)
        return Response(serializer.data)


class TokenView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"
