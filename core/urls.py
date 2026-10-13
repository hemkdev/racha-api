from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from core.views import BookingViewSet, CourtViewSet, OrderViewSet, TokenView

router = DefaultRouter()
router.register("courts", CourtViewSet)
router.register("bookings", BookingViewSet)
router.register("orders", OrderViewSet)

urlpatterns = [
    *router.urls,
    path("token/", TokenView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
