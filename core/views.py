# Create your views here.

from rest_framework import viewsets

from core.models import Booking, Court
from core.serializers import BookingSerializer, CourtSerializer


class CourtViewSet(viewsets.ModelViewSet):
    queryset = Court.objects.all()
    serializer_class = CourtSerializer


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
