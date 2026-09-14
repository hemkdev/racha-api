from rest_framework.routers import DefaultRouter

from core.views import BookingViewSet, CourtViewSet

router = DefaultRouter()
router.register("courts", CourtViewSet)
router.register("bookings", BookingViewSet)

urlpatterns = router.urls
