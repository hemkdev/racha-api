from django.db.models import ProtectedError
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Booking, Court, Role
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
