from datetime import date, datetime, time, timedelta

from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import CLOSES_AT, OPENS_AT, Booking, BookingStatus, Court, Role
from core.permissions import IsStaffRoleOrReadOnly
from core.serializers import BookingSerializer, CourtSerializer


class CourtViewSet(viewsets.ModelViewSet):
    queryset = Court.objects.all()
    serializer_class = CourtSerializer
    permission_classes = [IsStaffRoleOrReadOnly]

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
        slots = [
            {
                "starts_at": start,
                "ends_at": start + slot_duration,
                "available": start not in booked,
            }
            for start in starts
        ]
        return Response({"court": court.id, "date": value.isoformat(), "slots": slots})


class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role == Role.STAFF:
            return queryset
        return queryset.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
