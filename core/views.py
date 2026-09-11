# Create your views here.

from rest_framework import viewsets

from core.models import Court
from core.serializers import CourtSerializer


class CourtViewSet(viewsets.ModelViewSet):
    queryset = Court.objects.all()
    serializer_class = CourtSerializer
