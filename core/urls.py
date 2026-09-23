from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.views import BookingViewSet, CourtViewSet

router = DefaultRouter()
router.register("courts", CourtViewSet)
router.register("bookings", BookingViewSet)

urlpatterns = [
    *router.urls,
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
