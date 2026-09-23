from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from core.models import Booking, Court, Role
from core.permissions import IsStaffRoleOrReadOnly
from core.serializers import BookingSerializer, CourtSerializer


class CourtViewSet(viewsets.ModelViewSet):
    queryset = Court.objects.all()
    serializer_class = CourtSerializer
    permission_classes = [IsStaffRoleOrReadOnly]


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
