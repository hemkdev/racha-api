from rest_framework.routers import DefaultRouter

from core.views import CourtViewSet

router = DefaultRouter()
router.register("courts", CourtViewSet)

urlpatterns = router.urls
