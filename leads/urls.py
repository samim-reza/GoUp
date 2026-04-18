from rest_framework.routers import DefaultRouter

from leads.views import LeadViewSet


router = DefaultRouter()
router.register("", LeadViewSet, basename="lead")

urlpatterns = router.urls
